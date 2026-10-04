"""Content-addressed embeddings, with optional verified legacy vector references."""
import json
from pathlib import Path
import sqlite3

import numpy as np

from search.catalogue import content_hash


class EmbeddingCache:
    def __init__(self, root, model_version, dimension, legacy_dir=None):
        self.path = Path(root) / "embedding_cache.sqlite3"
        self.model_version = model_version
        self.dimension = dimension
        self.legacy_dir = Path(legacy_dir) if legacy_dir else None
        self.legacy_vectors = None
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS vectors (
                    work_id TEXT NOT NULL, model TEXT NOT NULL, hash TEXT NOT NULL,
                    vector BLOB, legacy_row INTEGER,
                    PRIMARY KEY(work_id,model));
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
            """)

    def connect(self):
        from contextlib import contextmanager

        @contextmanager
        def connection():
            db = sqlite3.connect(self.path, timeout=30)
            try:
                with db:
                    yield db
            finally:
                db.close()
        return connection()

    def _legacy(self):
        if self.legacy_vectors is None:
            self.legacy_vectors = np.load(self.legacy_dir / "vectors/embeddings.npy", mmap_mode="r")
            if self.legacy_vectors.shape[1] != self.dimension:
                raise ValueError("Legacy embedding dimension mismatch")
        return self.legacy_vectors

    def get_many(self, items):
        result = {}
        with self.connect() as db:
            for wid, digest in items:
                row = db.execute("SELECT vector,legacy_row FROM vectors WHERE work_id=? AND model=? AND hash=?",
                                 (wid, self.model_version, digest)).fetchone()
                if row:
                    try:
                        vector = (np.frombuffer(row[0], dtype=np.float32).copy() if row[0] is not None
                                  else np.array(self._legacy()[row[1]], dtype=np.float32))
                    except (ValueError, OSError, IndexError):
                        continue  # Derived cache can be regenerated from Mongo.
                    if (vector.shape != (self.dimension,) or not np.isfinite(vector).all()
                            or not np.isclose(np.linalg.norm(vector), 1, atol=1e-4)):
                        continue
                    result[wid] = vector
        return result

    def put_many(self, entries):
        with self.connect() as db:
            db.executemany("INSERT OR REPLACE INTO vectors VALUES(?,?,?,?,NULL)",
                           ((wid, self.model_version, digest, np.asarray(vector, dtype=np.float32).tobytes())
                            for wid, digest, vector in entries))

    def seed_legacy(self, encode):
        """Maintenance only. Do not assume parquet positions are business IDs.

        Verify EVERY parquet ID against the explicit embeddings work_id mapping.
        Legacy files have no model revision: verify sampled vectors with the local
        model before importing references. Current Mongo text must still hash-match.
        """
        if not self.legacy_dir or not (self.legacy_dir / "embedding_corpus.parquet").exists():
            return
        key = "legacy_seed:" + self.model_version
        with self.connect() as db:
            if db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone():
                return
        import pyarrow.parquet as pq
        meta = json.loads((self.legacy_dir / "vectors/checkpoint.json").read_text())
        if meta["model"] != "all-MiniLM-L6-v2" or meta["embedding_dimension"] != self.dimension:
            raise ValueError("Legacy model mismatch")
        ids = np.load(self.legacy_dir / "vectors/work_ids.npy", allow_pickle=True)
        vectors = self._legacy()
        parquet = pq.ParquetFile(self.legacy_dir / "embedding_corpus.parquet")
        if len(ids) != len(vectors) or parquet.metadata.num_rows != len(ids):
            raise ValueError("Legacy embedding mapping count mismatch")
        offset = 0
        for batch in parquet.iter_batches(batch_size=10000, columns=["work_id", "search_text"]):
            rows = batch.to_pydict()
            count = len(rows["work_id"])
            if list(ids[offset:offset+count]) != rows["work_id"]:
                raise ValueError("Legacy embedding work_id alignment mismatch")
            texts = [text or "" for text in rows["search_text"]]
            if offset == 0:
                sample = encode(texts[:8])
                if not np.allclose(sample, vectors[:len(sample)], atol=1e-4, rtol=1e-3):
                    raise ValueError("Legacy vectors incompatible with local embedding model")
            with self.connect() as db:
                db.executemany("INSERT OR IGNORE INTO vectors VALUES(?,?,?,NULL,?)",
                               ((wid, self.model_version, content_hash(text), offset+i)
                                for i, (wid, text) in enumerate(zip(rows["work_id"], texts))))
            offset += count
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (key, "complete"))
