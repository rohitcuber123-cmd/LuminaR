"""Optional read-only ISBN mapping; safe to import in a zero-write dry run."""
import os
from pathlib import Path


def isbn_candidates(isbns):
    numbers = sorted(set(v for v in isbns if v))
    path = Path(os.getenv('ISBN_LOOKUP_DB', str(Path(__file__).resolve().parents[2] / 'datasets/ai/mappings/isbn_lookup.duckdb')))
    if not numbers or not path.is_file():
        return {}
    try:
        import duckdb
    except ImportError:
        return {}
    try:
        with duckdb.connect(str(path), read_only=True) as connection:
            rows = []
            for start in range(0, len(numbers), 500):
                chunk = numbers[start:start + 500]
                rows.extend(connection.execute('SELECT isbn, work_id FROM isbn_lookup WHERE isbn IN (' + ','.join('?' for _ in chunk) + ')', chunk).fetchall())
    except (OSError, duckdb.Error):
        return {}
    matches = {}
    for isbn, work_id in rows:
        matches.setdefault(isbn, set()).add(work_id)
    return {isbn: next(iter(ids)) for isbn, ids in matches.items() if len(ids) == 1}
