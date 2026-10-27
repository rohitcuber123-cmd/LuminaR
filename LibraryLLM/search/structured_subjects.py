"""Existing graph feature index as a bounded shortcut for rare exact facets."""
from pathlib import Path
import sqlite3
from time import perf_counter

def candidate_ids(subject,limit=1000,path=None):
    from knowledge_graph.core import DEFAULT_GRAPH,canonical
    started = perf_counter()
    try:
        with sqlite3.connect(Path(path or DEFAULT_GRAPH).resolve().as_uri()+'?mode=ro',uri=True,timeout=.1) as graph:
            graph.set_progress_handler(lambda:int(perf_counter()-started>1.5),1000)
            # Existing accepted index edges(kind,term,book_id); no graph expansion.
            ids = [r[0] for r in graph.execute(
                "SELECT b.work_id FROM books b WHERE b.id IN (SELECT book_id FROM edges WHERE kind='subject' AND term=? ORDER BY book_id LIMIT ?) ORDER BY b.id",
                (canonical(subject),min(1000,limit)))]
            return ids or None
    except (sqlite3.Error,OSError,ValueError):
        return None  # Preserve the existing bounded canonical Mongo fallback.
