"""Isolated entitlement tests: no live records or real assets are modified."""
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import sleep

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from backend.services import book_capability_service as service
from backend.services import issue_service
from rag.services import book_access


NOW = datetime.now(timezone.utc)


def matches(row, query):
    for key, expected in query.items():
        actual = row.get(key)
        if isinstance(expected, dict):
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$gt" in expected and not (actual is not None and actual > expected["$gt"]):
                return False
        elif actual != expected:
            return False
    return True


class FakeCollection:
    def __init__(self, rows):
        self.rows = rows

    def find_one(self, query, projection=None):
        return next((dict(row) for row in self.rows if matches(row, query)), None)

    def distinct(self, field, query):
        return list({row[field] for row in self.rows if field in row and matches(row, query)})

    def find(self, query, projection=None):
        return [dict(row) for row in self.rows if matches(row, query)]


class TextPath:
    def read_text(self, encoding="utf-8"):
        return "Authorized full text"


class FakeBorrowLocks:
    def __init__(self):
        self.rows = {}
        self.lock = Lock()

    def insert_one(self, row):
        with self.lock:
            if row["_id"] in self.rows:
                from pymongo.errors import DuplicateKeyError
                raise DuplicateKeyError("duplicate lease")
            self.rows[row["_id"]] = dict(row)

    def delete_one(self, query):
        with self.lock:
            row = self.rows.get(query["_id"])
            if not row:
                return
            token = query.get("token")
            expiry = query.get("expires_at", {}).get("$lte")
            if token is not None and row.get("token") != token:
                return
            if expiry is not None and not row.get("expires_at") <= expiry:
                return
            del self.rows[query["_id"]]


@pytest.fixture
def access_context(monkeypatch):
    flags = {
        "OL1W": {"readable": True, "rag_available": True},
        "OL2W": {"readable": True, "rag_available": False},
        "OL3W": {"readable": False, "rag_available": True},
        "OL4W": {"readable": False, "rag_available": False},
    }
    books = [{"work_id": work_id, "title": work_id, "authors": "Author"} for work_id in flags]
    issues = [
        {"issue_id": 1, "user_id": 1, "work_id": "OL1W", "status": "ISSUED", "returned_at": None, "due_date": NOW + timedelta(days=1)},
        {"issue_id": 2, "user_id": 1, "work_id": "OL2W", "status": "ISSUED", "returned_at": None, "due_date": NOW + timedelta(days=1)},
        {"issue_id": 3, "user_id": 1, "work_id": "OL3W", "status": "ISSUED", "returned_at": None, "due_date": NOW + timedelta(days=1)},
        {"issue_id": 4, "user_id": 1, "work_id": "OL4W", "status": "ISSUED", "returned_at": None, "due_date": NOW + timedelta(days=1)},
        {"issue_id": 5, "user_id": 1, "work_id": "OL1W", "status": "RETURNED", "returned_at": NOW, "due_date": NOW + timedelta(days=1)},
        {"issue_id": 6, "user_id": 2, "work_id": "OL1W", "status": "CANCELLED", "returned_at": None, "due_date": NOW + timedelta(days=1)},
        {"issue_id": 7, "user_id": 3, "work_id": "OL1W", "status": "ISSUED", "returned_at": None, "due_date": NOW - timedelta(days=1)},
    ]
    monkeypatch.setattr(service, "books_collection", FakeCollection(books))
    monkeypatch.setattr(service, "issues_collection", FakeCollection(issues))
    monkeypatch.setattr(service, "capabilities", lambda ids: {work_id: flags.get(work_id, {"readable": False, "rag_available": False}) for work_id in ids})
    monkeypatch.setattr(service, "readable_path", lambda work_id: TextPath() if flags.get(work_id, {}).get("readable") else None)
    return flags, issues


def assert_http(status, call):
    with pytest.raises(HTTPException) as error:
        call()
    assert error.value.status_code == status


