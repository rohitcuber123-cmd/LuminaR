import time
import requests
import numpy as np


# ============================================================
# CONFIG
# ============================================================

URL = "http://127.0.0.1:8001/search"

QUERY = "books for learning deep learning and neural networks"

TOP_K = 10
ITERATIONS = 20


# ============================================================
# REQUEST
# ============================================================

payload = {
    "query": QUERY,
    "top_k": TOP_K
}


print("=" * 70)
print("LUMINAR — API LATENCY BENCHMARK")
print("=" * 70)

print(f"URL        : {URL}")
print(f"Query      : {QUERY}")
print(f"Top-K      : {TOP_K}")
print(f"Iterations : {ITERATIONS}")


# ============================================================
# HEALTH CHECK
# ============================================================

print()
print("Checking API...")

response = requests.get(
    "http://127.0.0.1:8001/health",
    timeout=10
)

response.raise_for_status()

print("API is healthy.")


# ============================================================
# WARM-UP
# ============================================================

print()
print("=" * 70)
print("API WARM-UP")
print("=" * 70)

for i in range(5):

    response = requests.post(
        URL,
        json=payload,
        timeout=30
    )

    response.raise_for_status()

print("Warm-up complete.")


# ============================================================
# BENCHMARK
# ============================================================

print()
print("=" * 70)
print("BENCHMARK")
print("=" * 70)

times = []

last_result = None

for i in range(ITERATIONS):

    start = time.perf_counter()

    response = requests.post(
        URL,
        json=payload,
        timeout=30
    )

    elapsed = (
        time.perf_counter() - start
    ) * 1000

    response.raise_for_status()

    result = response.json()

    times.append(elapsed)

    last_result = result

    print(
        f"[{i + 1:02d}/{ITERATIONS}] "
        f"Total: {elapsed:8.2f} ms"
    )


# ============================================================
# STATISTICS
# ============================================================

times = np.array(times)

print()
print("=" * 70)
print("API LATENCY RESULTS")
print("=" * 70)

print()
print(f"Average : {np.mean(times):8.2f} ms")
print(f"Median  : {np.median(times):8.2f} ms")
print(
    f"P95     : "
    f"{np.percentile(times, 95):8.2f} ms"
)
print(f"Minimum : {np.min(times):8.2f} ms")
print(f"Maximum : {np.max(times):8.2f} ms")


# ============================================================
# SERVER-SIDE TIMING
# ============================================================

server_times = last_result["timing_ms"]

print()
print("=" * 70)
print("LAST SERVER-SIDE SEARCH")
print("=" * 70)

print(
    f"Embedding          : "
    f"{server_times['embedding']:.2f} ms"
)

print(
    f"HNSW               : "
    f"{server_times['hnsw']:.2f} ms"
)

print(
    f"Candidate metadata  : "
    f"{server_times['candidate_metadata']:.2f} ms"
)

print(
    f"Pair construction   : "
    f"{server_times['pair_construction']:.2f} ms"
)

print(
    f"Reranking           : "
    f"{server_times['reranking']:.2f} ms"
)

print(
    f"Final metadata      : "
    f"{server_times['final_metadata']:.2f} ms"
)

print(
    f"Server total        : "
    f"{server_times['total']:.2f} ms"
)


# ============================================================
# COMPLETE
# ============================================================

print()
print("=" * 70)
print("API BENCHMARK COMPLETE")
print("=" * 70)