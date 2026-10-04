"""Isolated lexical correctness/recovery tests. No live catalogue/index writes."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from search.lexical_build import build_snapshot, LexicalSnapshotWriter, lexical_rows, writer_lock
from search.lexical_store import (LexicalSearchStore, digest_file, RANGE_SQL, prefix_upper,
                                 search_with_lexical_diagnostics)

BOOKS = [
    {'work_id':'A','title':'Frankenstein','authors':['Mary Shelley','Mary Shelley']},
    {'work_id':'B','title':'A Tale of Two Cities','authors':'Charles Dickens'},
    {'work_id':'C','title':'Animal Farm','authors':'George Orwell'},
    *[{'work_id':'P'+str(i),'title':x,'authors':'Test Author'}
      for i,x in enumerate(['AI','it','C++','C#','1984','python','java','foundation','Catch-22','I, Robot','Café'])],
]


class Collection:
    def __init__(self,docs=BOOKS): self.rows={d['work_id']:dict(d) for d in docs}
    def find_one(self,query,projection): return self.rows.get(query['work_id'])


@pytest.fixture
def root(tmp_path):
    build_snapshot(BOOKS,tmp_path,source_db='test')
    return tmp_path


def opened(root):
    s=LexicalSearchStore(root)
    assert s.health()['lexical_available'],s.health()
    return s


def test_controlled_full_build_requires_complete_exact_count(tmp_path):
    with pytest.raises(ValueError,match='exact expected source count'):
        build_snapshot(BOOKS,tmp_path,source_db='test',limit=2,controlled_full=True)
    with pytest.raises(ValueError,match='source count changed'):
        build_snapshot(BOOKS[:1],tmp_path,source_db='test',limit=2,
                       controlled_full=True,expected_source_count=2)
    with pytest.raises(ValueError,match='exceeded'):
        build_snapshot(BOOKS[:3],tmp_path,source_db='test',limit=2,
                       controlled_full=True,expected_source_count=2)
    assert not (tmp_path/'active_lexical.json').exists()


def manifest_path(root):
    v=json.loads((root/'active_lexical.json').read_text())['version']
    return root/('lexical_'+v+'.json')


@pytest.mark.parametrize('query,typ,target',[
    ('frankenstien','TITLE','frankenstein'),('mary shelly','AUTHOR','mary shelley'),
    ('charls dickens','AUTHOR','charles dickens'),('george orwel','AUTHOR','george orwell')])
def test_typos(root,query,typ,target):
    s=opened(root)
    r=s.fuzzy(typ,query)
    assert r['match']['value']==target,r
    assert r['work_ids']
    s.close()


@pytest.mark.parametrize('query',['AI','it','C++','C#','1984','python','java','foundation','Catch-22','I, Robot','Ｃ＋＋','Cafe\u0301'])
def test_exact_protection_unicode_punctuation(root,query):
    s=opened(root)
    r=s.fuzzy('TITLE',query)
    assert r['exact'] and r['match'] is None
    assert r['reason']=='exact_match_precedence'
    s.close()


def test_short_no_match_and_ambiguous(tmp_path):
    build_snapshot([{'work_id':'A','title':'abcdefgg'},{'work_id':'B','title':'abcdefgh'}],tmp_path,source_db='test')
    s=opened(tmp_path)
    assert s.fuzzy('TITLE','AI')['reason']=='short_query'
    assert s.fuzzy('TITLE','abcdxyz')['match'] is None
    assert s.fuzzy('TITLE','abcdefgj')['reason']=='ambiguous'
    s.close()


def test_limits_plans_and_duplicate_source_authors(root):
    s=opened(root)
    assert s.exact('AUTHOR','Mary Shelley')==[('mary shelley','A')]
    assert len(s.candidates('TITLE','frankenstien',1))<=1
    assert len(s.exact('AUTHOR','Test Author',999999))<=100
    sql='EXPLAIN QUERY PLAN '+RANGE_SQL
    plan=str(s.db.execute(sql,('TITLE','frank',prefix_upper('frank'),50)).fetchall())
    assert 'SEARCH' in plan and 'normalized_value>?' in plan and 'SCAN' not in plan
    assert s.work_id('A')==[('AUTHOR','mary shelley'),('TITLE','frankenstein')] or sorted(s.work_id('A'))==[('AUTHOR','mary shelley'),('TITLE','frankenstein')]
    s.close()


@pytest.mark.parametrize('kind',['missing','directory','empty','garbage'])
def test_open_never_creates_or_changes_files(tmp_path,kind):
    root=tmp_path/'sidecar'
    if kind=='directory': root.mkdir()
    elif kind in ('empty','garbage'):
        root.write_bytes(b'' if kind=='empty' else b'garbage')
    before={str(p):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    s=LexicalSearchStore(root)
    assert not s.health()['lexical_available']
    assert s.exact('TITLE','Frankenstein')==[]
    after={str(p):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert before==after
    if kind=='missing': assert not root.exists()


@pytest.mark.parametrize('damage',['missing_db','zero_db','garbage_db','bad_manifest','checksum','unsupported',
                                   'wrong_norm','missing_table','missing_index','wrong_index','wrong_metadata'])
def test_damage_fails_closed(root,damage):
    mp=manifest_path(root)
    m=json.loads(mp.read_text())
    dbp=mp.with_suffix('.sqlite')
    if damage=='missing_db': dbp.unlink()
    elif damage=='zero_db': dbp.write_bytes(b'')
    elif damage=='garbage_db': dbp.write_bytes(b'x'*m['file_size'])
    elif damage=='bad_manifest': mp.write_text('[]')
    elif damage=='checksum': m['sha256']='0'*64
    elif damage=='unsupported': m['schema_version']=999
    elif damage=='wrong_norm': m['normalization_version']='unknown'
    elif damage in ('missing_table','missing_index','wrong_index','wrong_metadata'):
        db=sqlite3.connect(dbp)
        if damage=='missing_table': db.execute('DROP TABLE lexical_values')
        elif damage=='missing_index': db.execute('DROP INDEX idx_lexical_work')
        elif damage=='wrong_index':
            db.execute('DROP INDEX idx_lexical_work')
            db.execute('CREATE INDEX idx_lexical_work ON lexical_values(normalized_value)')
        else: db.execute("UPDATE metadata SET value='wrong' WHERE key='sidecar_version'")
        db.commit(); db.close()
        m['sha256']=digest_file(dbp); m['file_size']=dbp.stat().st_size
    if damage!='bad_manifest': mp.write_text(json.dumps(m))
    s=LexicalSearchStore(root)
    assert not s.health()['lexical_available']
    assert s.fuzzy('TITLE','frankenstien')['reason']=='unavailable'


def test_unreadable_and_open_error(root):
    with patch('pathlib.Path.read_text',side_effect=PermissionError('simulated access denied')):
        assert not LexicalSearchStore(root).health()['lexical_available']
    with patch('search.lexical_store.sqlite3.connect',side_effect=sqlite3.OperationalError('open failed')):
        assert not LexicalSearchStore(root).health()['lexical_available']


def test_stale_and_wrong_source(root):
    s=LexicalSearchStore(root,required_generation=999)
    assert s.health()['lexical_pending'] and not s.health()['lexical_available']
    assert not LexicalSearchStore(root,expected_source_db='wrong').health()['lexical_available']


def test_repeated_updates_and_deletes(root):
    c=Collection()
    writer=LexicalSnapshotWriter(root,c)
    before=json.loads((root/'active_lexical.json').read_text())
    writer.sync_work_id('A')
    assert json.loads((root/'active_lexical.json').read_text())==before
    c.rows['A']['title']='Changed'
    writer.sync_work_id('A')
    s=opened(root)
    assert s.exact('TITLE','Changed')==[('changed','A')]
    assert s.exact('TITLE','Frankenstein')==[]
    s.close()
    writer.delete_work_id('A')
    version=(root/'active_lexical.json').read_bytes()
    writer.delete_work_id('A'); writer.delete_work_id('missing')
    assert (root/'active_lexical.json').read_bytes()==version
    s=opened(root); assert s.work_id('A')==[]; s.close()


@pytest.mark.parametrize('stage',['after_delete','during_insert','before_commit','after_commit','after_validation','before_pointer'])
def test_interrupted_mutation_keeps_old_snapshot(root,stage):
    c=Collection(); c.rows['A']['title']='Changed'
    before=(root/'active_lexical.json').read_bytes()
    def fail(point):
        if point==stage: raise RuntimeError('injected')
    with pytest.raises(RuntimeError): LexicalSnapshotWriter(root,c).sync_work_id('A',fail)
    assert (root/'active_lexical.json').read_bytes()==before
    s=opened(root); assert s.exact('TITLE','Frankenstein'); assert not s.exact('TITLE','Changed'); s.close()
    LexicalSnapshotWriter(root,c).sync_work_id('A')
    s=opened(root); assert s.exact('TITLE','Changed'); s.close()


def test_failure_after_publication_keeps_complete_new_state(root):
    c=Collection(); c.rows['A']['title']='Changed'
    def fail(stage):
        if stage=='after_pointer': raise RuntimeError('injected')
    with pytest.raises(RuntimeError): LexicalSnapshotWriter(root,c).sync_work_id('A',fail)
    s=opened(root); assert s.exact('TITLE','Changed'); assert not s.exact('TITLE','Frankenstein'); s.close()


def test_process_crash_before_pointer(root):
    code="""
