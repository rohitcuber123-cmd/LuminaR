import argparse
import faiss
import numpy as np
import time
import os
import sys
from tqdm import tqdm

def main():
    parser = argparse.ArgumentParser(description="FAISS Performance Benchmark")
    parser.add_argument("--index-dir", required=True, type=str, help="Directory containing the index")
    parser.add_argument("--embeddings", required=True, type=str, help="Path to embeddings numpy file")
    parser.add_argument("--queries", type=int, default=100, help="Number of queries to benchmark")
    parser.add_argument("--threads", type=int, default=os.cpu_count(), help="Number of CPU threads")
    
    args = parser.parse_args()
    
    if args.threads is not None:
        faiss.omp_set_num_threads(args.threads)
    
    index_path = os.path.join(args.index_dir, "faiss.index")
    if not os.path.exists(index_path):
        print(f"Error: FAISS index not found at {index_path}")
        sys.exit(1)
        
    index = faiss.read_index(index_path)
    
    if index.ntotal != 5000000:
        print(f"Warning: index.ntotal is {index.ntotal}, expected 5,000,000")
    if index.d != 384:
        print(f"Warning: index.d is {index.d}, expected 384")
        
    if not os.path.exists(args.embeddings):
        print(f"Error: Embeddings file not found at {args.embeddings}")
        sys.exit(1)
        
    # Do NOT load the complete embedding array into RAM
    embeddings = np.load(args.embeddings, mmap_mode="r")
    
    # Select random queries
    np.random.seed(42)
    total_vectors = embeddings.shape[0]
    
    if args.queries > total_vectors:
        print(f"Error: Requested {args.queries} queries but only {total_vectors} available")
        sys.exit(1)
        
    query_indices = np.random.choice(total_vectors, size=args.queries, replace=False)
    
    query_vectors = []
    for idx in query_indices:
        vec = embeddings[idx]
        # ensure contiguous float32 and shape (1, d)
        vec = np.ascontiguousarray(vec, dtype=np.float32).reshape(1, -1)
        query_vectors.append(vec)
        
    # Warm up the FAISS index before measuring
    _ = index.search(query_vectors[0], 10)
    
    print("=" * 70)
    print("ASTRALIB - FAISS PERFORMANCE BENCHMARK")
    print("=" * 70)
    print()
    print("Index:")
    print("  Type       : IndexFlatIP")
    print(f"  Vectors    : {index.ntotal:,}")
    print(f"  Dimension  : {index.d}")
    print("  Metric     : Inner Product")
    print()
    print(f"Queries     : {args.queries}")
    print(f"Hardware    : CPU")
    print()
    
    top_ks = [10, 50, 100]
    for top_k in top_ks:
        print("=" * 70)
        print(f"TOP-K = {top_k}")
        print("=" * 70)
        print()
        
        latencies = []
        for q in tqdm(query_vectors, desc=f"Benchmarking top_k={top_k}", leave=False, unit="query", ncols=80):
            start_t = time.perf_counter()
            index.search(q, top_k)
            end_t = time.perf_counter()
            latencies.append((end_t - start_t) * 1000) # convert to ms
            
        avg_lat = np.mean(latencies)
        med_lat = np.median(latencies)
        min_lat = np.min(latencies)
        max_lat = np.max(latencies)
        p95_lat = np.percentile(latencies, 95)
        
        # QPS = 1000 ms / average latency in ms
        qps = 1000.0 / avg_lat if avg_lat > 0 else 0
        
        print(f"Average     : {avg_lat:.2f} ms")
        print(f"Median      : {med_lat:.2f} ms")
        print(f"P95         : {p95_lat:.2f} ms")
        print(f"Minimum     : {min_lat:.2f} ms")
        print(f"Maximum     : {max_lat:.2f} ms")
        print(f"QPS         : {qps:.2f}")
        print()

if __name__ == "__main__":
    main()
