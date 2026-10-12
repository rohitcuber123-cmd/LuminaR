"""Additive multi-library services. Global domain services remain unchanged."""
import os
import re
from datetime import timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from backend.database.mongodb import users_collection
from backend.institution_dependencies import (
    actor_id, require_library_membership, require_library_role, require_library_staff,
)
from backend.services.identity_service import find_user_by_email, normalize_email
from backend.services.institution_repository import collection, now, audit, library_mutation, require_readable
from backend.services.institution_security import hash_code, verify_code, invitation_token, token_hash
from backend.schemas.institution_models import Library, LibraryMembership, LibraryInvitation


LIBRARY_FIELDS = ('library_id', 'name', 'slug', 'description', 'library_type', 'access_mode',
                  'contact_email', 'phone', 'address', 'status', 'created_at', 'updated_at')
MEMBERSHIP_FIELDS = ('membership_id', 'library_id', 'user_id', 'role', 'status', 'joined_at', 'created_at', 'updated_at')
INVITATION_FIELDS = ('invitation_id', 'library_id', 'email_normalized', 'role', 'invited_by_user_id',
                     'status', 'created_at', 'expires_at', 'accepted_at', 'revoked_at')


def public_library(row):
    return {k: row.get(k) for k in LIBRARY_FIELDS}


def public_membership(row, library):
    return {**{k: row.get(k) for k in MEMBERSHIP_FIELDS}, 'is_owner': row['user_id'] == library['owner_user_id']}


def public_invitation(row):
    result = {k: row.get(k) for k in INVITATION_FIELDS}
    expiry = row['expires_at'].replace(tzinfo=timezone.utc) if row['expires_at'].tzinfo is None else row['expires_at']
    if row['status'] == 'PENDING' and expiry <= now():
        result['status'] = 'EXPIRED'
    return result


def get_library(library_id):
    row = collection('libraries').find_one({'library_id': library_id, 'status': 'ACTIVE'})
    if not row:
        raise HTTPException(404, 'Library not found.')
    return row


def membership_document(library_id, user_id, role='GENERAL_USER', created_by=None):
    stamp = now()
    return {'membership_id': str(uuid4()), 'library_id': library_id, 'user_id': user_id,
            'role': role, 'status': 'ACTIVE', 'joined_at': stamp, 'created_at': stamp,
            'updated_at': stamp, 'created_by_user_id': created_by}


def register_library(request, current_user):
    user_id = actor_id(current_user)
    library_id = str(uuid4())
    stamp = now()
    data = request.model_dump(mode='json', exclude={'access_code'})
    row = {**data, 'library_id': library_id, 'slug': data['slug'].lower(),
           'slug_normalized': data['slug'].lower(), 'owner_user_id': user_id,
           'status': 'PROVISIONING', 'created_at': stamp, 'updated_at': stamp}
    encoded = hash_code(request.access_code.get_secret_value()) if request.access_code else None
    member = membership_document(library_id, user_id, 'ADMIN', user_id)
    Library.model_validate(row)
    LibraryMembership.model_validate(member)
    with library_mutation(library_id, durable=True):
        try:
            collection('libraries').insert_one(row)
        except DuplicateKeyError:
            raise HTTPException(409, 'Library slug is already in use.')
        # PROVISIONING is undiscoverable until all authoritative documents exist.
        collection('security').insert_one({'library_id': library_id, 'access_code_hash': encoded,
            'access_code_changed_at': stamp if encoded else None,
            'access_code_changed_by': user_id if encoded else None})
        collection('memberships').insert_one(member)
        from backend.services.library_canonical_defaults import initialize_new
        initialize_new(library_id, user_id)
        audit(library_id, 'LIBRARY_REGISTERED', user_id, membership_id=member['membership_id'], event_id='registration:' + library_id)
        collection('libraries').update_one({'library_id': library_id, 'status': 'PROVISIONING'}, {'$set': {'status': 'ACTIVE'}})
    row['status'] = 'ACTIVE'
    return {'library': public_library(row), 'membership': public_membership(member, row)}


