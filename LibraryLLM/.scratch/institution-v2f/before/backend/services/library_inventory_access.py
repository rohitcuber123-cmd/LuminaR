"""Inventory checks current account eligibility before V1 tenant authority."""
from fastapi import HTTPException
from backend.institution_dependencies import require_library_membership as member_guard, require_library_staff as staff_guard, require_library_patron as patron_guard
from backend.services.identity_service import current_identity


def eligible_actor(actor):
    identity = current_identity(actor)
    if not identity:
        raise HTTPException(401, 'An active verified account is required.')
    return identity


def require_library_membership(library_id, actor, *, locked=False):
    result = member_guard(library_id, eligible_actor(actor), locked=locked)
    require_lending_readable(library_id)
    return result


def require_library_staff(library_id, actor, *, locked=False):
    result = staff_guard(library_id, eligible_actor(actor), locked=locked)
    require_lending_readable(library_id)
    return result


def require_library_patron(library_id, actor, *, locked=False):
    result = patron_guard(library_id, eligible_actor(actor), locked=locked)
    require_lending_readable(library_id)
    return result


def require_lending_readable(library_id):
    from backend.services.institution_repository import collection
    config = collection('lending_config').find_one({'library_id': library_id})
    if config and config.get('state') in ['PREPARING', 'RECOVERY_REQUIRED']:
        raise HTTPException(503, 'RECOVERY_REQUIRED: circulation cutover or recovery must complete before this library can be used.')
