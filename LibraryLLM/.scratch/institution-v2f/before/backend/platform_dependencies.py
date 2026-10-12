"""Installation authority is explicit and independent of User.role and library membership."""
from datetime import datetime, timezone
from fastapi import Depends, HTTPException
from backend.dependencies import get_current_user
from backend.services import identity_service


def platform_assignments(user_id):
    from backend.database.mongodb import db
    now = datetime.now(timezone.utc)
    result = []
    for row in db['platform_role_assignments'].find({'user_id': int(user_id), 'role': 'PLATFORM_ADMIN', 'status': 'ACTIVE'}):
        # An imported legacy role or incomplete grant document is never authority.
        if not all(isinstance(row.get(key),str) and row[key].strip() for key in ('approval_ref','approved_by')) or not isinstance(row.get('approved_at'),datetime):
            continue
        approved = row['approved_at'].replace(tzinfo=row['approved_at'].tzinfo or timezone.utc)
        if approved > now:
            continue
        expires = row.get('expires_at')
        if expires is not None:
            if not isinstance(expires, datetime) or expires.replace(tzinfo=expires.tzinfo or timezone.utc) <= now:
                continue
        result.append(row)
    return result


def current_account(payload):
    try:
        identity = identity_service.current_identity(payload)
    except (ValueError, KeyError, TypeError):
        identity = None
    if not identity:
        raise HTTPException(401, 'Account is unavailable.')
    return identity


def has_platform_admin(payload):
    identity = current_account(payload)
    return bool(platform_assignments(identity['sub']))


def require_platform_admin(payload=Depends(get_current_user)):
    identity = current_account(payload)
    if not platform_assignments(identity['sub']):
        raise HTTPException(403, 'An active, explicitly approved PLATFORM_ADMIN assignment is required.')
    return identity


def ensure_indexes():
    from backend.database.mongodb import db
    db['platform_role_assignments'].create_index([('user_id', 1), ('role', 1)], unique=True)


def retirement():
    raise HTTPException(410, 'Legacy circulation is read-only. Use an explicitly selected library workspace and its canonical API.')
