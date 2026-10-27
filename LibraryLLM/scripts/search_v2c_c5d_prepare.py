"""C5D integrity discovery. Standard library only; never imports a parser."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

R=Path('reports')
P='search_v2c_c5d_'
def load(path):return json.loads(Path(path).read_text(encoding='utf8'))
def rows(path):return [json.loads(s) for s in Path(path).read_text(encoding='utf8').splitlines() if s.strip()]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def write(name,value):
    with (R/(P+name)).open('x',encoding='utf8') as f:f.write(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False)+'\n')
def jsonl(name,values):
    with (R/(P+name)).open('x',encoding='utf8') as f:
        for value in values:f.write(json.dumps(value,sort_keys=True,ensure_ascii=False)+'\n')

def main():
    assert not list(R.glob(P+'*')),'Do not overwrite an existing C5D milestone.'
    c=load(R/'search_v2c_c5c_freeze_manifest.json');b=load(R/'search_v2c_c5b_freeze_manifest.json');a=load(R/'search_v2c_c5a_freeze_manifest.json')
    pre=load(R/'search_v2c_c5c_preflight.json');final=load(R/'search_v2c_c5c_report_validation.json')
    checks={}
    for name,files in [('C5A_payload',a['files']),('C5B_payload',b['files']),('C5C_payload',c['files']),('protected',pre['protected_files']),('C5C_final_validation',final['evidence'])]:
        bad=[p for p,h in files.items() if sha(p)!=h];assert not bad,(name,bad)
        checks[name]={'verified_files':len(files),'mismatches':bad}
    assert sha(R/'search_v2c_c5c_predictions.jsonl')=='0a5ebcca95b4acec9363db860cdf76b90e5c2c7b9915b4ad959090e5e65bc704'
    assert sha(R/'search_v2c_c5b_freeze_manifest.json')==c['C5B_input_freeze_sha256']
    assert sha(R/'search_v2c_c5b_corpus_admission.json')==c['C5B_final_admission_sha256']
    sealed=load(R/'search_v2c_c5b_structural_isolation.json')['preservation']
    assert all(sha(x['path'])==x['sha256_after'] for x in sealed)
    # Only hash sealed files. No heldout records, private labels or predictions decoded.
    protected=dict(pre['protected_files'])
    protected.update({str(p):sha(p) for p in R.glob('search_v2c_c*') if p.is_file() and not p.name.startswith(P)})
    protected.update({str(p):sha(p) for p in Path('scripts').glob('search_v2c_c*.py') if not p.name.startswith(P)})
    sources=['search/query_plan.py','search/query_constraints.py','search/query_numeric.py','search/query_repair.py','search/query_confidence.py',
             'search/query_calibration.py','search/query_execution.py','search/query_interaction.py','search/interaction_api.py','search/session_store.py',
             'search/scope_authorization.py','backend/services/library_catalogue_experience.py','backend/services/library_inventory_access.py',
             'scripts/search_v2c_c5c_score.py','scripts/search_v2c_c_evaluate.py','scripts/search_v2c_c4_evaluate.py']
    qa=load(R/'search_v2c_c5c_final_qa.json')
    assert qa['FINAL']=='PASS' and qa['ELIGIBLE_PARSER_CONTEXTS']==644 and qa['FALSE_EXECUTION_COUNT']==191
    write('preflight.json',{'status':'PASS','at_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'protected_files':protected,
          'source_hashes':{p:sha(p) for p in sources},'C5B_freeze_sha256':sha(R/'search_v2c_c5b_freeze_manifest.json'),
          'C5B_admission_sha256':sha(R/'search_v2c_c5b_corpus_admission.json'),'C5C_freeze_sha256':sha(R/'search_v2c_c5c_freeze_manifest.json'),
          'C5C_prediction_sha256':sha(R/'search_v2c_c5c_predictions.jsonl'),'C5C_gold_sha256':sha(R/'search_v2c_c5b_expected_labels.jsonl'),
          'sealed_hash_only_checks':sealed,'sealed_contents_decoded':0,'new_production_parser_calls':0,
          'authorization_sha256':sha(r'C:\Users\balak\.codex\attachments\c63aa2f9-5509-4581-8c79-051c7e897f67\Pasted text.txt'),
          'scope':'Static causal/contract investigation and isolated replay of existing predictions; no production/model/native evaluation.'})
    print(json.dumps({'preflight':'PASS','C5C_payload':len(c['files']),'protected_existing_files':len(protected),'new_parser_calls':0}))

if __name__=='__main__':main()
