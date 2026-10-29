"""V11 server-owned preview policy. C4 remains the default execution policy.

The advanced compiler is a pinned, archived V10 dependency. It is deliberately
lazy and never imported by default search or EXACT. No new model is involved.
"""
from dataclasses import asdict
from copy import deepcopy
import os,re,hashlib,json
from fastapi import HTTPException
from search import query_plan as native

VERSION='search-smarteng-feature-preview-11'
REGISTRY_VERSION='V11-native-capabilities-v3'
QUERY_LIMIT=500
RELEASE_DECISION='ADVANCED_SMART_FROZEN_STABLE_SEARCH_RETAINED'


def preview_allowed(actor):
    enabled=os.getenv('LUMINAR_SMART_SEARCH_PREVIEW','0')=='1'
    users={x.strip() for x in os.getenv('LUMINAR_SMART_SEARCH_PREVIEW_USERS','').split(',') if x.strip()}
    development=os.getenv('LUMINAR_DEPLOYMENT_MODE','production') in ('development','test')
    return development and enabled and str(actor.get('sub','')) in users and bool(actor.get('sid'))


def require_preview(actor):
    if not preview_allowed(actor):raise HTTPException(404,'Search preview is unavailable.')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()


def normalize_source(source,facets=()):
    """Equivalent explicit field syntax only; preserve original separately.

    Quoted bibliographic operands are opaque. No bare topic is a category.
    Unsupported corrections stay in source for the proof compiler to block.
    """
    edits=[]
    quoted=[m.span() for m in re.finditer(r'"[^"\n]*"|“[^”\n]*”',source)]
    patterns=[
      (r'\b(?:include|require)\s+(?:the\s+)?(?:category|subject)\s*[:=]?\s*"([^"\n]+)"',lambda m:'include subject "'+m[1]+'"'),
      (r'\b(?:omit|exclude)\s+(?:the\s+)?"([^"\n]+)"\s+(?:category|subject)\b',lambda m:'exclude subject "'+m[1]+'"'),
      (r'\bpublication\s+years?\s+(?:from\s+)?(\d{4})\s+(?:through|to)\s+(\d{4})\b',lambda m:'published between '+m[1]+' and '+m[2]),
      (r'\border\s+(?:the\s+results\s+)?alphabetically\s+by\s+title\b',lambda m:'sort by title'),
    ]
    registered={' '.join(f.casefold().split()):f for f in facets}
    # Recognize the explicit syntactic frame once, then resolve its operand.
    # Do not compile a pair of regular expressions per taxonomy entry.
    for m in re.finditer(r'\b(include|require|choose|omit|exclude)\s+(?:the\s+)?([^;,.!?"\n]{1,200}?)\s+(?:category|subject)\b',source,re.I):
        value=registered.get(' '.join(m[2].casefold().split()))
        if value is None or any(a<=m.start()<b for a,b in quoted):continue
        replacement=('exclude' if m[1].casefold() in ('omit','exclude') else 'include')+' subject "'+value+'"'
        edits.append((m.start(),m.end(),m[0],replacement))
    for pattern,render in patterns:
        for m in re.finditer(pattern,source,re.I):
            if any(a<=m.start()<b for a,b in quoted):continue
            if any(m.start()<b and a<m.end() for a,b,_,_ in edits):continue
            edits.append((m.start(),m.end(),m[0],render(m)))
    accepted=source
    for a,b,old,new in sorted(edits,reverse=True):accepted=accepted[:a]+new+accepted[b:]
    if len(accepted)>QUERY_LIMIT:raise ValueError('Accepted search exceeds 500 characters; shorten the request.')
    provenance=[];delta=0
    for a,b,old,new in sorted(edits):
        provenance.append(dict(span=[a,b],accepted_span=[a+delta,a+delta+len(new)],original=old,accepted=new,kind='EQUIVALENT_FIELD_SYNTAX'))
        delta+=len(new)-(b-a)
    return accepted,provenance


