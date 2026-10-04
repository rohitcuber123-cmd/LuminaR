"""Disposable PDFs/accounts, actual resident RAG engine and HTTP handlers."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['KNOW_MORE_DEVICE_CACHE_ENABLED'] = 'true'
os.environ['LUMINAR_DEBUG_PROMPT'] = '0'

import fitz
import numpy as np
from fastapi.testclient import TestClient
from backend.database.mongodb import users_collection
from backend.services.identity_service import next_user_id
from backend.services.auth_service import hash_password
from backend.main import app as core_app
from rag.api import app, private_documents, engine


def pdf_bytes(pages):
    pdf = fitz.open()
    for i in range(pages):
        page = pdf.new_page()
        topic = ['Role design', 'Auditing access', 'Least privilege', 'Permission review'][i % 4]
        paragraph = (f'Chapter {i+1}: {topic}.\n\nRole-based access control assigns permissions to roles. '
            'Users receive access by being assigned appropriate roles. This separates permission management '
            'from individual user accounts. Administrators review role membership and grant only privileges '
            'required for each job. Read-only roles can inspect records; editor roles can modify authorized records. '
            'Audit logs record access decisions and membership changes. Explicit deny rules prevent access to '
            'restricted records. Removing a user from a role removes the permissions inherited from that role.\n\n')
        text = paragraph + (f'Section {i+1}. Permission reviews compare current responsibilities with assigned privileges. '
            'Reviewers document each approved change and check that privileged accounts remain appropriate. '
            'Access to financial records and personnel records is reviewed separately. Authentication verifies '
            'the identity of the caller; authorization checks whether that identity can perform a requested action. '
            'Sessions expire at a fixed time, and signing out invalidates the active session.\n\n') * 3
        page.insert_textbox(fitz.Rect(45, 45, 550, 800), text, fontsize=10)
    data = pdf.tobytes(); pdf.close()
    return data


def main():
    identities, rows, security, equivalence = [], [], [], []
    password = secrets.token_urlsafe(24)
    core = TestClient(core_app)
    def login(account):
        response = core.post('/auth/login', json={'email': account['email'], 'password': password})
        assert response.status_code == 200, response.status_code
        return {'Authorization': 'Bearer ' + response.json()['access_token']}
    def checked(name, response, status):
        security.append({'check': name, 'status': response.status_code, 'expected': status, 'pass': response.status_code == status})
        assert response.status_code == status, name
    try:
        for label in ['A', 'B']:
            account = {'user_id': next_user_id(), 'name': 'Disposable cache validation ' + label,
                       'email': f'cache-{uuid4().hex}@example.com', 'role': 'GENERAL_USER',
                       'password_hash': hash_password(password), 'is_email_verified': True}
            users_collection.insert_one(account); identities.append(account)
        a, b = identities
        with TestClient(app) as client:
            for label, pages in [('small', 2), ('medium', 40), ('large', 200)]:
                auth_a, auth_a2, auth_b = login(a), login(a), login(b)
                content = pdf_bytes(pages)
                baseline = private_documents.metrics.copy()
                started = time.perf_counter()
                response = client.post('/rag/upload', files={'file': (label+'.pdf', content, 'application/pdf')}, headers=auth_a)
                assert response.status_code == 200, response.text
                doc = response.json()['document']; upload_time = time.perf_counter()-started
                upload_counts = {k: private_documents.metrics[k]-baseline[k] for k in ['parse_calls', 'chunk_calls', 'embedding_calls', 'faiss_builds']}
                source_id = doc['document_id']
                checked(label+':unauth_export', client.post(f'/rag/documents/{source_id}/cache/export'), 401)
                checked(label+':other_account_get', client.get(f'/rag/documents/{source_id}', headers=auth_b), 404)
                checked(label+':same_account_other_session', client.get(f'/rag/documents/{source_id}', headers=auth_a2), 404)
                query = 'According to this PDF, what is role-based access control?'
                started = time.perf_counter()
                original_answer = client.post('/rag/ask', json={'query': query, 'document_id': source_id}, headers=auth_a)
                first_question = time.perf_counter()-started
                assert original_answer.status_code == 200, original_answer.text
                original = original_answer.json()
                # Capture exact dense retrieval scores/source identity with original query embedding.
                vector, _ = engine.reranker.retriever._embed_query(query)
                with private_documents.selected(source_id, {'sub':str(a['user_id']), **__import__('jose').jwt.get_unverified_claims(auth_a['Authorization'][7:])}):
                    scores0, ids0 = engine.reranker.retriever.doc_index.search(vector, 15)
                started = time.perf_counter()
                export = client.post(f'/rag/documents/{source_id}/cache/export', headers=auth_a)
                export_time = time.perf_counter()-started
                assert export.status_code == 200
                blob = export.content; meta = json.loads(export.headers['X-Luminar-Cache'])
                checked(label+':cross_account_restore', client.post('/rag/local-cache/restore', content=blob, headers=auth_b), 400)
                checked(label+':cross_account_inspect', client.post('/rag/local-cache/inspect', json={'descriptors':[meta['encrypted_descriptor']]}, headers=auth_b), 200)
                wrong = client.post('/rag/local-cache/inspect', json={'descriptors':[meta['encrypted_descriptor']]}, headers=auth_b).json()
                assert wrong['items'][0]['error']['code'] == 'INVALID_LOCAL_CACHE'
                baseline = private_documents.metrics.copy()
                started = time.perf_counter()
                restored_response = client.post('/rag/local-cache/restore', content=blob, headers=auth_a2)
                restore_time = time.perf_counter()-started
                assert restored_response.status_code == 200, restored_response.text
                restored = restored_response.json()['document']
                counts = {k: private_documents.metrics[k]-baseline[k] for k in upload_counts}
                assert all(counts[k] == 0 for k in ['parse_calls','chunk_calls','embedding_calls']) and counts['faiss_builds'] == 1
                assert restored['document_id'] != source_id
                new_id = restored['document_id']
                from jose import jwt
                claims = jwt.get_unverified_claims(auth_a2['Authorization'][7:])
                with private_documents.selected(new_id, claims):
                    scores1, ids1 = engine.reranker.retriever.doc_index.search(vector, 15)
                started = time.perf_counter()
                restored_answer = client.post('/rag/ask', json={'query':query, 'document_id':new_id}, headers=auth_a2)
                restored_question = time.perf_counter()-started
                assert restored_answer.status_code == 200
                final = restored_answer.json()
                def normalized_sources(answer):
                    return [{k:v for k,v in s.items() if k not in {'work_id','document_id'}} for s in answer.get('sources', [])]
                check = {'size':label, 'topk_ids_equal': bool(np.array_equal(ids0,ids1)),
                         'max_score_difference': float(np.max(np.abs(scores0-scores1))),
                         'sources_equal_excluding_new_document_identity': normalized_sources(original)==normalized_sources(final),
                         'source_ids_equal': [s['chunk_id'] for s in original.get('sources',[])] == [s['chunk_id'] for s in final.get('sources',[])],
                         'verdict_before': original.get('verdict'), 'verdict_after': final.get('verdict'),
                         'answer_before': original.get('answer'), 'answer_after': final.get('answer')}
                check['pass'] = check['topk_ids_equal'] and check['max_score_difference'] < 1e-6 and check['source_ids_equal'] and check['sources_equal_excluding_new_document_identity'] and check['verdict_before']==check['verdict_after']
                equivalence.append(check)
                checked(label+':restore_twice', client.post('/rag/local-cache/restore', content=blob, headers=auth_a2), 200)
                assert len(client.get('/rag/documents', headers=auth_a2).json()['documents']) == 1
                path = private_documents.directory(source_id)
                logout = client.post('/rag/session/logout', headers=auth_a)
                checked(label+':logout_purge', logout, 200)
                assert logout.json()['server_copies_removed'] and not path.exists()
                checked(label+':revoked_session_denied', client.get('/rag/documents', headers=auth_a), 401)
                checked(label+':other_session_survives', client.get(f'/rag/documents/{new_id}', headers=auth_a2), 200)
                # The same ciphertext restores for a fresh login after server purge.
                auth_again = login(a)
                again = client.post('/rag/local-cache/restore', content=blob, headers=auth_again)
                assert again.status_code == 200 and again.json()['document']['document_id'] != source_id
                for auth in [auth_a2, auth_again, auth_b]:
                    assert client.post('/rag/session/logout', headers=auth).json()['server_copies_removed']
                rows.append({'size':label, 'pages':pages, 'pdf_bytes':len(content), 'chunks':doc['chunks'],
                    'encrypted_bytes':len(blob), 'first_upload_seconds':upload_time, 'export_seconds':export_time,
                    'restore_seconds':restore_time, 'faiss_restore_seconds':restored['faiss_seconds'],
                    'preparation_saved_percent':100*(upload_time-restore_time)/upload_time,
                    'first_upload_calls':upload_counts, 'restore_calls':counts,
                    'first_question_seconds':first_question, 'restored_question_seconds':restored_question})
                print(json.dumps({'completed':label, 'counts':counts, 'saved_percent':rows[-1]['preparation_saved_percent']}), flush=True)
            with private_documents.db() as db:
                assert db.execute('SELECT COUNT(*) FROM documents WHERE owner IN (?,?)', (str(a['user_id']),str(b['user_id']))).fetchone()[0] == 0
    finally:
        for account in identities:
            with private_documents.db() as db:
                docs = [r[0] for r in db.execute('SELECT id FROM documents WHERE owner=?', (str(account['user_id']),))]
            for doc in docs: private_documents.purge(doc)
            users_collection.delete_one({'user_id':account['user_id'], 'email':account['email']})
        (ROOT/'reports/know_more_cache_performance.json').write_text(json.dumps({'model':'real MiniLM CUDA; real Qwen; warm resident services', 'fixtures':'generated realistic multi-page access-control study PDFs; no private user content', 'rows':rows, 'browser_storage_time':'measured separately in browser validation'}, indent=2), encoding='utf-8')
        (ROOT/'reports/know_more_cache_equivalence.json').write_text(json.dumps({'checks':equivalence,'pass':bool(equivalence) and all(c['pass'] for c in equivalence)}, indent=2),encoding='utf-8')
        (ROOT/'reports/know_more_cache_security.json').write_text(json.dumps({'live_http_checks':security,'pass':bool(security) and all(c['pass'] for c in security), 'disposable_accounts_removed':True},indent=2),encoding='utf-8')


if __name__ == '__main__': main()