import os,sys
from search.lexical_build import build_snapshot
def fail(stage):
    if stage=='before_pointer': os._exit(17)
build_snapshot([{'work_id':'Z','title':'Unpublished'}],sys.argv[1],source_db='test',failpoint=fail)
"""
    before=(root/'active_lexical.json').read_bytes()
    r=subprocess.run([sys.executable,'-c',code,str(root)])
    assert r.returncode==17
    assert (root/'active_lexical.json').read_bytes()==before
    s=opened(root); assert s.exact('TITLE','Frankenstein'); s.close()


def test_concurrent_readers_pin_old_and_open_new(root):
    old=opened(root)
    start=threading.Event()
    def read_many():
        start.wait()
        for _ in range(30):
            s=opened(root)
            old_rows=s.exact('TITLE','Frankenstein')
            new_rows=s.exact('TITLE','New Edition')
            assert bool(old_rows)!=bool(new_rows)
            s.close()
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(read_many) for _ in range(4)]
        start.set()
        build_snapshot([{'work_id':'A','title':'New Edition'}],root,source_db='test')
        for f in futures: f.result()
    assert old.exact('TITLE','Frankenstein')
    assert not old.exact('TITLE','New Edition')
    old.close()
    fresh=opened(root); assert fresh.exact('TITLE','New Edition'); fresh.close()


def test_process_writer_exclusion(root):
    code="""
