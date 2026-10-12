from pathlib import Path
import json
import time

import numpy as np
import faiss
import torch

from sentence_transformers import SentenceTransformer


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

# New book-centric chunk directory
CHUNKS_DIR = BASE_DIR / "book_chunks"

# Separate from your existing/general RAG
EMBEDDINGS_DIR = BASE_DIR / "book_embeddings"
INDEX_DIR = BASE_DIR / "book_index"

# Per-book indexes
BOOK_INDEX_DIR = INDEX_DIR / "books"

# Create directories
EMBEDDINGS_DIR.mkdir(
    parents=True,
    exist_ok=True
)

INDEX_DIR.mkdir(
    parents=True,
    exist_ok=True
)

BOOK_INDEX_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# MODEL
# ============================================================

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

DEVICE = (
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)


# ============================================================
# LOAD CHUNKS
# ============================================================

def load_chunks():

    all_chunks = []

    files = sorted(
        CHUNKS_DIR.glob("*.json")
    )

    print()
    print("=" * 70)
    print("LOADING BOOK RAG CHUNKS")
    print("=" * 70)

    print(
        f"Chunk files found : {len(files)}"
    )

    if not files:

        raise FileNotFoundError(
            f"No chunk files found in:\n{CHUNKS_DIR}"
        )

    for path in files:

        print(
            f"Loading: {path.name}"
        )

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        # Each book_ingest output is:
        #
        # {
        #     "document_id": "...",
        #     "work_id": "...",
        #     "title": "...",
        #     "author": "...",
        #     "chunks": [...]
        # }

        if not isinstance(data, dict):

            raise ValueError(
                f"{path.name} is not a valid "
                f"book chunk object."
            )

        chunks = data.get(
            "chunks",
            []
        )

        if not isinstance(chunks, list):

            raise ValueError(
                f"{path.name} has an invalid "
                f"'chunks' field."
            )

        all_chunks.extend(
            chunks
        )

        print(
            f"  Chunks: {len(chunks)}"
        )

    return all_chunks


# ============================================================
# VALIDATE CHUNKS
# ============================================================

def validate_chunks(chunks):

    print()
    print("=" * 70)
    print("VALIDATING BOOK CHUNKS")
    print("=" * 70)

    required_fields = [
        "chunk_id",
        "document_id",
        "filename",
        "text"
    ]

    errors = 0

    for index, chunk in enumerate(
        chunks
    ):

        for field in required_fields:

            if field not in chunk:

                print(
                    f"ERROR: chunk {index} "
                    f"is missing '{field}'"
                )

                errors += 1

                break

        if not chunk.get(
            "text",
            ""
        ).strip():

            print(
                f"ERROR: chunk {index} "
                f"has empty text"
            )

            errors += 1

    if errors:

        raise ValueError(
            f"Chunk validation failed "
            f"with {errors} error(s)."
        )

    # --------------------------------------------------------
    # Check duplicate IDs
    # --------------------------------------------------------

    chunk_ids = [
        chunk["chunk_id"]
        for chunk in chunks
    ]

    duplicate_ids = (
        len(chunk_ids)
        - len(set(chunk_ids))
    )

    if duplicate_ids:

        raise ValueError(
            f"Found {duplicate_ids} "
            f"duplicate chunk IDs."
        )

    # --------------------------------------------------------
    # Check work IDs
    # --------------------------------------------------------

    work_ids = set()

    for chunk in chunks:

        work_id = chunk.get(
            "work_id",
            chunk.get("document_id")
        )

        if work_id:

            work_ids.add(
                work_id
            )

    print(
        f"Valid chunks : {len(chunks):,}"
    )

    print(
        f"Unique books : {len(work_ids)}"
    )

    print(
        "Validation successful."
    )


# ============================================================
# BUILD PER-BOOK INDEXES
# ============================================================

