# -*- coding: utf-8 -*-
"""
AstraLib -- Benchmark Mini-LM Query Embedding Performance

Diagnose whether the observed ~1354 ms query embedding latency is
genuine inference cost or synchronization / warm-up / configuration
overhead.

This script is READ-ONLY with respect to production artefacts:
    - No HNSW index modification
    - No FAISS index modification
    - No embedding regeneration
    - No metadata database changes

Usage:
    python data_pipeline/ai/benchmark_embedding.py
"""

import math
import statistics
import time

import numpy as np
import torch

# ======================================================================
# TEST 5 — DIRECT TORCH GPU CHECK  (pre-model)
# ======================================================================

print()
print("=" * 70)
print("ASTRALIB — BENCHMARK MINI-LM QUERY EMBEDDING PERFORMANCE")
print("=" * 70)
print()

# ── GPU info (before model load) ─────────────────────────────────────

cuda_available = torch.cuda.is_available()

print("=" * 70)
print("TEST 5 — GPU / CUDA SANITY CHECK")
print("=" * 70)
print()
print(f"CUDA available     : {cuda_available}")
print(f"CUDA device count  : {torch.cuda.device_count()}")

if cuda_available:
    print(f"GPU name           : {torch.cuda.get_device_name(0)}")
    mem_alloc_before = torch.cuda.memory_allocated(0)
    mem_reserved_before = torch.cuda.memory_reserved(0)
    print(f"Memory allocated   : {mem_alloc_before / 1024**2:.1f} MB")
    print(f"Memory reserved    : {mem_reserved_before / 1024**2:.1f} MB")
else:
    mem_alloc_before = 0
    mem_reserved_before = 0

print(f"PyTorch            : {torch.__version__}")
print(f"CUDA version       : {torch.version.cuda}")

try:
    import sentence_transformers
    print(f"Sentence-Trans.    : {sentence_transformers.__version__}")
except AttributeError:
    print("Sentence-Trans.    : (version unavailable)")

print()

# ======================================================================
# MODEL LOADING
# ======================================================================

from sentence_transformers import SentenceTransformer  # noqa: E402

MODEL_NAME = "all-MiniLM-L6-v2"
DEVICE = "cuda" if cuda_available else "cpu"

print("=" * 70)
print("MODEL LOADING")
print("=" * 70)
print()
print(f"Model  : {MODEL_NAME}")
print(f"Device : {DEVICE}")
print()

# Load model — timed separately
load_start = time.perf_counter()
model = SentenceTransformer(MODEL_NAME, device=DEVICE)
if cuda_available:
    torch.cuda.synchronize()
load_elapsed = time.perf_counter() - load_start

print(f"Model load : {load_elapsed * 1000:.1f} ms")
print()
print("Model loading is a one-time startup cost and should not")
print("occur per API request.")
print()

# ── GPU memory after model load ──────────────────────────────────────

if cuda_available:
    mem_alloc_after = torch.cuda.memory_allocated(0)
    mem_reserved_after = torch.cuda.memory_reserved(0)
    print(f"GPU memory allocated (after load) : "
          f"{mem_alloc_after / 1024**2:.1f} MB  "
          f"(+{(mem_alloc_after - mem_alloc_before) / 1024**2:.1f} MB)")
    print(f"GPU memory reserved  (after load) : "
          f"{mem_reserved_after / 1024**2:.1f} MB  "
          f"(+{(mem_reserved_after - mem_reserved_before) / 1024**2:.1f} MB)")
    print()


# ======================================================================
# HELPER — TIMED ENCODE
# ======================================================================

