"""Single frozen primary scoring pass; no candidate calls or gold alteration."""
from pathlib import Path
from collections import Counter
import json,hashlib,math
from scripts.search_combined8_score_adapter import score,summary

R=Path('reports');P='search_combined8_'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(n):return json.loads((R/(P+n+'.json')).read_text(encoding='utf-8'))
def rows(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf-8').splitlines()]
def save(n,v):
    with (R/(P+n+'.json')).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,ensure_ascii=False)
def rate(n,d):return dict(numerator=n,denominator=d,percent=100*n/d if d else None,population='FRESH_INDEPENDENT_PRIMARY1_NOW_EXPOSED')
def wilson(n,d):
    if not d:return None
    z=1.95996398454;p=n/d;mid=(p+z*z/(2*d))/(1+z*z/d);half=z*math.sqrt(p*(1-p)/d+z*z/(4*d*d))/(1+z*z/d)
    return dict(lower=mid-half,upper=mid+half,confidence=.95,limit='Descriptive iid-binomial interval; linguistic family dependence violates iid and real error risk is not established')


def main():
    freeze=load('acceptance_freeze');assert all(sha(p)==h for p,h in freeze['files'].items())
    cfg=load('independent_parser_configuration');complete=load('independent_prediction_complete')
    expected=cfg['prediction_calls_planned'];assert complete['parser_calls']==expected and complete['captured']+complete['errors']==expected
    gold=rows(R/(P+'reviewed_population_r1.jsonl'));pred=rows(R/(P+'independent_predictions.jsonl'))
    assert len(gold)==len(pred)==expected and len({x['case_id'] for x in pred})==expected
    assert {x['case_id'] for x in gold}=={x['case_id'] for x in pred}
    save('independent_scoring_started',dict(primary_score=1,gold_sha256=sha(R/(P+'reviewed_population_r1.jsonl')),prediction_sha256=sha(R/(P+'independent_predictions.jsonl'))))
    by={p['case_id']:p for p in pred};scored=[score(g,by[g['case_id']]) for g in gold];s=summary(scored)
    exact=[x for x in scored if x['exact_subtype_applicable']]
    exact_metric=rate(sum(x['exact_typed_correct'] for x in exact),len(exact))
    critical=[x for x in scored if x['critical_executed_operand_mismatches']]
    inventions=[];losses=[];neg=[];roles=[]
    for g,r in zip(gold,scored):
        for a in r['assertions']:
            if a['field'] in ['exclude_terms','exclude_subjects','excluded_formats'] and a['expected']:
                neg.append(dict(case_id=g['case_id'],assertion=a,executed=r['execution']))
            if r['execution'] is not True or a['field'] not in r['critical_executed_operand_mismatches']:continue
            e,v=a['expected'],a['actual'];empty=lambda x:x is None or x==[] or x=='' or x is False
            if not empty(e):losses.append(dict(case_id=g['case_id'],assertion=a))
            if not empty(v):inventions.append(dict(case_id=g['case_id'],assertion=a))
        req=by[g['case_id']].get('actual_plan',{}).get('decision',{}).get('query_ir_contract',{}).get('requirements',[])
        for o in g.get('expected_source_roles',[]):
            t=o.get('source_text',o.get('text',''));q=g['query_text']
            if o.get('status') in ['N/A','UNRESOLVED'] or not t or q.count(t)!=1:
                roles.append(dict(case_id=g['case_id'],applicable=False));continue
            a=q.index(t);b=a+len(t)
            found=[x for x in req if (not o.get('field') or x['field']==o['field']) and (x['source_span'][0]<=a<b<=x['source_span'][1] or a<=x['source_span'][0]<x['source_span'][1]<=b)]
            ar=sorted({x['source_role'] for x in found});am=sorted({x['modality'] for x in found})
            roles.append(dict(case_id=g['case_id'],applicable=True,oracle=o,actual_roles=ar,actual_modalities=am,role_correct=ar==[o['role']],modality_correct=am==[o['modality']]))
    applicable=[x for x in roles if x['applicable']]
    gates=load('acceptance_contract')['gates']
    verdict=dict(typed_policy=s['typed_accuracy']['percent']>=100*gates['typed_minimum'],
                 typed_exact=exact_metric['percent'] is not None and exact_metric['percent']>=100*gates['typed_minimum'],
                 execution=s['execution_accuracy']['percent']>=100*gates['execution_minimum'],
                 critical_false_execution=s['false_execution']['numerator']==0,
                 missed_valid=s['missed_execution']['percent'] is not None and s['missed_execution']['percent']<=100*gates['missed_valid_maximum'],
                 critical_mandatory_loss_or_invention=not critical,
                 structural_isolation=load('population_eligibility')['eligible'],
                 output_errors=complete['errors']==0)
    metrics=dict(candidate_id='search-smarteng-disabled-proof-8',population='FRESH_INDEPENDENT_PRIMARY1_NOW_EXPOSED',
                 summary=s,typed_exact=exact_metric,optional_notice_contexts=len(scored)-len(exact),
                 gates=verdict,parser_acceptance_passed=all(verdict.values()),primary_attempts=1,
                 contexts=len(gold),distinct_linguistic_families=len({g['family_id'] for g in gold}),
                 family_counts=dict(Counter(g['family_id'] for g in gold)),scope_counts=dict(Counter(g['scope_type'] for g in gold)),
                 structural_audit='reports/search_combined8_population_eligibility.json',
                 critical_operand_loss=rate(len({x['case_id'] for x in losses}),sum(x['execution'] is True for x in scored)),
                 critical_hard_invention=rate(len({x['case_id'] for x in inventions}),sum(x['execution'] is True for x in scored)),
                 negative_preservation=rate(sum(x['assertion']['correct'] for x in neg),len(neg)),
                 source_roles=rate(sum(x['role_correct'] for x in applicable),len(applicable)),
                 modality=rate(sum(x['modality_correct'] for x in applicable),len(applicable)),role_exclusions=len(roles)-len(applicable),
                 uncertainty=dict(typed=wilson(s['typed_accuracy']['numerator'],len(gold)),execution=wilson(s['execution_accuracy']['numerator'],len(gold)),false_execution=wilson(s['false_execution']['numerator'],s['false_execution']['denominator'])),
                 limits=['AI-only independent author/reviewer;human0','No live auth/Mongo/CAS/vector relevance qualification','No repeated acceptance or post-primary gold/candidate changes','Scalar masks do not prove arbitrary linguistic completeness','Scope labels supplied by harness, never predicted authority'],
                 role_records=roles,loss_records=losses,invention_records=inventions)
    save('independent_metrics',metrics)
    save('independent_failures',dict(typed=[x for x in scored if not x['typed_correct']],execution=[x for x in scored if not x['execution_correct']],critical=critical,scored_dimension_failures=[x for x in scored if not x['all_scored_dimensions_correct']],no_retuning=True))
    with (R/(P+'independent_scored_observations.jsonl')).open('x',encoding='utf-8') as f:
        for x in scored:f.write(json.dumps(x,ensure_ascii=False)+'\n')
    save('independent_scoring_complete',dict(primary_attempts=1,scored=len(scored),parser_acceptance_passed=all(verdict.values()),source_unchanged=all(sha(p)==h for p,h in freeze['files'].items()),gold_changed=False))
    print(json.dumps(dict(summary=s,gates=verdict,typed_exact=exact_metric)))

if __name__=='__main__':main()
