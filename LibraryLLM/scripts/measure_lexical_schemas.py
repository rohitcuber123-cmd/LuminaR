"""Bounded, reproducible schema experiment; never writes Mongo or HNSW."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import statistics
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from search.typo_assistance import normalize_structured
import psutil


def stats(values):
    s = sorted(values)
    return dict(mean=statistics.mean(s), p50=statistics.median(s),
                p95=s[max(0, __import__('math').ceil(len(s)*.95)-1)], max=max(s))


def rows_for(doc, display):
    wid = doc['work_id']
    assert isinstance(wid, str) and wid.strip(), 'Invalid source work_id'
    authors = doc.get('authors') or []
    if isinstance(authors, str):
        authors = [authors]
    values = [('TITLE', doc.get('title')), *[('AUTHOR', a) for a in authors]]
    seen = set()
    for typ, value in values:
        if value is None or value == '':
            continue
        assert isinstance(value, str), 'Invalid lexical value'
        normalized = normalize_structured(value)
        if not normalized or (typ, normalized) in seen:
            continue
        seen.add((typ, normalized))
        # Explicit order: type, normalized value, work ID, optional display.
        yield (typ, normalized, wid, value) if display else (typ, normalized, wid)


def child(source, output, count, display):
    start = time.perf_counter()
    proc = psutil.Process()
    rss = {'start': proc.memory_info().rss, 'peak': 0, 'index_peak': 0}
    phase = ['insert']
    stop = threading.Event()
    def sample():
        while not stop.is_set():
            r = proc.memory_info().rss
            rss['peak'] = max(rss['peak'], r)
            if phase[0] == 'index': rss['index_peak'] = max(rss['index_peak'], r)
            stop.wait(.005)
    thread = threading.Thread(target=sample); thread.start()
    db = sqlite3.connect(output)
    db.executescript('PRAGMA page_size=4096; PRAGMA journal_mode=DELETE; PRAGMA synchronous=FULL; PRAGMA cache_size=-8192; PRAGMA temp_store=FILE;')
    db.execute('CREATE TABLE lexical_values(value_type TEXT NOT NULL, normalized_value TEXT NOT NULL, work_id TEXT NOT NULL'+(', display_value TEXT NOT NULL' if display else '')+')')
    columns = 'value_type,normalized_value,work_id'+(',display_value' if display else '')
    insert = 'INSERT INTO lexical_values('+columns+') VALUES('+','.join('?' for _ in columns.split(','))+')'
    commit_seconds = 0
    with open(source, encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= count: break
            db.executemany(insert, rows_for(json.loads(line), display))
            if (i+1) % 2000 == 0:
                t=time.perf_counter(); db.commit(); commit_seconds += time.perf_counter()-t
    db.commit()
    phase[0]='index'; t=time.perf_counter()
    db.executescript('CREATE UNIQUE INDEX idx_lexical_exact ON lexical_values(value_type,normalized_value,work_id); CREATE INDEX idx_lexical_work ON lexical_values(work_id);')
    index_seconds=time.perf_counter()-t
    phase[0]='validate'
    assert db.execute('SELECT COUNT(*) FROM lexical_values WHERE work_id IS NULL OR normalized_value IS NULL').fetchone()[0] == 0
    # Verify EVERY source mapping, not only a spot sample.
    expected = 0
    with open(source, encoding='utf-8') as f:
        for i,line in enumerate(f):
            if i >= count: break
            for row in rows_for(json.loads(line), display):
                got=db.execute('SELECT '+columns+' FROM lexical_values WHERE value_type=? AND normalized_value=? AND work_id=?',row[:3]).fetchone()
                assert got == row, (got,row)
                expected += 1
    assert db.execute('SELECT count(*) FROM lexical_values').fetchone()[0] == expected
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    db.execute('VACUUM'); db.close()
    rss['end']=proc.memory_info().rss
    stop.set(); thread.join()
    elapsed=time.perf_counter()-start
    db=sqlite3.connect(Path(output).resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
    queries={
        'exact_title':('SELECT normalized_value,work_id FROM lexical_values WHERE value_type=? AND normalized_value=? LIMIT 50',('TITLE','frankenstein')),
        'exact_author':('SELECT normalized_value,work_id FROM lexical_values WHERE value_type=? AND normalized_value=? LIMIT 50',('AUTHOR','mary shelley')),
        'prefix':('SELECT normalized_value,work_id FROM lexical_values WHERE value_type=? AND normalized_value>=? AND normalized_value<? ORDER BY normalized_value,work_id LIMIT 50',('TITLE','franken','frankeo')),
        'work_id':('SELECT normalized_value FROM lexical_values WHERE work_id=? LIMIT 50',('OL2000134W',)),
    }
    timings={}; plans={}; vm_steps={}
    for name,(sql,args) in queries.items():
        plans[name]=db.execute('EXPLAIN QUERY PLAN '+sql,args).fetchall()
        values=[]
        for j in range(105):
            t=time.perf_counter(); db.execute(sql,args).fetchall()
            if j>=5: values.append((time.perf_counter()-t)*1000)
        timings[name]=stats(values)
        steps=[0]
        def progress(): steps[0]+=1; return 0
        db.set_progress_handler(progress,1); db.execute(sql,args).fetchall(); db.set_progress_handler(None,0)
        vm_steps[name]=steps[0]
    result={'books':count,'display':display,'file':str(output),'bytes':Path(output).stat().st_size,
            'rows':expected,'null_work_ids':0,'null_normalized':0,'source_mappings_verified':expected,
            'counts':dict(db.execute('SELECT value_type,count(*) FROM lexical_values GROUP BY value_type')),
            'page_count':db.execute('pragma page_count').fetchone()[0], 'timing_ms':timings,'plans':plans,'sqlite_vm_steps':vm_steps,
            'rss':rss,'total_seconds':elapsed,'commit_seconds':commit_seconds,'index_seconds':index_seconds}
    db.close(); print(json.dumps(result))


def main():
    p=argparse.ArgumentParser(); p.add_argument('--directory',required=True); p.add_argument('--child',action='store_true'); p.add_argument('--count',type=int); p.add_argument('--display',action='store_true'); a=p.parse_args()
    directory=Path(a.directory); source=directory/'source.jsonl'
    if a.child:
        child(source,directory/f"flat_{a.count}_{'display' if a.display else 'normalized'}.sqlite",a.count,a.display); return
    directory.mkdir(parents=True,exist_ok=True)
    if source.exists(): raise RuntimeError('Use a fresh experiment directory')
    assert shutil.disk_usage(directory).free > 2*1024**3
    from dotenv import load_dotenv
    from pymongo import MongoClient
    load_dotenv(ROOT/'.env')
    client=MongoClient(os.getenv('MONGO_URI','mongodb://localhost:27017'))
    dbname=os.getenv('MONGO_DB_NAME','luminar_library')
    cursor=client[dbname].books.find({}, {'_id':0,'work_id':1,'title':1,'authors':1}).sort('_id',1).limit(100000).batch_size(1000)
    with source.open('w',encoding='utf-8') as f:
        for doc in cursor: f.write(json.dumps(doc,ensure_ascii=False)+'\n')
    client.close()
    results=[]
    for n in (10000,50000,100000):
        for display in (True,False):
            assert shutil.disk_usage(directory).free > 1024**3
            cmd=[sys.executable,__file__,'--directory',str(directory),'--child','--count',str(n)]
            if display: cmd.append('--display')
            run=subprocess.run(cmd,check=True,capture_output=True,text=True)
            result=json.loads(run.stdout); results.append(result)
            print(json.dumps(result),flush=True)
    (directory/'measurements.json').write_text(json.dumps({'source_db':dbname,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'results':results},indent=2),encoding='utf-8')

if __name__=='__main__': main()
