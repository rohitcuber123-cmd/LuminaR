import io
import json
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from types import SimpleNamespace

import fitz
import numpy as np
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.dependencies import get_current_user
from rag.services.local_document_cache import LocalDocumentCache, canonical, DIMENSION
from rag.services.private_documents import PrivateDocuments
from rag.services.private_document_routes import install_private_documents


class Model:
    def __init__(self): self.calls = 0
    def encode(self, texts, **kwargs):
        self.calls += 1
        vectors = np.random.default_rng(42).normal(size=(len(texts), DIMENSION)).astype('float32')
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv('LUMINAR_SESSION_DB', str(tmp_path / 'sessions.sqlite'))
    cache = LocalDocumentCache(b'K' * 32, enabled=True)
    retriever = SimpleNamespace(doc_index=None, doc_metadata=[], doc_ids=set(), doc_chunk_texts={})
    model = Model()
    service = PrivateDocuments(tmp_path / 'private', model, retriever, cache=cache)
    a = {'sub': '1', 'sid': 'session-a', 'exp': time.time()+3600}
    b = {'sub': '2', 'sid': 'session-b', 'exp': time.time()+3600}
    a2 = {**a, 'sid': 'session-a2'}
    pdf = fitz.open(); page = pdf.new_page()
    page.insert_text((50, 50), 'Private sample: role-based access control assigns privileges to roles.')
    content = pdf.tobytes(); pdf.close()
    doc = service.ingest(content, 'private.pdf', a)
    blob, metadata = service.export(doc['document_id'], a)
    return SimpleNamespace(service=service, cache=cache, a=a, b=b, a2=a2, content=content,
                           doc=doc, blob=blob, metadata=metadata, model=model, retriever=retriever)


@pytest.mark.parametrize('user', ['b', 'a2'])
@pytest.mark.parametrize('operation', ['owned', 'export', 'prepared'])
def test_active_owner_and_session_private_404(env, user, operation):
    with pytest.raises(HTTPException) as exc:
        getattr(env.service, operation)(env.doc['document_id'], getattr(env, user))
    assert exc.value.status_code == 404
    assert env.service.list(getattr(env, user)) == []


@pytest.mark.parametrize('user', [None, {}, {'sub': '1', 'exp': 99999999999}, {'sub': '1', 'sid': 'expired', 'exp': 1}])
def test_upload_restore_export_require_current_session(env, user):
    for action in [lambda: env.service.ingest(env.content, 'a.pdf', user),
                   lambda: env.service.export(env.doc['document_id'], user), lambda: env.service.restore(env.blob, user)]:
        with pytest.raises(HTTPException) as exc: action()
        assert exc.value.status_code == 401


def test_ciphertext_contains_no_content_filename_or_key(env):
    assert b'Private sample' not in env.blob and b'private.pdf' not in env.blob and b'K'*32 not in env.blob
    assert 'private.pdf' not in env.metadata['encrypted_descriptor']
    assert set(env.metadata) == {'cache_id', 'owner_scope_id', 'encrypted_descriptor', 'format_version', 'blob_size'}
    assert env.cache.inspect('1', env.metadata['encrypted_descriptor'])['filename'] == 'private.pdf'
    assert env.cache.scope('1') != env.cache.scope('2')


def test_cross_account_descriptor_and_bundle_rejected(env):
    for action in [lambda: env.cache.inspect('2', env.metadata['encrypted_descriptor']), lambda: env.service.restore(env.blob, env.b)]:
        with pytest.raises(HTTPException) as exc: action()
        assert exc.value.detail['code'] == 'INVALID_LOCAL_CACHE'
    assert env.service.list(env.b) == []


@pytest.mark.parametrize('alter', ['tag', 'truncate', 'ciphertext', 'header', 'magic'])
def test_modified_ciphertext_rejected(env, alter):
    blob = bytearray(env.blob)
    if alter == 'truncate': blob = blob[:-20]
    else: blob[{'tag': -1, 'ciphertext': -25, 'header': 30, 'magic': 0}[alter]] ^= 1
    with pytest.raises(HTTPException): env.service.restore(bytes(blob), env.a2)
    assert env.service.list(env.a2) == []


def test_old_key_and_pipeline_incompatible(env):
    env.cache.version = 2
    with pytest.raises(HTTPException) as exc: env.service.restore(env.blob, env.a2)
    assert exc.value.detail['code'] == 'CACHE_INCOMPATIBLE'


