"""Isolated native-compatible refinement through complete accepted source.

The caller owns authentication/session/CAS. No mutable plan can authorize a new
predicate. Native edit language is desugared, then the entire source is compiled.
"""
from copy import deepcopy
import re
from .parser import parse_query,validate,executable,normalize,_decode
from .proposals import FAMILIES
from .contract import digest

TOPIC={'semantic','semantic_residue','subject','author','title','preference'}

def _subtract(source,requirements,fields):
    chars=list(source)
    for r in requirements:
        if r.field in fields:
            for i in range(*r.source_span):chars[i]=' '
    return ''.join(chars)

def refine(previous,query,facets,mode='SMART'):
    raw=str(query);text=normalize(raw)
    if mode!='SMART' or previous is None or previous.mode!=mode:return parse_query(raw,facets,mode),False
    if not text:return validate(deepcopy(previous)),True
    if not executable(validate(deepcopy(previous))):return parse_query(raw,facets,mode),False
    ir=_decode(previous.decision['query_ir_contract']);source=ir.raw_query
    filters=deepcopy(ir.trusted_controls.get('filters',{}));omit=list(ir.trusted_controls.get('omit',()))
    rewrite=raw;fields=set();continued=True;rule='native.field_delta'
    if text in ('something different','new search','start over','clear search context'):
        p=parse_query('',facets,mode);continued=False;rule='native.reset'
    else:
        instead=re.fullmatch(r'(?:show me\s+)?(.+?)\s+instead',text) or re.fullmatch(r'instead\s+(?:show me\s+)?(.+)',text)
        if instead and instead[1] not in ('physical','online','digital'):
            fields=TOPIC;rewrite=instead[1];rule='native.topic_replacement'
        elif re.fullmatch(r'(?:only |show |show me |show only )?(?:ones |books )?(?:online|digital|physical|hard copy)(?: only| instead)?(?: ones| books)?',text):
            fields={'format','excluded_format','availability'};rewrite=re.sub(r'\s+instead$','',raw,flags=re.I);rule='native.format_replacement'
        elif text in ('only highly rated','highly rated','only highly rated ones'):
            fields={'rating'};rewrite='rated at least 4';rule='native.highly_rated_definition'
        elif re.fullmatch(r'(?:after|before)\s+\d{4}',text):
            fields={'year'};rewrite='published '+raw;rule='native.publication_delta'
        elif text in ('remove rating filter','show all ratings','any rating'):
            fields={'rating'};rewrite='';rule='native.remove_rating'
        elif text in ('any year','all years','remove year filter'):
            fields={'year'};rewrite='';rule='native.remove_year'
        elif text in ('show all formats','all formats','any format'):
            fields={'format','excluded_format'};rewrite='';rule='native.remove_format'
        elif text in ('any availability','remove availability filter'):
            fields={'availability'};rewrite='';rule='native.remove_availability'
        else:
            delta=parse_query(raw,facets,mode)
            if not executable(delta):return delta,False
            di=_decode(delta.decision['query_ir_contract'])
            fields={r.field for r in di.requirements if r.field in FAMILIES and r.field not in ['exclude','excluded_subject','excluded_format']}
            negative=any(r.field in ['exclude','excluded_subject','excluded_format'] for r in di.requirements)
            preference=any(r.field=='preference' for r in di.requirements)
            topic=any(r.field in ['semantic','semantic_residue','subject','title','author'] for r in di.requirements)
            if not (negative or preference or fields) or topic and not negative:
                return delta,False
            if preference:fields.add('preference')
        # Remove only the explicitly edited field's complete source owners.
        rest=_subtract(source,ir.requirements,fields)
        for f in fields:
            for name in FAMILIES.get(f,[]):filters.pop(name,None)
        accepted=rest+('; '+rewrite if rewrite else '')
        if len(accepted)>500:raise ValueError('Accepted source exceeds parser limit')
        p=validate(parse_query(accepted,facets,mode,filters,omit))
        if not executable(p):return p,False
        # Nothing outside the explicitly edited families may disappear.
        after=_decode(p.decision['query_ir_contract'])
        def signature(r):return (r.field,r.operator,digest(r.value),r.state,r.ownership,r.polarity)
        remaining=list(after.requirements)
        for r in ir.requirements:
            if r.field in fields or r.ownership!='MANDATORY':continue
            match=next((x for x in remaining if signature(x)==signature(r)),None)
            if match is None:raise ValueError('Refinement lost an untouched mandatory requirement')
            remaining.remove(match)
    p.decision['accepted_source_refinement']={'submitted_query':raw,'accepted_source':p.raw_query,'parent_source_digest':digest(source),
        'accepted_source_digest':digest(p.raw_query),'rule':rule,'edited_fields':sorted(fields),'full_reparse':True,'commit_performed':False}
    # Native display/edit provenance is separate from the compiled IR. It does
    # not pretend that inherited constraints came from this short command.
    if raw and rule=='native.topic_replacement':
        for field,value in [('subjects',p.subjects),('semantic_text',p.semantic_text)]:
            if value:p.constraint_candidates.append({'field':field,'operator':'SESSION_EDIT','normalized_value':value,'source_query':raw,'source_text':raw,'source_span_start':0,'source_span_end':len(raw),'recognizer_id':rule,'support_status':'SUPPORTED'})
    return p,continued