def discover(current_user, search='', kind='all', offset=0, limit=20):
    query = {'status': 'ACTIVE'}
    if search:
        literal = {'$regex': re.escape(search), '$options': 'i'}
        query['$or'] = [{k: literal} for k in ('name', 'slug_normalized', 'address.city', 'address.region')]
    if kind in ('public', 'private'):
        query['access_mode'] = 'PUBLIC' if kind == 'public' else 'PRIVATE_CODE'
    if kind == 'mine':
        # Bound result traversal in Mongo rather than building an unbounded client list.
        pipeline = [{'$match': {'user_id': actor_id(current_user), 'status': 'ACTIVE'}},
                    {'$lookup': {'from': collection('libraries').name, 'localField': 'library_id', 'foreignField': 'library_id', 'as': 'library'}},
                    {'$unwind': '$library'}, {'$replaceRoot': {'newRoot': '$library'}}, {'$match': query},
                    {'$sort': {'name': 1, 'library_id': 1}},
                    {'$facet': {'rows': [{'$skip': offset}, {'$limit': limit}], 'total': [{'$count': 'count'}]}}]
        result = list(collection('memberships').aggregate(pipeline))[0]
        rows, total = result['rows'], (result['total'][0]['count'] if result['total'] else 0)
    else:
        total = collection('libraries').count_documents(query)
        rows = list(collection('libraries').find(query).sort([('name', 1), ('library_id', 1)]).skip(offset).limit(limit))
    results = []
    for row in rows:
        membership = collection('memberships').find_one({'library_id': row['library_id'], 'user_id': actor_id(current_user)})
        results.append({**public_library(row), 'membership': public_membership(membership, row) if membership else None})
    return {'results': results, 'total': total, 'offset': offset, 'limit': limit, 'has_more': offset + len(rows) < total}


def my_libraries(current_user, offset=0, limit=100):
    user_id = actor_id(current_user)
    # Fetch one extra to communicate pagination; each row remains membership-guarded.
    rows = list(collection('memberships').find({'user_id': user_id, 'status': 'ACTIVE'}).sort('library_id', 1).skip(offset).limit(limit + 1))
    results = []
    for member in rows[:limit]:
        try:
            library, checked = require_library_membership(member['library_id'], current_user)
        except HTTPException as error:
            if error.status_code == 404:
                continue
            raise
        results.append({**public_library(library), 'membership': public_membership(checked, library)})
    return {'results': results, 'offset': offset, 'limit': limit, 'has_more': len(rows) > limit}


def consume_join_budget(library_id, user_id):
    stamp = now()
    window = max(60, int(os.getenv('LUMINAR_JOIN_WINDOW_SECONDS', '900')))
    bucket = int(stamp.timestamp()) // window
    for scope, cap in ((f'user:{user_id}:{library_id}', int(os.getenv('LUMINAR_JOIN_ATTEMPTS', '5'))),
                       (f'library:{library_id}', int(os.getenv('LUMINAR_LIBRARY_JOIN_ATTEMPTS', '200')))):
        key = f'{scope}:{bucket}'
        try:
            row = collection('attempts').find_one_and_update({'_id': key}, {
                '$inc': {'count': 1}, '$setOnInsert': {'expires_at': stamp + timedelta(seconds=window * 2)},
            }, upsert=True, return_document=ReturnDocument.AFTER)
        except DuplicateKeyError:
            row = collection('attempts').find_one_and_update({'_id': key}, {'$inc': {'count': 1}}, return_document=ReturnDocument.AFTER)
        if row['count'] > cap:
            retry = window - int(stamp.timestamp()) % window
            raise HTTPException(429, 'Too many join attempts. Please try again later.', headers={'Retry-After': str(retry)})