def build_book_indexes(
    chunks,
    embeddings
):

    print()
    print("=" * 70)
    print("BUILDING PER-BOOK FAISS INDEXES")
    print("=" * 70)

    # --------------------------------------------------------
    # Group embedding positions by work_id
    # --------------------------------------------------------

    book_groups = {}

    for position, chunk in enumerate(
        chunks
    ):

        work_id = chunk.get(
            "work_id",
            chunk.get("document_id")
        )

        if not work_id:

            print(
                f"WARNING: chunk "
                f"{chunk.get('chunk_id')} "
                f"has no work_id."
            )

            continue

        book_groups.setdefault(
            work_id,
            []
        ).append(
            position
        )

    print(
        f"Books found: {len(book_groups)}"
    )

    if not book_groups:

        raise RuntimeError(
            "No books were found "
            "for per-book indexing."
        )

    # --------------------------------------------------------
    # Build one FAISS index per book
    # --------------------------------------------------------

    total_book_vectors = 0

    for book_number, (
        work_id,
        positions
    ) in enumerate(
        sorted(book_groups.items()),
        start=1
    ):

        print()
        print(
            f"[{book_number}/{len(book_groups)}] "
            f"{work_id}"
        )

        # ----------------------------------------------------
        # Get embeddings for this book
        # ----------------------------------------------------

        book_embeddings = embeddings[
            positions
        ]

        dimension = (
            book_embeddings.shape[1]
        )

        # ----------------------------------------------------
        # Create FAISS index
        # ----------------------------------------------------

        book_index = faiss.IndexFlatIP(
            dimension
        )

        book_index.add(
            book_embeddings
        )

        # ----------------------------------------------------
        # Save FAISS index
        # ----------------------------------------------------

        index_path = (
            BOOK_INDEX_DIR /
            f"{work_id}.index"
        )

        faiss.write_index(
            book_index,
            str(index_path)
        )

        # ----------------------------------------------------
        # Save metadata
        # ----------------------------------------------------

        book_metadata = []

        for position in positions:

            chunk = chunks[position]

            book_metadata.append(
                {
                    "chunk_id":
                        chunk["chunk_id"],

                    "document_id":
                        chunk["document_id"],

                    "work_id":
                        chunk.get(
                            "work_id",
                            chunk["document_id"]
                        ),

                    "filename":
                        chunk["filename"],

                    "page":
                        chunk.get("page"),

                    "title":
                        chunk.get(
                            "title",
                            ""
                        ),

                    "author":
                        chunk.get(
                            "author",
                            ""
                        ),

                    "chapter":
                        chunk.get(
                            "chapter",
                            "Unknown"
                        ),

                    "chunk_index":
                        chunk.get(
                            "chunk_index"
                        ),

                    "text":
                        chunk["text"]
                }
            )

        metadata_path = (
            BOOK_INDEX_DIR /
            f"{work_id}_metadata.json"
        )

        with open(
            metadata_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                book_metadata,
                f,
                ensure_ascii=False,
                indent=2
            )

        # ----------------------------------------------------
        # Display information
        # ----------------------------------------------------

        title = ""

        author = ""

        if book_metadata:

            title = book_metadata[0].get(
                "title",
                ""
            )

            author = book_metadata[0].get(
                "author",
                ""
            )

        print(
            f"  Title   : {title}"
        )

        print(
            f"  Author  : {author}"
        )

        print(
            f"  Vectors : {book_index.ntotal}"
        )

        print(
            f"  Index   : {index_path.name}"
        )

        print(
            f"  Metadata: {metadata_path.name}"
        )

        total_book_vectors += (
            book_index.ntotal
        )

    # --------------------------------------------------------
    # Verify
    # --------------------------------------------------------

    print()
    print(
        "=" * 70
    )

    print(
        "PER-BOOK INDEX BUILD COMPLETE"
    )

    print(
        "=" * 70
    )

    print(
        f"Books indexed     : "
        f"{len(book_groups)}"
    )

    print(
        f"Vectors indexed   : "
        f"{total_book_vectors:,}"
    )

    print(
        f"Output directory  : "
        f"{BOOK_INDEX_DIR}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("LUMINAR BOOK RAG EMBEDDING PIPELINE")
    print("=" * 70)

    print(
        f"Device : {DEVICE}"
    )

    print(
        f"Model  : {MODEL_NAME}"
    )

    # --------------------------------------------------------
    # LOAD CHUNKS
    # --------------------------------------------------------

    chunks = load_chunks()

    if not chunks:

        print(
            "No chunks found."
        )

        return

    print()
    print(
        f"Total chunks: {len(chunks):,}"
    )

    # --------------------------------------------------------
    # VALIDATE
    # --------------------------------------------------------

    validate_chunks(
        chunks
    )

    # --------------------------------------------------------
    # EXTRACT TEXT
    # --------------------------------------------------------

    texts = [
        chunk["text"]
        for chunk in chunks
    ]

    # --------------------------------------------------------
    # LOAD MODEL
    # --------------------------------------------------------

    print()
    print(
        "Loading MiniLM..."
    )

    start = time.perf_counter()

    model = SentenceTransformer(
        MODEL_NAME,
        device=DEVICE
    )

    model_load_time = (
        time.perf_counter()
        - start
    )

    print(
        f"Model load: "
        f"{model_load_time * 1000:.2f} ms"
    )

    # --------------------------------------------------------
    # WARMUP
    # --------------------------------------------------------

    print()
    print(
        "Warming MiniLM..."
    )

    model.encode(
        ["warm up"],
        batch_size=1,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    print(
        "MiniLM warm-up complete."
    )

    # --------------------------------------------------------
    # CREATE EMBEDDINGS
    # --------------------------------------------------------

    print()
    print(
        "=" * 70
    )

    print(
        "CREATING BOOK EMBEDDINGS"
    )

    print(
        "=" * 70
    )

    start = time.perf_counter()

    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    embedding_time = (
        time.perf_counter()
        - start
    )

    embeddings = np.asarray(
        embeddings,
        dtype="float32"
    )

    print()
    print(
        f"Embedding shape : "
        f"{embeddings.shape}"
    )

    print(
        f"Embedding time  : "
        f"{embedding_time:.2f} seconds"
    )

    # --------------------------------------------------------
    # SAVE ALL EMBEDDINGS
    # --------------------------------------------------------

    embeddings_path = (
        EMBEDDINGS_DIR /
        "rag_embeddings.npy"
    )

    np.save(
        embeddings_path,
        embeddings
    )

    print()
    print(
        "Embeddings saved:"
    )

    print(
        embeddings_path
    )

    # --------------------------------------------------------
    # BUILD GLOBAL FAISS INDEX
    # --------------------------------------------------------

    dimension = (
        embeddings.shape[1]
    )

    print()
    print(
        "=" * 70
    )

    print(
        "BUILDING GLOBAL BOOK RAG FAISS INDEX"
    )

    print(
        "=" * 70
    )

    print(
        f"Vectors   : "
        f"{len(embeddings):,}"
    )

    print(
        f"Dimension : "
        f"{dimension}"
    )

    # Normalized embeddings + inner product
    # = cosine similarity.
    index = faiss.IndexFlatIP(
        dimension
    )

    index.add(
        embeddings
    )

    print(
        f"Index vectors: "
        f"{index.ntotal:,}"
    )

    # --------------------------------------------------------
    # SAVE GLOBAL INDEX
    # --------------------------------------------------------

    index_path = (
        INDEX_DIR /
        "rag.index"
    )

    faiss.write_index(
        index,
        str(index_path)
    )

    print()
    print(
        "Global FAISS index saved:"
    )

    print(
        index_path
    )

    # --------------------------------------------------------
    # SAVE GLOBAL METADATA
    # --------------------------------------------------------

    metadata_path = (
        INDEX_DIR /
        "rag_metadata.json"
    )

    metadata = []

    for chunk in chunks:

        metadata.append(
            {
                "chunk_id":
                    chunk["chunk_id"],

                "document_id":
                    chunk["document_id"],

                "filename":
                    chunk["filename"],

                "page":
                    chunk.get("page"),

                # Book-specific fields
                "work_id":
                    chunk.get(
                        "work_id",
                        chunk["document_id"]
                    ),

                "title":
                    chunk.get(
                        "title",
                        ""
                    ),

                "author":
                    chunk.get(
                        "author",
                        ""
                    ),

                "chapter":
                    chunk.get(
                        "chapter",
                        "Unknown"
                    ),

                "chunk_index":
                    chunk.get(
                        "chunk_index"
                    )
            }
        )

    with open(
        metadata_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            metadata,
            f,
            ensure_ascii=False,
            indent=2
        )

    print()
    print(
        "Global metadata saved:"
    )

    print(
        metadata_path
    )

    # --------------------------------------------------------
    # BUILD PER-BOOK INDEXES
    # --------------------------------------------------------

    build_book_indexes(
        chunks,
        embeddings
    )

    # --------------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------------

    unique_documents = len(
        set(
            c["document_id"]
            for c in chunks
        )
    )

    unique_books = len(
        set(
            c.get(
                "work_id",
                c["document_id"]
            )
            for c in chunks
        )
    )

    print()
    print("=" * 70)
    print("BOOK RAG EMBEDDING COMPLETE")
    print("=" * 70)

    print(
        f"Documents       : "
        f"{unique_documents}"
    )

    print(
        f"Books           : "
        f"{unique_books}"
    )

    print(
        f"Chunks          : "
        f"{len(chunks):,}"
    )

    print(
        f"Embedding dim   : "
        f"{dimension}"
    )

    print(
        f"Global vectors  : "
        f"{index.ntotal:,}"
    )

    print(
        f"Device          : "
        f"{DEVICE}"
    )

    print()
    print(
        "Global index:"
    )

    print(
        index_path
    )

    print()
    print(
        "Per-book indexes:"
    )

    print(
        BOOK_INDEX_DIR
    )

    print()
    print(
        "Next stage:"
    )

    print(
        "Update the RAG retriever to use "
        "the per-book indexes for work_id searches."
    )

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

def index_registered_book(work_id):
    """Publish one book using real embeddings; preserve other book vectors."""
    from rag.book_assets import valid_work_id, readable_path
    if not valid_work_id(work_id) or readable_path(work_id) is None:
        raise ValueError("Register authorized full text for a catalog work_id first.")
    data = json.loads((CHUNKS_DIR / f"{work_id}.json").read_text(encoding="utf-8"))
    chunks = data["chunks"]
    validate_chunks(chunks)
    if not chunks or any(chunk.get("work_id") != work_id or chunk.get("document_id") != work_id for chunk in chunks):
        raise ValueError("All chunks must belong to the selected work_id.")
    model = SentenceTransformer(MODEL_NAME, device=DEVICE, local_files_only=True)
    embeddings = np.asarray(model.encode([chunk["text"] for chunk in chunks],
        batch_size=32, convert_to_numpy=True, normalize_embeddings=True,
        show_progress_bar=True), dtype=np.float32)
    build_book_indexes(chunks, embeddings)
    new_metadata = json.loads((BOOK_INDEX_DIR / f"{work_id}_metadata.json").read_text(encoding="utf-8"))
    index_path = INDEX_DIR / "rag.index"
    metadata_path = INDEX_DIR / "rag_metadata.json"
    if index_path.exists() and metadata_path.exists():
        old_index = faiss.read_index(str(index_path))
        old_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if old_index.ntotal != len(old_metadata) or old_index.d != embeddings.shape[1]:
            raise ValueError("Existing global book index and metadata must agree before publication.")
        keep = [i for i, row in enumerate(old_metadata) if row.get("work_id") != work_id]
        retained = old_index.reconstruct_n(0, old_index.ntotal)[keep]
        vectors = np.concatenate([retained, embeddings])
        metadata = [old_metadata[i] for i in keep] + new_metadata
    else:
        vectors, metadata = embeddings, new_metadata
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(np.ascontiguousarray(vectors, dtype=np.float32))
    pending_index = index_path.with_suffix(".index.tmp")
    pending_metadata = metadata_path.with_suffix(".json.tmp")
    faiss.write_index(index, str(pending_index))
    pending_metadata.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    pending_index.replace(index_path)
    pending_metadata.replace(metadata_path)
    print(f"Published {work_id}: {len(chunks)} chunks; {index.ntotal} total book vectors.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build discovered book indexes or index one registered book.")
    parser.add_argument("--work-id")
    args = parser.parse_args()
    if args.work_id:
        index_registered_book(args.work_id)
    else:
        main()
