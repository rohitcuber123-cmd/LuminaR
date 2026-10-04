"""Read-only V4 source replay through V5; never call the V4 probe generator."""
from __future__ import annotations

from collections import Counter
import hashlib
import json

from rag_domain_common import ROOT, SOURCE_MAP, TRAINING, controls
from rag_domain_qa_v5 import extract_chunk_v5, validate_v5


def main():
    inventory = json.loads((TRAINING / "reports" / "rag_domain_qa_v5_v4_failure_inventory.json").read_text(encoding="utf-8"))
    frozen = {"gate": TRAINING / "reports" / "rag_domain_qa_v4_quality_gate.md",
              "probe": TRAINING / "reports" / "rag_domain_qa_v4_probe.json",
              "audit": TRAINING / "reports" / "rag_domain_qa_v4_probe_audit.json",
              "ranges": TRAINING / "manifests" / "rag_domain_qa_v4_probe_ranges.json"}
    for key, path in frozen.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != inventory["v4_file_sha256"][key]:
            raise RuntimeError(f"Frozen V4 artifact changed: {key}")
    probe = json.loads(frozen["probe"].read_text(encoding="utf-8"))
    _, split, labels = controls()
    mapping = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))["books"]
    sources = {wid: (ROOT / mapping[wid]["source_file"]).read_text(encoding="utf-8")
               for wid in {case["work_id"] for case in probe["cases"]}}
    old = {row["fingerprint"]: row for row in inventory["rows"]}
    fresh, validations = {}, {}
    for case in probe["cases"]:
        entries = case["propositions"]
        if not entries: continue
        example = entries[0]["candidate"]
        row = {"text": case["text"], "source_start_char": example["source_start"],
               "source_end_char": example["source_end"], "source_sha256": example["source_hash"],
               "work_id": case["work_id"], "title": case["title"], "chapter": example["chapter"],
               "chunk_id": case["chunk_id"], "split": "TRAIN"}
        candidates, _ = extract_chunk_v5(row)
        for c in candidates:
            fresh[c["proposition_fingerprint"]] = c
            validations[c["proposition_fingerprint"]] = validate_v5(
                c, sources[case["work_id"]], eval_queries=[q["question"] for q in labels],
                test_works=split["protected_test_work_ids"])
    rows, transition, families = [], Counter(), {}
    for fp, prior in old.items():
        c = fresh.get(fp)
        checked = validations.get(fp)
        if c is None:
            status = "REJECTED"
        elif c["extraction_confidence"] != "HIGH":
            status = "DOWNGRADED_MEDIUM"
        else:
            status = "STILL_HIGH"
        # A changed proposition is recorded only when the original fingerprint is gone
        # but another V5 fact points to the same source clause and relation.
        if status == "REJECTED" and any(x["work_id"] == prior["work_id"] and
              x["chunk_id"] == prior["chunk_id"] and x["relation_type"] == prior["relation"]
              for x in fresh.values()):
            status = "CHANGED_PROPOSITION"
        auto = bool(checked and checked["validation_status"] == "AUTO_VALIDATED")
        family = prior["failure_family"]
        record = {**prior, "v5_transition": status, "v5_validation_status": (
                  checked["validation_status"] if checked else "NOT_EMITTED"),
                  "v5_confidence_reasons": c.get("confidence_reasons", []) if c else [],
                  "v5_still_auto_validates": auto}
        rows.append(record)
        transition[status] += 1
        summary = families.setdefault(family, Counter())
        summary["old_count"] += 1
        summary["v5_blocks_upstream"] += status in {"DOWNGRADED_MEDIUM", "REJECTED", "CHANGED_PROPOSITION"}
        summary["v5_validator_rejects"] += status == "STILL_HIGH" and not auto
        summary["still_auto_validates"] += auto
    known = sum(r["v5_still_auto_validates"] for r in rows if r["failure_family"] != "CLEAN_REFERENCE")
    report = {"result_label": "EXPERIMENTAL ONLY — FROZEN V4 REGRESSION REPLAY",
              "old_high": len(rows), "transitions": dict(transition),
              "families": {k: dict(v) for k, v in families.items()},
              "known_v4_failures_still_auto_validating": known, "rows": rows}
    out = TRAINING / "reports" / "rag_domain_qa_v5_v4_replay.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# Frozen V4 → V5 source replay", "", "This is regression evidence, not a new probe.", "",
             f"Old HIGH: {len(rows)}; transitions: `{dict(transition)}`", "",
             "| Family | Old | Blocked upstream | Validator rejects | Still auto-validates |",
             "|---|---:|---:|---:|---:|"]
    for name, value in families.items():
        lines.append(f"| {name} | {value['old_count']} | {value['v5_blocks_upstream']} | "
                     f"{value['v5_validator_rejects']} | {value['still_auto_validates']} |")
    lines += ["", f"Known failed V4 propositions still auto-validating: **{known}**.", ""]
    (TRAINING / "reports" / "rag_domain_qa_v5_v4_replay.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"old_high": len(rows), "transitions": dict(transition),
                      "known_failures_still_auto_validating": known}, indent=2))


if __name__ == "__main__": main()
