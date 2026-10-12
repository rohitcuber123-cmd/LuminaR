"""Real HTTP authorization checks in a disposable standalone Mongo database."""
import os
from uuid import uuid4
os.environ['MONGO_URI'] = 'mongodb://127.0.0.1:27017'
os.environ['MONGO_DB_NAME'] = 'luminar_catalogue_test_' + uuid4().hex
os.environ['JWT_SECRET_KEY'] = 'catalogue-disposable-key'
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
    assert db.name.startswith('luminar_catalogue_test_')
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


