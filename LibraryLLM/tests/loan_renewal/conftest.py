"""Real Mongo indexes/query behavior in a uniquely named disposable database.

Run separately from the legacy staff_auth module which replaces database imports.
No production records or model processes are used.
"""
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.database.mongodb import client as mongo
from backend.dependencies import get_current_user
from backend.main import app
from backend.services import notification_service as ns, admin_operation_service as ops
from backend.services import identity_service, activity_service, issue_service, reservation_service, fine_service

NOW = datetime.now(timezone.utc).replace(microsecond=0)


@pytest.fixture
def isolated(monkeypatch):
    name = 'luminar_renewal_test_' + uuid4().hex
    db = mongo[name]
    from backend.database import mongodb
    monkeypatch.setattr(mongodb, 'db', db)
    assert name != 'luminar_library' and name.startswith('luminar_renewal_test_')
    for module in [ns, ops, identity_service]:
        monkeypatch.setattr(module, 'db', db)
    monkeypatch.setattr(ns, 'notifications', db.notifications)
    for module in [ns, ops, identity_service, activity_service, issue_service, reservation_service, fine_service]:
        for attr, collection in [('users_collection','users'),('activity_collection','activity'),
            ('issues_collection','issues'),('books_collection','books'),('reservations_collection','reservations'),
            ('fines_collection','fines'),('library_inventory_collection','library_inventory'),('borrow_locks_collection','borrow_locks')]:
            if hasattr(module, attr): monkeypatch.setattr(module, attr, db[collection])
    from backend.services import availability_service, book_capability_service
    monkeypatch.setattr(availability_service, 'library_inventory_collection', db.library_inventory)
    db.users.insert_many([{'user_id': uid, 'name': name, 'email': email, 'role': role,
                          'is_active': True, 'is_email_verified': True, 'password_hash': 'SECRET'}
        for uid,name,email,role in [(1,'Admin','admin@example.com','ADMIN'),(2,'Alice','alice@example.com','GENERAL_USER'),
                                  (3,'Bob','bob@example.com','GENERAL_USER'),(4,'Staff','staff@example.com','LIBRARIAN')]])
    db.books.insert_many([{'book_id':1,'work_id':'OL1W','title':'Dracula','available_copies':2,'total_copies':2},
                         {'book_id':2,'work_id':'OL2W','title':'Dune','available_copies':2,'total_copies':2}])
    monkeypatch.setattr(book_capability_service, 'issues_collection', db.issues)
    monkeypatch.setattr(book_capability_service, 'books_collection', db.books)
    ns.ensure_indexes()
    app.dependency_overrides.clear()
    yield db
    app.dependency_overrides.clear()
    mongo.drop_database(name)


def http(uid=1, claimed='ADMIN'):
    app.dependency_overrides[get_current_user] = lambda: {'sub': str(uid), 'role': claimed}
    return TestClient(app)

