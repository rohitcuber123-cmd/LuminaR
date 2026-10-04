"""Bounded lexical build; --full explicitly permits one checked catalogue pass."""
import argparse
from datetime import datetime, timezone
import itertools
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from search.lexical_build import (MAX_BUILD_BOOKS, MAX_CONTROLLED_FULL_BOOKS,
                                  build_snapshot, preflight)
from search.lexical_store import default_path


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--limit',type=int,default=10000)
    p.add_argument('--output',default=str(default_path()))
    p.add_argument('--check',action='store_true')
    p.add_argument('--full',action='store_true',help='Explicit controlled full-catalogue build; resource checks remain mandatory')
    p.add_argument('--source-jsonl')
    a=p.parse_args()
    if a.check and (a.source_jsonl or a.full): p.error('--check reads current Mongo statistics only')
    if a.full and (a.source_jsonl or a.limit!=10000): p.error('--full uses current Mongo and determines its own count')
    if not a.check and not a.full and not 1<=a.limit<=MAX_BUILD_BOOKS:
        p.error('Default phase gate: --limit must be 1..100000')
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env')
    source_db=os.getenv('MONGO_DB_NAME','luminar_library')
    if a.source_jsonl:
        with open(a.source_jsonl,encoding='utf-8') as f:
            result=build_snapshot((json.loads(line) for line in itertools.islice(f,a.limit)),
                                  a.output,source_db=source_db,limit=a.limit)
        print(json.dumps(result,indent=2))
        return
    from pymongo import MongoClient
    with MongoClient(os.getenv('MONGO_URI','mongodb://localhost:27017')) as client:
        books=client[source_db].books
        estimated=books.estimated_document_count()
        check=preflight(a.output,estimated,source_db)
        if a.check:
            print(json.dumps(check,indent=2))
            return
        count=books.count_documents({}) if a.full else a.limit
        if a.full and (count<1 or count>MAX_CONTROLLED_FULL_BOOKS):
            raise RuntimeError('Full source count exceeds the controlled build limit')
        checked=preflight(a.output,count,source_db)
        if not checked['resource_check_pass']: raise RuntimeError('Resource preflight failed')
        if a.full and checked['source_db_name']!='luminar_library':
            raise RuntimeError('Controlled full build is restricted to luminar_library')
        if a.full:
            print(json.dumps({'controlled_full_preflight':checked,'exact_document_count':count,
                              'started_at':utc_now()}),flush=True)
        cursor=books.find({}, {'_id':0,'work_id':1,'title':1,'authors':1}).sort('_id',1).batch_size(1000)
        if not a.full: cursor=cursor.limit(a.limit)
        if not a.full:
            result=build_snapshot(cursor,a.output,source_db=source_db,limit=a.limit)
            print(json.dumps(result,indent=2))
            return

        import psutil
        output=Path(a.output)
        process=psutil.Process()
        ram=psutil.virtual_memory()
        metrics={'started_at':utc_now(),'preflight':checked,
                 'rss_start_bytes':process.memory_info().rss,
                 'available_ram_start_bytes':ram.available,
                 'free_disk_start_bytes':shutil.disk_usage(output.parent).free}
        metrics['rss_peak_bytes']=metrics['rss_start_bytes']
        metrics['available_ram_min_bytes']=ram.available
        metrics['free_disk_min_bytes']=metrics['free_disk_start_bytes']
        metrics['temporary_db_peak_bytes']=0
        metrics['journal_temp_peak_bytes']=0
        stop=threading.Event()
        unsafe=threading.Event()
        extraction_seconds=[0.0]
        def monitor():
            while not stop.is_set():
                try:
                    free=shutil.disk_usage(output.parent).free
                    available=psutil.virtual_memory().available
                    metrics['free_disk_min_bytes']=min(metrics['free_disk_min_bytes'],free)
                    metrics['available_ram_min_bytes']=min(metrics['available_ram_min_bytes'],available)
                    metrics['rss_peak_bytes']=max(metrics['rss_peak_bytes'],process.memory_info().rss)
                    if output.exists():
                        for path in output.glob('building_*'):
                            try:
                                size=path.stat().st_size
                            except FileNotFoundError:
                                continue  # SQLite removes journals between discovery and stat.
                            if path.suffix=='.sqlite':
                                metrics['temporary_db_peak_bytes']=max(metrics['temporary_db_peak_bytes'],size)
                            else:
                                metrics['journal_temp_peak_bytes']=max(metrics['journal_temp_peak_bytes'],size)
                    if free<checked['minimum_free_bytes'] or available<checked['build_ram_reserve_bytes']:
                        metrics['unsafe_reason']='resource threshold'
                        unsafe.set()
                except (OSError,psutil.Error) as error:
                    metrics['unsafe_reason']=type(error).__name__
                    unsafe.set()
                stop.wait(.1)
        def safe(force):
            if unsafe.is_set(): return False
            if force:
                free=shutil.disk_usage(output.parent).free
                available=psutil.virtual_memory().available
                if free<checked['minimum_free_bytes'] or available<checked['build_ram_reserve_bytes']:
                    metrics['unsafe_reason']='resource threshold'
                    unsafe.set()
            return not unsafe.is_set()
        def timed_cursor():
            it=iter(cursor)
            while True:
                start=time.perf_counter()
                try: doc=next(it)
                except StopIteration:
                    extraction_seconds[0]+=time.perf_counter()-start
                    return
                extraction_seconds[0]+=time.perf_counter()-start
                yield doc
        def before_publication(stage):
            if stage=='before_pointer':
                latest=books.count_documents({})
                metrics['source_document_count_before_publication']=latest
                if latest!=count:
                    raise ValueError('Mongo source count changed before publication')
        thread=threading.Thread(target=monitor,name='lexical-build-resource-monitor',daemon=True)
        thread.start()
        try:
            result=build_snapshot(timed_cursor(),output,source_db=source_db,limit=count,
                                  controlled_full=True,expected_source_count=count,
                                  metrics=metrics,safety_check=safe,failpoint=before_publication)
            ending_count=books.count_documents({})
            metrics['source_document_count_after_build']=ending_count
            metrics['source_count_stable']=ending_count==count
            metrics['result']='published' if ending_count==count else 'published_source_count_changed'
        except Exception as error:
            metrics['result']='failed'
            metrics['error_type']=type(error).__name__
            metrics['error_message']=str(error)
            raise
        finally:
            stop.set(); thread.join()
            cursor.close()
            metrics['mongo_extraction_seconds']=extraction_seconds[0]
            metrics['rss_end_bytes']=process.memory_info().rss
            metrics['available_ram_end_bytes']=psutil.virtual_memory().available
            metrics['free_disk_end_bytes']=shutil.disk_usage(output.parent).free
            metrics['ended_at']=utc_now()
            output.mkdir(parents=True,exist_ok=True)
            (output/'full_build_metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
        print(json.dumps({'manifest':result,'metrics':metrics},indent=2))

if __name__=='__main__': main()
