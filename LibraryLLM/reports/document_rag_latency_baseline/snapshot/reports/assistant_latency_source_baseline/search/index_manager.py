"""One-writer FAISS HNSW catalogue index with immutable base + delta snapshots.

FAISS IndexHNSWFlat cannot remove/replace nodes. An override map tombstones base
and old delta labels. Normal writes clone only the small delta, append changed
vectors, validate immutable files, then atomically replace one pointer. Searches
retain one snapshot reference for the complete retrieval operation.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sqlite3
import threading
import time
import uuid

import faiss
import numpy as np

from search.catalogue import content_hash, current_books, searchable, semantic_text, text_value
from search.embedding_cache import EmbeddingCache
from search.sync_queue import SyncQueue, file_lock

LOG = logging.getLogger(__name__)
MODEL = "all-MiniLM-L6-v2"
DIMENSION = 384
VERSION_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def available_memory():
    if os.name == "nt":
        import ctypes
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in
                ("total_physical", "available_physical", "total_page", "available_page",
                 "total_virtual", "available_virtual", "extended")]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.available_physical
    elif hasattr(os, "sysconf"):
        return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    return None


def new_index(dimension=DIMENSION):
    index = faiss.IndexHNSWFlat(dimension, 32, faiss.METRIC_INNER_PRODUCT)
    index.hnsw.efConstruction = 200
    index.hnsw.efSearch = 128
    return index


def digest_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def durable_json(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False)
        file.flush()
        os.fsync(file.fileno())


@contextmanager
def writer_lock(root):
    with file_lock(Path(root) / "writer.lock") as acquired:
        yield acquired


@dataclass(frozen=True)
class Snapshot:
    base: object
    work_ids: object
    delta: object
    delta_ids: tuple
    overrides: dict
    manifest: dict
    managed_ids: frozenset = frozenset()

    def candidates(self, vector, count):
        found = {}
        for index, ids, is_delta in ((self.base, self.work_ids, False),
                                     (self.delta, self.delta_ids, True)):
            if index.ntotal == 0:
                continue
            scores, labels = index.search(vector, min(count, index.ntotal))
            for score, label in zip(scores[0], labels[0]):
                if label < 0 or label >= len(ids):
                    continue
                wid = str(ids[label])
                override = self.overrides.get(wid)
                if is_delta:
                    if override is None or override["label"] != int(label):
                        continue
                elif override is not None:
                    continue
                found[wid] = max(found.get(wid, float("-inf")), float(score))
        return [{"work_id": wid, "hnsw_score": score}
                for wid, score in sorted(found.items(), key=lambda item: item[1], reverse=True)]


class IndexManager:
    def __init__(self, root, books, embedder, *, model_version=None, legacy_dir=None,
                 dimension=DIMENSION, poll_seconds=2, corpus_limit=5_000_000, recover=False):
        self.root = Path(root)
        self.versions = self.root / "versions"
        self.versions.mkdir(parents=True, exist_ok=True)
        self.books = books
        self.embedder = embedder
        self.dimension = dimension
        self.poll_seconds = poll_seconds
        self.corpus_limit = corpus_limit
        self.model_lock = threading.Lock()
        self.local_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        self.queue = SyncQueue(self.root)
        # Hash actual local model weights/config instead of a mutable model alias.
        self.model_version = model_version or self._model_fingerprint()
        self.cache = EmbeddingCache(self.root, self.model_version, dimension, legacy_dir)
        try:
            self.snapshot = self._startup_snapshot()
        except (ValueError, OSError, RuntimeError, KeyError):
            if not recover:
                raise
            # Explicit administrator-only recovery worker. Search itself refuses
            # startup when no validated graph is available.
            self.snapshot = Snapshot(new_index(dimension), np.array([], dtype=str),
                                     new_index(dimension), (), {}, {
                "version": "recovery", "base_version": "recovery", "semantic_generation": 0,
                "active_vectors": 0, "mapping_count": 0, "deleted_vectors": 0,
                "mutation_count_since_rebuild": 0, "last_full_rebuild": None, "baseline_verified": False})
            self.queue.request(kind="rebuild")

    def _model_fingerprint(self):
        digest = hashlib.sha256((MODEL + ":normalize:256").encode())
        for name, tensor in self.embedder.state_dict().items():
            digest.update(name.encode())
            digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
        digest.update(json.dumps(self.embedder.tokenizer.get_vocab(), sort_keys=True).encode())
        return MODEL + ":" + digest.hexdigest()

    def encode(self, texts):
        with self.model_lock:
            vectors = np.asarray(self.embedder.encode(
                texts, batch_size=64, convert_to_numpy=True,
                normalize_embeddings=True, show_progress_bar=False), dtype=np.float32)
        if vectors.shape != (len(texts), self.dimension) or not np.isfinite(vectors).all():
            raise ValueError("Invalid generated embeddings")
        if np.any(np.linalg.norm(vectors, axis=1) < 1e-8):
            raise ValueError("Zero embedding")
        faiss.normalize_L2(vectors)
        return vectors

    def _version_dir(self, version):
        if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
            raise ValueError("Invalid snapshot version")
        return self.versions / version

    def _validate_graph(self, index, ids):
        if (not isinstance(index, faiss.IndexHNSWFlat) or index.d != self.dimension
                or index.metric_type != faiss.METRIC_INNER_PRODUCT or index.ntotal != len(ids)):
            raise ValueError("Index/mapping/dimension mismatch")
        if any(not isinstance(wid, (str, np.str_)) or not str(wid).strip() for wid in ids):
            raise ValueError("Invalid work_id mapping")
        index.hnsw.efSearch = 128

    def _legacy_snapshot(self):
        meta = json.loads((self.root / "hnsw_metadata.json").read_text())
        if (meta["model_name"] != MODEL or meta["dimension"] != self.dimension
                or not meta.get("normalized") or meta.get("metric") != "inner_product"):
            raise ValueError("Incompatible legacy manifest")
        index = faiss.read_index(str(self.root / "hnsw.index"))
        ids = np.load(self.root / "index_work_ids.npy", allow_pickle=True)
        self._validate_graph(index, ids)
        if meta["vector_count"] != len(ids) or len(set(ids)) != len(ids):
            raise ValueError("Invalid legacy mapping count or duplicate work_ids")
        return Snapshot(index, ids, new_index(self.dimension), (), {}, {
            "version": "legacy", "base_version": "legacy", "semantic_generation": 0,
            "active_vectors": len(ids), "mapping_count": len(ids), "deleted_vectors": 0,
            "mutation_count_since_rebuild": 0, "last_full_rebuild": None,
            "baseline_verified": False,
            "index_size_bytes": (self.root / "hnsw.index").stat().st_size,
        })

    def _startup_snapshot(self):
        pointer = self.root / "active_index.json"
        if not pointer.exists():
            return self._legacy_snapshot()
        candidates = []
        try:
            data = json.loads(pointer.read_text())
            candidates = [data["version"], *data.get("previous", [])]
        except (ValueError, KeyError, TypeError):
            candidates = [p.name for p in sorted(self.versions.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
                          if p.is_dir() and (p / "manifest.json").exists()]
        for i, version in enumerate(candidates):
            try:
                snapshot = self.load_snapshot(version)
                if i:
                    self.queue.state("STALE")
                    LOG.error("hnsw_startup_recovered_previous_snapshot")
                return snapshot
            except (ValueError, OSError, RuntimeError, KeyError):
                LOG.error("hnsw_snapshot_validation_failed")
        # A trusted old graph still requires Mongo validation and is marked stale.
        self.queue.state("STALE")
        return self._legacy_snapshot()

    def load_snapshot(self, version):
        directory = self._version_dir(version)
        manifest = json.loads((directory / "manifest.json").read_text())
        if not isinstance(manifest, dict):
            raise ValueError("Invalid snapshot manifest")
        if (manifest["version"] != version or manifest["embedding_dimension"] != self.dimension
                or manifest["embedding_model"] != MODEL or manifest["model_version"] != self.model_version):
            raise ValueError("Incompatible snapshot manifest")
        for name in ("delta.index", "delta.json"):
            if digest_file(directory / name) != manifest["checksums"][name]:
                raise ValueError("Snapshot checksum mismatch")
        base_version = manifest["base_version"]
        existing = getattr(self, "snapshot", None)
        if existing and existing.manifest["base_version"] == base_version:
            base, ids = existing.base, existing.work_ids
        elif base_version == "legacy":
            legacy = self._legacy_snapshot()
            base, ids = legacy.base, legacy.work_ids
        else:
            base_dir = self._version_dir(base_version)
            base_manifest = json.loads((base_dir / "manifest.json").read_text())
            if (base_manifest["version"] != base_version or base_manifest["model_version"] != self.model_version
                    or base_manifest["embedding_dimension"] != self.dimension):
                raise ValueError("Incompatible base manifest")
            for name in ("base.index", "base_ids.npy"):
                if digest_file(base_dir / name) != base_manifest["checksums"][name]:
                    raise ValueError("Base snapshot checksum mismatch")
            base = faiss.read_index(str(base_dir / "base.index"))
            ids = np.load(base_dir / "base_ids.npy", allow_pickle=False)
            self._validate_graph(base, ids)
            if len(set(ids)) != len(ids):
                raise ValueError("Duplicate base work_id")
        delta = faiss.read_index(str(directory / "delta.index"))
        mapping = json.loads((directory / "delta.json").read_text())
        if (not isinstance(mapping, dict) or not isinstance(mapping.get("ids"), list)
                or not isinstance(mapping.get("overrides"), dict)):
            raise ValueError("Invalid delta metadata")
        delta_ids = tuple(mapping["ids"])
        overrides = mapping["overrides"]
        self._validate_graph(delta, delta_ids)
        if not set(delta_ids).issubset(overrides):
            raise ValueError("Unmapped delta label")
        for wid, item in overrides.items():
            if not isinstance(item, dict) or not isinstance(item.get("base"), bool):
                raise ValueError("Invalid override metadata")
            label = item["label"]
            if (not wid or (label is not None and
                    (not isinstance(label, int) or label < 0 or label >= len(delta_ids) or delta_ids[label] != wid))):
                raise ValueError("Invalid delta label mapping")
        active_delta = sum(item["label"] is not None for item in overrides.values())
        deleted = sum(bool(item["base"]) for item in overrides.values()) + len(delta_ids) - active_delta
        active = len(ids) + len(delta_ids) - deleted
        if (manifest["mapping_count"] != len(ids) + len(delta_ids)
                or manifest["active_vectors"] != active or manifest["deleted_vectors"] != deleted):
            raise ValueError("Snapshot counts mismatch")
        return Snapshot(base, ids, delta, delta_ids, overrides, manifest,
                        frozenset(mapping.get("managed_ids", [])))

    def refresh(self):
        pointer = self.root / "active_index.json"
        if pointer.exists():
            try:
                version = json.loads(pointer.read_text())["version"]
                if version != self.snapshot.manifest["version"]:
                    snapshot = self.load_snapshot(version)
                    self.snapshot = snapshot
                    LOG.info("hnsw_index_swapped version=%s", version)
            except (ValueError, OSError, RuntimeError, KeyError, TypeError):
                # Keep serving the validated in-memory/previous generation.
                # Pending events must still be replayable to repair the pointer.
                LOG.error("hnsw_reload_failed previous_snapshot_retained=true")

    def _persist(self, base, ids, delta, delta_ids, overrides, generation, *, full=False, mutations=0, managed_ids=None):
        previous = self.snapshot
        version = uuid.uuid4().hex
        directory = self._version_dir(version)
        directory.mkdir()
        start = time.perf_counter()
        try:
            faiss.write_index(delta, str(directory / "delta.index"))
            managed_ids = (previous.managed_ids | set(overrides)) if managed_ids is None else managed_ids
            durable_json(directory / "delta.json", {"ids": list(delta_ids), "overrides": overrides,
                                                    "managed_ids": sorted(managed_ids)})
            files = ["delta.index", "delta.json"]
            if full:
                # Full-build caller transfers ownership, avoiding three huge
                # graphs resident simultaneously during reload validation.
                builder = base.pop()
                faiss.write_index(builder, str(directory / "base.index"))
                del builder
                np.save(directory / "base_ids.npy", np.asarray(ids, dtype=str), allow_pickle=False)
                files += ["base.index", "base_ids.npy"]
            for name in files:
                with open(directory / name, "r+b") as file:
                    os.fsync(file.fileno())
            active_delta = sum(item["label"] is not None for item in overrides.values())
            deleted = sum(bool(item["base"]) for item in overrides.values()) + len(delta_ids) - active_delta
            now = datetime.now(timezone.utc).isoformat()
            manifest = {
                "version": version, "created_at": now, "embedding_model": MODEL,
                "model_version": self.model_version, "embedding_dimension": self.dimension,
                "base_version": version if full else previous.manifest["base_version"],
                "semantic_generation": generation, "mapping_count": len(ids) + len(delta_ids),
                "active_vectors": len(ids) + active_delta - sum(bool(v["base"]) for v in overrides.values()),
                "deleted_vectors": deleted,
                "mutation_count_since_rebuild": 0 if full else previous.manifest["mutation_count_since_rebuild"] + mutations,
                "last_full_rebuild": now if full else previous.manifest["last_full_rebuild"],
                "baseline_verified": full or previous.manifest.get("baseline_verified", False),
                "checksums": {name: digest_file(directory / name) for name in files},
                "index_size_bytes": sum((directory / name).stat().st_size for name in files) + (
                    0 if full else (self.root / "hnsw.index").stat().st_size
                    if previous.manifest["base_version"] == "legacy" else
                    (self._version_dir(previous.manifest["base_version"]) / "base.index").stat().st_size),
            }
            durable_json(directory / "manifest.json", manifest)
            # Release the builder graph before loading the on-disk copy in full
            # builds at the caller where possible; validation always reads files.
            validated = self.load_snapshot(version)
            previous_versions = []
            if VERSION_PATTERN.fullmatch(previous.manifest["version"]):
                previous_versions.append(previous.manifest["version"])
            pointer = self.root / ("active_index." + version + ".tmp")
            durable_json(pointer, {"version": version, "previous": previous_versions})
            os.replace(pointer, self.root / "active_index.json")
            self.snapshot = validated
            LOG.info("hnsw_index_swapped version=%s generation=%d records=%d duration=%.3f",
                     version, generation, manifest["active_vectors"], time.perf_counter()-start)
            try:
                self._prune({version, *previous_versions})
            except OSError:
                LOG.warning("hnsw_snapshot_cleanup_deferred")
        except Exception:
            # Only this newly allocated, unpublished directory can be removed.
            if self.snapshot.manifest["version"] != version:
                shutil.rmtree(directory, ignore_errors=True)
            raise

    def _prune(self, retained):
        # Keep active + previous and both base dependencies. Never touch legacy,
        # model files, RAG, or unrecognized directories.
        for version in list(retained):
            manifest = json.loads((self._version_dir(version) / "manifest.json").read_text())
            retained.add(manifest["base_version"])
        for directory in self.versions.iterdir():
            if directory.resolve().parent != self.versions.resolve():
                continue
            if directory.is_dir() and VERSION_PATTERN.fullmatch(directory.name) and directory.name not in retained:
                if (directory / "manifest.json").is_file():
                    try:
                        shutil.rmtree(directory)
                    except OSError:
                        LOG.warning("hnsw_snapshot_cleanup_deferred")

    def _embeddings(self, books):
        texts = {book["work_id"]: semantic_text(book) for book in books}
        hashes = {wid: content_hash(text) for wid, text in texts.items()}
        vectors = self.cache.get_many(hashes.items())
        missing = [wid for wid in texts if wid not in vectors]
        for offset in range(0, len(missing), 64):
            batch = missing[offset:offset+64]
            encoded = self.encode([texts[wid] for wid in batch])
            self.cache.put_many((wid, hashes[wid], vector) for wid, vector in zip(batch, encoded))
            vectors.update(zip(batch, encoded))
        return hashes, vectors

    def _batch_sync(self, work_ids, generation):
        start = time.perf_counter()
        ids = list(dict.fromkeys(work_ids))
        LOG.info("hnsw_batch_sync_started batch_size=%d generation=%d", len(ids), generation)
        old = self.snapshot
        free = available_memory()
        clone_bytes = old.delta.ntotal * (self.dimension * 4 + 32 * 8) * 2
        if free is not None and free < clone_bytes:
            raise MemoryError("Not enough memory to copy and validate the delta graph")
        delta = faiss.clone_index(old.delta)
        delta_ids = list(old.delta_ids)
        overrides = dict(old.overrides)
        base_members = set(str(wid) for wid in old.work_ids[np.isin(old.work_ids, ids)])
        mutations = 0
        for offset in range(0, len(ids), 512):
            batch = ids[offset:offset+512]
            books = current_books(self.books, batch)
            hashes, vectors = self._embeddings(list(books.values()))
            additions = []
            for wid in batch:
                existing = overrides.get(wid)
                base_present = wid in base_members
                if wid not in books:
                    if existing and existing["label"] is None:
                        continue
                    overrides[wid] = {"label": None, "hash": None, "base": base_present}
                    mutations += 1
                    LOG.info("hnsw_delete_completed generation=%d", generation)
                    continue
                if existing and existing["hash"] == hashes[wid] and existing["label"] is not None:
                    continue
                label = len(delta_ids)
                additions.append(vectors[wid])
                delta_ids.append(wid)
                overrides[wid] = {"label": label, "hash": hashes[wid], "base": base_present}
                mutations += 1
                LOG.info("hnsw_%s_completed generation=%d", "update" if base_present or existing else "add", generation)
            if additions:
                free = available_memory()
                validation_bytes = (delta.ntotal + len(additions)) * (self.dimension * 4 + 32 * 8)
                if free is not None and free < validation_bytes:
                    raise MemoryError("Not enough memory for the growing delta snapshot")
                delta.add(np.asarray(additions, dtype=np.float32))
        self._persist(old.base, old.work_ids, delta, delta_ids, overrides, generation, mutations=mutations)
        LOG.info("hnsw_batch_sync_completed batch_size=%d duration=%.3f generation=%d",
                 len(ids), time.perf_counter()-start, generation)

    def _full_rebuild(self, generation, requested_ids=()):
        """Stream current Mongo into disk staging; retain the original quality/top-5M policy.

        Explicitly created/edited searchable records (overrides) are also included,
        even when outside the original offline corpus selection, as incremental ADD promises.
        """
        start = time.perf_counter()
        LOG.info("hnsw_full_rebuild_started generation=%d", generation)
        # The old graph stays resident. At least one additional graph must fit.
        # This estimate uses existing persisted graph bytes, not an arbitrary
        # catalogue-size threshold. Avoid taking the serving process down by OOM.
        base_version = self.snapshot.manifest["base_version"]
        base_path = (self.root / "hnsw.index" if base_version in {"legacy", "recovery"} else
                     self._version_dir(base_version) / "base.index")
        required = base_path.stat().st_size if base_path.exists() else 0
        if hasattr(self.books, "estimated_document_count"):
            # Account for corpus growth too: float32 vectors plus the graph's
            # existing observed bytes per record (or M=32 neighbour storage).
            count = min(self.books.estimated_document_count(), self.corpus_limit) + len(self.snapshot.managed_ids)
            per_record = max(self.dimension * 4 + 32 * 8, required / max(1, len(self.snapshot.work_ids)))
            required = max(required, int(count * per_record))
        free = available_memory()
        if free is not None and free < required:
            LOG.error("hnsw_full_rebuild_insufficient_memory required_bytes=%d available_bytes=%d", required, free)
            raise MemoryError("Not enough free physical memory for an additional HNSW graph")
        if shutil.disk_usage(self.root).free < required * 2:
            raise OSError("Not enough disk space for snapshot and staging")
        self.cache.seed_legacy(self.encode)
        managed = self.snapshot.managed_ids | set(self.snapshot.overrides) | set(requested_ids)
        path = self.root / ("corpus-" + uuid.uuid4().hex + ".sqlite3")
        stage = sqlite3.connect(path)
        try:
            stage.execute("CREATE TABLE corpus (id TEXT PRIMARY KEY, text TEXT, quality INTEGER, ratings REAL, logs REAL, editions REAL, explicit INTEGER)")
            cursor = self.books.find({}, {"_id": 0})
            try:
                for book in cursor:
                    if not searchable(book):
                        continue
                    wid = book["work_id"]
                    description = len(text_value(book.get("description"))) >= 50
                    subjects = len(text_value(book.get("subjects"))) >= 10
                    authors = bool(text_value(book.get("authors")))
                    ratings, logs = book.get("rating_count") or 0, book.get("reading_log_count") or 0
                    quality = 5*description + 3*subjects + 2*authors + 2*(ratings > 0) + 2*(logs > 0)
                    explicit = wid in managed
                    if (quality and any(text_value(book.get(k)) for k in ("authors", "subjects", "description"))) or explicit:
                        stage.execute("INSERT INTO corpus VALUES(?,?,?,?,?,?,?)", (wid, semantic_text(book), quality,
                                      ratings, logs, book.get("edition_count") or 0, int(explicit)))
            finally:
                if hasattr(cursor, "close"):
                    cursor.close()
            stage.commit()
            # Explicit records outside the original selection are unioned, never
            # substituted for a record on the basis of Mongo insertion order.
            rows = stage.execute("""SELECT id,text FROM corpus WHERE id IN (
                SELECT id FROM corpus WHERE quality>0 ORDER BY quality DESC,ratings DESC,logs DESC,editions DESC,id LIMIT ?)
                OR explicit=1 ORDER BY id""", (self.corpus_limit,))
            index = new_index(self.dimension)
            ids = []
            while batch := rows.fetchmany(512):
                hashes = {wid: content_hash(text) for wid, text in batch}
                vectors = self.cache.get_many(hashes.items())
                missing = [(wid, text) for wid, text in batch if wid not in vectors]
                for offset in range(0, len(missing), 64):
                    part = missing[offset:offset+64]
                    encoded = self.encode([text for _, text in part])
                    self.cache.put_many((wid, hashes[wid], vector) for (wid, _), vector in zip(part, encoded))
                    vectors.update((wid, vector) for (wid, _), vector in zip(part, encoded))
                index.add(np.asarray([vectors[wid] for wid, _ in batch], dtype=np.float32))
                ids.extend(wid for wid, _ in batch)
            builder = [index]
            del index
            self._persist(builder, ids, new_index(self.dimension), (), {}, generation, full=True,
                          managed_ids=managed)
            LOG.info("hnsw_full_rebuild_completed records=%d duration=%.3f generation=%d",
                     len(ids), time.perf_counter()-start, generation)
        finally:
            stage.close()
            path.unlink(missing_ok=True)

    def process_once(self):
        """Drain a bounded group. Events committed during a build remain pending."""
        if not self.local_lock.acquire(blocking=False):
            return False
        try:
            with writer_lock(self.root) as acquired:
                if not acquired:
                    return False
                self.queue.import_fallback_requests()
                self.queue.recover_mutations()
                self.refresh()
                events = self.queue.pending(self.snapshot.manifest["semantic_generation"])
                if not events:
                    self.queue.state("HEALTHY" if self.snapshot.manifest.get("baseline_verified") else "STALE")
                    return False
                if self.queue.status()["retry_at"] > time.time():
                    return False
                generation = events[-1][0]
                full = self.snapshot.manifest["version"] == "recovery" or any(kind == "rebuild" for _, kind, _ in events)
                try:
                    self.queue.state("REBUILDING" if full else "SYNCING")
                    ids = [wid for _, _, payload in events for wid in json.loads(payload)]
                    if full:
                        self._full_rebuild(generation, ids)
                    else:
                        self._batch_sync(ids, generation)
                    self.queue.state("STALE" if self.queue.latest() > generation else "HEALTHY")
                    return True
                except Exception as error:
                    self.queue.state("STALE", failed=True)
                    LOG.error("hnsw_%s_failed generation=%d error_type=%s",
                              "full_rebuild" if full else "batch_sync", generation, type(error).__name__)
                    return False
        finally:
            self.local_lock.release()

    def batch_sync(self, work_ids):
        return self.queue.request(work_ids)

    def add_book(self, work_id):
        return self.batch_sync([work_id])

    update_book = add_book
    delete_book = add_book

    def rebuild_full_index(self):
        return self.queue.request(kind="rebuild")

    def status(self):
        status = self.queue.status()
        manifest = self.snapshot.manifest
        pending = self.queue.latest() > manifest["semantic_generation"]
        if pending and status["index_status"] == "HEALTHY":
            status["index_status"] = "STALE"
        if not manifest.get("baseline_verified") and status["index_status"] == "HEALTHY":
            status["index_status"] = "STALE"
        status.update({key: manifest.get(key) for key in (
            "active_vectors", "deleted_vectors", "mapping_count", "mutation_count_since_rebuild",
            "last_full_rebuild", "index_size_bytes", "baseline_verified")})
        status.update(index_version=manifest["version"], semantic_generation=manifest["semantic_generation"], pending=pending)
        return status

    def start(self):
        if self.thread is not None:
            return
        self.stop_event.clear()
        def run():
            while not self.stop_event.is_set():
                try:
                    self.refresh()
                    self.process_once()
                except Exception as error:
                    LOG.error("hnsw_worker_failed error_type=%s", type(error).__name__)
                    try:
                        self.queue.state("STALE", failed=True)
                    except Exception:
                        LOG.error("hnsw_status_store_unavailable")
                self.stop_event.wait(self.poll_seconds)
        self.thread = threading.Thread(target=run, name="catalogue-index-sync", daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
