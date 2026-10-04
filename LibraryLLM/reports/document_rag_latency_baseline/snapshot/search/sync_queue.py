"""Durable local outbox shared by Core and Search on this Windows host.

Only identifiers cross the service boundary. Workers always re-read MongoDB.
Both processes must use the same LUMINAR_SEARCH_INDEX_DIR and database config.
"""
import json
import hashlib
import logging
import os
from pathlib import Path
import sqlite3
import time
import uuid
from contextlib import contextmanager

LOG = logging.getLogger(__name__)
DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "datasets/ai/faiss/hnsw"


@contextmanager
def file_lock(path):
    """Nonblocking process lock; the OS releases it even after a process crash."""
    file = open(path, "a+b")
    acquired = False
    try:
        if os.name == "nt":
            import msvcrt
            if file.tell() == 0:
                file.write(b"0")
                file.flush()
            file.seek(0)
            try:
                msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
                acquired = True
            except OSError:
                pass
        else:
            import fcntl
            try:
                fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                pass
        yield acquired
    finally:
        if acquired:
            if os.name == "nt":
                file.seek(0)
                msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(file.fileno(), fcntl.LOCK_UN)
        file.close()


class MutationJournal:
    """Durable intent before Mongo; publish only after success.

    An OS lock keeps the worker from consuming an in-flight intent. After Core
    crashes, the worker reconciles the orphaned IDs from CURRENT Mongo. There is
    no assumption that an interrupted Mongo operation committed or failed.
    """
    def __init__(self):
        self.root = index_root()
        # Bind/validate catalogue configuration before any Mongo write.
        SyncQueue(self.root)
        directory = self.root / "mutation_intents"
        directory.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        self.path = directory / (token + ".jsonl")
        self.lock_path = directory / (token + ".lock")
        self.lock = file_lock(self.lock_path)
        if not self.lock.__enter__():
            raise RuntimeError("Unable to acquire mutation intent lock")
        self.closed = False

    def add(self, work_ids):
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(list(work_ids)) + "\n")
            file.flush()
            os.fsync(file.fileno())

    def finish(self, work_ids=(), *, uncertain=False):
        if self.closed:
            return
        try:
            ids = list(work_ids)
            queued = request_catalogue_sync(ids) if ids else True
            if queued is not None and not uncertain:
                try:
                    self.path.unlink(missing_ok=True)
                except OSError:
                    LOG.warning("hnsw_mutation_intent_cleanup_deferred")
        finally:
            self.closed = True
            self.lock.__exit__(None, None, None)
            if not self.path.exists():
                try:
                    self.lock_path.unlink(missing_ok=True)
                except OSError:
                    LOG.warning("hnsw_mutation_lock_cleanup_deferred")


@contextmanager
def catalogue_mutation(work_ids):
    """Call `committed.extend(ids)` only after the Mongo operation succeeds."""
    journal = MutationJournal()
    committed = []
    uncertain = False
    try:
        journal.add(work_ids)
        yield committed
    except Exception as error:
        from pymongo.errors import AutoReconnect, WriteConcernError
        uncertain = isinstance(error, (AutoReconnect, WriteConcernError))
        raise
    finally:
        journal.finish(committed, uncertain=uncertain)


def index_root():
    configured = os.environ.get("LUMINAR_SEARCH_INDEX_DIR")
    if not configured and os.getenv("MONGO_DB_NAME", "luminar_library") != "luminar_library":
        raise ValueError("A non-default Mongo database requires a separate LUMINAR_SEARCH_INDEX_DIR")
    return Path(configured or DEFAULT_ROOT)


