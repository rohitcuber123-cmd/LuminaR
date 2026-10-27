"""Single C5 baseline of authorized calibration parser rows. No heldout path."""
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import time
from scripts.search_v2c_c5_prepare import R,P,read,rows,sha,write

def verify():
    m=read(R/(P+'calibration_manifest.json'))
    assert all(sha(p)==h for p,h in m['files'].items())
    assert all(sha(p)==h for p,h in m['parser_source_hashes'].items())

def rate(n,d):return {'numerator':n,'denominator':d,'percent':100*n/d if d else None,'status':'MEASURED' if d else 'NOT MEASURED'}

def summarize(observations):
    from scripts.search_v2c_c4_evaluate import metrics_for
    m=metrics_for(observations)
    for v in m.values():v['status']='MEASURED' if v['denominator'] else 'NOT MEASURED'
    n=len(observations);pol=[r['assessment']['policy'] for r in observations]
    m['AUTO_EXECUTION_COVERAGE']=rate(sum(p=='AUTO_EXECUTE' for p in pol),n)
    m['EXECUTE_WITH_NOTICE_RATE']=rate(sum(p=='EXECUTE_WITH_NOTICE' for p in pol),n)
    m['CLARIFICATION_RATE']=rate(sum(p=='CLARIFY' for p in pol),n)
    m['TOTAL_EXECUTION_COVERAGE']=rate(sum(r['execution'] for r in observations),n)
    m['USER_INTERRUPTION_RATE']=rate(sum(not r['execution'] for r in observations),n)
    return m

def main():
    verify()
    corpus=rows(R/(P+'calibration.jsonl'));assert len(corpus)==280 and all(r['split']=='calibration' for r in corpus)
    parsers=[r for r in corpus if not r.get('requires_native_execution')];assert len(parsers)==50
    source=Path(__file__)
    manifest=read(R/(P+'calibration_manifest.json'));manifest['baseline_evaluator_hash']=sha(source)
    manifest['representation_rules']={'protected_entity':'Matching surrounding single/double quote delimiters are syntax, excluded from protected entity content. Raw legacy protected containment result also retained.',
        'other_fields':'C4 scorer definitions and BOTH equivalence; original expected fields immutable; native plan fields masked.'}
    write('calibration_manifest.json',manifest)
    with (R/(P+'baseline_started.json')).open('x') as f:json.dump({'evaluator_sha256':sha(source),'parser_calls_planned':50,'heldout_calls':0},f)
    from scripts.search_v2c_c_evaluate import evaluate_case,norm
    from scripts.search_v2c_c4_evaluate import rescore
    scopes=read(R/'search_v2c_c_scope_vocabularies.json');result=[];latency=[]
    for case in parsers:
        started=time.perf_counter();raw=evaluate_case(case,scopes);latency.append((time.perf_counter()-started)*1000)
        row=rescore(case,raw,normalize_formats=True)
        literal=' '.join(str(row['actual_plan'].get(k) or '') for k in ['semantic_text','title_text','exact_text','author_text'])
        def content(s):
            t=s['text']
            return t[1:-1] if len(t)>1 and t[0]==t[-1] and t[0] in ['"',"'"] else t
        row['raw_protected_preserved']=row['protected_preserved']
        row['protected_preserved']=all(norm(content(s)) in norm(literal) for s in case.get('protected_spans',[]))
        row.update(query_text=case['query_text'],mode=case['search_mode'],interpretation_confidence=row['actual_plan']['interpretation_confidence'],
            recognized_hard_fields={k:v for k,v in row['actual_plan'].items() if k in ['subjects','exclude_subjects','exclude_terms','author_text','title_text','rating_min','rating_max','year_min','year_max','formats','availability','language'] and v not in (None,[],False,'')},
            source_spans=row['actual_plan']['source_spans'],repair_provenance=[c.get('repair_provenance') for c in row['actual_plan']['constraint_candidates'] if c.get('repair_provenance')],
            unresolved_fragments=row['actual_plan']['decision']['unresolved_fragments'],safe=not row['unsafe_auto_parse'] and not row['false_filters'],
            confidence_note='Existing categorical heuristic; not a probability')
        result.append(row)
    (R/(P+'baseline_observations.jsonl')).write_text(''.join(json.dumps(x,default=str)+'\n' for x in result),encoding='utf8')
    scopes_order=['GLOBAL','PUBLIC_PATRON','PUBLIC_STAFF','PRIVATE_PATRON','PRIVATE_STAFF']
    metrics=summarize(result)
    write('baseline_metrics.json',{'status':'BASELINE_CAPTURED_NOT_ACCEPTANCE','calibration_contexts':280,'parser_evaluations':50,'native_cases_pending':230,'metrics':metrics,
        'by_scope':{s:{'parser_cases':sum(r['scope']==s for r in result),'metrics':summarize([r for r in result if r['scope']==s])} for s in scopes_order},
        'by_family':{f:summarize([r for r in result if r['family_id']==f]) for f in sorted({r['family_id'] for r in result})},
        'label_denominators':'All50 reviewed parser rows retained. Native230 retained separately; single-turn plan metrics are inapplicable. No held-out rows loaded.',
        'raw_quoted_span_containment':rate(sum(r['raw_protected_preserved'] for r in result),50),'protected_representation_adapter':manifest['representation_rules']['protected_entity'],
        'policy':'Existing C4 execution_policy and typed decisions','policy_hash':sha('search/query_calibration.py'),'parser_samples_ms':latency,
        'calibration_parser_calls':50,'production_mongo_writes':0,'heldout_parser_calls':0})
    write('decision_confusion.json',{'pairs':dict(Counter(r['expected_decision']+' -> '+r['decision'] for r in result)),
        'scope':'50 reviewed calibration parser cases only; native interaction outcomes require a separate API/state oracle.'})
    slots={}
    for slot in result[0]['assessment']['slots']:
        slots[slot]={'buckets':dict(Counter(r['assessment']['slots'][slot]['calibration_bucket'] for r in result)),
            'recognized':sum(r['assessment']['slots'][slot]['recognized'] for r in result),'risk_by_bucket':{b:{'cases':sum(r['assessment']['slots'][slot]['calibration_bucket']==b for r in result),
                'false_filter_cases':sum(bool(r['false_filters']) and r['assessment']['slots'][slot]['calibration_bucket']==b for r in result)} for b in sorted({r['assessment']['slots'][slot]['calibration_bucket'] for r in result})}}
    write('slot_calibration.json',{'slots':slots,'score_kind':'categorical evidence; no fitted probability','reliability_limit':'All parser cases executable/private patron; cannot estimate blocked safety or cross-scope reliability.'})
    verify();print(json.dumps({'parser_evaluated':50,'metrics':metrics},indent=2))

if __name__=='__main__':main()