def mutate_bundle(env, mutation):
    _, plain = env.cache.decrypt('1', env.blob, 'bundle')
    with zipfile.ZipFile(io.BytesIO(plain)) as z:
        entries = {name: z.read(name) for name in z.namelist()}
    manifest = json.loads(entries['manifest.json'])
    mutation(entries, manifest)
    import hashlib
    manifest['checksums'] = {name: hashlib.sha256(data).hexdigest() for name, data in entries.items() if name != 'manifest.json'}
    entries['manifest.json'] = canonical(manifest)
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as z:
        for name, data in entries.items(): z.writestr(name, data)
    return output.getvalue()


@pytest.mark.parametrize('kind', ['dimension', 'rank', 'count', 'dtype', 'object', 'nan', 'inf', 'norm'])
def test_vector_validation_before_publish(env, kind):
    def mutate(entries, manifest):
        vectors = np.load(io.BytesIO(entries['embeddings.npy']), allow_pickle=False)
        if kind == 'dimension': vectors = vectors[:, :3]
        if kind == 'rank': vectors = vectors[0]
        if kind == 'count': vectors = np.concatenate([vectors, vectors])
        if kind == 'dtype': vectors = vectors.astype('float16')
        if kind == 'object': vectors = vectors.astype(object)
        if kind == 'nan': vectors[0, 0] = np.nan
        if kind == 'inf': vectors[0, 0] = np.inf
        if kind == 'norm': vectors *= 2
        out = io.BytesIO(); np.save(out, vectors, allow_pickle=True)
        entries['embeddings.npy'] = out.getvalue()
    plain = mutate_bundle(env, mutate)
    with pytest.raises(HTTPException): env.cache.unpack(plain, env.metadata['cache_id'])
    assert env.service.list(env.a2) == []


@pytest.mark.parametrize('kind', ['fingerprint', 'format', 'map', 'chunks', 'sha', 'count'])
def test_manifest_source_map_and_chunks_verified(env, kind):
    def mutate(entries, manifest):
        if kind == 'fingerprint': manifest['pipeline_fingerprint'] = 'bad'
        if kind == 'format': manifest['format_version'] = 9
        if kind == 'map': entries['source_map.json'] = b'[]'
        if kind == 'chunks': entries['chunks.json'] = b'{}'
        if kind == 'sha': manifest['document_sha256'] = 'invalid'
        if kind == 'count': manifest['chunk_count'] = 999
    with pytest.raises(HTTPException): env.cache.unpack(mutate_bundle(env, mutate), env.metadata['cache_id'])


@pytest.mark.parametrize('kind', ['unknown', 'traversal', 'absolute', 'duplicate', 'missing', 'bomb', 'invalid'])
def test_archive_bounds_and_paths(env, kind):
    _, plain = env.cache.decrypt('1', env.blob, 'bundle')
    with zipfile.ZipFile(io.BytesIO(plain)) as z: entries = {name: z.read(name) for name in z.namelist()}
    if kind == 'unknown': entries['extra.bin'] = b'a'
    if kind == 'traversal': entries['../manifest.json'] = entries.pop('manifest.json')
    if kind == 'absolute': entries['/manifest.json'] = entries.pop('manifest.json')
    if kind == 'missing': entries.pop('source_map.json')
    if kind == 'bomb': entries['chunks.json'] = b'0' * 1000000
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED if kind == 'bomb' else zipfile.ZIP_STORED) as z:
        for name, data in entries.items(): z.writestr(name, data)
        if kind == 'duplicate': z.writestr('manifest.json', entries['manifest.json'])
    with pytest.raises(HTTPException): env.cache.unpack(b'invalid' if kind == 'invalid' else out.getvalue(), env.metadata['cache_id'])


