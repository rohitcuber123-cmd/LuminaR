"""Exposed development populations only; immutable per-attempt source snapshots."""
from pathlib import Path
from dataclasses import asdict
import json,sys,time,hashlib
from collections import Counter
from scripts.search_v2c_c5er_evaluation_adapter_v2 import score,summary
from scratch.search_proof_recovery_v7r1.parser import parse_query,validate,executable,assess

R=Path('reports')
def write(path,value):
    with path.open('x',encoding='utf8') as f:json.dump(value,f,indent=2,ensure_ascii=False)
def main():
    tag=sys.argv[1];assert tag.isalnum()
    snap=Path('scratch/search_proof7r1_history')/tag;snap.mkdir(parents=True)
    hashes={}
    for p in Path('scratch/search_proof_recovery_v7r1').glob('*.py'):
        hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();(snap/(p.name+'.txt')).write_bytes(p.read_bytes())
    caps=json.loads((R/'search_v2c_c5a_capability_matrix.json').read_text(encoding='utf8'))['scopes']
    for cohort,path,prior in [
        ('c5e90','search_v2c_c5e_reviewed_population_v3.jsonl','search_v2c_smarteng_final90_predictions.jsonl'),
        ('c5er150','search_v2c_c5er_reviewed_population.jsonl','search_v2c_smarteng_final150_predictions.jsonl'),
        ('smarteng150','search_v2c_smarteng_reviewed_population.jsonl','search_v2c_smarteng_independent_predictions.jsonl'),
        ('comp3_150','search_comp3_reviewed_population.jsonl','search_comp3_independent_predictions.jsonl')]:
        gold=[json.loads(s) for s in (R/path).read_text(encoding='utf8').splitlines()]
        old={p['case_id']:p for p in map(json.loads,(R/prior).read_text(encoding='utf8').splitlines())}
        predictions=[]
        for g in gold:
            st=time.perf_counter();c=caps[g['scope_type']]
            p=validate(parse_query(g['query_text'],c['subjects'],g['search_mode']),c['capabilities'])
            predictions.append({'case_id':g['case_id'],'status':'CAPTURED','typed_decision':p.decision['decision_type'],
                'executable':executable(p),'actual_plan':asdict(p),'assessment':assess(p),'elapsed_ms':(time.perf_counter()-st)*1000})
        results=[score(g,p) for g,p in zip(gold,predictions)]
        changed=[]
        fields=['subjects','include_terms','exclude_terms','exclude_subjects','author_text','title_text','formats','excluded_formats','availability','language','rating_min','rating_max','year_min','year_max','semantic_text','sort']
        for p in predictions:
            o=old[p['case_id']];delta={f:{'old':o['actual_plan'].get(f),'new':p['actual_plan'].get(f)} for f in fields if o['actual_plan'].get(f)!=p['actual_plan'].get(f)}
            if p['typed_decision']!=o['typed_decision']:delta['decision']={'old':o['typed_decision'],'new':p['typed_decision']}
            if delta:changed.append({'case_id':p['case_id'],'changes':delta})
        report={'population':cohort,'fresh':False,'source_hashes':hashes,'source_snapshot':str(snap),'summary':summary(results),
            'confusion':dict(Counter(g['expected_typed_decision']+' -> '+p['typed_decision'] for g,p in zip(gold,predictions))),
            'critical_operands':[x for x in results if x['critical_executed_operand_mismatches']],
            'decision_failures':[x for x in results if not x['typed_correct'] or not x['execution_correct']],
            'changed_predictions':changed,'gold_edited':False}
        prefix=R/('search_proof7r1_'+tag+'_'+cohort)
        with Path(str(prefix)+'_predictions.jsonl').open('x',encoding='utf8') as f:
            for p in predictions:f.write(json.dumps(p,ensure_ascii=False)+'\n')
        write(Path(str(prefix)+'_results.json'),report)
        print(cohort,json.dumps(report['summary']),flush=True)
if __name__=='__main__':main()
