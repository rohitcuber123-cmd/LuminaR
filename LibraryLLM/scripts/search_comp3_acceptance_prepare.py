"""Freeze final disabled candidate, reviewed gold and unchanged acceptance gates."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,xml.etree.ElementTree as ET
from scripts.search_v2c_c5er_evaluation_adapter_v2 import check_gold
R=Path('reports');P='search_comp3_';C=Path('scratch/search_compositional_recovery_v3')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(n):return json.loads((R/(P+n)).read_text(encoding='utf8'))
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf8') as f:json.dump(v,f,indent=2,ensure_ascii=False,sort_keys=True)
def main():
    pre=load('preflight.json');assert all(sha(p)==h for p,h in pre['protected_files'].items())
    contract=load('acceptance_contract_v2.json');assert all(sha(p)==h for p,h in contract['source_hashes'].items())
    assert load('review_reconciliation.json')['status']=='COMPLETE_DEFINITIVE'
    assert load('review_reconciliation.json')['all_cells_exactly_five']
    assert load('final_structural_isolation.json')['status']=='PASS'
    suite=next(ET.parse(R/(P+'final2_regression.xml')).getroot().iter('testsuite'))
    assert int(suite.attrib['tests'])==1515 and int(suite.attrib['failures'])==int(suite.attrib['errors'])==0
    assert load('final2_c5c_typed_decision_scoring.json')['overall']['typed_accuracy']['numerator']==644
    assert load('final2_c5c_execution_decision_scoring.json')['overall']['execution_accuracy']['numerator']==644
    for cohort in ['c5e90','c5er150','smarteng150']:
        d=load('final2_'+cohort+'_results.json');s=d['summary']
        assert s['typed_accuracy']['numerator']==s['contexts'] and s['execution_accuracy']['numerator']==s['contexts']
        assert not d['critical_operands'] and not s['false_execution_ids'] and not s['missed_execution_ids']
    assert load('requalified_retrieval_contracts_final.json')['status']=='PASS_COMPONENT_CONTRACTS_ONLY'
    assert load('final_native_contracts.json')['count']==50
    pop=R/(P+'reviewed_population.jsonl');gold=[json.loads(s) for s in pop.read_text(encoding='utf8').splitlines()]
    assert len(gold)==150 and all(check_gold(g) for g in gold)
    keys=['case_id','query_text','scope_type','workspace_type','search_mode'];inputs=R/(P+'independent_parser_inputs.jsonl')
    with inputs.open('x',encoding='utf8') as f:
        for g in gold:f.write(json.dumps({k:g[k] for k in keys},ensure_ascii=False,sort_keys=True)+'\n')
    paths=list(C.glob('*.py'))+list(Path('scratch/search_v2c_c5er/candidate_search_v4').glob('*.py'))+[
        Path('scripts/search_comp3_independent_predict.py'),Path('scripts/search_comp3_independent_score.py'),
        Path('scripts/search_v2c_c5er_evaluation_adapter_v2.py'),Path('scripts/search_v2c_c5c_score.py'),
        Path('scripts/search_v2c_c_evaluate.py'),Path('scripts/search_v2c_c4_evaluate.py')]
    code={str(p):sha(p) for p in paths};frozen=dict(code)
    names=['acceptance_contract_v2.json','authored_v2.jsonl','author_provenance_v2.json','final_blind_reviewer_packet.json',
        'independent_review.json','review_reconciliation.json','reviewed_population.jsonl','final_structural_isolation.json',
        'v2_sealed_structural_isolation.json','v2_sealed_access_audit.json','independent_parser_inputs.jsonl',
        'final2_regression.xml','final2_c5c_typed_decision_scoring.json','final2_c5c_execution_decision_scoring.json',
        'requalified_retrieval_contracts_final.json','requalified_offline_native_components_final.json','final_native_contracts.json','final_performance.json']
    for n in names:frozen[str(R/(P+n))]=sha(R/(P+n))
    write('candidate_freeze.json',{'candidate_id':'search-smarteng-disabled-compositional-3','parent':'search-smarteng-disabled-compositional-2',
        'at_utc':datetime.now(timezone.utc).isoformat(),'files':frozen,'primary_acceptance_not_started':True,'primary_attempts_allowed':1,
        'contexts':150,'actual_topologies':30,'actual_cells':30,'production_activation':False,'all_Mongo_writes_prohibited':True,
        'independence':'Separate AI author and AI reviewer; human0; model identity NOT_EXPOSED. Root implementation did not see fresh queries/labels before source stabilization. Predictor gold-blind. No desired pass rates supplied to reviewers.',
        'population_preflight':'V1 rejected5 new rows for protected topology collision. Before prediction, independent author replaced that family in V2; original population/audit retained. V2 passes all exposed and sealed structural audits.',
        'quality_gates':contract['gates'],'operational_SLO':'NOT_AGREED; real operational qualification unavailable.'})
    caps=R/'search_v2c_c5a_capability_matrix.json'
    write('independent_parser_configuration.json',{'candidate_id':'search-smarteng-disabled-compositional-3','prediction_calls_planned':150,
        'input_sha256':sha(inputs),'caps_path':str(caps),'caps_sha256':sha(caps),'parser_source_hashes':{str(p):sha(p) for p in list(C.glob('*.py'))+list(Path('scratch/search_v2c_c5er/candidate_search_v4').glob('*.py'))},
        'frozen_before_prediction_scripts':code,'gold_population_path':str(pop),'gold_population_sha256':sha(pop),'candidate_freeze_sha256':sha(R/(P+'candidate_freeze.json')),
        'gold_file_reads_by_predictor':0,'production_activation':False})
    print(json.dumps({'candidate_frozen':True,'files':len(frozen),'candidate_sha256':sha(R/(P+'candidate_freeze.json'))}))
if __name__=='__main__':main()
