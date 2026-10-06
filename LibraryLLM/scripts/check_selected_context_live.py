"""Real existing-Qwen selected-context checks; one disposable reader only."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

import httpx

sys.stdout.reconfigure(encoding='utf8')

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.database.mongodb import users_collection, books_collection, db
from backend.services.identity_service import next_user_id
from backend.services.auth_service import hash_password
from backend.utils.jwt_utils import create_access_token

FIXTURE = ROOT / '.scratch/assistant_selected_context_fixture.json'
REPORT = ROOT / 'reports/assistant_selected_context_live.json'
PROFILE = ROOT / 'reports/assistant_selected_context_profiles.jsonl'

def save(path, value):
    path.write_text(json.dumps(value, indent=2, default=str), encoding='utf8')

def seed():
    assert not FIXTURE.exists(), 'Clean the previous repair fixture first.'
    marker = 'selected-context-' + uuid4().hex[:10]
    uid = next_user_id()
    email = marker + '@example.com'
    password = 'Selected-context-test-2026!'
    users_collection.insert_one({'user_id': uid, 'email': email, 'name': 'Disposable context reader',
        'role': 'GENERAL_USER', 'password_hash': hash_password(password), 'is_email_verified': True,
        'is_active': True, 'created_at': datetime.now(timezone.utc), 'selected_context_test_marker': marker})
    f = {'marker': marker, 'user_id': uid, 'email': email, 'password': password,
         'token': create_access_token(uid, email, 'GENERAL_USER')}
    FIXTURE.parent.mkdir(exist_ok=True)
    save(FIXTURE, f)
    projection = {'_id': 0, 'work_id': 1, 'title': 1, 'authors': 1, 'subjects': 1, 'description': 1}
    atomic = list(books_collection.find({'work_id': {'$in': ['OL19545719W', 'OL17930368W']}}, projection))
    collection = list(books_collection.find({'work_id': 'OL37490159W'}, projection))
    assert atomic and collection, 'Actual reported catalogue pair is required.'
    a = next(b for b in atomic if b['title'] == 'Atomic Habits')
    b = collection[0]
    others = []
    for work_id in ['OL45326637W', 'OL1968368W']:
        book = books_collection.find_one({'work_id': work_id}, projection)
        assert book, work_id
        others.append(book)
    f['books'] = [a, b, *others]
    save(FIXTURE, f)
    save(REPORT, {'router_mode': 'existing_qwen', 'books': f['books'], 'cases': []})
    print(json.dumps(f['books'], indent=2))

def run(start=0, stop=None):
    f = json.loads(FIXTURE.read_text())
    ids = [b['work_id'] for b in f['books']]
    pair = ids[:2]
    cases = [
        ('reported', 'why are these named similarly?', pair),
        ('connects', 'what connects these two?', pair),
        ('sounds', 'why do they sound alike?', pair),
        ('share', 'what do these share?', pair),
        ('titles', 'is there a reason their titles are so similar?', pair),
        ('related', 'how are these related?', pair),
        ('difference', 'what is the main difference between them?', pair),
        ('criterion', 'which seems more focused on practical habits?', pair),
        ('rating', 'which has the higher rating?', pair),
        ('availability', 'is the second available?', pair),
        ('replace', 'what do these have in common?', ids[2:]),
        ('clear', 'what do these have in common?', []),
        ('loans', 'show my loans', pair),
        ('search', 'find beginner books about Python', pair),
        ('single_stands', 'what stands out about this?', ids[:1]),
        ('single_read', 'why might someone read this?', ids[:1]),
        ('single_about', 'what is this mainly about?', ids[:1]),
        ('three', 'what do these have in common?', ids[:3]),
        ('four', 'which of these seem most closely related?', ids),
        ('override', 'tell me about Frankenstein', pair),
        ('missing_third', 'what about the third one?', pair),
        ('rag', 'what does chapter 3 argue?', ids[2:3]),
        ('account_borrowed', 'what books do I currently have borrowed?', pair),
        ('search_databases', 'find me books about databases', pair),
        ('details_second', 'tell me about the second', pair),
        ('recommend', 'recommend something based on these', pair),
        ('graph_second', 'anything like the second one', pair),
        ('borrow', 'borrow the first', pair),
        ('reading_list', 'add these to my reading list', pair),
        ('ordinal_relation', 'why does the second one seem related to the first?', pair),
        ('publication_cause', 'did one inspire the other?', pair),
        ('one_famous', 'why is this book famous?', ids[:1]),
    ]
    report = json.loads(REPORT.read_text())
    with httpx.Client(timeout=120) as client:
        for _ in range(80):
            try:
                if client.get('http://127.0.0.1:8005/health', timeout=1).status_code == 200: break
            except httpx.HTTPError:
                pass
            time.sleep(.5)
        else: raise RuntimeError('Existing RAG service did not become ready.')
        for name, message, selected in cases[start:stop]:
            started = time.perf_counter()
            response = client.post('http://127.0.0.1:8005/assistant/chat',
                headers={'Authorization': 'Bearer ' + f['token']},
                json={'message': message, 'selected_work_ids': selected, 'page_context': {}, 'recent_work_ids': []})
            response.raise_for_status()
            trace = response.headers.get('x-assistant-trace')
            profile = {}
            for _ in range(20):
                profiles = [json.loads(line) for line in PROFILE.read_text(encoding='utf8').splitlines()] if PROFILE.exists() else []
                profile = next((p for p in profiles if p['trace_id'] == trace), {})
                if profile: break
                time.sleep(.1)
            row = {'name': name, 'message': message, 'selected_work_ids': selected,
                   'response': response.json(), 'profile': profile,
                   'http_ms': round((time.perf_counter()-started)*1000, 2)}
            report['cases'] = [r for r in report['cases'] if r['name'] != name] + [row]
            save(REPORT, report)
            print(json.dumps({'name': name, 'intent': row['response']['intent'],
                'books': [b['work_id'] for b in row['response'].get('books', [])],
                'answer': row['response'].get('message'), 'clarification': row['response'].get('clarification'),
                'calls': profile.get('qwen_call_count'), 'route': profile.get('route'),
                'fuzzy': profile.get('fuzzy_title_calls'), 'search': profile.get('search_calls'),
                'ms': profile.get('total_ms')}, ensure_ascii=False), flush=True)

def clean():
    f = json.loads(FIXTURE.read_text())
    assert users_collection.find_one({'user_id': f['user_id'], 'selected_context_test_marker': f['marker']}), 'Fixture identity mismatch.'
    states = db['event_user_state'].delete_many({'user_id': f['user_id']}).deleted_count
    result = users_collection.delete_one({'user_id': f['user_id'], 'selected_context_test_marker': f['marker']})
    assert result.deleted_count == 1
    FIXTURE.unlink()
    save(ROOT / 'reports/assistant_selected_context_cleanup.json',
         {'disposable_reader_removed': True, 'owned_event_states_removed': states,
          'temporary_frontend_stopped': False, 'confirmed_mutations': 0})
    print('Disposable reader removed.')


def sequence():
    """One conversation: changed/removed/cleared selection and UI actions."""
    f = json.loads(FIXTURE.read_text())
    ids = [b['work_id'] for b in f['books']]
    report = json.loads(REPORT.read_text())
    steps = [
        ('chain_pair', 'what connects these two?', ids[:2], None, []),
        ('chain_replaced', 'what do these have in common?', ids[2:], None, []),
        ('chain_removed', 'what stands out about this?', ids[2:3], None, []),
        ('chain_cleared', 'what do these have in common?', [], None, []),
        ('ui_compare', 'Compare selected books', ids[:2], 'COMPARE', ids[:2]),
        ('ui_availability', 'Check availability', ids[:2], 'CHECK_AVAILABILITY', ids[1:2]),
    ]
    conversation = None
    with httpx.Client(timeout=120) as client:
        for name, message, selected, action, targets in steps:
            payload = {'message': message, 'selected_work_ids': selected,
                       'conversation_id': conversation, 'page_context': {'work_id': ids[0]}, 'recent_work_ids': ids[:2]}
            if action:
                payload.update(action=action, action_work_ids=targets)
            response = client.post('http://127.0.0.1:8005/assistant/chat',
                headers={'Authorization': 'Bearer ' + f['token']}, json=payload)
            response.raise_for_status()
            body = response.json()
            conversation = body['conversation_id']
            trace = response.headers.get('x-assistant-trace')
            profile = next(p for p in reversed([json.loads(line) for line in PROFILE.read_text(encoding='utf8').splitlines()])
                           if p['trace_id'] == trace)
            row = {'name': name, 'message': message, 'selected_work_ids': selected,
                   'action': action, 'action_work_ids': targets, 'response': body, 'profile': profile,
                   'same_conversation': True}
            report['cases'] = [r for r in report['cases'] if r['name'] != name] + [row]
            save(REPORT, report)
            print(json.dumps({'name': name, 'intent': body['intent'],
                              'books': [b['work_id'] for b in body.get('books', [])],
                              'answer': body['message'], 'calls': profile['qwen_call_count']}, ensure_ascii=False), flush=True)

def recover():
    assert not FIXTURE.exists()
    rows = list(users_collection.find({'selected_context_test_marker': {'$regex': '^selected-context-'},
                                      'name': 'Disposable context reader'}, {'_id': 0, 'user_id': 1, 'selected_context_test_marker': 1}))
    assert len(rows) == 1, 'Expected only the interrupted seed fixture.'
    row = rows[0]
    save(FIXTURE, {'user_id': row['user_id'], 'marker': row['selected_context_test_marker']})
    clean()

def refresh():
    f = json.loads(FIXTURE.read_text())
    f['token'] = create_access_token(f['user_id'], f['email'], 'GENERAL_USER')
    f['books'][2] = books_collection.find_one({'work_id': 'OL45326637W'},
        {'_id': 0, 'work_id': 1, 'title': 1, 'authors': 1, 'subjects': 1, 'description': 1})
    assert f['books'][2]
    save(FIXTURE, f)
    report = json.loads(REPORT.read_text())
    report['books'] = f['books']
    save(REPORT, report)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['seed', 'run', 'clean', 'recover', 'refresh', 'sequence'])
    p.add_argument('--start', type=int, default=0)
    p.add_argument('--stop', type=int)
    args = p.parse_args()
    if args.action == 'seed': seed()
    elif args.action == 'clean': clean()
    elif args.action == 'recover': recover()
    elif args.action == 'refresh': refresh()
    elif args.action == 'sequence': sequence()
    else: run(args.start, args.stop)
