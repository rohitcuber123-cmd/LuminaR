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
    baseline=Path('scratch/search_proof6_perf_recorded');baseline.mkdir()
    from scratch.search_proof_recovery_v5 import parser as old
    from scratch.search_proof_recovery_v6 import parser as new
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
    # Architecture outputs may differ; this is matched workload timing, not semantic equivalence.
    profile=cProfile.Profile();profile.enable()
    for g in qs:
        c=caps[g['scope_type']];new.validate(new.parse_query(g['query_text'],c['subjects']),c['capabilities'])
    profile.disable();profile.dump_stats(str(R/'search_proof6_recorded_profile_after.pstats'))
    buf=io.StringIO();pstats.Stats(profile,stream=buf).sort_stats('cumulative').print_stats(30)
    (R/'search_proof6_recorded_profile_after.txt').write_text(buf.getvalue(),encoding='utf8')
    report={'population':'Exposed C5ER150; same order, facets, capabilities and calls; one serial and one four-worker pass per revision',
        'results':results,'identical_complete_plans_between_architectures':sum(a==b for a,b in zip(outputs['before'],outputs['after'])),
        'before_sources':{str(p):sha(p) for p in Path('scratch/search_proof_recovery_v5').glob('*.py')},
        'after_sources':{str(p):sha(p) for p in Path('scratch/search_proof_recovery_v6').glob('*.py')},
        'optimization':'Source IR proof compiler vs frozen V3 on identical exposed C5ER150; outputs may differ, no optimization equivalence claim.',
        'limits':'Single shared host, sequential before then after, no statistical CI, warm process. Profiling timing not mixed with uninstrumented latency. No agreed staging SLO; no operational PASS.',
        'Mongo_calls':0,'network_calls':0,'model_calls':0,'full_search_latency':'N/A','real_vector_relevance':'N/A','operational_SLO':'UNAGREED; future staging proposal parser p95 <=100ms, four-worker p95 <=300ms, full search to be agreed on hardware/data/index generation.'}
    with (R/'search_proof6_recorded_performance.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(results))
if __name__=='__main__':main()
