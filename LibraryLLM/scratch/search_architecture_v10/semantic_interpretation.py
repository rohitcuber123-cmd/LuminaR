"""Additive compositional proposals. No native fields or scope authority here.

All patterns operate outside quotes. Overlays own a domain within a clause,
never discard unrelated mandatory requirements. Validation replays proposals;
the independent obligation scanner remains a distinct, finite coverage check.
"""
from dataclasses import replace
import re
from .language import primitive, SourceUnit, segment, visible, mode_of
from .contract import QueryIR, State


def propose(raw):
    result=[]
    def add(unit,field,op,value,status='SUPPORTED',ownership='MANDATORY'):
        r=primitive(raw,unit,field,op,value,status,ownership)
        r=replace(r,provenance={**r.provenance,'origin':'V10_INTERPRETATION','recognizer':'v10.compositional_source'})
        result.append(r)
    for u in segment(raw):
        text=u.text;v=visible(text)
        # A negated preference statement is background, not a format demand.
        if ((re.search(r'\b(?:hypothetical|background|slogan|folder name|details about the group)\b',v,re.I)
             and not re.search(r'\b(?:require|must)\b',v,re.I)) or
            (re.search(r'\b(?:colleague|friend|teacher)\s+said\b',v,re.I) and re.search(r'\b(?:ideal|would|hypothetical)\b',v,re.I)) or
            re.search(r'\b(?:not (?:an? |making .*?a )?(?:instruction|condition)|not as alternatives or optional preferences)\b',v,re.I)):
            add(u,'context','NON_OPERATIVE',text,ownership='NON_OPERATIVE');continue
        if re.match(r'^(?:also\s+)?(?:make me staff|switch|keep the search in|do not infer an author)',v,re.I):
            add(u,'context','NON_OPERATIVE',text,ownership='NON_OPERATIVE');continue
        neg=re.search(r'\bno\s+(?:returned\s+)?(?:record|book|result)\s+(?:may|must|should)\s+(?:offer|have|include)\s+(physical|online|digital)\s+(?:access|format)\b',v,re.I)
        if mode_of(text)!='MANDATORY' and not neg:continue
        # Bounded field-label repair requires an explicit field operand frame.
        for m in re.finditer(r'\b(languge|langauge)\s+(?:set\s+to\s+|is\s+)?([A-Za-z]+)\b',v,re.I):
            unit=SourceUnit(u.start+m.start(),u.start+m.end(),text[m.start():m.end()])
            add(unit,'language','EXACT',m[2].casefold())
        # Unresolved correction/reference syntax cannot authorize a broader
        # search when the existing compiler has not represented that edit.
        if re.search(r'\bcorrection\b',v,re.I) and re.search(r'\bcorrection\s*:',visible(raw),re.I):
            add(u,'relationship','ALTERNATIVE',{'source':text,'fields':['rating']},'AMBIGUOUS')
        if re.search(r'\b(?:require|include)\s+and\s+exclude\b',v,re.I):
            add(u,'relationship','CONFLICT',{'source':text},'CONTRADICTORY')
        # Deferral and operator alternatives remain unresolved even across '?'.
        if re.search(r'\b(?:minimum\s+or\s+maximum|maximum\s+or\s+minimum)\b',v,re.I):
            add(u,'relationship','ALTERNATIVE',{'fields':['rating'],'source':text},'AMBIGUOUS')
        if re.search(r'\bor\b',v,re.I) and re.search(r'\b(?:choose later|decide later|choose|undecided)\b',visible(raw),re.I):
            add(u,'relationship','ALTERNATIVE',{'fields':['subject'],'source':text},'AMBIGUOUS')
        # Implicit publication-year comparators use only four-digit operands;
        # they cannot turn publisher names or arbitrary numbers into dates.
        explicit_year=re.search(r'\b(?:published|publication|issued)\b',v,re.I)
        paired_year=re.search(r'\bafter\s+\d{4}\s+and\s+before\s+\d{4}\b',v,re.I)
        topical_year=re.search(r'\b(?:about|history|events?|remember|met in)\b',v,re.I)
        if (explicit_year or paired_year and not topical_year) and not re.search(r'\b(?:publisher|price|cost|edition|pages?)\b',v,re.I):
            for m in re.finditer(r'\b(after|before)\s+(\d{4})\b',v,re.I):
                add(SourceUnit(u.start+m.start(),u.start+m.end(),raw[u.start+m.start():u.start+m.end()]),
                    'year','>' if m[1].lower()=='after' else '<',int(m[2]))
        for m in re.finditer(r'\b(?:ratings?|rated)\s+(\d(?:\.\d+)?)\s+(?:to|through)\s+(\d(?:\.\d+)?)\b',v,re.I):
            add(SourceUnit(u.start+m.start(),u.start+m.end(),text[m.start():m.end()]),'rating','RANGE',[float(m[1]),float(m[2])])
        # Explicit negative access is mandatory even when phrased as 'no record may'.
        if neg:add(u,'excluded_format','NOT','PHYSICAL' if neg[1].lower()=='physical' else 'ONLINE')
        if re.search(r'\bphysical\s+copy\s+available\s+to\s+borrow\s+now\b',v,re.I):
            add(u,'availability','PRESENT','PHYSICAL_REQUESTABLE')
        # Topic-wide unsupported filters must still block when a topical phrase
        # precedes the requirement in the same sentence.
        for domain,pat in [('page_count',r'\b(?:under|over|at least|at most|less than|more than)\s+\d+\s+pages?\b'),
                           ('price',r'(?:\b(?:price|cost)\b\s*(?:under|over|above|below|[<>]=?)\s*[$₹€£]?\s*\d+|\b(?:under|over)\s*[$₹€£]\s*\d+)')]:
            m=re.search(pat,v,re.I)
            if m:add(SourceUnit(u.start+m.start(),u.start+m.end(),text[m.start():m.end()]),domain,'UNENFORCEABLE',m[0],'UNSUPPORTED')
    return tuple(result)


def overlay(raw,ir):
    rr=list(ir.requirements)
    for r in propose(raw):
        a,b=r.clause_span
        if r.field=='context' or r.field=='excluded_format' and re.search(r'\bno\s+(?:returned\s+)?(?:record|book|result)\b',r.source_text,re.I):
            rr=[x for x in rr if not (x.source_span[0]<b and a<x.source_span[1])]
        elif r.field in ('rating','availability','language'):
            rr=[x for x in rr if not ((x.field==r.field or r.field=='rating' and r.operator=='RANGE' and x.field in ('ambiguous_number','semantic_residue')) and x.source_span[0]<b and a<x.source_span[1])]
        elif r.field=='year':
            rr=[x for x in rr if not (x.field=='year' and x.source_span[0]<b and a<x.source_span[1])]
        elif r.field=='relationship':
            domains=r.value.get('fields',[])
            rr=[x for x in rr if not (x.field in domains and x.source_span[0]<b and a<x.source_span[1])]
        rr.append(r)
    # A numeric range span can replace overlapping legacy equality atoms;
    # keep semantic text in source order while adding optional advice to it.
    unique={r.requirement_id:r for r in rr}
    return QueryIR(raw,tuple(unique.values()),ir.clauses,ir.trusted_controls,version=10)


def evidence(r,raw):
    return any((x.field,x.operator,x.value,x.source_span,x.ownership)==
               (r.field,r.operator,r.value,r.source_span,r.ownership) for x in propose(raw))
