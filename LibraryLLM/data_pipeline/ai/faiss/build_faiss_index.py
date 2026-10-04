import argparse
import faiss
import numpy as np
import os
import time
from tqdm import tqdm

def build_index(embeddings_path, work_ids_path, output_dir):
    print(f"Loading work IDs from {work_ids_path}...")
    work_ids = np.load(work_ids_path, allow_pickle=True)
    
    print(f"Loading embeddings (mmap) from {embeddings_path}...")
    start_time = time.time()
    
    # 1. Load using mmap_mode="r"
    embeddings = np.load(embeddings_path, mmap_mode="r")
    
    # 3. Validate memory-mapped array shape and dtype
    if len(embeddings.shape) != 2:
        raise ValueError(f"Expected 2D array, got shape {embeddings.shape}")
        
    print(f"Embeddings shape: {embeddings.shape}, dtype: {embeddings.dtype}")
    
    # Vector count matches work_ids
    if len(embeddings) != len(work_ids):
        raise ValueError(f"Length mismatch: {len(embeddings)} embeddings vs {len(work_ids)} work_ids")
        
    # Duplicate work ID check
    if len(set(work_ids)) != len(work_ids):
        raise ValueError("Duplicate work IDs found!")
        
    # Dimension check
    dim = embeddings.shape[1]
    print(f"Dimension: {dim}")
    
    print("Building IndexFlatIP...")
    # 4. Build index
    base_index = faiss.IndexFlatIP(dim)
    
    if np.issubdtype(work_ids.dtype, np.integer):
        index = faiss.IndexIDMap(base_index)
    else:
        print("work_ids are not integers. Storing them implicitly by order.")
        index = base_index
        
    print(f"Adding vectors in chunks...")
    
    # 5 & 6. Add in chunks with tqdm
    for start in tqdm(range(0, len(embeddings), 100_000), desc="Indexing"):
        end = min(start + 100_000, len(embeddings))
        
        # Load chunk into memory, cast to float32
        chunk = np.ascontiguousarray(
            embeddings[start:end],
            dtype=np.float32
        )
        
        # Check for NaN or Inf in chunk
        if np.isnan(chunk).any() or np.isinf(chunk).any():
            raise ValueError(f"NaN or Inf found in chunk {start}:{end}")
            
        # Normalization check (sample first row of chunk)
        norm = np.linalg.norm(chunk[0])
        if not np.isclose(norm, 1.0, atol=1e-2):
            faiss.normalize_L2(chunk)
            
        if np.issubdtype(work_ids.dtype, np.integer):
            chunk_ids = work_ids[start:end].astype(np.int64)
            index.add_with_ids(chunk, chunk_ids)
        else:
            index.add(chunk)
            
    print(f"Index built with {index.ntotal} vectors in {time.time() - start_time:.2f}s")
    
    os.makedirs(output_dir, exist_ok=True)
    index_path = os.path.join(output_dir, "faiss.index")
    
    # 10. Save with write_index
    faiss.write_index(index, index_path)
    print(f"Index saved to {index_path}")
    
    if not np.issubdtype(work_ids.dtype, np.integer):
        ids_path = os.path.join(output_dir, "index_work_ids.npy")
        np.save(ids_path, work_ids)
        print(f"Saved sequential work_ids to {ids_path}")
        
    # 11. Reload and verify
    print("Reloading index to verify...")
    reloaded_index = faiss.read_index(index_path)
    print(f"Reloaded index vectors: {reloaded_index.ntotal}")
    print(f"Reloaded index dimension: {reloaded_index.d}")
    
    if reloaded_index.ntotal != len(embeddings):
        raise ValueError(f"Verification failed: expected {len(embeddings)} vectors, got {reloaded_index.ntotal}")
    if reloaded_index.d != dim:
        raise ValueError(f"Verification failed: expected dimension {dim}, got {reloaded_index.d}")
    
    print("Verification passed successfully.")

def main():
    parser = argparse.ArgumentParser(description="Build FAISS Index")
    parser.add_argument("--embeddings", type=str, required=True, help="Path to embeddings.npy")
    parser.add_argument("--work-ids", type=str, required=True, help="Path to work_ids.npy")
    parser.add_argument("--output-dir", type=str, required=True, help="Output directory for index")
    
    args = parser.parse_args()
    build_index(args.embeddings, args.work_ids, args.output_dir)

if __name__ == "__main__":
    main()
