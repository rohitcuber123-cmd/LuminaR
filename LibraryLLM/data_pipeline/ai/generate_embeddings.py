from pathlib import Path
import time

import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer


# ============================================================
# ASTRALIB - EMBEDDING MODEL COMPARISON
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
    / "model_benchmarks"
)

TEST_BOOKS = 10_000
BATCH_SIZE = 64

MODELS = [
    "all-MiniLM-L6-v2",
    "BAAI/bge-small-en-v1.5",
    "BAAI/bge-base-en-v1.5",
]


# ============================================================
# START
# ============================================================

print("=" * 70)
print("ASTRALIB - EMBEDDING MODEL COMPARISON")
print("=" * 70)

print()
print(f"Books per model : {TEST_BOOKS:,}")
print(f"Batch size      : {BATCH_SIZE}")
print()

if not torch.cuda.is_available():
    raise RuntimeError("CUDA is not available.")

print("GPU :", torch.cuda.get_device_name(0))
print("CUDA:", torch.version.cuda)
print()


# ============================================================
# INPUT
# ============================================================

if not INPUT.exists():
    raise FileNotFoundError(
        f"Embedding corpus not found:\n{INPUT}"
    )

print("Loading test records...")

df = pd.read_parquet(
    INPUT,
    columns=["work_id", "search_text"],
)

df = df.head(TEST_BOOKS).copy()

df["search_text"] = (
    df["search_text"]
    .fillna("")
    .astype(str)
)

texts = df["search_text"].tolist()

print(f"Loaded: {len(texts):,} books")
print()


# ============================================================
# OUTPUT DIRECTORY
# ============================================================

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# RESULTS
# ============================================================

results = []


# ============================================================
# TEST EACH MODEL
# ============================================================

for model_name in MODELS:

    print()
    print("=" * 70)
    print(f"MODEL: {model_name}")
    print("=" * 70)
    print()

    # --------------------------------------------------------
    # Clear GPU
    # --------------------------------------------------------

    torch.cuda.empty_cache()

    # --------------------------------------------------------
    # Load model
    # --------------------------------------------------------

    print("Loading model...")

    model = SentenceTransformer(
        model_name,
        device="cuda"
    )

    # Keep the same maximum sequence length
    # for a fair comparison.
    model.max_seq_length = 256

    dimension = model.get_embedding_dimension()

    print(
        f"Embedding dimension: {dimension}"
    )

    # --------------------------------------------------------
    # Warm-up
    # --------------------------------------------------------

    print("GPU warm-up...")

    model.encode(
        ["AstraLib semantic search benchmark"],
        batch_size=1,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    torch.cuda.synchronize()

    # --------------------------------------------------------
    # Clear previous peak statistics
    # --------------------------------------------------------

    torch.cuda.reset_peak_memory_stats()

    # --------------------------------------------------------
    # Benchmark
    # --------------------------------------------------------

    print()
    print("Starting benchmark...")
    print()

    start = time.time()

    embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    torch.cuda.synchronize()

    elapsed = time.time() - start

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    books_per_second = (
        len(texts) / elapsed
    )

    estimated_seconds = (
        5_000_000 / books_per_second
    )

    estimated_hours = (
        estimated_seconds / 3600
    )

    peak_allocated = (
        torch.cuda.max_memory_allocated()
        / (1024 ** 3)
    )

    peak_reserved = (
        torch.cuda.max_memory_reserved()
        / (1024 ** 3)
    )

    # --------------------------------------------------------
    # Save 10K benchmark embeddings
    # --------------------------------------------------------

    safe_name = (
        model_name
        .replace("/", "_")
    )

    output_file = (
        OUTPUT_DIR
        / f"{safe_name}_10k.npy"
    )

    np.save(
        output_file,
        embeddings.astype(np.float32)
    )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    result = {
        "model": model_name,
        "dimension": dimension,
        "books": len(texts),
        "batch_size": BATCH_SIZE,
        "time_seconds": elapsed,
        "books_per_second": books_per_second,
        "estimated_5m_hours": estimated_hours,
        "peak_gpu_allocated_gb": peak_allocated,
        "peak_gpu_reserved_gb": peak_reserved,
        "output": str(output_file),
    }

    results.append(result)

    # --------------------------------------------------------
    # Print result
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("RESULT")
    print("-" * 70)

    print(
        f"Model                  : {model_name}"
    )

    print(
        f"Embedding dimension    : {dimension}"
    )

    print(
        f"Books processed        : {len(texts):,}"
    )

    print(
        f"Time                   : {elapsed:.2f} seconds"
    )

    print(
        f"Speed                  : "
        f"{books_per_second:.2f} books/sec"
    )

    print(
        f"Estimated 5M time      : "
        f"{estimated_hours:.2f} hours"
    )

    print(
        f"Peak GPU allocated     : "
        f"{peak_allocated:.2f} GB"
    )

    print(
        f"Peak GPU reserved      : "
        f"{peak_reserved:.2f} GB"
    )

    print(
        f"Benchmark embeddings   : "
        f"{output_file}"
    )

    print()

    # --------------------------------------------------------
    # Delete model before next model
    # --------------------------------------------------------

    del model
    del embeddings

    torch.cuda.empty_cache()


# ============================================================
# COMPARISON TABLE
# ============================================================

print()
print("=" * 70)
print("FINAL MODEL COMPARISON")
print("=" * 70)

print()

print(
    f"{'Model':<30}"
    f"{'Dim':>6}"
    f"{'Books/s':>12}"
    f"{'5M hours':>12}"
    f"{'VRAM GB':>12}"
)

print("-" * 70)

for r in results:

    short_name = r["model"]

    if len(short_name) > 28:
        short_name = short_name[:28]

    print(
        f"{short_name:<30}"
        f"{r['dimension']:>6}"
        f"{r['books_per_second']:>12.2f}"
        f"{r['estimated_5m_hours']:>12.2f}"
        f"{r['peak_gpu_allocated_gb']:>12.2f}"
    )


# ============================================================
# SAVE RESULTS
# ============================================================

results_df = pd.DataFrame(results)

results_file = (
    OUTPUT_DIR
    / "model_comparison.csv"
)

results_df.to_csv(
    results_file,
    index=False
)


# ============================================================
# STORAGE ESTIMATES
# ============================================================

print()
print("=" * 70)
print("ESTIMATED RAW VECTOR STORAGE FOR 5M BOOKS")
print("=" * 70)

print()

for r in results:

    dimension = r["dimension"]

    bytes_required = (
        5_000_000
        * dimension
        * 4
    )

    gb = (
        bytes_required
        / (1024 ** 3)
    )

    print(
        f"{r['model']:<30}"
        f"{dimension:>6} dimensions"
        f"  ≈ {gb:.2f} GB"
    )


print()
print("=" * 70)
print("BENCHMARK COMPLETE")
print("=" * 70)

print()
print(f"Results saved to:")
print(results_file)