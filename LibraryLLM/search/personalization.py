"""Opt-in saved-book interests; bounded post-relevance reordering, no new candidates."""
from collections import Counter, OrderedDict
from dataclasses import dataclass
import math
from threading import RLock
from time import monotonic, perf_counter
from search.query_plan import normalize, values, primary_match

MAX_BOOST = .02
MAX_SHIFT = 2
MAX_LOGIT_GAP = .1
MAX_SAVES = 50
CACHE_SECONDS = 60
MAX_CACHE = 256
_cache = OrderedDict()
_lock = RLock()

@dataclass
class Profile:
    subjects: Counter
    authors: Counter

def empty():
    return Profile(Counter(), Counter())

def profile_from_books(books):
    subjects, authors = Counter(), Counter()
    for book in books[:MAX_SAVES*2]:
        subjects.update(set(normalize(s) for s in values(book.get('subjects'))[:20] if normalize(s)))
        authors.update(set(normalize(a) for a in values(book.get('authors'),';')[:10] if normalize(a)))
    # Finite profile vocabulary, never an opaque permanent interest store.
    return Profile(Counter(dict(subjects.most_common(100))),Counter(dict(authors.most_common(50))))

def invalidate(actor, library_id=None):
    with _lock:
        for key in list(_cache):
            if key[0] == str(actor['sub']) and (library_id is None or key[2] == library_id):
                _cache.pop(key,None)

def invalidate_scope(actor, library_id=None, *, staff=False):
    """Evict only the current login's profile for the inaccessible workspace."""
    owner=(str(actor['sub']),actor.get('sid'),library_id,bool(staff))
    with _lock:
        keys=[key for key in _cache if key[:4]==owner]
        for key in keys:_cache.pop(key,None)
    return len(keys)

def get_profile(actor, books_collection, *, library_id=None, staff=False, canonical=None):
    """Tenant caller must hold a freshly authorized catalogue.read_context.

    Global signal: saved GLOBAL_WORK identities -> live public catalogue metadata.
    Tenant addition: saved local-only identities in this exact authorized library.
    Neither snapshots stored in reading_list nor other tenants' metadata are read.
    """
    start = perf_counter()
    key = (str(actor['sub']),actor.get('sid'),library_id,bool(staff),'saved-canonical-v1')
    with _lock:
        entry = _cache.get(key)
        if entry and entry[0] > monotonic():
            _cache.move_to_end(key)
            return entry[1], {'cache':'HIT','elapsed_ms':round((perf_counter()-start)*1000,3)}
    from backend.database.mongodb import reading_list_collection
    saved = list(reading_list_collection.find({'user_id':int(actor['sub']),
        '$or':[{'target_type':'GLOBAL_WORK'},{'target_type':{'$exists':False}}],
        'work_id':{'$regex':r'^OL\d+W$'}},{'_id':0,'work_id':1}).sort('added_at',-1).limit(MAX_SAVES).max_time_ms(300))
    ids = [r['work_id'] for r in saved]
    from search.catalogue import current_books
    rows = list(current_books(books_collection,ids).values()) if ids else []
    if library_id:
        from backend.services import library_catalogue_experience as catalogue
        from backend.services.institution_repository import collection
        local = list(reading_list_collection.find({'user_id':int(actor['sub']), 'target_type':'LIBRARY_BOOK',
            'library_id':library_id},{'_id':0,'library_book_id':1}).sort('added_at',-1).limit(MAX_SAVES).max_time_ms(300))
        if local:
            raw = list(collection('library_books').aggregate([
                *catalogue.usable(library_id,staff=staff),
                {'$match':{'library_book_id':{'$in':[r['library_book_id'] for r in local]}}}, {'$limit':MAX_SAVES}]))
            rows += catalogue.hydrate(library_id,actor,raw,canonical,staff=staff)
    profile = profile_from_books(rows)
    with _lock:
        _cache[key] = (monotonic()+CACHE_SECONDS,profile)
        _cache.move_to_end(key)
        while len(_cache)>MAX_CACHE:
            _cache.popitem(last=False)
    return profile, {'cache':'MISS','elapsed_ms':round((perf_counter()-start)*1000,3)}