def join_library(library_id, request, current_user):
    user_id = actor_id(current_user)
    library = get_library(library_id)
    require_readable(library_id)
    existing = collection('memberships').find_one({'library_id': library_id, 'user_id': user_id})
    if existing:
        if existing['status'] != 'ACTIVE':
            raise HTTPException(403, 'Membership requires staff action.')
        library, member = require_library_membership(library_id, current_user)
        return {'library': public_library(library), 'membership': public_membership(member, library)}
    encoded = None
    if library['access_mode'] == 'PRIVATE_CODE':
        consume_join_budget(library_id, user_id)
        security = collection('security').find_one({'library_id': library_id})
        encoded = security.get('access_code_hash') if security else None
        if not verify_code(encoded, request.access_code.get_secret_value() if request.access_code else None):
            audit(library_id, 'PRIVATE_LIBRARY_JOIN_FAILED', user_id)
            raise HTTPException(403, 'Invalid access code.')
    with library_mutation(library_id):
        library = get_library(library_id)
        # Recheck mode/hash after KDF: a concurrent code rotation cannot admit an old code.
        security = collection('security').find_one({'library_id': library_id})
        if library['access_mode'] == 'PRIVATE_CODE' and (not encoded or not security or security['access_code_hash'] != encoded):
            raise HTTPException(409, 'Library access changed. Please try joining again.')
        existing = collection('memberships').find_one({'library_id': library_id, 'user_id': user_id})
        if existing:
            if existing['status'] != 'ACTIVE':
                raise HTTPException(403, 'Membership requires staff action.')
            member = existing
        else:
            member = membership_document(library_id, user_id)
            collection('memberships').insert_one(member)
            event = 'PUBLIC_LIBRARY_JOINED' if library['access_mode'] == 'PUBLIC' else 'PRIVATE_LIBRARY_JOINED'
            audit(library_id, event, user_id, membership_id=member['membership_id'])
    return {'library': public_library(library), 'membership': public_membership(member, library)}


def access_settings(library_id, current_user):
    require_library_staff(library_id, current_user)
    row = collection('security').find_one({'library_id': library_id}) or {}
    return {k: row.get(k) for k in ('access_code_changed_at', 'access_code_changed_by')} | {'access_code_set': bool(row.get('access_code_hash'))}


def change_code(library_id, request, current_user):
    require_library_staff(library_id, current_user)
    encoded = hash_code(request.access_code.get_secret_value())
    with library_mutation(library_id):
        library, _ = require_library_staff(library_id, current_user, locked=True)
        if library['access_mode'] != 'PRIVATE_CODE':
            raise HTTPException(400, 'Access codes apply to private institutions only.')
        collection('security').update_one({'library_id': library_id}, {'$set': {
            'access_code_hash': encoded, 'access_code_changed_at': now(), 'access_code_changed_by': actor_id(current_user)}}, upsert=True)
        audit(library_id, 'ACCESS_CODE_CHANGED', actor_id(current_user))
    return access_settings(library_id, current_user)


def change_access(library_id, request, current_user):
    require_library_role(library_id, current_user, 'ADMIN')
    encoded = hash_code(request.access_code.get_secret_value()) if request.access_code else None
    with library_mutation(library_id):
        library, _ = require_library_role(library_id, current_user, 'ADMIN', locked=True)
        stamp = now()
        collection('security').update_one({'library_id': library_id}, {'$set': {
            'access_code_hash': encoded, 'access_code_changed_at': stamp, 'access_code_changed_by': actor_id(current_user)}}, upsert=True)
        mode = request.access_mode
        collection('libraries').update_one({'library_id': library_id}, {'$set': {
            'access_mode': mode, 'library_type': 'PUBLIC_LIBRARY' if mode == 'PUBLIC' else 'PRIVATE_INSTITUTION', 'updated_at': stamp}})
        audit(library_id, 'ACCESS_MODE_CHANGED', actor_id(current_user), metadata={'access_mode': mode, 'previous_access_mode': library['access_mode']})
        if encoded:
            audit(library_id, 'ACCESS_CODE_CHANGED', actor_id(current_user))
    return public_library(get_library(library_id))


def update_profile(library_id, request, current_user):
    with library_mutation(library_id):
        require_library_role(library_id, current_user, 'ADMIN', locked=True)
        collection('libraries').update_one({'library_id': library_id}, {'$set': {**request.model_dump(mode='json'), 'updated_at': now()}})
        audit(library_id, 'LIBRARY_PROFILE_UPDATED', actor_id(current_user))
    return public_library(get_library(library_id))


