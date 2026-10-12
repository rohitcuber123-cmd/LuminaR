"""Real HTTP authorization checks in a disposable standalone Mongo database."""
import os
from uuid import uuid4
os.environ['MONGO_URI'] = 'mongodb://127.0.0.1:27017'
os.environ['MONGO_DB_NAME'] = 'luminar_dashboard_test_' + uuid4().hex
os.environ['JWT_SECRET_KEY'] = 'dashboard-disposable-key'
os.environ['ISBN_LOOKUP_DB'] = 'D:/SDC/LibraryLLM/.scratch/frontend-overhaul/no-isbn.duckdb'

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from backend.main import app
from backend.database.mongodb import db, client as mongo
from backend.dependencies import get_current_user
from backend.services.institution_repository import ensure_indexes as institutions
from backend.services.library_catalogue_repository import ensure_indexes as inventory
from backend.services.library_lending_journal import ensure_indexes as lending
from backend.services.library_reservation_service import ensure_indexes as reservations


@pytest.fixture(scope='session', autouse=True)
def disposable_database():
    mongo.admin.command('ping'); institutions(); inventory(); lending(); reservations()
    yield
    assert db.name.startswith('luminar_dashboard_test_')
    mongo.drop_database(db.name)


@pytest.fixture
def client():
    for name in db.list_collection_names(): db[name].delete_many({})
    db.users.insert_many([{'user_id': i, 'email': f'workspace-{i}@example.com', 'name': f'Account {i}',
        'role': 'ADMIN' if i == 1 else 'GENERAL_USER', 'is_active': True, 'is_email_verified': True} for i in (1, 2, 3)])
    def current(request: Request):
        user = int(request.headers.get('x-test-user', '1'))
        return {'sub': str(user), 'email': f'workspace-{user}@example.com', 'role': 'ADMIN' if user == 1 else 'GENERAL_USER'}
    app.dependency_overrides[get_current_user] = current
    with TestClient(app) as test_client: yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def libraries(client):
    result = []
    for label, owner, role in [('A', 1, 'ADMIN'), ('B', 2, 'GENERAL_USER'), ('C', 2, 'LIBRARIAN')]:
        row = client.post('/libraries/register', headers={'x-test-user': str(owner)}, json={'name': f'Library {label}',
            'slug': 'overhaul-' + uuid4().hex[:12], 'library_type': 'PUBLIC_LIBRARY', 'access_mode': 'PUBLIC'}).json()['library']
        library_id = row['library_id']; base = f'/libraries/{library_id}'
        if owner != 1:
            member = client.post(base + '/join', json={}, headers={'x-test-user': '1'}).json()['membership']
            if role == 'LIBRARIAN':
                assert client.patch(base + '/memberships/' + member['membership_id'], json={'role': role}, headers={'x-test-user': '2'}).status_code == 200
        # Fresh registrations are canonical; no fake cutover.
        created = client.post(base + '/inventory/books', headers={'x-test-user': str(owner)}, json={'idempotency_key': str(uuid4()), 'title': f'{label} Manual', 'subjects': ['Workspace'], 'copies': 2})
        assert created.status_code == 201, created.text
        book = created.json()
        result.append({'id': library_id, 'base': base, 'book': book['library_book_id'], 'owner': owner, 'role': role})
    return result
