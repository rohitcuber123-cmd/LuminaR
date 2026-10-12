"""Real tenant authorization/storage/PDF/FAISS with a bounded deterministic model.

Generation is deliberately observed through a resident-engine double; these
tests verify which private chunks reach it, rather than mocking authorization.
"""
import hashlib
import json
from threading import RLock
from types import SimpleNamespace
from uuid import uuid4

import fitz
import numpy as np
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from backend.dependencies import get_current_user
from backend.schemas.library_assets import AssetUpdate
from backend.services import library_asset_service as repository
from rag.services import library_asset_pipeline as pipeline_module
from rag.services.library_asset_pipeline import LibraryAssetPipeline, safe_child
from rag.services.library_asset_routes import install_library_assets
from rag.services.local_document_cache import DIMENSION


TEXT = ('Virtual memory is a memory-management technique that extends apparent main memory.\n'
        'Paging is a memory-management scheme that divides memory into fixed-size pages.\n'
        'Encryption refers to converting readable information into encoded data.\n'
        'Encryption protects business records during transmission across public networks.\n')


class Model:
    def encode(self, texts, **kwargs):
        vectors = np.ones((len(texts), DIMENSION), dtype='float32')
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


class Engine:
    def __init__(self):
        self.model = Model()
        self.reranker = SimpleNamespace(retriever=SimpleNamespace(model=self.model, doc_index=None,
            doc_metadata=[], doc_ids=set(), doc_chunk_texts={}))
        self.inference_lock = RLock()
        self.calls = []
        self.callback = None
        self.cache_clears = 0
        self._document_latency = SimpleNamespace(clear_cache=self.clear_cache)

    def clear_cache(self):
        self.cache_clears += 1

    def ask(self, **request):
        retriever = self.reranker.retriever
        metadata = retriever.doc_metadata
        self.calls.append((request, [dict(row) for row in metadata], dict(retriever.doc_chunk_texts)))
        if self.callback:
            self.callback()
        return {'answer': 'Source-derived test answer.', 'sources': [
            {'chunk_id': row['chunk_id'], 'filename': row['filename'], 'page': row['page']}
            for row in metadata], 'verdict': 'SUPPORTED', 'depth': request['depth']}


@pytest.fixture
def pipeline_env(library, database, tmp_path, monkeypatch):
    monkeypatch.setenv('LIBRARY_ASSET_ROOT', str(tmp_path / 'library-assets'))
    monkeypatch.setenv('LIBRARY_ASSET_WORKER_ENABLED', '0')
    lib = library(owner=1)
    other = library(owner=2)
    for library_id, user, role in [(lib, 3, 'GENERAL_USER'), (lib, 4, 'LIBRARIAN'),
                                    (other, 3, 'GENERAL_USER')]:
        database.institution_memberships.insert_one({'membership_id': str(uuid4()),
            'library_id': library_id, 'user_id': user, 'status': 'ACTIVE', 'role': role})
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_textbox((40, 40, 500, 700), TEXT)
    content = pdf.tobytes()
    pdf.close()
    engine = Engine()
    service = LibraryAssetPipeline(engine, encoder=engine.model.encode)

    def upload(library_id=lib, owner=1, visibility='MEMBERS', content_override=None, process=True):
        row = repository.upload(library_id, {'sub': str(owner)}, content_override or content,
            'manual.pdf', 'Library course notes', visibility, None, str(uuid4()))
        if process:
            assert service.run_one()
            row = repository.authorize_asset(library_id, row['asset_id'], {'sub': str(owner)}, ready=True)
        return row

    row = upload()
    app = FastAPI()

    def actor(request: Request):
        return {'sub': request.headers.get('x-test-user', '1')}

    app.dependency_overrides[get_current_user] = actor
    install_library_assets(app, engine, service)
    return SimpleNamespace(lib=lib, other=other, row=row, engine=engine, service=service,
        database=database, content=content, upload=upload, client=TestClient(app),
        base=f'/libraries/{lib}/assets/{row["asset_id"]}', tmp_path=tmp_path)


