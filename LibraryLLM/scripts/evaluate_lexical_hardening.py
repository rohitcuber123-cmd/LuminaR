"""Repeatable offline hardening/resource diagnostics, <=100k source books."""
import argparse
import itertools
import json
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import psutil
from search.lexical_build import build_snapshot
from search.lexical_store import LexicalSearchStore,RANGE_SQL,prefix_upper
from scripts.measure_lexical_schemas import stats


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--directory',required=True)
    p.add_argument('--build-count',type=int)
    p.add_argument('--lookup-only',action='store_true')
    a=p.parse_args()
    root=Path(a.directory)
    if a.build_count:
        process=psutil.Process()
        start_rss=process.memory_info().rss
        peak=[start_rss]
        stop=threading.Event()
        def monitor():
            while not stop.is_set():
                peak[0]=max(peak[0],process.memory_info().rss)
                stop.wait(.005)
        thread=threading.Thread(target=monitor); thread.start()
        t=time.perf_counter()
        try:
            with (root/'source.jsonl').open(encoding='utf-8') as f:
                m=build_snapshot((json.loads(line) for line in itertools.islice(f,a.build_count)),
                    root/('hardened_'+str(a.build_count)),source_db='luminar_library',limit=a.build_count)
        finally:
            stop.set(); thread.join()
        print(json.dumps({'books':a.build_count,'rss_start':start_rss,'rss_peak':peak[0],
            'rss_end':process.memory_info().rss,'seconds':time.perf_counter()-t,'manifest':m}))
        return
    resources=[]
    if a.lookup_only:
        resources=json.loads((root/'final-hardening.json').read_text(encoding='utf-8'))['build_resources']
    else:
        for count in (10000,50000,100000):
            result=subprocess.run([sys.executable,__file__,'--directory',str(root),'--build-count',str(count)],
                capture_output=True,text=True,check=True)
            resources.append(json.loads(result.stdout))
    process=psutil.Process(); before=process.memory_info().rss; t=time.perf_counter()
    store=LexicalSearchStore(root/'hardened_100000')
    startup_ms=(time.perf_counter()-t)*1000
    assert store.db is not None,store.health()
    rss_open=process.memory_info().rss
    queries=[('TITLE','frankenstien'),('AUTHOR','mary shelly'),('AUTHOR','charls dickens'),('AUTHOR','george orwel')]
    queries += [('TITLE',q) for q in ['AI','it','C++','C#','1984','python','java','foundation']]
    results=[]
    for typ,q in queries:
        evidence=store.fuzzy(typ,q)
        timings=[]
        for _ in range(105):
            t=time.perf_counter(); store.fuzzy(typ,q)
            if _>=5: timings.append((time.perf_counter()-t)*1000)
        steps=[0]
        def progress():
            steps[0]+=1
            return 0
        store.db.set_progress_handler(progress,1)
        store.candidates(typ,q)
        store.db.set_progress_handler(None,0)
        results.append({'query':q,'type':typ,'candidate_count':len(evidence['candidates']),
            'exact_count':len(evidence['exact']),'match':evidence['match'],'reason':evidence['reason'],
            'margin':evidence['margin'],'top_scores':evidence['scores'][:3],
            'candidate_sqlite_vm_steps':steps[0],'timing_ms':stats(timings)})
    # Diagnostic adapter overhead with a constant semantic stub isolates lexical
    # overhead; it is not a claim about end-to-end live API latency.
    baseline=[]; enabled=[]
    from search.lexical_store import search_with_lexical_diagnostics
    class SemanticStub:
        def search(self,q): return {'results':[]}
    engine=SemanticStub()
    for _ in range(100):
        t=time.perf_counter(); engine.search('frankenstien'); baseline.append((time.perf_counter()-t)*1000)
        t=time.perf_counter(); search_with_lexical_diagnostics(engine,store,'frankenstien'); enabled.append((time.perf_counter()-t)*1000)
    output={'build_resources':resources,'reader_rss_before':before,'reader_rss_open':rss_open,
            'reader_rss_after_queries':process.memory_info().rss,'startup_validation_ms':startup_ms,
            'queries':results,'adapter_only_ms':{'stub':stats(baseline),'stub_plus_lexical':stats(enabled)},
            'health':store.health()}
    store.close()
    (root/'final-hardening.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(json.dumps(output,indent=2))


if __name__=='__main__': main()