def source_contract(original,accepted,provenance,ir,controls):
    """Map accepted-source atoms back to the immutable submitted source.

    An equivalent syntax replacement maps to its complete original phrase;
    unchanged segments map character-for-character. Controls are explicitly
    separate request operands, never fabricated source spans.
    """
    def original_point(point,end=False):
        delta=0
        for edit in provenance:
            a,b=edit['accepted_span'];x,y=edit['span']
            if point<a or end and point==a:return point-delta
            if a<=point<b or end and a<point<=b:return y if end else x
            delta+=(b-a)-(y-x)
        return point-delta
    units=[]
    for r in ir.get('requirements',[]):
        a,b=r['source_span'];controlled=r['provenance'].get('origin')=='TRUSTED_CONTROL'
        x,y=(None,None) if controlled else (original_point(a),original_point(b,True))
        units.append(dict(requirement_id=r['requirement_id'],domain=r['field'],operator=r['operator'],operand=r['value'],
            modality=r['modality'],polarity=r['polarity'],ownership=r['ownership'],support=r['support'],resolution=r['resolution'],
            accepted_span=[a,b],accepted_text=accepted[a:b],original_span=None if controlled else [x,y],
            original_text=None if controlled else original[x:y],source_role='STRUCTURED_CONTROL' if controlled else r['source_role']))
    return dict(version='V11-source-intent-v1',original_source=original,accepted_source=accepted,original_digest=digest(original),
        accepted_digest=digest(accepted),ir_digest=digest(ir),units=units,normalizations=provenance,structured_controls=controls or {},
        limitation='Finite recognition and source mapping do not establish arbitrary natural-language completeness.')


