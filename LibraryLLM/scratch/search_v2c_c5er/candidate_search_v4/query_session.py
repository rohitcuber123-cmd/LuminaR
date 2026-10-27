"""Bounded deterministic plan edits. No transcript concatenation or model calls."""
from copy import deepcopy
import re
from scratch.search_v2c_c5er.candidate_search_v4.query_plan import QueryPlan, parse_query, normalize, FacetVocabulary, PARSER_VERSION

VERSION = 'search-v2b-session-1'

def item_edit_key(field,value):
    """A bounded remove-only address, never an entity lookup or plan patch."""
    import hashlib
    return field+'@'+hashlib.sha256(normalize(value).encode()).hexdigest()[:24]
REMOVALS = {
    'topic': ('semantic_text',), 'subject': ('subjects',), 'format': ('formats',),
    'author': ('author_text',), 'title': ('title_text',), 'exact': ('exact_text',),
    'exclude': ('exclude_terms', 'exclude_subjects'), 'preference': ('soft_preference',),
    **{k: (k,) for k in ('rating_min','rating_max','year_min','year_max','availability','language')},
}

def clean(plan):
    plan = deepcopy(plan)
    plan.kg_expansion_used = False
    plan.kg_generation = None
    plan.expanded_subjects = []
    plan.corrections = []
    return plan

def omit_fields(plan, omit):
    for key in set(omit):
        if key.startswith('subject@'):
            plan.subjects=[s for s in plan.subjects if item_edit_key('subject',s)!=key]
            continue
        if key.startswith('exclude@'):
            plan.exclude_terms=[s for s in plan.exclude_terms if item_edit_key('exclude',s)!=key]
            plan.exclude_subjects=[s for s in plan.exclude_subjects if item_edit_key('exclude',s)!=key]
            continue
        for name in REMOVALS.get(key, ()):
            setattr(plan, name, [] if isinstance(getattr(plan,name),list) else None)
        if key == 'subject':
            plan.unknown_subject = False
        if key == 'format':
            plan.exclusive_formats=[];plan.excluded_formats=[];plan.physical_available_only=False
        if key == 'preference' and plan.intent in ('LEARN','RESEARCH'):
            plan.intent = 'DISCOVER_TOPIC'
    return plan

def new_plan(query, facets, mode='SMART', filters=None):
    # V2B conversational entry grammar delegates the actual constraints to V2A.
    text = re.sub(r'^\s*i want books for learning\s+', 'learn ', query, flags=re.I)
    plan = parse_query(text, facets, mode, filters)
    plan.raw_query = query
    return plan

