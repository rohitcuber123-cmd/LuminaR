import argparse
import faiss
import os
import numpy as np

def verify_index(index_dir):
    index_path = os.path.join(index_dir, "faiss.index")
    if not os.path.exists(index_path):
        print(f"Error: Index file not found at {index_path}")
        return False
        
    print(f"Loading index from {index_path}...")
    try:
        index = faiss.read_index(index_path)
        print("Successfully loaded index.")
        print(f"Index type: {type(index)}")
        print(f"Dimension: {index.d}")
        print(f"Total vectors: {index.ntotal}")
        print(f"Is trained: {index.is_trained}")
        print(f"Metric type: {index.metric_type}")
        
        ids_path = os.path.join(index_dir, "index_work_ids.npy")
        if os.path.exists(ids_path):
            work_ids = np.load(ids_path, allow_pickle=True)
            print(f"Loaded sequential work_ids mapping: {len(work_ids)} elements")
            if len(work_ids) != index.ntotal:
                print(f"WARNING: ID count ({len(work_ids)}) does not match vector count ({index.ntotal})!")
            else:
                print("ID mapping count matches vector count.")
                
        return True
    except Exception as e:
        print(f"Failed to load or verify index: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Verify FAISS Index")
    parser.add_argument("--index-dir", type=str, required=True, help="Directory containing the index")
    args = parser.parse_args()
    
    verify_index(args.index_dir)

if __name__ == "__main__":
    main()
