from pathlib import Path
import json
import time

import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


# ============================================================
# ASTRALIB - PRODUCTION EMBEDDING GENERATOR
# ============================================================

BASE_DIR = Path(r"D:\SDC\LibraryLLM")

INPUT = (
    BASE_DIR
    / "datasets"
    / "ai"
    / "embeddings"
    / "embedding_corpus.parquet"
)

OUTPUT_DIR = (
    BASE_DIR
    / "datasets"
    / "ai"
    / "embeddings"
    / "vectors"
)

CHECKPOINT_DIR = OUTPUT_DIR / "checkpoints"

MODEL_NAME = "all-MiniLM-L6-v2"

BATCH_SIZE = 64

CHUNK_SIZE = 50_000

# ============================================================
# OUTPUT FILES
# ============================================================

FINAL_EMBEDDINGS = OUTPUT_DIR / "embeddings.npy"
FINAL_WORK_IDS = OUTPUT_DIR / "work_ids.npy"

STATE_FILE = OUTPUT_DIR / "checkpoint.json"


# ============================================================
# SETUP
# ============================================================

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

CHECKPOINT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


print("=" * 70)
print("ASTRALIB - PRODUCTION EMBEDDING GENERATOR")
print("=" * 70)

print()
print(f"Input        : {INPUT}")
print(f"Model        : {MODEL_NAME}")
print(f"Batch size   : {BATCH_SIZE}")
print(f"Chunk size   : {CHUNK_SIZE:,}")
print()


# ============================================================
# CHECK INPUT
# ============================================================

if not INPUT.exists():
    raise FileNotFoundError(
        f"Embedding corpus not found:\n{INPUT}"
    )


# ============================================================
# CHECK CUDA
# ============================================================

if not torch.cuda.is_available():
    raise RuntimeError(
        "CUDA is not available."
    )

DEVICE = "cuda"

GPU_NAME = torch.cuda.get_device_name(0)

print(f"GPU          : {GPU_NAME}")
print(f"CUDA         : {torch.version.cuda}")

print()


# ============================================================
# LOAD CORPUS INFORMATION
# ============================================================

print("=" * 70)
print("READING CORPUS")
print("=" * 70)

print()

# We only read the columns we actually need.
df = pd.read_parquet(
    INPUT,
    columns=[
        "work_id",
        "search_text"
    ]
)

total_books = len(df)

print(
    f"Books to embed: {total_books:,}"
)

print()


# ============================================================
# LOAD MODEL
# ============================================================

print("=" * 70)
print("LOADING EMBEDDING MODEL")
print("=" * 70)

print()

model = SentenceTransformer(
    MODEL_NAME,
    device=DEVICE
)

model.max_seq_length = 256

embedding_dimension = (
    model.get_embedding_dimension()
)

print(
    f"Embedding dimension: {embedding_dimension}"
)

print()


# ============================================================
# CHECKPOINT HELPERS
# ============================================================

def save_state(
    completed,
    total,
    chunks
):

    state = {
        "model": MODEL_NAME,
        "batch_size": BATCH_SIZE,
        "chunk_size": CHUNK_SIZE,
        "embedding_dimension": embedding_dimension,
        "total_books": total,
        "completed_books": completed,
        "completed_chunks": chunks
    }

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            state,
            f,
            indent=2
        )


