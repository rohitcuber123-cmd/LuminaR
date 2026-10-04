"""Classify frozen V4 audit rows for V5 regression replay; never regenerate V4."""
from __future__ import annotations

import hashlib
import json

from rag_domain_common import TRAINING


def main():
    paths = {
        "gate": TRAINING / "reports" / "rag_domain_qa_v4_quality_gate.md",
        "probe": TRAINING / "reports" / "rag_domain_qa_v4_probe.json",
        "audit": TRAINING / "reports" / "rag_domain_qa_v4_probe_audit.json",
        "ranges": TRAINING / "manifests" / "rag_domain_qa_v4_probe_ranges.json",
    }
    hashes = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in paths.items()}
    audit = json.loads(paths["audit"].read_text(encoding="utf-8"))
    rows = []
    for old in audit["rows"]:
        reason = old["reason"]
        if old["verdict"] == "CLEAN_ON_SOURCE_INSPECTION": family = "CLEAN_REFERENCE"
        elif "ANSWER_TOO_VAGUE" in reason: family = "STATEMENT_FRAGMENT"
        elif "STATEMENT_FALSE_TOPIC" in reason: family = "STATEMENT_TOPIC"
        elif "ACTION_CONTEXT_DRIFT" in reason: family = "ACTION_CONTEXT"
        elif "STATEMENT_CONTEXT_DEPENDENT" in reason: family = "DISCOURSE_DEPENDENCY"
        else: family = "OTHER_VALIDATOR_FAILURE"
        rows.append({"fingerprint": old["fingerprint"], "work_id": old["work_id"],
                     "chunk_id": old["chunk_id"], "relation": old["relation"],
                     "old_validation_status": old["validation_status"],
                     "old_source_audit": old["verdict"], "failure_family": family,
                     "old_rejection_reason": reason})
    result = {"result_label": "EXPERIMENTAL ONLY — FROZEN V4 REGRESSION INPUT",
              "v4_file_sha256": hashes, "count": len(rows), "rows": rows}
    out = TRAINING / "reports" / "rag_domain_qa_v5_v4_failure_inventory.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"count": len(rows), "families": {k: sum(r["failure_family"] == k for r in rows)
              for k in sorted({r["failure_family"] for r in rows})}}, indent=2))


if __name__ == "__main__": main()
