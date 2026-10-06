import json
import time
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from types import SimpleNamespace

import fitz
import numpy as np
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.dependencies import get_current_user
from rag.services import knowledge_algorithms as algorithms
from rag.services.knowledge_artifacts import KnowledgeArtifacts
from rag.services.knowledge_routes import install_knowledge_artifacts
from rag.services.local_document_cache import DIMENSION, LocalDocumentCache
from rag.services.private_document_routes import install_private_documents
from rag.services.private_documents import PrivateDocuments


class Model:
    calls = 0

    def encode(self, texts, **kwargs):
        self.calls += 1
        # No downloaded model is required to exercise the real extraction/chunk/index path.
        vectors = np.ones((len(texts), DIMENSION), dtype='float32')
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv('LUMINAR_SESSION_DB', str(tmp_path / 'sessions.sqlite'))
    model = Model()
    docs = PrivateDocuments(tmp_path / 'private', model, cache=LocalDocumentCache(b'K' * 32, enabled=True))
    user = {'sub': 'owner', 'sid': 'session1', 'exp': time.time() + 3600}
    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: user
    install_private_documents(app, docs, SimpleNamespace(inference_lock=RLock()))
    service = install_knowledge_artifacts(app, docs)
    client = TestClient(app)
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_textbox((40, 40, 500, 700),
        'Virtual memory is a memory-management technique that extends apparent main memory.\n'
        'Paging is a memory-management scheme that divides memory into fixed-size pages.\n'
        'Encryption refers to the process of converting readable information into encoded data.\n'
        'Encryption protects business records during transmission across public networks.')
    blob = pdf.tobytes(); pdf.close()
    response = client.post('/rag/upload', files={'file': ('manual.pdf', blob, 'application/pdf')})
    assert response.status_code == 200
    doc = response.json()['document']['document_id']
    return SimpleNamespace(docs=docs, service=service, app=app, client=client, user=user, doc=doc,
                           base=f'/rag/documents/{doc}', model=model, pdf=blob)


def test_pdf_upload_generate_persist_reopen_source_index_regression(env, monkeypatch):
    before = env.model.calls
    response = env.client.post(env.base + '/artifacts/flashcards', json={})
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    artifact = response.json()['artifact']
    cards = artifact['content']['cards']
    assert {'definition', 'cloze'} <= {c['type'] for c in cards}
    assert all(c['pageStart'] == 1 for c in cards)
    source = env.client.get(env.base + '/sources/' + cards[0]['sourceChunkIds'][0]).json()
    assert cards[0]['sourceExcerpt'] in source['text']
    reopened = KnowledgeArtifacts(env.docs)
    monkeypatch.setattr(algorithms, 'generate', lambda *args: pytest.fail('Compatible cache regenerated'))
    assert reopened.generate(env.doc, 'flashcards', env.user)['artifact']['id'] == artifact['id']
    assert env.client.get(env.base + '/artifacts/' + artifact['id']).json()['id'] == artifact['id']
    assert len(env.client.get(env.base + '/artifacts').json()['artifacts']) == 1
    assert env.model.calls == before
    import faiss
    index = faiss.read_index(str(env.docs.directory(env.doc) / 'runtime.faiss'))
    assert index.ntotal > 0
    assert env.client.get('/rag/documents').status_code == 200


def test_quiz_patch_version_does_not_reuse_previous_empty_result(env, monkeypatch):
    from pathlib import Path
    from rag.services import knowledge_quiz
    fixture = Path(__file__).parent/'fixtures/quiz_lecture_notes.json'
    (env.docs.directory(env.doc)/'chunks.json').write_bytes(fixture.read_bytes())
    with monkeypatch.context() as old:
        old.setattr(knowledge_quiz, 'VERSION', '2.0.0')
        old.setattr(algorithms, 'generate', lambda *args: {'questions': []})
        previous = env.client.post(env.base+'/artifacts/quiz', json={'questionTypes':['mcq']}).json()['artifact']
    result = env.client.post(env.base+'/artifacts/quiz', json={'questionTypes':['mcq']}).json()
    assert result['cached'] is False
    assert result['artifact']['id'] != previous['id']
    assert result['artifact']['generatorVersion'] == '2.1.0'
    assert result['artifact']['content']['questions']
    assert all(q['type'] == 'mcq' for q in result['artifact']['content']['questions'])
    replay = env.client.post(env.base+'/artifacts/quiz', json={'questionTypes':['mcq']}).json()
    assert replay['cached'] and replay['artifact']['id'] == result['artifact']['id']


@pytest.mark.parametrize('kind', ['key-concepts', 'summary', 'flashcards', 'mindmap', 'quiz'])
def test_all_routes(env, kind):
    response = env.client.post(env.base + '/artifacts/' + kind, json={})
    assert response.status_code == 200
    assert response.json()['cached'] is False
    assert env.client.post(env.base + '/artifacts/' + kind, json={}).json()['cached'] is True


