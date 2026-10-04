"""Read-only integrity check for the fixed V7 pilot artifacts."""
from __future__ import annotations

from collections import Counter
import json

import pyarrow.parquet as pq

from rag_domain_common import CONTROL, TRAINING, controls


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def validate():
    _, split, labels = controls()
    base = TRAINING / "luminar" / "domain_qa_assisted_v7_"
    raw = read_jsonl(base.with_name(base.name + "raw.jsonl"))
    auto = read_jsonl(base.with_name(base.name + "auto_checked.jsonl"))
    rejected = read_jsonl(base.with_name(base.name + "rejected.jsonl"))
    generation = json.loads((TRAINING / "reports" / "rag_domain_qa_assisted_v7_generation.json").read_text(encoding="utf-8"))
    chunks = {(r["work_id"], r["chunk_id"]): r for r in pq.read_table(CONTROL / "chunks.parquet").to_pylist()}
    assert len(raw) == 50 and [r["passage_index"] for r in raw] == list(range(1, 51))
    assert generation["passages"] == 50 and generation["seed"] == 503
    assert len({(r["work_id"], r["chunk_id"]) for r in raw}) == 50
    eval_spans = {}
    for q in labels:
        eval_spans.setdefault(q["work_id"], []).extend(p for p in q["accepted_passages"] if p["relevance_grade"] == 2)
    for r in raw:
        assert r["work_id"] in split["train_work_ids"]
        assert r["work_id"] not in split["protected_test_work_ids"]
        chunk = chunks[(r["work_id"], r["chunk_id"])]
        assert (r["source_start"], r["source_end"]) == (chunk["source_start_char"], chunk["source_end_char"])
        assert not any(r["source_start"] < p["source_end"] and p["source_start"] < r["source_end"]
                       for p in eval_spans.get(r["work_id"], []))
        assert len(r["candidate_ids"]) <= 2
    ids = [candidate_id for r in raw for candidate_id in r["candidate_ids"]]
    assert len(ids) == len(set(ids)) == generation["summary"]["raw_generated_QA"]
    found = [r["candidate_id"] for r in auto + rejected if r.get("candidate_id")]
    assert sorted(found) == sorted(ids)
    assert len(rejected) == len(ids) + generation["summary"].get("format_failures", 0) - len(auto)
    assert len(auto) == generation["summary"].get("AUTO_CHECKED", 0)
    assert all(r["review_status"] == "AUTO_CHECKED" and not r["reviewer"] and not r["review_date"] for r in auto)
    assert all(r.get("review_status") != "REVIEWED" for r in rejected)
    return {"selected_train_passages": len(raw), "raw_generated_QA": len(ids),
            "auto_checked": len(auto), "rejected_records": len(rejected),
            "format_failures": generation["summary"].get("format_failures", 0),
            "test_leakage": 0, "evaluation_span_leakage": 0,
            "review_packet_gate_passed": len(auto) >= 20}


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
