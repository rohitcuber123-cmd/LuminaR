"""Frozen DEVELOPMENT-only C3 scoring; no calibration/heldout entry point.

The original C2 scorer remains the raw metric definition. A parser result is
produced once, then its retained plan is rescored for explicitly separated
representation and independently reviewed-label views.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "reports"
DEVELOPMENT = R / "search_v2c_c2_v2_development.jsonl"
FREEZE = R / "search_v2c_c3_freeze.json"
VERSION = "V2C-C Development v3"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT)).replace("\\", "/")


def write(name, value):
    assert name.startswith("search_v2c_c3_") and "/" not in name and "\\" not in name
    (R / name).write_text(json.dumps(value, indent=2, default=str) + "\n", encoding="utf-8")


def required_frozen_files():
    paths = list((ROOT / "search").glob("query_*.py")) + [ROOT / name for name in [
        "search/session_store.py", "search/scope_authorization.py",
        "scripts/search_v2c_c_evaluate.py", "scripts/search_v2c_c3_evaluate.py",
        "scripts/search_v2c_c3_native_evaluate.py", "tests/institution_v2g/test_query_v2c_c3_native.py",
        "reports/search_v2c_c2_v2_development.jsonl", "reports/search_v2c_c_scope_vocabularies.json",
        "reports/search_v2c_c3_native_contract_v2.json", "reports/search_v2c_c3_delta_plan_contract_v2.json",
        "reports/search_v2c_c3_legacy_gold_v2.json", "reports/search_v2a_facet_vocabulary.json",
        "reports/search_v2c_a_gold_queries.jsonl", "reports/search_v2c_a_metamorphic_queries.jsonl",
        "tests/test_search_v2c_a.py",
    ]]
    return sorted({relative(p) for p in paths})


def verify_frozen(extra_paths=()):
    """Validate bytes only. Importing this module never imports the parser."""
    if not FREEZE.exists():
        raise RuntimeError("Final C3 freeze is required before execution: " + str(FREEZE))
    frozen = read_json(FREEZE)
    hashes = {}
    for key in ("files", "source_hashes", "file_hashes", "input_hashes", "corpus_hashes", "evaluator_hashes"):
        values = frozen.get(key, {})
        if isinstance(values, dict):
            for path, value in values.items():
                digest = value.get("sha256") if isinstance(value, dict) else value
                if isinstance(digest, str) and len(digest) == 64:
                    hashes[relative(ROOT / path)] = digest.lower()
        elif isinstance(values, list):
            for item in values:
                if isinstance(item, dict) and item.get("path") and item.get("sha256"):
                    hashes[relative(ROOT / item["path"])] = item["sha256"].lower()
    required = set(required_frozen_files()) | {relative(ROOT / p) for p in extra_paths}
    missing = sorted(required - hashes.keys())
    if missing:
        raise RuntimeError("C3 freeze omits required sources/inputs: " + ", ".join(missing))
    changed = [path for path, digest in hashes.items() if not (ROOT / path).is_file() or sha256(ROOT / path) != digest]
    if changed:
        raise RuntimeError("C3 source/input changed after final freeze: " + ", ".join(changed))
    return frozen


def development_population():
    rows = read_rows(DEVELOPMENT)
    if not rows or any(r.get("split") != "development" or r.get("benchmark_version") != "V2C-C-Benchmark-v2" for r in rows):
        raise RuntimeError("Only the complete explicit C2 V2 DEVELOPMENT population is authorized")
    ids = [r["query_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Duplicate development IDs must not be counted")
    return rows


def both_normalization_proof():
    """Verify the existing predicate structure without invoking the parser."""
    path = ROOT / "search/query_plan.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    matches = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "matches")
    loop = next(n for n in matches.body if isinstance(n, ast.For) and ast.unparse(n.iter) == "plan.formats")
    conditions = [ast.unparse(n.test) for n in loop.body if isinstance(n, ast.If)]
    required = ["fmt in ('ONLINE', 'BOTH') and book.get('has_online') is not True",
                "fmt in ('PHYSICAL', 'BOTH') and book.get('has_physical') is not True"]
    if conditions != required or len(loop.body) != 2 or loop.orelse:
        raise RuntimeError("BOTH predicate structure changed; representation equivalence needs a fresh proof")
    if any(len(n.body) != 1 or not isinstance(n.body[0], ast.Return) or not isinstance(n.body[0].value, ast.Constant) or n.body[0].value.value is not False or n.orelse for n in loop.body):
        raise RuntimeError("BOTH normalization proof cannot establish conjunctive rejection")
    truth = []
    for online in (False, True, None):
        for physical in (False, True, None):
            truth.append({"has_online": online, "has_physical": physical,
                          "BOTH_accepts": online is True and physical is True,
                          "ONLINE_and_PHYSICAL_accepts": online is True and physical is True})
    return {"rule": "formats ONLY: expand BOTH into ONLINE and PHYSICAL; compare conjunctive sets",
            "source": relative(path), "source_sha256": sha256(path), "source_conditions": conditions,
            "proof": "matches iterates every format conjunctively. BOTH rejects missing online and missing physical. Two separate ONLINE/PHYSICAL operands impose exactly these same predicates, including unknown/missing values.",
            "truth_table": truth, "applied_to": "all expected and actual formats, every row in the representation-normalized view",
            "does_not_normalize": ["excluded subject versus broad text", "exclusive_formats", "excluded_formats", "decision", "intent"],
            "raw_metrics_retained": True, "parser_calls": 0}


def normalize_both(plan):
    normalized = deepcopy(plan)
    values = normalized.get("formats")
    if values is not None:
        if isinstance(values, str):
            values = [values]
        normalized["formats"] = sorted({expanded for value in values for expanded in (["ONLINE", "PHYSICAL"] if str(value).upper() == "BOTH" else [str(value).upper()])})
    return normalized


def load_development_overrides(path, cases):
    if path is None:
        return {}, None
    document = read_json(ROOT / path)
    if document.get("review_status") != "AI_REVIEWED" or document.get("parser_output_visible") is not False:
        raise RuntimeError("Development overrides require independently output-blind AI_REVIEWED provenance")
    overrides = document.get("overrides")
    if not isinstance(overrides, dict):
        raise RuntimeError("Development override contract requires overrides keyed by query_id")
    population = {r["query_id"] for r in cases if not r.get("requires_native_execution")}
    allowed_extra = {"execution_allowed", "rating_min_exclusive", "rating_max_exclusive", "year_min_exclusive", "year_max_exclusive"}
    for query_id, changes in overrides.items():
        if query_id not in population or not isinstance(changes, dict):
            raise RuntimeError("Override is outside DEVELOPMENT parser population: " + query_id)
        if any(not key.startswith("expected_") and key not in allowed_extra for key in changes):
            raise RuntimeError("Override may only change authored expected fields: " + query_id)
    return overrides, {"path": relative(ROOT / path), "sha256": sha256(ROOT / path), "cases": len(overrides), "review_status": "AI_REVIEWED", "parser_output_visible": False}


def rescore(case, raw, normalize_formats=False):
    """C2 definitions applied to retained actual output; no second parser call."""
    from scripts.search_v2c_c_evaluate import expected, norm, atoms, token_f1
    row = deepcopy(raw)
    actual, gold = deepcopy(raw["actual_plan"]), expected(case)
    if normalize_formats:
        actual, gold = normalize_both(actual), normalize_both(gold)
    actual_kind, allow, wanted = raw["decision"], raw["execution"], case["execution_allowed"]
    expected_kind = {"AUTO_EXECUTE": "EXECUTABLE", "EXECUTE_WITH_NOTICE": "EXECUTABLE_WITH_NOTICE"}.get(case["expected_decision"], case["expected_decision"])
    mismatch = {k: {"expected": v, "actual": actual.get(k)} for k, v in gold.items() if norm(actual.get(k)) != norm(v)}
    if actual_kind != expected_kind:
        mismatch["decision"] = {"expected": expected_kind, "actual": actual_kind}
    if allow != wanted:
        mismatch["execution_allowed"] = {"expected": wanted, "actual": allow}
    for label, kind in [("expected_unsupported_fields", "UNSUPPORTED"), ("expected_incomplete_fields", "INCOMPLETE"), ("expected_contradiction_fields", "CONTRADICTORY")]:
        if label in case:
            affected = actual.get("decision", {}).get("affected_fields", []) if actual_kind == kind else []
            if norm(affected) != norm(case[label]):
                mismatch[label] = {"expected": case[label], "actual": affected}
    ea, aa, justified = atoms(gold, wanted), atoms(actual, allow), atoms(gold, True)
    extra = aa - justified
    comp_expected = [k for k in ("rating_min", "rating_max") if gold.get(k) is not None]
    unsafe = allow and not wanted and (bool(extra) or expected_kind == "CONTRADICTORY" or expected_kind == "UNSUPPORTED" and actual_kind != "EXECUTABLE_WITH_NOTICE")
    row.update(expected_decision=expected_kind, expected_execution=wanted, exact=not mismatch, mismatches=mismatch,
               unsafe_auto_parse=unsafe, safe_typed_decision_miss=allow and not wanted and not unsafe,
               hard_tp=len(ea & aa), hard_fp=len(aa - ea), hard_fn=len(ea - aa), false_filters=[list(x) for x in sorted(extra)],
               comparator_evaluable=bool(comp_expected) and wanted,
               comparator_correct=all(actual.get(k) == gold[k] and actual.get(k + "_exclusive") == gold.get(k + "_exclusive", False) for k in comp_expected),
               negative_correct=all(norm(actual.get(k)) == norm(gold.get(k)) for k in ("exclude_subjects", "exclude_terms") if k in gold),
               subjects_correct=norm(actual.get("subjects")) == norm(gold.get("subjects", [])),
               semantic_exact=norm(actual["semantic_text"]) == norm(gold.get("semantic_text")),
               semantic_f1=token_f1(actual["semantic_text"], gold.get("semantic_text")), actual_plan=actual)
    return row


def metrics_for(rows):
    from scripts.search_v2c_c_evaluate import aggregate, ratio
    metrics = aggregate(rows)
    metrics["ALL_CASE_UNSAFE_AUTO_PARSE_RATE"] = ratio(sum(r["unsafe_auto_parse"] for r in rows), len(rows))
    supported = [r for r in rows if r["expected_decision"] == "CONTRADICTORY" and not any(c.get("code") == "rating_domain_assumption" for c in r.get("label_review_concerns", []))]
    metrics["SUPPORTED_CONTRADICTION_RECALL"] = ratio(sum(r["decision"] == "CONTRADICTORY" for r in supported), len(supported))
    return metrics


def violations_for(metrics):
    violations = []
    for name, operator, limit in [("FALSE_HARD_FILTER_RATE", "<=", 1), ("UNSAFE_AUTO_PARSE_RATE", "<", 3),
        ("SUPPORTED_CONTRADICTION_RECALL", "==", 100), ("PROTECTED_ENTITY_PRESERVATION", ">=", 99),
        ("COMPARATOR_ACCURACY", ">=", 99), ("CROSS_SCOPE_VOCABULARY_LEAKAGE_RATE", "==", 0)]:
        value = metrics[name]["percent"]
        passes = value is not None and {"<=": lambda: value <= limit, "<": lambda: value < limit, ">=": lambda: value >= limit, "==": lambda: value == limit}[operator]()
        if not passes:
            violations.append({"metric": name, "observed": metrics[name], "required": operator + str(limit)})
    return violations


def evaluate_legacy():
    """Keep direct equality and the original raw assertion behavior intact."""
    from search.query_plan import parse_query, matches
    from search.query_session import refine
    from search.query_confidence import validate, executable
    facets = [r["subject"] for r in read_json(R / "search_v2a_facet_vocabulary.json")["results"]]
    interpretation = read_json(R / "search_v2c_c3_legacy_gold_v2.json")
    overrides = interpretation["overrides"]
    result = {"raw_136": [], "reviewed_v2_136": [], "raw_seeded_1000": []}
    for source, raw_key in [("search_v2c_a_gold_queries.jsonl", "raw_136"), ("search_v2c_a_metamorphic_queries.jsonl", "raw_seeded_1000")]:
        cases = read_rows(R / source)
        assert len(cases) == (136 if raw_key == "raw_136" else 1000)
        for case in cases:
            try:
                if case.get("sequence"):
                    plan = None
                    for query in case["sequence"]:
                        plan, _ = refine(plan, query, facets)
                        validate(plan)
                else:
                    plan = parse_query(case["query"], facets, case.get("mode", "SMART"))
                actual = {**vars(plan), "decision_type": plan.decision.get("decision_type", "EXECUTABLE")}
                raw_mismatches = {k: {"expected": v, "actual": actual.get(k)} for k, v in case["expected"].items() if actual.get(k) != v}
                assertion_failures = []
                if raw_key == "raw_136":
                    for candidate in plan.constraint_candidates:
                        text = candidate.get("source_query", plan.raw_query)
                        start, end = candidate["source_span_start"], candidate["source_span_end"]
                        if not (0 <= start < end <= len(text)) or text[start:end] != candidate["source_text"]:
                            assertion_failures.append("invalid_constraint_source_span")
                    if not executable(plan) and matches(plan, {"title": "Any book", "subjects": facets, "average_rating": 5, "has_online": True, "has_physical": True}):
                        assertion_failures.append("blocked_plan_matched_candidate")
                result[raw_key].append({"id": case["id"], "pass": not raw_mismatches and not assertion_failures, "mismatches": raw_mismatches, "assertion_failures": assertion_failures})
                if raw_key == "raw_136":
                    reviewed = deepcopy(case["expected"])
                    reviewed.update({("exclude_subjects" if k == "excluded_subjects" else k): v for k, v in overrides.get(case["id"], {}).items()})
                    differences = {k: {"expected": v, "actual": actual.get(k)} for k, v in reviewed.items() if actual.get(k) != v}
                    result["reviewed_v2_136"].append({"id": case["id"], "pass": not differences and not assertion_failures, "mismatches": differences, "assertion_failures": assertion_failures})
            except Exception as error:
                failure = {"id": case["id"], "pass": False, "status": "UNEXECUTED_ERROR", "error": repr(error)}
                result[raw_key].append(failure)
                if raw_key == "raw_136":
                    result["reviewed_v2_136"].append(deepcopy(failure))
    return {"population": "Immutable accepted historical regressions; not independent real-world evidence", "equality": "Original direct authored-field equality; no BOTH normalization in raw legacy suites", "interpretation_sha256": sha256(R / "search_v2c_c3_legacy_gold_v2.json"),
            **{key: {"passed": sum(row["pass"] for row in rows), "denominator": len(rows), "failures": [row for row in rows if not row["pass"]]} for key, rows in result.items()}}


def prepare(development_overrides=None, require_freeze=True):
    extra = [development_overrides] if development_overrides else []
    if require_freeze:
        verify_frozen(extra)
    cases = development_population()
    contract = read_json(R / "search_v2c_c3_native_contract_v2.json")
    native_ids = {r["query_id"] for r in cases if r.get("requires_native_execution")}
    contract_ids = [r["query_id"] for r in contract["cases"]]
    if len(contract_ids) != len(set(contract_ids)) or set(contract_ids) != native_ids:
        raise RuntimeError("Canonical native contract must cover every unique development native ID")
    overrides, provenance = load_development_overrides(development_overrides, cases)
    return cases, overrides, provenance, both_normalization_proof()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true", help="Validate JSON/populations/proof only; no parser imports/calls. Reports missing freeze requirements if no freeze exists.")
    parser.add_argument("--development-overrides")
    args = parser.parse_args()
    cases, overrides, provenance, proof = prepare(args.development_overrides, require_freeze=not args.prepare_only or FREEZE.exists())
    if args.prepare_only:
        print(json.dumps({"prepared": True, "parser_calls": 0, "development_rows": len(cases), "parser_rows": sum(not r.get("requires_native_execution") for r in cases), "native_rows": sum(bool(r.get("requires_native_execution")) for r in cases), "freeze_exists": FREEZE.exists(), "required_frozen_files": required_frozen_files(), "development_override_provenance": provenance, "BOTH_proof": proof}, indent=2))
        return
    marker = R / "search_v2c_c3_final_execution_started.json"
    with marker.open("x", encoding="utf-8") as out:
        json.dump({"version": VERSION, "started_at_utc": datetime.now(timezone.utc).isoformat(),
                   "freeze_sha256": sha256(FREEZE), "development_sha256": sha256(DEVELOPMENT),
                   "development_override_provenance": provenance,
                   "policy": "One final frozen execution. Do not tune or rerun after observing final development metrics."}, out, indent=2)
        out.write("\n")
    # Historical regression parser calls precede the one final development
    # measurement. Retain these results; do not call the parser after the gate.
    legacy_result = evaluate_legacy()
    from scripts.search_v2c_c_evaluate import evaluate_case
    started = time.perf_counter()
    scopes = read_json(R / "search_v2c_c_scope_vocabularies.json")
    observations, normalized, reviewed, errors = [], [], [], []
    for case in cases:
        if case.get("requires_native_execution"):
            continue
        try:
            row = evaluate_case(case, scopes)
            row.update(query_text=case["query_text"], benchmark_version=case["benchmark_version"], original_split=case.get("original_split"), review_status=case.get("review_status"), label_review_concerns=case.get("label_review_concerns", []), source_spans=row["actual_plan"]["source_spans"], expected_strict_filters={k: v for k, v in case.items() if k.startswith("expected_")})
            # Assert the snapshot rescorer is identical before enabling either
            # representation or independent-label changes.
            check = rescore(case, row)
            for key in ("exact", "mismatches", "unsafe_auto_parse", "hard_tp", "hard_fp", "hard_fn", "false_filters", "comparator_correct", "negative_correct", "subjects_correct", "semantic_exact", "semantic_f1"):
                if check[key] != row[key]:
                    raise RuntimeError("Raw snapshot scorer diverged from C2 metric definition: " + key)
            normalized_row = rescore(case, row, normalize_formats=True)
            reviewed_case = {**case, **overrides.get(case["query_id"], {})}
            review_row = rescore(reviewed_case, row, normalize_formats=True)
            review_row["development_label_override_applied"] = case["query_id"] in overrides
            observations.append(row)
            normalized.append(normalized_row)
            reviewed.append(review_row)
        except Exception as error:
            errors.append({"query_id": case["query_id"], "error": repr(error), "status": "UNEXECUTED_ERROR"})
    expected_count = sum(not r.get("requires_native_execution") for r in cases)
    raw_metrics, normalized_metrics, reviewed_metrics = metrics_for(observations), metrics_for(normalized), metrics_for(reviewed)
    violations = violations_for(reviewed_metrics)
    if errors or len(observations) != expected_count:
        violations.append({"metric": "UNEXECUTED_ROWS", "expected_parser_rows": expected_count, "scored_rows": len(observations), "cases": errors})
    output = {"version": VERSION, "evaluator_version": "c3-development-1", "split": "development", "development_rows": len(cases), "expected_parser_rows": expected_count, "parser_executed": len(observations), "expected_native_rows": len(cases) - expected_count,
              "unexecuted_rows": errors, "all_parser_rows_executed": not errors and len(observations) == expected_count,
              "strict_raw_original_label_metrics": raw_metrics, "representation_normalized_original_label_metrics": normalized_metrics,
              "reviewed_v2_label_metrics": reviewed_metrics, "development_override_provenance": provenance,
              "normalization": proof, "gate_metric_view": "reviewed_v2_label_metrics (original labels if no independent overrides supplied)",
              "mandatory_violations": violations, "status": "STOP_MANDATORY_GATE_FAILURE" if violations else "PARSER_GATES_PASS_ONLY",
              "native_security_gate": "Separate fresh native evaluator; parser-only result cannot authorize calibration",
              "elapsed_s": time.perf_counter() - started, "by_scope": {s: metrics_for([r for r in reviewed if r["scope"] == s]) for s in sorted({r["scope"] for r in reviewed})},
              "calibration_run": False, "heldout_evaluated": False, "no_silent_exclusions": True}
    write("search_v2c_c3_development_metrics.json", output)
    write("search_v2c_c3_format_equivalence.json", proof)
    for name, rows in [("development_observations", observations), ("development_normalized_observations", normalized), ("development_reviewed_observations", reviewed)]:
        (R / ("search_v2c_c3_" + name + ".jsonl")).write_text("".join(json.dumps(row, default=str) + "\n" for row in rows), encoding="utf-8")
    for name, predicate in [("false_hard_filters_after", lambda r: bool(r["false_filters"])), ("unsafe_after", lambda r: r["unsafe_auto_parse"]),
        ("comparators", lambda r: r["comparator_evaluable"]), ("contradictions", lambda r: r["expected_decision"] == "CONTRADICTORY"),
        ("protected_entities", lambda r: r["protected_count"] > 0), ("incomplete", lambda r: r["expected_decision"] == "INCOMPLETE"),
        ("unsupported", lambda r: r["expected_decision"] == "UNSUPPORTED"), ("negative_constraints", lambda r: bool(r["actual_plan"]["exclude_subjects"] or r["actual_plan"]["exclude_terms"]) or not r["negative_correct"])]:
        subset = [r for r in reviewed if predicate(r)]
        write("search_v2c_c3_" + name + ".json", {"population": "Complete DEVELOPMENT parser partition; reviewed view with raw observation links retained", "case_count": len(subset), "cases": subset})
    write("search_v2c_c3_legacy_regression.json", legacy_result)
    verify_frozen([args.development_overrides] if args.development_overrides else [])
    print(json.dumps({"parser_executed": len(observations), "raw_metrics": raw_metrics, "reviewed_metrics": reviewed_metrics, "mandatory_violations": violations}, indent=2))


if __name__ == "__main__":
    main()