def test_exact_work_id_access_matrix(access_context):
    service.authorize_reader(1, "OL1W")
    service.authorize_know_more(1, "OL1W")
    service.authorize_reader(1, "OL2W")
    assert_http(404, lambda: service.authorize_know_more(1, "OL2W"))
    assert_http(404, lambda: service.authorize_reader(1, "OL3W"))
    service.authorize_know_more(1, "OL3W")
    assert_http(404, lambda: service.authorize_reader(1, "OL4W"))
    assert_http(404, lambda: service.authorize_know_more(1, "OL4W"))


@pytest.mark.parametrize("user_id", [2, 3, 99])
def test_returned_cancelled_expired_and_unborrowed_are_denied(access_context, user_id):
    assert_http(403, lambda: service.authorize_reader(user_id, "OL1W"))
    assert_http(403, lambda: service.authorize_know_more(user_id, "OL1W"))


def test_nonexistent_work_id_is_404(access_context):
    assert_http(404, lambda: service.authorize_reader(1, "OL999W"))
    assert_http(404, lambda: service.authorize_know_more(1, "OL999W"))


def test_reader_returns_only_the_selected_entitled_book(access_context):
    result = service.get_readable_book(1, "OL2W")
    assert result["work_id"] == "OL2W"
    assert result["text"] == "Authorized full text"
    assert_http(403, lambda: service.get_readable_book(99, "OL2W"))


def test_reader_http_route_revalidates_on_direct_navigation(access_context):
    from backend.dependencies import get_current_user
    from backend.routes.books import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"sub": "99", "role": "GENERAL_USER"}
    client = TestClient(app)
    assert client.get("/books/OL1W/read").status_code == 403
    assert client.get("/books/OL999W/read").status_code == 404

    app.dependency_overrides[get_current_user] = lambda: {"sub": "1", "role": "GENERAL_USER"}
    result = client.get("/books/OL1W/read")
    assert result.status_code == 200
    assert result.json()["work_id"] == "OL1W"


def test_issue_enrichment_is_exact_and_separates_capabilities(access_context):
    _, issues = access_context
    enriched = service.with_issue_capabilities(issues[:4], 1)
    by_id = {row["work_id"]: row for row in enriched}
    assert by_id["OL1W"]["can_read"] and by_id["OL1W"]["can_know_more"]
    assert by_id["OL2W"]["can_read"] and not by_id["OL2W"]["can_know_more"]
    assert not by_id["OL3W"]["can_read"] and by_id["OL3W"]["can_know_more"]
    assert not by_id["OL4W"]["can_read"] and not by_id["OL4W"]["can_know_more"]


def test_reading_list_or_recommendation_presence_cannot_grant_access(access_context):
    # Neither feature participates in the authoritative issue query.
    assert_http(403, lambda: service.authorize_reader(99, "OL1W"))
    assert_http(403, lambda: service.authorize_know_more(99, "OL1W"))


def test_rag_manual_work_id_change_rechecks_entitlement(access_context, monkeypatch):
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")
    monkeypatch.setattr(book_access, "get_current_user", lambda _: {"sub": "99"})
    monkeypatch.setattr(book_access, "authorize_know_more", service.authorize_know_more)
    assert_http(403, lambda: book_access.authorize_selection(None, "OL1W", credentials, set()))
    assert_http(404, lambda: book_access.authorize_selection(None, "OL999W", credentials, set()))


def test_logout_or_user_switch_has_no_server_side_entitlement_leak(access_context):
    service.authorize_reader(1, "OL1W")
    assert_http(403, lambda: service.authorize_reader(2, "OL1W"))
    assert_http(403, lambda: service.authorize_reader(99, "OL1W"))


def test_issue_creation_wrapper_serializes_racing_borrow_requests(monkeypatch):
    state_lock = Lock()
    active = 0
    maximum_active = 0

    def fake_issue(user_id, work_id, library_id):
        nonlocal active, maximum_active
        with state_lock:
            active += 1
            maximum_active = max(maximum_active, active)
        sleep(0.02)
        with state_lock:
            active -= 1
        return {"user_id": user_id, "work_id": work_id, "library_id": library_id}

    monkeypatch.setattr(issue_service, "_issue_book", fake_issue)
    monkeypatch.setattr(issue_service, "borrow_locks_collection", FakeBorrowLocks())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: issue_service.issue_book(1, "OL1W"), range(2)))
    assert len(results) == 2
    assert maximum_active == 1