def check_staff_policy(library, current_user, target_role):
    if target_role == 'ADMIN' and library['owner_user_id'] != actor_id(current_user):
        raise HTTPException(403, 'Only the owner may manage admins.')


def expire_invitations(library_id=None):
    query = {'status': 'PENDING', 'expires_at': {'$lte': now()}}
    if library_id:
        query['library_id'] = library_id
    collection('invitations').update_many(query, {'$set': {'status': 'EXPIRED'}, '$unset': {'token_hash': ''}})


def invite_staff(library_id, request, current_user):
    email = normalize_email(request.email)
    raw = invitation_token()
    with library_mutation(library_id):
        library, _ = require_library_role(library_id, current_user, 'ADMIN', locked=True)
        check_staff_policy(library, current_user, request.role)
        expire_invitations(library_id)
        user = find_user_by_email(email)
        if user and user['user_id'] == library['owner_user_id']:
            raise HTTPException(403, 'The owner already has protected admin membership.')
        if user:
            existing = collection('memberships').find_one({'library_id': library_id, 'user_id': user['user_id']})
            if existing:
                check_staff_policy(library, current_user, existing['role'])
        row = {'invitation_id': str(uuid4()), 'library_id': library_id, 'email_normalized': email,
               'role': request.role, 'invited_user_id': user['user_id'] if user else None,
               'invited_by_user_id': actor_id(current_user), 'status': 'PENDING', 'token_hash': token_hash(raw),
               'created_at': now(), 'expires_at': now() + timedelta(days=max(1, int(os.getenv('LUMINAR_INVITE_DAYS', '7'))))}
        LibraryInvitation.model_validate(row)
        try:
            collection('invitations').insert_one(row)
        except DuplicateKeyError:
            raise HTTPException(409, 'A pending invitation already exists for this email.')
        audit(library_id, 'STAFF_INVITED', actor_id(current_user), target_email_normalized=email,
              metadata={'role': request.role, 'invitation_id': row['invitation_id']})
    # Raw token is returned exactly once, never echoed by list/detail/error routes.
    return {'invitation': public_invitation(row), 'invite_token': raw}


def pending_invitations(current_user, offset=0, limit=20):
    query = {'status': 'PENDING', 'expires_at': {'$gt': now()}, '$or': [
        {'invited_user_id': actor_id(current_user)},
        {'invited_user_id': None, 'email_normalized': normalize_email(current_user['email'])},
    ]}
    rows = list(collection('invitations').find(query).sort('created_at', -1).skip(offset).limit(limit))
    result = []
    for row in rows:
        library = collection('libraries').find_one({'library_id': row['library_id'], 'status': 'ACTIVE'})
        if library:
            result.append({**public_invitation(row), 'library_name': library['name'], 'requires_token': row['invited_user_id'] is None})
    return {'results': result, 'total': collection('invitations').count_documents(query)}


def invitation_for_account(invitation_id, request, current_user):
    row = collection('invitations').find_one({'invitation_id': invitation_id})
    if not row:
        raise HTTPException(404, 'Invitation not found.')
    user = users_collection.find_one({'user_id': actor_id(current_user), 'is_email_verified': True, 'is_active': {'$ne': False}})
    email = normalize_email(user.get('email', '')) if user else ''
    if not user or email != row['email_normalized'] or (row['invited_user_id'] is not None and row['invited_user_id'] != user['user_id']):
        raise HTTPException(404, 'Invitation not found.')
    if request.token:
        if token_hash(request.token.get_secret_value()) != row.get('token_hash'):
            raise HTTPException(404, 'Invitation not found.')
    elif row['invited_user_id'] is None:
        raise HTTPException(403, 'Open the invitation link to accept this invitation.')
    return row


