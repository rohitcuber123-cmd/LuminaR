"""Freeze definitive independently reviewed gold and gold-blind inputs before capture."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import json,hashlib
from scripts.search_v2c_c5er_evaluation_adapter_v2 import check_gold

R=Path('reports');P='search_proof6_'
def load(n):return json.loads((R/(P+n)).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,ensure_ascii=False)

def main():
    source=load('source_freeze.json');assert all(sha(p)==h for p,h in source['files'].items())
    assert load('step1_exit_gate.json')['eligible']
    assert load('author2_structural_isolation.json')['status']=='PASS'
    assert load('author_reconciliation.json')['status']=='BLIND_NORMATIVE_RECONCILIATION_COMPLETE'
    a=[json.loads(s) for s in (R/(P+'authored.jsonl')).read_text(encoding='utf-8').splitlines()]
    review=load('independent_review.json');mapping=load('reviewer_id_map.json');by={mapping[x['review_id']]:x for x in review['cases']}
    keys=['expected_typed_decision','expected_executable','expected_hard_constraints','metric_applicability','expected_sort','expected_semantic_remainder','expected_soft_preferences','expected_source_roles','expected_completion','semantic_justification']
    final=[]
    lists=['subjects','exclude_subjects','exclude_terms','formats','exclusive_formats','excluded_formats']
    for g in a:
        q=dict(g);r=by[g['case_id']]
        for k in keys:
            if k in r:q[k]=r[k]
        q['decision_stratum']=q['expected_typed_decision'];q['independent_review_id']=r['review_id'];q['review_status']='DEFINITIVE_INDEPENDENT_AI_REVIEWED_PRE_CAPTURE'
        check_gold(q)
        assert all(isinstance(q['expected_hard_constraints'][k],list) or q['metric_applicability'][k]['status']=='UNRESOLVED' for k in lists)
        assert q['query_text']==g['query_text'] and len(q['query_text'])<=500
        final.append(q)
    assert len(final)==150 and len({g['family_id'] for g in final})==30
    cells=Counter((g['scope_type'],g['decision_stratum']) for g in final);assert len(cells)==30 and set(cells.values())=={5}
    with (R/(P+'reviewed_population.jsonl')).open('x',encoding='utf-8') as f:
        for g in final:f.write(json.dumps(g,ensure_ascii=False,sort_keys=True)+'\n')
    inputs=R/(P+'independent_parser_inputs.jsonl')
    with inputs.open('x',encoding='utf-8') as f:
        for g in final:
            row={k:g[k] for k in ['case_id','query_text','scope_type','workspace_type','search_mode']}
            if g.get('completion_input'):row['completion_input']=g['completion_input']
            f.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')
    write('review_reconciliation.json',{'status':'COMPLETE_DEFINITIVE','contexts':150,'families':30,'actual_topologies':load('author2_structural_isolation.json')['distinct_actual_topologies'],
        'all_scope_stratum_cells_exactly_five':True,'typed_and_execution_author_reviewer_agreement':150,'schema_correction':'exclusive_formats boolean -> reviewed native lists:145 empty and5 ONLINE; known global year floor2014 retained. Author acknowledged before predictions.','queries_changed_after_review':0,'candidate_predictions_visible':False,'gold_basis':'Independent reviewer complete records plus original author independent acknowledgement; originals preserved.','human_authors_reviewers':0,'AI_author':'/root/v6_fresh_author','AI_reviewer':'/root/v6_blind_reviewer','actual_runtime_model_identity':'NOT_EXPOSED'})
    paths=[Path(p) for p in source['files']]+[Path(p) for p in ['scripts/search_proof6_independent_predict.py','scripts/search_proof6_independent_score.py','scripts/search_proof6_acceptance_prepare.py','scripts/search_proof6_population_audit.py','scripts/search_v2c_c5er_evaluation_adapter_v2.py','scripts/search_v2c_c5c_score.py','scripts/search_v2c_c_evaluate.py','scripts/search_v2c_c4_evaluate.py','scripts/search_v2c_c5a_sealed_audit.py','scripts/search_v2c_c2_benchmark.py']]
    files={str(p):sha(p) for p in paths}
    names=['source_freeze.json','step1_exit_gate.json','acceptance_contract.json','authored.jsonl','author_provenance.json','author_reconciliation.json','blind_author_brief.json','blind_reviewer_packet.json','reviewer_id_map.json','independent_review.json','review_reconciliation.json','reviewed_population.jsonl','author2_structural_isolation.json','author2_sealed_structural_isolation.json','author2_sealed_access_audit.json','independent_parser_inputs.jsonl','readiness_migration.json','readiness_tests.xml']
    for n in names:files[str(R/(P+n))]=sha(R/(P+n))
    caps=R/'search_v2c_c5a_capability_matrix.json';files[str(caps)]=sha(caps)
    write('acceptance_freeze.json',{'candidate_id':source['candidate_id'],'at_utc':datetime.now(timezone.utc).isoformat(),'files':files,'primary_attempts_allowed':1,'primary_attempts_started':0,'population':150,'families':30,'topologies':30,'completion_actions':sum(bool(g.get('completion_input')) for g in final),'long_contexts':sum(len(g['query_text'])>150 for g in final),'human_reviewers':0,'AI_author_and_reviewer_separate':True,'candidate_source_frozen_before_authoring':True,'Mongo_writes':0,'production_activation':False,'heldout_evaluations':0})
    write('independent_parser_configuration.json',{'candidate_id':source['candidate_id'],'prediction_calls_planned':150,'input_sha256':sha(inputs),'caps_path':str(caps),'caps_sha256':sha(caps),'parser_source_hashes':source['files'],'frozen_before_prediction_scripts':{str(p):sha(p) for p in paths},'gold_population_path':str(R/(P+'reviewed_population.jsonl')),'gold_population_sha256':sha(R/(P+'reviewed_population.jsonl')),'acceptance_freeze_sha256':sha(R/(P+'acceptance_freeze.json')),'gold_reads_by_predictor':0,'primary_attempts_allowed':1})
    print(json.dumps({'frozen':True,'files':len(files),'population':150,'families':30,'topologies':30,'completion_actions':sum(bool(g.get('completion_input')) for g in final),'freeze_sha256':sha(R/(P+'acceptance_freeze.json'))}))
if __name__=='__main__':main()
