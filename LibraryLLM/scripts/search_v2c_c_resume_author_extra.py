"""Independent, output-blind V2C-C Resume core authoring.

Reads only the permitted legacy scope snapshot. No parser, evaluator, test, or
runtime-output imports. Normative labels precede any execution. Original files
are never written. Security cases are native contracts, not parser tests.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/search_v2c_c_resume_additional_core.jsonl'
VOCAB = json.loads((ROOT / 'reports/search_v2c_c_scope_vocabularies.json').read_text(encoding='utf-8-sig'))
PRIVATE_LIVE = '9503c223-72fc-44c3-a9c6-8dcbda7b4510'
ROWS = []

def row(family, n, text, scope='PRIVATE_PATRON', split='development', **labels):
    r = dict(query_id=f'v2cc-resume-core-{family}-{n:02}', family_id=f'resume_{family}',
             template_id=f'resume_{family}_contract', variant_seed=None, query_text=text,
             query=text, scope_type=scope,
             workspace_type='GLOBAL' if scope == 'GLOBAL' else ('STAFF' if 'STAFF' in scope else 'PATRON'),
             split=split, search_mode='SMART', category='independent_additional_core',
             authoring_source='independent AI author; user prompt and frozen scope vocabularies only',
             review_source='AI author self-check; separate from independent review of original540',
             review_status='AI_REVIEWED', reviewer_type='AI', human_reviewed=False,
             expected_decision='AUTO_EXECUTE', expected_intent='DISCOVER_TOPIC',
             expected_subjects=[], expected_excluded_subjects=[], expected_exclude_terms=[],
             expected_author=None, expected_title=None, expected_title_entity=None,
             expected_exact_text=None, expected_rating_min=None, rating_min_exclusive=False,
             expected_rating_max=None, rating_max_exclusive=False, expected_year_min=None,
             year_min_exclusive=False, expected_year_max=None, year_max_exclusive=False,
             expected_format=[], expected_exclusive_formats=[], expected_excluded_formats=[],
             expected_availability=None, expected_sort=None, expected_semantic_text='',
             expected_soft_preferences=[], expected_unsupported_fields=[], expected_ambiguity=[],
             expected_ambiguous_spans=[], expected_incomplete_fields=[], expected_contradiction=[],
             expected_contradiction_fields=[], protected_spans=[], expected_execution_allowed=True,
             execution_allowed=True, requires_native_execution=False, parser_evaluable=True,
             notes='Normative label authored without parser implementation or output access.')
    if scope != 'GLOBAL':
        r['library_id'] = PRIVATE_LIVE if 'PRIVATE' in scope else VOCAB['PUBLIC_PATRON']['library_id']
        r['vocabulary_source'] = 'legacy synthetic offline snapshot; live private fixture identity is separate'
    r.update(labels)
    ROWS.append(r)
    return r

def plan(topic='Fiction', rating=3):
    return dict(subjects=[topic], rating_min=rating, rating_min_exclusive=False,
                excluded_subjects=[], semantic_text='', format=[])

DENIAL = dict(accepted='unchanged', pending_clarification='unchanged', personalization='unchanged',
              global_context='unchanged', unrelated_libraries='unchanged', other_sids='unchanged',
              private_metadata_disclosed=False, commits=0)

def native(family, n, action, scope, actor, *, status=403, split='development', expected=None, **extra):
    text = f'Fiction rated at least {3 + n / 10:.1f}'
    before = dict(context_key=dict(user='member_A', sid='sid_1', library='library_A', workspace='PATRON'),
                  accepted_plan=plan(rating=3 + n / 10), pending_clarification=dict(id='pending_A', valid=True),
                  personalization={'sentinel': f'personalization_{family}_{n}'},
                  global_context={'sentinel': 'global_accepted'},
                  other_library_context={'sentinel': 'other_library_accepted'},
                  other_sid_context={'sentinel': 'sid_2_accepted'})
    state = dict(DENIAL)
    state.update(expected or {})
    accepted_after = extra.pop('expected_accepted_plan_after_turn', before['accepted_plan'])
    decision = extra.pop('expected_decision', 'DENIED' if status == 403 else 'REJECTED')
    r = row(family, n, text, scope, split,
            expected_decision=decision,
            expected_execution_allowed=False, execution_allowed=False,
            expected_intent='NATIVE_LIFECYCLE_ACTION', requires_native_execution=True,
            parser_evaluable=False, expected_http_status=status, expected_action=action,
            security_case=True, previous_accepted_plan=before['accepted_plan'],
            expected_accepted_plan_after_turn=accepted_after,
            expected_pending_clarification='preserve valid pending_A unless explicitly expired or consumed',
            expected_context_mutation=state, actor_context=actor,
            sequence_steps=[dict(step=1, action='seed_authorized_control_contexts', state=before),
                            dict(step=2, action=action, actor=actor, query_text=text,
                                 expected_http_status=status, expected_state=state),
                            dict(step=3, action='assert_authorized_control_contexts_and_no_disclosure',
                                 expected_state=state)],
            expected_ambiguity=[], **extra)
    r['sequence_steps'][0]['state']['pending_clarification'].update(
        query_text='Fiction 4', offered_choice='genuine_choice', offered_plan=plan(rating=4))
    r['native_fixture_requirements'] = [
        'Resolve symbolic users, sids, library_A/library_B and context sentinels to isolated test fixture identities.',
        'Apply the accepted current authorization policy; never manufacture a denied path by weakening or changing role policy.',
        'Snapshot and compare accepted, pending, personalization and unrelated scope state at every action boundary.'
    ]
    if family in ['forged_clarification','cross_sid_clarification','cross_user_clarification']:
        r['sequence_steps'].insert(2, dict(step=3, action='submit_genuine_choice_in_original_authorized_context',
            actor=dict(user='member_A',sid='sid_1',pending='pending_A',choice='genuine_choice'),
            expected_http_status=200, expected_accepted_plan=plan(rating=4),
            expected_pending_clarification=None, expected_commits=1))
        r['sequence_steps'][-1]['step']=4
        r['sequence_steps'][-1]['expected_state']=dict(unrelated_contexts='unchanged', total_authorized_commits=1,
            accepted='genuine choice committed exactly once after invalid request', private_metadata_disclosed=False)
        r['sequence_contract_note']='Row-level expected_decision/accepted-after describe the invalid attempt; the later valid control is separately labeled per step.'
    if family == 'duplicate_clarification':
        r['sequence_steps']=[r['sequence_steps'][0],
            dict(step=2,action='submit_genuine_choice_in_original_authorized_context',expected_http_status=200,
                 expected_accepted_plan=plan(rating=4),expected_pending_clarification=None,expected_commits=1),
            dict(step=3,action='replay_identical_consumed_choice',expected_http_status=status,
                 expected_accepted_plan=plan(rating=4),expected_pending_clarification=None,expected_commits=1),
            dict(step=4,action='assert_no_second_commit_no_rollback_no_leak',expected_commits=1)]
        r['expected_accepted_plan_after_turn']=plan(rating=4)
    if family == 'revoked_membership':
        r['sequence_steps'].insert(1,dict(step=2,action='revoke_actual_current_membership_in_fixture',
            expected_authorization='membership is now absent in authoritative current source'))
        for index, step in enumerate(r['sequence_steps'],1): step['step']=index
        r['sequence_steps'][2]['action']='search_under_revoked_membership'
        r['expected_pending_clarification']=None
    if family == 'cross_library_isolation':
        r['sequence_steps'][1]['action']='search_unauthorized_staff_workspace_in_library_B'
        r['sequence_steps'].insert(2,dict(step=3,action='revoke_actual_membership_in_library_B_only'))
        r['sequence_steps'].insert(3,dict(step=4,action='search_library_B_after_revocation',expected_http_status=403,
            expected_state=dict(library_B_inaccessible='invalidated',library_A='unchanged',Global='unchanged',other_sids='unchanged unless same revoked B membership')))
        for index, step in enumerate(r['sequence_steps'],1): step['step']=index
    return r

SCOPES = ['PUBLIC_PATRON', 'PUBLIC_STAFF', 'PRIVATE_PATRON', 'PRIVATE_STAFF']
for n, scope in enumerate(SCOPES, 1):
    staff_target = 'PRIVATE_STAFF' if 'PRIVATE' in scope else 'PUBLIC_STAFF'
    native('cross_workspace_denial', n, 'search_unauthorized_workspace', staff_target,
           dict(user='member_A', sid='sid_1' if n % 2 else 'sid_2', library='library_A', workspace='STAFF', role='patron',
                role_policy_fixture='patron denied staff; valid patron control and independent authorized staff control remain intact'))
    native('revoked_membership', n, 'revoke_current_membership_then_search', scope,
           dict(user='revoked_member', sid='sid_1', library='library_A', membership='revoked'),
           expected=dict(accepted='invalidate only inaccessible library_A contexts',
                         pending_clarification='invalidate only inaccessible library_A contexts',
                         personalization='invalidate inaccessible library_A state only'),
           expected_accepted_plan_after_turn=None,
           revocation_scope='all and only now-inaccessible tenant contexts; no Global or library_B deletion')
    native('cross_library_isolation', n, 'search_denied_other_library_then_revoke_other_membership', staff_target,
           dict(user='multi_library_member', sid='sid_1', library='library_B', target_workspace='STAFF', role='patron'),
           multi_library_setup=dict(library_A='authorized', library_B='authorized patron but target workspace denied'),
           expected=dict(target_library_B_inaccessible_contexts='invalidated only after actual B revocation'))
    native('cross_sid_clarification', n, 'resolve_sid_1_clarification_under_sid_2', scope,
           dict(user='member_A', sid='sid_2', submitted_pending='sid_1/pending_A'),
           expected=dict(sid_1_valid_choice_after_denial='must still work exactly once'))
    native('platform_admin_without_membership', n, 'search_tenant_as_platform_admin_without_membership', scope,
           dict(user='platform_admin', sid='admin_sid', tenant_membership=False, role='platform_admin'),
           platform_admin_override_allowed=False,
           applicability_precondition='Target tenant/workspace requires membership under accepted current policy; if a public surface is anonymous-readable, record not-applicable rather than invent denial.')
    native('private_outsider_surface', n, ['request_private_suggestions', 'request_private_corrections',
           'request_private_clarification_choices', 'request_private_session_metadata'][n-1],
           'PRIVATE_OUTSIDER', dict(user='outsider', sid='outsider_sid', tenant_membership=False),
           disclosure_forbidden=['titles', 'authors', 'subjects', 'chips', 'KG concepts', 'correction candidates',
                                 'clarification choices', 'session metadata'])

REJECT_4XX = [400, 403, 409, 410, 422]
STATUS_POLICY = ('Prompt fixes denial=403 but does not fix lifecycle error codes. '
                 'This explicit accepted 4xx set tests safe rejection; freeze the native API-specific '
                 'exact contract before execution, without changing the state/no-disclosure oracle.')
for n, scope in enumerate(SCOPES, 1):
    native('forged_clarification', n, 'submit_forged_choice_then_submit_genuine_choice', scope,
           dict(user='member_A', sid='sid_1', pending='pending_A', choice='unoffered_choice'),
           status=REJECT_4XX, expected_http_status_policy=STATUS_POLICY,
           expected=dict(genuine_choice_after_rejection='works exactly once; one total authorized commit'))
    native('stale_clarification', n, 'submit_expired_or_superseded_clarification', scope,
           dict(user='member_A', sid='sid_1', pending='expired_A' if n % 2 else 'superseded_A'),
           status=REJECT_4XX, split='calibration', expected_http_status_policy=STATUS_POLICY,
           expected=dict(newer_accepted_revision='never rolled back', current_pending='unchanged'))
    native('stale_suggestion', n, 'apply_suggestion_from_older_revision', scope,
           dict(user='member_A', sid='sid_1', suggestion_revision=1, accepted_revision=2),
           status=REJECT_4XX, split='calibration', expected_http_status_policy=STATUS_POLICY,
           expected=dict(newer_accepted_revision='unchanged at revision 2'))
    native('stale_correction', n, 'apply_correction_after_context_switch', scope,
           dict(user='member_A', sid='sid_1', correction_context='old_workspace', current_context='new_workspace'),
           status=REJECT_4XX, split='calibration', expected_http_status_policy=STATUS_POLICY,
           expected=dict(current_workspace='unchanged', old_workspace='unchanged'))
    native('duplicate_clarification', n, 'submit_valid_choice_then_replay_identical_choice', scope,
           dict(user='member_A', sid='sid_1', pending='pending_A', choice='genuine_choice'),
           status=[200, 400, 409, 410, 422], split='calibration',
           expected_http_status_policy='Replay may be idempotent success or explicit stale rejection; never a second commit.',
           expected=dict(accepted='first genuine committed plan unchanged by replay', commits=1,
                         pending_clarification='consumed by first commit only'),
           expected_accepted_plan_after_turn='first genuine committed plan',
           expected_decision='IDEMPOTENT_OR_REJECTED')
    native('cross_user_clarification', n, 'resolve_another_users_clarification', scope,
           dict(user='member_B', sid='sid_B', submitted_pending='member_A/pending_A'),
           split='calibration', expected=dict(owner_valid_choice_after_denial='must still work exactly once'))

# Missing interaction and search-mode coverage. Four genuinely different inputs
# in each family; these are not anonymous one-row count padding.
for n, scope in enumerate(SCOPES, 1):
    r = row('clear_context', n, ['clear search', 'clear all search filters', 'reset my search',
                               'start a new search with no context'][n-1], scope,
            requires_native_execution=True, parser_evaluable=False,
            expected_decision='AUTO_EXECUTE', expected_intent='CLEAR_CONTEXT',
            expected_http_status=200, expected_action='clear_current_authorized_search_context',
            previous_accepted_plan=plan(), expected_accepted_plan_after_turn=None,
            expected_pending_clarification=None, expected_context_mutation=dict(
                current_accepted='cleared', current_pending='cleared', unrelated_contexts='unchanged'),
            sequence_steps=[dict(step=1, action='seed_current_and_unrelated_accepted_pending_contexts'),
                            dict(step=2, action='clear_current_authorized_search_context', expected_http_status=200),
                            dict(step=3, action='assert_current_cleared_and_unrelated_unchanged')])
    row('genre_subject_mode', n, ['Fiction', 'subject Fiction', 'include Fiction', 'browse Fiction'][n-1],
        scope, search_mode='GENRE_SUBJECT', expected_intent='BROWSE_CATEGORY', expected_subjects=['Fiction'])
    author = ['Mira Rao', 'N. K. Jemisin', 'Ursula K. Le Guin', 'bell hooks'][n-1]
    text = f'books by {author}'
    row('title_author_mode', n, text, scope, search_mode='TITLE_AUTHOR', expected_intent='FIND_AUTHOR',
        expected_author=author, protected_spans=[dict(start=9, end=len(text), text=author)])

RARE = ['Ngũgĩ wa Thiong’o', 'S. R. Ranganathan', 'Qxvyr-7', 'Æthelred']
for n, rare in enumerate(RARE, 1):
    text = f'books about "{rare}"'
    row('rare_entity_no_correction', n, text, 'GLOBAL', expected_semantic_text=rare,
        protected_spans=[dict(start=text.index(rare), end=text.index(rare)+len(rare), text=rare)],
        expected_correction=None, correction_policy='preserve rare quoted entity exactly; never destructive fuzzy replacement')

for n, (text, scope, expected) in enumerate([
    ('include Romance', 'PUBLIC_PATRON', dict(expected_decision='UNSUPPORTED', expected_unsupported_fields=['subject'], expected_execution_allowed=False, execution_allowed=False)),
    ('include Romance', 'PRIVATE_STAFF', dict(expected_intent='BROWSE_CATEGORY', expected_subjects=['Romance'])),
    ('books about Romance', 'PUBLIC_STAFF', dict(expected_semantic_text='Romance')),
    ('books about Java', 'PRIVATE_PATRON', dict(expected_semantic_text='Java')),
], 1):
    row('scope_strict_vs_topic', n, text, scope, **expected)

for n, (text, scope, expected) in enumerate([
    ('books published in 2024 about wind turbines', 'GLOBAL', dict(expected_decision='UNSUPPORTED', expected_unsupported_fields=['year'], expected_semantic_text='wind turbines', expected_execution_allowed=False, execution_allowed=False)),
    ('books published in 2024 about wind turbines', 'PUBLIC_PATRON', dict(expected_year_min=2024, expected_year_max=2024, expected_semantic_text='wind turbines')),
    ('physical only books about wind turbines', 'GLOBAL', dict(expected_decision='UNSUPPORTED', expected_unsupported_fields=['format'], expected_semantic_text='wind turbines', expected_execution_allowed=False, execution_allowed=False)),
    ('physical only books about wind turbines', 'PRIVATE_STAFF', dict(expected_format=['PHYSICAL'], expected_exclusive_formats=['PHYSICAL'], expected_semantic_text='wind turbines')),
], 1):
    row('scope_capability_distinctions', n, text, scope, **expected)

assert len(ROWS) == 72
assert len({r['family_id'] for r in ROWS}) == 18
assert len({r['query_id'] for r in ROWS}) == len(ROWS)
for family in {r['family_id'] for r in ROWS}:
    assert len({r['split'] for r in ROWS if r['family_id'] == family}) == 1
for r in ROWS:
    for span in r['protected_spans']:
        assert r['query_text'][span['start']:span['end']] == span['text']
OUT.write_text(''.join(json.dumps(r, ensure_ascii=False, separators=(',', ':'))+'\n' for r in ROWS), encoding='utf-8')
if __name__ == '__main__':
    print(json.dumps(dict(output=str(OUT), rows=len(ROWS), families=18,
                         native_rows=sum(r['requires_native_execution'] for r in ROWS),
                         parser_rows=sum(r['parser_evaluable'] for r in ROWS))))