def test_authorized_member_rag(pipeline_env):
    env = pipeline_env
    result = env.client.post(env.base + '/rag', headers={'x-test-user': '3'}, json={'query': 'What is virtual memory?'})
    assert result.status_code == 200, result.text
    assert result.headers['cache-control'] == 'no-store'
    assert result.json()['asset_id'] == env.row['asset_id']
    request, metadata, texts = env.engine.calls[-1]
    assert request['document_id'].startswith('library:' + env.lib)
    assert metadata and all(m['library_id'] == env.lib and m['asset_id'] == env.row['asset_id'] for m in metadata)
    assert any('Virtual memory' in value for value in texts.values())
    assert all(s['library_id'] == env.lib for s in result.json()['sources'])
    assert env.engine.reranker.retriever.doc_index is None
    assert env.engine.reranker.retriever.doc_ids == set()
    assert env.engine.cache_clears == 2


def test_staff_only_rag_denied_to_patron(pipeline_env):
    env = pipeline_env
    repository.update(env.lib, env.row['asset_id'], {'sub': '1'}, AssetUpdate(visibility='STAFF_ONLY'))
    result = env.client.post(env.base + '/rag', headers={'x-test-user': '3'}, json={'query': 'Explain memory.'})
    assert result.status_code == 404 and not env.engine.calls
    assert env.client.post(env.base + '/rag', headers={'x-test-user': '4'}, json={'query': 'Explain memory.'}).status_code == 200


def test_cross_library_rag_denied(pipeline_env):
    env = pipeline_env
    guessed = f'/libraries/{env.other}/assets/{env.row["asset_id"]}/rag'
    result = env.client.post(guessed, headers={'x-test-user': '3'}, json={'query': 'Use Library A PDF.'})
    assert result.status_code == 404 and not env.engine.calls


def test_asset_uuid_guess_denied_before_retrieval(pipeline_env, monkeypatch):
    env = pipeline_env
    monkeypatch.setattr(pipeline_module.faiss, 'read_index', lambda *_: pytest.fail('Unauthorized index opened'))
    monkeypatch.setattr(pipeline_module, 'digest', lambda *_: pytest.fail('Unauthorized artifact read'))
    result = env.client.post(env.base + '/rag', headers={'x-test-user': '2'}, json={'query': 'Guess document.'})
    assert result.status_code == 404 and not env.engine.calls


def test_rag_chunk_metadata_contains_library_asset(pipeline_env):
    env = pipeline_env
    chunks = json.loads((repository.artifacts_path(env.row) / 'chunks.json').read_text())
    for chunk in chunks:
        assert chunk['library_id'] == env.lib and chunk['asset_id'] == env.row['asset_id']
        assert chunk['generation_id'] == env.row['active_generation_id']
        assert chunk['page'] == 1 and chunk['source_start'] >= 0 and chunk['source_end'] > chunk['source_start']
        assert chunk['extraction_method'] == 'NATIVE'
        assert chunk['chunk_id'].startswith('library:' + env.lib + ':asset:' + env.row['asset_id'])


def test_identical_document_cache_tenant_isolated(pipeline_env):
    env = pipeline_env
    other = env.upload(library_id=env.other, owner=2)
    a = env.service.generate(env.lib, env.row['asset_id'], {'sub': '3'}, 'summary')['artifact']
    b = env.service.generate(env.other, other['asset_id'], {'sub': '3'}, 'summary')['artifact']
    assert other['checksum'] == env.row['checksum'] and other['asset_id'] != env.row['asset_id']
    assert a['id'] != b['id'] and a['libraryId'] != b['libraryId'] and a['sourceChunkIds'] != b['sourceChunkIds']
    assert repository.artifacts_path(other) != repository.artifacts_path(env.row)
    for row in [env.row, other]:
        response = env.service.ask(row['library_id'], row['asset_id'], {'sub': '3'}, 'What is virtual memory?')
        assert all(source['asset_id'] == row['asset_id'] for source in response['sources'])
    assert env.engine.calls[0][0]['document_id'] != env.engine.calls[1][0]['document_id']


