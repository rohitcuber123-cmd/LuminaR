from pathlib import Path
import json
import time
from collections import OrderedDict

import faiss
import numpy as np
import torch
from sentence_transformers import SentenceTransformer


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

# ------------------------------------------------------------
# GLOBAL BOOK RAG
# ------------------------------------------------------------

INDEX_PATH = BASE_DIR / "book_index" / "rag.index"
METADATA_PATH = BASE_DIR / "book_index" / "rag_metadata.json"

# ------------------------------------------------------------
# PER-BOOK RAG
# ------------------------------------------------------------

BOOK_INDEX_DIR = (
    BASE_DIR /
    "book_index" /
    "books"
)

# ------------------------------------------------------------
# BOOK CHUNKS
# ------------------------------------------------------------

CHUNKS_DIR = (
    BASE_DIR /
    "book_chunks"
)

# ------------------------------------------------------------
# UPLOADED DOCUMENT INDEX (separate from books)
# ------------------------------------------------------------

DOC_INDEX_DIR = BASE_DIR / "index"
DOC_INDEX_PATH = DOC_INDEX_DIR / "rag.index"
DOC_METADATA_PATH = DOC_INDEX_DIR / "rag_metadata.json"
DOC_CHUNKS_DIR = BASE_DIR / "chunks"


# ============================================================
# MODEL
# ============================================================

MODEL_NAME = (
    "sentence-transformers/"
    "all-MiniLM-L6-v2"
)

