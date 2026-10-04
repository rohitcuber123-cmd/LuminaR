"""Offline lexical builder and isolated copy-on-write mutation methods.

No consumer of semantic events is started. Mutation methods are intended for
test-sized snapshots: copying a 5M file per event is NOT a live-sync design.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time
import uuid

from search.lexical_store import (SCHEMA_VERSION, NORMALIZATION_VERSION, VERSION_RE,
                                  digest_file, validate_snapshot)
from search.typo_assistance import normalize_structured

BUILDER_VERSION = '2.0'
MAX_BUILD_BOOKS = 100000  # Default gate; a full build requires an explicit caller flag.
MAX_CONTROLLED_FULL_BOOKS = 5100000
INSERT = 'INSERT OR IGNORE INTO lexical_values(value_type,normalized_value,work_id) VALUES(?,?,?)'


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def writer_lock(root):
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    file=(root/'writer.lock').open('a+b')
    acquired=False
    try:
        if os.name=='nt':
            import msvcrt
            if file.tell()==0:
                file.write(b'0')
                file.flush()
            file.seek(0)
            try:
                msvcrt.locking(file.fileno(),msvcrt.LK_NBLCK,1)
                acquired=True
            except OSError: pass
        else:
            import fcntl
            try:
                fcntl.flock(file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                acquired=True
            except BlockingIOError: pass
        if not acquired: raise RuntimeError('Lexical writer already active')
        yield
    finally:
        if acquired:
            if os.name=='nt':
                file.seek(0)
                msvcrt.locking(file.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(file.fileno(),fcntl.LOCK_UN)
        file.close()


def sync_directory(root):
    if os.name!='nt':
        fd=os.open(root,os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
    # Windows: closed file fsync + atomic os.replace; directory fsync is not
    # supported here. Sudden power-loss durability depends on NTFS/storage.


def atomic_json(path,value):
    path=Path(path)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temp.open('w',encoding='utf-8') as f:
            json.dump(value,f,ensure_ascii=False,sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(20):
            try:
                os.replace(temp,path)
                break
            except PermissionError:
                if attempt==19: raise
                time.sleep(.01)
        sync_directory(path.parent)
    finally:
        temp.unlink(missing_ok=True)


def lexical_rows(doc):
    wid=doc.get('work_id')
    if not isinstance(wid,str) or not wid.strip(): raise ValueError('Missing/invalid work_id')
    authors=doc.get('authors') or []
    if isinstance(authors,str): authors=[authors]
    if not isinstance(authors,(list,tuple)): raise ValueError('Invalid authors')
    values=[('TITLE',doc.get('title')),*[('AUTHOR',a) for a in authors]]
    rows=set()
    for typ,value in values:
        if value is None or value=='': continue
        if not isinstance(value,str): raise ValueError('Invalid lexical value')
        normalized=normalize_structured(value)
        if normalized: rows.add((typ,normalized,wid))
    return sorted(rows)


def initialize(db):
    db.executescript("""
        PRAGMA page_size=4096;
        PRAGMA journal_mode=DELETE;
        PRAGMA synchronous=FULL;
        PRAGMA cache_size=-8192;
        PRAGMA temp_store=FILE;
        CREATE TABLE lexical_values(
            value_type TEXT NOT NULL CHECK(value_type IN ('TITLE','AUTHOR')),
            normalized_value TEXT NOT NULL CHECK(length(normalized_value)>0),
            work_id TEXT NOT NULL CHECK(length(work_id)>0));
        CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    """)


def create_indexes(db):
    db.executescript("""
        CREATE UNIQUE INDEX idx_lexical_exact ON lexical_values(value_type,normalized_value,work_id);
        CREATE INDEX idx_lexical_work ON lexical_values(work_id);
    """)


def previous(root):
    path=Path(root)/'active_lexical.json'
    if not path.exists(): return None,None
    pointer=json.loads(path.read_text(encoding='utf-8'))
    version=pointer['version']
    if not VERSION_RE.fullmatch(version): raise ValueError('Invalid previous pointer')
    path=Path(root)/('lexical_'+version+'.sqlite')
    manifest=json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
    db=validate_snapshot(path,manifest)
    db.close()
    return path,manifest


def finalize(root,temp,version,generation,book_count,source_db,start,old=None,failpoint=None,last_sync=None,metrics=None):
    def hook(stage):
        if failpoint: failpoint(stage)
    metrics=metrics if metrics is not None else {}
    validation_start=time.perf_counter()
    db=sqlite3.connect(temp)
    meta={'sidecar_version':version,'schema_version':SCHEMA_VERSION,
          'normalization_version':NORMALIZATION_VERSION,'lexical_generation':generation,
          'source_db_name':source_db}
    with db:
        db.executemany('INSERT OR REPLACE INTO metadata(key,value) VALUES(?,?)',[(k,str(v)) for k,v in meta.items()])
    counts=dict(db.execute('SELECT value_type,count(*) FROM lexical_values GROUP BY value_type'))
    represented_books=db.execute('SELECT count(DISTINCT work_id) FROM lexical_values').fetchone()[0]
    # DELETE mode, no outstanding WAL. Read integrity before closing.
    if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
        db.close()
        raise ValueError('Build failed integrity_check')
    db.close()
    with Path(temp).open('r+b') as f: os.fsync(f.fileno())
    metrics['initial_validation_seconds']=time.perf_counter()-validation_start
    checksum_start=time.perf_counter()
    checksum=digest_file(temp)
    metrics['checksum_seconds']=time.perf_counter()-checksum_start
    manifest={**meta,'created_at':now(),'book_count':represented_books,
              'source_book_count':old.get('source_book_count',book_count) if last_sync and old else book_count,
              'title_relationship_count':counts.get('TITLE',0),'author_relationship_count':counts.get('AUTHOR',0),
              'row_count':sum(counts.values()),'file_size':Path(temp).stat().st_size,
              'sha256':checksum,'build_duration_seconds':time.perf_counter()-start,
              'builder_version':BUILDER_VERSION,'last_sync':last_sync,'source_event_checkpoint':None}
    validation_start=time.perf_counter()
    validated=validate_snapshot(temp,manifest)
    validated.close()
    metrics['reader_validation_seconds']=time.perf_counter()-validation_start
    hook('after_validation')
    publication_start=time.perf_counter()
    final=Path(root)/('lexical_'+version+'.sqlite')
    os.replace(temp,final)
    sync_directory(root)
    atomic_json(final.with_suffix('.json'),manifest)
    hook('before_pointer')
    pointer={'version':version,'previous':old['sidecar_version'] if old else None}
    atomic_json(Path(root)/'active_lexical.json',pointer)
    hook('after_pointer')
    metrics['publication_seconds']=time.perf_counter()-publication_start
    metrics['total_build_seconds']=time.perf_counter()-start
    return manifest


def build_snapshot(documents,root,*,source_db,limit=MAX_BUILD_BOOKS,failpoint=None,
                   controlled_full=False,expected_source_count=None,metrics=None,safety_check=None):
    ceiling=MAX_CONTROLLED_FULL_BOOKS if controlled_full else MAX_BUILD_BOOKS
    if not 1<=limit<=ceiling: raise ValueError('Build limit exceeds the selected phase gate')
    if controlled_full and (expected_source_count is None or expected_source_count!=limit):
        raise ValueError('Controlled full build requires an exact expected source count')
    metrics=metrics if metrics is not None else {}
    root=Path(root)
    with writer_lock(root):
        _,old=previous(root)
        version=uuid.uuid4().hex
        temp=root/('building_'+version+'.sqlite')
        start=time.perf_counter()
        db=sqlite3.connect(temp)
        try:
            initialize(db)
            if safety_check:
                db.set_progress_handler(lambda: 0 if safety_check(False) else 1,10000)
            count=0
            skipped=0
            insert_seconds=0.0
            for doc in documents:
                if count>=limit:
                    if controlled_full: raise ValueError('Mongo source exceeded the approved full-build count')
                    break
                rows=lexical_rows(doc)
                # Duplicate lexical relationships fail unique-index creation.
                # Source identity is guaranteed by Mongo's unique work_id index.
                t=time.perf_counter()
                db.executemany('INSERT INTO lexical_values(value_type,normalized_value,work_id) VALUES(?,?,?)',rows)
                insert_seconds+=time.perf_counter()-t
                if not rows: skipped+=1
                count+=1
                if count%2000==0:
                    t=time.perf_counter(); db.commit(); insert_seconds+=time.perf_counter()-t
                    if safety_check and not safety_check(True): raise RuntimeError('Disk or RAM safety threshold violated')
            if controlled_full and count!=expected_source_count:
                raise ValueError(f'Mongo source count changed: expected {expected_source_count}, read {count}')
            t=time.perf_counter()
            db.commit()
            insert_seconds+=time.perf_counter()-t
            metrics.update(source_documents_read=count,skipped_records=skipped,invalid_records=0,
                           duplicate_relationships_rejected=0,sqlite_insertion_seconds=insert_seconds)
            if safety_check and not safety_check(True): raise RuntimeError('Disk or RAM safety threshold violated')
            t=time.perf_counter()
            create_indexes(db)
            metrics['index_creation_seconds']=time.perf_counter()-t
            if safety_check and not safety_check(True): raise RuntimeError('Disk or RAM safety threshold violated')
            t=time.perf_counter()
            db.execute('VACUUM')
            metrics['vacuum_seconds']=time.perf_counter()-t
            db.close()
            return finalize(root,temp,version,(old['lexical_generation']+1 if old else 1),
                            count,source_db,start,old,failpoint,metrics=metrics)
        finally:
            db.close()
            temp.unlink(missing_ok=True)
            Path(str(temp)+'-journal').unlink(missing_ok=True)


class LexicalSnapshotWriter:
    """Test/offline mutation API: unpublished copy, atomic transaction, new version."""
    def __init__(self,root,collection):
        self.root=Path(root)
        self.collection=collection

    def sync_work_id(self,work_id,failpoint=None):
        # Authoritative read under the same writer lock as replacement/publication.
        return self._replace(work_id,False,failpoint)

    def delete_work_id(self,work_id,failpoint=None):
        return self._replace(work_id,True,failpoint)

    def _replace(self,work_id,delete,failpoint):
        if not isinstance(work_id,str) or not work_id.strip(): raise ValueError('Invalid work_id')
        with writer_lock(self.root):
            path,old=previous(self.root)
            if path is None: raise ValueError('No lexical snapshot')
            if old['book_count']>MAX_BUILD_BOOKS: raise ValueError('Live/full-size mutation is not enabled')
            doc=None if delete else self.collection.find_one({'work_id':work_id},{'_id':0,'work_id':1,'title':1,'authors':1})
            if doc is not None and doc.get('work_id')!=work_id: raise ValueError('Mongo identity mismatch')
            rows=[] if doc is None else lexical_rows(doc)
            db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
            existing=db.execute('SELECT value_type,normalized_value,work_id FROM lexical_values WHERE work_id=? ORDER BY value_type,normalized_value',(work_id,)).fetchall()
            db.close()
            if existing==rows: return old  # Same payload is a genuine no-op.
            version=uuid.uuid4().hex
            temp=self.root/('building_'+version+'.sqlite')
            shutil.copyfile(path,temp)
            db=sqlite3.connect(temp)
            start=time.perf_counter()
            def hook(stage):
                if failpoint: failpoint(stage)
            try:
                db.execute('PRAGMA synchronous=FULL')
                with db:
                    db.execute('DELETE FROM lexical_values WHERE work_id=?',(work_id,))
                    hook('after_delete')
                    for row in rows:
                        db.execute(INSERT,row)
                        hook('during_insert')
                    hook('before_commit')
                hook('after_commit')
                db.close()
                # Build book_count is the source snapshot's count; update it for
                # representable IDs only. Empty-title/author docs cannot be counted
                # as membership without adding a separate table.
                count=old['book_count']+int(bool(rows))-int(bool(existing))
                return finalize(self.root,temp,version,old['lexical_generation']+1,count,
                                old['source_db_name'],start,old,failpoint,last_sync=now())
            finally:
                db.close()
                temp.unlink(missing_ok=True)
                Path(str(temp)+'-journal').unlink(missing_ok=True)


def preflight(root,book_count,source_db,bytes_per_book=400):
    root=Path(root).resolve()
    existing=root
    while not existing.exists(): existing=existing.parent
    final=int(book_count*bytes_per_book)
    retained=sum(p.stat().st_size for p in root.glob('lexical_*.*')) if root.is_dir() else 0
    # Build+index sort+validation, with a previous rollback copy and headroom.
    journal=int(final*.75)
    margin=max(2*1024**3,final)
    minimum=2*final+journal+retained+margin
    free=shutil.disk_usage(existing).free
    import psutil
    ram=psutil.virtual_memory()
    reserve=512*1024**2
    return {'source_db_name':source_db,'book_count':book_count,'output':str(root),
            'budget_bytes_per_book':bytes_per_book,
            'free_disk':free,'estimated_final_bytes':final,'temporary_build_bytes':final,
            'journal_and_sort_allowance':journal,'retained_versions_bytes':retained,
            'safety_margin':margin,'minimum_free_bytes':minimum,'recommended_free_bytes':int(minimum*1.5),
            'build_ram_reserve_bytes':reserve,'available_ram_bytes':ram.available,
            'resource_check_pass':free>=int(minimum*1.5) and ram.available>=reserve*2,
            'full_build_authorized':False,'phase_limit_books':MAX_BUILD_BOOKS}
