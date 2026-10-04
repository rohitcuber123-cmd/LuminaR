"""
AstraLib -- MetadataStore

Persistent, read-only DuckDB connection for production metadata lookups.

Key design decisions
--------------------
- Connection is opened ONCE at construction and kept alive.
- Database is opened read_only=True (no write-lock, no WAL overhead).
- Parameterized SQL -- no string concatenation of work IDs.
- Returns a dict keyed by work_id -- no Pandas, no full-table load.
- Only the eight columns required by the search UI are fetched.
- Parquet is never touched during a production lookup.

Usage
-----
    store = MetadataStore("D:/SDC/LibraryLLM/datasets/ai/metadata/book_metadata.duckdb")
    results = store.get_by_work_ids(["OL123W", "OL456W"])
    store.close()

    # or as a context manager
    with MetadataStore(db_path) as store:
        results = store.get_by_work_ids(work_ids)
"""

import os
import duckdb


# ======================================================================
# CONSTANTS
# ======================================================================

_COLUMNS = (
    "work_id",
    "title",
    "authors",
    "subjects",
    "description",
    "average_rating",
    "rating_count",
    "reading_log_count",
)

_SELECT = ", ".join(_COLUMNS)

_TEXT_COLUMNS = (
    "work_id",
    "title",
    "authors",
    "subjects",
    "description",
)

_TEXT_SELECT = ", ".join(_TEXT_COLUMNS)

# Lightweight fields used by the first-stage cross-encoder reranking.
# Description is intentionally excluded because it can be large and
# expensive to decompress/fetch for 50 candidates.
_RERANK_COLUMNS = (
    "work_id",
    "title",
    "authors",
    "subjects",
)

_RERANK_SELECT = ", ".join(_RERANK_COLUMNS)


# ======================================================================
# MetadataStore
# ======================================================================

class MetadataStore:
    """
    Persistent read-only DuckDB metadata store.

    Opens the connection once; reuses it for every lookup.
    Thread-safety: DuckDB connections are NOT thread-safe.
    For a multi-threaded API, create one MetadataStore per thread/worker.
    """

    def __init__(self, db_path: str):
        """
        Open the metadata database.

        Parameters
        ----------
        db_path : str
            Absolute path to book_metadata.duckdb.

        Raises
        ------
        FileNotFoundError
            If the database file does not exist.
        """
        if not os.path.exists(db_path):
            raise FileNotFoundError(
                f"Production metadata database not found: {db_path}\n"
                f"Run data_pipeline/ai/metadata/build_metadata_db.py first."
            )

        self._db_path = db_path
        self._conn = duckdb.connect(database=db_path, read_only=True)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_by_work_ids(self, work_ids: list) -> dict:
        """
        Fetch metadata for a list of work IDs.

        Parameters
        ----------
        work_ids : list[str]
            Work IDs to look up (e.g. ["OL123W", "OL456W"]).
            Empty list returns {}.

        Returns
        -------
        dict
            Mapping of work_id -> {field: value, ...}.
            Work IDs with no matching row are absent from the result.

        Example
        -------
        {
            "OL123W": {
                "work_id": "OL123W",
                "title": "Harry Potter",
                "authors": "J.K. Rowling",
                "subjects": "Fantasy",
                "description": "...",
                "average_rating": 4.5,
                "rating_count": 12000,
                "reading_log_count": 50000,
            }
        }
        """
        if not work_ids:
            return {}

        # Build parameterized placeholder list: (?, ?, ...)
        placeholders = ", ".join(["?"] * len(work_ids))

        sql = (
            f"SELECT {_SELECT} "
            f"FROM books "
            f"WHERE work_id IN ({placeholders})"
        )

        cursor = self._conn.execute(sql, list(work_ids))
        rows = cursor.fetchall()

        return {
            str(row[0]): dict(zip(_COLUMNS, row))
            for row in rows
        }

    def get_rerank_text_by_work_ids(self, work_ids: list) -> dict:
        """
        Fetch lightweight text fields for the Top-50 cross-encoder stage.

        Deliberately excludes description. Descriptions can be large and
        can make both DuckDB retrieval and cross-encoder tokenization much
        more expensive. Full metadata is fetched only for the final Top-K.
        """
        if not work_ids:
            return {}

        placeholders = ", ".join(["?"] * len(work_ids))

        sql = (
            f"SELECT {_RERANK_SELECT} "
            f"FROM books "
            f"WHERE work_id IN ({placeholders})"
        )

        cursor = self._conn.execute(sql, list(work_ids))
        rows = cursor.fetchall()

        return {
            str(row[0]): dict(zip(_RERANK_COLUMNS, row))
            for row in rows
        }

    def get_text_by_work_ids(self, work_ids: list) -> dict:
        """
        Fetch only the text metadata needed for reranking.
        """
        if not work_ids:
            return {}

        placeholders = ", ".join(["?"] * len(work_ids))

        sql = (
            f"SELECT {_TEXT_SELECT} "
            f"FROM books "
            f"WHERE work_id IN ({placeholders})"
        )

        cursor = self._conn.execute(sql, list(work_ids))
        rows = cursor.fetchall()

        return {
            str(row[0]): dict(zip(_TEXT_COLUMNS, row))
            for row in rows
        }

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def close(self):
        """Close the DuckDB connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self):
        status = "open" if self._conn is not None else "closed"
        return f"MetadataStore(db={self._db_path!r}, status={status!r})"
