"""Integration tests using real MongoDB records, provided full text and FAISS.

Run in the isolated DB prepared by scripts/prepare_dynamic_book_validation.py:
LUMINAR_RUN_BOOK_INTEGRATION=1 MONGO_DB_NAME=<validation DB> python -m pytest ...
No generated book content, mocked database, embeddings, or index are used.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil

import pytest

pytestmark = pytest.mark.skipif(os.getenv("LUMINAR_RUN_BOOK_INTEGRATION") != "1",
                                reason="Requires explicitly prepared isolated MongoDB validation data")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def context():
    assert os.environ.get("MONGO_DB_NAME", "").startswith("luminar_dynamic_book_validation_")
    from backend.database.mongodb import db
    from backend.main import app
    from backend.utils.jwt_utils import create_access_token
    from fastapi.testclient import TestClient
    from rag.book_assets import content_sources
    return db, TestClient(app), {"Authorization": "Bearer " + create_access_token(1, "reader1@validation.invalid", "GENERAL_USER")}, list(content_sources())


def test_list_requires_authentication(context):
    _, api, _, _ = context
    assert api.get("/know-more/books").status_code in {401, 403}


def test_all_current_assets_and_full_catalog_preserved(context):
    db, api, _, ids = context
    before = db.books.count_documents({})
    result = api.get("/books/?limit=100").json()
    assert result["count"] == before
    for work_id in ids:
        if not db.books.find_one({"work_id": work_id}):
            continue
        book = api.get(f"/books/{work_id}").json()
        assert book["readable"] and book["rag_available"]
        assert api.get(f"/books/{work_id}/read").status_code in {401, 403}
    modern = api.get("/books/OL17930368W").json()
    assert not modern["readable"] and not modern["rag_available"]
    assert api.get("/books/OL17930368W/read").status_code in {401, 403}


def test_borrow_return_and_other_user(context):
    db, api, headers, ids = context
    work_id = ids[0]
    before = api.get("/know-more/books", headers=headers).json()
    assert work_id not in {book["work_id"] for book in before["books"]}
    response = api.post("/issues/issue", json={"work_id": work_id}, headers=headers)
    assert response.status_code == 200, response.text
    issue = response.json()["issue"]
    try:
        result = api.get("/know-more/books", headers=headers)
        assert result.headers["Cache-Control"] == "no-store"
        assert work_id in {book["work_id"] for book in result.json()["books"]}
        assert len(api.get(f"/books/{work_id}/read", headers=headers).json()["text"]) > 10000
        from backend.utils.jwt_utils import create_access_token
        other = {"Authorization": "Bearer " + create_access_token(2, "reader2@validation.invalid", "GENERAL_USER")}
        assert api.get("/know-more/books", headers=other).json()["count"] == 0
        assert api.get(f"/books/{work_id}/read", headers=other).status_code == 403
    finally:
        assert api.post(f'/issues/return/{issue["issue_id"]}', headers=headers).status_code == 200
    assert work_id not in {book["work_id"] for book in api.get("/know-more/books", headers=headers).json()["books"]}
    assert api.get(f"/books/{work_id}").json()["readable"]


@pytest.mark.parametrize("status", ["RETURNED", "CLOSED", "CANCELLED", "EXPIRED"])
def test_inactive_status_excluded(context, status):
    db, api, headers, ids = context
    record = {"user_id": 1, "work_id": ids[0], "status": status,
              "returned_at": None, "due_date": datetime.now(timezone.utc) + timedelta(days=1)}
    inserted = db.issues.insert_one(record)
    try:
        assert ids[0] not in {book["work_id"] for book in api.get("/know-more/books", headers=headers).json()["books"]}
    finally:
        db.issues.delete_one({"_id": inserted.inserted_id})


def test_overdue_issued_excluded(context):
    db, api, headers, ids = context
    inserted = db.issues.insert_one({"user_id": 1, "work_id": ids[0], "status": "ISSUED",
        "returned_at": None, "due_date": datetime.now(timezone.utc) - timedelta(seconds=1)})
    try:
        assert ids[0] not in {book["work_id"] for book in api.get("/know-more/books", headers=headers).json()["books"]}
    finally:
        db.issues.delete_one({"_id": inserted.inserted_id})


def test_readable_nonindexed_and_dynamic_restoration(tmp_path, context):
    _, _, _, ids = context
    from rag.book_assets import BASE_DIR, capabilities
    work_id = ids[0]
    # Real assets copied into a temporary corpus; the live corpus is untouched.
    for directory in ["processed", "book_index", "book_chunks"]:
        shutil.copytree(BASE_DIR / directory, tmp_path / directory)
    shutil.copy2(BASE_DIR / "rag_book_mapping.json", tmp_path / "rag_book_mapping.json")
    assert capabilities([work_id], tmp_path)[work_id] == {"readable": True, "rag_available": True}
    path = tmp_path / f"book_index/books/{work_id}.index"
    original = path.read_bytes()
    path.unlink()
    assert capabilities([work_id], tmp_path)[work_id] == {"readable": True, "rag_available": False}
    path.write_bytes(original)
    assert capabilities([work_id], tmp_path)[work_id]["rag_available"]
    from rag.book_assets import readable_path
    readable_path(work_id, base=tmp_path).unlink()
    assert capabilities([work_id], tmp_path)[work_id] == {"readable": False, "rag_available": True}


def test_alias_unknown_and_unborrowed_authorization(context):
    _, _, _, ids = context
    from rag.services.book_access import authorize_selection
    from backend.utils.jwt_utils import create_access_token
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=create_access_token(2, "reader2@validation.invalid", "GENERAL_USER"))
    for document_id, work_id, auth, code in [
        (ids[0], None, None, 401), (None, ids[0], credentials, 403),
        (ids[0], None, credentials, 403), (ids[0], ids[1], credentials, 400),
        ("../book_index/rag", None, credentials, 404),
    ]:
        with pytest.raises(HTTPException) as error:
            authorize_selection(document_id, work_id, auth, set())
        assert error.value.status_code == code
    assert authorize_selection(None, None, None, set()) is None
