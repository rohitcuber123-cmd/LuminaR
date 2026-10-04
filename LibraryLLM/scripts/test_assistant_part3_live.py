"""Read-only Part 3 audit against existing services; never loads a model.

Uses existing eligible identities and keeps credentials/account rows in memory.
Library mutations remain disabled. Reading-list writes are tested separately
against isolated fixtures, never against a real user's persisted list.
"""
import hashlib
import json
from pathlib import Path
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def main():
    from backend.database.mongodb import users_collection, issues_collection, reservations_collection, reading_list_collection
    from backend.services.identity_service import current_identity
    from backend.utils.jwt_utils import create_access_token
    users = [u for u in users_collection.find({'role': 'GENERAL_USER', 'is_email_verified': True})
             if current_identity({'sub': str(u['user_id'])})]
    user = users[0]
    headers = {'Authorization': 'Bearer ' + create_access_token(user['user_id'], user['email'], user['role'])}
    config = json.loads((ROOT / 'reports/assistant_latency_cases.json').read_text())
    seeds, doc = config['seeds'], config['document_id']
    collections = [issues_collection, reservations_collection, reading_list_collection]
    before = [digest(list(c.find({}))) for c in collections]
    output = ROOT / 'reports/part3_test_live.json'
    results = {'real_services': True, 'mutations_enabled': False, 'cases': [],
               'privacy': 'No credentials or account rows retained; account response hashes only.'}
    with httpx.Client(timeout=180) as client:
        results['health'] = client.get('http://127.0.0.1:8005/health').json()
        def call(name, payload, auth=headers):
            start = time.perf_counter()
            resp = client.post('http://127.0.0.1:8005/assistant/chat', headers=auth, json=payload)
            body = resp.json()
            profile = None
            trace = resp.headers.get('x-assistant-trace')
            for _ in range(20):
                path = ROOT / 'reports/part3_test_profiles.jsonl'
                rows = [json.loads(line) for line in path.read_text().splitlines() if line] if path.exists() else []
                profile = next((r for r in rows if r['trace_id'] == trace), None)
                if profile:
                    break
                time.sleep(.025)
            rag = body.get('rag') or {}
            row = {'case': name, 'status': resp.status_code, 'intent': body.get('intent'),
                   'client_total_ms': round((time.perf_counter()-start)*1000, 2), 'profile': profile,
                   'book_ids': [b['work_id'] for b in body.get('books', [])],
                   'seed_work_ids': body.get('seed_work_ids'), 'recommendation_mode': body.get('recommendation_mode'),
                   'has_more': body.get('has_more'), 'result_offset': body.get('result_offset'),
                   'explanation_available': body.get('explanation_available'),
                   'reading_list_count': len(body.get('reading_list') or []),
                   'account_digest': digest(body.get('account')), 'account_present': body.get('account') is not None,
                   'availability': body.get('availability'),
                   'rag_verdict': rag.get('verdict'), 'rag_source_count': len(rag.get('sources', [])),
                   'error_codes': [e['code'] for e in body.get('errors', [])],
                   'clarification': (body.get('clarification') or {}).get('reason'),
                   'pending_present': bool(body.get('pending_action'))}
            if not body.get('account'):
                row['message'] = body.get('message')
            results['cases'].append(row)
            output.write_text(json.dumps(results, indent=2), encoding='utf-8')
            print(json.dumps({k: row[k] for k in ('case','status','intent','client_total_ms','error_codes')} |
                             {'qwen_calls': profile['qwen_call_count'] if profile else None}), flush=True)
            return body
        call('unauthenticated', {'message': 'Show my reading list', 'action': 'USER_READING_LIST'}, {})
        call('invalid_token', {'message': 'Show my reading list'}, {'Authorization': 'Bearer invalid-test-token'})
        search = call('search', {'message': 'Find books about neural networks'})
        for name, payload in [
            ('available_now', {'message': 'Show me books available now.', 'action': 'AVAILABLE_NOW'}),
            ('recommend_default', {'message': 'Recommend', 'action': 'RECOMMEND'}),
            ('recommend_one', {'message': 'Recommend', 'action': 'RECOMMEND_SIMILAR', 'selected_work_ids': seeds[:1]}),
            ('recommend_multiple', {'message': 'Recommend', 'action': 'RECOMMEND_FROM_SELECTION', 'selected_work_ids': seeds}),
            ('compare', {'message': 'Compare these two', 'action': 'COMPARE', 'selected_work_ids': seeds}),
            ('availability', {'message': 'Is this available?', 'action': 'CHECK_AVAILABILITY', 'selected_work_ids': seeds[:1]}),
            ('available_alternatives', {'message': 'Find available alternatives', 'action': 'RECOMMEND_AVAILABLE_SIMILAR', 'selected_work_ids': seeds[:1]}),
            ('reading_list', {'message': 'Show my reading list', 'action': 'USER_READING_LIST'}),
            ('fees', {'message': 'Do I have fines?', 'action': 'USER_FEES'}),
            ('loans', {'message': 'Show my loans', 'action': 'USER_LOANS'}),
            ('reservations', {'message': 'Show my reservations', 'action': 'USER_RESERVATIONS'}),
            ('general', {'message': 'What is Gothic fiction?'}),
            ('document_rag', {'message': 'According to this PDF, what is role-based access control?', 'action': 'DOCUMENT_QUESTION', 'page_context': {'document_id': doc}}),
            ('book_rag_unauthorized', {'message': 'What happens when Victor creates the creature?', 'action': 'BOOK_CONTENT_QUESTION', 'selected_work_ids': ['OL45326637W']}),
            ('show_more_ui_payload', {'message': 'Show more', 'action': 'SEARCH_BOOKS', 'conversation_id': search['conversation_id'], 'result_offset': len(search.get('books', []))}),
            ('unknown_book', {'message': 'Is this available?', 'action': 'CHECK_AVAILABILITY', 'selected_work_ids': ['OL_AUDIT_MISSING_W']}),
        ]:
            body = call(name, payload)
            if name == 'compare':
                call('explain_comparison_direct', {'message': 'Explain comparison', 'action': 'EXPLAIN_COMPARISON', 'conversation_id': body['conversation_id']})
            if name == 'recommend_one':
                call('explain_recommendation_direct', {'message': 'Why these recommendations?', 'action': 'EXPLAIN_RECOMMENDATION', 'conversation_id': body['conversation_id']})
        from rag.book_assets import indexed_books
        indexed = set(indexed_books())
        for candidate in users:
            loan = next((r for r in issues_collection.find({'user_id': candidate['user_id'], 'status': 'ISSUED'}) if r.get('work_id') in indexed), None)
            if loan:
                book_headers = {'Authorization': 'Bearer '+create_access_token(candidate['user_id'], candidate['email'], candidate['role'])}
                call('book_rag_authorized', {'message': 'Who is the main character in this selected book?', 'action': 'BOOK_CONTENT_QUESTION', 'selected_work_ids': [loan['work_id']]}, book_headers)
                break
        for name, message, context in [
            ('general_after_search', 'What is Gothic fiction?', {}),
            ('dystopian_after_search', 'What is dystopian fiction?', {}),
            ('autobiography_after_search', 'Explain autobiography.', {}),
            ('document_after_search', 'What does this PDF say about indexing?', {'document_id': doc}),
            ('account_after_search', 'What do I owe?', {}),
        ]:
            state = call(name+'_setup', {'message': 'Find books about AI'})
            call(name, {'message': message, 'conversation_id': state['conversation_id'], 'page_context': context})
        # Genuine refinements share search context; no list writes here.
        state = call('followup_search', {'message': 'Find books about AI'})
        for name, phrase in [('only_available', 'only available ones'), ('show_more_typed', 'show more'),
                             ('second_one', 'the second one'), ('more_like_second', 'recommend something like the second one')]:
            call(name, {'message': phrase, 'conversation_id': state['conversation_id']})
        loans = call('due_order_setup', {'message': 'Show my loans'})
        call('due_order_followup', {'message': 'Which one is due first?', 'conversation_id': loans['conversation_id']})
        call('reading_list_compare', {'message': 'Compare the first two books in my reading list'})
        pending = call('reserve_proposal', {'message': 'reserve this', 'selected_work_ids': seeds[:1]})
        if pending.get('pending_action'):
            base = {'conversation_id': pending['conversation_id'], 'pending_action_id': pending['pending_action']['action_id']}
            call('confirm_disabled', {'message': 'Confirm', 'action': 'CONFIRM_ACTION', **base})
            call('cancel', {'message': 'Cancel', 'action': 'CANCEL_ACTION', **base})
            call('confirm_after_cancel', {'message': 'Confirm', 'action': 'CONFIRM_ACTION', **base})
            if len(users) > 1:
                second = users[1]
                other = {'Authorization': 'Bearer '+create_access_token(second['user_id'], second['email'], second['role'])}
                call('cross_user_conversation', {'message': 'Show my reading list', 'action': 'USER_READING_LIST', 'conversation_id': pending['conversation_id']}, other)
        results['real_state_unchanged'] = before == [digest(list(c.find({}))) for c in collections]
        results['state_collections_checked'] = ['issues','reservations','reading_list']
        results['qwen_load_count'] = (ROOT / 'reports/part3_test_rag_stdout.log').read_text(encoding='utf-8', errors='replace').count('Loading Qwen2.5-3B-Instruct in 4-bit...')
        output.write_text(json.dumps(results, indent=2), encoding='utf-8')
        print('Live audit complete. Real state unchanged: '+str(results['real_state_unchanged']), flush=True)


if __name__ == '__main__':
    main()
