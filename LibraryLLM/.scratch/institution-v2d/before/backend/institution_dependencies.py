"""Reusable tenant guards for Institution V1 and future private resources."""
from fastapi import HTTPException

from backend.services.institution_repository import collection, require_readable


def actor_id(current_user):
    # JWT is authenticated upstream; identity is the existing canonical numeric user_id.
    try:
        value = int(current_user['sub'])
        if value < 1:
            raise ValueError()
        return value
    except (KeyError, TypeError, ValueError):
        raise HTTPException(401, 'Invalid account identity.')


def resolve_library_membership(library_id, current_user, *, locked=False):
    library = collection('libraries').find_one({'library_id': library_id, 'status': 'ACTIVE'})
    if not library:
        raise HTTPException(404, 'Library not found.')
    if not locked:
        require_readable(library_id)
    membership = collection('memberships').find_one({
        'library_id': library_id, 'user_id': actor_id(current_user), 'status': 'ACTIVE',
    })
    if membership and membership.get('grant_invitation_id'):
        proof = collection('invitations').find_one({
            'library_id': library_id, 'invitation_id': membership['grant_invitation_id'],
            'status': 'ACCEPTED', 'accepted_by_user_id': actor_id(current_user),
        })
        if not proof:
            membership = None
    if not locked:
        require_readable(library_id)
    return library, membership


def require_library_membership(library_id, current_user, *, locked=False):
    library, membership = resolve_library_membership(library_id, current_user, locked=locked)
    if not membership:
        # Conceal the existence of protected resources from outsiders, including global admins.
        raise HTTPException(404, 'Library resource not found.')
    return library, membership


def require_library_role(library_id, current_user, *roles, locked=False):
    library, membership = require_library_membership(library_id, current_user, locked=locked)
    if membership['role'] not in roles:
        raise HTTPException(403, 'Insufficient library permissions.')
    return library, membership


def require_library_staff(library_id, current_user, *, locked=False):
    return require_library_role(library_id, current_user, 'ADMIN', 'LIBRARIAN', locked=locked)


def require_library_patron(library_id, current_user, *, locked=False):
    """Personal library operations belong to an active GENERAL_USER membership."""
    return require_library_role(library_id, current_user, 'GENERAL_USER', locked=locked)


def require_library_owner(library_id, current_user, *, locked=False):
    library, membership = require_library_role(library_id, current_user, 'ADMIN', locked=locked)
    if library['owner_user_id'] != actor_id(current_user):
        raise HTTPException(403, 'Only the library owner can perform this action.')
    return library, membership