def load_state():

    if not STATE_FILE.exists():
        return {
            "completed_books": 0,
            "completed_chunks": 0
        }

    with open(
        STATE_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


# ============================================================
# RESUME INFORMATION
# ============================================================

state = load_state()

completed_books = state.get(
    "completed_books",
    0
)

completed_chunks = state.get(
    "completed_chunks",
    0
)


# ============================================================
# VALIDATE CHECKPOINT
# ============================================================

if completed_books > total_books:

    raise RuntimeError(
        "Checkpoint contains more books "
        "than the input corpus."
    )


if completed_books > 0:

    print("=" * 70)
    print("RESUMING PREVIOUS RUN")
    print("=" * 70)

    print()

    print(
        f"Already completed : "
        f"{completed_books:,}"
    )

    print(
        f"Remaining         : "
        f"{total_books - completed_books:,}"
    )

    print(
        f"Completed chunks  : "
        f"{completed_chunks}"
    )

    print()


else:

    print(
        "Starting from book 0."
    )

    print()


# ============================================================
# PROCESS CHUNKS
# ============================================================

start_time = time.time()

remaining_books = (
    total_books - completed_books
)

total_chunks = (
    (total_books + CHUNK_SIZE - 1)
    // CHUNK_SIZE
)


for chunk_number in range(
    completed_chunks,
    total_chunks
):

    chunk_start = (
        chunk_number * CHUNK_SIZE
    )

    chunk_end = min(
        chunk_start + CHUNK_SIZE,
        total_books
    )

    # Skip chunks already completed
    if chunk_end <= completed_books:
        continue

    print()
    print("=" * 70)

    print(
        f"CHUNK "
        f"{chunk_number + 1}/{total_chunks}"
    )

    print("=" * 70)

    print()

    print(
        f"Records: "
        f"{chunk_start:,} → {chunk_end:,}"
    )

    print()

    # --------------------------------------------------------
    # Extract chunk
    # --------------------------------------------------------

    chunk = df.iloc[
        chunk_start:chunk_end
    ]

    work_ids = (
        chunk["work_id"]
        .astype(str)
        .to_numpy()
    )

    texts = (
        chunk["search_text"]
        .fillna("")
        .astype(str)
        .tolist()
    )

    # --------------------------------------------------------
    # Generate embeddings
    # --------------------------------------------------------

    chunk_start_time = time.time()

    embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True
    )

    torch.cuda.synchronize()

    chunk_elapsed = (
        time.time()
        - chunk_start_time
    )

    chunk_speed = (
        len(texts)
        / chunk_elapsed
    )

    print()

    print(
        f"Chunk speed: "
        f"{chunk_speed:.2f} books/sec"
    )

    # --------------------------------------------------------
    # Save checkpoint
    # --------------------------------------------------------

    embedding_file = (
        CHECKPOINT_DIR
        / f"embeddings_{chunk_number:04d}.npy"
    )

    work_id_file = (
        CHECKPOINT_DIR
        / f"work_ids_{chunk_number:04d}.npy"
    )

    np.save(
        embedding_file,
        embeddings.astype(
            np.float32
        )
    )

    np.save(
        work_id_file,
        work_ids
    )

    # --------------------------------------------------------
    # Update state
    # --------------------------------------------------------

    completed_books = chunk_end

    completed_chunks = (
        chunk_number + 1
    )

    save_state(
        completed_books,
        total_books,
        completed_chunks
    )

    # --------------------------------------------------------
    # Progress
    # --------------------------------------------------------

    elapsed = (
        time.time()
        - start_time
    )

    current_speed = (
        (completed_books - state.get(
            "completed_books",
            0
        ))
        / elapsed
        if elapsed > 0
        else 0
    )

    overall_speed = (
        completed_books / elapsed
        if elapsed > 0
        else 0
    )

    remaining = (
        total_books - completed_books
    )

    eta_seconds = (
        remaining / overall_speed
        if overall_speed > 0
        else 0
    )

    eta_hours = (
        eta_seconds / 3600
    )

    percent = (
        completed_books
        / total_books
        * 100
    )

    print()

    print(
        f"Progress        : "
        f"{percent:.2f}%"
    )

    print(
        f"Completed       : "
        f"{completed_books:,}/"
        f"{total_books:,}"
    )

    print(
        f"Overall speed   : "
        f"{overall_speed:.2f} books/sec"
    )

    print(
        f"ETA             : "
        f"{eta_hours:.2f} hours"
    )

    print()

    # Release chunk memory
    del chunk
    del texts
    del work_ids
    del embeddings

    torch.cuda.empty_cache()


# ============================================================
# BUILD FINAL ARRAYS
# ============================================================

print()
print("=" * 70)
print("BUILDING FINAL EMBEDDING ARRAYS")
print("=" * 70)

