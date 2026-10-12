"""Real Mongo integration tests, always a unique disposable database.

Run separately from legacy suites which replace backend.database.mongodb.
"""
import os
from uuid import uuid4

os.environ['MONGO_URI'] = 'mongodb://127.0.0.1:27017'
os.environ['MONGO_DB_NAME'] = 'luminar_institution_test_' + uuid4().hex
os.environ['JWT_SECRET_KEY'] = 'institution-disposable-test-signing-key'

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from backend.main import app
from backend.database.mongodb import db, client as mongo
from backend.dependencies import get_current_user
from backend.services.institution_repository import ensure_indexes


@pytest.fixture(scope='session', autouse=True)
def disposable_database():
    mongo.admin.command('ping')
    ensure_indexes()
    yield
    assert db.name.startswith('luminar_institution_test_')
    mongo.drop_database(db.name)


@pytest.fixture(autouse=True)
def isolate():
    for name in db.list_collection_names():
        db[name].delete_many({})
    for i in range(1, 31):
        db.users.insert_one({'user_id': i, 'email': f'user{i}@example.com', 'name': f'User {i}',
                             'role': 'GENERAL_USER', 'is_email_verified': True, 'is_active': True})
    def current(request: Request):
        uid = int(request.headers.get('x-test-user', '1'))
        return {'sub': str(uid), 'email': f'user{uid}@example.com', 'role': request.headers.get('x-test-role', 'GENERAL_USER')}
    app.dependency_overrides[get_current_user] = current
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def database():
    return db


def headers(user=1, role='GENERAL_USER'):
    return {'x-test-user': str(user), 'x-test-role': role}


@pytest.fixture
def h():
    return headers


@pytest.fixture
def register(client, h):
    def create(owner=1, private=False, slug=None):
        data = {'name': 'Orion Research' if private else 'Aurora Public Library',
                'slug': slug or 'library-' + uuid4().hex[:10],
                'library_type': 'PRIVATE_INSTITUTION' if private else 'PUBLIC_LIBRARY',
                'access_mode': 'PRIVATE_CODE' if private else 'PUBLIC',
                'address': {'city': 'Hyderabad', 'region': 'Telangana'}}
        if private:
            data['access_code'] = 'Institution Test Passphrase'
        response = client.post('/libraries/register', json=data, headers=h(owner))
        assert response.status_code == 201, response.text
        return response.json()
    return create


@pytest.fixture
def invite(client, h):
    def create(library_id, target=2, role='LIBRARIAN', actor=1, email=None):
        response = client.post(f'/libraries/{library_id}/invitations', headers=h(actor),
                               json={'email': email or f'user{target}@example.com', 'role': role})
        assert response.status_code == 201, response.text
        return response.json()
    return create


@pytest.fixture
def accept(client, h):
    def respond(invitation, user=2):
        response = client.post('/invitations/' + invitation['invitation']['invitation_id'] + '/accept',
                               headers=h(user), json={'token': invitation['invite_token']})
        assert response.status_code == 200, response.text
        return response.json()
    return respond
