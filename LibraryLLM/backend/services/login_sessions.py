"""Shared revocation ledger for the existing JWT signer (no document content)."""
import os
import contextlib
import sqlite3
import time
from pathlib import Path


@contextlib.contextmanager
def connect():
    path = Path(os.getenv('LUMINAR_SESSION_DB', str(Path(__file__).resolve().parents[2] / 'rag' / 'private_sessions.sqlite')))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    db.execute('CREATE TABLE IF NOT EXISTS revoked_sessions (sid TEXT PRIMARY KEY, expires REAL NOT NULL)')
    try:
        with db:
            yield db
    finally:
        db.close()


def is_revoked(sid):
    if not sid:
        return False  # Legacy JWTs retain book/account compatibility, never private upload access.
    with connect() as db:
        return db.execute('SELECT 1 FROM revoked_sessions WHERE sid=?', (sid,)).fetchone() is not None


def revoke(identity):
    if not identity.get('sid'):
        return
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO revoked_sessions VALUES (?, ?)', (identity['sid'], identity['exp']))
        db.execute('DELETE FROM revoked_sessions WHERE expires < ?', (time.time() - 86400,))
