"""Data-driven local book assets shared by the catalog and RAG services.

The existing ingestion mapping describes provided full texts, not supported books.
New registrations are discovered from processed/*.book.json. Index availability
requires a valid global entry, a matching per-book FAISS index, and real chunks.
No models are loaded here. Parsed assets are cached by their file revisions.
"""
from functools import lru_cache
import json
from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parent
WORK_ID = re.compile(r"OL[0-9]+W\Z")


def valid_work_id(value):
    return isinstance(value, str) and WORK_ID.fullmatch(value) is not None


def revision(path):
    try:
        stat = path.stat()
        return str(path.resolve()), stat.st_mtime_ns, stat.st_size
    except OSError:
        return str(path.resolve()), None, None


@lru_cache(maxsize=256)
def read_json(stamp):
    try:
        return json.loads(Path(stamp[0]).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def content_sources(base=BASE_DIR):
    mapping = read_json(revision(base / "rag_book_mapping.json"))
    sources = {}
    for item in mapping if isinstance(mapping, list) else []:
        if isinstance(item, dict) and valid_work_id(item.get("work_id")):
            sources[item["work_id"]] = item
    for path in sorted((base / "processed").glob("*.book.json")):
        item = read_json(revision(path))
        if (isinstance(item, dict) and valid_work_id(item.get("work_id"))
                and item.get("rights") in {"public-domain", "authorized"}
                and item.get("full_text") is True):
            sources[item["work_id"]] = item
    return sources


@lru_cache(maxsize=128)
def has_text(stamp):
    try:
        return bool(Path(stamp[0]).read_text(encoding="utf-8").strip())
    except (OSError, UnicodeError):
        return False


def readable_path(work_id, sources=None, base=BASE_DIR):
    item = (sources if sources is not None else content_sources(base)).get(work_id)
    if not item or not isinstance(item.get("filename"), str):
        return None
    root = (base / "processed").resolve()
    path = (root / item["filename"]).resolve()
    if path.suffix != ".txt" or not path.is_relative_to(root):
        return None
    return path if has_text(revision(path)) else None


@lru_cache(maxsize=128)
def validated_index(index_stamp, metadata_stamp):
    import faiss

    metadata = read_json(metadata_stamp)
    if not isinstance(metadata, list) or not metadata:
        return None
    try:
        index = faiss.read_index(index_stamp[0])
        if index.ntotal != len(metadata):
            return None
        return metadata, index.d
    except (OSError, RuntimeError):
        return None


def index_revision(base=BASE_DIR):
    """Includes removals and replacements; only stats occur for unchanged assets."""
    paths = [base / "book_index/rag.index", base / "book_index/rag_metadata.json"]
    paths += sorted((base / "book_index/books").glob("*"))
    paths += sorted((base / "book_chunks").glob("*.json"))
    return tuple(revision(path) for path in paths if not path.is_dir())


@lru_cache(maxsize=8)
def _indexed_books(base_name, stamp):
    base = Path(base_name)
    global_pair = validated_index(revision(base / "book_index/rag.index"),
                                  revision(base / "book_index/rag_metadata.json"))
    if not global_pair:
        return {}
    global_metadata, dimension = global_pair
    groups = {}
    for row in global_metadata:
        work_id = row.get("work_id")
        if valid_work_id(work_id) and row.get("document_id") == work_id:
            groups.setdefault(work_id, []).append(row)
    books = {}
    for work_id, rows in groups.items():
        pair = validated_index(revision(base / f"book_index/books/{work_id}.index"),
                               revision(base / f"book_index/books/{work_id}_metadata.json"))
        chunks_data = read_json(revision(base / f"book_chunks/{work_id}.json"))
        if not pair or not isinstance(chunks_data, dict):
            continue
        metadata, book_dimension = pair
        if book_dimension != dimension or any(
            row.get("work_id") != work_id or row.get("document_id") != work_id
            for row in metadata
        ):
            continue
        ids = {row.get("chunk_id") for row in metadata}
        global_ids = {row.get("chunk_id") for row in rows}
        text_ids = {row.get("chunk_id") for row in chunks_data.get("chunks", [])
                    if row.get("work_id") == work_id and row.get("document_id") == work_id
                    and isinstance(row.get("text"), str) and row["text"].strip()}
        if None in ids or ids != global_ids or not ids.issubset(text_ids):
            continue
        books[work_id] = rows[0]
    return books


def indexed_books(base=BASE_DIR):
    return _indexed_books(str(base), index_revision(base))


def capabilities(work_ids, base=BASE_DIR):
    sources, indexed = content_sources(base), indexed_books(base)
    return {work_id: {"readable": readable_path(work_id, sources, base) is not None,
                      "rag_available": work_id in indexed}
            for work_id in work_ids}
