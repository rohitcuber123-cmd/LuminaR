"""Deterministic quality and evaluation-query leakage audit for generic pilot pairs."""
from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher
import json
from pathlib import Path
import random
import re

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "datasets" / "training"
LABELS = ROOT / "rag" / "evaluation" / "rag_retrieval_eval_v1.json"


def canonical(text: str) -> str:
    return re.sub(r"\W+", "", text, flags=re.UNICODE).casefold()


def audit_one(name: str, questions: list[str]) -> dict:
    path = TRAIN / "processed" / f"{name}_pairs_v1.parquet"
    rows = pq.read_table(path).to_pylist()
    sampled = random.Random(42).sample(range(len(rows)), min(100, len(rows)))
    failures = Counter()
    seen = set()
    suspicious = []
    for i, row in enumerate(rows):
        query, passage, answer = row["query"], row["positive"], row["answer"]
        if not query.strip() or not passage.strip():
            failures["empty"] += 1
        if canonical(answer) not in canonical(passage):
            failures["answer_absent"] += 1
        if not (15 <= row["token_count"] <= 220):
            failures["token_count_invalid"] += 1
        if re.search(r"</?[A-Za-z][^<>]*>|&(?:[A-Za-z]+|#\d+);", passage):
            failures["markup"] += 1
        key = (canonical(query), canonical(passage))
        if key in seen:
            failures["duplicate"] += 1
        seen.add(key)
        near = max((SequenceMatcher(None, query.casefold(), q.casefold()).ratio() for q in questions), default=0)
        if near >= 0.85:
            suspicious.append({"row": i, "query": query, "similarity": round(near, 3)})
    review = []
    for i in sampled:
        row = rows[i]
        review.append({"row": i, "source_id": row["source_id"],
                       "query": row["query"], "answer": row["answer"],
                       "positive": row["positive"], "token_count": row["token_count"],
                       "answer_visible": canonical(row["answer"]) in canonical(row["positive"])})
    return {"rows": len(rows), "sample_size": len(sampled), "automated_failures": dict(failures),
            "near_evaluation_queries": suspicious, "sample": review}


def main():
    questions = [q["question"] for q in json.loads(LABELS.read_text(encoding="utf-8"))["questions"]]
    result = {name: audit_one(name, questions) for name in ("squad", "nq")
              if (TRAIN / "processed" / f"{name}_pairs_v1.parquet").exists()}
    out = TRAIN / "reports" / "rag_generic_training_data_review.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# Generic pilot pair review", "", "Automated checks plus deterministic 100-row samples are in the JSON companion. Human semantic review remains required before scaled training.", ""]
    for name, report in result.items():
        lines += [f"## {name}", "", f"Rows: {report['rows']}; sampled: {report['sample_size']}; automated failures: {report['automated_failures']}; near evaluation queries: {len(report['near_evaluation_queries'])}.", ""]
        for row in report["sample"][:10]:
            lines += [f"- {row['source_id']}: {row['query']} | answer: {row['answer']} | visible: {row['answer_visible']}"]
        lines.append("")
    (TRAIN / "reports" / "rag_generic_training_data_review.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({k: {"rows": v["rows"], "automated_failures": v["automated_failures"],
                          "near_evaluation_queries": len(v["near_evaluation_queries"])}
                      for k, v in result.items()}, indent=2))
    if any(v["automated_failures"] or v["near_evaluation_queries"] for v in result.values()):
        raise SystemExit("Generic pair audit found issues; inspect report before training")


if __name__ == "__main__":
    main()