def test_library_asset_not_in_global_hnsw(pipeline_env, monkeypatch):
    env = pipeline_env
    for method in ('save_extraction', 'save_chunks', 'update_index'):
        if hasattr(env.service.processor, method):
            monkeypatch.setattr(env.service.processor, method, lambda *_: pytest.fail('Legacy/global mutation called'))
    before = env.engine.reranker.retriever.__dict__.copy()
    env.upload()
    assert env.engine.reranker.retriever.__dict__ == before
    assert not hasattr(env.service.processor, 'index')


@pytest.mark.parametrize('kind', ['key-concepts', 'summary', 'flashcards', 'mindmap', 'quiz'])
def test_library_knowledge_tools_reuse_and_cache(pipeline_env, kind):
    env = pipeline_env
    headers = {'x-test-user': '3'}
    first = env.client.post(env.base + '/artifacts/' + kind, headers=headers, json={})
    assert first.status_code == 200, first.text
    artifact = first.json()['artifact']
    assert first.json()['cached'] is False and artifact['libraryId'] == env.lib
    repeated = env.client.post(env.base + '/artifacts/' + kind, headers=headers, json={})
    assert repeated.json()['cached'] and repeated.json()['artifact']['id'] == artifact['id']
    assert env.client.get(env.base + '/artifacts', headers=headers).json()['artifacts'][0]['id'] == artifact['id']
    assert env.client.get(env.base + '/artifacts/' + artifact['id'], headers=headers).status_code == 200


def test_knowledge_source_provenance(pipeline_env):
    env = pipeline_env
    artifact = env.service.generate(env.lib, env.row['asset_id'], {'sub': '3'}, 'flashcards')['artifact']
    chunk = artifact['sourceChunkIds'][0]
    source = env.client.get(env.base + '/sources/' + chunk, headers={'x-test-user': '3'})
    assert source.status_code == 200 and source.json()['libraryId'] == env.lib
    assert artifact['content']['cards'][0]['sourceExcerpt'] in source.json()['text']


@pytest.mark.parametrize('operation', ['rag', 'artifacts', 'cached', 'source', 'grade'])
def test_selection_revalidates_membership(pipeline_env, operation, monkeypatch):
    env = pipeline_env
    artifact = env.service.generate(env.lib, env.row['asset_id'], {'sub': '3'}, 'summary')['artifact']
    chunk = artifact['sourceChunkIds'][0]
    env.database.institution_memberships.update_one({'library_id': env.lib, 'user_id': 3}, {'$set': {'status': 'REVOKED'}})
    monkeypatch.setattr(pipeline_module, 'bounded_json', lambda *_: pytest.fail('Private cache loaded after revocation'))
    operation_call = {'rag': lambda: env.service.ask(env.lib, env.row['asset_id'], {'sub': '3'}, 'Explain memory.'),
        'artifacts': lambda: env.service.list_artifacts(env.lib, env.row['asset_id'], {'sub': '3'}),
        'cached': lambda: env.service.generate(env.lib, env.row['asset_id'], {'sub': '3'}, 'summary'),
        'source': lambda: env.service.source(env.lib, env.row['asset_id'], {'sub': '3'}, chunk),
        'grade': lambda: env.service.grade(env.lib, env.row['asset_id'], {'sub': '3'}, artifact['id'], 'guessed', 'memory')}
    with pytest.raises(HTTPException) as error:
        operation_call[operation]()
    assert error.value.status_code == 404 and not env.engine.calls


def test_revoked_during_generation_answer_is_not_returned(pipeline_env):
    env = pipeline_env
    env.engine.callback = lambda: env.database.institution_memberships.update_one(
        {'library_id': env.lib, 'user_id': 3}, {'$set': {'status': 'REVOKED'}})
    result = env.client.post(env.base + '/rag', headers={'x-test-user': '3'}, json={'query': 'What is paging?'})
    assert result.status_code == 404
    assert env.engine.calls and env.engine.reranker.retriever.doc_index is None