def compile_query(source,facets=(),*,mode='SMART',filters=None,capabilities=None):
    if not isinstance(source,str) or len(source)>QUERY_LIMIT:raise ValueError('Search supports at most 500 characters.')
    if mode not in native.MODES:raise ValueError('Unknown search mode.')
    if mode!='SMART':
        # C4 literal/lexical path: no experimental interpretation is imported.
        from search.query_confidence import validate
        p=validate(native.parse_query(source,facets,mode,filters),capabilities)
        return p,source,[]
    from scratch.search_architecture_v10 import parser as compiler
    accepted,provenance=normalize_source(source,facets)
    p=compiler.validate(compiler.parse_query(accepted,facets,mode,filters),capabilities)
    metadata={k:deepcopy(p.decision[k]) for k in ('query_intent','interpretation_contract','source_obligations','clarification_targets') if k in p.decision}
    for notice in p.decision.get('repair_notices',[]):
        if 'from' not in notice and 'from_text' in notice:notice['from']=notice['from_text']
    ir=p.decision.get('query_ir_contract',{})
    missing=[]
    opaque=[m.span() for m in re.finditer(r'"[^"\n]*"|“[^”\n]*”',accepted)]
    for m in re.finditer(r'\b((?:(?:require|with)\s+)?format\s*(?:is\s+|set\s+to\s+)?(?:\[[^\]]*\]|\.{3}|_{2,})?)\s*(?=[;.!?]|$|\band\b)',accepted,re.I):
        a,b=m.span(1)
        if any(x<=a<y for x,y in opaque):continue
        clause_start=max(accepted.rfind(c,0,a) for c in ';.!?')+1
        prefix=accepted[clause_start:a].strip()
        if prefix and not re.match(r'^(?:with|require)\b',m[1],re.I) and not re.search(r'\band\s*$',prefix,re.I):continue
        from scratch.search_architecture_v10.language import mode_of
        clause_end=min([i for c in ';.!?' if (i:=accepted.find(c,b))>=0] or [len(accepted)])
        if mode_of(accepted[clause_start:clause_end])!='MANDATORY':continue
        represented=any(r['field']=='format' and r['source_span'][0]<b and a<r['source_span'][1] and r['ownership']=='MANDATORY' for r in ir.get('requirements',[]))
        if not represented:missing.append(dict(requirement_id=digest(['format',[a,b],accepted[a:b]])[:20],field='format',span=[a,b],text=accepted[a:b],state='OMITTED_REQUIRED_VALUE'))
    # Capability-first precedence: completing an unsupported domain cannot make
    # it executable. Preserve its missing state/source for an accurate question.
    unsupported=[r for r in ir.get('requirements',[]) if r['ownership']=='MANDATORY' and
        (r['field'] in ('page_count','price','publisher','edition') or (capabilities or {}).get(r['field']) is False)]
    if unsupported:
        compiler.decide(p,'UNSUPPORTED','V11_UNSUPPORTED_CAPABILITY',fields=sorted({r['field'] for r in unsupported}))
        p.decision['safe_public_message']='This catalogue cannot filter '+', '.join(sorted({r['field'].replace('_',' ') for r in unsupported}))+'. Remove that requirement to continue.'
    elif p.unknown_subject:
        compiler.decide(p,'UNSUPPORTED','V11_UNKNOWN_SELECTED_CATEGORY',fields=['subject'])
        p.decision['safe_public_message']='That category is not registered in this catalogue. Choose a listed category or search it as a topic.'
    elif any(n.get('kind')=='typo' for n in p.decision.get('repair_notices',[])):
        compiler.decide(p,'AMBIGUOUS','V11_CONFIRM_SOURCE_CORRECTION',fields=['subject'])
        p.decision['safe_public_message']='Apply the suggested category correction, or keep your wording as a topic.'
    elif missing:
        compiler.decide(p,'INCOMPLETE','V11_MISSING_FORMAT_OPERAND',fields=['format'])
        p.decision['safe_public_message']='Which format do you require? Choose an available format or edit the query.'
    elif p.decision.get('decision_type','').startswith('EXECUTABLE') and accepted.strip() and not p.semantic_text and not PreparedRuntime.has_hard(p) and p.sort=='RELEVANCE':
        compiler.decide(p,'INCOMPLETE','V11_MISSING_SEARCH_OBJECTIVE',fields=['topic'])
        p.decision['safe_public_message']='Add a topic, title, author or an explicit filter to search.'
    p.decision.update(metadata)
    p.decision['v11_missing_requirements']=missing
    p.parser_version=VERSION;p.decision['parser_version']=VERSION
    p.decision['preview_source']={'original':source,'accepted':accepted,'provenance':provenance,
        'source_digest':digest(source),'accepted_digest':digest(accepted),'ir_digest':digest(ir),'registry':REGISTRY_VERSION}
    p.decision['v11_source_contract']=source_contract(source,accepted,provenance,ir,filters)
    p.decision['v11_source_contract']['unresolved_source_requirements']=missing
    return p,accepted,provenance