@pytest.mark.parametrize('intruder', [
    {'sub': 'other', 'sid': 'other-session', 'exp': time.time() + 3600},
    {'sub': 'owner', 'sid': 'another-session', 'exp': time.time() + 3600},
    {'sub': 'owner', 'sid': 'session1', 'exp': 1},
])
def test_ownership_before_generation_read_delete_and_source(env, intruder):
    artifact = env.service.generate(env.doc, 'flashcards', env.user)['artifact']
    chunk = artifact['sourceChunkIds'][0]
    env.app.dependency_overrides[get_current_user] = lambda: intruder
    for method, path in [('post', '/artifacts/flashcards'), ('get', '/artifacts'),
                         ('get', '/artifacts/' + artifact['id']), ('delete', '/artifacts/' + artifact['id']),
                         ('get', '/sources/' + chunk)]:
        response = getattr(env.client, method)(env.base + path, **({'json': {}} if method == 'post' else {}))
        assert response.status_code in (401, 404)


def test_missing_bearer_and_input_validation(env):
    env.app.dependency_overrides.clear()
    assert env.client.get(env.base + '/artifacts').status_code in (401, 403)
    env.app.dependency_overrides[get_current_user] = lambda: env.user
    for payload in ({'mode': 'huge'}, {'scope': 'chapter'}, {'prompt': 'anything'}):
        assert env.client.post(env.base + '/artifacts/summary', json=payload).status_code == 422
    assert env.client.post(env.base + '/artifacts/unknown', json={}).status_code == 422


def test_cache_version_source_and_options_invalidation(env, monkeypatch):
    first = env.service.generate(env.doc, 'summary', env.user)['artifact']
    detailed = env.service.generate(env.doc, 'summary', env.user, 'detailed')['artifact']
    assert first['id'] != detailed['id']
    monkeypatch.setattr(algorithms, 'VERSION', '2.0.0')
    assert env.service.list(env.doc, env.user)['artifacts'] == []
    second = env.service.generate(env.doc, 'summary', env.user)['artifact']
    assert second['id'] != first['id']
    path = env.docs.directory(env.doc) / 'chunks.json'
    chunks = json.loads(path.read_text())
    chunks[0]['text'] += ' Compliance is a process for meeting documented organizational requirements.'
    path.write_text(json.dumps(chunks))
    assert env.service.list(env.doc, env.user)['artifacts'] == []
    third = env.service.generate(env.doc, 'summary', env.user)['artifact']
    assert third['id'] != second['id']


def test_delete_and_document_cleanup_cascade(env):
    artifact = env.service.generate(env.doc, 'quiz', env.user)['artifact']
    assert env.client.delete(env.base + '/artifacts/' + artifact['id']).status_code == 200
    assert env.service.list(env.doc, env.user)['artifacts'] == []
    env.service.generate(env.doc, 'flashcards', env.user)
    env.docs.purge(env.doc)
    with env.docs.db() as db:
        assert db.execute('SELECT COUNT(*) FROM knowledge_artifacts').fetchone()[0] == 0


def test_logout_during_generation_cannot_publish(env, monkeypatch):
    generate = algorithms.generate
    def logout_then_generate(*args):
        result = generate(*args)
        env.docs.logout(env.user)
        return result
    monkeypatch.setattr(algorithms, 'generate', logout_then_generate)
    with pytest.raises(HTTPException):
        env.service.generate(env.doc, 'flashcards', env.user)
    with env.docs.db() as db:
        assert db.execute('SELECT COUNT(*) FROM knowledge_artifacts').fetchone()[0] == 0


def test_concurrent_requests_share_persisted_result(env):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: env.service.generate(env.doc, 'flashcards', env.user), range(4)))
    assert len({r['artifact']['id'] for r in results}) == 1
    assert len(env.service.list(env.doc, env.user)['artifacts']) == 1


def test_missing_vectors_and_legacy_metadata(env):
    path = env.docs.directory(env.doc)
    (path / 'vectors.npy').unlink()
    chunks = json.loads((path / 'chunks.json').read_text())
    for chunk in chunks:
        chunk.pop('page', None)
    (path / 'chunks.json').write_text(json.dumps(chunks))
    artifact = env.service.generate(env.doc, 'flashcards', env.user)['artifact']
    assert artifact['content']['cards']
    assert all(c['pageStart'] is None for c in artifact['content']['cards'])


def test_damaged_source_and_missing_document_are_safe(env):
    (env.docs.directory(env.doc) / 'chunks.json').write_text('{}')
    assert env.client.post(env.base + '/artifacts/quiz', json={}).status_code == 409
    assert env.client.get('/rag/documents/doc_missing/artifacts').status_code == 404


def quiz_fixture(env):
    from pathlib import Path
    chunks = json.loads((Path(__file__).parent/'fixtures/quiz_study.json').read_text(encoding='utf-8'))
    (env.docs.directory(env.doc)/'chunks.json').write_text(json.dumps(chunks), encoding='utf-8')


