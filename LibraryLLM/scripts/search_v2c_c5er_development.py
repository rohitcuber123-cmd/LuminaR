"""Exposed-only development capture and strict scalar diagnostics."""
from pathlib import Path
from datetime import datetime,timezone
from dataclasses import asdict
from collections import Counter
import hashlib,json,sys,importlib,time
R=Path('reports');P='search_v2c_c5er_'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def rows(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf8').splitlines() if s.strip()]
def main():
    version=sys.argv[1];assert version.isdigit()
    namespace='scratch.search_v2c_c5er.'+('candidate_search' if version=='1' else 'candidate_search_v'+version)
    module=importlib.import_module(namespace+'.query_plan');confidence=importlib.import_module(namespace+'.query_confidence')
    caps=load(R/'search_v2c_c5a_capability_matrix.json')['scopes']
    source=Path(namespace.replace('.','/'));files={str(p):sha(p) for p in source.glob('*.py')}
    gold=rows(R/'search_v2c_c5e_reviewed_population_v3.jsonl');observed=[]
    for g in gold:
        start=time.perf_counter();plan=confidence.validate(module.parse_query(g['query_text'],caps[g['scope_type']]['subjects']),caps[g['scope_type']]['capabilities'])
        observed.append({'case_id':g['case_id'],'expected_decision':g['expected_typed_decision'],'expected_execution':g['expected_executable'],
           'decision':plan.decision['decision_type'],'execution':confidence.executable(plan),'actual_plan':asdict(plan),'elapsed_ms':(time.perf_counter()-start)*1000})
    prefix=P+'v'+version+'_exposed_c5e_'
    with (R/(prefix+'predictions.jsonl')).open('x',encoding='utf8') as f:
        for r in observed:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    summary={'source_hashes':files,'captured_at_utc':datetime.now(timezone.utc).isoformat(),'population':'Exposed C5E90; development only','contexts':90,
        'typed_correct':sum(r['expected_decision']==r['decision'] for r in observed),'execution_correct':sum(r['expected_execution']==r['execution'] for r in observed),
        'false_execution':[r['case_id'] for r in observed if not r['expected_execution'] and r['execution']],
        'missed_execution':[r['case_id'] for r in observed if r['expected_execution'] and not r['execution']],
        'confusion':dict(Counter(r['expected_decision']+' -> '+r['decision'] for r in observed)),
        'prior_C5E_25_false_and10_missed_included':True,'independent_acceptance':False,'model_calls':0,'database_calls':0}
    with (R/(prefix+'summary.json')).open('x',encoding='utf8') as f:json.dump(summary,f,indent=2)
    print(json.dumps({k:summary[k] for k in ['typed_correct','execution_correct','false_execution','missed_execution','confusion']}))
if __name__=='__main__':main()
