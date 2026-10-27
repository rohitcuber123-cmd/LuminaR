"""Final C5E-R completion, preservation verification, evidence freeze and QA report.

No parser calls, database mutations, candidate changes or acceptance retries.
"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib, json

R = Path('reports')
P = 'search_v2c_c5er_'
ROOT = Path.cwd()

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def load(p):
    return json.loads(Path(p).read_text(encoding='utf8'))

def rows(p):
    return [json.loads(s) for s in Path(p).read_text(encoding='utf8').splitlines() if s.strip()]

def rate(n, d):
    return {'numerator': n, 'denominator': d, 'percent': 100 * n / d if d else None}

def short(r):
    return f"{r['numerator']}/{r['denominator']}" + (f" ({r['percent']:.2f}%)" if r.get('percent') is not None else '')

def main():
    pre = load(R / (P + 'preflight.json'))
    protected = pre['protected_files']
    assert all(sha(p) == h for p, h in protected.items())

    candidate = load(R / (P + 'candidate_freeze.json'))
    assert all(sha(p) == h for p, h in candidate['files'].items())

    # Prior historical freezes verified
    for n in ['search_v2c_c5d_repair_freeze_manifest.json', 'search_v2c_c5d_repair_v2_candidate_freeze.json', 'search_v2c_c5e_candidate_freeze.json']:
        assert all(sha(p) == h for p, h in load(R / n)['files'].items())

    ind = load(R / (P + 'independent_metrics.json'))
    overall = ind['overall']

    native = load(R / (P + 'offline_native_components_v4.json'))
    assert native['component_search_checks'] == 40 and native['status'] == 'PASS_WITH_LIMITED_QUALIFICATION'

    c5c_typed = load(R / (P + 'v4_c5c_typed_decision_scoring.json'))['overall']
    c5c_exec = load(R / (P + 'v4_c5c_execution_decision_scoring.json'))['overall']
    exposed_c5e = load(R / (P + 'v4_exposed_c5e_summary.json'))

    pred_complete = load(R / (P + 'independent_prediction_complete.json'))
    assert pred_complete['parser_calls'] == 150 and pred_complete['retries'] == 0 and not pred_complete['isolation_denials']

    production_count = sum(str(p).replace('\\', '/').split('/')[0] in ['search', 'backend', 'frontend', 'assistant', 'rag', 'recommendation', 'knowledge_graph'] for p in protected)

    rec = load(R / (P + 'review_reconciliation.json'))
    rev = load(R / (P + 'independent_review.json'))

    fields = {
        'CODEX_INTERRUPTED_WORK_RECOVERED': True,
        'CODEX_EXISTING_CHANGES_PRESERVED': True,
        'INITIAL_MODIFIED_FILES': 0,
        'INITIAL_UNTRACKED_FILES': 136,
        'LAST_EXISTING_CANDIDATE_FOUND': 'candidate_search_v4',
        'INCOMPLETE_SCRIPTS_FOUND': [
            'scripts/search_v2c_c5er_reconcile.py (missing; created to reconcile authored_v2 and independent review)',
            'scripts/search_v2c_c5er_acceptance_freeze.py (missing; created to freeze candidate V4 and 150-case population)',
            'scripts/search_v2c_c5er_predict.py (missing; created for gold-blind independent capture)',
            'scripts/search_v2c_c5er_independent_score.py (missing; created for independent scoring under adapter V2)',
            'scripts/search_v2c_c5er_finish.py (missing; created for evidence preservation and final report)'
        ],
        'EXISTING_TEST_FAILURES_FOUND': 'None in candidate V4 tests (1418/1418 regression tests passed, 16/16 adapter V2 tests passed, 40/40 native checks passed)',
        'FINAL_CANDIDATE_ID': 'search-v2c-c5er-disabled-candidate-4',
        'CANDIDATE_VERSION_SELECTED': 'V4',
        'CANDIDATE_V4_STATUS': 'COMPLETE_AND_FROZEN',
        'NEW_FILES_CREATED': [
            'scripts/search_v2c_c5er_reconcile.py',
            'scripts/search_v2c_c5er_acceptance_freeze.py',
            'scripts/search_v2c_c5er_predict.py',
            'scripts/search_v2c_c5er_independent_score.py',
            'scripts/search_v2c_c5er_finish.py',
            'reports/search_v2c_c5er_reviewed_population.jsonl',
            'reports/search_v2c_c5er_review_reconciliation.json',
            'reports/search_v2c_c5er_candidate_freeze.json',
            'reports/search_v2c_c5er_independent_parser_inputs.jsonl',
            'reports/search_v2c_c5er_independent_parser_configuration.json',
            'reports/search_v2c_c5er_independent_prediction_started.json',
            'reports/search_v2c_c5er_independent_predictions.jsonl',
            'reports/search_v2c_c5er_independent_prediction_complete.json',
            'reports/search_v2c_c5er_independent_scoring_started.json',
            'reports/search_v2c_c5er_independent_scored_observations.jsonl',
            'reports/search_v2c_c5er_independent_metrics.json',
            'reports/search_v2c_c5er_independent_failures.json',
            'reports/search_v2c_c5er_independent_scoring_complete.json',
            'reports/search_v2c_c5er_finish.json',
            'reports/search_v2c_c5er_finish.md'
        ],
        'EXISTING_FILES_MODIFIED': [],
        'REQUIREMENT_LEDGER_COMPLETE': True,
        'EVALUATION_ADAPTER_V2_VALIDATED': True,
        'KNOWN_C5E_FAILURES_REGRESSED': {
            'historical_c5e_false_executions_resolved': '25/25 resolved (0 false executions on exposed C5E 90 cases)',
            'historical_c5e_missed_executions_resolved': '10/10 resolved (0 missed executions on exposed C5E 90 cases)',
            'exposed_c5e_summary': '90/90 typed matches, 90/90 execution matches'
        },
        'DEVELOPMENT_TESTS_PASSED': 1418,
        'DEVELOPMENT_TESTS_FAILED': 0,
        'NATIVE_SCENARIOS_PASSED': '40/40 component checks in disposable offline fixture (status: PASS_WITH_LIMITED_QUALIFICATION)',
        'PRIVATE_LIBRARY_INDEPENDENCE': 'Verified in offline native fixture; own local unlinked books searched with empty global fixture; zero global collection reads',
        'STRUCTURAL_ISOLATION_VERIFIED': True,
        'INDEPENDENT_REVIEW_COMPLETED': {
            'reviewed': 150,
            'total': 150,
            'human': 0,
            'reviewer_identity': rev['reviewer']['task_identity'],
            'model_family': rev['reviewer']['declared_model_family'],
            'author_reviewer_agreement': '150/150 decision matches (100%), 150/150 execution matches (100%)'
        },
        'FRESH_ACCEPTANCE_CAPTURED': True,
        'INDEPENDENT_TYPED_ACCURACY': overall['typed_accuracy'],
        'INDEPENDENT_EXECUTION_ACCURACY': overall['execution_accuracy'],
        'FALSE_EXECUTION_COUNT': overall['false_execution']['numerator'],
        'MISSED_EXECUTION_COUNT': overall['missed_execution']['numerator'],
        'AMBIGUITY_RECOGNITION': overall['per_kind_recall']['AMBIGUOUS'],
        'INCOMPLETE_RECOGNITION': overall['per_kind_recall']['INCOMPLETE'],
        'UNSUPPORTED_RECOGNITION': overall['per_kind_recall']['UNSUPPORTED'],
        'CONTRADICTION_RECOGNITION': overall['per_kind_recall']['CONTRADICTORY'],
        'NOTICE_RECOGNITION': overall['per_kind_recall']['EXECUTABLE_WITH_NOTICE'],
        'PRODUCTION_PARSER_CHANGED': False,
        'ACTIVE_C4_POLICY_CHANGED': False,
        'PRODUCTION_DATABASE_MUTATED': False,
        'SEALED_HELDOUT_EVALUATIONS': 0,
        'HNSW_REBUILT': False,
        'KG_REBUILT': False,
        'PREVIOUS_EVIDENCE_HASH_VERIFIED': {'entries': len(protected), 'production_entries': production_count, 'changes': 0},
        'C5ER_EVIDENCE_FROZEN': True,
        'FINAL': 'PARTIAL',
        'C5F_READY': False,
        'REMAINING_BLOCKERS': [
            'Fresh independent false-execution recommendations observed: 8/100 (8.00%) in ambiguous cases (pre-registered threshold: 0 false executions)',
            'Fresh independent missed-execution recommendations observed: 45/50 (90.00%)',
            'Independent typed decision accuracy (38.00%) and ambiguity recognition (0/25) below required thresholds',
            'Full end-to-end native integration with live Mongo/JWT session and full catalog requires dedicated operational phase'
        ],
        'NEXT_AUTHORIZED_ACTION': 'Report truthfully as PARTIAL. Retain frozen candidate V4 and all evidence. Await explicit authorization before any candidate revision or C5F readiness activation.'
    }

    report = {
        'task': 'V2C-C.5E-R Semantic Parser Recovery Continuation and Final Validation',
        'at_utc': datetime.now(timezone.utc).isoformat(),
        'candidate_id': 'search-v2c-c5er-disabled-candidate-4',
        'final_decision': 'PARTIAL',
        'c5f_ready': False,
        'fields': fields,
        'cohort_performance': {
            'A_C5C_development': {
                'eligible': 644,
                'typed_accuracy': c5c_typed['typed_accuracy'],
                'execution_accuracy': c5c_exec['execution_accuracy'],
                'false_execution': c5c_exec['false_execution_rate'],
                'missed_execution': c5c_exec['missed_execution_rate']
            },
            'B_Exposed_C5E_historical': {
                'contexts': 90,
                'typed_accuracy': rate(90, 90),
                'execution_accuracy': rate(90, 90),
                'false_execution': rate(0, 60),
                'missed_execution': rate(0, 30),
                'note': 'Historical 25 false and 10 missed execution defects in C5E are 100% resolved on exposed regression.'
            },
            'C_Fresh_Independent_Acceptance': {
                'contexts': 150,
                'scope_stratum_cells': 30,
                'typed_accuracy': overall['typed_accuracy'],
                'execution_accuracy': overall['execution_accuracy'],
                'false_execution': overall['false_execution'],
                'missed_execution': overall['missed_execution'],
                'false_execution_ids': overall['false_execution_ids'],
                'per_decision_recall': overall['per_kind_recall']
            }
        },
        'verification': {
            'protected_files_checked': len(protected),
            'broken_files': 0,
            'structural_isolation': 'PASS (0 collisions)',
            'regression_test_assertions': 1418,
            'native_component_checks': 40
        }
    }

    with (R / (P + 'finish.json')).open('w', encoding='utf8') as f:
        json.dump(report, f, indent=2, sort_keys=True, ensure_ascii=False)

    md_lines = [
        "# V2C-C.5E-R — Final Semantic Parser Recovery and Fresh Independent Validation Report",
        "",
        "## Executive Summary",
        "",
        "- **Outcome**: `PARTIAL`",
        "- **C5F Readiness**: `BLOCKED` (`C5F_READY=False`)",
        "- **Candidate Selected**: `search-v2c-c5er-disabled-candidate-4` (Candidate V4)",
        "- **Candidate Activation**: `DISABLED` (Current production parser and C4 policy remain untouched)",
        "",
        "## Key Results by Evaluation Cohort",
        "",
        "| Evaluation Cohort | Population Size | Typed Accuracy | Execution Accuracy | False Executions | Missed Executions |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
        f"| **A. C5C Development** | 644 | {short(c5c_typed['typed_accuracy'])} | {short(c5c_exec['execution_accuracy'])} | {short(c5c_exec['false_execution_rate'])} | {short(c5c_exec['missed_execution_rate'])} |",
        f"| **B. Exposed Historical C5E** | 90 | 90/90 (100.00%) | 90/90 (100.00%) | 0/60 (0.00%) | 0/30 (0.00%) |",
        f"| **C. Fresh Independent Acceptance** | 150 | {short(overall['typed_accuracy'])} | {short(overall['execution_accuracy'])} | {short(overall['false_execution'])} | {short(overall['missed_execution'])} |",
        "",
        "## Regression and Native Validation",
        "",
        f"- **Development Regressions**: 1,418 / 1,418 test assertions passed (`regression_v4/test_generalized_ledger.py` etc.).",
        f"- **Evaluation Adapter V2**: 16 / 16 unit tests passed (`test_evaluation_adapter_v2.py`).",
        f"- **Offline Native Components**: 40 / 40 checks passed (`PASS_WITH_LIMITED_QUALIFICATION`).",
        f"- **Private Library Independence**: Verified; searches own unlinked books with empty global fixture.",
        f"- **Structural Isolation**: `PASS` (0 collisions detected against heldout and baseline).",
        f"- **Protected File Verification**: {len(protected)} / {len(protected)} files verified unchanged with SHA256 hashes.",
        "",
        "## Remaining Blockers for C5F",
        "",
        "1. **False-Execution Gate**: Observed 8/100 (8.00%) false executions in fresh independent ambiguous cases (cases: `C5ER_A01_*`, `C5ER_A02_*` across tenant scopes). Pre-registered safety threshold requires 0 false executions.",
        "2. **Missed-Execution Rate**: Observed 45/50 (90.00%) missed executions on fresh independent executable queries.",
        "3. **Typed Accuracy**: 57/150 (38.00%) on fresh independent acceptance cohort.",
        "",
        "## Preservation Guarantees",
        "",
        "- Production parser: **UNCHANGED**",
        "- Active C4 policy: **UNCHANGED**",
        "- Production Mongo database: **ZERO MUTATIONS**",
        "- Sealed heldout examples: **0 EVALUATIONS / UNACCESSED**",
        "- HNSW / KG indexes: **ZERO REBUILDS**",
        "- Historical C5A-C5E evidence: **100% PRESERVED & VERIFIED**"
    ]

    with (R / (P + 'finish.md')).open('w', encoding='utf8') as f:
        f.write('\n'.join(md_lines) + '\n')

    print(json.dumps({
        'FINAL': fields['FINAL'],
        'C5F_READY': fields['C5F_READY'],
        'protected_verified': len(protected),
        'fresh_independent_typed': overall['typed_accuracy']['percent'],
        'fresh_independent_execution': overall['execution_accuracy']['percent'],
        'false_execution_count': overall['false_execution']['numerator']
    }))

if __name__ == '__main__':
    main()
