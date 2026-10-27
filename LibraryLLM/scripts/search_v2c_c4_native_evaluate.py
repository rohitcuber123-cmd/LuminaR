"""Score fresh DEVELOPMENT native observations against both retained contracts.

This reads only the explicit C2 development file, C4 machine contracts, and fresh
C4 observations. It never imports or calls the query parser.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from scripts.search_v2c_c4_evaluate import ROOT, R, read_json, read_rows, sha256, verify_frozen, development_population, write


def ratio(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator, "percent": 100 * numerator / denominator if denominator else None}


def status_matches(actual, expected):
    return None if expected is None else actual in expected if isinstance(expected, list) else actual == expected


def _lookup(snapshot, kind, key):
    return next((row for row in snapshot[kind] if row["_id"] == key), None)


def state_oracle(record, contract):
    """Compare captured exact records, rather than infer corruption from HTTP."""
    before, after = record.get("before"), record.get("after")
    bindings = record.get("control_bindings", {})
    if before is None or after is None or not bindings:
        return False, ["missing before/after or exact ownership bindings"]
    oracle = contract["state_oracle_id"]
    failures = []
    if oracle == "no_mutation":
        if before != after:
            failures.append("denied request mutated accepted, pending or profiles")
    elif oracle in ("current_membership_loss", "other_library_membership_loss", "clear_exact_context"):
        target = bindings["B" if oracle == "other_library_membership_loss" else "A"]
        expected = deepcopy(before)
        for kind, key in (("accepted", "sid"), ("pending", "cid")):
            expected[kind] = [row for row in expected[kind] if row["_id"] != target[key]]
        if oracle != "clear_exact_context":
            expected["profiles"].pop(target["profile_key"], None)
        if expected != after:
            failures.append("cleanup differed from the exact authorized ownership boundary")
        if oracle == "other_library_membership_loss":
            first = record.get("boundaries", [{}])[0]
            if first.get("state_before") != first.get("state_after"):
                failures.append("initial wrong-workspace denial mutated state")
    elif oracle == "reject_then_genuine_once":
        target = bindings["A"]
        boundaries = record.get("boundaries", [])
        if len(boundaries) != 3:
            failures.append("invalid/genuine/replay boundaries were not all captured")
        else:
            rejected, genuine, replay = boundaries
            if rejected["state_before"] != rejected["state_after"]:
                failures.append("rejected choice mutated or consumed pending state")
            if replay["status"] != 409 or replay["state_before"] != replay["state_after"]:
                failures.append("replay mutated state or was not409")
            original = _lookup(before, "accepted", target["sid"])
            committed = _lookup(after, "accepted", target["sid"])
            pending = _lookup(after, "pending", target["cid"])
            if not original or not committed or committed.get("version") != original.get("version", 0) + 1:
                failures.append("genuine choice did not commit exactly once")
            if not pending or pending.get("used") is not True:
                failures.append("genuine pending choice was not marked used")
            for kind, key in (("accepted", "sid"), ("pending", "cid")):
                if [r for r in before[kind] if r["_id"] != target[key]] != [r for r in after[kind] if r["_id"] != target[key]]:
                    failures.append("genuine choice changed unrelated " + kind)
            if before["profiles"] != after["profiles"]:
                failures.append("choice sequence changed unrelated personalization")
    elif oracle == "legacy_delta_sequence":
        for key, binding in bindings.items():
            for kind, identifier in (("accepted", "sid"), ("pending", "cid")):
                if _lookup(before, kind, binding[identifier]) != _lookup(after, kind, binding[identifier]):
                    failures.append("delta changed unrelated " + key + " " + kind)
        if before["profiles"] != after["profiles"]:
            failures.append("delta changed unrelated personalization")
        if record.get("delta_execution_allowed") is False and record.get("delta_seed_before") != record.get("delta_seed_after"):
            failures.append("blocked delta overwrote accepted prior")
        if record.get("delta_seed_before") is None or record.get("delta_seed_after") is None:
            failures.append("delta seed before/after evidence missing")
    else:
        failures.append("unknown machine state oracle " + str(oracle))
    return not failures, failures


def privacy_oracle(record, contract):
    failures = []
    boundaries = record.get("boundaries", [])
    if not boundaries:
        failures.append("response/body boundary evidence missing")
    for boundary in boundaries:
        if boundary.get("status", 0) >= 400:
            body = boundary.get("response_body")
            if not isinstance(body, dict) or set(body) != {"detail"} or not isinstance(body["detail"], str):
                failures.append("non-generic denial response at " + boundary.get("label", "unknown"))
    expected_detail = contract.get("body_or_error", {}).get("canonical_detail")
    if expected_detail is not None and record.get("response_body") != {"detail": expected_detail}:
        failures.append("primary denial differs from canonical generic error body")
    if any(record.get(key) for key in ("private_leak", "foreign_profile_used", "global_fallback_used")):
        failures.append("explicit privacy or scope fallback violation recorded")
    return not failures, failures


def reviewed_delta(record, contract):
    gold = contract["normative_v2"]
    actual = record.get("delta_plan", {})
    accepted = (record.get("delta_seed_after") or {}).get("current_plan", {})
    prior = record.get("delta_seed_before") or {}
    after = record.get("delta_seed_after") or {}
    mismatches = {}
    actual_decision = actual.get("decision", {}).get("decision_type", "EXECUTABLE")
    if actual_decision != gold["decision"]:
        mismatches["decision"] = {"expected": gold["decision"], "actual": actual_decision}
    if record.get("delta_execution_allowed") != gold["execution_allowed"]:
        mismatches["execution_allowed"] = {"expected": gold["execution_allowed"], "actual": record.get("delta_execution_allowed")}
    for field, value in gold["accepted_plan_after"].items():
        if accepted.get(field) != value:
            mismatches["accepted_plan_after." + field] = {"expected": value, "actual": accepted.get(field)}
    version_delta = after.get("version", 0) - prior.get("version", 0)
    if version_delta != gold["accepted_version_delta"]:
        mismatches["accepted_version_delta"] = {"expected": gold["accepted_version_delta"], "actual": version_delta}
    if "emitted_hard_rating_bound" in gold and any(actual.get(k) is not None for k in ("rating_min", "rating_max")):
        mismatches["emitted_hard_rating_bound"] = {"expected": None, "actual": {k: actual.get(k) for k in ("rating_min", "rating_max")}}
    return {"query_id": record["query_id"], "mismatches": mismatches, "pass": not mismatches, "provenance": contract["review_provenance"]}


def evaluate(observations_path):
    verify_frozen()
    cases = [r for r in development_population() if r.get("requires_native_execution")]
    original = {r["query_id"]: r for r in cases}
    document = read_json(R / "search_v2c_c4_native_contract_v2.json")
    contracts = {r["query_id"]: r for r in document["cases"]}
    if len(contracts) != len(document["cases"]) or contracts.keys() != original.keys():
        raise RuntimeError("Canonical native contract does not cover complete unique DEVELOPMENT population")
    rows = read_rows(observations_path)
    ids = [r["query_id"] for r in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(original):
        raise RuntimeError("Fresh native observations must contain exactly all DEVELOPMENT native IDs once")
    scored = []
    for row in rows:
        contract = contracts[row["query_id"]]
        state_ok, state_failures = state_oracle(row, contract)
        privacy_ok, privacy_failures = privacy_oracle(row, contract)
        historical = status_matches(row.get("actual_status"), original[row["query_id"]].get("expected_http_status"))
        canonical = status_matches(row.get("actual_status"), contract["expected_statuses"])
        extra_status_ok = True
        later = contract.get("request", {}).get("later_request")
        if later:
            extra_status_ok = row.get("post_revocation_status") == later["status"]
        scored.append({"query_id": row["query_id"], "scope": row["scope"], "action": row.get("action"),
                       "historical_expected": original[row["query_id"]].get("expected_http_status"), "canonical_v2_expected": contract["canonical_v2_expected"], "actual": row.get("actual_status"),
                       "historical_status_match": historical, "canonical_v2_status_match": canonical, "later_status_match": extra_status_ok,
                       "state_oracle_match": state_ok, "state_failures": state_failures, "privacy_oracle_match": privacy_ok, "privacy_failures": privacy_failures,
                       "harness_result": row.get("result"), "state_oracle_id": contract["state_oracle_id"], "response_body": row.get("response_body"), "actual_error_class": row.get("actual_error_class"),
                       "expected_error_class": contract["body_or_error"]["class"], "native_boundary_count": len(row.get("boundaries", [])), "parser_only": row.get("parser_only")})
    historical_rows = [r for r in scored if r["historical_status_match"] is not None]
    security = [r for r in rows if original[r["query_id"]].get("security_case")]
    unsafe = [r for r in security if r.get("actual_status") == 200 and not original[r["query_id"]]["execution_allowed"]]
    deltas = {r["query_id"]: r for r in read_json(R / "search_v2c_c4_delta_plan_contract_v2.json")["cases"]}
    delta_scores = [reviewed_delta(r, deltas[r["query_id"]]) for r in rows if r["query_id"] in deltas]
    if len(delta_scores) != len(deltas):
        raise RuntimeError("Reviewed delta contracts were not all executed")
    state_failures = [r for r in scored if not r["state_oracle_match"]]
    privacy_failures = [r for r in scored if not r["privacy_oracle_match"]]
    failures = [r for r in scored if r["harness_result"] == "FAIL"]
    result = {"version": "V2C-C Development v4 native", "native_contract_version": document["version"], "observations": str(observations_path), "observations_sha256": sha256(observations_path),
              "native_rows": len(rows), "unique_executed_ids": ids, "unexecuted": [], "parser_only_substitutions": sum(bool(r.get("parser_only")) for r in rows),
              "historical_status_agreement": ratio(sum(r["historical_status_match"] for r in historical_rows), len(historical_rows)),
              "canonical_v2_status_agreement": ratio(sum(r["canonical_v2_status_match"] and r["later_status_match"] for r in scored), len(scored)),
              "state_oracle_agreement": ratio(len(rows) - len(state_failures), len(rows)), "privacy_oracle_agreement": ratio(len(rows) - len(privacy_failures), len(rows)),
              "historical_status_disagreements": [r for r in scored if r["historical_status_match"] is False],
              "canonical_v2_status_disagreements": [r for r in scored if not r["canonical_v2_status_match"] or not r["later_status_match"]],
              "state_oracle_failures": state_failures, "privacy_oracle_failures": privacy_failures, "harness_failures": failures,
              "security_family_unsafe_auto_parse": ratio(len(unsafe), len(security)), "session_corruption_rate": ratio(len(state_failures), len(rows)), "private_leaks": len(privacy_failures),
              "private_leak_count_semantics": "Failed exact generic-body/scope privacy oracles; failures retain reasons and are not inferred from arbitrary HTTP status differences.",
              "raw_legacy_delta_mismatches": [{"query_id": r["query_id"], "mismatches": r["delta_mismatches"]} for r in rows if r.get("delta_mismatches")],
              "reviewed_v2_delta_cases": delta_scores, "reviewed_v2_delta_agreement": ratio(sum(r["pass"] for r in delta_scores), len(delta_scores)),
              "cases": scored, "production_index_builds": 0, "calibration_run": False, "heldout_evaluated": False,
              "status": "FAIL" if state_failures or privacy_failures or failures or unsafe or any(not r["canonical_v2_status_match"] or not r["later_status_match"] for r in scored) else "PASS_NATIVE_CONTRACT_ONLY"}
    verify_frozen()
    write("search_v2c_c4_native_metrics.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, default=R / "search_v2c_c4_native_current/search_v2c_c4_native_observations.jsonl")
    args = parser.parse_args()
    result = evaluate(args.observations)
    print(json.dumps({k: result[k] for k in ("status", "native_rows", "historical_status_agreement", "canonical_v2_status_agreement", "state_oracle_agreement", "privacy_oracle_agreement", "security_family_unsafe_auto_parse", "reviewed_v2_delta_agreement")}, indent=2))


if __name__ == "__main__":
    main()
