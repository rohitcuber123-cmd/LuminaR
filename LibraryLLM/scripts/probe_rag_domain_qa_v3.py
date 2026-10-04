"""Deterministic 20-chunk extractor mechanics probe; no training admission."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import random

from rag_domain_common import ROOT, SOURCE_MAP, TRAINING, controls, passage_pool
from rag_domain_qa_v2 import classify_passage_v2
from rag_domain_qa_v3 import extract_chunk, validate_v3


def scan(rows):
    pool = []
    for row in rows:
        if row["split"] != "TRAIN": continue
        candidates, stats = extract_chunk(row)
        pool.append((row, candidates, stats))
    return pool


def select(pool, count, seed):
    rng = random.Random(seed)
    items = list(pool)
    rng.shuffle(items)
    picked, book_count, relation_count = [], Counter(), Counter()
    while len(picked) < count:
        available = [item for item in items if item[0]["chunk_id"] not in {x[0]["chunk_id"] for x in picked}
                     and book_count[item[0]["work_id"]] < 3]
        if not available: break
        def score(item):
            high = [x for x in item[1] if x["extractor_confidence"] == "HIGH"]
            novelty = sum(1 for x in high if relation_count[x["relation_type"]] == 0)
            return (bool(high), novelty, -book_count[item[0]["work_id"]], bool(item[1]))
        selected = max(available, key=score)
        picked.append(selected)
        book_count[selected[0]["work_id"]] += 1
        relation_count.update(x["relation_type"] for x in selected[1])
    if len(picked) != count: raise RuntimeError("Cannot select enough diverse TRAIN chunks")
    return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--precision", default="high")
    args = ap.parse_args()
    if args.chunks != 20 or args.precision != "high":
        raise ValueError("This gate permits exactly 20 chunks in high precision mode")
    _, split, labels = controls()
    rows, quality = passage_pool(classifier=classify_passage_v2)
    picked = select(scan(rows), args.chunks, args.seed)
    mapping = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    sources = {wid: (ROOT / mapping[wid]["source_file"]).read_text(encoding="utf-8")
               for wid in {row["work_id"] for row, _, _ in picked}}
    eval_queries = [q["question"] for q in labels]
    seen, cases = set(), []
    stats = Counter()
    relation = Counter()
    for row, extracted, segment_stats in picked:
        stats["chunks"] += 1
        stats["sentences"] += segment_stats["sentences"]
        stats["clauses"] += segment_stats["clauses"]
        stats["matches"] += segment_stats["relation_patterns_matched"]
        shown = []
        for c in extracted:
            if c["proposition_fingerprint"] in seen:
                stats["duplicate_propositions"] += 1
                continue
            seen.add(c["proposition_fingerprint"])
            stats[c["extractor_confidence"]] += 1
            relation[c["relation_type"]] += 1
            checked = validate_v3(c, sources[row["work_id"]], eval_queries=eval_queries,
                                  test_works=split["protected_test_work_ids"])
            stats[checked["review_status"]] += 1
            shown.append({"candidate": c, "validation_status": checked["review_status"],
                          "rejections": checked["auto_validation"]["rejection_reasons"]})
        cases.append({"work_id": row["work_id"], "book_title": row["title"],
                      "chunk_id": row["chunk_id"], "source_excerpt": row["text"],
                      "segmentation": segment_stats, "propositions": shown,
                      "no_proposition_reason": "NO_SUPPORTED_EXPLICIT_PATTERN" if not shown else None})
    report = {"result_label": "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS",
              "seed": args.seed, "precision": args.precision,
              "stats": dict(stats), "relation_yield": dict(relation), "cases": cases,
              "automated_structural_gate": stats["HIGH"] > 0 and stats["GROUNDING_FAILED"] == 0,
              "manual_source_spot_gate": "PENDING_INSPECTION", "pilot_allowed": False,
              "protected_test_works": split["protected_test_work_ids"]}
    out = TRAINING / "reports" / "rag_domain_qa_v3_extractor_probe.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# V3 deterministic extractor: 20-chunk source probe", "",
             "**EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS**", "",
             f"Stats: `{dict(stats)}`", f"Relations: `{dict(relation)}`", "",
             "Manual source inspection is required before a 50-chunk pilot.", ""]
    for i, item in enumerate(cases, 1):
        lines += [f"## {i}. {item['book_title']} — {item['chunk_id']}", "",
                  f"- Sentences: {item['segmentation']['sentences']}; clauses: {item['segmentation']['clauses']}"]
        if not item["propositions"]: lines += ["- NO_PROPOSITION: no supported explicit pattern", ""]
        for entry in item["propositions"]:
            c = entry["candidate"]
            lines += [f"- Source clause: {c['clause_text']}",
                      f"- Extractor: {c['relation_type']}; confidence: {c['extractor_confidence']}",
                      f"- Proposition: `{json.dumps({k: v for k, v in c['proposition'].items() if k in {'subject','predicate','object','cause','effect','location','time','relation_type','v3_relation','instruction','entity_a','entity_b'}}, ensure_ascii=False)}`",
                      f"- Template question: {c['template_question']}",
                      f"- Answer: {c['short_answer']}",
                      f"- V2 validation: {entry['validation_status']} {entry['rejections']}", ""]
    (TRAINING / "reports" / "rag_domain_qa_v3_extractor_probe.md").write_text(
        "\n".join(lines), encoding="utf-8")
    print(json.dumps({"stats": dict(stats), "relations": dict(relation),
                      "automated_structural_gate": report["automated_structural_gate"]}, indent=2))


if __name__ == "__main__": main()
