"""Pure execution proof over the completed IR and its native projection."""
from dataclasses import asdict
import re,math
from .contract import State,Proof,digest
from .proposals import FAMILIES
from .projection import _apply
from .source_roles import partition,annotate,Modality,governing
from types import SimpleNamespace
from scratch.search_v2c_c5er.candidate_search_v4 import query_constraints as grammar
from scratch.search_v2c_c5er.candidate_search_v4.query_plan import normalize,QueryPlan
from scratch.search_v2c_c5er.candidate_search_v4.query_session import explicit_filters,omit_fields

HARD_FIELDS=tuple(dict.fromkeys(k for names in FAMILIES.values() for k in names))
def projection(plan):return {k:getattr(plan,k) for k in HARD_FIELDS}

def validate_ir(ir,plan,expected_projection=None):
    violations=[];states=[];fields=[];covered=[];units=partition(ir.raw_query)
    from .obligations import verify_ir as audit
    for item in audit(ir)['violations']:violations.append(('coverage',item['reason']))
    if ir.raw_query!=plan.raw_query:violations.append(('source','QUERY_SOURCE_MISMATCH'))
    for r in ir.requirements:
        if r.ownership=='REMOVED_BY_CONTROL':continue
        a,b=r.source_span
        if r.provenance.get('origin')!='TRUSTED_CONTROL':
            if not (0<=a<b<=len(ir.raw_query)) or ir.raw_query[a:b]!=r.source_text:
                violations.append((r.requirement_id,'INVALID_SOURCE_SPAN'));continue
            if not r.clause_span[0]<=a<b<=r.clause_span[1]:violations.append((r.requirement_id,'INVALID_CLAUSE_OWNER'))
        if r.provenance.get('origin') not in ['TRUSTED_CONTROL','V9_INTERPRETATION','V10_INTERPRETATION'] and r.operator!='NON_SEARCH_INQUIRY':
            expected=annotate(r,units)
            if any(getattr(r,k)!=v for k,v in expected.items()):violations.append((r.requirement_id,'SOURCE_ROLE_MISMATCH'))
        if r.ownership=='ADVISORY' and r.field!='preference':violations.append((r.requirement_id,'UNPROVEN_ADVISORY_DEMOTION'))
        if r.ownership=='NON_OPERATIVE':
            u=governing(units,a,b)
            if r.field!='context' or r.provenance.get('origin') not in ['V9_INTERPRETATION','V10_INTERPRETATION'] and (u is None or u.modality!=Modality.NON_OPERATIVE):violations.append((r.requirement_id,'UNPROVEN_BACKGROUND_DEMOTION'))
        if r.ownership in ['ADVISORY','NON_OPERATIVE']:covered.append(r.requirement_id);continue
        if r.modality in [Modality.SHOULD,Modality.MAY,Modality.NON_OPERATIVE] and r.representation=='HARD_FILTER':violations.append((r.requirement_id,'NON_MANDATORY_HARD_FILTER'))
        state=State(r.state)
        if state in [State.EMPTY,State.OMITTED,State.PLACEHOLDER]:states.append('INCOMPLETE');fields.append(r.field)
        elif state==State.AMBIGUOUS:states.append('AMBIGUOUS');fields.append(r.field)
        elif state==State.CONTRADICTORY:states.append('CONTRADICTORY');fields.append(r.field)
        elif state==State.UNSUPPORTED or r.support!='SUPPORTED':states.append('UNSUPPORTED');fields.append(r.field)
        elif r.representation=='HARD_FILTER':
            if r.field not in FAMILIES:violations.append((r.requirement_id,'UNSUPPORTED_PROJECTION_FIELD'))
            if r.value in (None,'',[]):violations.append((r.requirement_id,'EMPTY_RESOLVED_VALUE'))
            if not r.provenance.get('recognizer'):violations.append((r.requirement_id,'NO_SOURCE_RECOGNIZER'))
            if r.provenance.get('origin')=='V10_INTERPRETATION':
                from .semantic_interpretation import evidence
                if not evidence(r,ir.raw_query):violations.append((r.requirement_id,'V10_SOURCE_EVIDENCE_MISMATCH'))
            elif r.provenance.get('origin')=='V10_INTERPRETATION':
                from .semantic_interpretation import evidence
                if not evidence(r,ir.raw_query):violations.append((r.requirement_id,'V10_SOURCE_EVIDENCE_MISMATCH'))
            elif r.provenance.get('origin')=='V9_INTERPRETATION':
                from .validation import local_evidence
                if not local_evidence(r):violations.append((r.requirement_id,'V9_SOURCE_EVIDENCE_MISMATCH'))
            elif r.provenance.get('origin')!='TRUSTED_CONTROL':
                text=r.provenance.get('interpreted_text',r.source_text)
                from scratch.search_v2c_c5er.candidate_search_v4.semantic_safety import VOCABULARY,distance_one
                for edit in r.provenance.get('grammar_edits',[]):
                    if ir.raw_query[edit['start']:edit['end']]!=edit['from'] or edit['to'].casefold() not in VOCABULARY or not distance_one(edit['from'].casefold(),edit['to'].casefold()):
                        violations.append((r.requirement_id,'UNPROVEN_GRAMMAR_REPAIR'))
                # Numeric values/operators must be reproduced by the same pure
                # bounded recognizer, not trusted from a proposed scalar.
                if r.field in ['rating','year']:
                    # Reproduce operators in their complete owning clause.
                    # A second conjunct can inherit the explicit numeric domain.
                    from .source_repair import prepare_source
                    prepared,_,offsets,_=prepare_source(ir.raw_query[slice(*r.clause_span)])
                    check=grammar.Source(prepared)
                    from scratch.search_v2c_c5er.candidate_search_v4.requirement_ledger import own
                    own(check,())
                    from .numeric_proposals import recognize
                    recognize(check)
                    (grammar.ratings if r.field=='rating' else grammar.years)(check)
                    reproduced=any(c.field==r.field and c.operator==r.operator and c.normalized_value==r.value and r.clause_span[0]+offsets[c.source_span_start]==a and r.clause_span[0]+offsets[c.source_span_end-1]+1==b for c in check.items)
                    if not reproduced and r.provenance.get('recognizer')=='source.declared_domain_comparator':
                        from .source_analysis import label_repairs
                        domains={x['domain'] for x in label_repairs(ir.raw_query)}
                        m=re.fullmatch(r'(minimum|maximum)\s+(?:of\s+)?(\d+(?:\.\d+)?)',r.source_text,re.I)
                        reproduced=bool(domains=={r.field} and m and float(m[2])==r.value and r.operator==('>=' if m[1].casefold()=='minimum' else '<='))
                    if not reproduced:violations.append((r.requirement_id,'NUMERIC_EVIDENCE_MISMATCH'))
                elif r.field in ['author','title']:
                    cues=r'\b(?:by|author|creator|writer)\b' if r.field=='author' else r'\b(?:titled|called|named|title)\b'
                    if not re.search(cues,text,re.I) or normalize(r.value) not in normalize(text):violations.append((r.requirement_id,'ENTITY_EVIDENCE_MISMATCH'))
                elif r.field in ['subject','excluded_subject']:
                    fact=r.provenance.get('canonical_fact')
                    if not fact or fact.get('value')!=r.value or not fact.get('vocabulary_digest'):
                        violations.append((r.requirement_id,'NO_SCOPED_CANONICAL_PROOF'))
                    else:
                        from .vocabulary import FacetVocabulary
                        term=fact.get('input_term','')
                        resolved,_,_=FacetVocabulary([r.value]).resolve(term)
                        if not term or normalize(term) not in normalize(text) or resolved!=r.value:violations.append((r.requirement_id,'CANONICAL_EVIDENCE_MISMATCH'))
                elif r.field=='literal':
                    from .source_units import frames
                    explicit=any(f.field=='literal' and f.start==a and f.end==b and normalize(f.value)==normalize(r.value) for f in frames(ir.raw_query))
                    if r.operator!='EXACT' or normalize(r.value) not in normalize(text) or not (explicit or re.search(r'\b(?:search|find|look)\s+for\s+["“]',text,re.I)):violations.append((r.requirement_id,'LITERAL_EVIDENCE_MISMATCH'))
                elif r.field=='exclude':
                    if r.polarity!='NEGATIVE' or r.operator!='TEXT_NOT' or normalize(r.value) not in normalize(text) or not re.search(r'\b(?:exclude|excluding|without|except|not|reject|forbid)\b',text,re.I):
                        violations.append((r.requirement_id,'UNPROVEN_NEGATIVE_DOMAIN'))
                elif r.field in ['format','excluded_format']:
                    pattern={'ONLINE':r'online|digital','PHYSICAL':r'physical|hard\s+cop','BOTH':r'both|physical.*(?:online|digital)|(?:online|digital).*physical'}.get(r.value,r'(?!)')
                    if not re.search(pattern,text,re.I):violations.append((r.requirement_id,'FORMAT_EVIDENCE_MISMATCH'))
                elif r.field=='language' and normalize(r.value) not in normalize(text):violations.append((r.requirement_id,'LANGUAGE_EVIDENCE_MISMATCH'))
                elif r.field=='sort':
                    pattern={'TITLE':'title','RATING':'rating|rated','NEWEST':'newest','RELEVANCE':'relevance'}.get(r.value,r'(?!)')
                    if not re.search(pattern,text,re.I):violations.append((r.requirement_id,'SORT_EVIDENCE_MISMATCH'))
            covered.append(r.requirement_id)
        else:covered.append(r.requirement_id)
    active=[r for r in ir.requirements if r.state==State.SUPPLIED and r.support=='SUPPORTED' and r.ownership=='MANDATORY' and r.field in FAMILIES]
    unresolved={f for r in ir.requirements if r.field=='relationship' and isinstance(r.value,dict) for f in r.value.get('fields',[])}
    active=[r for r in active if r.field not in unresolved and not(r.field=='excluded_subject' and 'subject' in unresolved)]
    rebuilt=QueryPlan(ir.raw_query,'SMART')
    _apply(rebuilt,[SimpleNamespace(field=r.field,operator=r.operator,normalized_value=r.value,support_status='SUPPORTED') for r in active],set(FAMILIES))
    explicit_filters(rebuilt,ir.trusted_controls.get('filters',{}));omit_fields(rebuilt,ir.trusted_controls.get('omit',()))
    if projection(plan)!=projection(rebuilt):violations.append(('projection','UNPROVEN_PLAN_MUTATION'))
    if expected_projection is not None and projection(plan)!=expected_projection:violations.append(('projection','RECORDED_PROJECTION_MISMATCH'))
    # Soft retrieval text is also part of the source contract. It cannot be
    # silently replaced after compilation while retaining a hard-filter proof.
    from .surface import semantic_projection
    semantic=semantic_projection(ir)
    if plan.semantic_text!=semantic:violations.append(('semantic','UNPROVEN_SEMANTIC_MUTATION'))
    for name,value in projection(plan).items():
        if name.endswith('_exclusive') or name=='physical_available_only':
            if type(value) is not bool:violations.append((name,'INVALID_BOOL_SCHEMA'))
        elif name in ['rating_min','rating_max','year_min','year_max']:
            if value is not None and (type(value) not in [int,float] or not math.isfinite(value)):violations.append((name,'INVALID_NUMBER_SCHEMA'))
        elif isinstance(getattr(plan,name),list) and not all(isinstance(v,str) for v in value):violations.append((name,'INVALID_LIST_SCHEMA'))
    if violations:states.append('UNSUPPORTED')
    decision=next((k for k in ['CONTRADICTORY','INCOMPLETE','AMBIGUOUS','UNSUPPORTED'] if k in states),'EXECUTABLE')
    return Proof(decision=='EXECUTABLE',decision,'IR_PROOF_VALID' if decision=='EXECUTABLE' else 'IR_'+decision,tuple(sorted(set(fields))),tuple(violations),tuple(covered))