def refine(previous, query, facets, mode='SMART'):
    """Return (plan, continuation). Independent topics reset all inherited state.

    Explicit 'X instead' replaces topic while retaining the other constraints.
    Exact/author/subject modes always start a new V2A plan.
    """
    if mode != 'SMART' or previous is None or previous.mode != mode:
        return new_plan(query, facets, mode), False
    plan = clean(previous)
    text = normalize(query)
    if not text:
        return plan, True
    if text in ('something different','new search','start over','clear search context'):
        from scratch.search_v2c_c5er.candidate_search_v4.query_confidence import decide
        return decide(QueryPlan('', mode=mode)), False
    instead = re.fullmatch(r'(?:show me\s+)?(.+?)\s+instead', text) or re.fullmatch(r'instead\s+(?:show me\s+)?(.+)',text)
    if instead and instead[1] not in ('physical','online','digital'):
        replacement = new_plan(instead[1], facets)
        from scratch.search_v2c_c5er.candidate_search_v4.query_confidence import executable
        if not executable(replacement):return replacement,False
        for field in ('semantic_text','subjects','title_text','author_text','exact_text','intent','soft_preference','unknown_subject'):
            setattr(plan, field, getattr(replacement, field))
    elif re.fullmatch(r'(?:only |show |show me |show only )?(?:beginner(?: friendly)?|introductory)(?: ones| books)?', text):
        plan.soft_preference = 'Introductory / beginner (preference)'
        plan.intent = 'LEARN'
    elif text in ('more advanced','advanced ones','show advanced ones'):
        plan.soft_preference = 'Advanced (preference)'
        plan.intent = 'RESEARCH'
    elif text in ('remove rating filter','show all ratings','any rating'):
        plan.rating_min = plan.rating_max = None
    elif text in ('show all formats','all formats','any format'):
        plan.formats = []
    elif text in ('any year','all years','remove year filter'):
        plan.year_min = plan.year_max = None
    elif text in ('any availability','remove availability filter'):
        plan.availability = None
    elif text in ('sort by rating','sort by relevance','sort by title','sort by newest','show newer books'):
        plan.sort = 'NEWEST' if text in ('sort by newest','show newer books') else text.split()[-1].upper()
    elif text in ('only highly rated','highly rated','only highly rated ones'):
        plan.rating_min, plan.rating_max, plan.rating_min_exclusive = 4., None, False
    elif re.fullmatch(r'(?:only |show |show me |show only )?(?:ones |books )?(?:available now|available to request)(?: only)?', text):
        plan.availability = 'REQUESTABLE' if 'request' in text else 'AVAILABLE_NOW'
    elif re.fullmatch(r'(?:only )?(?:online|digital|physical|hard copy)(?: only| instead)?(?: ones| books)?', text):
        plan.formats = ['ONLINE' if 'online' in text or 'digital' in text else 'PHYSICAL']
        plan.exclusive_formats=plan.formats[:] if 'only' in text else []
        plan.excluded_formats=[];plan.physical_available_only=False
    elif re.fullmatch(r'(?:rating|rated|ratings)\s+(?:above|over|below|under|at least|at most|greater than|less than)\s+[0-5](?:\.[0-9]+)?(?: stars)?', text):
        delta = parse_query(text, facets)
        for field in ('rating_min','rating_max','rating_min_exclusive','rating_max_exclusive'):
            setattr(plan, field, getattr(delta, field))
    elif re.fullmatch(r'(?:after|before)\s+[0-9]{4}', text):
        delta = parse_query(text, facets)
        for field in ('year_min','year_max','year_min_exclusive','year_max_exclusive'):
            setattr(plan, field, getattr(delta, field))
    elif re.fullmatch(r'(?:not|exclude|without)\s+.{1,100}', text):
        delta=parse_query(query,facets)
        from scratch.search_v2c_c5er.candidate_search_v4.query_confidence import executable
        if not executable(delta):return delta,False
        plan.exclude_terms=list(dict.fromkeys([*plan.exclude_terms,*delta.exclude_terms]))[-5:]
        plan.exclude_subjects=list(dict.fromkeys([*plan.exclude_subjects,*delta.exclude_subjects]))[-5:]
        plan.excluded_formats=list(dict.fromkeys([*plan.excluded_formats,*delta.excluded_formats]))
        for field in ('rating_min','rating_max','year_min','year_max'):
            if getattr(delta,field) is not None:
                setattr(plan,field,getattr(delta,field));setattr(plan,field+'_exclusive',getattr(delta,field+'_exclusive'))
    elif re.fullmatch(r'include\s+.{1,100}\s+again', text):
        term = text.removeprefix('include ').removesuffix(' again')
        plan.exclude_terms = [x for x in plan.exclude_terms if normalize(x) != term]
        plan.exclude_subjects = [x for x in plan.exclude_subjects if normalize(x) != term]
    else:
        return new_plan(query, facets, mode), False
    plan.raw_query = query
    plan.normalized_query = text
    # Source evidence for explicit V2B field edits; inherited evidence retains
    # its original source_query, never pretends to refer to this short input.
    evidence={c['field']:c for c in plan.constraint_candidates}
    for field in ('semantic_text','subjects','title_text','author_text','exact_text','rating_min','rating_max','year_min','year_max','formats','availability','exclude_terms','excluded_formats','soft_preference'):
        if getattr(plan,field)!=getattr(previous,field):
            evidence[field]={'field':field,'operator':'SESSION_EDIT','normalized_value':getattr(plan,field),
              'source_span_start':0,'source_span_end':len(query),'source_text':query,'source_query':query,
              'recognizer_id':'session.explicit_refinement','specificity':100,'support_status':'SUPPORTED','repair_provenance':None}
    plan.constraint_candidates=list(evidence.values())[-24:]
    plan.source_spans=[{'kind':'STRUCTURED_CONSTRAINT','start':c['source_span_start'],'end':c['source_span_end'],'text':c['source_text'],'source_query':c.get('source_query',query)} for c in plan.constraint_candidates]
    plan.parser_version=PARSER_VERSION
    from scratch.search_v2c_c5er.candidate_search_v4.query_confidence import decide,validate
    validate(decide(plan))
    return plan, True

def explicit_filters(plan, filters, previous_filters=None):
    """Only changed controls overwrite a continued plan; clearing a control clears it."""
    for key, value in (filters or {}).items():
        if previous_filters is not None and value == previous_filters.get(key):
            continue
        if key == 'circulation_status':
            continue  # enforced separately by the canonical tenant executor
        empty = value is None or value == ''
        field = {'subject':'subjects','format':'formats'}.get(key, key)
        if key == 'subject':
            plan.subjects = [] if empty else [str(value)]
            plan.unknown_subject = False
        elif key == 'format':
            plan.formats = [] if empty else [str(value)]
        elif field in ('rating_min','rating_max','year_min','year_max','language','availability','author'):
            setattr(plan, 'author_text' if field == 'author' else field, None if empty else value)
            if field.startswith(('rating','year')):
                setattr(plan,field+'_exclusive',False)
        elif key == 'sort' and not empty:
            if value not in ('RELEVANCE','RATING','NEWEST','TITLE'):
                raise ValueError('Unknown sort order.')
            plan.sort = value
    return plan

def active(plan):
    return any((plan.semantic_text,plan.subjects,plan.title_text,plan.author_text,plan.exact_text,
                plan.formats,plan.availability,plan.exclude_terms,plan.exclude_subjects,plan.soft_preference,plan.unknown_subject,
                any(getattr(plan,k) is not None for k in ('rating_min','rating_max','year_min','year_max','language'))))
