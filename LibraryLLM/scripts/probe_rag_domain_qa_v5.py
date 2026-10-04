"""Fresh source-range-disjoint 40-chunk V5 precision probe."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import random

from rag_domain_common import ROOT, SOURCE_MAP, TRAINING, controls, passage_pool
from rag_domain_qa_v2 import classify_passage_v2
from rag_domain_qa_v5 import extract_chunk_v5, validate_v5


def overlaps(a, b):
    return a["work_id"] == b["work_id"] and a["source_start_char"] < b["source_end"] and (
        b["source_start"] < a["source_end_char"])


def select_balanced(rows, count, seed):
    rng = random.Random(seed)
    groups = defaultdict(list)
    for row in rows: groups[row["work_id"]].append(row)
    books = sorted(groups)
    rng.shuffle(books)
    for group in groups.values(): rng.shuffle(group)
    chosen = []
    while len(chosen) < count and any(groups.values()):
        for book in books:
            if groups[book] and len(chosen) < count:
                chosen.append(groups[book].pop())
    if len(chosen) != count:
        raise RuntimeError("Insufficient disjoint TRAIN source ranges")
    return chosen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=40)
    ap.add_argument("--seed", type=int, default=101)
    ap.add_argument("--exclude-prior-probe-ranges", action="store_true")
    ap.add_argument("--precision", default="high")
    args = ap.parse_args()
    if (args.chunks, args.seed, args.precision) != (40, 101, "high") or not args.exclude_prior_probe_ranges:
        raise ValueError("V5 probe requires 40 chunks, seed 101, prior-range exclusion, high precision")
    _, split, labels = controls()
    prior_path = TRAINING / "manifests" / "rag_domain_qa_v4_probe_ranges.json"
    prior = json.loads(prior_path.read_text(encoding="utf-8"))["source_ranges"]
    rows, quality = passage_pool(classifier=classify_passage_v2)
    eligible = [r for r in rows if r["split"] == "TRAIN" and not any(overlaps(r, p) for p in prior)]
    picked = select_balanced(eligible, 40, 101)
    if any(overlaps(r, p) for r in picked for p in prior):
        raise RuntimeError("V5 probe overlaps frozen V4 source ranges")
    ranges = [{"work_id": r["work_id"], "chunk_id": r["chunk_id"],
               "source_start": r["source_start_char"], "source_end": r["source_end_char"],
               "source_hash": r["source_sha256"], "selection_seed": 101} for r in picked]
    digest = hashlib.sha256(json.dumps(ranges, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    manifest = {"seed": 101, "chunks": 40,
                "prior_range_manifests_excluded": [str(prior_path.relative_to(ROOT))],
                "ranges_sha256": digest, "source_ranges": ranges, "v4_range_overlap": 0}
    (TRAINING / "manifests" / "rag_domain_qa_v5_probe_ranges.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    mapping = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    sources = {wid: (ROOT / mapping[wid]["source_file"]).read_text(encoding="utf-8")
               for wid in {r["work_id"] for r in picked}}
    eval_queries = [q["question"] for q in labels]
    seen, stats, relation, cases = set(), Counter(), Counter(), []
    streams = {key: [] for key in ("high", "medium", "rejected")}
    for row in picked:
        candidates, segment = extract_chunk_v5(row)
        stats["chunks"] += 1
        stats["sentences"] += segment.get("sentences", 0)
        stats["clauses"] += segment.get("clauses", 0)
        stats["can_match_cues"] += sum(v for k, v in segment.items() if k.startswith("cue_"))
        stats["relation_matches"] += segment.get("matches", 0)
        stats["answer_sufficiency_rejects"] += segment.get("answer_sufficiency_rejects", 0)
        entries = []
        for c in candidates:
            fp = c["proposition_fingerprint"]
            if fp in seen:
                stats["duplicates_removed"] += 1
                continue
            seen.add(fp)
            confidence = c["extraction_confidence"]
            stats[f"extracted_{confidence}"] += 1
            relation[c["relation_type"]] += 1
            checked = validate_v5(c, sources[row["work_id"]], eval_queries=eval_queries,
                                  test_works=split["protected_test_work_ids"])
            if confidence == "HIGH":
                stats["validator_passing_HIGH" if checked["validation_status"] == "AUTO_VALIDATED"
                      else "validator_failing_HIGH"] += 1
            stats[checked["validation_status"]] += 1
            entry = {"candidate": c, "validation_status": checked["validation_status"],
                     "validator_review_status": checked["review_status"],
                     "rejections": checked["auto_validation"]["rejection_reasons"],
                     "source_audit_status": "NOT_AUDITED"}
            entries.append(entry)
            streams["high" if confidence == "HIGH" else "medium"].append(entry)
            if checked["validation_status"] == "FAILED": streams["rejected"].append(entry)
        cases.append({"work_id": row["work_id"], "title": row["title"], "chapter": row["chapter"],
                      "chunk_id": row["chunk_id"], "range": [row["source_start_char"], row["source_end_char"]],
                      "text": row["text"], "segmentation": segment, "propositions": entries})
    luminar = TRAINING / "luminar"
    for key, entries in streams.items():
        (luminar / f"domain_qa_v5_probe_{key}.jsonl").write_text(
            "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
    pass_rate = (stats["validator_passing_HIGH"] / stats["extracted_HIGH"]
                 if stats["extracted_HIGH"] else 0.0)
    report = {"result_label": "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS",
              "seed": 101, "precision": "high", "v4_source_range_overlap": 0,
              "source_range_manifest_sha256": digest, "stats": dict(stats),
              "high_validator_pass_rate": pass_rate, "relation_yield": dict(relation),
              "cases": cases, "source_audit_status": "PENDING", "pilot_allowed": False,
              "passage_quality": quality}
    (TRAINING / "reports" / "rag_domain_qa_v5_probe.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# V5 fresh 40-chunk precision probe", "", "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS", "",
             f"Manifest SHA-256: `{digest}`; V4 source-range overlap: 0", "",
             f"Stats: `{dict(stats)}`", f"HIGH validator pass rate: {pass_rate:.3f}", ""]
    for case in cases:
        lines += [f"## {case['title']} — {case['chunk_id']}", "", f"Source range: {case['range']}", ""]
        for e in case["propositions"]:
            c = e["candidate"]
            lines += [f"- {c['extraction_confidence']} {c['relation_type']}: {c['question']} → {c['short_answer']}",
                      f"  Source: {c['clause_text']}",
                      f"  Validation: {e['validation_status']} {e['rejections']}", ""]
    (TRAINING / "reports" / "rag_domain_qa_v5_probe.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"stats": dict(stats), "pass_rate": pass_rate,
                      "manifest_sha256": digest, "v4_overlap": 0}, indent=2))


if __name__ == "__main__": main()