def test_restore_zero_processing_new_identity_equivalent_vectors_sources(env, monkeypatch):
    before = env.service.metrics.copy(), env.model.calls
    row, chunks, vectors = env.service.prepared(env.doc['document_id'], env.a)
    for name in ['extract_pdf', 'create_chunks', 'embed_chunks']:
        monkeypatch.setattr(env.service.processor, name, lambda *args: pytest.fail('Restore repeated processing'))
    restored = env.service.restore(env.blob, env.a2)
    assert restored['document_id'] != env.doc['document_id']
    restored_row, restored_chunks, restored_vectors = env.service.prepared(restored['document_id'], env.a2)
    assert restored_row['owner'] == '1' and restored_row['sid'] == env.a2['sid']
    assert [(c['chunk_id'], c['page'], c['text']) for c in chunks] == [(c['chunk_id'], c['page'], c['text']) for c in restored_chunks]
    np.testing.assert_array_equal(vectors, restored_vectors)
    import faiss
    original_index = faiss.read_index(str(env.service.directory(env.doc['document_id']) / 'runtime.faiss'))
    restored_index = faiss.read_index(str(env.service.directory(restored['document_id']) / 'runtime.faiss'))
    for v in vectors:
        s1, i1 = original_index.search(v[None], 5); s2, i2 = restored_index.search(v[None], 5)
        np.testing.assert_array_equal(i1, i2); np.testing.assert_allclose(s1, s2, atol=1e-7)
    assert before[1] == env.model.calls
    for key in ['parse_calls', 'chunk_calls', 'embedding_calls']: assert before[0][key] == env.service.metrics[key]
    assert env.service.restore(env.blob, env.a2)['document_id'] == restored['document_id']


def test_logout_all_artifacts_gone_other_session_survives_and_blob_remains(env):
    other = env.service.restore(env.blob, env.a2)
    path = env.service.directory(env.doc['document_id'])
    assert {'chunks.json', 'vectors.npy', 'runtime.faiss', 'extracted.json'} <= {p.name for p in path.iterdir()}
    result = env.service.logout(env.a)
    assert result == {'purged': 1, 'pending': 0, 'server_copies_removed': True}
    assert not path.exists()
    with env.service.db() as db: assert db.execute('SELECT 1 FROM documents WHERE id=?', (env.doc['document_id'],)).fetchone() is None
    assert env.service.owned(other['document_id'], env.a2)
    assert env.cache.inspect('1', env.metadata['encrypted_descriptor'])
    env.service.purge(env.doc['document_id']); env.service.purge(env.doc['document_id'])
    assert env.retriever.doc_ids == set() and env.retriever.doc_index is None


def test_cleanup_failure_disables_access_and_sweeper_retries(env, monkeypatch):
    import rag.services.private_documents as module
    original = module.shutil.rmtree
    monkeypatch.setattr(module.shutil, 'rmtree', lambda *args: (_ for _ in ()).throw(OSError('busy')))
    assert not env.service.purge(env.doc['document_id'])
    with pytest.raises(HTTPException) as exc: env.service.owned(env.doc['document_id'], env.a)
    assert exc.value.status_code == 404
    monkeypatch.setattr(module.shutil, 'rmtree', original)
    env.service.sweep()
    assert not env.service.directory(env.doc['document_id']).exists()


def test_expiry_sweeper_removes_artifacts(env):
    with env.service.db() as db: db.execute('UPDATE documents SET expires=1')
    assert env.service.list(env.a) == []
    env.service.sweep()
    assert not env.service.directory(env.doc['document_id']).exists()


def test_selected_runtime_only_and_clears_on_error(env):
    with pytest.raises(RuntimeError):
        with env.service.selected(env.doc['document_id'], env.a):
            assert env.retriever.doc_ids == {env.doc['document_id']}
            raise RuntimeError('Question failed')
    assert env.retriever.doc_ids == set() and env.retriever.doc_chunk_texts == {}


def test_logout_during_ingestion_cannot_publish(env, monkeypatch):
    from backend.services.login_sessions import revoke
    original = env.service.processor.embed_chunks
    def embed(chunks): revoke(env.a2); return original(chunks)
    monkeypatch.setattr(env.service.processor, 'embed_chunks', embed)
    with pytest.raises(HTTPException): env.service.ingest(env.content, 'test.pdf', env.a2)
    with env.service.db() as db: assert db.execute('SELECT 1 FROM documents WHERE sid=?', (env.a2['sid'],)).fetchone() is None


def test_http_auth_bounds_idempotent_concurrent_restore(env):
    app = FastAPI(); engine = SimpleNamespace(inference_lock=RLock())
    install_private_documents(app, env.service, engine)
    client = TestClient(app)
    assert client.post(f"/rag/documents/{env.doc['document_id']}/cache/export").status_code in [401, 403]
    app.dependency_overrides[get_current_user] = lambda: env.a2
    assert client.post(f"/rag/documents/{env.doc['document_id']}/cache/export").status_code == 404
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: client.post('/rag/local-cache/restore', content=env.blob).json(), range(2)))
    assert results[0]['document']['document_id'] == results[1]['document']['document_id']
    assert client.post('/rag/local-cache/inspect', json={'descriptors': ['x'] * 21}).status_code == 422
    app.dependency_overrides[get_current_user] = lambda: env.b
    assert client.post('/rag/local-cache/restore', content=env.blob).status_code == 400