class SyncQueue:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "sync_queue.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
                    ids TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS status (
                    id INTEGER PRIMARY KEY CHECK(id=1), state TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0, retry_at REAL NOT NULL DEFAULT 0);
                INSERT OR IGNORE INTO status(id,state) VALUES(1,'STALE');
                CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
            # A shared directory must never silently combine different catalogues.
            source = hashlib.sha256((os.getenv("MONGO_URI", "mongodb://localhost:27017") + "\n" +
                                     os.getenv("MONGO_DB_NAME", "luminar_library")).encode()).hexdigest()
            db.execute("INSERT OR IGNORE INTO config VALUES('source',?)", (source,))
            if db.execute("SELECT value FROM config WHERE key='source'").fetchone()[0] != source:
                raise ValueError("Search directory belongs to a different Mongo configuration")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        finally:
            db.close()

    def request(self, work_ids=(), kind="sync"):
        ids = list(dict.fromkeys(str(wid) for wid in work_ids if wid))
        if not ids and kind != "rebuild":
            return None
        with self.connect() as db:
            seq = db.execute("INSERT INTO events(kind,ids,created) VALUES(?,?,?)",
                             (kind, json.dumps(ids), time.time())).lastrowid
            db.execute("UPDATE status SET state='STALE' WHERE id=1 AND state NOT IN ('SYNCING','REBUILDING')")
        LOG.info("hnsw_sync_requested generation=%s batch_size=%d kind=%s", seq, len(ids), kind)
        return seq

    def pending(self, after):
        with self.connect() as db:
            return db.execute("SELECT seq,kind,ids FROM events WHERE seq>? ORDER BY seq LIMIT 100",
                              (after,)).fetchall()

    def latest(self):
        with self.connect() as db:
            return db.execute("SELECT COALESCE(MAX(seq),0) FROM events").fetchone()[0]

    def status(self):
        with self.connect() as db:
            state, attempts, retry_at = db.execute("SELECT state,attempts,retry_at FROM status WHERE id=1").fetchone()
        return {"index_status": state, "retry_attempts": attempts, "retry_at": retry_at}

    def state(self, state, failed=False):
        with self.connect() as db:
            attempts = db.execute("SELECT attempts FROM status WHERE id=1").fetchone()[0]
            if failed:
                attempts += 1
            elif state not in {"SYNCING", "REBUILDING"}:
                attempts = 0
            retry_at = time.time() + min(300, 2 ** min(attempts, 8)) if failed else 0
            db.execute("UPDATE status SET state=?,attempts=?,retry_at=? WHERE id=1",
                       (state, attempts, retry_at))

    def import_fallback_requests(self):
        # A locked/unavailable queue can still accept a durable per-request spool.
        # Reimport after a crash is harmless because synchronization is idempotent.
        for path in (self.root / "pending_requests").glob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.request(payload["ids"], payload["kind"])
            path.unlink()

    def recover_mutations(self):
        for path in (self.root / "mutation_intents").glob("*.jsonl"):
            lock_path = path.with_suffix(".lock")
            with file_lock(lock_path) as acquired:
                if not acquired:
                    continue
                if not path.exists():
                    continue
                ids = []
                # A crash while appending the next line happened BEFORE that
                # batch's Mongo write; completed lines remain recoverable.
                for line in path.read_text(encoding="utf-8").splitlines():
                    try:
                        ids.extend(json.loads(line))
                    except json.JSONDecodeError:
                        break
                if ids:
                    self.request(ids)
                path.unlink()
                LOG.warning("hnsw_interrupted_mongo_mutation_recovered batch_size=%d", len(ids))
            lock_path.unlink(missing_ok=True)


def request_catalogue_sync(work_ids, kind="sync"):
    # Called only AFTER Mongo success. A disk error must not roll back Mongo or
    # misreport its successful write as a failed catalogue mutation.
    try:
        return SyncQueue(index_root()).request(work_ids, kind)
    except ValueError:
        LOG.error("hnsw_index_marked_stale reason=index_configuration_mismatch maintenance_required=true")
        return None
    except Exception:
        try:
            directory = index_root() / "pending_requests"
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / (uuid.uuid4().hex + ".tmp")
            with path.open("w", encoding="utf-8") as file:
                json.dump({"ids": list(work_ids), "kind": kind}, file)
                file.flush()
                os.fsync(file.fileno())
            os.replace(path, path.with_suffix(".json"))
            LOG.warning("hnsw_index_marked_stale reason=outbox_spooled retryable=true")
            return "spooled"
        except Exception:
            LOG.error("hnsw_index_marked_stale reason=outbox_unavailable maintenance_required=true")
        return None


class CatalogueImportSync:
    """Collect committed IDs across a partial import; publish ONE final event."""
    def __init__(self):
        self.affected = set()
        self.journal = None
        self.uncertain = False

    def insert(self, collection, documents, *, bulk=False):
        from pymongo import InsertOne
        from pymongo.errors import BulkWriteError
        if self.journal is None:
            self.journal = MutationJournal()
        self.journal.add(doc['work_id'] for doc in documents)
        try:
            result = (collection.bulk_write([InsertOne(doc) for doc in documents], ordered=False)
                      if bulk else collection.insert_many(documents, ordered=False))
        except BulkWriteError as error:
            self.uncertain = bool(error.details.get("writeConcernErrors"))
            if error.details.get("nInserted", 0):
                failed = {item["index"] for item in error.details.get("writeErrors", [])}
                self.affected.update(doc["work_id"] for i, doc in enumerate(documents) if i not in failed)
            raise
        except Exception as error:
            from pymongo.errors import AutoReconnect, WriteConcernError
            self.uncertain = isinstance(error, (AutoReconnect, WriteConcernError))
            raise
        else:
            self.affected.update(doc["work_id"] for doc in documents)
            return result

    def finish(self):
        if self.journal:
            self.journal.finish(sorted(self.affected), uncertain=self.uncertain)
