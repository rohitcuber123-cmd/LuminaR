"""Parser latency/resources and concurrency over exposed development queries."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import json,time,statistics,math,hashlib
import psutil
from scratch.search_smart_engineering.ownership_recovery.parser import parse_query,validate
R=Path('reports');P='search_v2c_smarteng_'
def statistics_ms(v):
    s=sorted(v);return {'count':len(s),'p50_ms':statistics.median(s),'p95_ms':s[math.ceil(.95*len(s))-1],'max_ms':max(s)}
def main():
    gold=[json.loads(s) for s in (R/'search_v2c_c5er_reviewed_population.jsonl').read_text(encoding='utf8').splitlines()]
    caps=json.loads((R/'search_v2c_c5a_capability_matrix.json').read_text(encoding='utf8'))['scopes']
    proc=psutil.Process();before=proc.memory_info().rss;cpu=time.process_time();start=time.perf_counter()
    def call(g):
        start=time.perf_counter();p=validate(parse_query(g['query_text'],caps[g['scope_type']]['subjects']),caps[g['scope_type']]['capabilities'])
        value=json.dumps(asdict(p),sort_keys=True,ensure_ascii=False)
        return hashlib.sha256(value.encode()).hexdigest(),(time.perf_counter()-start)*1000
    serial=[call(g) for g in gold]
    with ThreadPoolExecutor(max_workers=4) as pool:parallel=list(pool.map(call,gold))
    assert [r[0] for r in serial]==[r[0] for r in parallel]
    result={'population':'Exposed C5ER150, no fresh acceptance inputs read','serial':statistics_ms([r[1] for r in serial]),'concurrent_four_workers':statistics_ms([r[1] for r in parallel]),
        'deterministic_serial_parallel_matches':150,'wall_ms':(time.perf_counter()-start)*1000,'process_CPU_ms':(time.process_time()-cpu)*1000,
        'rss_before_bytes':before,'rss_after_bytes':proc.memory_info().rss,'Mongo_calls':0,'network_calls':0,'Qwen_or_model_calls':0,
        'comparison_limits':'Prior10.19/20.63ms from a different C5E90 population; current serial150 is not an identical matched latency cohort. Thread timings include GIL/scheduling overhead.',
        'full_production_search_latency':'N/A','vector_lookup_latency':'N/A','real_Mongo_query_latency':'N/A','real_semantic_retrieval_latency':'N/A',
        'resident_health':'Last known STALE/degraded; baseline_verified=False; no resident repoll'}
    with (R/(P+'performance.json')).open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
    print(json.dumps({'serial':result['serial'],'concurrent_matches':150,'Mongo_calls':0}))
if __name__=='__main__':main()
