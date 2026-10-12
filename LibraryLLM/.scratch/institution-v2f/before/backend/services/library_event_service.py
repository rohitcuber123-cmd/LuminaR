"""Tenant authorization and lifecycle boundary around the shared Events V1 service."""
from fastapi import HTTPException
from backend.institution_dependencies import resolve_library_membership, require_library_staff
from backend.services.library_inventory_access import eligible_actor
from backend.services.institution_repository import collection, library_mutation
from backend.services import event_service as events


def ensure_indexes():
    events.events.create_index([('library_id', 1), ('status', 1), ('start_at', 1)])
    events.events.create_index([('library_id', 1), ('updated_at', -1), ('event_id', 1)])


def access(library_id, actor, *, staff=False, locked=False):
    identity = eligible_actor(actor)
    if staff:
        return require_library_staff(library_id, identity, locked=locked)
    return resolve_library_membership(library_id, identity, locked=locked)


def public_library(library):
    return library['library_type'] == 'PUBLIC_LIBRARY' and library['access_mode'] == 'PUBLIC'


def listing(library_id, actor, view, category, query, page, page_size, *, staff=False, status=None):
    # Workspace summaries also use this gate. Wait for them instead of exposing
    # a transient 503 during an ordinary concurrent page load.
    with library_mutation(library_id, wait_seconds=30):
        library, member = access(library_id, actor, staff=staff, locked=True)
        if not member and not public_library(library):
            raise HTTPException(404, 'Library resource not found.')
        result = events.listing(view, category, query, None, page, page_size, status, 'updated', staff,
                                library_id=library_id, public_only=not bool(member))
    return result


def detail(library_id, event_id, actor, *, staff=False):
    with library_mutation(library_id, wait_seconds=30):
        library, member = access(library_id, actor, staff=staff, locked=True)
        row = events.document(event_id, library_id)
        if not staff and (row['status'] not in {'PUBLISHED', 'CANCELLED'} or not row.get('published_at') or
                          not member and not (public_library(library) and row.get('visibility') == 'PUBLIC')):
            raise HTTPException(404, 'Event not found.')
        value = events.hydrate([row], staff)[0]
    return value


def mutate(library_id, actor, operation, *, body=None, event_id=None):
    # Single event document changes are atomic. Shared gate serializes membership
    # revocation and platform suspension with authorization and the event write.
    with library_mutation(library_id, durable=True):
        library, _ = access(library_id, actor, staff=True, locked=True)
        if body and getattr(body, 'visibility', None) == 'PUBLIC' and not public_library(library):
            raise HTTPException(422, 'Private institution events must be restricted to library members.')
        uid = int(actor['sub'])
        if operation == 'create':
            value = events.create(body, uid, library_id)
        elif operation == 'edit':
            value = events.edit(event_id, body, uid, library_id)
        elif operation == 'delete':
            value = events.delete_draft(event_id, library_id)
        else:
            old = events.document(event_id, library_id)
            if operation == 'publish' and old.get('visibility') == 'PUBLIC' and not public_library(library):
                raise HTTPException(422, 'Private institution events must be restricted to library members.')
            value = events.transition(event_id, operation, uid, library_id, getattr(body, 'reason', None))
    return value