def respond_invitation(invitation_id, request, current_user, accept=True):
    initial = invitation_for_account(invitation_id, request, current_user)
    library_id = initial['library_id']
    with library_mutation(library_id):
        row = invitation_for_account(invitation_id, request, current_user)
        if row['status'] != 'PENDING':
            raise HTTPException(409, 'Invitation is no longer pending.')
        expiry = row['expires_at'].replace(tzinfo=timezone.utc) if row['expires_at'].tzinfo is None else row['expires_at']
        if expiry <= now():
            collection('invitations').update_one({'invitation_id': invitation_id}, {'$set': {'status': 'EXPIRED'}, '$unset': {'token_hash': ''}})
            raise HTTPException(410, 'Invitation has expired.')
        library = get_library(library_id)
        user_id = actor_id(current_user)
        if not accept:
            audit(library_id, 'STAFF_INVITE_DECLINED', user_id, metadata={'invitation_id': invitation_id})
            collection('invitations').update_one({'invitation_id': invitation_id}, {'$set': {'status': 'DECLINED'}, '$unset': {'token_hash': ''}})
            return {'status': 'DECLINED'}
        # Stale invitations cannot preserve privileges after their inviter loses authority.
        inviter = {'sub': str(row['invited_by_user_id'])}
        require_library_role(library_id, inviter, 'ADMIN', locked=True)
        check_staff_policy(library, inviter, row['role'])
        inviter_account = users_collection.find_one({'user_id': row['invited_by_user_id'], 'is_active': {'$ne': False}, 'is_email_verified': True})
        if not inviter_account:
            raise HTTPException(403, 'Inviter no longer has authority.')
        existing = collection('memberships').find_one({'library_id': library_id, 'user_id': user_id})
        if user_id == library['owner_user_id']:
            raise HTTPException(403, 'Owner membership cannot be changed.')
        if existing:
            check_staff_policy(library, inviter, existing['role'])
        member = existing or membership_document(library_id, user_id, row['role'], row['invited_by_user_id'])
        member = {**member, 'role': row['role'], 'status': 'ACTIVE', 'updated_at': now(),
                  'grant_invitation_id': invitation_id, 'role_changed_by_user_id': row['invited_by_user_id']}
        # The grant is invisible to guards until the ACCEPTED proof is committed.
        collection('memberships').update_one({'library_id': library_id, 'user_id': user_id}, {'$set': {k: v for k, v in member.items() if k != '_id'}}, upsert=True)
        audit(library_id, 'STAFF_INVITE_ACCEPTED', user_id, membership_id=member['membership_id'],
              metadata={'role': row['role'], 'invitation_id': invitation_id}, event_id='invite-accepted:' + invitation_id)
        collection('invitations').update_one({'invitation_id': invitation_id, 'status': 'PENDING'}, {
            '$set': {'status': 'ACCEPTED', 'accepted_at': now(), 'accepted_by_user_id': user_id}, '$unset': {'token_hash': ''}})
    return {'library': public_library(library), 'membership': public_membership(member, library)}


def list_staff(library_id, current_user, offset=0, limit=20, staff_only=False):
    library, _ = require_library_role(library_id, current_user, 'ADMIN')
    query = {'library_id': library_id}
    if staff_only:
        query['role'] = {'$in': ['ADMIN', 'LIBRARIAN']}
    rows = list(collection('memberships').find(query).sort([('role', 1), ('joined_at', 1)]).skip(offset).limit(limit))
    users = {r['user_id']: r for r in users_collection.find({'user_id': {'$in': [r['user_id'] for r in rows]}}, {'_id': 0, 'user_id': 1, 'name': 1, 'email': 1})}
    results = [{**public_membership(r, library), 'name': users.get(r['user_id'], {}).get('name'), 'email': users.get(r['user_id'], {}).get('email')} for r in rows]
    require_readable(library_id)
    return {'results': results, 'total': collection('memberships').count_documents(query)}


def list_invitations(library_id, current_user, offset=0, limit=20):
    require_library_role(library_id, current_user, 'ADMIN')
    query = {'library_id': library_id}
    rows = list(collection('invitations').find(query).sort('created_at', -1).skip(offset).limit(limit))
    return {'results': [public_invitation(r) for r in rows], 'total': collection('invitations').count_documents(query)}


