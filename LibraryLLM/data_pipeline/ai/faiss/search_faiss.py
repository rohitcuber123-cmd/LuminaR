import argparse
import faiss
import numpy as np
import os
import sys
import duckdb
import torch
import warnings

# Suppress noisy sentence_transformers warnings
warnings.filterwarnings("ignore", category=FutureWarning)
from sentence_transformers import SentenceTransformer

PARQUET_PATH = "D:/SDC/LibraryLLM/datasets/ai/search/search_corpus.parquet"

class FaissSearcher:
    def __init__(self, index_dir):
        self.index_path = os.path.join(index_dir, "faiss.index")
        self.ids_path = os.path.join(index_dir, "index_work_ids.npy")
        
        if not os.path.exists(self.index_path):
            raise FileNotFoundError(f"FAISS index not found at {self.index_path}")
        if not os.path.exists(self.ids_path):
            raise FileNotFoundError(f"Work IDs mapping not found at {self.ids_path}")
            
        self.index = faiss.read_index(self.index_path)
        self.work_ids = np.load(self.ids_path, allow_pickle=True)
        
    def search(self, query_vector, top_k=10):
        # Query vector must be normalized for IP
        query_vector = np.array(query_vector, dtype=np.float32)
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)
            
        if query_vector.shape[1] != self.index.d:
            raise ValueError(f"Query vector dimension ({query_vector.shape[1]}) does not match index dimension ({self.index.d})")
            
        faiss.normalize_L2(query_vector)
        
        distances, indices = self.index.search(query_vector, top_k)
        
        results = []
        for rank, (dist, idx) in enumerate(zip(distances[0], indices[0]), start=1):
            if idx == -1:
                continue
                
            work_id = self.work_ids[idx]
            results.append({
                "rank": rank,
                "work_id": str(work_id),
                "score": float(dist),
                "faiss_index": int(idx)
            })
            
        return results

def get_metadata(work_ids):
    if not os.path.exists(PARQUET_PATH):
        raise FileNotFoundError(f"Search corpus Parquet file not found at {PARQUET_PATH}")
        
    if not work_ids:
        return {}
        
    conn = duckdb.connect()
    
    # Generate placeholders for the IN clause
    placeholders = ", ".join(["?"] * len(work_ids))
    
    query = f"""
        SELECT work_id, title, authors, subjects, description, average_rating, rating_count, reading_log_count
        FROM read_parquet('{PARQUET_PATH}')
        WHERE work_id IN ({placeholders})
    """
    
    rows = conn.execute(query, work_ids).fetchall()
    columns = [desc[0] for desc in conn.description]
    
    metadata_by_id = {}
    for row in rows:
        work_id = row[0]
        metadata_by_id[work_id] = {col: val for col, val in zip(columns, row)}
        
    return metadata_by_id

def main():
    parser = argparse.ArgumentParser(description="Search FAISS Index")
    parser.add_argument("--index-dir", type=str, required=True, help="Directory containing the index")
    parser.add_argument("--query", type=str, required=True, help="Natural language query")
    parser.add_argument("--top-k", type=int, default=10, help="Number of results to return")
    parser.add_argument("--k", type=int, dest="top_k", help="Alias for --top-k")
    parser.add_argument("--with-metadata", action="store_true", help="Fetch metadata from DuckDB")
    
    args = parser.parse_args()
    
    try:
        searcher = FaissSearcher(args.index_dir)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
        
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = SentenceTransformer('all-MiniLM-L6-v2', device=device)
    
    # Encode natural-language query
    query_vector = model.encode(args.query)
    
    try:
        results = searcher.search(query_vector, top_k=args.top_k)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
        
    if args.with_metadata:
        work_ids = [res["work_id"] for res in results]
        try:
            metadata_by_id = get_metadata(work_ids)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
            
        for res in results:
            res["metadata"] = metadata_by_id.get(res["work_id"], {})

    print("=" * 60)
    print("ASTRA LIB - SEMANTIC SEARCH")
    print("=" * 60)
    print(f"\nQuery: {args.query}")
    print("Model: all-MiniLM-L6-v2")
    print(f"Results: {len(results)}\n")
    
    for res in results:
        print("-" * 60)
        print(f"Rank {res['rank']}")
        print(f"Work ID: {res['work_id']}")
        print(f"Score: {res['score']:.4f}")
        
        if args.with_metadata:
            meta = res.get("metadata", {})
            print(f"Title: {meta.get('title', 'N/A')}")
            print(f"Authors: {meta.get('authors', 'N/A')}")
            print(f"Subjects: {meta.get('subjects', 'N/A')}")
            print(f"Rating: {meta.get('average_rating', 'N/A')}")
            
    print("-" * 60)

if __name__ == "__main__":
    main()
