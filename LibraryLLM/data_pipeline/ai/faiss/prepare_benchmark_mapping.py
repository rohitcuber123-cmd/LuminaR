import argparse
import numpy as np
import json
import os

def prepare_mapping(work_ids_path, output_path):
    """
    Creates a mapping from FAISS index (integer) to work_id (string).
    """
    print(f"Loading work IDs from {work_ids_path}...")
    work_ids = np.load(work_ids_path, allow_pickle=True)
    
    mapping = {i: str(work_id) for i, work_id in enumerate(work_ids)}
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f)
        
    print(f"Saved mapping for {len(mapping)} items to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Prepare FAISS to work_id mapping")
    parser.add_argument("--work-ids", type=str, required=True, help="Path to work_ids.npy")
    parser.add_argument("--output", type=str, required=True, help="Path to output mapping.json")
    
    args = parser.parse_args()
    prepare_mapping(args.work_ids, args.output)

if __name__ == "__main__":
    main()
