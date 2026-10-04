"""Small durable-overlay tests; no live Mongo or semantic index writes."""
import json
import sqlite3
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import pytest

from search.lexical_build import build_snapshot
from search.lexical_store import FIRST_VALUE_SQL,NEXT_VALUE_SQL
from search.lexical_delta import (initialize_delta,LexicalDeltaWriter,
                                  LexicalOverlayStore,DELTA_FILENAME,
                                  MAX_BASE_IDS_INSPECTED,MAX_BASE_IDS_PER_VALUE,
                                  MAX_DELTA_IDS_INSPECTED,MAX_OVERRIDE_CHECKS,
                                  MAX_OVERLAY_SQL_CALLS)


class Queue:
    def __init__(self): self.events=[]
    def latest(self): return self.events[-1][0] if self.events else 0
    def pending(self,after): return [event for event in self.events if event[0]>after]
    def add(self,*ids):
        seq=self.latest()+1
        self.events.append((seq,'sync',json.dumps(list(ids))))


class Books:
    def __init__(self,docs):
        self.docs={d['work_id']:dict(d) for d in docs}
        self.fail=False
    def find_one(self,query,projection):
        if self.fail: raise OSError('simulated Mongo outage')
        return self.docs.get(query['work_id'])


def setup(tmp_path):
    docs=[{'work_id':'A','title':'Frankenstein','authors':['Mary Shelley']},
          {'work_id':'B','title':'A Tale of Two Cities','authors':['Charles Dickens']}]
    base=build_snapshot(docs,tmp_path,source_db='luminar_library')
    books=Books(docs); queue=Queue()
    initialize_delta(tmp_path,base,0,queue)
    return books,queue,LexicalDeltaWriter(tmp_path,books,queue)


def test_delta_create_update_delete_and_nonlexical_noop(tmp_path):
    books,queue,writer=setup(tmp_path)
    base_path=next(tmp_path.glob('lexical_*.sqlite'))
    base_before=(base_path.stat().st_size,base_path.stat().st_mtime_ns)
    reader=LexicalOverlayStore(tmp_path)
    assert reader.health()['lexical_available']
    assert reader.exact('TITLE','Frankenstein')==[('frankenstein','A')]
    books.docs['C']={'work_id':'C','title':'New Title','authors':['New Author']}
    queue.add('C')
    assert writer.process_once()
    assert reader.exact('TITLE','New Title')==[('new title','C')]
    assert reader.exact('AUTHOR','New Author')==[('new author','C')]
    generation=writer.status()['lexical_generation']
    books.docs['C']['description']='Changed description only'
    queue.add('C')
    assert writer.process_once()
    assert writer.status()['lexical_generation']==generation
    books.docs['A']['title']='Revised Monster'
    queue.add('A')
    assert writer.process_once()
    assert reader.exact('TITLE','Frankenstein')==[]
    assert reader.exact('TITLE','Revised Monster')==[('revised monster','A')]
    books.docs['A']['authors']=['Revised Author']
    queue.add('A')
    assert writer.process_once()
    assert reader.exact('AUTHOR','Mary Shelley')==[]
    assert reader.exact('AUTHOR','Revised Author')==[('revised author','A')]
    del books.docs['A']
    queue.add('A')
    assert writer.process_once()
    assert reader.work_id('A')==[]
    assert reader.exact('TITLE','Revised Monster')==[]
    assert writer.status()['tombstone_count']==1
    assert writer.status()['source_event_checkpoint']==5
    assert (base_path.stat().st_size,base_path.stat().st_mtime_ns)==base_before
    reader.close();writer.close()