def timed_encode(mdl, texts, batch_size=1):
    """Encode with proper CUDA synchronisation and return elapsed seconds."""
    if cuda_available:
        torch.cuda.synchronize()
    t0 = time.perf_counter()
    emb = mdl.encode(
        texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    if cuda_available:
        torch.cuda.synchronize()
    return time.perf_counter() - t0, emb


# ======================================================================
# WARM-UP (GPU model)
# ======================================================================

WARMUP_QUERY = "book on wizards"
WARMUP_ITERS = 20

print("=" * 70)
print("WARM-UP  (GPU)")
print("=" * 70)
print()
print(f"Query      : \"{WARMUP_QUERY}\"")
print(f"Iterations : {WARMUP_ITERS}")

for _ in range(WARMUP_ITERS):
    timed_encode(model, [WARMUP_QUERY])

print("Warm-up complete.")
print()


# ======================================================================
# TEST 1 — CUDA SINGLE QUERY
# ======================================================================

QUERIES = [
    "book on wizards",
    "a book about good habits",
    "books for learning deep learning and neural networks",
]

ITERATIONS = 100

print("=" * 70)
print("TEST 1 — CUDA SINGLE QUERY")
print("=" * 70)
print()

for query in QUERIES:
    timings = []
    for _ in range(ITERATIONS):
        elapsed, _ = timed_encode(model, [query])
        timings.append(elapsed * 1000)  # ms

    avg = statistics.mean(timings)
    med = statistics.median(timings)
    p95 = sorted(timings)[int(0.95 * len(timings))]
    mn  = min(timings)
    mx  = max(timings)

    print(f"Query      : \"{query}\"")
    print(f"Batch size : 1")
    print(f"Iterations : {ITERATIONS}")
    print()
    print(f"  Average  : {avg:8.2f} ms")
    print(f"  Median   : {med:8.2f} ms")
    print(f"  P95      : {p95:8.2f} ms")
    print(f"  Minimum  : {mn:8.2f} ms")
    print(f"  Maximum  : {mx:8.2f} ms")
    print()

# Remember primary query stats for summary
primary_timings_gpu = []
for _ in range(ITERATIONS):
    elapsed, _ = timed_encode(model, [QUERIES[0]])
    primary_timings_gpu.append(elapsed * 1000)

gpu_single_avg = statistics.mean(primary_timings_gpu)
gpu_single_med = statistics.median(primary_timings_gpu)


# ======================================================================
# TEST 2 — CPU SINGLE QUERY
# ======================================================================

print("=" * 70)
print("TEST 2 — CPU SINGLE QUERY")
print("=" * 70)
print()

cpu_model = SentenceTransformer(MODEL_NAME, device="cpu")

# CPU warm-up
print(f"CPU warm-up ({WARMUP_ITERS} iterations)...")
for _ in range(WARMUP_ITERS):
    cpu_model.encode(
        [WARMUP_QUERY],
        batch_size=1,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
print("CPU warm-up complete.")
print()

cpu_timings = []
for _ in range(ITERATIONS):
    t0 = time.perf_counter()
    cpu_model.encode(
        [WARMUP_QUERY],
        batch_size=1,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    cpu_timings.append((time.perf_counter() - t0) * 1000)

cpu_avg = statistics.mean(cpu_timings)
cpu_med = statistics.median(cpu_timings)
cpu_p95 = sorted(cpu_timings)[int(0.95 * len(cpu_timings))]
cpu_mn  = min(cpu_timings)
cpu_mx  = max(cpu_timings)

print(f"Query      : \"{WARMUP_QUERY}\"")
print(f"Batch size : 1")
print(f"Iterations : {ITERATIONS}")
print()
print(f"  Average  : {cpu_avg:8.2f} ms")
print(f"  Median   : {cpu_med:8.2f} ms")
print(f"  P95      : {cpu_p95:8.2f} ms")
print(f"  Minimum  : {cpu_mn:8.2f} ms")
print(f"  Maximum  : {cpu_mx:8.2f} ms")
print()

# Free CPU model to save memory
del cpu_model


# ======================================================================
# TEST 3 — BATCH SIZE COMPARISON ON GPU
# ======================================================================

BATCH_SIZES = [1, 8, 32, 64]
TARGET_TEXTS = 100

print("=" * 70)
print("TEST 3 — GPU BATCH PERFORMANCE")
print("=" * 70)
print()

header = (f"{'Batch':>6}  {'Batches':>7}  {'Texts':>6}  "
          f"{'Total ms':>10}  {'ms/text':>9}  {'texts/sec':>10}")
print(header)
print("-" * len(header))

best_throughput = 0.0

for bs in BATCH_SIZES:
    n_batches = max(1, math.ceil(TARGET_TEXTS / bs))
    total_texts = n_batches * bs
    texts = [WARMUP_QUERY] * bs

    # Warm-up for this batch size
    for _ in range(5):
        timed_encode(model, texts, batch_size=bs)

    total_time = 0.0
    for _ in range(n_batches):
        elapsed, _ = timed_encode(model, texts, batch_size=bs)
        total_time += elapsed

    total_ms = total_time * 1000
    ms_per_text = total_ms / total_texts
    texts_per_sec = total_texts / total_time if total_time > 0 else 0

    if texts_per_sec > best_throughput:
        best_throughput = texts_per_sec

    print(f"{bs:>6}  {n_batches:>7}  {total_texts:>6}  "
          f"{total_ms:>10.1f}  {ms_per_text:>9.2f}  "
          f"{texts_per_sec:>10.1f}")

print()


# ======================================================================
# TEST 4 — TOKENIZATION VS MODEL INFERENCE
# ======================================================================

print("=" * 70)
print("TEST 4 — TOKENIZATION VS INFERENCE BREAKDOWN")
print("=" * 70)
print()

try:
    tokenizer = model.tokenizer
    pool_module = model[1] if len(model) > 1 else None
    transformer = model[0]

    test_text = WARMUP_QUERY
    BREAKDOWN_ITERS = 100

    # ── Tokenization ─────────────────────────────────────────────────
    tok_times = []
    for _ in range(BREAKDOWN_ITERS):
        if cuda_available:
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        encoded = tokenizer(
            [test_text],
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="pt",
        )
        tok_times.append((time.perf_counter() - t0) * 1000)

    # ── Transformer forward pass ─────────────────────────────────────
    fwd_times = []
    encoded_gpu = {k: v.to(DEVICE) for k, v in encoded.items()}
    # warm-up transformer
    for _ in range(10):
        with torch.no_grad():
            transformer(encoded_gpu)

    for _ in range(BREAKDOWN_ITERS):
        encoded_gpu = {k: v.to(DEVICE) for k, v in encoded.items()}
        if cuda_available:
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        with torch.no_grad():
            out = transformer(encoded_gpu)
        if cuda_available:
            torch.cuda.synchronize()
        fwd_times.append((time.perf_counter() - t0) * 1000)

    # ── Pooling + normalisation ──────────────────────────────────────
    pool_times = []
    if pool_module is not None:
        # warm-up
        for _ in range(10):
            pool_module(out)

        for _ in range(BREAKDOWN_ITERS):
            if cuda_available:
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            pooled = pool_module(out)
            if cuda_available:
                torch.cuda.synchronize()
            pool_times.append((time.perf_counter() - t0) * 1000)

    # ── numpy conversion + L2 normalisation ──────────────────────────
    conv_times = []
    for _ in range(BREAKDOWN_ITERS):
        if cuda_available:
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        if pool_module is not None:
            emb_np = pooled["sentence_embedding"].cpu().numpy()
        else:
            # fallback: use the token_embeddings CLS
            emb_np = out["token_embeddings"][:, 0, :].cpu().numpy()
        emb_np = emb_np / np.linalg.norm(emb_np, axis=1, keepdims=True)
        conv_times.append((time.perf_counter() - t0) * 1000)

    tok_avg = statistics.mean(tok_times)
    fwd_avg = statistics.mean(fwd_times)
    pool_avg = statistics.mean(pool_times) if pool_times else 0.0
    conv_avg = statistics.mean(conv_times)
    total_parts = tok_avg + fwd_avg + pool_avg + conv_avg

    print(f"  Tokenization          : {tok_avg:8.3f} ms")
    print(f"  Transformer forward   : {fwd_avg:8.3f} ms")
    if pool_times:
        print(f"  Pooling               : {pool_avg:8.3f} ms")
    print(f"  Numpy + normalise     : {conv_avg:8.3f} ms")
    print(f"  -----------------------------------")
    print(f"  Sum of parts          : {total_parts:8.3f} ms")
    print(f"  model.encode() avg    : {gpu_single_avg:8.3f} ms")
    print()

except Exception as exc:
    print(f"  Detailed breakdown unavailable: {exc}")
    print("  (This may be due to SentenceTransformer version differences.)")
    print()


# ======================================================================
# TEST 6 — EMBEDDING OUTPUT VALIDATION
# ======================================================================

print("=" * 70)
print("TEST 6 — EMBEDDING OUTPUT VALIDATION")
print("=" * 70)
print()

_, val_emb = timed_encode(model, ["book on wizards"])

print(f"Embedding shape : {val_emb.shape}")
print(f"Embedding dtype : {val_emb.dtype}")
print(f"Contains NaN    : {np.isnan(val_emb).any()}")
print(f"Contains Inf    : {np.isinf(val_emb).any()}")
emb_norm = np.linalg.norm(val_emb[0])
print(f"Embedding norm  : {emb_norm:.6f}")

assert val_emb.shape == (1, 384), (
    f"Expected (1, 384), got {val_emb.shape}"
)
assert val_emb.dtype == np.float32, (
    f"Expected float32, got {val_emb.dtype}"
)
assert not np.isnan(val_emb).any(), "Embedding contains NaN"
assert not np.isinf(val_emb).any(), "Embedding contains Inf"
assert abs(emb_norm - 1.0) < 0.01, (
    f"Norm is {emb_norm:.6f}, expected ~1.0"
)

print()
print("All validation checks passed.")
print()


# ======================================================================
# TEST 5 (cont.) — GPU MEMORY AFTER ALL TESTS
# ======================================================================

if cuda_available:
    print("=" * 70)
    print("GPU MEMORY — POST BENCHMARK")
    print("=" * 70)
    print()
    print(f"Memory allocated : {torch.cuda.memory_allocated(0) / 1024**2:.1f} MB")
    print(f"Memory reserved  : {torch.cuda.memory_reserved(0) / 1024**2:.1f} MB")
    print(f"Max allocated    : {torch.cuda.max_memory_allocated(0) / 1024**2:.1f} MB")
    print()


# ======================================================================
# FINAL SUMMARY
# ======================================================================

print("=" * 70)
print("ASTRALIB -- EMBEDDING PERFORMANCE SUMMARY")
print("=" * 70)
print()

gpu_name = torch.cuda.get_device_name(0) if cuda_available else "N/A"

print(f"Model                   : {MODEL_NAME}")
print(f"GPU                     : {gpu_name}")
print(f"CUDA                    : {'available' if cuda_available else 'NOT available'}")

if not cuda_available:
    print()
    print("  [!!] PyTorch was installed WITHOUT CUDA support.")
    print(f"       PyTorch build: {torch.__version__}")
    print("       All 'GPU' results above are actually CPU results.")
    print("       To enable CUDA, install the CUDA-enabled PyTorch build:")
    print("         pip install torch --index-url https://download.pytorch.org/whl/cu126")
    print("       (Replace cu126 with your CUDA toolkit version.)")

print()
print(f"GPU single-query (avg)  : {gpu_single_avg:.2f} ms")
print(f"GPU single-query (med)  : {gpu_single_med:.2f} ms")
print(f"CPU single-query (avg)  : {cpu_avg:.2f} ms")
print(f"CPU single-query (med)  : {cpu_med:.2f} ms")
print()
print(f"Best GPU batch throughput : {best_throughput:.0f} texts/sec")
print(f"Embedding dimension       : 384")
print(f"Model load                : {load_elapsed:.1f} sec")
print()

# ── Diagnosis ────────────────────────────────────────────────────────

print("=" * 70)
print("DIAGNOSIS")
print("=" * 70)
print()

if gpu_single_avg > 1000:
    print("[!] GPU inference latency is high; investigate model/device "
          "configuration.")
elif gpu_single_avg > cpu_avg:
    print("[!] GPU is not providing an advantage for single-sentence "
          "inference; investigate transfer/launch overhead.")
elif gpu_single_avg < cpu_avg * 0.5:
    print("[OK] GPU configuration is working correctly.")
else:
    print("[OK] GPU provides a modest advantage over CPU for single-query "
          "inference.")

if gpu_single_avg < 50:
    print("[OK] MiniLM inference is healthy; previous 1.35 s timing was "
          "likely caused by synchronisation / configuration / first-run "
          "overhead.")
elif gpu_single_avg < 200:
    print("[~] MiniLM latency is acceptable but could be optimised.")
else:
    print("[!] MiniLM latency is higher than expected; further "
          "investigation recommended.")

print()
print("=" * 70)
print("BENCHMARK COMPLETE")
print("=" * 70)