def test_feature_flag_no_master_no_cache(env):
    cache = LocalDocumentCache(b'', enabled=False)
    with pytest.raises(HTTPException): cache.scope('1')
    with pytest.raises(RuntimeError): LocalDocumentCache(b'', enabled=True)


def test_no_unsafe_deserializer_or_server_cache_archive():
    from pathlib import Path
    source = Path('rag/services/local_document_cache.py').read_text(encoding='utf-8')
    assert 'allow_pickle=False' in source
    for unsafe in ['pickle.load', 'torch.load', 'joblib.load', 'extractall']:
        assert unsafe not in source


def test_real_http_ask_adapter_private_global_book_and_failure_boundaries(env):
    # Execute the actual HTTP adapter without instantiating another Qwen model.
    import ast
    import contextlib
    from pathlib import Path
    from fastapi import Depends
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from pydantic import BaseModel, model_validator
    tree = ast.parse(Path('rag/api.py').read_text(encoding='utf-8'))
    module = ast.Module(body=[n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in {'RAGRequest', 'ask'}], type_ignores=[])
    observations = []
    def model_ask(**kwargs):
        observations.append(set(env.retriever.doc_ids))
        if kwargs['question'] == 'fail': raise RuntimeError('test failure')
        return {'sources': [{'work_id': c['document_id']} for c in env.retriever.doc_metadata], 'answer': 'Grounded'}
    engine = SimpleNamespace(inference_lock=RLock(), reranker=SimpleNamespace(retriever=env.retriever), ask=model_ask)
    namespace = {'app': FastAPI(), 'BaseModel': BaseModel, 'model_validator': model_validator, 'Depends': Depends,
                 'HTTPException': HTTPException, 'HTTPAuthorizationCredentials': HTTPAuthorizationCredentials,
                 'optional_auth': HTTPBearer(auto_error=False), 'engine': engine, 'private_documents': env.service,
                 'contextlib': contextlib, 'valid_work_id': lambda value: value.startswith('OL'),
                 'authorize_selection': lambda document_id, work_id, credentials, document_ids: work_id or document_id,
                 'get_current_user': lambda credentials: {'a': env.a, 'b': env.b, 'a2': env.a2}[credentials.credentials],
                 'book_runtime': SimpleNamespace(refresh=lambda: None)}
    exec(compile(module, 'rag/api.py', 'exec'), namespace)
    request, ask = namespace['RAGRequest'], namespace['ask']
    creds = lambda value: HTTPAuthorizationCredentials(scheme='Bearer', credentials=value)
    for value in ['b', 'a2']:
        with pytest.raises(HTTPException) as exc: ask(request(query='Question', document_id=env.doc['document_id']), creds(value))
        assert exc.value.status_code == 404
    with pytest.raises(HTTPException) as exc: ask(request(query='Question', document_id=env.doc['document_id']), None)
    assert exc.value.status_code == 401
    own = ask(request(query='Question', document_id=env.doc['document_id']), creds('a'))
    assert own['sources'] and all(s['work_id'] == env.doc['document_id'] for s in own['sources'])
    assert ask(request(query='Global'), None)['sources'] == []
    assert ask(request(query='Book', work_id='OL1W'), creds('a'))['sources'] == []
    with pytest.raises(HTTPException): ask(request(query='fail', document_id=env.doc['document_id']), creds('a'))
    assert env.retriever.doc_ids == set()


def test_safe_aggregate_metrics_and_logs(env, caplog):
    import logging
    caplog.set_level(logging.INFO, logger='uvicorn.error')
    with pytest.raises(HTTPException): env.service.restore(env.blob, env.b)
    env.cache.version = 2
    with pytest.raises(HTTPException): env.service.restore(env.blob, env.a2)
    env.cache.version = 1
    restored = env.service.restore(env.blob, env.a2)
    assert env.cache.metrics['failures_by_code'] == {'INVALID_LOCAL_CACHE': 1, 'CACHE_INCOMPATIBLE': 1}
    assert env.cache.metrics['pipeline_incompatibilities'] == 1
    assert env.cache.metrics['average_encrypted_bytes'] == len(env.blob)
    assert env.service.metrics['restore_seconds_total'] > 0
    assert restored['document_id'] in caplog.text
    assert 'private.pdf' not in caplog.text and 'Private sample' not in caplog.text
    assert str(env.cache.master) not in caplog.text