def test_delta_retry_replay_and_restart(tmp_path):
    books,queue,writer=setup(tmp_path)
    books.docs['A']['title']='Changed'
    queue.add('A')
    books.fail=True
    assert not writer.process_once()
    assert writer.status()['source_event_checkpoint']==0
    assert writer.status()['retry_attempts']==1
    books.fail=False
    db=sqlite3.connect(tmp_path/DELTA_FILENAME)
    with db: db.execute("UPDATE metadata SET value='0' WHERE key='retry_at'")
    db.close()
    assert writer.process_once()
    assert writer.status()['source_event_checkpoint']==1
    generation=writer.status()['lexical_generation']
    writer.close()
    replay=LexicalDeltaWriter(tmp_path,books,queue)
    assert not replay.process_once()
    queue.add('A')
    assert replay.process_once()
    assert replay.status()['source_event_checkpoint']==2
    assert replay.status()['lexical_generation']==generation
    reader=LexicalOverlayStore(tmp_path)
    assert reader.exact('TITLE','Changed')==[('changed','A')]
    reader.close();replay.close()


def test_delta_missing_and_corrupt_fail_closed(tmp_path):
    books,queue,writer=setup(tmp_path)
    writer.close()
    path=tmp_path/DELTA_FILENAME
    backup=tmp_path/'delta-backup.sqlite3'
    backup.write_bytes(path.read_bytes())
    path.unlink()
    assert not LexicalOverlayStore(tmp_path).health()['lexical_available']
    path.write_bytes(b'corrupt')
    assert not LexicalOverlayStore(tmp_path).health()['lexical_available']
    path.write_bytes(backup.read_bytes())
    assert LexicalOverlayStore(tmp_path).health()['lexical_available']


def test_concurrent_delta_readers_see_complete_states(tmp_path):
    books,queue,writer=setup(tmp_path)
    reader=LexicalOverlayStore(tmp_path)
    start=threading.Event()
    def read_many():
        start.wait()
        for _ in range(40):
            with reader._read_transaction():
                old=reader.exact('TITLE','Frankenstein')
                new=reader.exact('TITLE','Changed')
                assert not (old and new)
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures=[pool.submit(read_many) for _ in range(5)]
        books.docs['A']['title']='Changed';queue.add('A')
        start.set()
        writer.process_once()
        for future in futures: future.result()
    assert reader.exact('TITLE','Changed')==[('changed','A')]
    reader.close();writer.close()


def test_delta_crash_rolls_back_checkpoint_and_rows(tmp_path):
    books,queue,writer=setup(tmp_path)
    writer.close()
    code='''
import json,os,sys
from search.lexical_delta import LexicalDeltaWriter
class Q:
 def pending(self,after): return [(1,'sync',json.dumps(['A']))] if after<1 else []
 def latest(self): return 1
class B:
 def find_one(self,q,p): return {'work_id':'A','title':'Changed','authors':['Mary Shelley']}
w=LexicalDeltaWriter(sys.argv[1],B(),Q())
w.process_once(failpoint=lambda stage: os._exit(37) if stage=='after_insert' else None)
'''
    result=subprocess.run([sys.executable,'-c',code,str(tmp_path)])
    assert result.returncode==37
    reader=LexicalOverlayStore(tmp_path)
    assert reader.exact('TITLE','Frankenstein')==[('frankenstein','A')]
    assert reader.exact('TITLE','Changed')==[]
    reader.close()
    books.docs['A']['title']='Changed';queue.add('A')
    retry=LexicalDeltaWriter(tmp_path,books,queue)
    assert retry.process_once()
    assert retry.status()['source_event_checkpoint']==1
    retry.close()


def test_delta_latest_mongo_wins_over_old_event_payload(tmp_path):
    books,queue,writer=setup(tmp_path)
    books.docs['A']['title']='Latest title'
    queue.add('A')
    queue.add('A')
    assert writer.process_once()
    assert writer.status()['source_event_checkpoint']==2
    assert writer.status()['override_count']==1
    reader=LexicalOverlayStore(tmp_path,event_queue=queue)
    assert reader.exact('TITLE','Latest title')==[('latest title','A')]
    assert reader.exact('TITLE','Frankenstein')==[]
    assert not reader.health()['lexical_pending']
    queue.add('A')
    assert reader.health()['lexical_pending']
    assert not reader.health()['lexical_available']
    reader.close();writer.close()


