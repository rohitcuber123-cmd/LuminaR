"""One score after a complete frozen gold-blind capture; never invokes candidate."""
from pathlib import Path
from collections import Counter
import json,hashlib
from scripts.search_v2c_c5er_evaluation_adapter_v2 import score,summary

R=Path('reports');P='search_proof6_'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(n):return json.loads((R/(P+n)).read_text(encoding='utf-8'))
def rows(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf-8').splitlines()]
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,ensure_ascii=False)
def rate(n,d):return {'numerator':n,'denominator':d,'percent':100*n/d if d else None,'status':'MEASURED_FRESH_INDEPENDENT' if d else 'N/A_NO_ORACLE'}

def main():
    freeze=load('acceptance_freeze.json');assert all(sha(p)==h for p,h in freeze['files'].items())
    complete=load('independent_prediction_complete.json');assert complete['parser_calls']==150 and complete['captured']+complete['errors']==150
    gold=rows(R/(P+'reviewed_population.jsonl'));pred=rows(R/(P+'independent_predictions.jsonl'));assert len(gold)==len(pred)==150
    assert {g['case_id'] for g in gold}=={p['case_id'] for p in pred}
    write('independent_scoring_started.json',{'prediction_sha256':sha(R/(P+'independent_predictions.jsonl')),'capture_complete_sha256':sha(R/(P+'independent_prediction_complete.json')),'primary_score':1})
    by={p['case_id']:p for p in pred};scored=[score(g,by[g['case_id']]) for g in gold];s=summary(scored)
    roles=[];actions=[]
    for g in gold:
        p=by[g['case_id']];requirements=p.get('actual_plan',{}).get('decision',{}).get('query_ir_contract',{}).get('requirements',[])
        for o in g.get('expected_source_roles',[]):
            text=o.get('source_text',o.get('text',''));query=g['query_text']
            if o.get('status') in ['N/A','UNRESOLVED'] or not text or query.count(text)!=1:
                roles.append({'case_id':g['case_id'],'applicable':False,'reason':'No unique reviewed source span/role oracle'});continue
            a=query.index(text);b=a+len(text)
            match=[r for r in requirements if (not o.get('field') or r['field']==o['field']) and (r['source_span'][0]<=a<b<=r['source_span'][1] or a<=r['source_span'][0]<r['source_span'][1]<=b)]
            actual_roles=sorted({r.get('source_role') for r in match if r.get('source_role')});actual_modal=sorted({r.get('modality') for r in match if r.get('modality')})
            roles.append({'case_id':g['case_id'],'oracle':o,'applicable':True,'actual_roles':actual_roles,'actual_modalities':actual_modal,
                'role_correct':actual_roles==[o['role']],'modality_correct':actual_modal==[o['modality']]})
        if g.get('completion_input') and g.get('expected_completion'):
            o=g['expected_completion'];a=p.get('completion_prediction',{})
            decision=o.get('decision',o.get('expected_typed_decision'))
            check={'case_id':g['case_id']+':completion','scope_type':g['scope_type'],'decision_stratum':decision,'expected_typed_decision':decision,
                'expected_executable':decision in ['EXECUTABLE','EXECUTABLE_WITH_NOTICE'],'expected_hard_constraints':o.get('hard_constraints',o.get('expected_hard_constraints',{})),
                'metric_applicability':o.get('metric_applicability',{}),'expected_sort':o.get('expected_sort','RELEVANCE'),'expected_semantic_remainder':o.get('expected_semantic_remainder')}
            result=score(check,a)
            actions.append({'case_id':g['case_id'],'result':result,'prediction':a,'commit_performed':a.get('commit_performed',False),'authority':'MOCK_ONLY'})
    applicable=[r for r in roles if r['applicable']]
    rolemetrics={'role':rate(sum(r['role_correct'] for r in applicable),len(applicable)),'modality':rate(sum(r['modality_correct'] for r in applicable),len(applicable)),'excluded':len(roles)-len(applicable),'records':roles,'limitation':'Exact source/field/role agreement under independently reviewed annotations; not arbitrary semantic entailment.'}
    actionmetrics={'contexts':len(actions),'typed_correct':rate(sum(a['result']['typed_correct'] for a in actions),len(actions)),
        'execution_correct':rate(sum(a['result']['execution_correct'] for a in actions),len(actions)),
        'strict_fields_correct':rate(sum(a['result']['all_scored_dimensions_correct'] for a in actions),len(actions)),'actual_Mongo_CAS_qualification':False,'records':actions}
    contract=load('acceptance_contract.json')['gates']
    gates={'typed':s['typed_accuracy']['percent']>=100*contract['typed_minimum'],'execution':s['execution_accuracy']['percent']>=100*contract['execution_minimum'],
        'critical_false_execution':s['false_execution']['numerator']==0,'missed_valid':s['missed_execution']['percent']<=100*contract['missed_valid_maximum'],
        'mandatory_loss_or_invention':not s['critical_executed_operand_case_ids'],'native_completion':all(a['result']['all_scored_dimensions_correct'] for a in actions)}
    metrics={'candidate_id':'search-smarteng-disabled-proof-6','population':'FRESH_INDEPENDENT_PRIMARY_ATTEMPT1_NOW_EXPOSED','summary':s,
        'confusion':dict(Counter(r['expected_decision']+' -> '+str(r['decision']) for r in scored)),'source_roles':rolemetrics,'native_completion':actionmetrics,
        'gates':gates,'parser_acceptance_passed':all(gates.values()),'source_role_gate':'Reported separately; no unregistered numerical threshold invented.',
        'authorization_gate':'N/A_LIVE_UNVERIFIED; read-only native fixtures separate. No production readiness from parser sample.',
        'primary_attempts':1,'gold_changed':False,'recapture_after_failure_permitted':False,'human_reviewers':0}
    write('independent_metrics.json',metrics)
    with (R/(P+'independent_scored_observations.jsonl')).open('x',encoding='utf-8') as f:
        for r in scored:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    write('independent_failures.json',{'failures':[r for r in scored if not r['all_scored_dimensions_correct']],'typed_failures':[r for r in scored if not r['typed_correct']],
        'critical_executed_operand_mismatches':[r for r in scored if r['critical_executed_operand_mismatches']],'no_candidate_retuning':True})
    write('independent_scoring_complete.json',{'prediction_sha256':sha(R/(P+'independent_predictions.jsonl')),'gold_sha256':sha(R/(P+'reviewed_population.jsonl')),
        'scored':len(scored),'primary_attempts':1,'parser_acceptance_passed':all(gates.values()),'source_frozen_unchanged':True})
    print(json.dumps({'summary':s,'gates':gates,'role_accuracy':rolemetrics['role'],'modality_accuracy':rolemetrics['modality'],'completion_contexts':len(actions)}))
if __name__=='__main__':main()
