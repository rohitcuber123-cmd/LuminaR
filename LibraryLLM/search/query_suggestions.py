"""Bounded suggestions; no embeddings, KG, ranking models or search commits.

Projection caches are keyed by authorization scope and an audit generation.
Authority is checked outside/before every access. Entity IDs are always hydrated
again through canonical visibility, including on cache hits.
"""
from bisect import bisect_left
from collections import OrderedDict
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import RLock
from time import monotonic
import secrets
from fastapi import HTTPException
from pymongo.collation import Collation

from search.lexical_store import RANGE_SQL, prefix_upper
from search.query_plan import FacetVocabulary, normalize, values
from search.typo_assistance import best_bounded_match, normalize_structured

MAX_ITEMS=8
ENTITY_BOUND=32
PROJECTION_TTL=30
_projections=OrderedDict()
_issued=OrderedDict()
_lock=RLock()
_author_index=False
AUTHOR_INDEX='v2cb_author_prefix'
AUTHOR_COLLATION=Collation('en',strength=2)


def generation(library_id):
    from backend.services.institution_repository import collection
    row=collection('audit').find_one({'library_id':library_id},{'_id':1},sort=[('created_at',-1)])
    return str(row['_id']) if row else 'EMPTY'


def projection(engine,actor,library_id=None,staff=False):
    from search.session_store import identity
    from search.query_execution import global_facets
    owner=identity(actor,library_id,staff)
    gen=generation(library_id) if library_id else str(getattr(getattr(engine,'lexical_store',None),'manifest',{}).get('sidecar_version','global'))
    key=(*owner.values(),gen);now=monotonic()
    with _lock:
        cached=_projections.get(key)
        if cached and cached[0]>now:
            _projections.move_to_end(key);return cached[1],gen,'HIT'
    if library_id:
        from backend.services import library_catalogue_experience as catalogue
        rows=catalogue.subject_rows(library_id,limit=2048,staff=staff)
        facets={**rows,'capabilities':{'rating':True,'year':True,'language':True,'formats':['ONLINE','PHYSICAL','BOTH'],'availability':True}}
    else:facets=global_facets(engine)
    vocab=FacetVocabulary([r['subject'] for r in facets['results']])
    data={'facets':facets,'vocab':vocab,'keys':sorted(vocab.rows),'buckets':{}}
    # Built once per bounded generation, not a vocabulary regex loop on typing.
    for value in data['keys']:
        data['buckets'].setdefault(value[:2],[]).append(value)
    with _lock:
        _projections[key]=(now+PROJECTION_TTL,data);_projections.move_to_end(key)
        while len(_projections)>16:_projections.popitem(last=False)
    return data,gen,'MISS'


def global_entities(engine,prefix):
    lexical=getattr(engine,'lexical_store',None)
    if lexical is None or getattr(lexical,'db',None) is None:return [],{'TITLE':'PARTIAL: lexical prefix index unavailable','AUTHOR':'PARTIAL: lexical prefix index unavailable'}
    candidates=[]
    # The existing overlay transaction supplies a coherent base/delta view.
    manager=lexical._read_transaction() if hasattr(lexical,'_read_transaction') else nullcontext()
    with manager:
        for kind in ('AUTHOR','TITLE'):
            rows=list(lexical._query(RANGE_SQL,(kind,prefix,prefix_upper(prefix),ENTITY_BOUND)))
            if getattr(lexical,'delta_available',False):
                rows+=lexical._query(RANGE_SQL.replace('FROM lexical_values','FROM lexical_delta.lexical_values'),(kind,prefix,prefix_upper(prefix),ENTITY_BOUND))
            candidates.extend((kind,value,wid) for value,wid in rows)
    ids=list(dict.fromkeys(wid for _,_,wid in candidates))
    if not ids:return [],{'AUTHOR':'INDEXED','TITLE':'INDEXED'}
    rows={r['work_id']:r for r in engine.books_collection.find({'work_id':{'$in':ids}},{'_id':0,'work_id':1,'title':1,'authors':1}).limit(ENTITY_BOUND*4)}
    result=[]
    for kind,_,wid in candidates:
        row=rows.get(wid)
        if not row:continue
        names=[row.get('title','')] if kind=='TITLE' else values(row.get('authors'),';')
        for name in names:
            if normalize_structured(name).startswith(prefix):result.append((kind,name,wid))
    return result,{'AUTHOR':'INDEXED','TITLE':'INDEXED'}