@pytest.mark.parametrize('total',[2000,10000,50000])
def test_duplicate_heavy_overlay_has_hard_inspection_budget(tmp_path,total):
    docs=({'work_id':f'W{i:06d}','title':'Popular Title','authors':['Popular Author']}
          for i in range(total))
    manifest=build_snapshot(docs,tmp_path,source_db='luminar_library',limit=total)
    initialize_delta(tmp_path,manifest,0,Queue())
    delta=sqlite3.connect(tmp_path/DELTA_FILENAME)
    vm_samples=[]
    try:
        for fraction in (0,.5,.9,.99,1):
            suppressed=int(total*fraction)
            with delta:
                delta.execute('DELETE FROM overrides')
                delta.executemany('INSERT INTO overrides(work_id,deleted,last_event_seq) '
                                  'VALUES(?,1,1)',
                                  ((f'W{i:06d}',) for i in range(suppressed)))
            reader=LexicalOverlayStore(tmp_path)
            assert reader.health()['lexical_available']
            vm=[0]
            reader.db.set_progress_handler(lambda: vm.__setitem__(0,vm[0]+100) or 0,100)
            ids=reader.work_ids_for_value('TITLE','popular title')
            expansion_budget=reader.last_read_budget
            with reader._read_transaction():
                eligible=reader._candidate_eligible('TITLE','popular title')
            eligibility_budget=reader.last_read_budget
            result=reader.fuzzy('TITLE','populr title')
            fuzzy_budget=result['overlay_budget']
            reader.db.set_progress_handler(None,0)
            for budget in (expansion_budget,eligibility_budget,fuzzy_budget):
                assert budget['base_ids_inspected']<=MAX_BASE_IDS_INSPECTED
                assert budget['delta_ids_inspected']<=MAX_DELTA_IDS_INSPECTED
                assert budget['override_checks']<=MAX_OVERRIDE_CHECKS
                assert budget['sql_calls']<=MAX_OVERLAY_SQL_CALLS
            assert expansion_budget['base_ids_inspected']<=MAX_BASE_IDS_PER_VALUE
            assert eligibility_budget['base_ids_inspected']<=MAX_BASE_IDS_PER_VALUE
            assert len(ids)<=50
            assert all(int(wid[1:])>=suppressed for wid in ids)
            assert not eligible if fraction==1 else eligible==bool(ids)
            if fraction==1:
                assert result['match'] is None
                assert result['work_ids']==[]
            vm_samples.append(vm[0])
            reader.close()
        # A larger duplicate run must not multiply request VM work.
        assert max(vm_samples)<250000
    finally:
        delta.close()


def test_overlay_query_plans_use_base_delta_and_override_indexes(tmp_path):
    books,queue,writer=setup(tmp_path)
    reader=LexicalOverlayStore(tmp_path)
    try:
        plans=[(FIRST_VALUE_SQL,('TITLE','fr','fs')),
               (NEXT_VALUE_SQL,('TITLE','frankenstein','fs')),
               (FIRST_VALUE_SQL.replace('FROM lexical_values',
                                        'FROM lexical_delta.lexical_values'),
                ('TITLE','fr','fs')),
               (NEXT_VALUE_SQL.replace('FROM lexical_values',
                                       'FROM lexical_delta.lexical_values'),
                ('TITLE','frankenstein','fs')),
               ('SELECT work_id FROM lexical_values WHERE value_type=? '
                'AND normalized_value=? ORDER BY work_id LIMIT ?',('TITLE','frankenstein',128)),
               ('SELECT work_id FROM lexical_delta.lexical_values WHERE value_type=? '
                'AND normalized_value=? ORDER BY work_id LIMIT ?',('TITLE','frankenstein',50)),
               ('SELECT work_id FROM lexical_delta.overrides WHERE work_id IN (?,?)',('A','B'))]
        descriptions=[' '.join(row[3] for row in reader.db.execute(
            'EXPLAIN QUERY PLAN '+sql,args)) for sql,args in plans]
        assert all('idx_lexical_exact' in text and 'COVERING INDEX' in text
                   for text in (descriptions[0],descriptions[1],descriptions[4]))
        assert all('idx_delta_exact' in text and 'COVERING INDEX' in text
                   for text in (descriptions[2],descriptions[3],descriptions[5]))
        assert 'sqlite_autoindex_overrides_1' in descriptions[6]
        assert all('SCAN ' not in description and 'TEMP B-TREE' not in description
                   for description in descriptions)
    finally:
        reader.close();writer.close()


