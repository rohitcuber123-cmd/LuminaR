"""Real Mongo, isolated canonical fixtures; production membership guards retained."""
import os
from uuid import uuid4

os.environ['MONGO_URI'] = 'mongodb://127.0.0.1:27017'
os.environ['MONGO_DB_NAME'] = 'luminar_institution_v2e_test_' + uuid4().hex
os.environ['JWT_SECRET_KEY'] = 'institution-v2e-isolated-key'
os.environ['NOTIFICATION_DUE_WORKER_ENABLED'] = '0'
os.environ['NOTIFICATION_OUTBOX_WORKER_ENABLED'] = '0'

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from backend.main import app
from backend.dependencies import get_current_user
from backend.database.mongodb import db, client as mongo
from backend.services import institution_repository, library_catalogue_repository, library_lending_journal
from backend.services import library_reservation_service, library_catalogue_experience, library_event_service
from backend.services import event_service, notification_service, tenant_notification_service


@pytest.fixture(scope='session', autouse=True)
def database_lifecycle():
    mongo.admin.command('ping')
    for module in (institution_repository, library_catalogue_repository, library_lending_journal,
                   library_reservation_service, library_catalogue_experience, event_service,
                   library_event_service, notification_service, tenant_notification_service):
        module.ensure_indexes()
    yield
    assert db.name.startswith('luminar_institution_v2e_test_')
    mongo.drop_database(db.name)


@pytest.fixture(autouse=True)
def isolate():
    for name in db.list_collection_names():
        db[name].delete_many({})
    db.users.insert_many([{'user_id': user, 'name': f'Fixture account {user}',
        'email': f'v2e-{user}@example.com', 'is_active': True, 'is_email_verified': True,
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
    def create(owner=1, private=True, name='Analytics fixture'):
        payload = {'name': name, 'slug': 'analytics-' + uuid4().hex[:16],
            'library_type': 'PRIVATE_INSTITUTION' if private else 'PUBLIC_LIBRARY',
            'access_mode': 'PRIVATE_CODE' if private else 'PUBLIC'}
        if private:
            payload['access_code'] = 'Isolated fixture access code'
        response = client.post('/libraries/register', headers={'x-test-user': str(owner)}, json=payload)
        assert response.status_code == 201, response.text
        return response.json()['library']['library_id']
    return create
