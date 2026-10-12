"""Shared identity rules, using the existing users collection and numeric IDs."""
import re
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from backend.database.mongodb import users_collection, db

READER_ROLE = 'GENERAL_USER'
STAFF_ROLES = ('ADMIN', 'LIBRARIAN')
ROLES = (READER_ROLE, *STAFF_ROLES)

def normalize_email(email):
    return str(email).strip().lower()

def find_user_by_email(email):
    # Legacy addresses remain unchanged. Ambiguous case variants fail closed.
    matches = list(users_collection.find({'email': {'$regex': '^' + re.escape(normalize_email(email)) + '$', '$options': 'i'}}).limit(2))
    return matches[0] if len(matches) == 1 else None

def email_exists(email):
    return users_collection.find_one({'email': {'$regex': '^' + re.escape(normalize_email(email)) + '$', '$options': 'i'}}, {'_id':1}) is not None

def ensure_identity_indexes():
    indexes = list(users_collection.list_indexes())
    for field in ('email', 'user_id'):
        if not any(dict(i['key']) == {field:1} and i.get('unique') and not i.get('partialFilterExpression') for i in indexes):
            raise RuntimeError('Required unique user indexes are missing. An operator must review the schema; no indexes were changed.')

def next_user_id():
    ensure_identity_indexes()
    # Establish a floor, atomically, without changing any existing user IDs.
    latest = users_collection.find_one({}, {'user_id':1}, sort=[('user_id',-1)])
    floor = latest['user_id'] if latest else 0
    if not isinstance(floor, int) or isinstance(floor, bool) or floor < 0:
        raise RuntimeError('Existing numeric user IDs need operator review.')
    counters = db['counters']
    try:
        counters.update_one({'_id':'users'}, {'$max':{'seq':floor}}, upsert=True)
    except DuplicateKeyError:
        counters.update_one({'_id':'users'}, {'$max':{'seq':floor}})
    counter = counters.find_one_and_update({'_id':'users'}, {'$inc':{'seq':1}}, return_document=ReturnDocument.AFTER)
    if not counter or not isinstance(counter.get('seq'), int):
        raise RuntimeError('User ID counter is unavailable.')
    return counter['seq']

def public_user(user):
    return {key:user[key] for key in ('user_id','name','email','role','is_email_verified')}

def current_identity(payload):
    user_id = int(payload['sub'])
    if user_id < 1: return None
    user = users_collection.find_one({'user_id':user_id}, {
        '_id':0, 'email':1, 'role':1, 'is_email_verified':1,
        'is_active':1, 'password_setup_required':1,
    })
    if (not user or user.get('role') not in ROLES or not user.get('is_email_verified')
            or user.get('is_active', True) is not True or user.get('password_setup_required',False)):
        return None
    return {**payload, 'sub':str(user_id), 'role':user['role'], 'email':user['email']}
