"""Final candidate/gold/scorer freeze before one gold-blind primary capture."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,ast,xml.etree.ElementTree as ET
from scripts.search_v2c_c5er_evaluation_adapter_v2 import check_gold
R=Path('reports');P='search_v2c_smarteng_';C=Path('scratch/search_smart_engineering/ownership_recovery')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def rows(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf8').splitlines() if s.strip()]
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf8') as f:json.dump(v,f,indent=2,sort_keys=True,ensure_ascii=False)
def main():
    pre=load(R/(P+'preflight.json'));assert all(sha(p)==h for p,h in pre['protected_files'].items())
    assert load(R/(P+'structural_isolation.json'))['status']=='PASS'
    assert load(R/(P+'review_reconciliation.json'))['status']=='COMPLETE_DEFINITIVE'
    pop=R/(P+'reviewed_population.jsonl');gold=rows(pop);author={r['case_id']:r for r in rows(R/(P+'authored.jsonl'))}
    assert len(gold)==150 and all(check_gold(g) for g in gold)
    keys=['case_id','query_text','scope_type','workspace_type','search_mode']
    assert all(all(g[k]==author[g['case_id']][k] for k in keys) for g in gold)
    assert len({(g['scope_type'],g['decision_stratum']) for g in gold})==30
    assert all(sum(g['scope_type']==s and g['decision_stratum']==t for g in gold)==5 for s,t in {(g['scope_type'],g['decision_stratum']) for g in gold})
    suite=next(ET.parse(R/(P+'final_regression.xml')).getroot().iter('testsuite'));assert int(suite.attrib['tests'])==1438 and int(suite.attrib['failures'])==int(suite.attrib['errors'])==0
    assert load(R/(P+'retrieval_contracts_final.json'))['status']=='PASS_COMPONENT_CONTRACTS_ONLY'
    # Confirm no later focused fixture/test topology entered the fresh cohort.
    from scripts.search_v2c_c2_benchmark import structure
    focused=[]
    for p in Path('scratch/search_smart_engineering').rglob('test*.py'):
        for n in ast.walk(ast.parse(p.read_text(encoding='utf8'))):
            if isinstance(n,ast.Constant) and isinstance(n.value,str) and len(n.value)>7:focused.append({'query_text':n.value,'search_mode':'SMART'})
    used={structure(x) for x in focused}
    collisions=[g['case_id'] for g in gold if structure(g) in used];assert not collisions
    write('final_local_isolation_confirmation.json',{'status':'PASS','new_focused_strings':len(focused),'additional_collisions':[],
        'sealed_audit_reference':str(R/(P+'sealed_structural_isolation.json')),'heldout_evaluations':0,'gold_queries_unchanged':True})
    inputs=R/(P+'independent_parser_inputs.jsonl')
    with inputs.open('x',encoding='utf8') as f:
        for g in gold:f.write(json.dumps({k:g[k] for k in keys},ensure_ascii=False,sort_keys=True)+'\n')
    predictor=Path('scripts/search_v2c_smarteng_independent_predict.py')
    text=Path('scripts/search_v2c_c5e_v2_predict.py').read_text(encoding='utf8')
    old="P = 'search_v2c_c5e_v2_development_' if len(sys.argv)>1 and sys.argv[1]=='development' else 'search_v2c_c5e_independent_'"
    assert old in text;text=text.replace(old,"P = 'search_v2c_smarteng_independent_'")
    for n in ['query_plan','query_confidence','query_calibration']:text=text.replace('scratch.search_v2c_c5e.candidate_search_v2.'+n,'scratch.search_smart_engineering.ownership_recovery.parser')
    with predictor.open('x',encoding='utf8') as f:f.write(text)
    scorer=Path('scripts/search_v2c_smarteng_independent_score.py')
    text=Path('scripts/search_v2c_c5er_independent_score.py').read_text(encoding='utf8').replace("P = 'search_v2c_c5er_independent_'","P = 'search_v2c_smarteng_independent_'").replace("R / 'search_v2c_c5er_candidate_freeze.json'","R / 'search_v2c_smarteng_candidate_freeze.json'")
    with scorer.open('x',encoding='utf8') as f:f.write(text)
    paths=list(C.glob('*.py'))+list(Path('scratch/search_v2c_c5er/candidate_search_v4').glob('*.py'))+[predictor,scorer,
        Path('scripts/search_v2c_c5er_evaluation_adapter_v2.py'),Path('scripts/search_v2c_c5c_score.py'),Path('scripts/search_v2c_c_evaluate.py'),Path('scripts/search_v2c_c4_evaluate.py')]
    code={str(p):sha(p) for p in paths};frozen=dict(code)
    for n in ['acceptance_design.json','authored.jsonl','author_provenance.json','independent_review.json','review_reconciliation.json','reviewed_population.jsonl',
        'structural_isolation.json','sealed_structural_isolation.json','sealed_access_audit.json','final_local_isolation_confirmation.json',
        'independent_parser_inputs.jsonl','final_regression.xml','native_choice_tests.xml','retrieval_contracts_final.json','offline_native_components_final.json']:
        frozen[str(R/(P+n))]=sha(R/(P+n))
    write('candidate_freeze.json',{'candidate_id':'search-smarteng-disabled-compositional-2','at_utc':datetime.now(timezone.utc).isoformat(),'files':frozen,
        'primary_acceptance_not_started':True,'primary_attempts':1,'contexts':150,'scope_stratum_cells':30,'actual_topologies':30,
        'native_limit':'No Mongo writes authorized: fresh true Mongo/API/one-use durability qualification unavailable; only exact native-function read-only fixtures.',
        'production_activation':False,'architecture':'Compositional ownership IR with shared frozen native grammar/output compatibility and protected entity repairs.',
        'independence':'Fresh AI author and fresh AI reviewer, human0; no source/predictions/target rates supplied. Root did not inspect fresh queries or gold labels for implementation.'})
    caps=R/'search_v2c_c5a_capability_matrix.json'
    write('independent_parser_configuration.json',{'candidate_id':'search-smarteng-disabled-compositional-2','prediction_calls_planned':150,'input_sha256':sha(inputs),'caps_path':str(caps),'caps_sha256':sha(caps),
        'parser_source_hashes':{str(p):sha(p) for p in list(C.glob('*.py'))+list(Path('scratch/search_v2c_c5er/candidate_search_v4').glob('*.py'))},
        'frozen_before_prediction_scripts':code,'gold_population_path':str(pop),'gold_population_sha256':sha(pop),
        'candidate_freeze_sha256':sha(R/(P+'candidate_freeze.json')),'gold_file_reads_by_predictor':0,'production_activation':False})
    print(json.dumps({'candidate_frozen':True,'contexts':150,'frozen_files':len(frozen),'candidate_freeze_sha256':sha(R/(P+'candidate_freeze.json'))}))
if __name__=='__main__':main()