@pytest.mark.parametrize('selection', [
    ['mcq'], ['fill_blank'], ['matching'], ['mcq','fill_blank'], ['mcq','matching'],
    ['fill_blank','matching'], ['mcq','fill_blank','matching'],
])
def test_quiz_selected_types_real_route_and_cache(env, selection):
    quiz_fixture(env)
    before = env.model.calls
    body = {'questionTypes': selection, 'questionCount': 10}
    first = env.client.post(env.base+'/artifacts/quiz', json=body)
    assert first.status_code == 200 and first.headers['cache-control'] == 'no-store'
    artifact = first.json()['artifact']
    assert artifact['generator'] == 'deterministic-v2' and artifact['generatorVersion'] == '2.1.0'
    assert artifact['options']['questionTypes'] == sorted(selection)
    assert {q['type'] for q in artifact['content']['questions']} == set(selection)
    assert env.model.calls == before
    second = env.client.post(env.base+'/artifacts/quiz', json={**body,'questionTypes':list(reversed(selection))}).json()
    assert second['cached'] and second['artifact']['id'] == artifact['id']
    assert env.client.get(env.base+'/artifacts/'+artifact['id']).status_code == 200
    source = env.client.get(env.base+'/sources/'+artifact['sourceChunkIds'][0])
    assert source.status_code == 200


@pytest.mark.parametrize('payload', [
    {'questionTypes':[]}, {'questionTypes':['unknown']}, {'questionTypes':'mcq'},
    {'questionTypes':None}, {'questionCount':0}, {'questionCount':31}, {'questionCount':True},
    {'questionCount':'10'}, {'questionTypes':['mcq'], 'scope':'chapter'},
])
def test_quiz_request_validation(env, payload):
    assert env.client.post(env.base+'/artifacts/quiz', json=payload).status_code == 422


def test_quiz_cache_selection_count_version_and_non_quiz_preservation(env, monkeypatch):
    from rag.services import knowledge_quiz
    quiz_fixture(env)
    summary = env.service.generate(env.doc,'summary',env.user)['artifact']
    blank = env.service.generate(env.doc,'quiz',env.user,question_types=['fill_blank'])['artifact']
    mcq = env.service.generate(env.doc,'quiz',env.user,question_types=['mcq'])['artifact']
    mixed = env.service.generate(env.doc,'quiz',env.user,question_types=['mcq','fill_blank'])['artifact']
    fewer = env.service.generate(env.doc,'quiz',env.user,question_types=['mcq'],question_count=5)['artifact']
    assert len({a['id'] for a in (blank,mcq,mixed,fewer)}) == 4
    assert env.service.generate(env.doc,'quiz',env.user,question_types=['fill_blank','mcq'])['artifact']['id'] == mixed['id']
    monkeypatch.setattr(knowledge_quiz,'VERSION','9.0.0')
    assert env.service.generate(env.doc,'quiz',env.user,question_types=['mcq'])['artifact']['id'] != mcq['id']
    assert env.service.generate(env.doc,'summary',env.user)['artifact']['id'] == summary['id']
    assert summary['generatorVersion'] == '1.0.0'


def test_legacy_quiz_remains_readable_but_cannot_satisfy_a_new_selection(env):
    quiz_fixture(env)
    artifact = env.service.generate(env.doc,'quiz',env.user)['artifact']
    artifact.update(id='legacy_quiz',generator='deterministic-v1',generatorVersion='1.0.0',options={})
    artifact['content'] = algorithms.quiz(algorithms.generate('FLASHCARDS',
        json.loads((env.docs.directory(env.doc)/'chunks.json').read_text()),'Manual',{})['cards'])
    with env.docs.db() as db:
        db.execute('DELETE FROM knowledge_artifacts WHERE document_id=?',(env.doc,))
        db.execute('INSERT INTO knowledge_artifacts VALUES (?,?,?,?,?,?,?)',
            (artifact['id'],env.doc,env.user['sub'],'QUIZ','legacy-key',json.dumps(artifact),time.time()))
    assert env.client.get(env.base+'/artifacts/legacy_quiz').json()['id'] == 'legacy_quiz'
    new = env.client.post(env.base+'/artifacts/quiz',json={'questionTypes':['mcq','matching']}).json()
    assert not new['cached'] and new['artifact']['id'] != 'legacy_quiz'
    assert {q['type'] for q in new['artifact']['content']['questions']} == {'mcq','matching'}
    assert env.client.post(env.base+'/artifacts/quiz',json={}).status_code == 200


def test_quiz_security_and_direct_service_validation(env):
    with pytest.raises(HTTPException) as error:
        env.service.generate(env.doc,'quiz',env.user,question_types=[])
    assert error.value.status_code == 422
    env.app.dependency_overrides[get_current_user] = lambda: {**env.user, 'sub':'intruder'}
    assert env.client.post(env.base+'/artifacts/quiz',json={'questionTypes':['mcq']}).status_code == 404
    env.app.dependency_overrides.clear()
    assert env.client.post(env.base+'/artifacts/quiz',json={'questionTypes':['mcq']}).status_code in (401,403)


def test_quiz_fields_do_not_change_other_artifact_requests(env):
    assert env.client.post(env.base+'/artifacts/flashcards',json={'questionTypes':['mcq']}).status_code == 422
    assert env.client.post(env.base+'/artifacts/flashcards',json={}).status_code == 200
