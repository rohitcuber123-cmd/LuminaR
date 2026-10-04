import time
import numpy as np

from metadata_store import MetadataStore


DB_PATH = r"D:\SDC\LibraryLLM\datasets\ai\metadata\book_metadata.duckdb"
IDS_PATH = r"D:\SDC\LibraryLLM\datasets\ai\faiss\hnsw\index_work_ids.npy"


ids = np.load(
    IDS_PATH,
    allow_pickle=True
)[:50].tolist()


store = MetadataStore(DB_PATH)

print("Testing get_text_by_work_ids()")
print("IDs:", len(ids))

# Warm-up
for _ in range(5):
    store.get_rerank_text_by_work_ids(ids)

times = []

for i in range(20):
    start = time.perf_counter()

    result = store.get_rerank_text_by_work_ids(ids)

    elapsed = (time.perf_counter() - start) * 1000
    times.append(elapsed)

    print(f"{i + 1:2d}: {elapsed:.2f} ms")

print()
print("=" * 50)
print(f"Average : {np.mean(times):.2f} ms")
print(f"Median  : {np.median(times):.2f} ms")
print(f"Min     : {np.min(times):.2f} ms")
print(f"Max     : {np.max(times):.2f} ms")
print(f"Records : {len(result)}")
print("=" * 50)

store.close()