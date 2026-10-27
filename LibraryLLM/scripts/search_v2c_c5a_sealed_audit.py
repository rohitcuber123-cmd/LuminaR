"""C5A sealed context/family audit. No parser, evaluator, model or policy calls.

Only the established pure C2 identity/operation-topology functions are used.
Sealed rows are projected in memory onto the metadata needed by those functions.
Never serialize heldout rows, labels, identifiers, text or topology strings.
The only row identifiers emitted belong to the NEW input being audited.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
PREFIX = "search_v2c_c5a_"
SCOPE_ALIASES = {
    "PUBLIC_TENANT_PATRON": "PUBLIC_PATRON",
    "PUBLIC_TENANT_STAFF": "PUBLIC_STAFF",
    "PRIVATE_TENANT_PATRON": "PRIVATE_PATRON",
    "PRIVATE_TENANT_STAFF": "PRIVATE_STAFF",
}
ROW_FIELDS = frozenset({
    "query_text", "search_mode", "scope_type", "workspace_type",
    "requires_native_execution", "expected_action", "family_id",
    "structural_family_id", "structural_component_id",
})


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashed(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf8")).hexdigest()


def local_path(value):
    # Manifests contain both Windows absolute and repository-relative paths.
    path = Path(str(value).replace("\\", "/"))
    path = path if path.is_absolute() else ROOT / path
    path = path.resolve()
    if path != ROOT and ROOT not in path.parents:
        raise ValueError("MANIFEST_PATH_OUTSIDE_WORKSPACE")
    return path


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def safe_write(path, value):
    path = path.resolve()
    if path.parent != REPORTS or not path.name.startswith(PREFIX) or path.suffix != ".json":
        raise ValueError("ONLY_NEW_C5A_REPORTS_MAY_BE_WRITTEN")
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf8")


def pure_c2_functions(path, expected_hash):
    if sha256(path) != expected_hash:
        raise ValueError("ESTABLISHED_C2_SOURCE_HASH_MISMATCH")
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    names = {"normalized", "mode", "identity", "structure"}
    selected = [node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in selected} != names:
        raise ValueError("ESTABLISHED_C2_FUNCTIONS_MISSING")
    # No module import or main() invocation; compile only four verified pure defs.
    namespace = {"json": json, "re": re, "unicodedata": unicodedata}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["identity"], namespace["structure"]


def projected_rows(path, *, new=False):
    with path.open(encoding="utf-8-sig") as source:
        for line in source:
            if not line.strip():
                continue
            # JSON decoding is unavoidable; gold/prediction fields are never read.
            raw = json.loads(line)
            row = {key: raw[key] for key in ROW_FIELDS if key in raw}
            if new:
                case_id = raw.get("case_id", raw.get("query_id"))
                if not isinstance(case_id, str) or not case_id:
                    raise ValueError("NEW_CASE_IDENTIFIER_MISSING")
                row["new_case_id"] = case_id
            del raw
            scope = row.get("scope_type")
            row["scope_type"] = SCOPE_ALIASES.get(scope, scope)
            if row["scope_type"] == "GLOBAL":
                row["workspace_type"] = "GLOBAL"
            elif row["scope_type"] in {"PUBLIC_PATRON", "PRIVATE_PATRON"}:
                row["workspace_type"] = "PATRON"
            elif row["scope_type"] in {"PUBLIC_STAFF", "PRIVATE_STAFF"}:
                row["workspace_type"] = "STAFF"
            if not all(key in row for key in ("query_text", "search_mode", "scope_type", "workspace_type")):
                raise ValueError("STRUCTURAL_INPUT_FIELDS_MISSING")
            yield row


def fingerprints(row, scopes, identity, structure):
    return {
        "canonical_context_sha256": hashed(identity(row, scopes)),
        "operation_topology_sha256": hashed(structure(row)),
        "family_sha256": hashed(row["family_id"]) if row.get("family_id") else None,
        "component_sha256": hashed(row.get("structural_family_id") or row.get("structural_component_id"))
        if row.get("structural_family_id") or row.get("structural_component_id") else None,
    }


def indices(paths, scopes, identity, structure):
    result = {key: set() for key in ("canonical_context_sha256", "operation_topology_sha256", "family_sha256", "component_sha256")}
    rows = 0
    for path in paths:
        for row in projected_rows(path):
            rows += 1
            for key, value in fingerprints(row, scopes, identity, structure).items():
                if value is not None:
                    result[key].add(value)
    return result, rows


def audit(input_path, output_path):
    c2_path = REPORTS / "search_v2c_c2_benchmark_v2_manifest.json"
    c2_holdout_path = REPORTS / "search_v2c_c2_holdout_manifest.json"
    c3_path = REPORTS / "search_v2c_c3_sealed_manifest.json"
    original_path = REPORTS / "search_v2c_c_holdout_manifest.json"
    baseline_path = REPORTS / "search_v2c_c5a_baseline.json"
    scope_path = REPORTS / "search_v2c_c_scope_vocabularies.json"
    c2 = load_json(c2_path)
    c2_holdout = load_json(c2_holdout_path)
    c3 = load_json(c3_path)
    original = load_json(original_path)
    baseline = load_json(baseline_path)
    scopes = load_json(scope_path)
    expected = {}
    for entry in c2["files"] + original["files"] + original["legacy_original_manifest"]["files"]:
        expected[local_path(entry["path"])] = entry["sha256"]
    for entry in c3["outputs"]:
        # Preserve sealed heldout using the C3 manifest; do not read C3 labels.
        if entry.get("split") == "heldout":
            expected[local_path(entry["path"])] = entry["sha256"]
    # All metadata manifests used here must agree with the initial C5A baseline.
    baseline_expected = {local_path(name): value for name, value in baseline["historical_evidence_hashes"].items()}
    for path in [c2_path, c2_holdout_path, c3_path, original_path, scope_path]:
        if path not in baseline_expected:
            raise ValueError("REQUIRED_MANIFEST_MISSING_FROM_INITIAL_BASELINE")
        expected[path] = baseline_expected[path]
    c2_source = ROOT / "scripts" / "search_v2c_c2_benchmark.py"
    source_hash = next(value for name, value in c2_holdout["source_hashes"].items()
                       if str(name).replace("\\", "/") == "scripts/search_v2c_c2_benchmark.py")
    expected[c2_source] = source_hash
    before = {path: sha256(path) for path in expected}
    mismatch = [str(path.relative_to(ROOT)) for path in expected if before[path] != expected[path]]
    if mismatch:
        raise ValueError("FROZEN_INPUT_HASH_MISMATCH:" + ",".join(mismatch))
    identity, structure = pure_c2_functions(c2_source, source_hash)
    development = [local_path(entry["path"]) for entry in c2["files"] if entry["split"] == "development"]
    heldout = [local_path(entry["path"]) for entry in c2["files"] if entry["split"] == "heldout"]
    heldout += [local_path(entry["path"]) for entry in c3["outputs"] if entry.get("split") == "heldout"]
    calibration = [local_path(entry["path"]) for entry in c2["files"] if entry["split"] == "calibration"]
    development_index, development_rows = indices(development, scopes, identity, structure)
    heldout_index, heldout_rows = indices(heldout, scopes, identity, structure)
    old_calibration_index, old_calibration_rows = indices(calibration, scopes, identity, structure)
    input_exists = input_path.exists()
    input_hash = sha256(input_path) if input_exists else None
    collisions = []
    counts = Counter()
    new_contexts = Counter()
    new_ids = Counter()
    new_rows = []
    if input_exists:
        for row in projected_rows(input_path, new=True):
            fp = fingerprints(row, scopes, identity, structure)
            case_id = row["new_case_id"]
            new_ids[case_id] += 1
            new_contexts[fp["canonical_context_sha256"]] += 1
            new_rows.append((case_id, fp))
            matches = {}
            for partition, index in (("development", development_index), ("heldout", heldout_index), ("original_calibration", old_calibration_index)):
                kinds = [key for key, value in fp.items() if value and value in index[key]]
                if kinds:
                    matches[partition] = kinds
                    counts[partition + "_colliding_new_cases"] += 1
                    for key in kinds:
                        counts[partition + "_" + key + "_colliding_new_cases"] += 1
            if matches:
                # These IDs and hashes describe NEW rows only, never sealed IDs.
                collisions.append({"new_case_id": case_id, **fp, "collision_types_by_partition": matches,
                                   "required_action": "DISCARD_NEW_CASE" if "development" in matches or "heldout" in matches else "RECONCILE_RETAINED_OR_REPLACEMENT_ACCOUNTING"})
    after = {path: sha256(path) for path in expected}
    if before != after or (input_exists and sha256(input_path) != input_hash):
        raise ValueError("INPUT_CHANGED_DURING_AUDIT")
    forbidden_ids = {entry["new_case_id"] for entry in collisions if "development" in entry["collision_types_by_partition"] or "heldout" in entry["collision_types_by_partition"]}
    duplicate_rows = [{"new_case_id": case_id, "canonical_context_sha256": fp["canonical_context_sha256"]}
                      for case_id, fp in new_rows if new_contexts[fp["canonical_context_sha256"]] > 1]
    result = {
        "version": "C5A-sealed-structural-audit-v1",
        "status": "NOT_RUN_INPUT_ABSENT" if not input_exists else "FORBIDDEN_OVERLAP_DETECTED" if forbidden_ids else "DUPLICATES_DETECTED" if duplicate_rows or any(v > 1 for v in new_ids.values()) else "PASS",
        "input_path": str(input_path.relative_to(ROOT)), "input_sha256": input_hash,
        "new_case_count": len(new_rows), "new_unique_contexts": len(new_contexts),
        "new_duplicate_context_excess_rows": sum(v-1 for v in new_contexts.values()),
        "duplicate_new_case_ids": [key for key, value in new_ids.items() if value > 1],
        "duplicate_new_context_rows": duplicate_rows,
        "forbidden_colliding_new_case_count": len(forbidden_ids),
        "collision_counts": dict(counts), "colliding_new_rows": collisions,
        "baseline_counts": {"development_rows": development_rows, "current_heldout_source_rows": heldout_rows,
                            "current_heldout_unique_contexts": len(heldout_index["canonical_context_sha256"]),
                            "original_calibration_rows": old_calibration_rows,
                            "development_heldout_canonical_overlap": len(development_index["canonical_context_sha256"] & heldout_index["canonical_context_sha256"]),
                            "development_heldout_operation_topology_overlap": len(development_index["operation_topology_sha256"] & heldout_index["operation_topology_sha256"])},
        "method": {"canonical_context": "Established C2 identity; alias scopes normalized to original scope keys and canonical workspace. Full original capability profile; no gold or prediction used.",
                   "structural_family": "Established C2 operation topology WITHOUT scope, plus established family/component hash comparisons. New IDs cannot bypass established topology.",
                   "rejected_remediation": "Do not move, reveal or rewrite heldout/development. Discard colliding NEW calibration rows.",
                   "topology_strings_emitted": False, "heldout_case_ids_emitted": False},
        "preservation": [{"path": str(path.relative_to(ROOT)), "manifest_sha256": expected[path], "sha256_before": before[path], "sha256_after": after[path], "unchanged": True}
                         for path in expected],
        "calibration_parser_evaluations": 0, "heldout_parser_evaluations": 0,
        "heldout_policy_evaluations": 0, "parser_calls": 0, "evaluator_calls": 0, "model_calls": 0, "policy_calls": 0,
        "gold_fields_accessed": [], "heldout_query_text_emitted": False,
        "heldout_labels_emitted": False, "heldout_predictions_accessed_or_emitted": False,
    }
    safe_write(output_path, result)
    audit_path = REPORTS / (PREFIX + "sealed_access_audit.json")
    previous = load_json(audit_path) if audit_path.exists() else {"version": "C5A-sealed-access-audit-v1", "runs": []}
    previous["runs"].append({
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "tool_sha256": sha256(Path(__file__)),
        "input_path": result["input_path"], "input_sha256": input_hash, "result_path": str(output_path.relative_to(ROOT)),
        "status": result["status"], "sealed_files_structurally_read": [str(path.relative_to(ROOT)) for path in heldout],
        "sealed_structural_source_rows_read": heldout_rows,
        "fields_projected": sorted(ROW_FIELDS), "sealed_case_ids_projected": False,
        "gold_fields_read": [], "predictions_read": False, "heldout_text_or_topology_emitted": False,
        "parser_calls": 0, "evaluator_calls": 0, "model_calls": 0, "policy_calls": 0,
        "frozen_inputs_unchanged": True, "only_new_c5a_reports_written": True,
    })
    previous.update({"parser_calls": 0, "evaluator_calls": 0, "model_calls": 0, "policy_calls": 0,
                     "heldout_text_labels_predictions_or_topology_emitted": False,
                     "original_heldout_files_changed": False})
    safe_write(audit_path, previous)
    return {key: result[key] for key in ("status", "new_case_count", "new_unique_contexts", "new_duplicate_context_excess_rows", "forbidden_colliding_new_case_count", "collision_counts")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="reports/search_v2c_c5a_author_draft.jsonl")
    parser.add_argument("--output", default="reports/search_v2c_c5a_family_isolation_initial.json")
    args = parser.parse_args()
    try:
        input_path, output_path = local_path(args.input), local_path(args.output)
        if input_path.parent != REPORTS or not input_path.name.startswith(PREFIX) or input_path.suffix != ".jsonl":
            raise ValueError("INPUT_MUST_BE_NEW_C5A_JSONL")
        print(json.dumps(audit(input_path, output_path)))
    except Exception as error:
        # Never print row payloads, parsing snippets or traceback locals.
        print(json.dumps({"status": "AUDIT_ERROR", "error_type": type(error).__name__,
                          "reason": str(error) if isinstance(error, ValueError) and not isinstance(error, json.JSONDecodeError) else "RESTRICTED_ERROR_NO_PAYLOAD"}))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