def test_generation_exception_clears_private_runtime(pipeline_env):
    env = pipeline_env
    def fail():
        raise RuntimeError('Generation unavailable')
    env.engine.callback = fail
    result = env.client.post(env.base + '/rag', headers={'x-test-user': '3'}, json={'query': 'Explain memory.'})
    assert result.status_code == 503
    assert 'Generation unavailable' not in result.text
    assert env.engine.reranker.retriever.doc_index is None and not env.engine.reranker.retriever.doc_chunk_texts


@pytest.mark.parametrize('stage', ['ocr', 'chunking', 'embedding'])
def test_processing_stage_failure_and_retry(pipeline_env, monkeypatch, stage):
    env = pipeline_env
    row = env.upload(process=False)
    with monkeypatch.context() as changed:
        def fail(*args, **kwargs):
            raise RuntimeError('Simulated private pipeline fault')
        if stage == 'ocr':
            changed.setattr(pipeline_module.private_document_ocr, 'prepare', fail)
        else:
            changed.setattr(env.service.processor, 'create_chunks' if stage == 'chunking' else 'embed_chunks', fail)
        assert env.service.run_one()
    failed = env.database.institution_library_assets.find_one({'asset_id': row['asset_id']})
    assert failed['status'] == 'FAILED' and failed['error_code'] == 'PROCESSING_FAILED'
    retry = repository.reprocess(env.lib, row['asset_id'], {'sub': '1'})
    assert retry['status'] == 'PROCESSING'
    assert env.service.run_one()
    ready = repository.authorize_asset(env.lib, row['asset_id'], {'sub': '1'}, ready=True)
    assert ready['status'] == 'READY'


def test_processing_source_checksum_rejected(pipeline_env):
    env = pipeline_env
    row = env.upload(process=False)
    path = repository.source_path(row)
    content = bytearray(path.read_bytes())
    content[-8] ^= 1
    path.write_bytes(content)
    assert env.service.run_one()
    failed = env.database.institution_library_assets.find_one({'asset_id': row['asset_id']})
    assert failed['status'] == 'FAILED' and failed['error_code'] == 'SOURCE_CHECKSUM_MISMATCH'


@pytest.mark.parametrize('scope', ['chunks', 'manifest', 'index'])
def test_rag_artifact_corruption_fails_before_generation(pipeline_env, scope):
    env = pipeline_env
    folder = repository.artifacts_path(env.row)
    name = {'chunks': 'chunks.json', 'manifest': 'manifest.json', 'index': 'runtime.faiss'}[scope]
    (folder / name).write_text('{}')
    result = env.client.post(env.base + '/rag', json={'query': 'Explain memory.'})
    assert result.status_code == 409 and not env.engine.calls


def test_worker_does_not_publish_after_authority_revoked(pipeline_env, monkeypatch):
    env = pipeline_env
    row = env.upload(process=False)
    original = env.service.processor.embed_chunks
    def embed(chunks):
        vectors = original(chunks)
        env.database.institution_memberships.update_one({'library_id': env.lib, 'user_id': 1}, {'$set': {'status': 'REVOKED'}})
        return vectors
    monkeypatch.setattr(env.service.processor, 'embed_chunks', embed)
    assert env.service.run_one()
    assert env.database.institution_library_assets.find_one({'asset_id': row['asset_id']})['status'] == 'FAILED'


def test_worker_lease_fences_old_generation(pipeline_env):
    from backend.services.institution_repository import now
    from datetime import timedelta
    env = pipeline_env
    row = env.upload(process=False)
    first = repository.claim_job('worker-a')
    env.database.institution_library_asset_jobs.update_one({'job_id': first['job_id']}, {'$set': {
        'lease_expires_at': now() - timedelta(seconds=1)}})
    second = repository.claim_job('worker-b')
    assert first['generation_id'] != second['generation_id']
    old_manifest = env.service.process_job(first)
    assert repository.complete_job(first, old_manifest) is False
    assert repository.fail_job(first, 'PROCESSING_FAILED') is False
    assert repository.renew_job(first) is False
    manifest = env.service.process_job(second)
    assert repository.complete_job(second, manifest) is True
    ready = repository.authorize_asset(env.lib, row['asset_id'], {'sub': '1'}, ready=True)
    assert ready['active_generation_id'] == second['generation_id']


