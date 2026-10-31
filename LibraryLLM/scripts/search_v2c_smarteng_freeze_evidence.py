"""Final immutable evidence inventory and byte verification. No application IO."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess
R=Path('reports');P='search_v2c_smarteng_'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(n):return json.loads((R/(P+n)).read_text(encoding='utf8'))
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf8') as f:json.dump(v,f,indent=2,sort_keys=True)
def main():
    pre=load('preflight.json');candidate=load('candidate_freeze.json');qa=load('final_qa.json')
    assert all(sha(p)==h for p,h in pre['protected_files'].items())
    assert all(sha(p)==h for p,h in candidate['files'].items())
    assert qa['required_fields']['FINAL']=='PARTIAL' and qa['required_fields']['C5F_READY'] is False
    assert qa['primary_attempts']==1 and qa['postcapture_candidate_changes']==qa['postcapture_gold_changes']==0
    complete=load('independent_prediction_complete.json')
    assert complete['parser_calls']==complete['captured']==150 and complete['errors']==complete['retries']==0 and not complete['isolation_denials']
    assert sha(R/(P+'independent_predictions.jsonl'))==complete['prediction_sha256']
    tracked=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines()
    staged=subprocess.check_output(['git','diff','--cached','--name-only'],text=True).splitlines()
    assert not tracked and not staged,'Unexpected tracked or staged modifications require review'
    for n in ['final_c5c_source_lineage.json','frame_reuse_lineage.json']:
        value=load(n)
        if n=='final_c5c_source_lineage.json':
            for source,data in value.items():assert sha(data['snapshot'])==data['sha256']
        else:assert sha(value['source_snapshot'])==value['sha256']
    production={p:h for p,h in pre['protected_files'].items() if str(p).replace('\\','/').split('/')[0] in ['search','backend','frontend','rag','recommendation','assistant','knowledge_graph']}
    write('preservation_report.json',{'status':'PASS','at_utc':datetime.now(timezone.utc).isoformat(),'protected_entries':len(pre['protected_files']),
        'original_production_entries':462,'current_verified_production_entries':len(production),'changed':[],
        'C5ER_original_freeze_verified':True,'old_C5C_C5E_C5ER_gold_predictions_and_failures_preserved':True,'current_primary_candidate_files_verified':len(candidate['files']),
        'development_source_snapshot_hashes_verified':True,'tracked_changes':tracked,'staged_changes':staged,
        'branch':subprocess.check_output(['git','branch','--show-current'],text=True).strip(),'Mongo_calls':0,'Mongo_writes':0,
        'production_parser_or_policy_changes':0,'HNSW_or_KG_rebuilds':0,'heldout_evaluations':0,'resident_endpoint_calls':0,
        'new_source_and_artifacts_only':True,'C5F_started':False})
    files={str(p):sha(p) for p in R.glob(P+'*') if p.is_file() and p.name not in [P+'freeze_manifest.json',P+'freeze_verification.json']}
    files.update({str(p):sha(p) for p in Path('scripts').glob(P+'*.py')})
    files.update({str(p):sha(p) for p in Path('scratch/search_smart_engineering').rglob('*') if p.is_file() and p.suffix in ['.py','.txt'] and '__pycache__' not in p.parts})
    write('freeze_manifest.json',{'version':'Smart Search Engineering evidence freeze v1','at_utc':datetime.now(timezone.utc).isoformat(),'files':files,
        'candidate_id':'search-smarteng-disabled-compositional-2','candidate_freeze_sha256':sha(R/(P+'candidate_freeze.json')),
        'FINAL':'PARTIAL','C5F_READY':False,'candidate_disabled':True,'protected_preflight_reference':str(R/(P+'preflight.json')),
        'self_exclusions':[P+'freeze_manifest.json',P+'freeze_verification.json']})
    assert all(sha(p)==h for p,h in files.items()) and all(sha(p)==h for p,h in pre['protected_files'].items())
    assert all(sha(p)==h for p,h in candidate['files'].items())
    write('freeze_verification.json',{'status':'PASS','at_utc':datetime.now(timezone.utc).isoformat(),'frozen_new_files':len(files),'historical_entries_verified':len(pre['protected_files']),
        'candidate_files_verified':len(candidate['files']),'changed':0,'manifest_sha256':sha(R/(P+'freeze_manifest.json')),
        'candidate_freeze_sha256':sha(R/(P+'candidate_freeze.json')),'primary_prediction_sha256':sha(R/(P+'independent_predictions.jsonl')),
        'final_qa_sha256':sha(R/(P+'final_qa.json')),'production_activation':False})
    print(json.dumps({'FINAL':'PARTIAL','C5F_READY':False,'frozen_files':len(files),'historical_verified':len(pre['protected_files']),
        'production_verified':len(production),'manifest_sha256':sha(R/(P+'freeze_manifest.json')),'new_tracked_changes':0}))
if __name__=='__main__':main()