def revoke_invitation(library_id, invitation_id, current_user):
    with library_mutation(library_id):
        library, _ = require_library_role(library_id, current_user, 'ADMIN', locked=True)
        row = collection('invitations').find_one({'library_id': library_id, 'invitation_id': invitation_id})
        if not row:
            raise HTTPException(404, 'Invitation not found.')
        check_staff_policy(library, current_user, row['role'])
        if row['status'] != 'PENDING':
            raise HTTPException(409, 'Invitation is no longer pending.')
        audit(library_id, 'STAFF_INVITE_REVOKED', actor_id(current_user), metadata={'invitation_id': invitation_id})
        collection('invitations').update_one({'invitation_id': invitation_id}, {'$set': {
            'status': 'REVOKED', 'revoked_at': now(), 'revoked_by_user_id': actor_id(current_user)}, '$unset': {'token_hash': ''}})
    return {'status': 'REVOKED'}


def change_membership(library_id, membership_id, request, current_user):
    with library_mutation(library_id):
        library, _ = require_library_role(library_id, current_user, 'ADMIN', locked=True)
        target = collection('memberships').find_one({'library_id': library_id, 'membership_id': membership_id})
        if not target:
            raise HTTPException(404, 'Membership not found.')
        if target['user_id'] == library['owner_user_id']:
            raise HTTPException(403, 'Owner membership cannot be changed.')
        check_staff_policy(library, current_user, target['role'])
        role = request.role.value if request.role else target['role']
        status = request.status or target['status']
        check_staff_policy(library, current_user, role)
        owner = collection('memberships').find_one({'library_id': library_id, 'user_id': library['owner_user_id'], 'role': 'ADMIN', 'status': 'ACTIVE'})
        if not owner:
            raise HTTPException(409, 'Library owner membership requires recovery. Admin changes are blocked.')
        if target['role'] == 'ADMIN' and target['status'] == 'ACTIVE' and (role != 'ADMIN' or status != 'ACTIVE'):
            if collection('memberships').count_documents({'library_id': library_id, 'role': 'ADMIN', 'status': 'ACTIVE'}) <= 1:
                raise HTTPException(409, 'At least one active admin must remain.')
        changes = {'role': role, 'status': status, 'updated_at': now()}
        actor = actor_id(current_user)
        if role != target['role']:
            changes['role_changed_by_user_id'] = actor
            audit(library_id, 'STAFF_ROLE_CHANGED', actor, target_user_id=target['user_id'], membership_id=membership_id,
                  metadata={'role': role, 'previous_role': target['role']})
        if status != target['status']:
            event, field = {'SUSPENDED': ('STAFF_SUSPENDED', 'suspended_by_user_id'), 'REMOVED': ('STAFF_REMOVED', 'removed_by_user_id'), 'ACTIVE': ('STAFF_REACTIVATED', 'reactivated_by_user_id')}[status]
            changes[field] = actor
            audit(library_id, event, actor, target_user_id=target['user_id'], membership_id=membership_id,
                  metadata={'status': status, 'previous_status': target['status']})
        collection('memberships').update_one({'library_id': library_id, 'membership_id': membership_id}, {'$set': changes})
    return public_membership({**target, **changes}, library)


def audit_events(library_id, current_user, offset=0, limit=20):
    require_library_role(library_id, current_user, 'ADMIN')
    query = {'library_id': library_id}
    rows = list(collection('audit').find(query, {'_id': 0}).sort('created_at', -1).skip(offset).limit(limit))
    return {'results': rows, 'total': collection('audit').count_documents(query)}


OPERATION_EVENTS = r'^(LIBRARY_BOOK_|LIBRARY_COPY_|HOLDING_|STOCK_|SHELF_|COPY_|BORROW_|RETURN_|LOAN_|RESERVATION_|FEE_)'

def operational_activity(library_id, current_user, offset=0, limit=20):
    from backend.services.library_inventory_access import require_library_staff
    require_library_staff(library_id,current_user)
    query={'library_id':library_id,'event':{'$regex':OPERATION_EVENTS}}
    return {'results':list(collection('audit').find(query,{'_id':0}).sort('created_at',-1).skip(offset).limit(limit)),
            'total':collection('audit').count_documents(query)}
