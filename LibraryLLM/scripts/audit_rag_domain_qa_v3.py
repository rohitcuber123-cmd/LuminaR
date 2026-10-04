"""Summarize v3 extractor probe or bounded pilot without creating a review batch."""
from __future__ import annotations

import argparse
from collections import Counter
import json

from rag_domain_common import TRAINING, controls


def read(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--version", default="v3")
    args = ap.parse_args()
    controls()
    if args.probe:
        path = TRAINING / "reports" / "rag_domain_qa_v3_extractor_probe.json"
        probe = json.loads(path.read_text(encoding="utf-8"))
        print(json.dumps({k: probe[k] for k in ("stats", "relation_yield", "automated_structural_gate",
                                                 "manual_source_spot_gate", "pilot_allowed")}, indent=2))
        return
    if args.version != "v3": raise ValueError("Only v3 supported")
    path = TRAINING / "reports" / "rag_domain_qa_generation_audit_v3.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    high = read(TRAINING / "luminar" / "domain_qa_v3_high_confidence.jsonl")
    medium = read(TRAINING / "luminar" / "domain_qa_v3_medium_low.jsonl")
    rejected = read(TRAINING / "luminar" / "domain_qa_v3_rejected.jsonl")
    attempts = read(TRAINING / "luminar" / "domain_qa_v3_attempts.jsonl")
    revalidation = json.loads((TRAINING / "reports" / "rag_domain_qa_validation_v3.json").read_text(encoding="utf-8"))
    if len(high) != report["stats"]["AUTO_VALIDATED"] or revalidation["statuses"].get("AUTO_VALIDATED", 0) != len(high):
        raise RuntimeError("Pilot and read-only validation disagree")
    gate = len(high) >= 10
    probe = json.loads((TRAINING / "reports" / "rag_domain_qa_v3_extractor_probe.json").read_text(encoding="utf-8"))
    probe_fingerprints = {entry["candidate"]["proposition_fingerprint"]
                          for case in probe["cases"] for entry in case["propositions"]
                          if entry["candidate"]["extractor_confidence"] == "HIGH"}
    overlap = sum(x["proposition_fingerprint"] in probe_fingerprints for x in high)
    from rag_domain_common import passage_pool
    from rag_domain_qa_v2 import classify_passage_v2
    from rag_domain_qa_v3 import EXTRACTORS, segment_clauses, segment_sentences
    wanted = {x["chunk_id"] for x in attempts}
    rows, _ = passage_pool(classifier=classify_passage_v2)
    source_rows = {x["chunk_id"]: x for x in rows if x["chunk_id"] in wanted}
    if set(source_rows) != wanted: raise RuntimeError("Pilot source chunk lookup failed")
    extractor_attempts = Counter()
    for item in attempts:
        row = source_rows[item["chunk_id"]]
        for sentence in segment_sentences(row["text"]):
            for clause in segment_clauses(sentence):
                for extractor in EXTRACTORS:
                    if extractor.can_match(clause): extractor_attempts[type(extractor).__name__] += 1
    report.update({"review_gate_pass": gate, "review_packet_rows": 0 if not gate else len(high),
                   "human_review": "NOT YET COMPLETE", "training_gate": "CLOSED",
                   "high_confidence_revalidated": len(high), "medium_low_diagnostic": len(medium),
                   "high_rejected": len(rejected), "review_packet_rendered": False,
                   "extractor_can_match_attempts": dict(extractor_attempts),
                   "auto_validated_overlap_with_probe": overlap})
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# V3 deterministic domain QA: 50-source audit", "",
             "**EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS**", "",
             f"Review gate: {'PASS' if gate else 'FAIL'}; {len(high)} AUTO_VALIDATED against the required ≥10.",
             "Human review: NOT YET COMPLETE. Training gate: CLOSED.", "",
             "## Counts", ""]
    lines += [f"- {k}: {v}" for k, v in sorted(report["stats"].items())]
    lines += ["", "## Per relation", ""]
    lines += [f"- {k}: {v}" for k, v in sorted(report["per_relation"].items())]
    lines += ["", "## Extractor can-match attempts", ""]
    lines += [f"- {k}: {v}" for k, v in sorted(extractor_attempts.items())]
    lines += ["", "## Rejection codes", ""]
    lines += [f"- {k}: {v}" for k, v in sorted(report["rejection_reasons"].items())]
    lines += ["", f"AUTO_VALIDATED propositions also seen in the probe: {overlap}/{len(high)}. "
              "The pilot therefore does not provide independent quality confirmation for those examples.",
              "No Qwen paraphrases were attempted. The template question was kept for every emitted candidate.", ""]
    (TRAINING / "reports" / "rag_domain_qa_generation_audit_v3.md").write_text(
        "\n".join(lines), encoding="utf-8")
    if not gate:
        diagnostic = ["# V3 high-confidence source diagnostic — below review threshold", "",
                      "**EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS**", "",
                      "This is an engineering diagnostic, not a human-review packet or REVIEWED data. "
                      "Only five candidates passed automatic checks; the ≥10 review threshold failed.", ""]
        for c in high:
            diagnostic += [f"## {c['candidate_id']} — {c['book_title']}", "",
                           f"- Relation: {c['relation_type']}; confidence: {c['extractor_confidence']}",
                           f"- Clause: {c['clause_text']}",
                           f"- Proposition: `{json.dumps({k: v for k, v in c['proposition'].items() if k in {'subject','predicate','object','cause','effect','location','time','relation_type','v3_relation','instruction','entity_a','entity_b'}}, ensure_ascii=False)}`",
                           f"- Template: {c['template_question']}",
                           f"- Final: {c['final_question']}",
                           f"- Answer: {c['short_answer']}",
                           f"- Evidence: {c['proposition']['evidence_quote']}",
                           f"- Automatic validation: {c['auto_validation']}", ""]
        (TRAINING / "reports" / "rag_domain_qa_v3_diagnostic.md").write_text(
            "\n".join(diagnostic), encoding="utf-8")
    print(json.dumps({"auto_validated": len(high), "medium_low": len(medium),
                      "rejected_high": len(rejected), "review_gate_pass": gate,
                      "review_packet_rendered": False}, indent=2))


if __name__ == "__main__": main()
