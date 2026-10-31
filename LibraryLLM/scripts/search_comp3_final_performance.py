"""Matched parser-only measurements; no application/network imports."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import json,time,math,statistics,hashlib,cProfile,pstats,io
import psutil

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stats(v):
    v=sorted(v);return {'count':len(v),'p50_ms':statistics.median(v),'p95_ms':v[math.ceil(.95*len(v))-1],'max_ms':max(v)}
def main():
    baseline=Path('scratch/search_comp3_optimization_baseline2');baseline.mkdir()
    for p in Path('scratch/search_compositional_recovery_v3').glob('*.py'):(baseline/p.name).write_bytes(p.read_bytes())
    (baseline/'vocabulary.py').write_bytes(Path('scratch/search_comp3_history/profile_before/vocabulary.py.txt').read_bytes())
    prior=Path('scratch/search_comp3_history/profile_before/query_ir.py.txt').read_text(encoding='utf8')
    start=prior.index('            if not resolved and 4<=');end=prior.index('            if resolved:',start)
    q=(baseline/'query_ir.py').read_text(encoding='utf8').replace('            if resolved:',prior[start:end]+'            if resolved:')
    (baseline/'query_ir.py').write_text(q,encoding='utf8')
    from scratch.search_comp3_optimization_baseline2 import parser as old
    from scratch.search_compositional_recovery_v3 import parser as new
    R=Path('reports')
    qs=[json.loads(s) for s in (R/'search_v2c_c5er_reviewed_population.jsonl').read_text(encoding='utf8').splitlines()]
    caps=json.loads((R/'search_v2c_c5a_capability_matrix.json').read_text())['scopes']
    proc=psutil.Process();results={};outputs={}
    for label,module in [('before',old),('after',new)]:
        def call(g):
            c=caps[g['scope_type']];st=time.perf_counter()
            p=module.validate(module.parse_query(g['query_text'],c['subjects']),c['capabilities'])
            elapsed=(time.perf_counter()-st)*1000
            return hashlib.sha256(json.dumps(asdict(p),sort_keys=True,ensure_ascii=False).encode()).hexdigest(),elapsed
        rss=proc.memory_info().rss;cpu=time.process_time();st=time.perf_counter()
        serial=[call(g) for g in qs]
        with ThreadPoolExecutor(max_workers=4) as pool:parallel=list(pool.map(call,qs))
        assert [x[0] for x in serial]==[x[0] for x in parallel]
        outputs[label]=[x[0] for x in serial]
        results[label]={'serial':stats([x[1] for x in serial]),'four_workers':stats([x[1] for x in parallel]),
            'CPU_ms':(time.process_time()-cpu)*1000,'wall_ms':(time.perf_counter()-st)*1000,
            'rss_before':rss,'rss_after':proc.memory_info().rss,'errors':0,'calls':300,'serial_concurrent_identical':150}
    assert outputs['before']==outputs['after'],'Optimization changed the matched complete plan output'
    profile=cProfile.Profile();profile.enable()
    for g in qs:
        c=caps[g['scope_type']];new.validate(new.parse_query(g['query_text'],c['subjects']),c['capabilities'])
    profile.disable();profile.dump_stats(str(R/'search_comp3_final_profile_after.pstats'))
    buf=io.StringIO();pstats.Stats(profile,stream=buf).sort_stats('cumulative').print_stats(30)
    (R/'search_comp3_final_profile_after.txt').write_text(buf.getvalue(),encoding='utf8')
    report={'population':'Exposed C5ER150; same order, facets, capabilities and calls; one serial and one four-worker pass per revision',
        'results':results,'matched_before_after_complete_plan_hashes':150,
        'before_sources':{str(p):sha(p) for p in baseline.glob('*.py')},
        'after_sources':{str(p):sha(p) for p in Path('scratch/search_compositional_recovery_v3').glob('*.py')},
        'optimization':'Confirmed repeated vocabulary enumeration and redundant edit-distance scan; immutable complete-scope length/token buckets preserve candidates, thresholds, margins and edit fallback.',
        'limits':'Single shared host, sequential before then after, no statistical CI, warm process. Profiling timing not mixed with uninstrumented latency. No agreed staging SLO; no operational PASS.',
        'Mongo_calls':0,'network_calls':0,'model_calls':0,'full_search_latency':'N/A','real_vector_relevance':'N/A','operational_SLO':'UNAGREED; future staging proposal parser p95 <=100ms, four-worker p95 <=300ms, full search to be agreed on hardware/data/index generation.'}
    with (R/'search_comp3_final_performance.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(results))
if __name__=='__main__':main()