def tenant_entities(library_id,prefix,staff=False):
    from backend.services.institution_repository import collection
    from backend.services import library_catalogue_experience as catalogue
    global _author_index
    books=collection('library_books');sources={'TITLE':'INDEXED','AUTHOR':'INDEXED'}
    if not _author_index:
        with _lock:
            if not _author_index:
                books.create_index([('library_id',1),('status',1),('authors',1)],name=AUTHOR_INDEX,collation=AUTHOR_COLLATION)
                _author_index=True
    title_ids=[r['library_book_id'] for r in books.find({'library_id':library_id,'normalized_title':{'$gte':prefix,'$lt':prefix_upper(prefix)}},{'_id':0,'library_book_id':1}).hint([('library_id',1),('normalized_title',1)]).limit(ENTITY_BOUND).max_time_ms(300)]
    author_ids=[r['library_book_id'] for r in books.find({'library_id':library_id,'status':'ACTIVE','authors':{'$elemMatch':{'$gte':prefix,'$lt':prefix_upper(prefix)}}},{'_id':0,'library_book_id':1}).collation(AUTHOR_COLLATION).hint(AUTHOR_INDEX).limit(ENTITY_BOUND).max_time_ms(300)]
    ids=list(dict.fromkeys(title_ids+author_ids))
    if not ids:return [],sources
    pipeline=catalogue.usable(library_id,staff=staff)
    pipeline[0]['$match']['library_book_id']={'$in':ids}
    rows=list(books.aggregate([*pipeline,{'$project':{'_id':0,'library_book_id':1,'title':1,'authors':1}},{'$limit':ENTITY_BOUND*2}],maxTimeMS=500))
    result=[]
    for row in rows:
        bid=row['library_book_id']
        if bid in title_ids and normalize_structured(row['title']).startswith(prefix):result.append(('TITLE',row['title'],bid))
        for author in row.get('authors',[]):
            if bid in author_ids and normalize_structured(author).startswith(prefix):result.append(('AUTHOR',author,bid))
    return result,sources


def visible_subjects(library_id,subjects,staff):
    if not subjects:return set()
    from backend.services.institution_repository import collection
    from backend.services import library_catalogue_experience as catalogue
    # Each canonical value gets a bounded indexed proof. Never expose a cached
    # private facet whose last discoverable book was removed or hidden.
    visible=set()
    for subject in subjects[:MAX_ITEMS]:
        ids=[r['library_book_id'] for r in collection('library_books').find({'library_id':library_id,'status':'ACTIVE','subjects':subject},{'_id':0,'library_book_id':1}).hint([('library_id',1),('status',1),('subjects',1)]).limit(ENTITY_BOUND).max_time_ms(200)]
        if not ids:continue
        pipeline=catalogue.usable(library_id,staff=staff)
        pipeline[0]['$match'].update(library_book_id={'$in':ids},subjects=subject)
        if next(iter(collection('library_books').aggregate([*pipeline,{'$limit':1},{'$project':{'_id':1}}],maxTimeMS=500)),None):visible.add(subject)
    return visible


def issue(item,actor,q,mode,gen,library_id,staff):
    from search.session_store import identity
    payload={**identity(actor,library_id,staff),'q':q,'mode':mode,'generation':gen,
             'item':item,'expires':int(datetime.now(timezone.utc).timestamp())+120}
    # An opaque capability exposes no user/sid/generation metadata, even when
    # decoded. The bounded process cache is not a general-purpose session store.
    key=secrets.token_urlsafe(24)
    with _lock:
        _issued[key]=payload
        while len(_issued)>2048:_issued.popitem(last=False)
    return key


