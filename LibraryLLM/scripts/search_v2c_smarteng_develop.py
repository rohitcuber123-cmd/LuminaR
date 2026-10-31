"""Versioned exposed development only; immutable predictions and source snapshots."""
from pathlib import Path
from dataclasses import asdict
from collections import Counter
from datetime import datetime,timezone
import json,hashlib,time,sys
R=Path('reports');P='search_v2c_smarteng_'
def main():
    tag=sys.argv[1];assert tag.replace('_','').isalnum()
    from scratch.search_smart_engineering.parser import parse_query,validate,executable,assess
    sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('scratch/search_smart_engineering').glob('*.py')}
    snap=Path('scratch/search_smart_engineering/history')/tag;snap.mkdir(parents=True)
    for p in Path('scratch/search_smart_engineering').glob('*.py'):(snap/(p.name+'.txt')).write_bytes(p.read_bytes())
    gold=[json.loads(s) for s in (R/'search_v2c_c5er_reviewed_population.jsonl').read_text(encoding='utf8').splitlines()]
    caps=json.loads((R/'search_v2c_c5a_capability_matrix.json').read_text(encoding='utf8'))['scopes'];pred=[]
    for g in gold:
        start=time.perf_counter();plan=validate(parse_query(g['query_text'],caps[g['scope_type']]['subjects']),caps[g['scope_type']]['capabilities'])
        pred.append({'case_id':g['case_id'],'typed_decision':plan.decision['decision_type'],'executable':executable(plan),'actual_plan':asdict(plan),
            'assessment':assess(plan),'elapsed_ms':(time.perf_counter()-start)*1000,'expected_decision':g['expected_typed_decision'],'expected_execution':g['expected_executable']})
    with (R/(P+tag+'_predictions.jsonl')).open('x',encoding='utf8') as f:
        for p in pred:f.write(json.dumps(p,ensure_ascii=False)+'\n')
    summary={'cohort':'Exposed C5ER150, development only','contexts':150,'source_hashes':sources,'source_snapshot':str(snap),'at_utc':datetime.now(timezone.utc).isoformat(),
        'typed_correct':sum(p['typed_decision']==p['expected_decision'] for p in pred),'execution_correct':sum(p['executable']==p['expected_execution'] for p in pred),
        'false_execution':[p['case_id'] for p in pred if not p['expected_execution'] and p['executable']],
        'missed_execution':[p['case_id'] for p in pred if p['expected_execution'] and not p['executable']],
        'confusion':dict(Counter(p['expected_decision']+' -> '+p['typed_decision'] for p in pred))}
    with (R/(P+tag+'_summary.json')).open('x',encoding='utf8') as f:json.dump(summary,f,indent=2)
    print(json.dumps({k:summary[k] for k in ['typed_correct','execution_correct','false_execution','missed_execution','confusion']}))
if __name__=='__main__':main()
