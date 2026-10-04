"""Durable lexical overlay consuming the existing catalogue work-ID outbox.

The 5M SQLite base is never written. A small WAL database stores one current
override per work ID, plus normalized values for those overrides.
"""
from datetime import datetime, timezone
from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import sqlite3
import threading
import time

from search.lexical_build import lexical_rows, writer_lock
from search.lexical_store import (LexicalSearchStore, FIRST_VALUE_SQL,
                                  NEXT_VALUE_SQL, EDIT_VALUE_SQL,
                                  MAX_WORK_IDS_PER_VALUE,MAX_QUERY_LENGTH)

LOG=logging.getLogger(__name__)
DELTA_SCHEMA_VERSION=1
DELTA_FILENAME='lexical_delta.sqlite3'
MAX_EVENT_WORK_IDS=1000
# Per-request overlay limits. A SQL LIMIT after an anti-join does not bound
# rejected base rows, so base rows are fetched before override checks.
MAX_BASE_IDS_INSPECTED=2048
MAX_BASE_IDS_PER_VALUE=128
MAX_DELTA_IDS_INSPECTED=2048
MAX_OVERRIDE_CHECKS=2048
MAX_OVERLAY_SQL_CALLS=3072
MAX_LEXICAL_VALUE_LENGTH=4096
MAX_WORK_ID_LENGTH=256


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def delta_connection(path,readonly=False):
    path=Path(path)
    if readonly:
        db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,
                           timeout=2,check_same_thread=False)
        db.execute('PRAGMA query_only=ON')
    else:
        db=sqlite3.connect(path,timeout=5,check_same_thread=False)
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA synchronous=FULL')
    db.execute('PRAGMA busy_timeout=2000')
    db.execute('PRAGMA cache_size=-2048')
    db.execute('PRAGMA mmap_size=0')
    return db


def metadata(db):
    return dict(db.execute('SELECT key,value FROM metadata'))