def test_worker_acknowledgement_loss_does_not_duplicate(pipeline_env, monkeypatch):
    env = pipeline_env
    row = env.upload(process=False)
    complete = repository.complete_job
    def lost(job, manifest):
        assert complete(job, manifest)
        raise RuntimeError('Acknowledgement lost after publication')
    monkeypatch.setattr(repository, 'complete_job', lost)
    assert env.service.run_one()
    ready = repository.authorize_asset(env.lib, row['asset_id'], {'sub': '1'}, ready=True)
    assert ready['status'] == 'READY'
    assert repository.artifacts_path(ready).is_dir()
    assert env.database.institution_library_asset_jobs.find_one({'job_id': ready['active_job_id']})['state'] == 'READY'
    assert env.service.run_one() is False


def test_worker_transient_guard_503_waits_for_coherent_snapshot(pipeline_env, monkeypatch):
    env = pipeline_env
    row = env.upload(process=False)
    original = repository.authorize_asset
    attempts = []
    def busy(*args, **kwargs):
        attempts.append(1)
        if len(attempts) <= 2:
            raise HTTPException(503, 'Library update in progress.')
        return original(*args, **kwargs)
    monkeypatch.setattr(repository, 'authorize_asset', busy)
    assert env.service.run_one()
    ready = original(env.lib, row['asset_id'], {'sub': '1'}, ready=True)
    assert ready['status'] == 'READY' and len(attempts) == 4


def test_worker_denial_precedes_source_read_and_is_not_retried(pipeline_env, monkeypatch):
    env = pipeline_env
    row = env.upload(process=False)
    attempts = []
    def denied(*args, **kwargs):
        attempts.append(1)
        raise HTTPException(404, {'code': 'MEMBERSHIP_REVOKED'})
    monkeypatch.setattr(repository, 'authorize_asset', denied)
    monkeypatch.setattr(pipeline_module, 'digest', lambda *_: pytest.fail('Private file read before authorization'))
    assert env.service.run_one()
    failed = env.database.institution_library_assets.find_one({'asset_id': row['asset_id']})
    assert failed['status'] == 'FAILED' and len(attempts) == 1


def test_fenced_publication_retires_only_own_generation(pipeline_env, monkeypatch):
    env = pipeline_env
    row = env.upload(process=False)
    prepare = env.service.process_job
    observed = {}
    def revoke_after_prepare(job):
        result = prepare(job)
        observed['generation'] = repository.artifacts_path(job['asset'], job['generation_id'])
        env.database.institution_memberships.update_one({'library_id': env.lib, 'user_id': 1},
            {'$set': {'status': 'REVOKED'}})
        return result
    monkeypatch.setattr(env.service, 'process_job', revoke_after_prepare)
    existing = repository.artifacts_path(env.row)
    assert env.service.run_one()
    assert not observed['generation'].exists()
    assert existing.exists() and repository.source_path(row).exists()


def test_delete_racing_late_generation_is_cleaned(pipeline_env, monkeypatch):
    env = pipeline_env
    row = env.upload(process=False)
    prepare = env.service.process_job
    observed = {}
    def delete_and_late_artifact(job):
        result = prepare(job)
        repository.delete(env.lib, row['asset_id'], {'sub': '1'})
        folder = repository.artifacts_path(job['asset'], job['generation_id'])
        folder.mkdir(parents=True)
        (folder / 'chunks.json').write_text('[]')
        observed['generation'] = folder
        return result
    monkeypatch.setattr(env.service, 'process_job', delete_and_late_artifact)
    assert env.service.run_one()
    assert not observed['generation'].exists()
    assert env.database.institution_library_assets.find_one({'asset_id': row['asset_id']})['status'] == 'DELETED'


