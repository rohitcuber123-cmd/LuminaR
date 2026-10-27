"""Deterministic human search interpretation and strict canonical predicates.

No models, databases, cached tenant data, or client-supplied query plans.
"""
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
import math
import re
import unicodedata
from functools import lru_cache
from types import MappingProxyType

MODES = ('SMART', 'GENRE_SUBJECT', 'TITLE_AUTHOR', 'EXACT')
SORTS = ('RELEVANCE', 'RATING', 'NEWEST', 'TITLE')
PARSER_VERSION = 'search-v2c-c5er-disabled-candidate-1'
INTENTS = ('FIND_EXACT','FIND_AUTHOR','BROWSE_CATEGORY','DISCOVER_TOPIC','LEARN','REFERENCE','RESEARCH','FIND_AVAILABLE','FIND_ONLINE','DISCOVER_RELATED')


def normalize(value):
    text = unicodedata.normalize('NFKC', str(value or '')).casefold()
    return ' '.join(re.sub(r'[^\w\s]', ' ', text).split())


def values(value, separator='|'):
    return [str(v).strip() for v in (value if isinstance(value, (list, tuple)) else str(value or '').split(separator)) if str(v).strip()]


class FacetVocabulary:
    def __init__(self, facets):
        self.rows,self.aliases=_facet_projection(tuple(facets))

    def _build(self, facets):
        self.rows = {}
        for name in facets:
            if normalize(name): self.rows.setdefault(normalize(name), str(name))
        self.aliases = {}
        for alias, target in {'sci fi': 'science fiction', 'bio': 'biography', 'kids': "children's fiction", 'folktale': 'folktales'}.items():
            if normalize(target) in self.rows: self.aliases[alias] = normalize(target)
        for target in ('detective fiction', 'detective and mystery stories', 'fiction mystery detective general'):
            if target in self.rows:
                self.aliases['detective'] = target
                break

    def resolve(self, term, fuzzy=True):
        key = normalize(term)
        if key in self.rows: return self.rows[key], 1.0, None
        if key in self.aliases: return self.rows[self.aliases[key]], .98, {'from': term, 'to': self.rows[self.aliases[key]], 'kind': 'alias'}
        if not fuzzy or len(key) < 4 or len(key) > 60: return None, 0., None
        if len(key)>=6:
            transposed=set()
            for i in range(len(key)-1):
                swapped=key[:i]+key[i+1]+key[i]+key[i+2:]
                if swapped==key:continue
                target=self.aliases.get(swapped,swapped)
                if target in self.rows:transposed.add(target)
            if len(transposed)==1:
                target=transposed.pop()
                return self.rows[target],.95,{'from':term,'to':self.rows[target],'kind':'typo'}
        candidates = [(SequenceMatcher(None, key, k).ratio(), k) for k in dict.fromkeys([*self.rows, *self.aliases])
                      if abs(len(k) - len(key)) <= max(2, len(key)//5) and len(k.split()) == len(key.split())]
        candidates.sort(reverse=True)
        if not candidates or candidates[0][0] < .86 or len(candidates) > 1 and candidates[0][0] - candidates[1][0] < .05:
            return None, 0., None
        score, matched = candidates[0]; target = self.aliases.get(matched, matched)
        return self.rows[target], score, {'from': term, 'to': self.rows[target], 'kind': 'typo'}


@lru_cache(maxsize=8)
def _facet_projection(facets):
    # Tiny bounded vocabulary projections, keyed by their COMPLETE authorized
    # content. Access still follows fresh scope authorization; no query cache.
    obj=object.__new__(FacetVocabulary);obj._build(facets)
    return MappingProxyType(obj.rows),MappingProxyType(obj.aliases)


@dataclass
class QueryPlan:
    raw_query: str
    mode: str = 'SMART'
    semantic_text: str | None = None
    title_text: str | None = None
    author_text: str | None = None
    subjects: list[str] = field(default_factory=list)
    rating_min: float | None = None
    rating_max: float | None = None
    rating_min_exclusive: bool = False
    rating_max_exclusive: bool = False
    year_min: int | None = None
    year_max: int | None = None
    year_min_exclusive: bool = False
    year_max_exclusive: bool = False
    formats: list[str] = field(default_factory=list)
    availability: str | None = None
    language: str | None = None
    exact_text: str | None = None
    sort: str = 'RELEVANCE'
    interpretation_confidence: float = 1.
    corrections: list[dict] = field(default_factory=list)
    unknown_subject: bool = False
    suggested_subject: str | None = None
    normalized_query: str = ''
    intent: str = 'DISCOVER_TOPIC'
    parser_version: str = PARSER_VERSION
    include_terms: list[str] = field(default_factory=list)
    exclude_terms: list[str] = field(default_factory=list)
    exclude_subjects: list[str] = field(default_factory=list)
    expanded_subjects: list[str] = field(default_factory=list)
    soft_preference: str | None = None
    kg_expansion_used: bool = False
    kg_generation: str | None = None
    constraint_candidates: list[dict] = field(default_factory=list)
    source_spans: list[dict] = field(default_factory=list)
    decision: dict = field(default_factory=dict)
    exclusive_formats: list[str] = field(default_factory=list)
    excluded_formats: list[str] = field(default_factory=list)
    physical_available_only: bool = False

    def ranking_query(self):
        topic=self.semantic_text or ''
        prefix={'LEARN':'introductory beginner guide to ','REFERENCE':'reference handbook for ','RESEARCH':'research studies about '}.get(self.intent,'')
        return prefix+topic

    def cache_key(self,*,library_id=None,hnsw_generation=None):
        import json
        return json.dumps({'scope':library_id or 'GLOBAL','hnsw_generation':hnsw_generation,'plan':asdict(self)}, sort_keys=True, ensure_ascii=False)

    def public(self):
        chips = []
        unsupported=set(self.decision.get('affected_fields',[])) if self.decision.get('decision_type')=='UNSUPPORTED' else set()
        def chip(key, label):
            if key not in unsupported and key.split('_')[0] not in unsupported:chips.append({'key': key, 'label': label})
        if self.semantic_text: chip('topic', 'Topic: ' + self.semantic_text)
        for subject in self.subjects: chip('subject', 'Genre / Subject: ' + subject)
        if self.title_text: chip('title', 'Title / Author: ' + self.title_text)
        if self.author_text: chip('author', 'Author: ' + self.author_text)
        if self.exact_text: chip('exact', 'Exact: ' + self.exact_text)
        if self.rating_min is not None: chip('rating_min', f"Rating: {'>' if self.rating_min_exclusive else '≥'} {self.rating_min:g}")
        if self.rating_max is not None: chip('rating_max', f"Rating: {'<' if self.rating_max_exclusive else '≤'} {self.rating_max:g}")
        if self.year_min is not None: chip('year_min', f"Year: {'>' if self.year_min_exclusive else '≥'} {self.year_min}")
        if self.year_max is not None: chip('year_max', f"Year: {'<' if self.year_max_exclusive else '≤'} {self.year_max}")
        for fmt in self.formats: chip('format', 'Format: ' + {'ONLINE':'Online', 'PHYSICAL':'Physical', 'BOTH':'Physical + Online'}[fmt])
        if self.availability: chip('availability', 'Availability: ' + self.availability.replace('_',' ').title())
        if self.language: chip('language', 'Language: ' + self.language)
        for term in self.exclude_terms:chip('exclude', 'Exclude: '+term)
        for subject in self.exclude_subjects:
            if subject not in self.exclude_terms:chip('exclude', 'Exclude subject: '+subject)
        decision={k:self.decision.get(k) for k in ('decision_type','reason_code','affected_fields','safe_public_message','parser_version')} if self.decision else {'decision_type':'EXECUTABLE','parser_version':self.parser_version}
        return {'mode': self.mode, 'intent':self.intent, 'intent_label':self.intent.replace('_',' ').capitalize(), 'decision':decision,
                'related_concepts':self.expanded_subjects if self.kg_expansion_used else [],
                'preference':self.soft_preference, 'chips': chips, 'corrections': self.corrections,
                'notice': 'No canonical subject matches this query.' if self.unknown_subject else ' '.join('Interpreted “'+str(r['from'])+'” as “'+str(r['to'])+'”.' for r in self.decision.get('repair_notices',[])),
                'suggested_subject': self.suggested_subject}


def parse_query(query, facets=(), mode='SMART', filters=None, omit=()):
    if len(str(query))>500:raise ValueError('Search query is too long.')
    # Retain accepted validation/error semantics for explicit UI/API controls.
    if filters:_parse_legacy('',(),mode,filters,())
    if mode!='SMART' or re.fullmatch(r'(?:\d{13}|\d{9}[\dXx]|OL\d+W)',re.sub(r'[-\s]','',str(query)),re.I):
        from scratch.search_v2c_c5er.candidate_search.query_confidence import decide,validate
        plan=_parse_legacy(query,facets,mode,filters,omit)
        # The explicit Search mode (or complete identifier syntax) supplies
        # field evidence; its operand is the actual query span, not SMART prose.
        from scratch.search_v2c_c5er.candidate_search.query_constraints import Candidate
        raw=str(query)
        if raw.strip():
            for field,value in [('title',plan.title_text),('exact_text',plan.exact_text),
                                *[('subject',subject) for subject in plan.subjects]]:
                if value is None:continue
                candidate=asdict(Candidate(field,'LITERAL_TITLE_OR_AUTHOR' if field=='title' else 'IDENTITY' if field=='exact_text' else 'SCOPED_EXACT',value,0,len(raw),raw,'mode.explicit_operand'))
                candidate.update(source_query=raw,source_mode=mode)
                plan.constraint_candidates.append(candidate)
                plan.source_spans.append({'kind':'CANONICAL_FACET' if field=='subject' else 'CANONICAL_ENTITY','start':0,'end':len(raw),'text':raw,'source_query':raw,'recognizer_id':'mode.explicit_operand'})
        return validate(decide(plan))
    from scratch.search_v2c_c5er.candidate_search.query_repair import compose
    return compose(str(query),facets,_parse_legacy,filters or {},omit)

def _parse_legacy(query, facets=(), mode='SMART', filters=None, omit=(), recognize_constraints=True):
    if mode not in MODES: raise ValueError('Unknown search mode.')
    if len(str(query)) > 500: raise ValueError('Search query is too long.')
    plan = QueryPlan(str(query).strip(), mode); vocab = FacetVocabulary(facets)
    plan.normalized_query=normalize(plan.raw_query)
    text = unicodedata.normalize('NFKC',plan.raw_query).casefold().strip()
    if mode == 'EXACT': plan.exact_text = plan.raw_query
    elif mode == 'TITLE_AUTHOR': plan.title_text = plan.raw_query
    elif mode == 'GENRE_SUBJECT':
        subject, confidence, correction = vocab.resolve(text)
        if subject: plan.subjects = [subject]; plan.interpretation_confidence = confidence
        else: plan.unknown_subject = True
        if correction: plan.corrections.append(correction)
    else:
        compact=re.sub(r'[-\s]','',plan.raw_query)
        if re.fullmatch(r'(?:\d{13}|\d{9}[\dXx]|OL\d+W)',compact,re.I):
            plan.exact_text=plan.raw_query;text=''
        def extract(pattern, action):
            nonlocal text
            if not recognize_constraints:return
            def consume(match): action(match); return ' '
            text = re.sub(pattern, consume, text, flags=re.I)
        number = r'([0-5](?:\.\d+)?)(?![\d.])'
        def bound(key, exclusive, value): setattr(plan,key,float(value)); setattr(plan,key+'_exclusive',exclusive)
        extract(r'\bbetween\s+'+number+r'\s+and\s+'+number+r'\s+stars?\b', lambda m:(bound('rating_min',False,m[1]),bound('rating_max',False,m[2])))
        extract(r'\b(?:rating|rated|ratings?)\s*(?:above|over|greater than|>)\s*'+number, lambda m:bound('rating_min',True,m[1]))
        extract(r'\b(?:rating|rated|ratings?)\s*(?:at least|>=|≥)\s*'+number, lambda m:bound('rating_min',False,m[1]))
        extract(r'\b(?:rating|rated|ratings?)\s*(?:below|under|less than|<)\s*'+number, lambda m:bound('rating_max',True,m[1]))
        extract(r'\b(?:rating|rated|ratings?)\s*(?:at most|<=|≤)\s*'+number, lambda m:bound('rating_max',False,m[1]))
        extract(r'\b'+number+r'\s*(?:\+\s*(?:stars?)?|or higher|stars?\s+or higher)',lambda m:bound('rating_min',False,m[1]))
        extract(r'\b(?:rating|rated)\s*'+number+r'\s*(?:\+|or higher)',lambda m:bound('rating_min',False,m[1]))
        extract(r'\b(?:at least|>=|≥)\s*'+number+r'\s+stars?\b',lambda m:bound('rating_min',False,m[1]))
        extract(r'\b(?:above|over)\s*'+number+r'\s+stars?\b',lambda m:bound('rating_min',True,m[1]))
        extract(r'\b(?:below|under)\s*'+number+r'\s+stars?\b',lambda m:bound('rating_max',True,m[1]))
        def year(key, exclusive, value): setattr(plan,key,int(value));setattr(plan,key+'_exclusive',exclusive)
        extract(r'\b(?:published\s+)?after\s+(\d{4})\b',lambda m:year('year_min',True,m[1]))
        extract(r'\b(?:published\s+)?before\s+(\d{4})\b',lambda m:year('year_max',True,m[1]))
        extract(r'\bfrom\s+(\d{4})\s+to\s+(\d{4})\b',lambda m:(year('year_min',False,m[1]),year('year_max',False,m[2])))
        extract(r'\bpublished\s+in\s+(\d{4})\b',lambda m:(year('year_min',False,m[1]),year('year_max',False,m[1])))
        extract(r'\b(?:available\s+online|online\s+now)\b',lambda m:plan.formats.append('ONLINE'))
        extract(r'\bavailable\s+to\s+request\b',lambda m:setattr(plan,'availability','REQUESTABLE'))
        extract(r'\bavailable\s+now\b',lambda m:setattr(plan,'availability','AVAILABLE_NOW'))
        extract(r'\bphysical\s*(?:\+|and)\s*(?:online|digital)\b',lambda m:plan.formats.append('BOTH'))
        extract(r'\b(?:online|digital)\b',lambda m:plan.formats.append('ONLINE'))
        extract(r'\b(?:physical|hard cop(?:y|ies))\b',lambda m:plan.formats.append('PHYSICAL'))
        def exclude(match):
            for term in re.split(r'\s*(?:,|\band\b|\bor\b)\s*',match[1].strip(' .?!'))[:5]:
                term=term.strip(' \"\'')
                if not term:continue
                subject,_,_=vocab.resolve(term,fuzzy=False)
                plan.exclude_terms.append(subject or term)
                if subject:plan.exclude_subjects.append(subject)
        extract(r'\b(?:but\s+not|excluding|without)\s+(.{1,100})$',exclude)
        extract(r'\bbooks?\s+(?:written\s+)?by\s+(.+?)\s*$',lambda m:setattr(plan,'author_text',m[1].strip()))
        if re.search(r'\b(?:easy introduction|introduction to|beginner|learn|learning guide)\b',text):
            plan.intent='LEARN';plan.soft_preference='Introductory / beginner (preference)'
            text=re.sub(r'^\s*(?:i\s+want\s+|show\s+me\s+|find\s+me\s+)?(?:an?\s+)?(?:easy\s+)?(?:introduction\s+to|beginner(?:s)?(?:\s+guide)?(?:\s+to)?|learn)\s+','',text)
        elif re.search(r'\breference\s+(?:book|material|guide)',text):
            plan.intent='REFERENCE';text=re.sub(r'\breference\s+(?:books?|material|guide)\s*(?:for|about|on)?',' ',text)
        elif re.search(r'\bresearch\s+(?:material|books?|studies)',text):
            plan.intent='RESEARCH';text=re.sub(r'\bresearch\s+(?:material|books?|studies)\s*(?:for|about|on)?',' ',text)
        elif re.search(r'\b(?:related to|similar to)\b',text):
            plan.intent='DISCOVER_RELATED';text=re.sub(r'\b(?:related to|similar to)\b',' ',text)
        # Categories are recognized as a complete query or an explicit prefix
        # before “books”; ordinary “books about X” stays semantic.
        stripped = re.sub(r'\b(?:with|and|books?)\b',' ',text).strip(' ?.!,')
        candidate = re.split(r'\b(?:books?|about|on)\b',text,maxsplit=1)[0].strip(' ?.!,') or stripped
        subject,confidence,correction=vocab.resolve(candidate)
        generic_topic=bool(re.fullmatch(r'(?:stories|novels|biographies|works|writings)',candidate)
                           and re.search(r'\b'+re.escape(candidate)+r'\s+(?:about|on)\s+',text))
        if generic_topic:subject=None
        if subject and normalize(candidate) in {'women','men','general','science','education','research','law','computers','networks','war','love'} and not re.search(r'\bbooks?\b',text):
            plan.suggested_subject=subject;subject=None;plan.interpretation_confidence=.6
        if subject and plan.intent not in ('LEARN','REFERENCE','RESEARCH','DISCOVER_RELATED') and not re.search(r'\babout\b', candidate):
            plan.subjects=[subject];plan.interpretation_confidence=confidence
            text=re.sub(re.escape(candidate),' ',text,count=1)
            if correction:plan.corrections.append(correction)
        remainder=text if generic_topic else re.sub(r'\b(?:books?|about|on|with|and|please|find|show|me|ratings?|rated|stars?)\b',' ',text)
        remainder=' '.join(remainder.strip(' ?.!,').split())
        plan.semantic_text=remainder or None
    filters=filters or {}
    if filters.get('subject'):
        subject,_,_=vocab.resolve(filters['subject'],fuzzy=False)
        plan.subjects=[subject or str(filters['subject'])]
    if filters.get('author'):plan.author_text=str(filters['author']).strip()
    for key in ('rating_min','rating_max','year_min','year_max','language','availability'):
        if filters.get(key) is not None and filters.get(key)!='':
            val=filters[key]
            if key.startswith('rating'):val=float(val)
            if key.startswith('year'):val=int(val)
            setattr(plan,key,val)
            if key.startswith(('rating','year')):setattr(plan,key+'_exclusive',False)
    if filters.get('format'):
        if filters['format'] not in ('PHYSICAL','ONLINE','BOTH'):raise ValueError('Unknown format.')
        plan.formats=[filters['format']]
    sort=str(filters.get('sort') or 'RELEVANCE').upper()
    if sort not in SORTS:raise ValueError('Unknown sort order.')
    plan.sort=sort
    if any(v is not None and not 0<=v<=5 for v in (plan.rating_min,plan.rating_max)):raise ValueError('Rating must be between 0 and 5.')
    if any(v is not None and not 1000<=v<=2100 for v in (plan.year_min,plan.year_max)):raise ValueError('Invalid publication year.')
    for key in set(omit):
        if key=='topic':plan.semantic_text=None
        elif key=='subject':plan.subjects=[];plan.unknown_subject=False
        elif key=='format':plan.formats=[]
        elif key=='author':plan.author_text=None
        elif key=='title':plan.title_text=None
        elif key=='exact':plan.exact_text=None
        elif key=='exclude':plan.exclude_terms=[];plan.exclude_subjects=[]
        elif key in ('rating_min','rating_max','year_min','year_max','availability','language'):setattr(plan,key,None)
    if plan.exact_text:plan.intent='FIND_EXACT'
    elif plan.author_text or plan.title_text:plan.intent='FIND_AUTHOR' if plan.author_text else 'FIND_EXACT'
    elif plan.availability:plan.intent='FIND_AVAILABLE'
    elif 'ONLINE' in plan.formats or 'BOTH' in plan.formats:plan.intent='FIND_ONLINE'
    elif plan.subjects and not plan.semantic_text:plan.intent='BROWSE_CATEGORY'
    return plan


def matches(plan, book):
    from scratch.search_v2c_c5er.candidate_search.query_confidence import executable
    if not executable(plan):return False
    if plan.unknown_subject:return False
    if not all(normalize(s) in {normalize(v) for v in values(book.get('subjects'))} for s in plan.subjects):return False
    if {normalize(s) for s in plan.exclude_subjects} & {normalize(v) for v in values(book.get('subjects'))}:return False
    text=normalize(' '.join([str(book.get('title') or ''),' '.join(values(book.get('authors'),';')),' '.join(values(book.get('subjects'))),str(book.get('description') or '')]))
    if any(re.search(r'(?<!\w)'+re.escape(normalize(term))+r'(?!\w)',text) for term in plan.exclude_terms):return False
    author=' '.join(values(book.get('authors'),';'))
    if plan.author_text and normalize(plan.author_text) not in normalize(author):return False
    if plan.title_text and normalize(plan.title_text) not in normalize(book.get('title')) and normalize(plan.title_text) not in normalize(author):return False
    if plan.exact_text:
        text=normalize(plan.exact_text)
        ids=[book.get(k) for k in ('work_id','global_work_id','library_book_id','accession_number','isbn_10','isbn_13','local_call_number')]
        isbn=re.sub(r'[-\s]','',plan.exact_text).upper()
        isbn_match=bool(re.fullmatch(r'(?:\d{13}|\d{9}[\dX])',isbn) and isbn in {re.sub(r'[-\s]','',str(book.get(k) or '')).upper() for k in ('isbn_10','isbn_13')})
        if plan.mode=='SMART' and re.fullmatch(r'(?:\d{13}|\d{9}[\dX])',isbn) and not isbn_match:return False
        if not isbn_match and text not in {normalize(v) for v in ids if v} and text!=normalize(book.get('title')):return False
    rating=book.get('average_rating',book.get('rating'))
    try:rating=float(rating);rating=rating if math.isfinite(rating) and not(rating==0 and not book.get('rating_count')) else None
    except (TypeError,ValueError):rating=None
    year=book.get('publication_year')
    if year is None:
        match=re.fullmatch(r'(\d{4})(?:-\d\d-\d\d)?',str(book.get('first_publish_date') or ''));year=int(match[1]) if match else None
    for val,low,high,lo_ex,hi_ex in [(rating,plan.rating_min,plan.rating_max,plan.rating_min_exclusive,plan.rating_max_exclusive),(year,plan.year_min,plan.year_max,plan.year_min_exclusive,plan.year_max_exclusive)]:
        if low is not None and (val is None or (val<=low if lo_ex else val<low)):return False
        if high is not None and (val is None or (val>=high if hi_ex else val>high)):return False
    for fmt in plan.formats:
        if fmt in ('ONLINE','BOTH') and book.get('has_online') is not True:return False
        if fmt in ('PHYSICAL','BOTH') and book.get('has_physical') is not True:return False
    if any(book.get('has_physical' if fmt=='PHYSICAL' else 'has_online') is True for fmt in plan.excluded_formats):return False
    if plan.availability:
        requestable=book.get('circulation_status')=='CIRCULATING' and (book.get('requestable_count') or 0)>0
        if plan.physical_available_only and not requestable:return False
        if not(requestable or plan.availability=='AVAILABLE_NOW' and book.get('has_online')):return False
    if plan.language and normalize(book.get('language'))!=normalize(plan.language):return False
    return True


def primary_match(plan,book):
    """Explicit primary phrase evidence outranks expansion-only evidence."""
    text=normalize(' '.join([str(book.get('title') or ''),' '.join(values(book.get('subjects'))),str(book.get('description') or '')]))
    return bool(plan.semantic_text and re.search(r'(?<!\w)'+re.escape(normalize(plan.semantic_text))+r'(?!\w)',text))


def sort_books(rows, plan):
    if plan.sort=='TITLE':return sorted(rows,key=lambda r:(normalize(r.get('title')),r.get('work_id',r.get('display_id',''))))
    if plan.sort=='RATING':return sorted(rows,key=lambda r:(-(r.get('average_rating',r.get('rating')) or 0),normalize(r.get('title'))))
    if plan.sort=='NEWEST':return sorted(rows,key=lambda r:(r.get('publication_year') or 0,normalize(r.get('title'))),reverse=True)
    return rows