print()

all_embedding_files = sorted(
    CHECKPOINT_DIR.glob(
        "embeddings_*.npy"
    )
)

all_work_id_files = sorted(
    CHECKPOINT_DIR.glob(
        "work_ids_*.npy"
    )
)

if len(all_embedding_files) == 0:

    raise RuntimeError(
        "No embedding checkpoint files found."
    )


print(
    f"Embedding chunks: "
    f"{len(all_embedding_files)}"
)

print()


# ============================================================
# MERGE EMBEDDINGS
# ============================================================

print("Merging embedding chunks...")

embedding_arrays = []

for file in tqdm(
    all_embedding_files,
    desc="Loading embeddings"
):

    embedding_arrays.append(
        np.load(
            file,
            mmap_mode="r"
        )
    )


print()
print(
    "Creating final embedding array..."
)

final_embeddings = np.concatenate(
    embedding_arrays,
    axis=0
)

np.save(
    FINAL_EMBEDDINGS,
    final_embeddings.astype(
        np.float32
    )
)

del embedding_arrays
del final_embeddings


# ============================================================
# MERGE WORK IDS
# ============================================================

print()
print("Merging work IDs...")

work_id_arrays = []

for file in tqdm(
    all_work_id_files,
    desc="Loading work IDs"
):

    work_id_arrays.append(
        np.load(
            file,
            allow_pickle=True
        )
    )


final_work_ids = np.concatenate(
    work_id_arrays
)

np.save(
    FINAL_WORK_IDS,
    final_work_ids
)

del work_id_arrays
del final_work_ids


# ============================================================
# FINAL VERIFICATION
# ============================================================

print()
print("=" * 70)
print("FINAL VERIFICATION")
print("=" * 70)

print()

embeddings = np.load(
    FINAL_EMBEDDINGS,
    mmap_mode="r"
)

work_ids = np.load(
    FINAL_WORK_IDS,
    allow_pickle=True
)

print(
    f"Embeddings shape : "
    f"{embeddings.shape}"
)

print(
    f"Work IDs         : "
    f"{len(work_ids):,}"
)

print(
    f"Dimension        : "
    f"{embeddings.shape[1]}"
)

print(
    f"Dtype            : "
    f"{embeddings.dtype}"
)

print()


if len(embeddings) != len(work_ids):

    raise RuntimeError(
        "Embedding count and work ID count "
        "do not match!"
    )


if embeddings.shape[1] != embedding_dimension:

    raise RuntimeError(
        "Unexpected embedding dimension!"
    )


# ============================================================
# CHECK NORMALIZATION
# ============================================================

print("Checking embedding normalization...")

sample = embeddings[
    :min(1000, len(embeddings))
]

norms = np.linalg.norm(
    sample,
    axis=1
)

print(
    f"Minimum norm : "
    f"{norms.min():.5f}"
)

print(
    f"Maximum norm : "
    f"{norms.max():.5f}"
)

print()


# ============================================================
# FILE SIZES
# ============================================================

embedding_size = (
    FINAL_EMBEDDINGS.stat().st_size
    / (1024 ** 3)
)

work_id_size = (
    FINAL_WORK_IDS.stat().st_size
    / (1024 ** 3)
)

print(
    f"Embeddings file : "
    f"{embedding_size:.2f} GB"
)

print(
    f"Work IDs file   : "
    f"{work_id_size:.2f} GB"
)

print()


# ============================================================
# FINAL
# ============================================================

total_elapsed = (
    time.time()
    - start_time
)

print("=" * 70)
print("EMBEDDING GENERATION COMPLETE")
print("=" * 70)

print()

print(
    f"Books embedded : "
    f"{len(embeddings):,}"
)

print(
    f"Dimensions     : "
    f"{embeddings.shape[1]}"
)

print(
    f"Total time     : "
    f"{total_elapsed / 3600:.2f} hours"
)

print()

print("Embeddings:")
print(FINAL_EMBEDDINGS)

print()

print("Work IDs:")
print(FINAL_WORK_IDS)

print()

print("=" * 70)