def test_processing_exception_retires_unpublished_generation(pipeline_env, monkeypatch):
    env = pipeline_env
    row = env.upload(process=False)
    def invalid(chunks):
        raise RuntimeError('Deliberately withheld private exception message.')
    monkeypatch.setattr(env.service.processor, 'embed_chunks', invalid)
    assert env.service.run_one()
    job = env.database.institution_library_asset_jobs.find_one({'asset_id': row['asset_id']})
    assert not repository.artifacts_path(row, job['generation_id']).exists()
    assert repository.source_path(row).exists()


@pytest.mark.parametrize('artifact', ['extracted.json', 'chunks.json', 'manifest.json'])
def test_processing_json_budget_prevents_unreadable_ready_asset(pipeline_env, monkeypatch, artifact):
    env = pipeline_env
    row = env.upload(process=False)
    existing = repository.artifacts_path(env.row)
    if artifact == 'manifest.json':
        monkeypatch.setattr(pipeline_module, 'MAX_MANIFEST_BYTES', 32)
    else:
        # Exercise chunk output separately after extraction fits its budget.
        limit = 32 if artifact == 'extracted.json' else (existing / 'extracted.json').stat().st_size + 1
        assert (existing / artifact).stat().st_size > limit
        monkeypatch.setattr(pipeline_module, 'MAX_JSON_ARTIFACT_BYTES', limit)
    assert env.service.run_one()
    failed = env.database.institution_library_assets.find_one({'asset_id': row['asset_id']})
    job = env.database.institution_library_asset_jobs.find_one({'job_id': failed['active_job_id']})
    assert failed['status'] == 'FAILED' and failed['error_code'] == 'ARTIFACT_LIMIT'
    assert job['state'] == 'FAILED' and job['error_code'] == 'ARTIFACT_LIMIT'
    assert repository.source_path(failed).read_bytes() == env.content
    assert not repository.artifacts_path(failed, job['generation_id']).exists()
    response = env.client.post(f"/libraries/{env.lib}/assets/{row['asset_id']}/rag",
        json={'query': 'Use this oversized document.'})
    assert response.status_code == 409 and not env.engine.calls


def test_json_artifact_budget_counts_utf8_bytes_and_preserves_published_file(tmp_path):
    path = tmp_path / 'artifact.json'
    path.write_text('previous valid artifact', encoding='utf-8')
    payload = {'title': '漢字漢字'}
    serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    assert len(serialized.encode('utf-8')) > len(serialized)
    with pytest.raises(HTTPException) as oversized:
        pipeline_module.atomic_json(path, payload, limit=len(serialized))
    assert oversized.value.status_code == 413 and oversized.value.detail == 'ARTIFACT_LIMIT'
    assert path.read_text(encoding='utf-8') == 'previous valid artifact'
    assert list(tmp_path.glob('*.tmp')) == []
    pipeline_module.atomic_json(path, payload, limit=len(serialized.encode('utf-8')))
    assert json.loads(path.read_text(encoding='utf-8')) == payload


def test_knowledge_artifact_delete_requires_staff(pipeline_env):
    env = pipeline_env
    artifact = env.service.generate(env.lib, env.row['asset_id'], {'sub': '3'}, 'summary')['artifact']
    assert env.client.delete(env.base + '/artifacts/' + artifact['id'], headers={'x-test-user': '3'}).status_code == 403
    assert env.client.delete(env.base + '/artifacts/' + artifact['id'], headers={'x-test-user': '4'}).status_code == 200


def test_cache_and_chunk_symlink_escape_rejected(pipeline_env, tmp_path):
    env = pipeline_env
    destination = tmp_path / 'outside'
    destination.mkdir()
    folder = repository.artifacts_path(env.row)
    try:
        (folder / 'knowledge').symlink_to(destination, target_is_directory=True)
    except OSError:
        # Windows junctions are covered separately by asset storage tests; no
        # administrator symlink privilege is required for lexical escape check.
        with pytest.raises(HTTPException):
            safe_child(folder, '..', '..', '..', 'outside')
        return
    with pytest.raises(HTTPException) as error:
        env.service.generate(env.lib, env.row['asset_id'], {'sub': '1'}, 'summary')
    assert error.value.status_code == 404