@pytest.mark.parametrize('stage',[
    'before_transaction','after_delete','after_insert',
    'before_checkpoint_update','after_checkpoint_update',
    'before_commit','after_commit'])
def test_delta_process_crash_at_transaction_boundaries(tmp_path,stage):
    books,queue,writer=setup(tmp_path)
    writer.close()
    code='''
import json,os,sys
from search.lexical_delta import LexicalDeltaWriter
class Q:
 def pending(self,after): return [(1,'sync',json.dumps(['A']))] if after<1 else []
 def latest(self): return 1
class B:
 def find_one(self,q,p): return {'work_id':'A','title':'Changed','authors':['Mary Shelley']}
w=LexicalDeltaWriter(sys.argv[1],B(),Q())
w.process_once(failpoint=lambda stage: os._exit(37) if stage==sys.argv[2] else None)
'''
    result=subprocess.run([sys.executable,'-c',code,str(tmp_path),stage])
    assert result.returncode==37
    reader=LexicalOverlayStore(tmp_path)
    committed=stage=='after_commit'
    assert reader.exact('TITLE','Changed')==([('changed','A')] if committed else [])
    assert reader.exact('TITLE','Frankenstein')==([] if committed else [('frankenstein','A')])
    reader.close()
    books.docs['A']['title']='Changed';queue.add('A')
    replay=LexicalDeltaWriter(tmp_path,books,queue)
    assert replay.status()['source_event_checkpoint']==(1 if committed else 0)
    if committed:
        assert not replay.process_once()
    else:
        assert replay.process_once()
    assert replay.status()['source_event_checkpoint']==1
    replay.close()


def test_delta_repeated_create_update_delete_and_recreate(tmp_path):
    books,queue,writer=setup(tmp_path)
    reader=LexicalOverlayStore(tmp_path)
    try:
        books.docs['C']={'work_id':'C','title':'First','authors':['Author One']}
        expected=[('First','Author One'),('Second','Author Two'),(None,None),
                  ('Third','Author Three')]
        for title,author in expected:
            if title is None: books.docs.pop('C')
            else: books.docs['C']={'work_id':'C','title':title,'authors':[author]}
            queue.add('C');assert writer.process_once()
            generation=writer.status()['lexical_generation']
            queue.add('C');assert writer.process_once()
            assert writer.status()['lexical_generation']==generation
            assert reader.work_id('C')==([] if title is None else
                   [('AUTHOR',author.casefold()),('TITLE',title.casefold())])
        assert writer.status()['override_count']==1
        assert writer.status()['tombstone_count']==0
    finally:
        reader.close();writer.close()


