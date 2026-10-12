"""Global identity administration; never grants platform roles or library membership."""
import re
import secrets
from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError
from backend.services import identity_service as identities
from backend.services.auth_service import hash_password, resend_verification_otp
from backend.utils.security_audit import security_event

FIELDS = {'_id': 0, 'user_id': 1, 'name': 1, 'email': 1, 'role': 1, 'is_email_verified': 1, 'is_active': 1, 'created_at': 1}


def collection():
    from backend.database.mongodb import db
    return db.users


def public(row):
    return {**{key: row.get(key) for key in FIELDS if key != '_id'}, 'is_active': row.get('is_active', True)}


def directory(limit, offset, q=''):
    query = {'$or': [{'email': {'$regex': re.escape(q), '$options': 'i'}}, {'name': {'$regex': re.escape(q), '$options': 'i'}}]} if q else {}
    return {'users': [public(u) for u in collection().find(query, FIELDS).sort('user_id', 1).skip(offset).limit(limit)],
            'count': collection().count_documents(query), 'limit': limit, 'offset': offset}


def create(name, email, actor):
    email = identities.normalize_email(email)
    if identities.email_exists(email):
        raise ValueError('Email already registered. Existing accounts are unchanged.')
    user = {'user_id': identities.next_user_id(), 'name': name.strip(), 'email': email,
            'password_hash': hash_password(secrets.token_urlsafe(32)), 'role': 'GENERAL_USER',
            'is_email_verified': False, 'is_active': True, 'password_setup_required': True,
            'created_at': datetime.now(timezone.utc)}
    try:
        collection().insert_one(user)
    except DuplicateKeyError:
        raise ValueError('Account identity already exists.') from None
    security_event('platform_account_created', actor, user['user_id'])
    try:
        resend_verification_otp(email)
        sent = True
    except (RuntimeError, ValueError):
        sent = False
    return {'user': public(user), 'verification_sent': sent, 'library_membership_granted': False, 'platform_role_granted': False}


def account(user_id):
    row = collection().find_one({'user_id': user_id}, FIELDS)
    if not row:
        raise LookupError('Account not found.')
    return row


def update(user_id, changes, actor):
    account(user_id)
    allowed = {key: value for key, value in changes.items() if key in ('name', 'is_active') and value is not None}
    if not allowed:
        raise ValueError('No supported changes supplied.')
    if user_id == actor and allowed.get('is_active') is False:
        raise ValueError('You cannot disable your own account.')
    collection().update_one({'user_id': user_id}, {'$set': allowed})
    security_event('platform_account_updated', actor, user_id)
    return public(account(user_id))


def resend(user_id, actor):
    row = account(user_id)
    if not row.get('is_active', True):
        raise ValueError('Enable this account before sending verification.')
    resend_verification_otp(row['email'])
    security_event('platform_account_verification_resent', actor, user_id)
    return {'message': 'Verification email sent.'}