import sys
from search.lexical_build import writer_lock
try:
    with writer_lock(sys.argv[1]): pass
except RuntimeError: sys.exit(19)
"""
    with writer_lock(root):
        r=subprocess.run([sys.executable,'-c',code,str(root)])
        assert r.returncode==19


def test_bad_mapping_rejected(tmp_path):
    with pytest.raises(ValueError): build_snapshot([{'work_id':None,'title':'Wrong'}],tmp_path,source_db='test')
    assert not (tmp_path/'active_lexical.json').exists()
    with pytest.raises(ValueError): build_snapshot(BOOKS,tmp_path,source_db='test',limit=5000000)


def test_adapter_fallback_preserves_results(root):
    class Engine:
        def search(self,q,**kw): return {'results':[{'work_id':'A','title':'Current Mongo title'}]}
    class Broken:
        def health(self): raise sqlite3.OperationalError('unavailable')
    result=search_with_lexical_diagnostics(Engine(),Broken(),'query')
    assert result['results']==Engine().search('query')['results']
    assert not result['lexical_diagnostics']['health']['lexical_available']


def test_reader_no_checksum_per_query(root,monkeypatch):
    s=opened(root)
    def forbidden(*a,**kw): raise AssertionError('Per-request checksum')
    monkeypatch.setattr('search.lexical_store.digest_file',forbidden)
    for _ in range(3): assert s.exact('TITLE','Frankenstein')
    with pytest.raises(sqlite3.OperationalError): s.db.execute('DELETE FROM lexical_values')
    s.close()


def test_published_reader_does_not_create_journal_or_sidefiles(root):
    before={p.name:p.read_bytes() for p in root.iterdir() if p.is_file()}
    s=opened(root)
    s.fuzzy('TITLE','frankenstien')
    s.close()
    assert before=={p.name:p.read_bytes() for p in root.iterdir() if p.is_file()}


def test_benchmark_explicit_column_mapping():
    from scripts.measure_lexical_schemas import rows_for
    doc={'work_id':'OL1W','title':'Display Title','authors':['Jane Example']}
    with_display=list(rows_for(doc,True))
    no_display=list(rows_for(doc,False))
    assert with_display==[('TITLE','display title','OL1W','Display Title'),('AUTHOR','jane example','OL1W','Jane Example')]
    assert no_display==[r[:3] for r in with_display]
    with pytest.raises(AssertionError): list(rows_for({'work_id':None,'title':'bad'},False))

@pytest.mark.parametrize('stage',['after_delete','during_insert','before_commit','after_commit','before_pointer','after_pointer'])
def test_process_crash_at_mutation_boundaries(root,stage):
    code="""
import os,sys
from search.lexical_build import LexicalSnapshotWriter
class Collection:
    def find_one(self,q,p): return {'work_id':'A','title':'After crash','authors':'Author'}
def fail(stage):
    if stage==sys.argv[2]: os._exit(23)