def test_empty_overlay_typo_and_ambiguity_regression(tmp_path):
    docs=[{'work_id':'F','title':'Frankenstein','authors':['Mary Shelley']},
          {'work_id':'M','title':'Another Book','authors':['Mary Sheley']},
          {'work_id':'C','title':'A Tale of Two Cities','authors':['Charles Dickens']},
          {'work_id':'G','title':'1984','authors':['George Orwell']}]
    manifest=build_snapshot(docs,tmp_path,source_db='luminar_library')
    initialize_delta(tmp_path,manifest,0,Queue())
    reader=LexicalOverlayStore(tmp_path)
    try:
        for typ,query,expected in (
            ('TITLE','frankenstien','frankenstein'),
            ('AUTHOR','charls dickens','charles dickens'),
            ('AUTHOR','george orwel','george orwell')):
            result=reader.fuzzy(typ,query)
            assert result['match']['value']==expected
            assert result['work_ids']
            assert not result['overlay_budget']['exhausted']
        ambiguous=reader.fuzzy('AUTHOR','mary shelly')
        assert ambiguous['match'] is None
        assert ambiguous['reason']=='ambiguous'
    finally:
        reader.close()


def test_overlay_rejects_oversized_inputs_before_lookups(tmp_path):
    books,queue,writer=setup(tmp_path)
    reader=LexicalOverlayStore(tmp_path)
    try:
        oversized='a'*100000
        assert reader.exact('TITLE',oversized)==[]
        assert reader.candidates('TITLE',oversized)==[]
        assert reader.work_ids_for_value('TITLE',oversized)==[]
        assert reader.work_id(oversized)==[]
        result=reader.fuzzy('TITLE',oversized)
        assert result['reason']=='invalid_or_long_query'
        assert result['match'] is None
        assert result['overlay_budget']['sql_calls']==0
    finally:
        reader.close();writer.close()


def test_lexical_generation_classifies_semantic_and_inventory_fields(tmp_path):
    books,queue,writer=setup(tmp_path)
    reader=LexicalOverlayStore(tmp_path)
    try:
        initial=writer.status()
        for field,value in (('description','New description'),
                            ('subjects',['New subject']),
                            ('first_publish_date','2001')):
            books.docs['A'][field]=value
            queue.add('A')  # Core semantic event; lexical contents unchanged.
            assert writer.process_once()
            status=writer.status()
            assert status['lexical_generation']==initial['lexical_generation']
            assert status['source_event_checkpoint']==queue.latest()
            assert status['override_count']==0
        books.docs['A']['available_copies']=0
        # Core does not enqueue inventory-only changes. Even an unexpected
        # replay must be a lexical no-op.
        assert not writer.process_once()
        assert writer.status()['lexical_generation']==initial['lexical_generation']
        assert writer.status()['source_event_checkpoint']==queue.latest()
        books.docs['A']['title']='New title'
        queue.add('A');assert writer.process_once()
        assert writer.status()['lexical_generation']==initial['lexical_generation']+1
        assert reader.exact('TITLE','Frankenstein')==[]
        assert reader.exact('TITLE','New title')==[('new title','A')]
        books.docs['A']['authors']=['New author']
        queue.add('A');assert writer.process_once()
        assert writer.status()['lexical_generation']==initial['lexical_generation']+2
        assert reader.exact('AUTHOR','Mary Shelley')==[]
        assert reader.exact('AUTHOR','New author')==[('new author','A')]
    finally:
        reader.close();writer.close()


def test_delta_unavailable_keeps_event_pending_then_recovers(tmp_path,monkeypatch):
    import search.lexical_delta as delta_module
    books,queue,writer=setup(tmp_path)
    books.docs['A']['title']='Recovered title'
    queue.add('A')
    real_connect=delta_module.delta_connection
    def unavailable(path,readonly=False):
        if not readonly: raise OSError('simulated delta outage')
        return real_connect(path,readonly=readonly)
    monkeypatch.setattr(delta_module,'delta_connection',unavailable)
    try:
        assert not writer.process_once()
        assert writer.error=='OSError'
        assert writer.status()['source_event_checkpoint']==0
        assert writer.status()['pending']
    finally:
        monkeypatch.setattr(delta_module,'delta_connection',real_connect)
    assert writer.process_once()
    assert writer.status()['source_event_checkpoint']==1
    reader=LexicalOverlayStore(tmp_path)
    assert reader.exact('TITLE','Recovered title')==[('recovered title','A')]
    reader.close();writer.close()
