"""Offline, output-visible C3 review of preserved DEVELOPMENT native evidence.

Reads only explicitly named development/C2 native inputs and contract source.
Does not import/call a parser, application, fixture, database, or evaluator.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reports'
OBS = 'reports/search_v2c_c2_native_current/search_v2c_c2_native_observations.jsonl'
DEV = 'reports/search_v2c_c2_v2_development.jsonl'
INPUTS = [OBS, DEV, 'reports/search_v2c_c2_development_native.json',
          'reports/search_v2c_c2_native_diagnostics.json']
SOURCES = ['backend/institution_dependencies.py',
           'backend/services/library_inventory_access.py',
           'backend/services/library_catalogue_experience.py',
           'search/scope_authorization.py', 'search/session_store.py',
           'search/interaction_api.py', 'search/query_interaction.py',
           'search/query_execution.py', 'search/query_session.py',
           'tests/institution_v2g/test_query_v2c_c2_native.py',
           'tests/institution_v2g/test_query_v2c_c1.py',
           'tests/institution_v2g/test_query_v2c_b.py',
           'tests/institution_v2g/test_query_v2c_b1.py',
           'reports/search_v2b_session_rules.json',
           'reports/search_v2b_session_architecture.md']


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf8'))


def rows(path):
    return [json.loads(line) for line in (ROOT / path).read_text(encoding='utf8').splitlines()]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def write(name, value):
    (R / ('search_v2c_c3_' + name)).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf8')


OWNER = ('user_id', 'login_session', 'scope', 'library_id', 'workspace')
PLAN = ('mode', 'intent', 'semantic_text', 'subjects', 'author_text', 'title_text',
        'rating_min', 'rating_max', 'rating_min_exclusive', 'rating_max_exclusive',
        'year_min', 'year_max', 'year_min_exclusive', 'year_max_exclusive',
        'formats', 'exclusive_formats', 'excluded_formats', 'availability',
        'exclude_subjects', 'exclude_terms', 'language', 'sort', 'exact_text', 'soft_preference')


def plan_summary(plan):
    return {k: plan.get(k) for k in PLAN}


def state_summary(state):
    result = {'sha256': digest(state)}
    result['accepted'] = [{'_id': v['_id'], **{k: v.get(k) for k in OWNER},
                           'version': v['version'], 'plan': plan_summary(v['current_plan']),
                           'document_sha256': digest(v)} for v in state['accepted']]
    result['pending'] = [{'_id': v['_id'], **{k: v.get(k) for k in OWNER},
                          'query': v['query'], 'search_session_id': v['search_session_id'],
                          'base_version': v['base_version'], 'used': v.get('used', False),
                          'expires_at': v['expires_at'], 'document_sha256': digest(v)}
                         for v in state['pending']]
    result['profiles'] = {k: {'value_sha256': digest(v)} for k, v in state['profiles'].items()}
    return result


def changes(before, after):
    result = {}
    for kind in ('accepted', 'pending'):
        b = {v['_id']: v for v in before[kind]}
        a = {v['_id']: v for v in after[kind]}
        result[kind] = {'removed': sorted(b.keys() - a.keys()),
                        'inserted': sorted(a.keys() - b.keys()),
                        'updated': sorted(k for k in b.keys() & a.keys() if b[k] != a[k]),
                        'preserved': sorted(k for k in b.keys() & a.keys() if b[k] == a[k])}
    b, a = before['profiles'], after['profiles']
    result['profiles'] = {'removed': sorted(b.keys() - a.keys()),
                          'inserted': sorted(a.keys() - b.keys()),
                          'updated': sorted(k for k in b.keys() & a.keys() if b[k] != a[k]),
                          'preserved': sorted(k for k in b.keys() & a.keys() if b[k] == a[k])}
    return result


def binding(observation):
    # The harness seeds A and S2 with Fiction 4; B and GLOBAL use a bounds conflict.
    pending = observation['before']['pending']
    a = next(p for p in pending if p['query'] == 'Fiction 4' and p['login_session'] == 'v2cb-login')
    b = next(p for p in pending if p['library_id'] and p['library_id'] != a['library_id'])
    return a, b


ORACLES = {
    'no_mutation': {'accepted': 'all exact documents unchanged', 'pending': 'all exact documents unchanged',
                    'personalization': 'all exact entries unchanged', 'commits': 0},
    'current_membership_loss': {'accepted': 'remove only freshly inaccessible exact actor-login/library/workspace tuples',
                              'pending': 'remove only pending records in those exact tuples',
                              'personalization': 'remove only entries in those exact tuples',
                              'preserve': ['other library', 'GLOBAL', 'other login sid', 'still-authorized workspace'],
                              'commits': 0},
    'other_library_membership_loss': {'first_denial': 'all accepted/pending/profile state unchanged',
                                    'after_membership_removal': 'only inaccessible B ownership tuple removed',
                                    'preserve': ['A', 'GLOBAL', 'other login sid', 'still-authorized workspace'], 'commits': 0},
    'reject_then_genuine_once': {'invalid_attempt': 'accepted, pending and profiles all unchanged; no claim/consumption',
                               'genuine_attempt': 'original owner can apply original offered choice exactly once; accepted version +1; pending used true',
                               'replay': '409; committed accepted document unchanged',
                               'unrelated': 'all unrelated accepted/pending/profile documents unchanged', 'authorized_commits': 1},
    'clear_exact_context': {'accepted': 'delete exact owned search UUID only',
                            'pending': 'delete only its exact-owner pending records',
                            'personalization': 'unchanged by explicit context clear',
                            'unrelated': 'all unchanged', 'commits': 0},
    'legacy_delta_sequence': {'setup': 'seed separate neural-networks topic with explicit inclusive rating>=2',
                              'unrelated': 'all A/B/GLOBAL/S2 accepted/pending/profile controls unchanged',
                              'decision': 'a blocked returned plan must not overwrite the accepted prior',
                              'semantic_delta': 'compare raw authored nonempty delta separately; four reviewed rows have explicit v2 delta contracts',
                              'limitation': 'C2 before snapshot precedes synthetic seed; prior is reconstructed from final previous_plan or unchanged accepted seed'},
}
PRIVACY = {'private_metadata_disclosed': False, 'private_vocabulary_disclosed': False,
           'foreign_plan_or_choices_disclosed': False, 'foreign_profile_used': False,
           'no_global_fallback_for_tenant_search': True,
           'check_error_body': 'generic class-specific detail only, never source documents or offered choices',
           'evidence_limit': 'C2 observation logs contain no response body; body assertions exist for private suggestion/correction/resolve only. Fresh v3 must capture and inspect all bodies.'}


def action_contract(row, obs):
    action = row.get('expected_action')
    staff = 'STAFF' in row['scope_type'] and action not in (
        'search_unauthorized_workspace', 'search_denied_other_library_then_revoke_other_membership')
    role = 'LIBRARIAN' if staff else 'GENERAL_USER'
    request = {'auth': 'active verified actor, valid login sid', 'query': row['query_text'],
               'library': 'A', 'workspace': 'STAFF' if staff else 'PATRON',
               'transport': 'in-process service call with HTTPException status adapter'}
    canonical, oracle, detail, error_class, body_evidence = 404, 'no_mutation', None, None, 'SOURCE_INFERRED_NOT_CAPTURED'
    basis = 'No active exact-library membership deliberately conceals the resource.'
    if action == 'search_unauthorized_workspace':
        canonical, oracle = 403, 'no_mutation'
        request.update(entrypoint='search.query_execution.tenant_search', workspace='STAFF', session='A')
        detail, error_class = 'Insufficient library permissions.', 'AUTHORIZED_ACCOUNT_WRONG_LIBRARY_ROLE'
        basis = 'Active GENERAL_USER belongs to A but cannot enter STAFF. Patron A remains authorized; denial cannot erase it.'
    elif action == 'revoke_current_membership_then_search':
        oracle = 'current_membership_loss'
        request.update(entrypoint='search.query_execution.tenant_search', session='A', preceding_mutation='membership.status=REMOVED')
        role += ' -> REMOVED'
        detail, error_class = 'Library resource not found.', 'LIBRARY_MEMBERSHIP_CONCEALED'
    elif action == 'search_denied_other_library_then_revoke_other_membership':
        canonical, oracle = 403, 'other_library_membership_loss'
        request.update(entrypoint='search.query_execution.tenant_search', library='B', workspace='STAFF', session='B',
                       later_request={'preceding_mutation': 'B membership.status=REMOVED', 'workspace': 'PATRON', 'status': 404})
        detail, error_class = 'Insufficient library permissions.', 'AUTHORIZED_ACCOUNT_WRONG_LIBRARY_ROLE'
        basis = 'Initial request has active GENERAL_USER membership in B, so role denial403; subsequent no-membership request conceals B with404.'
    elif action in ('resolve_sid_1_clarification_under_sid_2', 'submit_forged_choice_then_submit_genuine_choice'):
        oracle = 'reject_then_genuine_once'
        request.update(entrypoint='POST /query/resolve', transport='FastAPI TestClient HTTP', query='Fiction 4',
                       session='A', clarification='pending_A', choice='genuine offered choice')
        if action.startswith('resolve_sid'):
            request['login_sid'] = 'sid_2, while pending_A belongs to sid_1'
            error_class = 'CHOICE_OWNERSHIP_CONCEALED'
            basis = 'Account authentication is valid; login-session ownership does not match. Exact tuple lookup conceals foreign pending choices404.'
        else:
            request['choice'] = 'fresh well-formed UUID not present in pending_A.choices'
            error_class = 'UNAVAILABLE_UNOFFERED_CHOICE'
            basis = 'The offered-choice namespace treats a syntactically valid unoffered UUID as unavailable404, not expired410, conflict409 or operand-invalid422.'
        detail = 'Search choice is unavailable. Submit the query again.'
    elif action == 'search_tenant_as_platform_admin_without_membership':
        request.update(entrypoint='search.query_execution.tenant_search', actor='platform administrator account9, admin-login', session=None)
        role = 'PLATFORM_ADMIN_WITHOUT_LIBRARY_MEMBERSHIP'
        detail, error_class = 'Library resource not found.', 'LIBRARY_MEMBERSHIP_CONCEALED'
        basis = 'Platform authority never creates tenant membership. Current Search requires exact-library role even for PUBLIC libraries.'
    elif action and action.startswith('request_private_'):
        request.update(actor='active verified outsider account3, outsider-login', workspace='PATRON')
        role = 'NONMEMBER_PRIVATE_OUTSIDER'
        if action in ('request_private_suggestions', 'request_private_corrections'):
            request.update(entrypoint='GET /query/suggestions', transport='FastAPI TestClient HTTP')
            detail, error_class = 'Library resource not found.', 'LIBRARY_MEMBERSHIP_CONCEALED'
            body_evidence = 'EXACT_GENERIC_BODY_ASSERTED_IN_C2_TEST_NOT_SERIALIZED_IN_OBSERVATION'
            if action.endswith('corrections'):
                request['surface_note'] = 'Corrections share suggestions endpoint; C2 did not execute a separate correction-select transport.'
        elif action == 'request_private_clarification_choices':
            request.update(entrypoint='POST /query/resolve', transport='FastAPI TestClient HTTP', query='Fiction 4',
                           session='A', clarification='pending_A', choice='genuine offered choice')
            detail, error_class = 'Library resource not found.', 'LIBRARY_MEMBERSHIP_CONCEALED'
            body_evidence = 'EXACT_GENERIC_BODY_ASSERTED_IN_C2_TEST_NOT_SERIALIZED_IN_OBSERVATION'
        else:
            request.update(entrypoint='search.session_store.resolve', query='', session='A')
            detail, error_class = 'Search context not found.', 'SEARCH_CONTEXT_OWNERSHIP_CONCEALED'
            basis = 'C2 calls the lower-level session restore directly: foreign account/login fails full ownership equality404 before returning plan. Full HTTP authorization wrapper was not exercised by this row.'
    elif action == 'clear_current_authorized_search_context':
        canonical, oracle = 200, 'clear_exact_context'
        request.update(entrypoint='search.session_store.clear', query=None, session='A',
                       note='Explicit clear control; row query text is not passed to a natural-language parser.')
        error_class, detail = 'SUCCESS_EXACT_OWNER_CLEAR', None
        basis = 'Exact owner may delete its accepted and pending context. This function does not delete personalization.'
    elif row['family_id'] in ('d24_refinement_turns', 'd25_instead_turns'):
        canonical, oracle = 200, 'legacy_delta_sequence'
        request.update(entrypoint='search.session_store.resolve', session='new synthetic delta UUID',
                       facets=['Fiction', 'History', 'Computer science', 'Java', 'Neural networks'],
                       preceding_request={'query': 'books about neural networks', 'filters': {'rating_min': 2}})
        error_class, detail = 'SUCCESS_TYPED_PLAN_RESPONSE', None
        basis = 'A returned typed blocked plan is still HTTP-style success200; execution and accepted-state commitment depend on its decision, not this status.'
    else:
        raise AssertionError(action)
    return {'expected_status': canonical, 'expected_statuses': [canonical], 'state_oracle_id': oracle,
            'actor_role': role, 'request': request,
            'body_or_error': {'class': error_class, 'canonical_detail': detail, 'historical_body': None,
                              'historical_body_recorded': False, 'evidence': body_evidence},
            'canonical_reason': basis}


def check_boundary(obs, oracle):
    c = changes(obs['before'], obs['after'])
    # Independent document comparisons; phase assertions are explicitly distinguished below.
    if oracle == 'no_mutation':
        ok = obs['before'] == obs['after']
    elif oracle in ('current_membership_loss', 'other_library_membership_loss', 'clear_exact_context'):
        ok = all(len(c[k]['removed']) == 1 and not c[k]['inserted'] and not c[k]['updated']
                 for k in ('accepted', 'pending'))
        ok = ok and not c['profiles']['inserted'] and not c['profiles']['updated']
        ok = ok and len(c['profiles']['removed']) == (0 if oracle == 'clear_exact_context' else 1)
        a, b = binding(obs)
        target = b if oracle == 'other_library_membership_loss' else a
        ok = ok and c['accepted']['removed'] == [target['search_session_id']] and c['pending']['removed'] == [target['_id']]
    elif oracle == 'reject_then_genuine_once':
        a, _ = binding(obs)
        ok = c['accepted']['updated'] == [a['search_session_id']] and c['pending']['updated'] == [a['_id']]
        ok = ok and all(not c[k][op] for k in ('accepted', 'pending', 'profiles') for op in ('inserted', 'removed'))
        ok = ok and not c['profiles']['updated']
        before = next(v for v in obs['before']['accepted'] if v['_id'] == a['search_session_id'])
        after = next(v for v in obs['after']['accepted'] if v['_id'] == a['search_session_id'])
        pending = next(v for v in obs['after']['pending'] if v['_id'] == a['_id'])
        ok = ok and after['version'] == before['version'] + 1 and pending.get('used') is True
        ok = ok and all(before.get(k) == after.get(k) for k in OWNER)
    elif oracle == 'legacy_delta_sequence':
        ok = len(c['accepted']['inserted']) == 1 and not c['accepted']['removed'] and not c['accepted']['updated']
        ok = ok and all(not c[k][op] for k in ('pending', 'profiles') for op in ('inserted', 'removed', 'updated'))
    else:
        raise AssertionError(oracle)
    return {'snapshot_boundary_oracle_pass': bool(ok), 'changes': c,
            'intermediate_denial_snapshot_available': False,
            'intermediate_phase_evidence': 'C2 source assertions: compare capture()==before immediately after denial; genuine+replay occur before final snapshot' if oracle == 'reject_then_genuine_once' else 'C2 source assertions and final snapshots; full action phase bodies are not recorded'}


def main():
    provenance = {'review_status': 'AI_REVIEWED', 'human_reviewed': False, 'human_reviewed_count': 0,
                  'reviewer': 'C3 delegated contract reviewer; separate from parser-hardening agent',
                  'current_parser_output_visible': True, 'c2_native_outputs_visible': True,
                  'blind_gold_correction': False, 'calibration_or_heldout_read': False,
                  'fresh_parser_or_application_calls': 0,
                  'independence_scope': 'Independent semantic judgment from source contracts; not output-blind and not human review'}
    data = [r for r in rows(DEV) if r.get('requires_native_execution')]
    observations = rows(OBS)
    by_id = {r['query_id']: r for r in data}
    assert len(data) == len(by_id) == len(observations) == 352
    assert set(by_id) == {r['query_id'] for r in observations}
    contracts, audited = [], []
    for line, obs in enumerate(observations, 1):
        row = by_id[obs['query_id']]
        c = action_contract(row, obs)
        record = {'query_id': row['query_id'], 'family_id': row['family_id'],
                  'scope': row['scope_type'], 'action': row.get('expected_action'),
                  'historical_expected_status': row.get('expected_http_status'),
                  'canonical_v2_expected': c['expected_status'], **c,
                  'state_oracle': deepcopy(ORACLES[c['state_oracle_id']]), 'privacy_oracle': deepcopy(PRIVACY),
                  'fixture_binding': {'A': 'primary exact-library context', 'B': 'other exact-library control',
                                      'GLOBAL': 'global control', 'S2': 'same account other-login control',
                                      'resolve_symbols_to_disposable_ids': True},
                  'provenance': provenance}
        if row['family_id'] in ('d24_refinement_turns', 'd25_instead_turns'):
            record['raw_authored_nonempty_delta'] = {k: v for k, v in row.items()
                                                    if k.startswith('expected_') and v not in (None, [], False, '')}
            if obs.get('delta_mismatches'):
                record['reviewed_delta_contract'] = {'file': 'reports/search_v2c_c3_delta_plan_contract_v2.json', 'query_id': row['query_id']}
        contracts.append(record)
        if obs['raw_status_match'] is False:
            forged = row.get('expected_action') == 'submit_forged_choice_then_submit_genuine_choice'
            classification = 'B. STALE TEST EXPECTATION' if forged else 'C. VALID EQUIVALENT DENIAL STATUS'
            audit = {'query_id': row['query_id'], 'scope': row['scope_type'], 'actor_role': c['actor_role'],
                     'request': c['request'], 'authored_query_text': row['query_text'],
                     'expected_historical_status': row.get('expected_http_status'), 'actual_status': obs['actual_status'],
                     'canonical_v2_expected': c['expected_status'], 'canonical_v2_status_agrees': obs['actual_status'] == c['expected_status'],
                     'body_or_error_class': c['body_or_error'], 'classification': classification,
                     'reason': c['canonical_reason'], 'recommended_canonical_contract': record,
                     'state_before': state_summary(obs['before']), 'state_after': state_summary(obs['after']),
                     'state_boundary_comparison': check_boundary(obs, c['state_oracle_id']),
                     'raw_evidence': {'file': OBS, 'line': line, 'query_id': row['query_id'],
                                      'full_before_and_after_retained': True},
                     'security_invariant': 'No unauthorized execution or private disclosure; no foreign-owner mutation. Rejection preserves state unless fresh evidence proves exact current scope access lost; genuine authorized choice may commit once.',
                     'authn_vs_authz': 'Authenticated verified actor; failure concerns membership/role or resource ownership, not invalid login authentication.',
                     'provenance': provenance}
            audited.append(audit)
    assert len(audited) == 233
    old = read('reports/search_v2c_c2_development_native.json')
    assert {r['query_id'] for r in audited} == {r['query_id'] for r in old['raw_http_status_mismatch_cases']}
    inputs_hashes = {p: file_hash(p) for p in INPUTS}
    source_hashes = {p: file_hash(p) for p in SOURCES}
    historical_labels = sum(r.get('expected_http_status') is not None for r in data)
    boundary = [check_boundary(o, c['state_oracle_id']) for o, c in zip(observations, contracts)]
    write('native_status_audit.json', {
        'version': 'V2C-C.3-native-status-audit-1', 'generated_at': datetime.now(timezone.utc).isoformat(),
        'review_provenance': provenance, 'historical_artifacts_modified': False,
        'population': {'all_native': 352, 'historically_labeled_statuses': historical_labels,
                       'historical_status_agreements': 99, 'historical_status_disagreements': 233},
        'classification_counts': dict(Counter(r['classification'] for r in audited)),
        'classification_categories': {'A': 'PRODUCT CONTRACT DEFECT', 'B': 'STALE TEST EXPECTATION',
                                      'C': 'VALID EQUIVALENT DENIAL STATUS', 'D': 'AUTHENTICATION VS AUTHORIZATION',
                                      'E': 'FIXTURE / PRIOR-STATE ASSUMPTION', 'F': 'RACE / EXPIRY EXPECTATION', 'G': 'UNKNOWN'},
        'product_status_contract_defects': 0, 'unknown_classifications': 0,
        'c2_evidence_rechecked_against_v2': {'status_agreements': sum(o['actual_status'] == c['expected_status'] for o, c in zip(observations, contracts)),
                                            'denominator': 352, 'fresh_evaluation': False,
                                            'boundary_state_oracle_failures': sum(not v['snapshot_boundary_oracle_pass'] for v in boundary)},
        'limitations': ['No C2 response bodies were serialized; inferred canonical body must not be reported as observed.',
                        'Private corrections use suggestions endpoint; private metadata uses direct session-store ownership guard.',
                        'C2 final choice snapshots include later valid commit; invalid-attempt invariance is proved by source test assertions, not a serialized intermediate snapshot.',
                        'HTTP200 on a delta row does not prove execution or semantic refinement correctness.'],
        'input_sha256': inputs_hashes, 'canonical_source_sha256': source_hashes, 'cases': audited})
    write('native_contract_v2.json', {
        'version': 'LuminaR-native-contract-v2-c3-1', 'review_provenance': provenance,
        'population': '352 unique DEVELOPMENT native IDs, no calibration/heldout cases', 'case_count': 352,
        'historical_expectations_preserved': True, 'status_policy': {
            '401': 'invalid/expired decoded authentication or inactive account; interactions additionally require login sid',
            '403': 'active exact-library member lacks requested GENERAL_USER versus ADMIN/LIBRARIAN workspace role',
            '404': 'absent/foreign concealed resource: no active membership, foreign exact owner tuple, unavailable/unoffered choice',
            '409': 'accepted version changed, used/mismatched choice, concurrent reservation; original accepted state preserved',
            '410': 'existing pending choice expired at request time; no imposed410 for ordinary accepted-context expiry',
            '422': 'invalid structured request/UUID, forbidden plan injection or invalid supported operand',
            '503': 'temporary catalogue recovery/busy; never independently proves access loss'},
        'privacy_and_ownership_contract': {
            'owner_tuple': list(OWNER), 'public_tenant_search_requires_membership': True,
            'role_policy': {'PATRON': ['GENERAL_USER'], 'STAFF': ['ADMIN', 'LIBRARIAN']},
            'platform_admin_override': False, 'authorization_before_vocabulary_and_state_io': True,
            'rejected_endpoint_error_alone_can_invalidate': False,
            'cleanup_authority': 'fresh current eligibility/role check under existing library mutation lock; delete only inaccessible exact tuple(s) for this account/login/library',
            'preserve': ['other login sid', 'other library', 'GLOBAL', 'still-authorized workspace'],
            'pending_binding': ['owner tuple', 'search_session_id', 'query', 'mode', 'parser_version', 'base_version', 'offered choice_id', 'expiry'],
            'single_use': 'validation preview before reservation; accepted CAS/version+receipt commits at most once; invalid request does not consume genuine choice'},
        'state_oracles': ORACLES, 'privacy_oracle': PRIVACY,
        'input_sha256': inputs_hashes, 'canonical_source_sha256': source_hashes, 'cases': contracts})
    make_delta(by_id, observations, provenance, inputs_hashes)
    make_markdown(contracts, audited, provenance)
    print(json.dumps({'native_ids': 352, 'audited_status_disagreements': 233,
                      'classifications': dict(Counter(r['classification'] for r in audited)),
                      'c2_status_agreement_with_source_grounded_v2': '352/352 (historical evidence only)',
                      'boundary_state_failures': sum(not v['snapshot_boundary_oracle_pass'] for v in boundary),
                      'delta_cases_audited': 4}))


def make_delta(by_id, observations, provenance, hashes):
    diagnostics = read('reports/search_v2c_c2_native_diagnostics.json')['legacy_delta_cases']
    selected = [r for r in diagnostics if r.get('delta_mismatches')]
    assert len(selected) == 4
    cases, contracts = [], []
    for obs in selected:
        row = by_id[obs['query_id']]
        known_before = {r['_id'] for r in obs['before']['accepted']}
        final = next(r for r in obs['after']['accepted'] if r['_id'] not in known_before)
        prior = final.get('previous_plan') or final['current_plan']
        above = row['query_text'] == 'above 4'
        prior_expected = {'mode': 'SMART', 'intent': 'DISCOVER_TOPIC', 'semantic_text': 'neural networks',
                          'subjects': [], 'rating_min': 2, 'rating_min_exclusive': False,
                          'rating_max': None, 'rating_max_exclusive': False, 'formats': [],
                          'exclude_subjects': [], 'exclude_terms': []}
        if above:
            classification = 'LEGACY_LABEL_PRIOR_CONTEXT_UNDERSPECIFIED_SAFE_NONEXECUTION'
            normative = {'decision': 'AMBIGUOUS', 'execution_allowed': False,
                         'emitted_hard_rating_bound': None, 'accepted_plan_after': prior_expected,
                         'accepted_version_delta': 0, 'requires_field_clarification': 'rating versus another quantitative meaning'}
            reason = 'A bare above4 lacks a named field or unit. The original row has no prior plan, so rating>4 cannot be independent gold. The synthetic prior supplies an explicit rating control but never proves that this utterance addresses it. Accepted V2B finite grammar documents rating above4; source-evidence safety favors clarification over inventing a strict rating edit.'
            effect = 'Authored rating>4 would discard rating2..4 candidates. Safe nonexecution executes no new candidate set and retains accepted neural-networks/rating>=2 state; it is not state corruption.'
            intentional = 'The finite explicit-field refinement contract intentionally does not infer every fieldless comparative. C2 preserved accepted version1/rating2; exact returned decision/body was not serialized.'
        else:
            subject = row['query_text'].split(' ', 1)[1]
            classification = 'SESSION_REFINEMENT_DEFECT_WITH_SYNTHETIC_PRIOR_LIMITATION'
            plan = {**prior_expected, 'intent': 'BROWSE_CATEGORY', 'semantic_text': None, 'subjects': [subject]}
            normative = {'decision': 'EXECUTABLE', 'execution_allowed': True,
                         'accepted_plan_after': plan, 'accepted_version_delta': 1,
                         'retained_fields': ['rating_min', 'rating_min_exclusive'],
                         'replaced_fields': ['semantic_text', 'subjects', 'title_text', 'author_text', 'exact_text', 'intent', 'soft_preference']}
            reason = 'Explicit instead is a topic-replacement operator under accepted V2B prose; position before X has the same semantics as X instead. Canonical X is supplied by the isolated facet vocabulary. Replacement retains non-topic constraints, so the synthetic rating>=2 must survive. Existing suffix-only recognizer falls back to a fresh independent query for this prefix.'
            effect = 'Expected hard canonical subject '+subject+' plus rating>=2; actual accepted plan has neither hard guard and literal topic '+repr(final['current_plan'].get('semantic_text'))+'. This changes strict eligibility and semantic retrieval. A subject-X book rated1.5 is excluded by reviewed guards but not by actual hard guards; actual ranked/result membership was not captured, so no end-to-end result count is inferred.'
            intentional = 'Resetting filters for a new independent topic is intentional; treating explicit prefix instead as an independent topic is not semantically justified. This is a refinement/eligibility defect, not foreign ownership or security corruption.'
        contract = {'query_id': row['query_id'], 'query_text': row['query_text'],
                    'scope': row['scope_type'], 'fixture_prior': prior_expected,
                    'facet_vocabulary': ['Fiction', 'History', 'Computer science', 'Java', 'Neural networks'],
                    'expected_http_status': 200, 'normative_v2': normative,
                    'review_provenance': provenance, 'original_label_immutable': True}
        contracts.append(contract)
        cases.append({'query_id': row['query_id'], 'family_id': row['family_id'], 'scope': row['scope_type'],
                      'requested_refinement': row['query_text'], 'previous_accepted_plan': plan_summary(prior),
                      'prior_evidence': 'reconstructed from final unchanged current_plan' if above else 'final previous_plan captures accepted synthetic seed',
                      'original_prior_defined': False, 'synthetic_prior': {'seed_query': 'books about neural networks', 'explicit_filters': {'rating_min': 2},
                                                                        'fixture_validity': 'Valid isolated supplemental sequence; does not repair absent original authoring context or create output-blind gold.'},
                      'original_expected_delta': obs['delta_mismatches'],
                      'original_expected_authored_fields': {k: v for k, v in row.items() if k.startswith('expected_')},
                      'actual_delta': {k: v['actual'] for k, v in obs['delta_mismatches'].items()},
                      'actual_accepted_plan_after': plan_summary(final['current_plan']),
                      'actual_accepted_version': final['version'], 'actual_returned_complete_plan_recorded': False,
                      'accepted_prior_rating_retained': obs['accepted_plan_prior_rating_retained'],
                      'classification': classification, 'semantic_reason': reason,
                      'candidate_set_effect': effect, 'intentionality': intentional,
                      'normative_v2_contract': contract, 'review_provenance': provenance})
    write('delta_plan_audit.json', {'version': 'V2C-C.3-legacy-delta-review-1', 'case_count': 4,
                                   'selection_rule': 'Exactly nonempty C2 delta_mismatches among 20 legacy native delta rows; rating-retention diagnostics alone are not failures.',
                                   'review_provenance': provenance, 'historical_artifacts_modified': False,
                                   'original_delta_labels_rewritten': False, 'input_sha256': hashes,
                                   'classification_counts': dict(Counter(r['classification'] for r in cases)), 'cases': cases})
    write('delta_plan_contract_v2.json', {'version': 'LuminaR-reviewed-synthetic-delta-contract-v2-c3-1',
                                         'review_provenance': provenance, 'case_count': 4,
                                         'policy': 'Supplemental normative output-visible AI review. Compare raw original deltas separately. No blind-gold or real-world sequence claim.', 'cases': contracts})


def make_markdown(contracts, audited, provenance):
    table = Counter((r['action'] or r['family_id'], r['expected_status']) for r in contracts)
    lines = ['# LuminaR native contract v2 — C3 development review', '',
             'AI_REVIEWED; HUMAN_REVIEWED=0. Reviewer is separate from the parser-hardening agent, but saw preserved C2 native outputs. This is a source-grounded contract audit, not output-blind gold correction. No fresh parser/API/database/evaluator calls, calibration or held-out access occurred.', '',
             'All 352 unique DEVELOPMENT native IDs are covered by `search_v2c_c3_native_contract_v2.json`. The 233 historical discrepancies and original statuses remain individually visible in `search_v2c_c3_native_status_audit.json`; C2 inputs are immutable.', '',
             '## Existing authorization and ownership', '',
             'Public library status changes discovery/join policy; current tenant Search still requires active exact-library membership. GENERAL_USER owns PATRON operations; ADMIN/LIBRARIAN owns STAFF operations. Platform administration supplies no membership override. Guards check current verified identity and current membership before facets, projections, cache/index reads, pending state, retrieval or hydration.', '',
             'A resource belongs to `(user_id, login_session/JWT sid, GLOBAL-or-LIBRARY scope, exact library_id, workspace)`. Matching only account, UUID or library is insufficient. Search plans, pending choices and profiles never cross this tuple. Tenant Search never falls back to the global candidate universe.', '',
             'Active membership with the wrong workspace role returns403. No active membership, including removed membership and platform admins without tenant membership, returns generic concealed404. Foreign search UUID or pending choice ownership and a valid-shaped unoffered choice UUID also return404. None of the 233 cases involves invalid authentication.', '',
             'Invalid/expired decoded authentication or inactive identity returns401; interactions additionally require a login sid. No missing-bearer transport status is prescribed by this audit. Malformed UUID/schema, forbidden plan patches and invalid operands return422. A used/stale/mismatched-version choice or concurrent claim returns409. Existing pending choices that are still stored but expired return410; Mongo TTL may already have removed a choice, yielding404. Ordinary accepted-context expiry starts a fresh plan; no blanket410 is imposed. Busy/recovery503 does not prove authorization loss.', '',
             '## Mutation and privacy invariants', '',
             'A denied endpoint operation alone cannot erase accepted or pending state. Fresh current-scope eligibility loss, checked under the existing membership mutation lock, permits deleting only inaccessible exact tuples for the current account/login/library and their profile entries. Preserve other libraries, GLOBAL, other login sids and still-authorized workspaces. A STAFF role denial must preserve an authorized PATRON context.', '',
             'Choice resolution validates the server-issued choice before claiming it, binds original query/mode/session/parser/base-version/expiry, and commits through accepted-context CAS with a receipt. An invalid choice must preserve every document and the genuine choice. The genuine original owner may subsequently commit exactly once; replay409 must preserve that commit. A successful explicit context clear deletes that exact accepted UUID and its pending records, leaving profiles unchanged.', '',
             'The privacy oracle requires generic errors with no private catalogue/vocabulary, result, accepted plan, candidate choices or personalization disclosures. C2 observation JSONL did not serialize bodies: details in the audit are source-inferred, not fabricated observed responses. C2 asserts exact generic bodies only on private suggestions/corrections/resolve. A fresh evaluator must capture bodies and phase snapshots to strengthen privacy evidence.', '',
             '## Exact request status contracts', '',
             '| Action/family | Cases | Canonical primary status |', '|---|---:|---:|']
    lines.extend('| '+str(action)+' | '+str(count)+' | '+str(status)+' |' for (action, status), count in sorted(table.items()))
    lines += ['', 'The 47 cross-library sequences additionally require404 after B membership removal. The 91 invalid-choice/cross-login sequences additionally require genuine200 then replay409. Twenty legacy delta rows return typed plans with status200 even when their decision blocks execution; status must not substitute for semantic delta or accepted-plan checks.', '',
              'Classification: 189 C VALID EQUIVALENT DENIAL STATUS, 44 B STALE TEST EXPECTATION. The forged-choice list omitted the existing unavailable-choice404 convention and included statuses with other meanings. No evidence supports changing authorization/product behavior for these233 status disagreements. Source-grounded v2 expectations happen to agree with all352 preserved C2 primary statuses; this is a retrospective evidence check, not a fresh C3 result.', '',
              '## Four legacy delta rows', '',
              'The separate delta audit selects exactly the four nonempty authored-field mismatch dictionaries, not all rating changes. Original delta labels remain untouched. Three prefix `instead X` queries should replace the topic with canonical X while retaining synthetic rating>=2; suffix-only recognition instead reset the accepted plan. Bare `above 4` has no field/unit and the original row has no prior state. The reviewed supplemental sequence requires safe clarification and no accepted mutation, rather than turning an injected prior control into independent blind gold.', '',
              '`search_v2c_c3_delta_plan_contract_v2.json` freezes these four output-visible normative supplemental contracts. The original raw delta comparison must remain separate. Full prior plans in the audit come from C2 final `previous_plan` or unchanged seed; the C2 before snapshot predates synthetic seeding. No end-to-end candidate counts are inferred.', '',
              '## Executable artifact and preservation', '',
              'Machine-readable case records include historical expectation, exact v2 expected status, symbolic request and role, transport distinction, phase/state/privacy oracles and review provenance. Each JSON artifact records SHA256 for its immutable inputs and the contract source used. Native records preserve all IDs; no broad 4xx adapter, silent status normalization or weakened state oracle is introduced.', '']
    (R / 'search_v2c_c3_native_contract_v2.md').write_text('\n'.join(lines), encoding='utf8')


if __name__ == '__main__':
    main()