def test_cached_output_wrong_tenant_identity_is_not_served(pipeline_env):
    env = pipeline_env
    env.service.generate(env.lib, env.row['asset_id'], {'sub': '3'}, 'summary')
    folder = repository.artifacts_path(env.row) / 'knowledge'
    target = next(path for path in folder.glob('*.json') if not path.name.endswith('.model.json'))
    artifact = json.loads(target.read_text())
    artifact['libraryId'] = env.other
    target.write_text(json.dumps(artifact))
    with pytest.raises(HTTPException) as error:
        env.service.generate(env.lib, env.row['asset_id'], {'sub': '3'}, 'summary')
    assert error.value.status_code == 409
    assert env.service.list_artifacts(env.lib, env.row['asset_id'], {'sub': '3'}) == {'artifacts': []}


def test_visibility_changed_during_cached_tool_read_is_denied(pipeline_env, monkeypatch):
    env = pipeline_env
    env.service.generate(env.lib, env.row['asset_id'], {'sub': '3'}, 'summary')
    read = pipeline_module.bounded_json
    def cached_read(path, *args, **kwargs):
        value = read(path, *args, **kwargs)
        if not path.name.endswith('.model.json'):
            repository.update(env.lib, env.row['asset_id'], {'sub': '1'}, AssetUpdate(visibility='STAFF_ONLY'))
        return value
    monkeypatch.setattr(pipeline_module, 'bounded_json', cached_read)
    with pytest.raises(HTTPException) as error:
        env.service.generate(env.lib, env.row['asset_id'], {'sub': '3'}, 'summary')
    assert error.value.status_code == 404


def test_deleted_asset_cannot_retrieve_or_reopen_cached_tools(pipeline_env):
    env = pipeline_env
    artifact = env.service.generate(env.lib, env.row['asset_id'], {'sub': '3'}, 'summary')['artifact']
    repository.delete(env.lib, env.row['asset_id'], {'sub': '1'})
    for suffix in ('/rag', '/artifacts', '/artifacts/' + artifact['id']):
        response = (env.client.post(env.base + suffix, json={'query': 'Read deleted source.'}) if suffix == '/rag'
                    else env.client.get(env.base + suffix))
        assert response.status_code == 404
    assert not env.engine.calls


def test_processing_invalid_vectors_fail_safely(pipeline_env, monkeypatch):
    env = pipeline_env
    row = env.upload(process=False)
    monkeypatch.setattr(env.service.processor, 'embed_chunks',
                        lambda chunks: np.full((len(chunks), DIMENSION), np.nan, dtype='float32'))
    assert env.service.run_one()
    failed = env.database.institution_library_assets.find_one({'asset_id': row['asset_id']})
    assert failed['status'] == 'FAILED' and failed['error_code'] == 'EMBEDDING_INVALID'


@pytest.mark.parametrize('payload', [{}, {'query': ' '}, {'query': 'A', 'question': 'B'},
    {'query': 'A', 'depth': 'unsafe'}, {'query': 'A', 'asset_id': str(uuid4())}])
def test_rag_request_validation(pipeline_env, payload):
    result = pipeline_env.client.post(pipeline_env.base + '/rag', json=payload)
    assert result.status_code == 422 and not pipeline_env.engine.calls


def test_global_assistant_does_not_search_library_assets(pipeline_env):
    from assistant.schemas import AssistantRequest
    from rag.services.book_access import authorize_selection
    env = pipeline_env
    request = AssistantRequest(message='Use the PDF uploaded in Library B.')
    assert request.selected_work_ids == [] and request.page_context.document_id is None
    assert env.engine.reranker.retriever.doc_ids == set()
    assert env.engine.reranker.retriever.doc_metadata == []
    # The legacy WorkID syntax permits an opaque UUID, but no library asset
    # registry is consulted by the global book/document authorization adapter.
    with pytest.raises(HTTPException) as error:
        authorize_selection(None, env.row['asset_id'], None, set())
    assert error.value.status_code == 404