DEVICE = (
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


# ============================================================
# CACHE SETTINGS
# ============================================================

# Maximum number of book FAISS indexes kept in RAM.
#
# Since we currently have only 17 books, this is more than
# enough for development while still preventing unlimited
# memory usage if the corpus grows later.
#
MAX_CACHED_BOOKS = 5


# ============================================================
# RAG RETRIEVER
# ============================================================

class RAGRetriever:

    def __init__(self):

        print()
        print("=" * 70)
        print("LUMINAR BOOK RAG RETRIEVER")
        print("=" * 70)

        print(
            f"Device : {DEVICE}"
        )

        # ----------------------------------------------------
        # GLOBAL INDEX
        # ----------------------------------------------------

        self._load_global_index()

        # ----------------------------------------------------
        # GLOBAL METADATA
        # ----------------------------------------------------

        self._load_global_metadata()

        # ----------------------------------------------------
        # BOOK CHUNK TEXT
        # ----------------------------------------------------

        self._load_chunk_texts()

        # ----------------------------------------------------
        # BOOK INDEX CACHE
        # ----------------------------------------------------

        self.book_index_cache = OrderedDict()

        # ----------------------------------------------------
        # UPLOADED DOCUMENT INDEX
        # ----------------------------------------------------

        self._load_document_index()
        self._load_document_metadata()
        self._load_document_chunk_texts()

        # ----------------------------------------------------
        # MODEL
        # ----------------------------------------------------

        print()
        print("Loading MiniLM...")

        start = time.perf_counter()

        self.model = SentenceTransformer(
            MODEL_NAME,
            device=DEVICE
        )

        model_time = (
            time.perf_counter()
            - start
        )

        print(
            f"Model load : "
            f"{model_time * 1000:.2f} ms"
        )

        # ----------------------------------------------------
        # WARM UP
        # ----------------------------------------------------

        print()
        print("Warming MiniLM...")

        self.model.encode(
            ["warm up"],
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        print(
            "MiniLM warm-up complete."
        )

        print()
        print("Book RAG retriever ready.")

    # ========================================================
    # LOAD GLOBAL INDEX
    # ========================================================

    def _load_global_index(self):

        print()
        print(
            "Loading global book RAG FAISS index..."
        )

        start = time.perf_counter()

        if not INDEX_PATH.exists():

            raise FileNotFoundError(
                "Global book RAG FAISS index "
                f"not found:\n{INDEX_PATH}"
            )

        self.index = faiss.read_index(
            str(INDEX_PATH)
        )

        elapsed = (
            time.perf_counter()
            - start
        )

        print(
            f"Vectors    : "
            f"{self.index.ntotal:,}"
        )

        print(
            f"Dimension  : "
            f"{self.index.d}"
        )

        print(
            f"Index load : "
            f"{elapsed * 1000:.2f} ms"
        )

    # ========================================================
    # LOAD GLOBAL METADATA
    # ========================================================

    def _load_global_metadata(self):

        print()
        print(
            "Loading global book RAG metadata..."
        )

        if not METADATA_PATH.exists():

            raise FileNotFoundError(
                "Global book RAG metadata "
                f"not found:\n{METADATA_PATH}"
            )

        with open(
            METADATA_PATH,
            "r",
            encoding="utf-8"
        ) as f:

            self.metadata = json.load(f)

        print(
            f"Metadata rows : "
            f"{len(self.metadata):,}"
        )

        # ----------------------------------------------------
        # Safety check
        # ----------------------------------------------------

        if (
            len(self.metadata)
            != self.index.ntotal
        ):

            raise RuntimeError(
                "FAISS index and metadata "
                "are out of sync.\n"
                f"Index vectors = "
                f"{self.index.ntotal}\n"
                f"Metadata rows = "
                f"{len(self.metadata)}"
            )

        # ----------------------------------------------------
        # Determine available work IDs
        # ----------------------------------------------------

        self.work_ids = set()

        for metadata in self.metadata:

            work_id = metadata.get(
                "work_id"
            )

            if not work_id:

                work_id = metadata.get(
                    "document_id"
                )

            if work_id:

                self.work_ids.add(
                    work_id
                )

        print(
            f"Books indexed : "
            f"{len(self.work_ids)}"
        )

    # ========================================================
    # LOAD CHUNK TEXT
    # ========================================================

    def _load_chunk_texts(self):

        print()
        print(
            "Loading book chunk text..."
        )

        self.chunk_texts = {}

        if not CHUNKS_DIR.exists():

            raise FileNotFoundError(
                "Book chunks directory "
                f"not found:\n{CHUNKS_DIR}"
            )

        chunk_files = sorted(
            CHUNKS_DIR.glob("*.json")
        )

        print(
            f"Chunk files : "
            f"{len(chunk_files)}"
        )

        for path in chunk_files:

            with open(
                path,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

            if isinstance(data, list):
                chunks = data
            else:
                chunks = data.get(
                    "chunks",
                    []
                )

            for chunk in chunks:

                chunk_id = chunk.get(
                    "chunk_id"
                )

                if not chunk_id:
                    continue

                self.chunk_texts[
                    chunk_id
                ] = chunk.get(
                    "text",
                    ""
                )

        print(
            f"Chunk texts : "
            f"{len(self.chunk_texts):,}"
        )

    # ========================================================
    # LOAD ONE BOOK INDEX
    # ========================================================

    def _load_book_index(
        self,
        work_id
    ):

        # ----------------------------------------------------
        # Already cached?
        # ----------------------------------------------------

        if work_id in self.book_index_cache:

            cached = (
                self.book_index_cache.pop(
                    work_id
                )
            )

            # Move to end = recently used
            self.book_index_cache[
                work_id
            ] = cached

            return cached

        # ----------------------------------------------------
        # Paths
        # ----------------------------------------------------

        index_path = (
            BOOK_INDEX_DIR /
            f"{work_id}.index"
        )

        metadata_path = (
            BOOK_INDEX_DIR /
            f"{work_id}_metadata.json"
        )

        # ----------------------------------------------------
        # Validate files
        # ----------------------------------------------------

        if not index_path.exists():

            raise FileNotFoundError(
                "Per-book FAISS index not found "
                f"for work_id={work_id}\n"
                f"Expected:\n{index_path}"
            )

        if not metadata_path.exists():

            raise FileNotFoundError(
                "Per-book metadata not found "
                f"for work_id={work_id}\n"
                f"Expected:\n{metadata_path}"
            )

        print()
        print(
            f"[Book RAG] Loading index: "
            f"{work_id}"
        )

        start = time.perf_counter()

        book_index = faiss.read_index(
            str(index_path)
        )

        with open(
            metadata_path,
            "r",
            encoding="utf-8"
        ) as f:

            book_metadata = json.load(f)

        elapsed = (
            time.perf_counter()
            - start
        )

        # ----------------------------------------------------
        # Safety check
        # ----------------------------------------------------

        if (
            len(book_metadata)
            != book_index.ntotal
        ):

            raise RuntimeError(
                "Book FAISS index and "
                "metadata are out of sync.\n"
                f"Work ID = {work_id}\n"
                f"Index vectors = "
                f"{book_index.ntotal}\n"
                f"Metadata rows = "
                f"{len(book_metadata)}"
            )

        cached_data = {
            "index": book_index,
            "metadata": book_metadata
        }

        # ----------------------------------------------------
        # Add to cache
        # ----------------------------------------------------

        self.book_index_cache[
            work_id
        ] = cached_data

        # ----------------------------------------------------
        # LRU eviction
        # ----------------------------------------------------

        while (
            len(self.book_index_cache)
            > MAX_CACHED_BOOKS
        ):

            removed_work_id, _ = (
                self.book_index_cache.popitem(
                    last=False
                )
            )

            print(
                f"[Book RAG] Cache evicted: "
                f"{removed_work_id}"
            )

        print(
            f"[Book RAG] Loaded "
            f"{book_index.ntotal:,} vectors "
            f"in {elapsed * 1000:.2f} ms"
        )

        print(
            f"[Book RAG] Cache size: "
            f"{len(self.book_index_cache)}/"
            f"{MAX_CACHED_BOOKS}"
        )

        return cached_data

    # ========================================================
    # HOT RELOAD
    # ========================================================

    def reload(self):

        print()
        print("=" * 70)
        print("RELOADING LUMINAR BOOK RAG")
        print("=" * 70)

        start = time.perf_counter()

        self._load_global_index()

        self._load_global_metadata()

        self._load_chunk_texts()

        # ----------------------------------------------------
        # Clear cached per-book indexes
        # ----------------------------------------------------

        self.book_index_cache.clear()

        # ----------------------------------------------------
        # Reload uploaded document index
        # ----------------------------------------------------

        self._load_document_index()
        self._load_document_metadata()
        self._load_document_chunk_texts()

        elapsed = (
            time.perf_counter()
            - start
        )

        print()
        print(
            f"Retriever reload complete "
            f"in {elapsed * 1000:.2f} ms"
        )

        print(
            f"Global vectors : "
            f"{self.index.ntotal:,}"
        )

        print(
            f"Book chunks    : "
            f"{len(self.chunk_texts):,}"
        )

        doc_vectors = (
            self.doc_index.ntotal
            if self.doc_index
            else 0
        )

        print(
            f"Doc vectors    : "
            f"{doc_vectors:,}"
        )

        print(
            f"Doc chunks     : "
            f"{len(self.doc_chunk_texts):,}"
        )

        print(
            "Per-book cache cleared."
        )

        print("=" * 70)

    # ========================================================
    # EMBED QUERY
    # ========================================================

    def _embed_query(
        self,
        query
    ):

        start = time.perf_counter()

        vector = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        vector = np.asarray(
            vector,
            dtype="float32"
        )

        elapsed = (
            time.perf_counter()
            - start
        )

        return vector, elapsed

    # ========================================================
    # SEARCH
    # ========================================================

    def search(
        self,
        query,
        top_k=5,
        document_id=None,
        work_id=None
    ):

        # ----------------------------------------------------
        # Normalize query
        # ----------------------------------------------------

        if query is None:

            query = ""

        query = str(
            query
        ).strip()

        # ----------------------------------------------------
        # Backwards compatibility
        # ----------------------------------------------------

        if (
            not work_id
            and document_id
        ):

            work_id = document_id

        # ----------------------------------------------------
        # Normalize top_k
        # ----------------------------------------------------

        try:

            top_k = int(
                top_k
            )

        except (
            TypeError,
            ValueError
        ):

            top_k = 5

        if top_k < 1:

            top_k = 1

        # ----------------------------------------------------
        # Empty query
        # ----------------------------------------------------

        if not query:

            return {
                "query": query,
                "top_k": top_k,
                "document_filter":
                    document_id,
                "work_id":
                    work_id,
                "search_mode":
                    "none",
                "timing_ms": {
                    "embedding": 0,
                    "faiss": 0,
                    "total": 0
                },
                "results": []
            }

        # ----------------------------------------------------
        # Embed query
        # ----------------------------------------------------

        query_vector, embedding_elapsed = (
            self._embed_query(
                query
            )
        )

        # ====================================================
        # UPLOADED DOCUMENT SEARCH
        #
        # If document_id is given and it matches an uploaded
        # document (not a book), search the document index.
        # ====================================================

        if document_id and self._is_uploaded_document(
            document_id
        ):

            return self._search_documents(
                query=query,
                query_vector=query_vector,
                top_k=top_k,
                document_id=document_id,
                embedding_elapsed=
                    embedding_elapsed
            )

        # ====================================================
        # BOOK-SPECIFIC SEARCH
        # ====================================================

        if work_id:

            return self._search_book(
                query=query,
                query_vector=query_vector,
                top_k=top_k,
                work_id=work_id,
                embedding_elapsed=
                    embedding_elapsed,
                document_id=document_id
            )

        # ====================================================
        # GLOBAL SEARCH
        # ====================================================

        return self._search_global(
            query=query,
            query_vector=query_vector,
            top_k=top_k,
            embedding_elapsed=
                embedding_elapsed,
            document_id=document_id
        )

    # ========================================================
    # SEARCH ONE BOOK
    # ========================================================

    def _search_book(
        self,
        query,
        query_vector,
        top_k,
        work_id,
        embedding_elapsed,
        document_id
    ):

        # ----------------------------------------------------
        # Load only this book's index
        # ----------------------------------------------------

        start = time.perf_counter()

        try:

            book_data = (
                self._load_book_index(
                    work_id
                )
            )

        except FileNotFoundError:

            search_elapsed = (
                time.perf_counter()
                - start
            )

            return {
                "query": query,
                "top_k": top_k,
                "document_filter":
                    document_id,
                "work_id":
                    work_id,
                "search_mode":
                    "book",
                "timing_ms": {
                    "embedding":
                        round(
                            embedding_elapsed
                            * 1000,
                            2
                        ),
                    "faiss":
                        round(
                            search_elapsed
                            * 1000,
                            2
                        ),
                    "total":
                        round(
                            (
                                embedding_elapsed
                                + search_elapsed
                            ) * 1000,
                            2
                        )
                },
                "results": []
            }

        book_index = book_data[
            "index"
        ]

        book_metadata = book_data[
            "metadata"
        ]

        # ----------------------------------------------------
        # Search ONLY this book
        # ----------------------------------------------------

        search_k = min(
            top_k,
            book_index.ntotal
        )

        scores, indices = (
            book_index.search(
                query_vector,
                search_k
            )
        )

        search_elapsed = (
            time.perf_counter()
            - start
        )

        # ----------------------------------------------------
        # Build results
        # ----------------------------------------------------

        results = []

        for score, local_index in zip(
            scores[0],
            indices[0]
        ):

            if local_index < 0:

                continue

            local_index = int(
                local_index
            )

            if (
                local_index
                >= len(book_metadata)
            ):

                continue

            metadata = book_metadata[
                local_index
            ]

            chunk_id = metadata.get(
                "chunk_id"
            )

            # ------------------------------------------------
            # Text is already present in per-book metadata.
            #
            # Fall back to chunk_texts for compatibility.
            # ------------------------------------------------

            text = metadata.get(
                "text",
                ""
            )

            if not text:

                text = (
                    self.chunk_texts.get(
                        chunk_id,
                        ""
                    )
                )

            if not text:

                continue

            results.append(
                {
                    "rank":
                        len(results) + 1,

                    "score":
                        float(score),

                    "chunk_id":
                        chunk_id,

                    "document_id":
                        metadata.get(
                            "document_id"
                        ),

                    "work_id":
                        metadata.get(
                            "work_id",
                            work_id
                        ),

                    "filename":
                        metadata.get(
                            "filename"
                        ),

                    "page":
                        metadata.get(
                            "page"
                        ),

                    "title":
                        metadata.get(
                            "title"
                        ),

                    "author":
                        metadata.get(
                            "author"
                        ),

                    "chapter":
                        metadata.get(
                            "chapter"
                        ),

                    "chunk_index":
                        metadata.get(
                            "chunk_index"
                        ),

                    "text":
                        text
                }
            )

        total_elapsed = (
            embedding_elapsed
            + search_elapsed
        )

        return {
            "query":
                query,

            "top_k":
                top_k,

            "document_filter":
                document_id,

            "work_id":
                work_id,

            "search_mode":
                "book",

            "timing_ms": {
                "embedding":
                    round(
                        embedding_elapsed
                        * 1000,
                        2
                    ),

                "faiss":
                    round(
                        search_elapsed
                        * 1000,
                        2
                    ),

                "total":
                    round(
                        total_elapsed
                        * 1000,
                        2
                    )
            },

            "results":
                results
        }

    # ========================================================
    # GLOBAL SEARCH
    # ========================================================

    def _search_global(
        self,
        query,
        query_vector,
        top_k,
        embedding_elapsed,
        document_id
    ):

        start = time.perf_counter()

        search_k = min(
            top_k,
            self.index.ntotal
        )

        scores, indices = (
            self.index.search(
                query_vector,
                search_k
            )
        )

        search_elapsed = (
            time.perf_counter()
            - start
        )

        results = []

        # ----------------------------------------------------
        # ADD BOOK RESULTS
        # ----------------------------------------------------
        for score, index_id in zip(
            scores[0],
            indices[0]
        ):

            if index_id < 0:
                continue

            index_id = int(index_id)

            if index_id >= len(self.metadata):
                continue

            metadata = self.metadata[index_id]
            chunk_id = metadata.get("chunk_id")
            text = self.chunk_texts.get(chunk_id, "")

            if not text:
                continue

            results.append(
                {
                    "score": float(score),
                    "chunk_id": chunk_id,
                    "document_id": metadata.get("document_id"),
                    "work_id": metadata.get("work_id", metadata.get("document_id")),
                    "filename": metadata.get("filename"),
                    "page": metadata.get("page"),
                    "title": metadata.get("title"),
                    "author": metadata.get("author"),
                    "chapter": metadata.get("chapter"),
                    "chunk_index": metadata.get("chunk_index"),
                    "text": text
                }
            )

        # ----------------------------------------------------
        # ADD UPLOADED DOCUMENT RESULTS
        # ----------------------------------------------------
        if self.doc_index is not None and self.doc_index.ntotal > 0:

            doc_start = time.perf_counter()

            doc_search_k = min(
                top_k,
                self.doc_index.ntotal
            )

            doc_scores, doc_indices = (
                self.doc_index.search(
                    query_vector,
                    doc_search_k
                )
            )

            search_elapsed += (
                time.perf_counter()
                - doc_start
            )

            for score, index_id in zip(
                doc_scores[0],
                doc_indices[0]
            ):

                if index_id < 0:
                    continue

                index_id = int(index_id)

                if index_id >= len(self.doc_metadata):
                    continue

                metadata = self.doc_metadata[index_id]
                chunk_id = metadata.get("chunk_id")
                text = self.doc_chunk_texts.get(chunk_id, "")

                if not text:
                    continue

                results.append(
                    {
                        "score": float(score),
                        "chunk_id": chunk_id,
                        "document_id": metadata.get("document_id"),
                        "work_id": metadata.get("document_id"),
                        "filename": metadata.get("filename"),
                        "page": metadata.get("page"),
                        "title": None,
                        "author": None,
                        "chapter": None,
                        "chunk_index": None,
                        "text": text
                    }
                )

        # ----------------------------------------------------
        # MERGE AND RANK
        # ----------------------------------------------------
        results.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        results = results[:top_k]

        for i, res in enumerate(results):
            res["rank"] = i + 1

        total_elapsed = (
            embedding_elapsed
            + search_elapsed
        )

        return {
            "query":
                query,

            "top_k":
                top_k,

            "document_filter":
                document_id,

            "work_id":
                None,

            "search_mode":
                "global",

            "timing_ms": {
                "embedding":
                    round(
                        embedding_elapsed
                        * 1000,
                        2
                    ),

                "faiss":
                    round(
                        search_elapsed
                        * 1000,
                        2
                    ),

                "total":
                    round(
                        total_elapsed
                        * 1000,
                        2
                    )
            },

            "results":
                results
        }

    # ========================================================
    # UPLOADED DOCUMENT INDEX — LOADING
    # ========================================================

    def _load_document_index(self):

        self.doc_index = None

        if not DOC_INDEX_PATH.exists():

            print(
                "No uploaded-document FAISS index found "
                "(this is normal on first run)."
            )

            return

        print()
        print(
            "Loading uploaded-document FAISS index..."
        )

        start = time.perf_counter()

        self.doc_index = faiss.read_index(
            str(DOC_INDEX_PATH)
        )

        elapsed = (
            time.perf_counter()
            - start
        )

        print(
            f"Doc vectors : "
            f"{self.doc_index.ntotal:,}"
        )

        print(
            f"Doc index load : "
            f"{elapsed * 1000:.2f} ms"
        )

    def _load_document_metadata(self):

        self.doc_metadata = []
        self.doc_ids = set()

        if not DOC_METADATA_PATH.exists():

            return

        print(
            "Loading uploaded-document metadata..."
        )

        with open(
            DOC_METADATA_PATH,
            "r",
            encoding="utf-8"
        ) as f:

            self.doc_metadata = json.load(f)

        # Build set of known uploaded document IDs

        for item in self.doc_metadata:

            doc_id = item.get(
                "document_id"
            )

            if doc_id:

                self.doc_ids.add(
                    doc_id
                )

        print(
            f"Doc metadata rows : "
            f"{len(self.doc_metadata):,}"
        )

        print(
            f"Uploaded documents : "
            f"{len(self.doc_ids)}"
        )

        # Safety check

        if (
            self.doc_index
            and len(self.doc_metadata)
            != self.doc_index.ntotal
        ):

            print(
                f"WARNING: Doc FAISS index and "
                f"metadata are out of sync.\n"
                f"Index vectors = "
                f"{self.doc_index.ntotal}\n"
                f"Metadata rows = "
                f"{len(self.doc_metadata)}"
            )

    def _load_document_chunk_texts(self):

        self.doc_chunk_texts = {}

        if not DOC_CHUNKS_DIR.exists():

            return

        print(
            "Loading uploaded-document chunk text..."
        )

        chunk_files = sorted(
            DOC_CHUNKS_DIR.glob("*.json")
        )

        for path in chunk_files:

            with open(
                path,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

            if isinstance(data, list):
                chunks = data
            else:
                chunks = data.get(
                    "chunks",
                    []
                )

            for chunk in chunks:

                chunk_id = chunk.get(
                    "chunk_id"
                )

                if not chunk_id:
                    continue

                self.doc_chunk_texts[
                    chunk_id
                ] = chunk.get(
                    "text",
                    ""
                )

        print(
            f"Doc chunk texts : "
            f"{len(self.doc_chunk_texts):,}"
        )

    # ========================================================
    # IS UPLOADED DOCUMENT?
    # ========================================================

    def _is_uploaded_document(
        self,
        document_id
    ):
        """Check if document_id is a known uploaded document."""

        return (
            document_id in self.doc_ids
        )

    # ========================================================
    # SEARCH UPLOADED DOCUMENTS
    # ========================================================

    def _search_documents(
        self,
        query,
        query_vector,
        top_k,
        document_id,
        embedding_elapsed
    ):
        """Search uploaded-document index with document_id filtering."""

        if (
            self.doc_index is None
            or self.doc_index.ntotal == 0
        ):

            return {
                "query": query,
                "top_k": top_k,
                "document_filter":
                    document_id,
                "work_id":
                    document_id,
                "search_mode":
                    "document",
                "timing_ms": {
                    "embedding":
                        round(
                            embedding_elapsed
                            * 1000,
                            2
                        ),
                    "faiss": 0,
                    "total":
                        round(
                            embedding_elapsed
                            * 1000,
                            2
                        )
                },
                "results": []
            }

        start = time.perf_counter()

        # Search more candidates than needed to allow
        # document_id filtering.

        search_k = min(
            top_k * 5,
            self.doc_index.ntotal
        )

        scores, indices = (
            self.doc_index.search(
                query_vector,
                search_k
            )
        )

        search_elapsed = (
            time.perf_counter()
            - start
        )

        results = []

        for score, index_id in zip(
            scores[0],
            indices[0]
        ):

            if index_id < 0:
                continue

            index_id = int(index_id)

            if (
                index_id
                >= len(self.doc_metadata)
            ):
                continue

            metadata = self.doc_metadata[
                index_id
            ]

            # Document-ID filtering

            if (
                document_id
                and metadata.get(
                    "document_id"
                ) != document_id
            ):
                continue

            chunk_id = metadata.get(
                "chunk_id"
            )

            text = (
                self.doc_chunk_texts.get(
                    chunk_id,
                    ""
                )
            )

            if not text:
                continue

            results.append(
                {
                    "rank":
                        len(results) + 1,

                    "score":
                        float(score),

                    "chunk_id":
                        chunk_id,

                    "document_id":
                        metadata.get(
                            "document_id"
                        ),

                    "work_id":
                        metadata.get(
                            "document_id"
                        ),

                    "filename":
                        metadata.get(
                            "filename"
                        ),

                    "page":
                        metadata.get(
                            "page"
                        ),

                    "title":
                        None,

                    "author":
                        None,

                    "chapter":
                        None,

                    "chunk_index":
                        None,

                    "text":
                        text
                }
            )

            if len(results) >= top_k:
                break

        total_elapsed = (
            embedding_elapsed
            + search_elapsed
        )

        return {
            "query":
                query,

            "top_k":
                top_k,

            "document_filter":
                document_id,

            "work_id":
                document_id,

            "search_mode":
                "document",

            "timing_ms": {
                "embedding":
                    round(
                        embedding_elapsed
                        * 1000,
                        2
                    ),

                "faiss":
                    round(
                        search_elapsed
                        * 1000,
                        2
                    ),

                "total":
                    round(
                        total_elapsed
                        * 1000,
                        2
                    )
            },

            "results":
                results
        }


# ============================================================
# CLI TEST
# ============================================================

def main():

    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "LuminaR optimized "
            "book-centric RAG retriever"
        )
    )

    parser.add_argument(
        "--query",
        required=True
    )

    parser.add_argument(
        "--top_k",
        type=int,
        default=5
    )

    parser.add_argument(
        "--document",
        default=None,
        help=(
            "Optional document_id. "
            "For backwards compatibility "
            "this is treated as work_id."
        )
    )

    parser.add_argument(
        "--work_id",
        default=None,
        help=(
            "Open Library Work ID for "
            "book-specific retrieval."
        )
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # Initialize
    # --------------------------------------------------------

    retriever = RAGRetriever()

    # --------------------------------------------------------
    # Search
    # --------------------------------------------------------

    result = retriever.search(
        query=args.query,
        top_k=args.top_k,
        document_id=args.document,
        work_id=args.work_id
    )

    # --------------------------------------------------------
    # Print summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("BOOK RAG RETRIEVAL RESULTS")
    print("=" * 70)

    print()
    print(
        f"Query : {result['query']}"
    )

    print(
        f"Top K : {result['top_k']}"
    )

    print(
        f"Mode  : {result['search_mode']}"
    )

    if result.get("work_id"):

        print(
            f"Work ID : "
            f"{result['work_id']}"
        )

    print()
    print(
        f"Embedding : "
        f"{result['timing_ms']['embedding']} ms"
    )

    print(
        f"FAISS     : "
        f"{result['timing_ms']['faiss']} ms"
    )

    print(
        f"Total     : "
        f"{result['timing_ms']['total']} ms"
    )

    print()
    print(
        f"Results   : "
        f"{len(result['results'])}"
    )

    # --------------------------------------------------------
    # Results
    # --------------------------------------------------------

    for item in result["results"]:

        print()
        print("-" * 70)

        print(
            f"Rank       : "
            f"{item['rank']}"
        )

        print(
            f"Score      : "
            f"{item['score']:.4f}"
        )

        print(
            f"Title      : "
            f"{item.get('title')}"
        )

        print(
            f"Author     : "
            f"{item.get('author')}"
        )

        print(
            f"Chapter    : "
            f"{item.get('chapter')}"
        )

        print(
            f"Document   : "
            f"{item.get('filename')}"
        )

        print(
            f"Work ID    : "
            f"{item.get('work_id')}"
        )

        print(
            f"Chunk ID   : "
            f"{item.get('chunk_id')}"
        )

        print()

        print(
            item["text"]
        )

    print()
    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()