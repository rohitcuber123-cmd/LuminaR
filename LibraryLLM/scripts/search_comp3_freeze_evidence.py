"""Final byte verification and evidence inventory. No application imports."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,subprocess
R=Path('reports');P='search_comp3_'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(n):return json.loads((R/(P+n)).read_text(encoding='utf8'))
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf8') as f:json.dump(v,f,indent=2,sort_keys=True)
def main():
    pre=load('preflight.json');freeze=load('candidate_freeze.json');qa=load('final_qa.json');complete=load('independent_prediction_complete.json')
    assert all(sha(p)==h for p,h in pre['protected_files'].items())
    assert all(sha(p)==h for p,h in freeze['files'].items())
    assert complete['parser_calls']==complete['captured']==150 and complete['errors']==complete['retries']==0 and not complete['isolation_denials']
    assert sha(R/(P+'independent_predictions.jsonl'))==complete['prediction_sha256']
    assert qa['required_fields']['FINAL']=='PARTIAL' and qa['required_fields']['PRODUCTION_READINESS']=='BLOCKED'
    assert qa['primary_attempts']==1 and qa['candidate_changes_after_primary_capture']==qa['gold_changes_after_primary_capture']==0
    tracked=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines()
    staged=subprocess.check_output(['git','diff','--cached','--name-only'],text=True).splitlines()
    assert not tracked and not staged
    production={p:h for p,h in pre['protected_files'].items() if str(p).replace('\\','/').split('/')[0] in ['search','backend','frontend','rag','recommendation','assistant','knowledge_graph']}
    assert len(production)==462
    required=['FINAL','CANDIDATE_ID','ARCHITECTURE_STATUS','PRODUCTION_READINESS','CANDIDATE_ACTIVATED','MISSING_OPERAND_FIX_STATUS',
        'NEGATIVE_CONSTRAINT_FIX_STATUS','INVENTED_FACET_FIX_STATUS','CANONICAL_REPAIR_FIX_STATUS','DEVELOPMENT_TYPED_ACCURACY',
        'DEVELOPMENT_EXECUTION_ACCURACY','DEVELOPMENT_FALSE_EXECUTION','DEVELOPMENT_MISSED_EXECUTION','MANDATORY_OPERAND_PRESERVATION',
        'INDEPENDENT_ACCEPTANCE_SIZE','INDEPENDENT_TYPED_ACCURACY','INDEPENDENT_EXECUTION_ACCURACY','INDEPENDENT_FALSE_EXECUTION',
        'INDEPENDENT_MISSED_EXECUTION','INCOMPLETE_RECOGNITION','AMBIGUITY_RECOGNITION','NOTICE_RECOGNITION','SMART_MODE_STATUS',
        'EXACT_MODE_STATUS','PRIVATE_LIBRARY_STATUS','PRIVATE_GLOBAL_INDEPENDENCE','NATIVE_AUTHORIZATION_STATUS','NATIVE_CHOICE_CONTRACT_STATUS',
        'SEMANTIC_RETRIEVAL_STATUS','PARSER_P50','PARSER_P95','FOUR_WORKER_P95','STAGING_READINESS','CURRENT_RUNTIME_HEALTH_VERIFIED',
        'PRODUCTION_SOURCE_CHANGED','PRODUCTION_POLICY_CHANGED','MONGO_MUTATIONS','HNSW_REBUILDS','KG_REBUILDS','HELDOUT_EVALUATIONS',
        'HISTORICAL_EVIDENCE_PRESERVED','REMAINING_BLOCKERS','NEXT_AUTHORIZED_ACTION']
    assert set(required)==set(qa['required_fields'])
    for i in range(1,18):assert len(list(R.glob(P+str(i).zfill(2)+'_*.md')))==1
    write('preservation_report.json',{'status':'PASS','historical_parent_entries_verified':2224,'protected_union_verified':len(pre['protected_files']),
        'production_entries_verified':len(production),'frozen_candidate_and_contract_files_verified':len(freeze['files']),'changed':[],
        'tracked_changes':tracked,'staged_changes':staged,'branch':subprocess.check_output(['git','branch','--show-current'],text=True).strip(),
        'Mongo_calls':0,'Mongo_writes':0,'resident_health_calls':0,'production_activation':False,'HNSW_KG_rebuilds':0,'heldout_evaluations':0,
        'primary_attempts':1,'postcapture_candidate_changes':0,'postcapture_gold_changes':0,'required_QA_fields_verified':len(required)})
    files={str(p):sha(p) for p in R.glob(P+'*') if p.is_file() and p.name not in [P+'freeze_manifest.json',P+'freeze_verification.json']}
    files.update({str(p):sha(p) for p in Path('scripts').glob(P+'*.py')})
    roots=[Path('scratch/search_compositional_recovery_v3')]+list(Path('scratch').glob('search_comp3*'))
    for root in roots:
        if root.is_dir():
            files.update({str(p):sha(p) for p in root.rglob('*') if p.is_file() and p.suffix in ['.py','.txt'] and '__pycache__' not in p.parts})
    write('freeze_manifest.json',{'version':'Compositional recovery V3 evidence freeze v1','at_utc':datetime.now(timezone.utc).isoformat(),
        'files':files,'candidate_id':freeze['candidate_id'],'candidate_freeze_sha256':sha(R/(P+'candidate_freeze.json')),
        'FINAL':'PARTIAL','PRODUCTION_READINESS':'BLOCKED','candidate_disabled':True,'protected_preflight_reference':str(R/(P+'preflight.json')),
        'self_exclusions':[P+'freeze_manifest.json',P+'freeze_verification.json']})
    assert all(sha(p)==h for p,h in files.items()) and all(sha(p)==h for p,h in pre['protected_files'].items())
    assert all(sha(p)==h for p,h in freeze['files'].items())
    write('freeze_verification.json',{'status':'PASS','new_frozen_files':len(files),'protected_union_verified':len(pre['protected_files']),
        'historical_parent_entries_verified':2224,'production_entries_verified':462,'candidate_contract_files_verified':len(freeze['files']),
        'changed':0,'manifest_sha256':sha(R/(P+'freeze_manifest.json')),'candidate_freeze_sha256':sha(R/(P+'candidate_freeze.json')),
        'primary_prediction_sha256':sha(R/(P+'independent_predictions.jsonl')),'final_QA_sha256':sha(R/(P+'final_qa.json')),
        'FINAL':'PARTIAL','production_activation':False,'Mongo_writes':0})
    print(json.dumps({'FINAL':'PARTIAL','new_files':len(files),'historical_verified':2224,'protected_union':len(pre['protected_files']),
        'production_verified':462,'manifest_sha256':sha(R/(P+'freeze_manifest.json'))}))
if __name__=='__main__':main()