def affinity(book, profile):
    subjects = [(profile.subjects[normalize(s)],s) for s in values(book.get('subjects'))]
    authors = [(profile.authors[normalize(a)],a) for a in values(book.get('authors'),';')]
    subject = max(subjects,default=(0,''))
    author = max(authors,default=(0,''))
    strength = min(1., .8*min(subject[0]/3,1.) + .2*min(author[0]/3,1.))
    reason = ('Related to '+subject[1][:80]+' books in your Reading List') if subject[0] else (
        'Related to authors in your Reading List' if author[0] else None)
    return MAX_BOOST*strength, reason

def relevance(book):
    value = book.get('_search_relevance',book.get('rerank_score'))
    if value is None:
        return None
    try:
        number = float(value)
        if not math.isfinite(number):
            return None
        return 1./(1.+math.exp(-max(-40.,min(40.,number))))
    except (ValueError,TypeError):
        return None

def rerank(rows, plan, profile=None, enabled=False):
    """At most two places within an adjacent 3-row relevance band.

    The full band's CE sigmoid span must be <= .02. Scores are never calibrated
    probabilities. No crossing V2A primary/expansion groups or explicit sorts.
    Disabled and cold starts keep the exact baseline order.
    """
    start = perf_counter()
    original = list(rows)
    boosts = {id(b):affinity(b,profile) for b in rows} if enabled and profile else {}
    if enabled and profile and (profile.subjects or profile.authors) and plan.sort == 'RELEVANCE' and not (plan.exact_text or plan.title_text or plan.author_text):
        ordered = []
        index = 0
        while index < len(rows):
            group = [rows[index]]
            score = relevance(rows[index])
            primary = primary_match(plan,rows[index]) if plan.kg_expansion_used else True
            while index+len(group) < len(rows) and len(group) <= MAX_SHIFT:
                candidate = rows[index+len(group)]
                other = relevance(candidate)
                if (primary_match(plan,candidate) if plan.kg_expansion_used else True) != primary:
                    break
                # With no CE (structured/fallback), only equally ranked adjacent
                # candidates can be adjusted; bound displacement to two.
                if (score is None) != (other is None) or score is not None and abs(score-other) > MAX_BOOST:
                    break
                if score is not None and abs(float(rows[index].get('_search_relevance',rows[index].get('rerank_score')))-float(candidate.get('_search_relevance',candidate.get('rerank_score')))) > MAX_LOGIT_GAP:
                    break
                group.append(candidate)
            ordered.extend(sorted(group,key=lambda b:-((relevance(b) or 0.)+boosts[id(b)][0])))
            index += len(group)
        rows = ordered
    result = []
    for book in rows:
        reasons = []
        if enabled and boosts.get(id(book),(0,None))[1]:
            reasons.append(boosts[id(book)][1])
        if primary_match(plan,book):
            reasons.append('Matches your search for “'+(plan.semantic_text or '')[:80]+'”')
        elif plan.subjects:
            reasons.append('Matches the selected subject')
        if book.get('has_online') is True or book.get('readable') is True:
            reasons.append('Available online')
        clean = {k:v for k,v in book.items() if k not in ('rerank_score','hnsw_score','_search_relevance','personalization_score')}
        clean['search_reasons'] = reasons[:2]
        result.append(clean)
    return result, {'enabled':enabled, 'profile_available':bool(profile and (profile.subjects or profile.authors)),
                    'max_boost':MAX_BOOST, 'max_shift':MAX_SHIFT,
                    'order_changed':any(a is not b for a,b in zip(original,rows)),
                    'elapsed_ms':round((perf_counter()-start)*1000,3)}

def safe_profile(actor, books_collection, **scope):
    # Preference lookup is optional; authorization is performed by the caller
    # before this function and is never swallowed here.
    try:
        return get_profile(actor,books_collection,**scope)
    except Exception:
        return empty(), {'cache':'UNAVAILABLE','elapsed_ms':0}
