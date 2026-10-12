"""Canonical isolated Mongo and storage; no existing library/user/document mutation."""
import os
from uuid import uuid4

os.environ['MONGO_URI'] = 'mongodb://127.0.0.1:27017'
os.environ['MONGO_DB_NAME'] = 'luminar_institution_v2f_test_' + uuid4().hex
os.environ['JWT_SECRET_KEY'] = 'institution-v2f-isolated-key'
os.environ['NOTIFICATION_DUE_WORKER_ENABLED'] = '0'
os.environ['NOTIFICATION_OUTBOX_WORKER_ENABLED'] = '0'

import fitz
import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from backend.main import app
from backend.dependencies import get_current_user
from backend.database.mongodb import db, client as mongo
from backend.services import institution_repository, library_catalogue_repository, library_lending_journal
from backend.services import library_reservation_service, library_catalogue_experience, library_asset_service


@pytest.fixture(scope='session', autouse=True)
def database_lifecycle():
    mongo.admin.command('ping')
    for module in (institution_repository, library_catalogue_repository, library_lending_journal,
                   library_reservation_service, library_catalogue_experience, library_asset_service):
        module.ensure_indexes()
    yield
    assert db.name.startswith('luminar_institution_v2f_test_')
    mongo.drop_database(db.name)


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    for name in db.list_collection_names():
        db[name].delete_many({})
    monkeypatch.setenv('LIBRARY_ASSET_ROOT', str(tmp_path / 'library-assets'))
    db.users.insert_many([{'user_id': user, 'name': f'Fixture account {user}',
        'email': f'v2f-{user}@example.com', 'is_active': True, 'is_email_verified': True,
        'role': 'ADMIN' if user == 9 else 'GENERAL_USER'} for user in range(1, 15)])
    def identity(request: Request):
        return {'sub': request.headers.get('x-test-user', '1'), 'role': request.headers.get('x-test-role', 'GENERAL_USER')}
    app.dependency_overrides[get_current_user] = identity
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def database():
    return db


@pytest.fixture
def library(client):
    def create(owner=1, private=False, name='Digital assets fixture'):
        payload = {'name': name, 'slug': 'assets-' + uuid4().hex[:16],
            'library_type': 'PRIVATE_INSTITUTION' if private else 'PUBLIC_LIBRARY',
            'access_mode': 'PRIVATE_CODE' if private else 'PUBLIC'}
        if private:
            payload['access_code'] = 'Isolated fixture access code'
        response = client.post('/libraries/register', headers={'x-test-user': str(owner)}, json=payload)
        assert response.status_code == 201, response.text
        return response.json()['library']['library_id']
    return create


@pytest.fixture
def pdf_bytes():
    document = fitz.open()
    page = document.new_page()
    page.insert_text((60, 60), 'The library document access code for this safe fixture is violet lantern.\n'
                     'This document belongs only to its explicitly owning library.\n' * 8)
    content = document.tobytes()
    document.close()
    return content


@pytest.fixture
def upload(client, pdf_bytes):
    def create(library_id, *, user=1, visibility='MEMBERS', title='Safe fixture PDF', book_id=None,
               content=None, filename='fixture.pdf', upload_id=None):
        data = {'title': title, 'visibility': visibility}
        if book_id:
            data['library_book_id'] = book_id
        return client.post(f'/libraries/{library_id}/assets', headers={'x-test-user': str(user),
            'X-Luminar-Upload': upload_id or str(uuid4())}, data=data,
            files={'file': (filename, pdf_bytes if content is None else content, 'application/pdf')})
    return create


@pytest.fixture
def ready():
    def publish(asset):
        job = library_asset_service.claim_job('isolated-test-worker')
        assert job and job['asset_id'] == asset['asset_id']
        path = library_asset_service.artifacts_path(job['asset'], job['generation_id'])
        path.mkdir(parents=True)
        for name in library_asset_service.ARTIFACT_FILES:
            (path / name).write_bytes(b'fixture')
        manifest = {'library_id': asset['library_id'], 'asset_id': asset['asset_id'],
            'generation_id': job['generation_id'], 'checksum': asset['checksum'], 'pages': 1, 'chunks': 2}
        assert library_asset_service.complete_job(job, manifest)
        return job
    return publish
