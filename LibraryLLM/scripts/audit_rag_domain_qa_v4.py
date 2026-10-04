"""Record the source inspection of the frozen V4 probe; no pilot admission."""
from __future__ import annotations

import argparse
import json

from rag_domain_common import TRAINING


# These annotations apply only to the seed-42 probe and are never extractor rules.
UNSAFE_VALIDATED = {
    8: "ACTION_CONTEXT_DRIFT: question folds a second action into the location context",
    9: "STATEMENT_FALSE_TOPIC: 'Where' is a question word, not a named topic",
    14: "STATEMENT_FALSE_TOPIC: 'Good' is an interjection, not a named topic",
    20: "STATEMENT_FALSE_TOPIC: 'Have' is a question auxiliary, not a named topic",
    22: "STATEMENT_FALSE_TOPIC: 'Miss' is a form of address, not a named topic",
    23: "STATEMENT_CONTEXT_DEPENDENT: 'I swear the same' lacks the referred pledge",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", required=True)
    args = ap.parse_args()
    path = TRAINING / "reports" / "rag_domain_qa_v4_probe.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    if report["seed"] != 42 or report["source_range_manifest_sha256"] != (
            "f195ab4c7213b4fa147941b250f3c4891edd8305aa4c5a0469525ea7329e7276"):
        raise RuntimeError("Probe changed; human audit annotations must be repeated")
    highs = [(case, entry) for case in report["cases"] for entry in case["propositions"]
             if entry["candidate"]["extractor_confidence"] == "HIGH"]
    if len(highs) != 27:
        raise RuntimeError("Probe HIGH count changed; human audit annotations must be repeated")
    rows = []
    for i, (case, entry) in enumerate(highs):
        c = entry["candidate"]
        if entry["validation_status"] != "AUTO_VALIDATED":
            verdict = "REJECT"
            reason = "UNCHANGED_V2_VALIDATOR: " + ", ".join(entry["rejections"])
        elif i in UNSAFE_VALIDATED:
            verdict = "REJECT"
            reason = UNSAFE_VALIDATED[i]
        else:
            verdict = "CLEAN_ON_SOURCE_INSPECTION"
            reason = "Named participant, relation, question, and answer match the local source"
        rows.append({"index": i, "work_id": case["work_id"], "chunk_id": case["chunk_id"],
                     "fingerprint": c["proposition_fingerprint"], "relation": c["relation_type"],
                     "question": c["question"], "answer": c["short_answer"],
                     "source_clause": c["clause_text"], "validation_status": entry["validation_status"],
                     "verdict": verdict, "reason": reason})
    clean = sum(r["verdict"] == "CLEAN_ON_SOURCE_INSPECTION" for r in rows)
    output = {"result_label": "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS",
              "probe_manifest_sha256": report["source_range_manifest_sha256"],
              "high_inspected": len(rows), "clean": clean, "rejected": len(rows) - clean,
              "validator_failures": 14, "semantic_failures_despite_validator_pass": 6,
              "probe_gate_passed": False, "pilot_allowed": False, "rows": rows}
    (TRAINING / "reports" / "rag_domain_qa_v4_probe_audit.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# V4 probe HIGH source audit", "", "EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS", "",
             f"Inspected all {len(rows)} HIGH. Clean: {clean}. Rejected: {len(rows)-clean}.",
             "The ≥8 HIGH / zero-failure gate failed. Independent pilot is blocked.", ""]
    for r in rows:
        lines += [f"## {r['index']}. {r['relation']} — {r['verdict']}", "",
                  f"- Question: {r['question']}", f"- Answer: {r['answer']}",
                  f"- Source: {r['source_clause']}", f"- Reason: {r['reason']}", ""]
    (TRAINING / "reports" / "rag_domain_qa_v4_probe_audit.md").write_text(
        "\n".join(lines), encoding="utf-8")
    print(json.dumps({k: output[k] for k in ("high_inspected", "clean", "rejected",
                                             "validator_failures", "semantic_failures_despite_validator_pass",
                                             "probe_gate_passed")}, indent=2))


if __name__ == "__main__":
    main()
