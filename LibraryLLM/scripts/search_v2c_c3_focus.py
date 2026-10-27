"""Capture bounded development grammar evidence before the final evaluation."""
from dataclasses import asdict
import hashlib,json
from pathlib import Path
from search.query_plan import parse_query
from search.query_numeric import range_contradiction,valid_numeric_domain

R=Path('reports')
FACETS=['Fiction','Romance','Mystery','Wizards','History','Neural Networks']
def main():
    bounds=[]
    for low in (0,1,4,4.5,5):
        for high in (0,1,4,4.5,5):
            for le in (False,True):
                for he in (False,True):
                    expected=low>high or low==high and (le or he)
                    actual=range_contradiction(low,high,le,he)
                    assert actual==expected
                    bounds.append(dict(low=low,high=high,low_exclusive=le,high_exclusive=he,contradictory=actual))
    domains=[{'field':field,'value':value,'valid':valid_numeric_domain(field,value)} for field,values in [('rating',[-1,0,4.5,5,6,float('inf')]),('year',[999,1000,1984,2020.5,2100,2101])] for value in values]
    (R/'search_v2c_c3_range_validation.json').write_text(json.dumps({'central_helper':'search/query_numeric.py','truth_table_cases':len(bounds),'passed':True,'bounds':bounds,'domain_checks':domains,'empty_strict_domain':'Strict rating >5 or <0 is typed UNSUPPORTED, never clamped; mathematical clause contradictions remain CONTRADICTORY'},indent=2))
    rows=[]
    for query in ['fiction by George Orwell','books by Terry Pratchett about witches','books about Isaac Asimov','Asimov books about robots','Foundation by Asimov','not about Borges; written by Borges','published by 2019','filter by subject Fiction','books called 1984','books about .NET 8','stories where characters do not trust machines']:
        plan=parse_query(query,FACETS)
        rows.append({'query':query,'plan':asdict(plan)})
        for c in plan.constraint_candidates:
            assert query[c['source_span_start']:c['source_span_end']]==c['source_text']
    (R/'search_v2c_c3_author_topic_boundaries.json').write_text(json.dumps({'population':'Bounded DEVELOPMENT and accepted-contract syntax examples, not sealed cases','cases':rows,'source_offsets_valid':True,'canonical_negative_predicate':'exclude_subjects only for resolved canonical subjects; literal exclusion retained for unresolved text phrases','source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path('search/query_constraints.py'),Path('search/query_repair.py')] }},indent=2))
    print('Range truth table100; focused source offsets valid')
if __name__=='__main__':main()
