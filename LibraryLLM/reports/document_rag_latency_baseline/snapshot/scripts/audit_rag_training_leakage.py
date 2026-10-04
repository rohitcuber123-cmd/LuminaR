"""Check generic pairs and domain split against protected TEST source text."""
from __future__ import annotations

import json
from pathlib import Path
import re

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "datasets" / "training"
CHUNKS = ROOT / "datasets" / "rag_experiments" / "chunking_v1" / "tokens_220" / "chunks.parquet"


def words(text):
    return re.findall(r"\w+", text.casefold())


def shingles(text, n=12):
    w = words(text)
    return {tuple(w[i:i+n]) for i in range(len(w) - n + 1)}


def main():
    split = json.loads((TRAIN / "reports" / "rag_training_decontamination_v1.json").read_text(encoding="utf-8"))
    protected = set(split["protected_test_work_ids"])
    if protected & set(split["train_work_ids"]) or protected & set(split["validation_work_ids"]):
        raise RuntimeError("Protected TEST book leaked into domain split")
    rows = pq.read_table(CHUNKS, columns=["work_id", "text"]).to_pylist()
    test_shingles = set()
    for row in rows:
        if row["work_id"] in protected:
            test_shingles.update(shingles(row["text"]))
    overlap = []
    counts = {}
    for name in ("nq", "squad"):
        pairs = pq.read_table(TRAIN / "processed" / f"{name}_pairs_v1.parquet",
                              columns=["source_id", "positive"]).to_pylist()
        counts[name] = len(pairs)
        for row in pairs:
            matches = shingles(row["positive"]) & test_shingles
            if matches:
                overlap.append({"source": name, "source_id": row["source_id"],
                                "matching_12_word_shingles": len(matches)})
    report = {"protected_test_work_ids": sorted(protected), "generic_pair_counts": counts,
              "test_chunk_count": sum(r["work_id"] in protected for r in rows),
              "test_12_word_shingles": len(test_shingles),
              "generic_test_overlap": overlap,
              "status": "PASS" if not overlap else "FAIL"}
    out = TRAIN / "reports" / "rag_generic_test_leakage_v1.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("generic_pair_counts", "test_chunk_count", "generic_test_overlap", "status")}, indent=2))
    if overlap:
        raise RuntimeError("Generic pilot contaminated by protected TEST text")


if __name__ == "__main__":
    main()
