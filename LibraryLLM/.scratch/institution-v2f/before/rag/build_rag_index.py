import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


# ============================================================
# CONFIG
# ============================================================

CHUNKS_FILE = Path("rag/chunks/all_chunks.json")
INDEX_DIR = Path("rag/index")

INDEX_FILE = INDEX_DIR / "rag.faiss"
METADATA_FILE = INDEX_DIR / "metadata.json"

# IMPORTANT:
# Replace this with the EXACT MiniLM model used by your
# existing LuminaR search system if the name differs.
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

BATCH_SIZE = 64


# ============================================================
# LOAD CHUNKS
# ============================================================

def load_chunks():

    if not CHUNKS_FILE.exists():
        raise FileNotFoundError(
            f"Chunk file not found: {CHUNKS_FILE}"
        )

    with open(
        CHUNKS_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        chunks = json.load(f)

    if not chunks:
        raise ValueError(
            "No chunks found."
        )

    return chunks


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print(" LuminaR RAG — FAISS INDEX BUILDER")
    print("=" * 60)
    print()

    INDEX_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Load chunks
    # --------------------------------------------------------

    print("Loading chunks...")

    chunks = load_chunks()

    print(
        f"Loaded {len(chunks):,} chunks."
    )

    # --------------------------------------------------------
    # Load MiniLM
    # --------------------------------------------------------

    print()
    print(
        f"Loading embedding model: {MODEL_NAME}"
    )

    model = SentenceTransformer(
        MODEL_NAME
    )

    print("Embedding model loaded.")

    # --------------------------------------------------------
    # Extract text
    # --------------------------------------------------------

    texts = [
        chunk["text"]
        for chunk in chunks
    ]

    # --------------------------------------------------------
    # Generate embeddings
    # --------------------------------------------------------

    print()
    print("Generating embeddings...")

    embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    embeddings = np.asarray(
        embeddings,
        dtype=np.float32
    )

    print(
        f"Embedding shape: {embeddings.shape}"
    )

    # --------------------------------------------------------
    # Build FAISS index
    # --------------------------------------------------------

    dimension = embeddings.shape[1]

    print()
    print(
        f"Creating FAISS index "
        f"with dimension {dimension}..."
    )

    # Because embeddings are normalized, inner product is
    # equivalent to cosine similarity.
    index = faiss.IndexFlatIP(
        dimension
    )

    index.add(
        embeddings
    )

    print(
        f"FAISS vectors: {index.ntotal:,}"
    )

    # --------------------------------------------------------
    # Save index
    # --------------------------------------------------------

    faiss.write_index(
        index,
        str(INDEX_FILE)
    )

    # --------------------------------------------------------
    # Save metadata
    # --------------------------------------------------------

    metadata = []

    for chunk in chunks:

        metadata.append(
            {
                "chunk_id": chunk["chunk_id"],
                "work_id": chunk["work_id"],
                "title": chunk["title"],
                "author": chunk["author"],
                "source_file": chunk["source_file"],
                "chunk_index": chunk["chunk_index"],
                "chapter": chunk["chapter"],
                "text": chunk["text"]
            }
        )

    with open(
        METADATA_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            metadata,
            f,
            indent=2,
            ensure_ascii=False
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print(" RAG INDEX BUILD COMPLETE")
    print("=" * 60)

    print(
        f"Books/chunks: {len(chunks):,}"
    )

    print(
        f"Vector dimension: {dimension}"
    )

    print(
        f"FAISS vectors: {index.ntotal:,}"
    )

    print(
        f"FAISS index: {INDEX_FILE}"
    )

    print(
        f"Metadata: {METADATA_FILE}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()