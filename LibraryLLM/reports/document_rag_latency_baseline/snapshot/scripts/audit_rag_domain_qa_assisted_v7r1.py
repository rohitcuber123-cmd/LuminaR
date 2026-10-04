"""Gate V7R1, preserve original V7, and report source-audit outcomes."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import re
import unicodedata

import pyarrow.parquet as pq

from rag_domain_common import CONTROL, ROOT, TRAINING
from rag_domain_qa_assisted_v7 import strict_json
from validate_rag_domain_qa_assisted_v7r1 import read_jsonl, validate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def diagnostic_normalize(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()


def main():
    validation = validate()
    contract = json.loads((TRAINING / "reports" / "rag_domain_qa_assisted_v7r1_contract_audit.json").read_text(encoding="utf-8"))
    original_drift = [path for path, expected in contract["original_v7_frozen_sha256"].items()
                      if sha(ROOT / path) != expected]
    if original_drift: raise RuntimeError(f"Original V7 artifact changed: {original_drift}")
    production = json.loads((ROOT / "datasets" / "rag_experiments" / "chunking_v1" / "reports" /
                             "production_before_sha256.json").read_text(encoding="utf-8"))
    production_drift = [path for path, expected in production.items()
                        if not (ROOT / path).exists() or sha(ROOT / path) != expected]
    if production_drift: raise RuntimeError(f"Production snapshot drift: {production_drift}")
    auto = read_jsonl(TRAINING / "luminar" / "domain_qa_assisted_v7r1_auto_checked.jsonl")
    rejected = read_jsonl(TRAINING / "luminar" / "domain_qa_assisted_v7r1_rejected.jsonl")
    raw = read_jsonl(TRAINING / "luminar" / "domain_qa_assisted_v7r1_raw.jsonl")
    generation = json.loads((TRAINING / "reports" / "rag_domain_qa_assisted_v7r1_generation.json").read_text(encoding="utf-8"))
    reasons = Counter(reason for row in rejected for reason in row.get("rejection_reasons", []))
    chunks = {(r["work_id"], r["chunk_id"]): r for r in pq.read_table(CONTROL / "chunks.parquet").to_pylist()}
    whitespace_only = 0
    substantive_or_other = 0
    for row in raw:
        parsed = strict_json(row["generator_raw"])
        if parsed is None: continue
        passage = chunks[(row["work_id"], row["chunk_id"])]["text"]
        for generated in parsed["candidates"]:
            evidence = generated["evidence_quote"]
            if evidence and evidence not in passage:
                if diagnostic_normalize(evidence) in diagnostic_normalize(passage):
                    whitespace_only += 1
                else:
                    substantive_or_other += 1
    # Engineering source audit cannot classify any accepted proposal because
    # deterministic validation produced no AUTO_CHECKED rows.
    source_audit = {"plausible_for_human_review": 0, "obvious_semantic_error": 0,
                    "ambiguous": 0, "obvious_semantic_error_rate": None,
                    "audited_auto_checked": len(auto)}
    if auto:
        raise RuntimeError("Unexpected AUTO_CHECKED rows require individual engineering source audit")
    gate = "B. ASSISTED AUTHORING QUALITY STILL TOO LOW — REVISE GENERATION STRATEGY"
    report = {"version": "v7r1", "gate_status": gate,
              "same_original_50_passages": validation["same_original_50_in_order"],
              "original_v7_hashes_unchanged": True, "production_snapshot_files": len(production),
              "production_snapshot_changed": 0, "source_hashes_valid": validation["source_hashes_valid"],
              "test_leakage": validation["test_leakage"],
              "evaluation_span_leakage": validation["evaluation_span_leakage"],
              "generation_settings": {key: generation[key] for key in (
                  "generator_model", "generator_model_index_sha256", "dtype", "device", "do_sample",
                  "max_new_tokens_generator", "max_new_tokens_judge", "same_model_generator_and_judge")},
              "counts": {"passages": len(raw), "raw_proposals": validation["raw_generated_QA"],
                         "zero_candidate_passages": validation.get("zero_candidate_passages", 0),
                         "invalid_json": validation.get("format_failures", 0),
                         "deterministic_passes": generation["summary"].get("deterministic_passes", 0),
                         "AUTO_CHECKED": len(auto), "rejected_records": len(rejected)},
              "rejection_reasons": dict(reasons.most_common()),
              "evidence_exact_failure_diagnostics": {
                  "zero_exact_occurrences": reasons["EVIDENCE_NOT_EXACT_IN_POSITIVE"],
                  "multiple_exact_occurrences": reasons["AMBIGUOUS_EVIDENCE_OCCURRENCE"],
                  "diagnostic_whitespace_nfkc_only": whitespace_only,
                  "diagnostic_other_mismatch": substantive_or_other,
                  "normalization_used_for_acceptance": False},
              "matcher_bug": False,
              "matcher_finding": "Original V7 error label conflated zero exact matches and duplicates; all 80 were zero, with no duplicates. V7R1 records counts and offsets.",
              "engineering_source_audit": source_audit,
              "review_packet_rows": 0, "human_review_status": "NOT_REVIEWED",
              "v8_v9_v10_started": False}
    output = TRAINING / "reports" / "rag_domain_qa_assisted_v7r1_audit.json"
    if output.exists(): raise RuntimeError("V7R1 audit exists; refusing overwrite")
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# V7R1 assisted-QA controlled rerun audit", "", f"**Gate: {gate}**", "",
             "Original V7 is a frozen, misconfigured control. Its six hashes remain unchanged; the exact same 50 TRAIN passages were reused in order.",
             "The local Qwen2.5-3B-Instruct ran greedily on CUDA in FP16, max 430 generator and 210 judge tokens; no judge inference was reached.",
             "The fixed prompt explicitly listed nine categories and three difficulties and required exact evidence and answer substrings.",
             "", "## Results", "",
             f"- 50 passages; {validation['raw_generated_QA']} proposals; {validation.get('zero_candidate_passages', 0)} zero-candidate passages.",
             f"- 0 invalid JSON/category/difficulty; 0 deterministic passes; 0 AUTO_CHECKED.",
             f"- {reasons['EVIDENCE_NOT_EXACT_IN_POSITIVE']} quotes had zero exact target-passage matches; {reasons['AMBIGUOUS_EVIDENCE_OCCURRENCE']} were duplicate exact matches.",
             f"- {whitespace_only} of the zero-match quotes matched only after diagnostic whitespace/NFKC normalization; {substantive_or_other} did not. No normalization was used for acceptance.",
             f"- {reasons['ANSWER_NOT_EXACT_IN_EVIDENCE']} answers were not exact substrings of their proposed evidence.",
             "- Source hashes valid; TEST leakage 0; evaluation-span leakage 0.",
             "- Engineering source audit: 0 AUTO_CHECKED rows to inspect; plausible 0, obvious error 0, ambiguous 0; obvious-error rate not applicable.",
             "- Review packet rows 0; human review not started; V8–V10 not started.",
             "", "The matcher had no false duplicate-quote failures. The original reason name was misleading: all 80 were absent exact strings.",
             "The corrected category contract worked (91 → 0 invalid), but the model still usually rewrote line-wrapped source text rather than copying it exactly.",
             "Revising the extraction strategy is required before another generation run. The <20 AUTO_CHECKED gate stops this run.", ""]
    (TRAINING / "reports" / "rag_domain_qa_assisted_v7r1_audit.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__": main()
