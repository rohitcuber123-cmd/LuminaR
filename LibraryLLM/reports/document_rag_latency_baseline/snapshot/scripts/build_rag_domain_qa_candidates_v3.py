"""Bounded 50-chunk deterministic v3 QA pilot; no model training or review admission."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import random

from rag_domain_common import ROOT, SOURCE_MAP, TRAINING, controls, passage_pool
from rag_domain_qa_v2 import classify_passage_v2
from rag_domain_qa_v3 import extract_chunk, validate_v3
from probe_rag_domain_qa_v3 import scan


def select_balanced(pool, seed):
    rng = random.Random(seed)
    groups = defaultdict(list)
    for item in pool:
        groups[item[0]["work_id"]].append(item)
    books = sorted(groups)
    if len(books) != 12: raise RuntimeError("Expected 12 TRAIN books")
    rng.shuffle(books)
    for group in groups.values():
        rng.shuffle(group)
        group.sort(key=lambda item: (any(x["extractor_confidence"] == "HIGH" for x in item[1]),
                                     bool(item[1])), reverse=True)
    selected = []
    for i in range(50):
        wid = books[i % len(books)]
        selected.append(groups[wid][i // len(books)])
    assert len({x[0]["chunk_id"] for x in selected}) == 50
    return selected


def save_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + ("\n" if rows else ""),
                    encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--precision", default="high")
    args = ap.parse_args()
    if args.chunks != 50 or args.precision != "high":
        raise ValueError("The v3 pilot permits exactly 50 chunks, high precision")
    probe = json.loads((TRAINING / "reports" / "rag_domain_qa_v3_extractor_probe.json").read_text(encoding="utf-8"))
    if not probe.get("pilot_allowed") or not probe.get("automated_structural_gate"):
        raise RuntimeError("20-chunk extractor probe gate has not passed")
    outbase = TRAINING / "luminar"
    outputs = {k: outbase / f"domain_qa_v3_{k}.jsonl" for k in
               ("high_confidence", "medium_low", "rejected", "attempts")}
    if any(x.exists() for x in outputs.values()):
        raise RuntimeError("v3 pilot outputs already exist; refusing to overwrite")
    _, split, labels = controls()
    rows, quality = passage_pool(classifier=classify_passage_v2)
    selected = select_balanced(scan(rows), args.seed)
    mapping = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    sources = {wid: (ROOT / mapping[wid]["source_file"]).read_text(encoding="utf-8")
               for wid in {x[0]["work_id"] for x in selected}}
    eval_queries = [x["question"] for x in labels]
    seen_fp, seen_questions = set(), []
    auto, medium, rejected, attempts = [], [], [], []
    stats, reasons, relations = Counter(), Counter(), defaultdict(Counter)
    for row, candidates, segmentation in selected:
        stats["source_chunks_attempted"] += 1
        stats["sentences_examined"] += segmentation["sentences"]
        stats["clauses_examined"] += segmentation["clauses"]
        stats["relation_patterns_matched"] += segmentation["relation_patterns_matched"]
        record = {"work_id": row["work_id"], "chunk_id": row["chunk_id"],
                  "sentences": segmentation["sentences"], "clauses": segmentation["clauses"],
                  "matched": len(candidates), "candidate_ids": []}
        for c in candidates:
            relations[c["relation_type"]]["matches"] += 1
            fp = c["proposition_fingerprint"]
            if fp in seen_fp:
                stats["duplicate_propositions_removed"] += 1
                relations[c["relation_type"]]["duplicates"] += 1
                continue
            seen_fp.add(fp)
            c["candidate_id"] = "DQ3-" + fp[:12]
            record["candidate_ids"].append(c["candidate_id"])
            confidence = c["extractor_confidence"]
            stats[confidence] += 1
            relations[c["relation_type"]][confidence] += 1
            if confidence != "HIGH":
                c["review_status"] = "MEDIUM_LOW_DIAGNOSTIC"
                medium.append(c)
                continue
            stats["template_questions_built"] += 1
            checked = validate_v3(c, sources[row["work_id"]], eval_queries=eval_queries,
                                  test_works=split["protected_test_work_ids"],
                                  seen_queries=seen_questions)
            if checked["review_status"] == "AUTO_VALIDATED":
                auto.append(checked)
                seen_questions.append(checked["question"])
                stats["template_questions_validated"] += 1
                relations[c["relation_type"]]["passed_validation"] += 1
            else:
                rejected.append({"candidate_id": c["candidate_id"], "work_id": row["work_id"],
                                 "chunk_id": row["chunk_id"], "relation_type": c["relation_type"],
                                 "source_clause": c["clause_text"], "template_question": c["template_question"],
                                 "answer": c["short_answer"], "stage": checked["review_status"],
                                 "rejection_codes": checked["auto_validation"]["rejection_reasons"]})
                stats[checked["review_status"]] += 1
                relations[c["relation_type"]]["failed_validation"] += 1
                reasons.update(checked["auto_validation"]["rejection_reasons"])
        attempts.append(record)
    outbase.mkdir(parents=True, exist_ok=True)
    for key, values in (("high_confidence", auto), ("medium_low", medium),
                        ("rejected", rejected), ("attempts", attempts)):
        save_jsonl(outputs[key], values)
    stats.update({"paraphrases_attempted": 0, "paraphrases_accepted": 0,
                  "AUTO_VALIDATED": len(auto), "review_packet_rows": 0})
    report = {"result_label": "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS",
              "seed": args.seed, "precision": args.precision,
              "stats": dict(stats), "source_quality_counts": quality,
              "per_relation": {k: dict(v) for k, v in sorted(relations.items())},
              "rejection_reasons": dict(reasons),
              "book_distribution": dict(Counter(x[0]["work_id"] for x in selected)),
              "test_leakage_count": reasons["TEST_LEAKAGE"],
              "eval_leakage_count": reasons["EVAL_QUERY_SIMILARITY"],
              "training_gate": "CLOSED_PENDING_HUMAN_REVIEW"}
    report_path = TRAINING / "reports" / "rag_domain_qa_generation_audit_v3.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"stats": dict(stats), "per_relation": report["per_relation"],
                      "rejection_reasons": dict(reasons)}, indent=2))


if __name__ == "__main__": main()
