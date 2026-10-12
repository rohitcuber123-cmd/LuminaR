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
    service = install_knowledge_artifacts(app, docs, encoder=model.encode)
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
    assert 'definition' in {c['type'] for c in cards}
    assert len({c['sourceExcerpt'] for c in cards}) == len(cards)
    assert all(c['pageStart'] == 1 for c in cards)
    source = env.client.get(env.base + '/sources/' + cards[0]['sourceChunkIds'][0]).json()
    assert cards[0]['sourceExcerpt'] in source['text']
    reopened = KnowledgeArtifacts(env.docs)
    monkeypatch.setattr(algorithms, 'generate', lambda *args: pytest.fail('Compatible cache regenerated'))
    assert reopened.generate(env.doc, 'flashcards', env.user)['artifact']['id'] == artifact['id']
    assert env.client.get(env.base + '/artifacts/' + artifact['id']).json()['id'] == artifact['id']
    assert len(env.client.get(env.base + '/artifacts').json()['artifacts']) == 1
    assert env.model.calls == before + 1
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
    assert result['artifact']['generatorVersion'] == '3.2.2'
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
    assert artifact['generator'] == 'document-knowledge-v3' and artifact['generatorVersion'] == '3.2.2'
    assert artifact['options']['questionTypes'] == sorted(selection)
    assert {q['type'] for q in artifact['content']['questions']} == set(selection)
    assert env.model.calls == before + 1
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
    assert summary['generatorVersion'] == '3.0.0'


def test_obsolete_quiz_is_hidden_and_cannot_satisfy_a_new_selection(env):
    quiz_fixture(env)
    artifact = env.service.generate(env.doc,'quiz',env.user)['artifact']
    artifact.update(id='legacy_quiz',generator='deterministic-v1',generatorVersion='1.0.0',options={})
    artifact['content'] = algorithms.quiz(algorithms.generate('FLASHCARDS',
        json.loads((env.docs.directory(env.doc)/'chunks.json').read_text()),'Manual',{})['cards'])
    with env.docs.db() as db:
        db.execute('DELETE FROM knowledge_artifacts WHERE document_id=?',(env.doc,))
        db.execute('INSERT INTO knowledge_artifacts VALUES (?,?,?,?,?,?,?)',
            (artifact['id'],env.doc,env.user['sub'],'QUIZ','legacy-key',json.dumps(artifact),time.time()))
    assert env.client.get(env.base+'/artifacts/legacy_quiz').status_code == 404
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


def test_shared_model_parses_and_embeds_once_across_all_five_tabs(env, monkeypatch):
    calls = []
    parse = env.service._parse
    monkeypatch.setattr(env.service, '_parse', lambda raw: (calls.append(1), parse(raw))[1])
    before = env.model.calls
    for kind in ('key-concepts','summary','flashcards','mindmap','quiz'):
        result = env.service.generate(env.doc, kind, env.user)
        assert result['artifact']['analysis']['knowledgeCached'] == (kind != 'key-concepts')
    assert len(calls) == 1 and env.model.calls == before + 1


def test_document_purge_removes_model_and_artifacts(env):
    env.service.generate(env.doc,'key-concepts',env.user)
    env.docs.purge(env.doc)
    with env.docs.db() as db:
        assert db.execute('SELECT COUNT(*) FROM document_knowledge').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM knowledge_artifacts').fetchone()[0] == 0


def test_logout_removes_shared_model_and_cannot_reopen_it(env):
    env.service.generate(env.doc,'key-concepts',env.user)
    env.docs.logout(env.user)
    with env.docs.db() as db:
        assert db.execute('SELECT COUNT(*) FROM document_knowledge').fetchone()[0] == 0
    with pytest.raises(HTTPException):
        KnowledgeArtifacts(env.docs).generate(env.doc,'summary',env.user)


def test_revision_and_knowledge_version_invalidate_model(env, monkeypatch):
    from rag.services import document_knowledge
    env.service.generate(env.doc,'summary',env.user)
    before = env.model.calls
    path = env.docs.directory(env.doc)/'chunks.json'
    chunks = json.loads(path.read_text())
    chunks[0]['text'] += ' Compression is a coding method that reduces stored data size using repeated patterns.'
    path.write_text(json.dumps(chunks))
    env.service.generate(env.doc,'summary',env.user)
    assert env.model.calls == before + 1
    monkeypatch.setattr(document_knowledge,'VERSION','9.1.0')
    env.service.generate(env.doc,'flashcards',env.user)
    assert env.model.calls == before + 2


def test_reopened_service_uses_session_model_without_reparsing(env, monkeypatch):
    env.service.generate(env.doc,'key-concepts',env.user)
    reopened = KnowledgeArtifacts(env.docs, encoder=lambda _: pytest.fail('re-embedded'))
    monkeypatch.setattr(reopened,'_parse',lambda _: pytest.fail('reparsed'))
    assert reopened.generate(env.doc,'mindmap',env.user)['artifact']['analysis']['knowledgeCached']


def test_per_user_admission_rejects_extra_work_but_allows_another_user(env, monkeypatch):
    from threading import Event
    other = {**env.user,'sub':'other','sid':'other-session'}
    env.app.dependency_overrides[get_current_user] = lambda: other
    second = env.client.post('/rag/upload',files={'file':('other.pdf',env.pdf,'application/pdf')}).json()['document']['document_id']
    entered, release = Event(), Event()
    original = env.service._generate
    def blocked(document_id,*args):
        if document_id == env.doc:
            entered.set()
            assert release.wait(10)
        return original(document_id,*args)
    monkeypatch.setattr(env.service,'_generate',blocked)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(env.service.generate,env.doc,'key-concepts',env.user)
        assert entered.wait(5)
        try:
            with pytest.raises(HTTPException) as error:
                env.service.generate(env.doc,'summary',env.user)
            assert error.value.status_code == 429
            assert env.service.generate(second,'summary',other)['artifact']['documentId'] == second
        finally:
            release.set()
        assert first.result()['artifact']['documentId'] == env.doc
