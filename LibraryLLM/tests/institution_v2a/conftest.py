"""Real Mongo; isolated from old suites which replace Mongo modules globally."""
import os
from uuid import uuid4
os.environ['MONGO_URI'] = 'mongodb://127.0.0.1:27017'
os.environ['MONGO_DB_NAME'] = 'luminar_institution_v2a_test_' + uuid4().hex
os.environ['JWT_SECRET_KEY'] = 'institution-v2a-disposable-key'
os.environ['ISBN_LOOKUP_DB'] = 'D:/SDC/LibraryLLM/.scratch/institution-v2a/no-isbn-lookup.duckdb'

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from backend.main import app
from backend.database.mongodb import db, client as mongo
from backend.dependencies import get_current_user
from backend.services.institution_repository import ensure_indexes as institution_indexes
from backend.services.library_catalogue_repository import ensure_indexes


@pytest.fixture(scope='session', autouse=True)
def disposable_database():
    mongo.admin.command('ping'); institution_indexes(); ensure_indexes()
    yield
    assert db.name.startswith('luminar_institution_v2a_test_')
    mongo.drop_database(db.name)


@pytest.fixture(autouse=True)
def isolate():
    for name in db.list_collection_names():
        db[name].delete_many({})
    db.users.insert_many([{'user_id': i, 'email': f'v2a-user-{i}@example.com', 'name': f'User {i}',
        'role': 'GENERAL_USER', 'is_email_verified': True, 'is_active': True} for i in range(1, 31)])
    db.books.insert_many([{'work_id': 'OL-Networks', 'title': 'Computer Networks', 'subjects': ['Networking'], 'authors': ['Forouzan']},
                         {'work_id': 'OL-Systems', 'title': 'Operating Systems', 'subjects': ['Systems']}])
    def current(request: Request):
        user = int(request.headers.get('x-test-user', '1'))
        return {'sub': str(user), 'email': f'v2a-user-{user}@example.com', 'role': request.headers.get('x-test-role', 'GENERAL_USER')}
    app.dependency_overrides[get_current_user] = current
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def database():
    return db


@pytest.fixture
def h():
    return lambda user=1, role='GENERAL_USER': {'x-test-user': str(user), 'x-test-role': role}


@pytest.fixture
def register(client, h):
    def create(owner=1, private=False, name='Aurora Library'):
        data = {'name': name, 'slug': 'v2a-' + uuid4().hex[:10], 'library_type': 'PRIVATE_INSTITUTION' if private else 'PUBLIC_LIBRARY',
                'access_mode': 'PRIVATE_CODE' if private else 'PUBLIC'}
        if private:
            data['access_code'] = 'Private V2A Passphrase'
        response = client.post('/libraries/register', json=data, headers=h(owner))
        assert response.status_code == 201, response.text
        library_id = response.json()['library']['library_id']
        # These accepted suites exercise historical snapshot/cutover semantics.
        # Fresh registration is tested independently with canonical defaults.
        for name in ['lending_config', 'v2c_config', 'fee_policies', 'lending_operations']:
            db['institution_' + name].delete_many({'library_id': library_id})
        return library_id
    return create


@pytest.fixture
def create(client, register):
    def add(library_id=None, actor=1, **fields):
        library_id = library_id or register()
        response = client.post(f'/libraries/{library_id}/inventory/books', headers={'x-test-user': str(actor)}, json={'title': 'Laboratory Manual', 'subjects': ['Systems'], **fields})
        assert response.status_code == 201, response.text
        return response.json()
    return add


@pytest.fixture
def preview(client):
    def upload(library_id, text, headers=None, filename='inventory.csv'):
        response = client.post(f'/libraries/{library_id}/inventory/imports/preview', headers=headers,
                               files={'file': (filename, text.encode() if isinstance(text, str) else text, 'text/csv')})
        assert response.status_code == 201, response.text
        return response.json()
    return upload


@pytest.fixture
def commit(client):
    def apply(library_id, job, policy='skip', headers=None):
        response = client.post(f'/libraries/{library_id}/inventory/imports/{job["import_id"]}/apply', json={'existing_policy': policy}, headers=headers)
        assert response.status_code == 200, response.text
        return response.json()
    return apply
