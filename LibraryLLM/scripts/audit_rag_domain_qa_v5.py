"""Gate the V5 probe; substantive AUTO_VALIDATED cases require manual source audit."""
from __future__ import annotations

import argparse
import json

from rag_domain_common import TRAINING


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", required=True)
    ap.parse_args()
    report = json.loads((TRAINING / "reports" / "rag_domain_qa_v5_probe.json").read_text(encoding="utf-8"))
    auto = [(case, entry) for case in report["cases"] for entry in case["propositions"]
            if entry["validation_status"] == "AUTO_VALIDATED"]
    if auto:
        raise RuntimeError("Source audit requires explicit per-candidate human engineering inspection")
    stats = report["stats"]
    result = {"auto_validated_inspected": 0, "source_audit_clean": 0, "source_audit_rejected": 0,
              "yield_pass": stats.get("AUTO_VALIDATED", 0) >= 8,
              "calibration_pass": report["high_validator_pass_rate"] >= .8,
              "v4_range_overlap": report["v4_source_range_overlap"],
              "probe_gate_passed": False, "pilot_allowed": False}
    (TRAINING / "reports" / "rag_domain_qa_v5_probe_audit.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    (TRAINING / "reports" / "rag_domain_qa_v5_probe_audit.md").write_text(
        "# V5 fresh-probe source audit\n\n"
        "**EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS**\n\n"
        "The 40-chunk probe emitted zero propositions and zero AUTO_VALIDATED candidates. "
        "There are no candidates to source-audit; CLEAN and REJECTED counts are both zero. "
        "The ≥8 AUTO_VALIDATED yield gate and ≥80% HIGH validation pass-rate gate fail. "
        "The independent pilot is blocked.\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__": main()
