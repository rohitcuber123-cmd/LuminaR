"""Parser-only timings over exposed probes; never reads acceptance queries."""
from pathlib import Path
from datetime import datetime,timezone
import time,json,statistics,hashlib,tracemalloc,os
import psutil
from scratch.search_v2c_c5e.candidate_search.query_plan import parse_query
from scratch.search_v2c_c5e.candidate_search.query_confidence import validate
R=Path('reports');P='search_v2c_c5e_'
QUERIES=['include History','online onyl','prefer beginer explanations','rated above','require at least 300 pages',
         'titled "A Shrot Guide"; exclude every record containing the text "online"; rated above 3',
         'include subject "History" and one more subject that I have not named',
         'not category "History" or "Physics"; I lost the parentheses around the negative part']
def stats(values):
    s=sorted(values);return {'count':len(s),'p50_ms':statistics.median(s),'p95_ms':s[max(0,__import__('math').ceil(.95*len(s))-1)],'max_ms':max(s)}
def main():
    caps=json.loads((R/'search_v2c_c5a_capability_matrix.json').read_text(encoding='utf8'))['scopes']
    process=psutil.Process();before=process.memory_info().rss;cpu=time.process_time();tracemalloc.start()
    values=[];errors=[];total=time.perf_counter()
    for _ in range(10):
        for scope,contract in caps.items():
            for q in QUERIES:
                start=time.perf_counter()
                try:validate(parse_query(q,contract['subjects']),contract['capabilities'])
                except Exception as exc:errors.append(type(exc).__name__)
                values.append((time.perf_counter()-start)*1000)
    wall=(time.perf_counter()-total)*1000;current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    rejects=[]
    for q,mode in [('x'*501,'SMART'),('History','INVALID')]:
        try:parse_query(q,[],mode)
        except ValueError as exc:rejects.append({'input_class':'TOO_LONG' if len(q)>500 else 'INVALID_MODE','error_type':'ValueError','message':str(exc)})
    result={'at_utc':datetime.now(timezone.utc).isoformat(),'population':'B exposed focused probes; not acceptance','parser_calls':len(values),'warm_repeated_timings':stats(values),
        'wall_ms':wall,'process_cpu_ms':(time.process_time()-cpu)*1000,'rss_before_bytes':before,'rss_after_bytes':process.memory_info().rss,
        'python_traced_peak_bytes':peak,'instrumentation':'psutil + tracemalloc; overhead included, in-process warmed imports','errors':errors,'invalid_input_rejections':rejects,
        'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('scratch/search_v2c_c5e/candidate_search').glob('*.py')},
        'full_search_latency_inferred_from_parser':False,'resident_endpoint_calls':0,'model_calls':0,'database_calls':0,'confidence_is_probability':False}
    with (R/(P+'parser_performance.json')).open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
    print(json.dumps({'parser_calls':len(values),'errors':len(errors),'timing':stats(values)}))
if __name__=='__main__':main()
