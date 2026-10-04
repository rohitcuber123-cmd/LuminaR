"""Evaluate dense-preserving 50→80 candidate union on DEV for B pilot."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import faiss
import numpy as np
import pyarrow.parquet as pq
import torch
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rag.evaluation.metrics import evaluate_query
from rag.evidence import generate_expanded_queries
from scripts.evaluate_rag_candidate_union_v2 import full_pool, pool_summary, union

TRAIN = ROOT / "datasets" / "training"
CONTROL = ROOT / "datasets" / "rag_experiments" / "chunking_v1" / "tokens_220"


def main():
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise RuntimeError("Set PYTHONHASHSEED=0 for deterministic query expansion")
    model = SentenceTransformer(str(TRAIN / "models" / "minilm_generic_pilot_v1"),
                                device="cuda" if torch.cuda.is_available() else "cpu", local_files_only=True)
    rows = pq.read_table(CONTROL / "chunks.parquet", columns=["chunk_id", "work_id",
                                                              "source_start_char", "source_end_char"]).to_pylist()
    by_book = {}
    for r in rows:
        by_book.setdefault(r["work_id"], []).append(r)
    questions = [q for q in json.loads((ROOT / "rag" / "evaluation" / "rag_retrieval_eval_v1.json").read_text(encoding="utf-8"))["questions"]
                 if q["split"] == "DEV"]
    root = TRAIN / "evaluation_indexes" / "minilm_generic_pilot_v1"
    dense_rows = {r["query_id"]: r for r in json.loads((root / "dense_dev_evaluation.json").read_text(encoding="utf-8"))["queries"]}
    indexes = {wid: faiss.read_index(str(root / "books" / f"{wid}.index")) for wid in {q["work_id"] for q in questions}}
    records = []
    for q in questions:
        wid = q["work_id"]
        book = by_book[wid]
        index = indexes[wid]
        def search(text, limit):
            vector = np.asarray(model.encode([text], normalize_embeddings=True,
                                             convert_to_numpy=True), dtype="float32")
            _, pos = index.search(vector, limit)
            return [book[p]["chunk_id"] for p in pos[0] if p >= 0]
        dense = search(q["question"], 50)
        if dense != [r["chunk_id"] for r in dense_rows[q["query_id"]]["top50"]]:
            raise RuntimeError(f"Dense ranking changed for {q['query_id']}")
        expanded = []
        for text in generate_expanded_queries(q["question"]):
            for cid in search(text, 15):
                if cid not in expanded:
                    expanded.append(cid)
        expanded = expanded[:40]
        pool = union(dense, expanded, preserve=50, cap=80)
        chunks = {r["chunk_id"]: {"start": r["source_start_char"],
                                   "end": r["source_end_char"]} for r in book}
        scored = {"raw_dense": dense, "union_50_80": pool}
        records.append({"query_id": q["query_id"], "work_id": wid, "split": "DEV",
                        "pools": {name: {"count": len(ids), "ids": ids,
                                         "metrics": evaluate_query(q, ids, chunks),
                                         "full": full_pool(q, ids, chunks)}
                                  for name, ids in scored.items()}})
    result = {"result_label": "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS",
              "model": "B_GENERIC_PILOT", "split": "DEV", "queries": records,
              "summary": {name: pool_summary(records, name) for name in ("raw_dense", "union_50_80")}}
    out = TRAIN / "reports" / "minilm_generic_pilot_union_dev_v1.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
