"""Mine review-only same-book dense negatives from the frozen baseline index."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys

import faiss
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from rag_domain_common import CONTROL, TRAINING, controls, passage_pool

REVIEWED = TRAINING / "luminar" / "domain_qa_reviewed_v1.jsonl"
OUT = TRAINING / "luminar" / "domain_negative_candidates_v1.jsonl"
REPORT = TRAINING / "reports" / "rag_hard_negative_mining_v1.json"


def compact(text):
    return " ".join(text.casefold().split())


def safe_candidate(qa, row):
    if row["split"] != "TRAIN" or row["work_id"] != qa["work_id"]:
        return False, "WRONG_SPLIT_OR_BOOK"
    if row["chunk_id"] == qa["chunk_id"] or row["text"] == qa["positive_passage"]:
        return False, "SAME_POSITIVE"
    if row["source_start_char"] < qa["evidence_end"] and qa["evidence_start"] < row["source_end_char"]:
        return False, "EVIDENCE_OVERLAP"
    if abs(row["source_start_char"] - qa["evidence_start"]) < 300:
        return False, "TOO_CLOSE_TO_EVIDENCE"
    answer = compact(qa["short_answer"])
    if answer and answer in compact(row["text"]):
        return False, "ANSWER_TEXT_PRESENT"
    return True, "NEEDS_HUMAN_FALSE_NEGATIVE_REVIEW"


def main():
    _, split, _ = controls()
    if not REVIEWED.exists():
        raise RuntimeError("No human-reviewed QA exists; hard-negative mining is gated")
    reviewed = [json.loads(x) for x in REVIEWED.read_text(encoding="utf-8").splitlines() if x.strip()]
    train = [q for q in reviewed if q["split"] == "TRAIN" and q["review_status"] == "REVIEWED"]
    if not train:
        raise RuntimeError("No reviewed TRAIN QA; hard-negative mining is gated")
    if any(q["work_id"] not in split["train_work_ids"] for q in train):
        raise RuntimeError("Reviewed QA book outside TRAIN split")
    eligible, _ = passage_pool()
    allowed = {r["chunk_id"]: r for r in eligible if r["split"] == "TRAIN"}
    import pyarrow.parquet as pq
    all_rows = pq.read_table(CONTROL / "chunks.parquet", columns=["chunk_id", "work_id"]).to_pylist()
    by_book = {}
    for row in all_rows:
        by_book.setdefault(row["work_id"], []).append(row["chunk_id"])
    snapshots = sorted((Path.home() / ".cache" / "huggingface" / "hub" /
                        "models--sentence-transformers--all-MiniLM-L6-v2" / "snapshots").glob("*"))
    model = SentenceTransformer(str(snapshots[-1]), device="cuda" if torch.cuda.is_available() else "cpu",
                                local_files_only=True)
    indexes = {wid: faiss.read_index(str(CONTROL / "books" / f"{wid}.index"))
               for wid in {q["work_id"] for q in train}}
    for wid, index in indexes.items():
        if index.ntotal != len(by_book[wid]) or index.d != 384:
            raise RuntimeError(f"Frozen baseline index mismatch: {wid}")
    results, rejected = [], Counter()
    for qa in train:
        wid = qa["work_id"]
        vector = np.asarray(model.encode([qa["query"]], normalize_embeddings=True,
                                         convert_to_numpy=True), dtype="float32")
        scores, positions = indexes[wid].search(vector, 20)
        admitted = 0
        for rank, (position, score) in enumerate(zip(positions[0], scores[0]), 1):
            if position < 0:
                continue
            cid = by_book[wid][position]
            row = allowed.get(cid)
            if row is None:
                rejected["INELIGIBLE_SOURCE"] += 1
                continue
            safe, reason = safe_candidate(qa, row)
            if not safe:
                rejected[reason] += 1
                continue
            results.append({"negative_id": f"HN_{qa['candidate_id']}_{rank:02d}",
                            "candidate_id": qa["candidate_id"], "query": qa["query"],
                            "positive": qa["positive_passage"], "evidence": qa["evidence_text"],
                            "short_answer": qa["short_answer"], "negative": row["text"],
                            "negative_chunk_id": cid, "work_id": wid,
                            "book_title": row["title"], "chapter": row["chapter"],
                            "source_start": row["source_start_char"], "source_end": row["source_end_char"],
                            "source_hash": row["source_sha256"],
                            "baseline_rank": rank, "similarity": float(score),
                            "negative_type": "SAME_CHAPTER_WRONG_FACT" if row["chapter"] == qa["chapter"] else "SAME_BOOK_WRONG_EVENT",
                            "review_status": "UNREVIEWED", "validation_note": reason})
            admitted += 1
            if admitted >= 5:
                break
    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in results) + ("\n" if results else ""), encoding="utf-8")
    report = {"reviewed_train_queries": len(train), "negative_candidates": len(results),
              "queries_without_candidate": len(train) - len({r["candidate_id"] for r in results}),
              "auto_rejections": dict(rejected), "all_candidates_require_human_review": True}
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
