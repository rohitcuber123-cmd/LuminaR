"""Matched offline parser timings; these are not full-search timings or an SLO."""
import sys,json,time,math,statistics,contextvars
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import psutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scratch.search_architecture_v10 import parser
from scratch.search_architecture_v10.capabilities import mask
from scratch.search_architecture_v9 import parser as previous

active=contextvars.ContextVar('timing',default=None)

def stats(values):
    a=sorted(values)
    return dict(samples=len(a),p50_ms=statistics.median(a),p95_ms=a[math.ceil(.95*len(a))-1],max_ms=max(a),
                evidence='MEASURED_EXPOSED_DEVELOPMENT_OFFLINE_COMPONENT',population='matched reviewed V10 query contexts; no real provider')


def main():
    rows=[json.loads(x) for x in Path('reports/search_arch10_realistic_reviewed_r1.jsonl').read_text(encoding='utf8').splitlines()]
    facets=['Biology','Mystery','Romance','Physics','Fiction'];originals=[];observations=[]
    def instrument(obj,name,key):
        old=getattr(obj,name);originals.append((obj,name,old))
        def wrapped(*a,**k):
            start=time.perf_counter()
            try:return old(*a,**k)
            finally:
                target=active.get()
                if target is not None:target[key]=target.get(key,0)+(time.perf_counter()-start)*1000
        setattr(obj,name,wrapped)
    instrument(parser.legacy,'parse_query','legacy_interpretation')
    instrument(parser,'interpret','compositional_interpretation')
    instrument(parser,'overlay','semantic_interpretation')
    instrument(parser,'audit','source_obligation_validation')
    instrument(parser.legacy,'validate','proof_and_native_validation')
    instrument(parser,'project','native_planning')
    start=time.perf_counter();proc=psutil.Process();ram_start=psutil.virtual_memory().available;rss_start=proc.memory_info().rss
    try:
        for repeat in range(3):
            for row in rows:
                measured={};token=active.set(measured);t=time.perf_counter()
                parser.validate(parser.parse_query(row['query_text'],facets,row['mode']),mask(row['scope']))
                measured['combined_parser']=(time.perf_counter()-t)*1000;active.reset(token)
                measured['interpretation']=sum(measured.get(x,0) for x in ('legacy_interpretation','compositional_interpretation','semantic_interpretation'))
                observations.append(dict(scope=row['scope'],complexity=row['complexity'],length=row['length_bucket'],mode=row['mode'],timing=measured))
        exact=[]
        for q in ['Quiet River','9781234567890','available online']*10:
            t=time.perf_counter();parser.parse_query(q,mode='EXACT');exact.append((time.perf_counter()-t)*1000)
    finally:
        for obj,name,old in reversed(originals):setattr(obj,name,old)
    # Same exposed contexts, same hardware and no model/IO, measured separately.
    baseline=[]
    for row in rows:
        t=time.perf_counter();previous.validate(previous.parse_query(row['query_text'],facets,row['mode']),mask(row['scope']));baseline.append((time.perf_counter()-t)*1000)
    def worker(row):
        t=time.perf_counter();parser.validate(parser.parse_query(row['query_text'],facets,row['mode']),mask(row['scope']));return (time.perf_counter()-t)*1000
    four_start=time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as pool:four=list(pool.map(worker,rows))
    four_wall=time.perf_counter()-four_start
    report=dict(environment='SAME_HOST_READ_ONLY_OFFLINE_NO_EMBEDDING_OR_DB',
        stages={key:stats([r['timing'].get(key,0) for r in observations]) for key in sorted(observations[0]['timing'])},
        by_complexity={k:stats([r['timing']['combined_parser'] for r in observations if r['complexity']==k]) for k in ['ordinary','structured','complex']},
        by_scope={k:stats([r['timing']['combined_parser'] for r in observations if r['scope']==k]) for k in sorted({r['scope'] for r in observations})},
        by_decision={},exact=stats(exact),matched_v9=stats(baseline),four_worker=dict(**stats(four),concurrency=4,wall_seconds=four_wall,throughput_contexts_per_second=len(four)/four_wall),
        resource=dict(rss_start_bytes=rss_start,rss_end_bytes=proc.memory_info().rss,available_ram_start=ram_start,available_ram_end=psutil.virtual_memory().available),
        parser_timeouts=0,parser_errors=0,semantic_provider_latency='UNMEASURED',native_filter_hydration_timing='SEE_READ_ONLY_NATIVE_FIXTURE_REPORTS',
        full_search_latency='UNMEASURED_NO_REAL_SERVICE_INDEX_QUALIFICATION',production_slo='NOT_SET_OR_INFERRED',wall_seconds=time.perf_counter()-start)
    # Decision timings are measured on the same population, from labels only;
    # do not infer runtime provider or auth latency from these parser timings.
    for decision in sorted({r['expected_decision'] for r in rows}):
        keys={r['case_id'] for r in rows if r['expected_decision']==decision}
        idx=[i for i,r in enumerate(rows) if r['case_id'] in keys]
        report['by_decision'][decision]=stats([observations[rep*len(rows)+i]['timing']['combined_parser'] for rep in range(3) for i in idx])
    tag=sys.argv[1] if len(sys.argv)>1 else ''
    assert not tag or tag.isalnum()
    with Path('reports/search_arch10_performance'+('_'+tag if tag else '')+'.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:report[k] for k in ['stages','four_worker','resource']}))

if __name__=='__main__':main()
