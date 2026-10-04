"""Bounded 30-chunk V4 mechanics gate; no training or review admission."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import random

from rag_domain_common import ROOT, SOURCE_MAP, TRAINING, controls, passage_pool
from rag_domain_qa_v2 import classify_passage_v2
from rag_domain_qa_v4 import extract_chunk_v4, validate_v4


def select(pool, count, seed, per_book=3):
    rng = random.Random(seed)
    items = list(pool)
    rng.shuffle(items)
    picked, books, relations = [], Counter(), Counter()
    while len(picked) < count:
        available = [x for x in items if x[0]["chunk_id"] not in {p[0]["chunk_id"] for p in picked}
                     and books[x[0]["work_id"]] < per_book]
        if not available:
            raise RuntimeError("Insufficient balanced TRAIN chunks")
        def score(item):
            high = [c for c in item[1] if c["extractor_confidence"] == "HIGH"]
            return (bool(high), sum(relations[c["relation_type"]] == 0 for c in high),
                    -books[item[0]["work_id"]], bool(item[1]))
        chosen = max(available, key=score)
        picked.append(chosen)
        books[chosen[0]["work_id"]] += 1
        relations.update(c["relation_type"] for c in chosen[1])
    return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--precision", default="high")
    args = ap.parse_args()
    if (args.chunks, args.seed, args.precision) != (30, 42, "high"):
        raise ValueError("V4 probe requires --chunks 30 --seed 42 --precision high")
    _, split, labels = controls()
    rows, quality = passage_pool(classifier=classify_passage_v2)
    pool = [(row, *extract_chunk_v4(row)) for row in rows if row["split"] == "TRAIN"]
    picked = select(pool, args.chunks, args.seed)
    mapping = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    sources = {wid: (ROOT / mapping[wid]["source_file"]).read_text(encoding="utf-8")
               for wid in {r["work_id"] for r, _, _ in picked}}
    ranges = [{"work_id": r["work_id"], "chunk_id": r["chunk_id"],
               "source_start": r["source_start_char"], "source_end": r["source_end_char"],
               "source_hash": r["source_sha256"]} for r, _, _ in picked]
    digest = hashlib.sha256(json.dumps(ranges, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    manifest = {"seed": args.seed, "chunks": 30, "source_ranges": ranges, "ranges_sha256": digest}
    manifest_path = TRAINING / "manifests" / "rag_domain_qa_v4_probe_ranges.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    seen, stats, relation, cases = set(), Counter(), Counter(), []
    eval_queries = [x["question"] for x in labels]
    for row, candidates, segment in picked:
        stats["chunks"] += 1
        stats["sentences"] += segment.get("sentences", 0)
        stats["clauses"] += segment.get("clauses", 0)
        stats["can_match_cues"] += sum(v for k, v in segment.items() if k.startswith("cue_"))
        stats["relation_matches"] += segment.get("matches", 0)
        entries = []
        for c in candidates:
            if c["proposition_fingerprint"] in seen:
                stats["duplicate_propositions"] += 1
                continue
            seen.add(c["proposition_fingerprint"])
            stats[c["extractor_confidence"]] += 1
            relation[c["relation_type"]] += 1
            checked = validate_v4(c, sources[row["work_id"]], eval_queries=eval_queries,
                                  test_works=split["protected_test_work_ids"])
            stats[checked["review_status"]] += 1
            if c["extractor_confidence"] == "HIGH" and checked["review_status"] != "AUTO_VALIDATED":
                stats["validator_failures"] += 1
            entries.append({"candidate": c, "validation_status": checked["review_status"],
                            "rejections": checked["auto_validation"]["rejection_reasons"]})
        cases.append({"work_id": row["work_id"], "title": row["title"],
                      "chunk_id": row["chunk_id"], "range": [row["source_start_char"], row["source_end_char"]],
                      "text": row["text"], "segmentation": segment, "propositions": entries})
    report = {"result_label": "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS", "seed": 42,
              "precision": "high", "source_range_manifest_sha256": digest,
              "stats": dict(stats), "relation_yield": dict(relation), "cases": cases,
              "structural_gate": stats["HIGH"] >= 8 and stats["validator_failures"] == 0,
              "semantic_spot_audit": "PENDING", "pilot_allowed": False,
              "passage_quality": quality}
    out = TRAINING / "reports" / "rag_domain_qa_v4_probe.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# V4 30-chunk mechanics probe", "", "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS", "",
             f"Stats: `{dict(stats)}`", f"Relations: `{dict(relation)}`", f"Source ranges SHA-256: `{digest}`", ""]
    for case in cases:
        lines += [f"## {case['title']} — {case['chunk_id']}", "", f"Range: {case['range']}", ""]
        for entry in case["propositions"]:
            c = entry["candidate"]
            lines += [f"- {c['extractor_confidence']} {c['relation_type']}: {c['question']} → {c['short_answer']}",
                      f"  Source: {c['clause_text']}", f"  Validation: {entry['validation_status']} {entry['rejections']}"]
        lines.append("")
    (TRAINING / "reports" / "rag_domain_qa_v4_probe.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"stats": dict(stats), "relations": dict(relation),
                      "structural_gate": report["structural_gate"], "range_manifest_sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