def validate_delta(db,base_manifest):
    if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':
        raise ValueError('Lexical delta integrity error')
    tables={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'metadata','overrides','lexical_values'}<=tables:
        raise ValueError('Incomplete lexical delta schema')
    indexes={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    if not {'idx_delta_exact','idx_delta_work'}<=indexes:
        raise ValueError('Incomplete lexical delta indexes')
    if [r[2] for r in db.execute('PRAGMA index_info(idx_delta_exact)')]!=[
        'value_type','normalized_value','work_id']:
        raise ValueError('Invalid lexical delta exact index')
    if [r[2] for r in db.execute('PRAGMA index_info(idx_delta_work)')]!=['work_id']:
        raise ValueError('Invalid lexical delta work index')
    m=metadata(db)
    if (m.get('schema_version')!=str(DELTA_SCHEMA_VERSION)
            or m.get('base_version')!=base_manifest['sidecar_version']
            or m.get('source_db_name')!=base_manifest['source_db_name']):
        raise ValueError('Lexical delta/base mismatch')
    for key in ('lexical_generation','source_event_checkpoint','retry_attempts'):
        if key not in m or not m[key].isdigit(): raise ValueError('Invalid lexical delta metadata')
    return m


def initialize_delta(root,base_manifest,base_checkpoint,queue):
    root=Path(root)
    path=root/DELTA_FILENAME
    if not isinstance(base_checkpoint,int) or base_checkpoint<0:
        raise ValueError('Base event checkpoint must be explicit')
    with writer_lock(root):
        if path.exists():
            db=delta_connection(path,readonly=True)
            try: return validate_delta(db,base_manifest)
            finally: db.close()
        if queue.latest()<base_checkpoint:
            raise ValueError('Base checkpoint is ahead of durable event queue')
        if base_checkpoint:
            with sqlite3.connect(Path(queue.path).resolve().as_uri()+'?mode=ro',uri=True) as events:
                event=events.execute('SELECT created FROM events WHERE seq=?',(base_checkpoint,)).fetchone()
            if event is None or event[0]>=datetime.fromisoformat(base_manifest['created_at']).timestamp():
                raise ValueError('Base checkpoint is not older than published snapshot')
        stage=root/(DELTA_FILENAME+'.building')
        if stage.exists(): raise ValueError('Unfinished lexical delta initialization requires review')
        db=sqlite3.connect(stage)
        try:
            db.executescript('''
                PRAGMA journal_mode=DELETE;
                PRAGMA synchronous=FULL;
                CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE overrides(
                    work_id TEXT PRIMARY KEY CHECK(length(work_id)>0),
                    deleted INTEGER NOT NULL CHECK(deleted IN (0,1)),
                    last_event_seq INTEGER NOT NULL);
                CREATE TABLE lexical_values(
                    value_type TEXT NOT NULL CHECK(value_type IN ('TITLE','AUTHOR')),
                    normalized_value TEXT NOT NULL CHECK(length(normalized_value)>0),
                    work_id TEXT NOT NULL CHECK(length(work_id)>0));
                CREATE UNIQUE INDEX idx_delta_exact
                    ON lexical_values(value_type,normalized_value,work_id);
                CREATE INDEX idx_delta_work ON lexical_values(work_id);
            ''')
            initial={'schema_version':DELTA_SCHEMA_VERSION,
                     'base_version':base_manifest['sidecar_version'],
                     'source_db_name':base_manifest['source_db_name'],
                     'lexical_generation':base_manifest['lexical_generation'],
                     'source_event_checkpoint':base_checkpoint,
                     'base_event_checkpoint':base_checkpoint,
                     'last_sync':'','retry_attempts':0,'retry_at':0,'last_error':''}
            with db:
                db.executemany('INSERT INTO metadata(key,value) VALUES(?,?)',
                               [(k,str(v)) for k,v in initial.items()])
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                raise ValueError('New lexical delta failed integrity check')
        finally:
            db.close()
        with stage.open('r+b') as file: os.fsync(file.fileno())
        os.replace(stage,path)
        return initial


class LexicalDeltaWriter:
    def __init__(self,root,collection,queue,*,expected_source_db='luminar_library'):
        self.root=Path(root)
        self.collection=collection
        self.queue=queue
        self.base=LexicalSearchStore(self.root,expected_source_db=expected_source_db)
        if not self.base.health()['lexical_available']:
            raise ValueError('Lexical base unavailable')
        self.path=self.root/DELTA_FILENAME
        db=delta_connection(self.path,readonly=True)
        try: validate_delta(db,self.base.manifest)
        finally: db.close()
        self.local_lock=threading.Lock()
        self.stop_event=threading.Event()
        self.thread=None
        self.error=None

    def status(self):
        db=delta_connection(self.path,readonly=True)
        try:
            m=validate_delta(db,self.base.manifest)
            overrides=db.execute('SELECT count(*) FROM overrides').fetchone()[0]
            tombstones=db.execute('SELECT count(*) FROM overrides WHERE deleted=1').fetchone()[0]
            rows=db.execute('SELECT count(*) FROM lexical_values').fetchone()[0]
        finally: db.close()
        checkpoint=int(m['source_event_checkpoint'])
        return {'lexical_generation':int(m['lexical_generation']),
                'source_event_checkpoint':checkpoint,'pending':self.queue.latest()>checkpoint,
                'retry_attempts':int(m['retry_attempts']),
                'retry_at':float(m.get('retry_at','0')),
                'last_sync':m['last_sync'] or None,
                'last_error':m['last_error'] or self.error,
                'override_count':overrides,'tombstone_count':tombstones,
                'delta_row_count':rows,
                'delta_size_bytes':sum(p.stat().st_size for p in (
                    self.path,Path(str(self.path)+'-wal')) if p.exists())}

    def _effective_rows(self,db,work_id):
        override=db.execute('SELECT deleted FROM overrides WHERE work_id=?',(work_id,)).fetchone()
        if override is None:
            return self.base.db.execute('SELECT value_type,normalized_value,work_id '
                                        'FROM lexical_values WHERE work_id=? '
                                        'ORDER BY value_type,normalized_value',(work_id,)).fetchall()
        return db.execute('SELECT value_type,normalized_value,work_id FROM lexical_values '
                          'WHERE work_id=? ORDER BY value_type,normalized_value',(work_id,)).fetchall()

    def process_once(self,failpoint=None):
        if not self.local_lock.acquire(blocking=False): return False
        try:
            with writer_lock(self.root):
                try:
                    db=delta_connection(self.path)
                except (OSError,sqlite3.Error) as error:
                    # The durable source event remains pending. There is no
                    # writable delta in which to persist retry metadata yet.
                    self.error=type(error).__name__
                    LOG.error('lexical_delta_unavailable error_type=%s',self.error)
                    return False
                try:
                    committed=False
                    m=validate_delta(db,self.base.manifest)
                    if float(m.get('retry_at','0'))>time.time(): return False
                    checkpoint=int(m['source_event_checkpoint'])
                    events=self.queue.pending(checkpoint)
                    if not events: return False
                    ids=list(dict.fromkeys(wid for _,_,payload in events for wid in json.loads(payload)))
                    if len(ids)>MAX_EVENT_WORK_IDS:
                        raise ValueError('Lexical event batch exceeds work-ID cap; maintenance required')
                    documents={wid:self.collection.find_one({'work_id':wid},
                                         {'_id':0,'work_id':1,'title':1,'authors':1}) for wid in ids}
                    for wid,doc in documents.items():
                        if doc is not None and doc.get('work_id')!=wid:
                            raise ValueError('Mongo work-ID mismatch')
                    sequence=events[-1][0]
                    changed=0
                    if failpoint: failpoint('before_transaction')
                    db.execute('BEGIN IMMEDIATE')
                    for wid,doc in documents.items():
                        new=[] if doc is None else lexical_rows(doc)
                        if self._effective_rows(db,wid)==new: continue
                        db.execute('DELETE FROM lexical_values WHERE work_id=?',(wid,))
                        if failpoint: failpoint('after_delete')
                        if new:
                            db.executemany('INSERT INTO lexical_values(value_type,normalized_value,work_id) '
                                           'VALUES(?,?,?)',new)
                        if failpoint: failpoint('after_insert')
                        db.execute('INSERT INTO overrides(work_id,deleted,last_event_seq) VALUES(?,?,?) '
                                   'ON CONFLICT(work_id) DO UPDATE SET deleted=excluded.deleted,'
                                   'last_event_seq=excluded.last_event_seq',(wid,int(doc is None),sequence))
                        changed+=1
                    update={'source_event_checkpoint':sequence,'last_sync':utc_now(),
                            'retry_attempts':0,'retry_at':0,'last_error':''}
                    if changed: update['lexical_generation']=int(m['lexical_generation'])+1
                    if failpoint: failpoint('before_checkpoint_update')
                    db.executemany('UPDATE metadata SET value=? WHERE key=?',
                                   [(str(v),k) for k,v in update.items()])
                    if failpoint: failpoint('after_checkpoint_update')
                    if failpoint: failpoint('before_commit')
                    db.commit()
                    committed=True
                    self.error=None
                    if failpoint: failpoint('after_commit')
                    return True
                except Exception as error:
                    db.rollback()
                    if committed:
                        # A post-commit hook may fail; the durable state already
                        # contains the event and must not acquire a false retry.
                        self.error=None
                        return True
                    self.error=type(error).__name__
                    try:
                        db.execute('BEGIN IMMEDIATE')
                        m=metadata(db)
                        attempts=int(m.get('retry_attempts','0'))+1
                        db.execute("UPDATE metadata SET value=? WHERE key='retry_attempts'",
                                   (str(attempts),))
                        db.execute("UPDATE metadata SET value=? WHERE key='retry_at'",
                                   (str(time.time()+min(300,2**min(attempts,8))),))
                        db.execute("UPDATE metadata SET value=? WHERE key='last_error'",
                                   (self.error,))
                        db.commit()
                    except sqlite3.Error:
                        db.rollback()
                    LOG.error('lexical_sync_failed error_type=%s',self.error)
                    return False
                finally: db.close()
        finally: self.local_lock.release()

    def start(self,poll_seconds=2):
        if self.thread is not None: return
        self.stop_event.clear()
        def run():
            while not self.stop_event.is_set():
                try:
                    self.process_once()
                except Exception as error:
                    self.error=type(error).__name__
                    LOG.error('lexical_worker_unavailable error_type=%s',self.error)
                self.stop_event.wait(poll_seconds)
        self.thread=threading.Thread(target=run,name='lexical-sync',daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread is not None: self.thread.join(timeout=5)
        self.base.close()


class LexicalOverlayStore(LexicalSearchStore):
    """Read an immutable base and one transactional delta snapshot together."""
    def __init__(self,path=None,*,event_queue=None,**kwargs):
        super().__init__(path,**kwargs)
        self.event_queue=event_queue
        self.delta_available=False
        self._read_budget=None
        self.last_read_budget={}
        if self.db is None: return
        delta=self.root/DELTA_FILENAME
        try:
            if not delta.is_file(): raise ValueError('Missing lexical delta')
            self.db.execute('ATTACH DATABASE ? AS lexical_delta',
                            (delta.resolve().as_uri()+'?mode=ro',))
            m=dict(self.db.execute('SELECT key,value FROM lexical_delta.metadata'))
            if (m.get('schema_version')!=str(DELTA_SCHEMA_VERSION)
                    or m.get('base_version')!=self.manifest['sidecar_version']
                    or m.get('source_db_name')!=self.manifest['source_db_name']):
                raise ValueError('Lexical delta/base mismatch')
            tables={r[0] for r in self.db.execute(
                "SELECT name FROM lexical_delta.sqlite_master WHERE type='table'")}
            indexes={r[0] for r in self.db.execute(
                "SELECT name FROM lexical_delta.sqlite_master WHERE type='index'")}
            if not {'metadata','overrides','lexical_values'}<=tables or not {
                'idx_delta_exact','idx_delta_work'}<=indexes:
                raise ValueError('Incomplete lexical delta schema')
            if self.db.execute('PRAGMA lexical_delta.quick_check').fetchone()[0]!='ok':
                raise ValueError('Lexical delta integrity error')
            self.delta_available=True
        except (OSError,ValueError,sqlite3.Error) as error:
            self.error=type(error).__name__+': '+str(error)
            self.close()

    def _seek_candidate(self,sql,args):
        base=super()._seek_candidate(sql,args)
        delta=super()._seek_candidate(sql.replace('FROM lexical_values',
                                               'FROM lexical_delta.lexical_values'),args)
        return min((v for v in (base,delta) if v is not None),default=None)

    def _query(self,sql,args):
        budget=self._read_budget
        if budget is not None:
            if budget['sql_calls']>=MAX_OVERLAY_SQL_CALLS:
                budget['exhausted']=True
                return []
            budget['sql_calls']+=1
        return super()._query(sql,args)

    def _bounded_base_ids(self,value_type,normalized_value,limit):
        budget=self._read_budget
        remaining=MAX_BASE_IDS_INSPECTED-budget['base_ids_inspected']
        if remaining<=0:
            budget['exhausted']=True
            return []
        cap=min(limit,MAX_BASE_IDS_PER_VALUE,remaining)
        rows=self._query('SELECT work_id FROM lexical_values '
                         'WHERE value_type=? AND normalized_value=? '
                         'ORDER BY work_id LIMIT ?',
                         (value_type,normalized_value,cap))
        ids=[row[0] for row in rows]
        budget['base_ids_inspected']+=len(ids)
        return ids

    def _unoverridden(self,ids):
        if not ids: return []
        budget=self._read_budget
        remaining=MAX_OVERRIDE_CHECKS-budget['override_checks']
        if remaining<=0:
            budget['exhausted']=True
            return []
        if len(ids)>remaining: budget['exhausted']=True
        ids=ids[:remaining]
        budget['override_checks']+=len(ids)
        placeholders=','.join('?' for _ in ids)
        suppressed={row[0] for row in self._query(
            'SELECT work_id FROM lexical_delta.overrides WHERE work_id IN ('+
            placeholders+')',ids)}
        return [wid for wid in ids if wid not in suppressed]

    def _candidate_eligible(self,value_type,normalized_value):
        budget=self._read_budget
        if len(normalized_value)>MAX_LEXICAL_VALUE_LENGTH:
            budget['exhausted']=True
            return False
        if budget['delta_ids_inspected']>=MAX_DELTA_IDS_INSPECTED:
            budget['exhausted']=True
            return False
        delta=self._query('SELECT work_id FROM lexical_delta.lexical_values '
                          'WHERE value_type=? AND normalized_value=? LIMIT 1',
                          (value_type,normalized_value))
        budget['delta_ids_inspected']+=len(delta)
        if delta:
            return True
        ids=self._bounded_base_ids(value_type,normalized_value,MAX_BASE_IDS_PER_VALUE)
        survivors=self._unoverridden(ids)
        if not survivors and len(ids)==min(MAX_BASE_IDS_PER_VALUE,
                                           MAX_BASE_IDS_INSPECTED-(budget['base_ids_inspected']-len(ids))):
            # A surviving ID might lie beyond this bounded window. Abstain
            # rather than scoring from a potentially incomplete value set.
            budget['exhausted']=True
        return bool(survivors)

    def _has_leading_token(self,value_type,query):
        from search.lexical_store import prefix_upper
        prefix=query+' '
        upper=prefix_upper(prefix)
        value=self._seek_candidate(FIRST_VALUE_SQL,(value_type,prefix,upper))
        for _ in range(100):
            if value is None: return False
            if self._candidate_eligible(value_type,value): return True
            value=self._seek_candidate(NEXT_VALUE_SQL,(value_type,value,upper))
        return True  # On cap exhaustion, avoid an unsafe correction.

    def work_ids_for_value(self,value_type,normalized_value,limit=MAX_WORK_IDS_PER_VALUE):
        with self._read_transaction():
            if (value_type not in ('TITLE','AUTHOR') or
                    not isinstance(normalized_value,str) or not normalized_value or
                    len(normalized_value)>MAX_LEXICAL_VALUE_LENGTH):
                return []
            limit=min(MAX_WORK_IDS_PER_VALUE,self._limit(limit))
            if not limit: return []
            budget=self._read_budget
            remaining_delta=MAX_DELTA_IDS_INSPECTED-budget['delta_ids_inspected']
            if remaining_delta<=0:
                budget['exhausted']=True
                return []
            delta=[r[0] for r in self._query('SELECT work_id FROM lexical_delta.lexical_values '
                                              'WHERE value_type=? AND normalized_value=? '
                                              'ORDER BY work_id LIMIT ?',
                                              (value_type,normalized_value,min(limit,remaining_delta)))]
            budget['delta_ids_inspected']+=len(delta)
            remaining=limit-len(delta)
            base=[] if remaining<=0 else self._unoverridden(
                self._bounded_base_ids(value_type,normalized_value,
                                       MAX_BASE_IDS_PER_VALUE))[:remaining]
            return list(dict.fromkeys(delta+base))[:limit]

    def candidates(self,value_type,query,limit=50):
        if not isinstance(query,str) or len(query)>MAX_QUERY_LENGTH:
            return []
        with self._read_transaction():
            values=super().candidates(value_type,query,limit)
            return [] if self._read_budget['exhausted'] else values

    def exact(self,value_type,query,limit=MAX_WORK_IDS_PER_VALUE):
        from search.typo_assistance import normalize_structured
        if not isinstance(query,str) or len(query)>MAX_QUERY_LENGTH:
            return []
        with self._read_transaction():
            value=normalize_structured(query)
            return [(value,wid) for wid in self.work_ids_for_value(value_type,value,limit)]

    def work_id(self,work_id,limit=100):
        if not isinstance(work_id,str) or len(work_id)>MAX_WORK_ID_LENGTH:
            return []
        with self._read_transaction():
            found=self._query('SELECT 1 FROM lexical_delta.overrides WHERE work_id=? LIMIT 1',(work_id,))
            self._read_budget['override_checks']+=len(found)
            if found:
                rows=self._query('SELECT value_type,normalized_value FROM lexical_delta.lexical_values '
                                 'WHERE work_id=? LIMIT ?',(work_id,self._limit(limit)))
                self._read_budget['delta_ids_inspected']+=len(rows)
                return rows
            rows=super().work_id(work_id,limit)
            self._read_budget['base_ids_inspected']+=len(rows)
            return rows

    @contextmanager
    def _read_transaction(self):
        with self.lock:
            outer=self._read_budget is None
            if outer:
                self._read_budget={'sql_calls':0,'base_ids_inspected':0,
                                   'delta_ids_inspected':0,'override_checks':0,
                                   'exhausted':False}
            started=self.db is not None and not self.db.in_transaction
            if started: self.db.execute('BEGIN')
            try: yield
            finally:
                if started and self.db is not None: self.db.rollback()
                if outer:
                    self.last_read_budget=dict(self._read_budget)
                    self._read_budget=None

    def fuzzy(self,value_type,query,limit=50):
        with self._read_transaction():
            invalid=not isinstance(query,str) or len(query)>MAX_QUERY_LENGTH
            result=super().fuzzy(value_type,'' if invalid else query,limit)
            if invalid:
                result.update(reason='invalid_or_long_query',match=None,work_ids=[])
            if self._read_budget['exhausted']:
                result.update(match=None,work_ids=[],reason='overlay_budget_exhausted')
            elif result['match'] is not None and not result['work_ids']:
                result.update(match=None,reason='overlay_no_effective_work_ids')
            result['overlay_budget']=dict(self._read_budget)
            return result

    def health(self):
        status=super().health()
        status['lexical_available']=status['lexical_available'] and self.delta_available
        status['lexical_base_version']=self.manifest.get('sidecar_version')
        status['lexical_base_generation']=self.manifest.get('lexical_generation')
        status['lexical_base_size']=self.manifest.get('file_size')
        status['lexical_worker_configured']=os.getenv('LUMINAR_LEXICAL_SYNC_ENABLED','false').lower()=='true'
        status['lexical_worker_enabled']=False
        status['lexical_ranking_enabled']=False
        if self.delta_available:
            try:
                m=dict(self._query('SELECT key,value FROM lexical_delta.metadata',()))
                status.update(lexical_generation=int(m['lexical_generation']),
                              lexical_delta_generation=int(m['lexical_generation']),
                              lexical_source_event_checkpoint=int(m['source_event_checkpoint']),
                              lexical_last_sync=m['last_sync'] or None,
                              lexical_retry_attempts=int(m['retry_attempts']),
                              lexical_retry_at=float(m.get('retry_at','0')),
                              lexical_last_error=m['last_error'] or self.error,
                              lexical_delta_version=int(m['schema_version']),
                              lexical_delta_size=sum(p.stat().st_size for p in (
                                  self.root/DELTA_FILENAME,
                                  self.root/(DELTA_FILENAME+'-wal')) if p.exists()))
                if self.event_queue is not None:
                    status['lexical_pending']=self.event_queue.latest()>int(m['source_event_checkpoint'])
                    if status['lexical_pending']: status['lexical_available']=False
            except (ValueError,KeyError,OSError,sqlite3.Error) as error:
                status['lexical_available']=False
                status['lexical_last_error']=type(error).__name__
        return status
