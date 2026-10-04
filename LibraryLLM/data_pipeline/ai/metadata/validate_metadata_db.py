"""
AstraLib — Validate Metadata Database (Phase 11)

Ensures that the new DuckDB metadata backend returns the exact same data
as the original Parquet backend.

Test query: "a mystery novel set in Victorian London"
"""

import os
import sys

# Add the parent directory so we can import from data_pipeline
sys.path.append(os.path.abspath("D:/SDC/LibraryLLM"))

from data_pipeline.ai.faiss.search_hnsw import (
    HNSWSearcher,
    _get_metadata_parquet,
    _get_metadata_duckdb,
    MODEL_NAME,
)
from sentence_transformers import SentenceTransformer

# ======================================================================
# CONFIGURATION
# ======================================================================

INDEX_DIR = "D:/SDC/LibraryLLM/datasets/ai/faiss/hnsw"
DB_PATH   = "D:/SDC/LibraryLLM/datasets/ai/metadata/book_metadata.duckdb"
TEST_QUERY = "a mystery novel set in Victorian London"
TOP_K     = 10

# ======================================================================
# MAIN
# ======================================================================

def main():

    print("=" * 70)
    print("ASTRALIB — METADATA VALIDATION (Phase 11)")
    print("=" * 70)
    print()

    # 1. Load Model & Index
    print("Loading model and index ...")
    model = SentenceTransformer(MODEL_NAME, device="cpu")
    searcher = HNSWSearcher(INDEX_DIR, ef_search=128)
    
    # 2. Search
    print(f"Query: '{TEST_QUERY}'")
    query_vector = model.encode(TEST_QUERY, convert_to_numpy=True, normalize_embeddings=True)
    results = searcher.search(query_vector, top_k=TOP_K)
    
    work_ids = [r["work_id"] for r in results]
    print(f"Retrieved {len(work_ids)} work IDs from HNSW.")
    
    # 3. Fetch from both backends
    print("\nFetching metadata from Parquet backend ...")
    meta_parquet = _get_metadata_parquet(work_ids)
    
    print("Fetching metadata from DuckDB DB backend ...")
    meta_duckdb = _get_metadata_duckdb(work_ids, DB_PATH)
    
    print("\nValidating results ...\n")
    
    fields_to_check = [
        "title",
        "authors",
        "subjects",
        "average_rating",
    ]
    
    all_passed = True
    
    for rank, result in enumerate(results, start=1):
        wid = result["work_id"]
        score = result["score"]
        
        print(f"[{rank}] Work ID: {wid}  (Score: {score:.4f})")
        
        p_data = meta_parquet.get(wid, {})
        d_data = meta_duckdb.get(wid, {})
        
        # Check presence
        if not p_data and not d_data:
            print("  -> WARNING: Missing in both backends.")
            continue
        elif not p_data:
            print("  -> FAIL: Found in DB, missing in Parquet.")
            all_passed = False
            continue
        elif not d_data:
            print("  -> FAIL: Found in Parquet, missing in DB.")
            all_passed = False
            continue
            
        # Field comparison
        for field in fields_to_check:
            val_p = p_data.get(field)
            val_d = d_data.get(field)
            
            # Handle NaNs / None equivalence if necessary, but DuckDB usually returns None
            if val_p != val_d:
                # Some float precision might differ slightly? Ratings should be exact.
                if isinstance(val_p, float) and isinstance(val_d, float):
                    if abs(val_p - val_d) > 1e-5:
                        print(f"  -> FAIL: {field} mismatch. Parquet={val_p} vs DB={val_d}")
                        all_passed = False
                else:
                    print(f"  -> FAIL: {field} mismatch. Parquet={val_p} vs DB={val_d}")
                    all_passed = False
        
        if all_passed:
             # Just show title so user knows it worked
             title = d_data.get("title", "N/A")
             print(f"  -> PASS  ({title[:50]}...)")
             
        print()
    
    print("=" * 70)
    if all_passed:
        print("SUCCESS: DuckDB Database backend perfectly matches Parquet backend.")
    else:
        print("FAILED : Mismatches detected between backends.")
    print("=" * 70)


if __name__ == "__main__":
    main()