def verify(suggestion_id,actor,q,mode,gen,library_id,staff):
    from search.session_store import identity
    try:
        with _lock:row=deepcopy(_issued.get(suggestion_id))
        if not row:raise ValueError()
        if any(row.get(k)!=v for k,v in identity(actor,library_id,staff).items()):raise ValueError()
        if row['q']!=q or row['mode']!=mode or row['generation']!=gen or row['expires']<=datetime.now(timezone.utc).timestamp():raise ValueError()
        return row['item']
    except (ValueError,KeyError,TypeError):raise HTTPException(409,'Suggestion changed. Type again to refresh suggestions.')


def suggest(engine,actor,q,*,mode='SMART',limit=8,library_id=None,staff=False):
    q=normalize_structured(q)
    if len(q)<2 or len(q)>150 or mode=='EXACT' or any(c in q for c in ('"','“','”')) or q.isnumeric():
        return {'query':q,'scope':'LIBRARY' if library_id else 'GLOBAL','suggestions':[],'sources':{}}
    data,gen,cache=projection(engine,actor,library_id,staff)
    vocab=data['vocab'];keys=data['keys'];start=bisect_left(keys,q)
    canonical=[vocab.rows[k] for k in keys[start:start+MAX_ITEMS] if k.startswith(q)] if mode!='TITLE_AUTHOR' else []
    items=[{'type':'SUBJECT','display':s,'insert_text':s,'match_kind':'PREFIX'} for s in canonical]
    if mode!='TITLE_AUTHOR':
        for alias,target in vocab.aliases.items():
            if alias.startswith(q) and vocab.rows[target] not in canonical:
                items.append({'type':'SUBJECT','display':vocab.rows[target],'insert_text':vocab.rows[target],'match_kind':'ALIAS'})
        # Corrections are choices, never automatically inserted while typing.
        if len(q)>=5 and not items and not any(c.isdigit() for c in q):
            shortlist=data['buckets'].get(q[:2],[])[:64]
            match=best_bounded_match(q,shortlist)
            if match:
                s=vocab.rows[match['value']];items.append({'type':'SUBJECT','display':s,'insert_text':s,'match_kind':'TYPO'})
    if library_id:
        visible=visible_subjects(library_id,list(dict.fromkeys(i['display'] for i in items)),staff)
        items=[i for i in items if i['display'] in visible]
    entities,sources=(tenant_entities(library_id,q,staff) if library_id else global_entities(engine,q)) if len(q)>=3 and mode!='GENRE_SUBJECT' else ([],{'AUTHOR':'MIN_PREFIX_3','TITLE':'MIN_PREFIX_3'})
    for kind,name,_ in sorted(entities,key=lambda r:({'AUTHOR':0,'TITLE':1}[r[0]],normalize(r[1]))):
        items.append({'type':kind,'display':name,'insert_text':('books by '+name) if kind=='AUTHOR' and mode=='SMART' else name,'match_kind':'PREFIX'})
    templates=['rated above 4','rated at least 4','available online']
    if library_id:templates+=['physical only','available now','published after 2020']
    if mode=='SMART':
        for text in templates:
            if text.startswith(q):items.append({'type':'TEMPLATE','display':text,'insert_text':text,'match_kind':'TEMPLATE'})
    dedup=[];seen=set()
    items.sort(key=lambda item:(0 if item['match_kind']=='PREFIX' and normalize_structured(item['display'])==q else
                               {'SUBJECT':1,'AUTHOR':2,'TITLE':3}.get(item['type'],6) if item['match_kind']=='PREFIX' else
                               {'ALIAS':4,'TYPO':5,'TEMPLATE':6}[item['match_kind']],normalize_structured(item['display'])))
    for item in items:
        key=(item['type'],item['display'])
        if key not in seen:dedup.append(item);seen.add(key)
        if len(dedup)>=min(MAX_ITEMS,max(1,limit)):break
    return {'query':q,'scope':'LIBRARY' if library_id else 'GLOBAL',
            'suggestions':[dict(item,id=issue(item,actor,q,mode,gen,library_id,staff)) for item in dedup],
            'sources':{'SUBJECT':'BOUNDED_CANONICAL_PROJECTION',**sources}}
