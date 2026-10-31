"""Finalize V6 from immutable observations; never import or execute the candidate."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reports'


def read(name):
    return json.loads((R / f'search_proof6_{name}.json').read_text(encoding='utf-8'))


def rows(name):
    return [json.loads(s) for s in (R / f'search_proof6_{name}.jsonl').read_text(encoding='utf-8').splitlines() if s]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(name, data):
    path = R / f'search_proof6_{name}.json'
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def verify(files):
    failures = []
    for name, expected in files.items():
        path = ROOT / name
        if not path.is_file() or sha(path) != expected:
            failures.append(name)
    return {'verified': not failures, 'entries': len(files), 'failures': failures}


def main():
    preflight = read('preflight')
    source = read('source_freeze')
    acceptance = read('acceptance_freeze')
    metrics = read('independent_metrics')
    dev = read('development_summary')
    diag = read('exposed_namespace_diagnostic')
    perf = read('recorded_performance')['results']['after']
    edits = read('recompilation_timing')
    gold = {x['case_id']: x for x in rows('reviewed_population')}
    predictions = {x['case_id']: x for x in rows('independent_predictions')}
    observations = rows('independent_scored_observations')
    source_map = read('source_map')['files']
    maps = {Path(x['path']).name: x for x in source_map}
    assert len(gold) == len(predictions) == len(observations) == 150
    assert metrics['primary_attempts'] == 1

    # These are post-primary explanations of recorded transformations, not new predictions.
    causes = {
        'e04': ('Literal domain ownership', 'The explicit quoted search literal becomes semantic retrieval text rather than an enforceable exact_text predicate. Source validity and semantic rendering checks do not prove mandatory literal enforcement.', ['ownership.py', 'parser.py', 'proof.py']),
        'n02': ('Metalinguistic correction ownership', 'The instruction to repair a quoted field label is treated as residue; the correctly spelled later titled operand is recognized without the requested correction notice. Colon-delimited Sort: title is also left in semantic residue.', ['source_roles.py', 'ownership.py', 'parser.py']),
        'n03': ('Cross-clause label/domain binding', 'The quoted correction and later minimum operand are not composed into one rating requirement. The requested rating floor is absent while the query executes; correction notice and title sort are also lost.', ['source_roles.py', 'ownership.py', 'numeric_proposals.py', 'parser.py']),
        'n04': ('Metalinguistic correction ownership', 'The author operand is recognized, but the explicit instruction repairing the quoted field label does not create a source-backed notice.', ['source_roles.py', 'ownership.py', 'parser.py']),
        'n05': ('Operation/reference versus missing operand', 'A reference to sort and alphabetic ordering is not bound into the supplied operation; slot and legacy relationship evidence produce INCOMPLETE for a valid repair request. The nonempty quoted ellipsis is a literal, not a missing title operand.', ['ownership.py', 'operands.py', 'parser.py']),
        'a02': ('Required alternative relationship ownership', 'An either/or minimum and the following still-need-to-choose clause are not bound into an unresolved rating relationship. Required residual text becomes UNSUPPORTED instead of AMBIGUOUS.', ['source_roles.py', 'ownership.py', 'parser.py']),
        'a04': ('Unresolved modality ownership', 'Cannot yet say whether mandatory or preference does not match the bounded unresolved-association contract. Descriptor preference recognition and required residue processing do not preserve the unresolved modality relationship.', ['source_roles.py', 'ownership.py', 'surface.py', 'parser.py']),
        'u02': ('Unsafe grammar repair before negative-domain ownership', 'The ordinary metadata domain publisher is proposed as published by distance-one grammar repair. The negative parser bounds its operand before published, projects every edition whose as a text exclusion, and leaves the publisher value as semantic text. The unsupported publisher relation disappears and execution is allowed. Proof checks reproduce the same mistaken source interpretation.', ['source_repair.py', 'ownership.py', 'parser.py', 'proof.py']),
        'u04': ('Cross-book relationship versus ordinary field ownership', 'The year comparison to a different book is decomposed into a missing publication operand and ordinary title/category proposals. The referenced title is invented as an independent target filter and Books is invented as an excluded category; decision safely blocks but with the wrong type.', ['ownership.py', 'numeric_proposals.py', 'parser.py']),
        'u05': ('Ordered-proximity relationship ownership', 'The ordering relation is mistaken for a missing sort operation, while negative syntax produces the spurious text exclusion reversing that. The requested ordered proximity remains unrepresented; decision blocks with INCOMPLETE rather than UNSUPPORTED.', ['ownership.py', 'operands.py', 'parser.py']),
        'c02': ('Canonical exclusion operand boundary', 'The positive category resolves, but the exclusion operand includes simultaneously and fails canonical resolution. The identical positive/negative category conflict is never represented; proof returns UNSUPPORTED.', ['ownership.py', 'parser.py', 'proof.py']),
        'c05': ('Numeric negative comparator relationship', 'The negated rating boundary is handled as text/required residue rather than a strict numeric lower bound. This loses the exclusive bound and prevents the singleton contradiction from being represented.', ['ownership.py', 'numeric_proposals.py', 'parser.py', 'proof.py']),
    }
    grouped = defaultdict(list)
    for obs in observations:
        if not obs['typed_correct'] or obs['critical_executed_operand_mismatches']:
            grouped[gold[obs['case_id']]['family_id']].append(obs)
    families = []
    for family, members in sorted(grouped.items()):
        example = next(x for x in members if x['scope'] == 'GLOBAL')
        record = gold[example['case_id']]
        code = family.split('-')[1]
        stage, explanation, modules = causes[code]
        plan = predictions[example['case_id']]['actual_plan']
        families.append({
            'family_id': family, 'affected_contexts': len(members),
            'contexts': [x['case_id'] for x in members],
            'query': record['query_text'], 'scope_replication': 'One linguistic family repeated in five scope/role contexts.',
            'first_incorrect_transformation': stage, 'source_grounded_analysis': explanation,
            'analysis_status': 'POST_PRIMARY_STATIC_EXPLANATION; no candidate change or fresh replay',
            'expected_decision': example['expected_decision'], 'actual_decision': example['decision'],
            'expected_execution': example['expected_execution'], 'actual_execution': example['execution'],
            'critical_executed_fields': example['critical_executed_operand_mismatches'],
            'scored_mismatches_and_frozen_masks': example['mismatches'],
            'expected_source_roles': record['expected_source_roles'],
            'captured_source_IR': plan['decision'].get('query_ir_contract'),
            'captured_repair_notices': plan['decision'].get('repair_notices'),
            'captured_source_roles': plan['decision'].get('source_roles'),
            'captured_native_fields': {k: plan[k] for k in plan if k not in ['decision', 'constraint_candidates', 'source_spans']},
            'source_citations': [maps[m] for m in modules],
        })
    assert len(families) == 12
    assert sum(not x['typed_correct'] for x in observations) == 55
    assert sum(bool(x['critical_executed_operand_mismatches']) for x in observations) == 15

    hard_fields = set(next(iter(gold.values()))['expected_hard_constraints'])
    inventable = hard_fields - {k for k in hard_fields if k.endswith('_exclusive')}
    invented = []
    negative = []
    for obs in observations:
        for a in obs['assertions']:
            if a['field'] in inventable and a['mask']['status'] == 'APPLICABLE_ABSENCE' and not a['correct']:
                invented.append({'case_id': obs['case_id'], 'executed': obs['execution'], **a})
            if a['field'] in {'exclude_terms', 'exclude_subjects', 'excluded_formats'} and a['mask']['status'] == 'APPLICABLE' and a['expected'] not in [None, [], 'UNRESOLVED']:
                negative.append({'case_id': obs['case_id'], 'executed': obs['execution'], **a})
    invention_denominator = sum(a['field'] in inventable and a['mask']['status'] == 'APPLICABLE_ABSENCE' for x in observations for a in x['assertions'])
    supplemental = {
        'status': 'POST_PRIMARY_DESCRIPTIVE_COUNTS_FROM_FROZEN_ASSERTIONS; not new acceptance thresholds',
        'invented_absent_hard_field_assertions': len(invented),
        'applicable_absent_hard_field_assertions': invention_denominator,
        'contexts_with_invented_absent_hard_fields': len({x['case_id'] for x in invented}),
        'executed_contexts_with_invented_absent_hard_fields': len({x['case_id'] for x in invented if x['executed']}),
        'negative_supplied_field_assertions_correct': sum(x['correct'] for x in negative),
        'negative_supplied_field_assertions': len(negative),
        'limits': 'Unknown/unresolved negative domains are excluded from scalar field comparison. Correct scalar predicates do not prove preservation of all unsupported relations; u02 violates that semantic contract.',
        'invention_records': invented, 'negative_records': negative,
    }
    error = {
        'candidate_id': acceptance['candidate_id'], 'population': metrics['population'],
        'typed_failure_contexts': 55, 'typed_failure_linguistic_families': 11,
        'critical_executed_contexts': 15, 'executed_context_denominator': 50,
        'critical_executed_linguistic_families': 3, 'family_analyses': families,
        'supplemental_field_counts': supplemental,
        'cross_family_issue': 'Explicit Sort: title is not recognized by the sort operation grammar: 100/150 scored sort assertions disagree. Its colon syntax is not licensed by whitespace-only ownership.sort; leftover text can enter semantic retrieval. This is a source interpretation limitation, not an authorization or tenant escalation.',
        'proof_boundary': 'Valid spans, reproducible recognizers and consistent projections prove internal correspondence only. They do not prove extraction completeness or linguistic entailment. An omitted or wrongly interpreted requirement can still receive an internally valid proof.',
        'measurement_limits': {
            'independent_role_modality': 'N/A as semantic agreement rates: native field names were compared directly with IR domains. Raw primary output retained (role0/665, modality5/665). See independently reviewed measurement_audit.',
            'independent_completion': 'Qualification incomplete: all20 native-named completion inputs fail before issuance because the adapter expects IR domains. Raw0/20 is an end-to-end protocol failure, not an estimate of compiler completion capability.',
            'post_exposure_diagnostic': {k: diag[k] for k in ['population', 'role_correct', 'modality_correct', 'role_denominator', 'role_excluded', 'completion_contexts', 'completion_typed_correct', 'completion_strict_correct']},
            'diagnostic_remaining_completion_failures': 'Mapped rating floor rejects No unique source-owned operand in5contexts; mapped negative-word completion rejects Previously mandatory condition lost or changed in5contexts. These are safe component rejections, not actual stateful native qualification.',
        },
        'candidate_changed_after_primary': False, 'gold_changed_after_freeze': False,
        'primary_attempts': 1, 'now_exposed': True,
    }
    write('error_analysis', error)

    # Stream even large index assets; never load them into memory or import DB modules.
    protection = {
        'candidate_id': acceptance['candidate_id'], 'at_utc': datetime.now(timezone.utc).isoformat(),
        'previous_evidence': verify(preflight['protected_files']),
        'candidate_source': verify(source['files']),
        'acceptance_freeze': verify(acceptance['files']),
        'preflight_sha256': sha(R / 'search_proof6_preflight.json'),
        'source_freeze_sha256': sha(R / 'search_proof6_source_freeze.json'),
        'acceptance_freeze_sha256': sha(R / 'search_proof6_acceptance_freeze.json'),
        'tracked_worktree_diff': subprocess.check_output(['git', 'diff', '--name-only'], cwd=ROOT, text=True).splitlines(),
        'tracked_staged_diff': subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=ROOT, text=True).splitlines(),
        'production_activation': False, 'Mongo_mutations': 0, 'HNSW_rebuilds': 0, 'KG_rebuilds': 0,
        'sealed_heldout_parser_evaluations': 0,
        'sealed_metadata_audit': 'Established pure structural auditor only; no heldout content emitted or scored.',
    }
    assert all(protection[k]['verified'] for k in ['previous_evidence', 'candidate_source', 'acceptance_freeze'])
    assert not protection['tracked_worktree_diff'] and not protection['tracked_staged_diff']
    write('preservation', protection)

    parent = json.loads((R / 'search_proof5_source_freeze.json').read_text(encoding='utf-8'))
    parent_by_name = {Path(k).name: v for k, v in parent['files'].items() if 'search_proof_recovery_v5' in k}
    changes = [{'path': str(ROOT / k), 'change': 'ADDED' if Path(k).name not in parent_by_name else 'MODIFIED_FROM_V5', 'sha256': v}
               for k, v in source['files'].items() if 'search_proof_recovery_v6' in k and parent_by_name.get(Path(k).name) != v]
    prereqs = [
        'Obtain a new candidate that passes reviewed semantic/execution/critical-constraint gates on a genuinely new structurally isolated population; this150 is now development-only. Do not reuse protected heldout.',
        'Freeze and independently audit a single native-field-to-IR-domain ontology for roles, modality, completion operands and all scoring masks before future prediction capture.',
        'Integrate accepted full source separately from submitted edit command; bind source and IR digest, parser and accepted-plan versions, backend-issued operation/domain/value, owner/login/library/workspace/mode, expiry and one-use status. Reparse complete accepted source and preserve untouched mandatory requirements.',
        'Review the exact unapplied reports/search_proof6_transport_proposal.patch (ChoiceRequest and frontend150->500); add production callback and persistence changes in a separately authorized integration. Widening alone does not integrate accepted-source lifecycle. Keep current production correction_keep422 until reviewed integration.',
        'Obtain explicit isolated Mongo write authorization and namespace before seeding anything. Then qualify real JWT, current membership, PUBLIC/PRIVATE patron/staff/outsider concealment and cross-tenant boundaries. No such writes are currently permitted.',
        'Qualify durable CAS/one-use consumption, duplicate requests, expiry, stale sessions, crash recovery, rollback and atomic accepted-plan version changes against actual persistence.',
        'Use an authorized real semantic provider with verified paired vector/catalog generation and relevance judgments; qualify empty/unavailable-global private search and linked enrichment failure independently.',
        'Agree hardware/workload/full-search latency and concurrent-request SLOs, runtime health requirements, service-unavailable responses, observability and rollback before any staging PASS. Last recorded global health remains STALE/degraded; no new health poll was performed.',
    ]
    blockers = [
        'Fresh typed95/150 and execution140/150 fail95%/99% gates.',
        'Five false executions and five missed valid searches; critical executed hard mismatch15/50 contexts in three linguistic families.',
        'Source-role/modality and native completion primary evaluation adapters have confirmed namespace defects; independent qualification incomplete for those dimensions.',
        'Semantic extraction loses required literal/rating/negative publisher meaning; deterministic proof does not prove linguistic completeness.',
        'Native500-character transport and accepted-source integration remain isolated; real Mongo/JWT/CAS, vector relevance and operational qualification unavailable.',
    ]
    s = metrics['summary']
    qa = {
        'FINAL': 'PARTIAL', 'STEP_1_STATUS': 'PASS_REVIEWED_CONTRACT_MIGRATION',
        'STEP_2_STATUS': 'FAILED_FRESH_INDEPENDENT_PRIMARY',
        'CANDIDATE_ID': acceptance['candidate_id'], 'CANDIDATE_DISABLED': True,
        'PRODUCTION_READINESS': 'BLOCKED', 'STAGING_READINESS': 'BLOCKED', 'REMAINING_BLOCKERS': blockers,
        'PREVIOUS_FREEZE_VERIFIED': protection['previous_evidence'],
        'SOURCE_ROLE_RECOVERY': 'Partial development recovery; independent semantic rate N/A due field namespace mismatch. Exposed post-hoc mapped diagnostic325/605 annotations correct,60 excluded; not fresh acceptance.',
        'MODALITY_RECOVERY': 'Partial; independent semantic rate N/A due same protocol mismatch. Exposed mapped diagnostic435/605 correct,60 excluded; unresolved-modality language still fails.',
        'ACCEPTED_SOURCE_REFINEMENT': 'Implemented isolated full-source reparsing and preservation checks;60/60 pure edit drafts pass, no persistent commits.',
        'SEMANTIC_PROJECTION_CORRECTNESS': {'independent_strict_scored_contexts': s['strict_scored_fields'], 'limits': 'Frozen scalar masks only; structured preference equivalence N/A. Critical executed mismatches15/50; not semantically qualified.'},
        'DETERMINISTIC_PROOF_STATUS': 'Source span, modality, projection and mutation checks implemented. Linguistic completeness/entailment not established; fresh unsafe negative-domain repair passes internal proof.',
        'MANDATORY_OPERAND_PRESERVATION': 'Exposed frozen0/430 executed contexts with critical hard mismatch; independent15/50 executed contexts with critical hard mismatch. Universal mandatory semantic preservation NOT established.',
        'HARD_FILTER_INVENTION': {k:v for k,v in supplemental.items() if k not in ['invention_records', 'negative_records']},
        'NEGATIVE_CONSTRAINT_PRESERVATION': {'correct_supplied_scalar_assertions': supplemental['negative_supplied_field_assertions_correct'], 'applicable_supplied_scalar_assertions': supplemental['negative_supplied_field_assertions'], 'status': 'FAILED semantic contract: unsupported publisher exclusion lost in5contexts; scalar counts exclude unresolved domains.'},
        'NATIVE_EDIT_COMPATIBILITY': '26/26 isolated adapter tests and60/60 pure timing drafts pass; fresh completion qualification incomplete (native/IR namespace defect). Exposed mapped diagnostic10/20 completions correct,10 safe rejections.',
        'RAW_QUERY_500_150_CONTRACT': 'ActiveChoiceRequest/frontend150 unchanged; parser/session500. Test-only500 schema passes8boundary checks. Exact unapplied two-file patch provided; no truncation.',
        'SOURCE_FILES_CHANGED': changes,
        'BROAD_REGRESSION_TOTAL': 1614, 'BROAD_REGRESSION_PASSED': 1614, 'BROAD_REGRESSION_FAILED': 0,
        'BROAD_REGRESSION_CONTRACT': '1564 reviewed-equivalent historical checks (1558 original retained +6 replacements), plus50 new checks. Six exact historical nodes deselected. Unchanged historical view1558/1564; six incompatibilities remain visible.',
        'PREVIOUS_45_FAILURES_RESOLVED': '45/45 dispositioned:39 implementation repairs +6 independently reviewed narrow migration replacements; original gold/assertions preserved.',
        'DEVELOPMENT_TYPED_ACCURACY': {'numerator':1184,'denominator':1184,'cohort':'All five frozen exposed development cohorts'},
        'DEVELOPMENT_EXECUTION_ACCURACY': {'numerator':1184,'denominator':1184,'false_execution':'0/754 blocked','missed_execution':'0/430 valid','cohort':'All five frozen exposed development cohorts'},
        'DEVELOPMENT_STRICT_FIELD_MATCHES': {'C5C':'235/644','C5E':'45/90','C5ER':'135/150','SmartEng':'135/150','Comp3':'130/150','limits':'Original applicability masks; not universal semantic equivalence'},
        'NEW_SAFETY_REGRESSIONS': 'Final frozen exposed:0/754 false execution,0/430 critical executed hard mismatch. Developmentdev1 had10 false executions; preserved and repaired before freeze. Fresh primary has5/100 false execution and15/50 critical executed hard mismatch; readiness blocked.',
        'INDEPENDENT_EVALUATION_ELIGIBLE': True, 'FRESH_INDEPENDENT_TEST_PERFORMED': True,
        'INDEPENDENT_POPULATION_SIZE': {'contexts':150,'linguistic_families':30,'topologies':30,'scopes':5,'strata':6,'contexts_per_cell':5,'long_151_to_500_contexts':65,'completion_actions':20,'primary_attempts':1},
        'INDEPENDENT_TYPED_ACCURACY': s['typed_accuracy'], 'INDEPENDENT_EXECUTION_ACCURACY': s['execution_accuracy'],
        'INDEPENDENT_FALSE_EXECUTION': s['false_execution'], 'INDEPENDENT_MISSED_EXECUTION': s['missed_execution'],
        'AMBIGUITY_RECOGNITION': s['per_kind_recall']['AMBIGUOUS'], 'INCOMPLETE_RECOGNITION': s['per_kind_recall']['INCOMPLETE'],
        'NOTICE_RECOGNITION': s['per_kind_recall']['EXECUTABLE_WITH_NOTICE'],
        'UNSUPPORTED_RECOGNITION': s['per_kind_recall']['UNSUPPORTED'], 'CONTRADICTION_RECOGNITION': s['per_kind_recall']['CONTRADICTORY'],
        'MANDATORY_SEMANTIC_PRESERVATION': 'FAILED:15/50 executed contexts fail critical hard-field preservation,3/30 linguistic families. Mandatory omissions and invented negative predicate observed. Full structured semantic equivalence N/A.',
        'STRUCTURAL_ISOLATION': 'PASS:30topologies against exposed historical/candidate tests and established sealed metadata auditor; heldout parser/scorer calls0. Gold/predictor/scorer62-entry freeze unchanged.',
        'REVIEW_PROVENANCE': {'author':'/root/v6_fresh_author','reviewer':'/root/v6_blind_reviewer','contract_and_measurement_review':'/root/v6_contract_review','human_reviewers':0,'actual_runtime_model':'NOT_EXPOSED','blindness':'Separate contexts; candidate/predictions/author labels hidden from reviewer. Pre-prediction source/gold reconciliation retained; no post-freeze label changes.'},
        'SMART_MODE_STATUS': '30/30 pure mode checks acrossSMART/EXACT; native fixtures pass. Fresh SMART semantic generalization FAILED; activeC4 unchanged.',
        'EXACT_MODE_STATUS': 'Literal-mode compatibility passes in pure/native fixtures; actual live API latency/authorization N/A. EXACT bypasses semantic extraction.',
        'PUBLIC_LIBRARY_STATUS': 'Offline actual native-function fixtures pass within40local checks; real JWT/membership/Mongo N/A.',
        'PRIVATE_LIBRARY_STATUS': 'Offline actual native-function fixtures pass within40local checks, including outsiders404 and own rows. Real authenticated staging N/A.',
        'PRIVATE_GLOBAL_INDEPENDENCE': 'Own unlinked institutional rows discoverable with global EMPTY/INACCESSIBLE in40local fixtures; no global reads on those paths. Linked metadata enrichment, recommendations and generation/relevance remain global-dependent and unqualified.',
        'NATIVE_CHOICE_STATUS': 'Isolated Apply/Keep/source-ownedComplete callback implemented;26tests and4native projections pass. Fresh completion protocol fails20/20 before issuance; underlying semantic rate N/A. Production correction_keep remains422; real one-use durability N/A.',
        'LEARNED_EXTRACTOR_RECOMMENDED': 'Separately scoped bounded extraction comparison recommended; retain deterministic proof and backend authorization.',
        'LEARNED_EXTRACTOR_IMPLEMENTED': False, 'LEARNED_EXTRACTOR_ENABLED': False,
        'PARSER_P50': {'ms':perf['serial']['p50_ms'],'cohort':'150 exposedC5ER serial parses; warm process'},
        'PARSER_P95': {'ms':perf['serial']['p95_ms'],'max_ms':perf['serial']['max_ms'],'cohort':'150 exposedC5ER serial parses; warm process'},
        'FOUR_WORKER_P95': {'ms':perf['four_workers']['p95_ms'],'max_ms':perf['four_workers']['max_ms'],'cohort':'150 exposedC5ER parses,4workers'},
        'REAL_SEMANTIC_RETRIEVAL_VERIFIED': False, 'ACTUAL_MONGO_JWT_STAGING_VERIFIED': False,
        'PRODUCTION_PARSER_CHANGED': False, 'ACTIVE_C4_POLICY_CHANGED': False, 'FRONTEND_CHANGED': False,
        'MONGO_MUTATIONS':0, 'HNSW_REBUILDS':0, 'KG_REBUILDS':0, 'HELDOUT_EVALUATIONS':0,
        'PREVIOUS_EVIDENCE_PRESERVED': protection['previous_evidence'],
        'DETERMINISTIC_GENERALIZATION_DECISION': 'FAILED for unrestricted supported-language front end. Retain proof compiler as validator; do not activate this candidate or add endless phrase exceptions.',
        'NEXT_AUTHORIZED_ACTION': 'ThisV6 execution is complete. Preserve failed primary and stop before staging. A learned-extractor experiment or production integration requires a separately scoped authorization; no model selected/downloaded/trained/activated.',
        'EXACT_STAGING_PREREQUISITES': prereqs,
        'FINAL_RECOMMENDATION': 'KeepV6 disabled; repair the ontology/evaluation boundary in a new experiment, compare a bounded extractor with a deterministic restricted-language baseline, and require genuinely new independent semantic acceptance before staged integration.',
        'evidence': {'report':'reports/search_proof6_final_report.md','error_analysis':'reports/search_proof6_error_analysis.json','preservation':'reports/search_proof6_preservation.json','measurement_audit':'reports/search_proof6_measurement_audit.json','source_map':'reports/search_proof6_source_map.json'},
    }
    write('final_qa', qa)

    table = '\n'.join(f"| {n} | {d['typed_accuracy']['numerator']}/{d['typed_accuracy']['denominator']} | {d['execution_accuracy']['numerator']}/{d['execution_accuracy']['denominator']} | {qa['DEVELOPMENT_STRICT_FIELD_MATCHES'][{'C5C':'C5C','c5e90':'C5E','c5er150':'C5ER','smarteng150':'SmartEng','comp3_150':'Comp3'}[n]]} |" for n,d in dev['cohorts'].items())
    family_table = '\n'.join(f"| {x['family_id']} | {x['expected_decision']} → {x['actual_decision']} | {x['first_incorrect_transformation']} |" for x in families)
    report = f'''# LuminaR Smart Search — Combined Phase V6

Date: 28 October 2026 (Asia/Calcutta). Candidate `{acceptance['candidate_id']}` remains disabled.

**FINAL=PARTIAL. STEP_1_STATUS=PASS_REVIEWED_CONTRACT_MIGRATION. STEP_2_STATUS=FAILED_FRESH_INDEPENDENT_PRIMARY. STAGING_READINESS=BLOCKED. PRODUCTION_READINESS=BLOCKED.**

V6 repairs the exposed regression and isolated edit contracts, but fails unfamiliar semantic language. Its one independent primary capture yields **95/150 typed decisions, 140/150 execution decisions, 5/100 false executions and 5/50 missed valid executions**. Fifteen of50 executable outputs have critical hard-field mismatches in three linguistic families. No production routing, policy, frontend, database or index changes were made.

## Step1 — recovered contracts and disabled implementation

The authoritative V5 manifests and sources were recovered before implementation. The final preservation audit verifies all{protection['previous_evidence']['entries']} protected entries, all{protection['candidate_source']['entries']} V6 source/dependency files and all{protection['acceptance_freeze']['entries']} acceptance inputs unchanged. Tracked worktree and staged diffs are empty. Exact source functions and line numbers are in [source_map](search_proof6_source_map.json); all changes are versioned scratch/scripts/reports, with candidate changes enumerated in [final_QA](search_proof6_final_qa.json).

The [45-failure matrix](search_proof6_recovery_matrix.json) preserves every old failure. Nine cause groups cover literal/notice migration, preferences, canonical ownership, surface rendering, domains, refinement, availability and whitespace. Thirty-nine failures were repaired in implementation. Six historical assertions received narrow independently reviewed replacements: a nonempty quoted ellipsis remains a literal, and five canonical repairs retain the same hard fields but explicitly require notices. Active C4 execution policy supports notice semantics; its typed layer historically resets to plain executable. We do not claim that C4 typed output mandated the migration. [Independent contract review](search_proof6_independent_contract_review.json), exact deselections and equivalent replacement assertions are preserved; original normative gold and tests are unchanged.

The unchanged broad view is1558/1564, with those six incompatibilities visible. The reviewed suite has **1614/1614 pass**, zero unexplained failures:1558 retained old checks +6 replacement checks +50 new native/property checks. Focused coverage totals187 tests (131 inherited +26 adapter +24 compositional +6 migration). [Readiness JUnit](search_proof6_readiness_tests.xml) and [migration ledger](search_proof6_readiness_migration.json) make that accounting reviewable.

`surface.py` now owns preference/grammatical frames and one shared semantic projection while preserving technical and quoted punctuation. `ownership.py` bounds canonical fields and exclusions by independent role units. Numeric quantity units are bound before fieldless ambiguity; this repairs the five C5ERU03 scope replicas. `parser.py` preserves mandatory governing-unit status after splitting residual source, so consuming a known format prefix does not erase an unknown required tail. `proof.py` checks spans, source/IR digests, modality, bounded operand evidence and rebuilt hard/semantic projection.

`refinement.py` subtracts only legitimately edited source-owned spans, constructs the complete accepted source, reparses it, and checks untouched mandatory requirement signatures. The short edit command is recorded separately from accepted source. `native_adapter.py` implements isolated backend-issued Apply, Keep and source-owned completion with strict DTOs, source substring/digest validation, owner/login/library/workspace/mode/parser/accepted-version/expiry/used bindings, safe failure statuses and native callback shape. No client plan or offsets are trusted. Preview does not commit or consume persistent state. This is pure offline compatibility, not actual JWT, persistence, durable one-use or CAS qualification.

The active ChoiceRequest/frontend query bound remains150; parser/session supports500. Eight boundary checks verify active versus isolated500 schemas without truncation. [Exact transport patch](search_proof6_transport_proposal.patch) is unapplied. Widening two input bounds alone does not integrate accepted-source/version lifecycle. Production correction_keep still safely returns422; isolated V6 Keep works in its component tests.

Frozen exposed development results:

| Population | Typed | Execution | Strict scored context match |
|---|---:|---:|---:|
{table}

Aggregate typed/execution1184/1184, false execution0/754 blocked contexts, missed execution0/430 valid contexts, critical executed hard mismatch0/430 under the frozen applicability masks. Strict scalar matches are not a universal semantic equivalence metric; structured preference equivalence is unavailable. Changed V5 predictions are retained in [comparison](search_proof6_changed_predictions_vs_V5.json). An intermediate development attempt had10 false executions in two mandatory format-tail families; its failing evidence remains preserved. Those were repaired before the source freeze, rather than omitted from the development history.

## Step2 — independent protocol and failed acceptance

The [Step1 exit gate](search_proof6_step1_exit_gate.json) passed before independent authoring. The33-file source freeze SHA256 is `{protection['source_freeze_sha256']}`. A separate AI author produced150 contexts,30 linguistic families and30 structural topologies, balanced across5scopes ×6decision strata ×5contexts/cell. These are30 independent language families replicated in five scope/role contexts, not150 independent phrases. Sixty-five inputs are151–500characters;20 have completion actions.

Separate blind AI review covered all150 examples,665 role/modality annotations and20 completion oracles. The reviewer packet omitted candidate code, predictions, author labels and desired scores. Human reviewers=0; actual runtime model identity was not exposed. Prior author topology drafts, structural failures, review differences and pre-prediction reconciliation remain preserved. The author corrected an exclusive_formats schema defect and accepted one source-backed mandatory year floor before prediction. A preflight helper was narrowed to admit explicitly unresolved masked domains; no candidate predictions had yet been made. Final gold was frozen before capture. An earlier contract reviewer incidentally saw copied historical regression lines, disclosed in its report; it did not see V6 implementation or the new population.

Structural isolation passed against exposed historical/candidate tests and the established sealed metadata auditor. No sealed query content was emitted, parsed or scored. The62-entry [acceptance freeze](search_proof6_acceptance_freeze.json) includes source/dependencies, population, gold, masks, predictor, scorer, audit helpers and pre-registered gates; SHA256 `{protection['acceptance_freeze_sha256']}`. The sole gold-blind primary captured150/150 outputs, parser errors0, retries0, gold reads0, isolation denials0, network/model calls0. No failed-primary tuning, gold changes or fresh recapture occurred.

| Primary metric | Result | Frozen requirement |
|---|---:|---|
| Typed decision |95/150 (63.33%)|≥95% — FAIL|
| Execution decision |140/150 (93.33%)|≥99% — FAIL|
| False execution |5/100 blocked contexts (5%)|0 critical — FAIL|
| Missed valid execution |5/50 valid contexts (10%)|≤5% — FAIL|
| Critical executed hard mismatch |15/50 executed contexts;3families|0 — FAIL|
| Strict scored context match |20/150 (13.33%)|Descriptive scalar metric; semantic equivalence not established|

Stratum recall: executable25/25, notice5/25, ambiguous15/25, incomplete25/25, unsupported10/25, contradictory15/25. All finite population denominators are contextual; no zero real-world error claim is supported. [Primary metrics](search_proof6_independent_metrics.json), captured predictions, scored observations and failures remain byte-identical.

The typed errors span11 linguistic families (55contexts); the exact-literal failure adds a twelfth analysis family despite a correct typed decision:

| Family | Expected → actual | First wrong transformation |
|---|---|---|
{family_table}

The most serious failure is `publisher`→`published` grammar repair before exclusion-domain ownership. An unsupported publisher exclusion becomes the invented text exclusion `every edition whose` and executes in allfive scopes. The other critical families lose the mandatory exact literal `brass sundial` and the minimum rating3.3. The [error analysis](search_proof6_error_analysis.json) contains representative full queries, expected/actual projections, frozen masks, captured source IR/provenance and source function citations. Explicit `Sort: title` also fails100/150 scored sort assertions. Post-primary descriptive hard-field/negative assertion counts and their limits are recorded there and in finalQA.

**Measurement limitation:** the primary role scorer compares native names such as author_text/rating_min/formats directly with IR domains author/rating/format; raw role0/665 and modality5/665 therefore cannot be interpreted as semantic accuracy. Completion inputs also use native field names where `issue_choice` expects an IR domain, so all20 reject before issuance. That is a real workflow qualification failure, not proof the underlying compiler completes0/20. An independent static [measurement audit](search_proof6_measurement_audit.json) confirmed both defects without reading metric outcomes. Main150 typed/execution and hard-field safety findings are unaffected.

A separate **now-exposed, post-hoc diagnostic**, never a replacement independent score, maps unambiguous field namespaces: role325/605 and modality435/605, with60 excluded annotations; mapped completion10/20 correct,10 safe rejections (five ambiguous source-owned rating operands and five preservation-check rejections for negative-word completion). Candidate, gold and primary artifacts were unchanged. This diagnostic shows additional component work remains; it does not restore fresh qualification. The150population is now development-only.

## Native scopes, performance and preservation boundaries

Exact hash-verified production functions were AST-loaded with collection/authority/provider doubles, avoiding database initialization or index creation. Forty local native-function fixtures coverPUBLIC/PRIVATE ×PATRON/STAFF ×globalEMPTY/INACCESSIBLE, institution-owned unlinked rows, foreign-row filtering and outsider404. Eight global fixtures verify hard predicates, negative filtering, topic transport, hydration, pagination and serialization. Four native choice projections and30pure SMART/EXACT checks pass. This establishes component transport and filtering behavior, not actual live authentication, Mongo atomicity or vector relevance.

Private institution-owned unlinked search is independent of global catalog size in those fixtures. Linked global enrichment, recommendations and index-generation/relevance still have global dependencies; global5Mcount is historical. No catalog reduction or rebuild occurred. The last recorded global runtime wasSTALE/degraded and baseline_verified=False; no status poll with side effects was run. Actual JWT/current membership, durableCAS/expiry/replay, real semantic-provider relevance and full API load remain unverified.

On the recorded Ryzen7 260 (8cores/16logical),16,438,054,912bytesRAM, RTX5060LaptopGPU8,151MiB, Python3.11.9 Windows host, one warm serial150 plus four-worker150 exposedC5ER workload gives V6p50={perf['serial']['p50_ms']:.3f}ms, p95={perf['serial']['p95_ms']:.3f}ms, max={perf['serial']['max_ms']:.3f}ms; four-workerp95={perf['four_workers']['p95_ms']:.3f}ms, max={perf['four_workers']['max_ms']:.3f}ms. CPU10,468.75ms, wall10,794.52ms;RSS37,359,616→38,846,464bytes, errors0/300 and serial/concurrent complete-plan equality150/150. The actual matched V5 comparison is serialp5025.539ms/p9560.492ms and four-workerp95251.691ms. The measured artifact contains a stale V3 description; its imports and before_sources prove V5 was measured. No cross-architecture plan equivalence is claimed.

Pure edit recompilation60/60 drafts: p50={edits['timing']['p50_ms']:.3f}ms, p95={edits['timing']['p95_ms']:.3f}ms, max={edits['timing']['max_ms']:.3f}ms. Shared-host sequential warm measurements have no statisticalCI, cold-start qualification or agreed operationalSLO. Real vector/full-search latency isN/A. Hardware totals are not reserved free capacity.

Production parser/C4/frontend/authentication remain unchanged; Mongo mutations0, HNSW/KGbuilds0, heldout evaluations0. RAG/Qwen/uploads/recommendations/MoreLikeThis/library transactions and other platform files remain protected. [Preservation audit](search_proof6_preservation.json) records exact hashes/counts; the final evidence manifest covers all V6 attempts, source snapshots, reviews, captures, diagnostics and reports.

## Architecture decision and separately scoped next experiment

The deterministic source-role front end has **failed generalization qualification**. Keep the proof compiler, but recognize that it validates represented requirements against its own recognizers: correct source spans and internally consistent JSON do not prove extraction completeness, domain entailment, or preservation of every mandatory clause. The publisher failure demonstrates this boundary directly. Do not activate V6 or continue accumulating unrelated phrase exceptions.

A separately authorized bounded extraction comparison is justified. No model, runtime or weights are selected; no download, training, remote API, model inference, newQwen use or activation has occurred. The following is an engineering feasibility assessment, not an accuracy or capacity claim:

| Approach | Work/data needs | Reliability and operational tradeoff |
|---|---|---|
| Deterministic restricted language |Explicit supported syntax, reviewed ontology and clarification UI; smallest runtime/data burden|Auditable, predictable latency; unfamiliar relations remain coverage-limited. Must safely reject unsupported mandatory language.|
| Specialized intent model |Intent/domain labels plus rejection calibration|Could route requests; cannot alone recover operands, scoped modality and relations. Insufficient as the complete extractor.|
| Encoder with span/relation heads |Token/character alignment, spans, domains, modality/polarity and relation labels; explicitunknown states|Direct source alignment; significant annotation/ontology and overlapping-relation engineering. Actual memory/latencyN/A pending a chosen candidate.|
| Bounded generative schema extractor |Schema/constraint training examples, omission/error labels, deterministic source-span verification and timeout/failure handling|Flexible relation representation; omissions, hallucinated domains, queueing and generation cost need measurement. ValidJSON alone never authorizes execution.|

Start with a small independently reviewed ontology pilot to validate native-field/IR mappings, span ownership, quoted references, unresolved modalities and completion contracts before deciding dataset size or model family. Avoid generating thousands of self-labeled examples against a defective schema. Use the now-exposed150 only for development/error analysis. Freeze a future experiment and obtain genuinely new structurally independent author/reviewer acceptance examples; keep old sealed content untouched. Compare deterministic restricted-language, encoder and bounded generative alternatives only within the newly authorized scope. Actual extractor memory, licensing/runtime suitability, latency, quality and operating cost areN/A until candidates are separately selected and measured on this host under concurrent platform load. No improvement is claimed.

Any extractor may only propose source spans, operands/operators, domains, intent, modality, polarity, relationships and explicit unknowns. Backend authority supplies scope/current membership; the extractor receives no database handles, tool privileges or scope-selection power. Deterministic enforcement must reject unsupported mandatory residue, ambiguous/incomplete operands, unverifiable spans, changed source and stale accepted state. EXACT bypasses extraction. A future design must bound input500characters, requirement/output counts, timeouts/queue length, failure responses, local privacy, model/runtime/license pinning and rollback; choose exact generation/token budgets only after measured design review. A proposal is never an execution proof.

## Exact gates before staging

{chr(10).join(str(i+1)+'. '+text for i,text in enumerate(prereqs))}

No Mongo writes, staged integration or deployment are authorized now. This execution ends with the disabled failed candidate and complete evidence. All requested final QA fields, including unavailable measurements and exact cohorts, are in [final_QA](search_proof6_final_qa.json).
'''
    with (R / 'search_proof6_final_report.md').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(report)

    # Freeze only versioned V6 evidence, retaining every earlier attempt.
    paths = set()
    for directory, pattern in [('reports', 'search_proof6_*'), ('scripts', 'search_proof6_*')]:
        paths.update(p for p in (ROOT / directory).glob(pattern) if p.is_file())
    for dirname in ['search_proof_recovery_v6', 'search_proof6_regression', 'search_proof6_history']:
        paths.update(p for p in (ROOT / 'scratch' / dirname).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    manifest = {'candidate_id': acceptance['candidate_id'], 'at_utc': datetime.now(timezone.utc).isoformat(),
                'previous_manifest': 'reports/search_proof5_freeze_manifest.json',
                'previous_protected_entries': protection['previous_evidence']['entries'],
                'files': {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)},
                'self_hash_policy': 'Manifest excludes itself and subsequent verification to avoid a hash cycle.',
                'production_activation': False, 'primary_acceptance_attempts': 1}
    write('freeze_manifest', manifest)
    result = verify(manifest['files'])
    assert result['verified']
    write('freeze_verification', {**result, 'manifest_sha256': sha(R / 'search_proof6_freeze_manifest.json'), 'previous_protection': protection, 'FINAL':'PARTIAL'})
    print(json.dumps({'FINAL':'PARTIAL','frozen_V6_entries':result['entries'],'previous_protected_entries':protection['previous_evidence']['entries'],'source_files':protection['candidate_source']['entries'],'acceptance_files':protection['acceptance_freeze']['entries'],'post_primary_field_counts':{k:v for k,v in supplemental.items() if not k.endswith('_records')},'candidate_changes':len(changes)}, indent=2))


if __name__ == '__main__':
    main()