class PreparedRuntime:
    """Adapter to native execution; never loads/saves native C4 sessions."""
    candidate_limit=5000
    def __init__(self,plan,actor,library_id=None,staff=False):
        self.plan=deepcopy(plan);self.actor=(str(actor['sub']),actor.get('sid'));self.library_id=library_id;self.staff=staff
        self.scanned=0;self.exhausted=False

    def resolve(self,query,actor,facets,*,mode='SMART',library_id=None,staff=False,**options):
        if (str(actor['sub']),actor.get('sid'))!=self.actor or (library_id,staff)!=(self.library_id,self.staff):
            raise HTTPException(404,'Search state is unavailable.')
        if query!=self.plan.raw_query or mode!=self.plan.mode:raise HTTPException(409,'Search source changed.')
        return deepcopy(self.plan),None

    @staticmethod
    def matches(plan,row):
        # Absence is not a known negative capability. Global canonical flags
        # are explicitly derived by native execution from current entitlements.
        negative=set(plan.excluded_formats)
        for fmt in plan.exclusive_formats:
            negative.add('PHYSICAL' if fmt=='ONLINE' else 'ONLINE')
        for fmt in negative:
            if type(row.get('has_physical' if fmt=='PHYSICAL' else 'has_online')) is not bool:return False
        return native.matches(plan,row)

    @staticmethod
    def semantic_query(plan):
        advice=[r['source_text'] for r in plan.decision.get('query_ir_contract',{}).get('requirements',[]) if r['ownership']=='ADVISORY']
        return '; '.join(dict.fromkeys([str(plan.semantic_text or ''),*advice])).strip('; ')

    @staticmethod
    def has_hard(plan):
        return bool(plan.subjects or plan.exclude_subjects or plan.author_text or plan.title_text or plan.exact_text or
            plan.rating_min is not None or plan.rating_max is not None or plan.year_min is not None or plan.year_max is not None or
            plan.language or plan.formats or plan.excluded_formats or plan.exclusive_formats or plan.availability or plan.exclude_terms)

    @staticmethod
    def pushdown(plan):
        """Only authoritative tenant-local fields; ratings/stock need hydration."""
        predicates=[]
        if plan.language:predicates.append({'language':{'$regex':'^'+re.escape(plan.language)+'$','$options':'i'}})
        year={}
        if plan.year_min is not None:year['$gt' if plan.year_min_exclusive else '$gte']=plan.year_min
        if plan.year_max is not None:year['$lt' if plan.year_max_exclusive else '$lte']=plan.year_max
        if year:predicates.append({'publication_year':year})
        for fmt in plan.formats:
            if fmt in ('ONLINE','BOTH'):predicates.append({'has_online':True})
            if fmt in ('PHYSICAL','BOTH'):predicates.append({'has_physical':True})
        for fmt in plan.excluded_formats:predicates.append({'has_physical' if fmt=='PHYSICAL' else 'has_online':False})
        return [{'$match':{'$and':predicates}}] if predicates else []

    def collect(self,collection,pipeline):
        """Bounded keyset refill, stable row identity; no offset before filters.

        Scan all admitted rows up to the budget so native sort is deterministic
        within this window. Counts remain explicitly incomplete.
        """
        rows=[];last=None
        while len(rows)<self.candidate_limit:
            size=min(1000,self.candidate_limit-len(rows))
            page=[*pipeline]
            if last is not None:page.append({'$match':{'library_book_id':{'$gt':last}}})
            page.extend([{'$sort':{'library_book_id':1}},{'$limit':size+1}])
            batch=list(collection.aggregate(page));more=len(batch)>size;batch=batch[:size]
            if any(not isinstance(r.get('library_book_id'),str) for r in batch):raise HTTPException(503,'Library candidate identities are unavailable.')
            if batch and (last is not None and batch[0]['library_book_id']<=last or len({r['library_book_id'] for r in batch})!=len(batch)):
                raise HTTPException(503,'Library candidate ordering changed. Retry your search.')
            rows.extend(batch)
            if not more:self.exhausted=True;break
            last=batch[-1]['library_book_id']
        self.scanned=len(rows)
        return rows

    def finish(self,response):
        for row in response['results']:
            if self.library_id and row.get('library_id')!=self.library_id:raise HTTPException(503,'Library result scope could not be verified.')
            if not self.matches(self.plan,row):raise HTTPException(503,'Search result constraints changed during serialization.')
        response['total']=None
        response['coverage']={'kind':'RANKED_CANDIDATE_WINDOW','complete':False,
            'local_candidate_budget':self.candidate_limit if self.library_id else None,'global_ranked_window_limit':None if self.library_id else 50,
            'scanned':self.scanned if self.library_id else None,'local_window_exhausted':self.exhausted if self.library_id else None,
            'notice':'Filters are enforced. Results cover a bounded retrieval window; this is not a complete catalogue count.'}
        return response