LexicalSnapshotWriter(sys.argv[1],Collection()).sync_work_id('A',fail)
"""
    r=subprocess.run([sys.executable,'-c',code,str(root),stage])
    assert r.returncode==23
    s=opened(root)
    if stage=='after_pointer':
        assert s.exact('TITLE','After crash') and not s.exact('TITLE','Frankenstein')
    else:
        assert s.exact('TITLE','Frankenstein') and not s.exact('TITLE','After crash')
    s.close()
    # The crashed process's OS lock is released. Retrying completes cleanly.
    c=Collection(); c.rows['A']['title']='After crash'
    LexicalSnapshotWriter(root,c).sync_work_id('A')
    s=opened(root); assert s.exact('TITLE','After crash'); s.close()


def test_sql_token_wildcards_are_literal(root):
    s=opened(root)
    assert s._query(RANGE_SQL,('TITLE','fran%',prefix_upper('fran%'),50))==[]
    assert s._query(RANGE_SQL,('TITLE','fran_',prefix_upper('fran_'),50))==[]
    s.close()


def test_missing_mongo_sync_is_delete(root):
    c=Collection()
    del c.rows['A']
    w=LexicalSnapshotWriter(root,c)
    w.sync_work_id('A')
    s=opened(root); assert s.work_id('A')==[]; s.close()
    prior=(root/'active_lexical.json').read_bytes()
    w.sync_work_id('A')
    assert (root/'active_lexical.json').read_bytes()==prior


def test_single_word_title_token_blocks_unnecessary_suggestion(tmp_path):
    build_snapshot([{'work_id':'A','title':'Foundations'},{'work_id':'B','title':'Foundation of science'}],tmp_path,source_db='test')
    s=opened(tmp_path)
    assert s.fuzzy('TITLE','foundation')['reason']=='exact_title_token_evidence'
    s.close()


def test_prefix_progress_is_bounded_even_for_common_prefix(tmp_path):
    build_snapshot(({'work_id':str(i),'title':'Common title '+str(i)} for i in range(2000)),tmp_path,source_db='test')
    s=opened(tmp_path)
    instructions=[0]
    def progress():
        instructions[0]+=1
        return 0
    s.db.set_progress_handler(progress,1)
    r=s.candidates('TITLE','common typo',limit=20)
    s.db.set_progress_handler(None,0)
    assert len(r)==20
    assert instructions[0]<5000
    result=s.fuzzy('TITLE','common typo',limit=20)
    assert result['reason']=='candidate_cap_reached'
    assert result['candidate_generation_seeks']<=512
    s.close()


def test_distinct_value_seek_skips_duplicate_editions(tmp_path):
    from search.lexical_store import FIRST_VALUE_SQL,NEXT_VALUE_SQL
    build_snapshot(({'work_id':str(i),'title':'Frankenstein'} for i in range(2000)),
                   tmp_path,source_db='test')
    s=opened(tmp_path)
    plan=str(s.db.execute('EXPLAIN QUERY PLAN '+NEXT_VALUE_SQL,
                          ('TITLE','frankenstein','frankensu')).fetchall())
    assert 'COVERING INDEX idx_lexical_exact' in plan and 'SCAN' not in plan
    first=s.db.execute(FIRST_VALUE_SQL,('TITLE','franken','franko')).fetchone()
    assert first==('frankenstein',)
    instructions=[0]
    s.db.set_progress_handler(lambda: instructions.__setitem__(0,instructions[0]+1) or 0,1)
    next_value=s.db.execute(NEXT_VALUE_SQL,('TITLE','frankenstein','franko')).fetchone()
    s.db.set_progress_handler(None,0)
    assert next_value is None
    assert instructions[0]<100
    assert s.candidates('TITLE','frankenstien')==['frankenstein']
    s.close()

def test_edited_prefix_recovers_missing_letter_with_crowded_name_range(tmp_path):
    docs=[{'work_id':str(i),'title':'Book','authors':'Veronica A '+str(i)} for i in range(150)]
    docs.append({'work_id':'target','title':'Target','authors':'Veronica Collins'})
    build_snapshot(docs,tmp_path,source_db='test')
    s=opened(tmp_path)
    calls=[]
    original=s._query
    def counted(sql,args):
        calls.append((sql,args))
        return original(sql,args)
    s._query=counted
    r=s.fuzzy('AUTHOR','Vernica Collins')
    assert r['match']['value']=='veronica collins'
    assert r['work_ids']==['target']
    assert len(calls)<=259
    assert all('LIKE' not in sql and 'LOWER' not in sql for sql,_ in calls)
    s.close()
