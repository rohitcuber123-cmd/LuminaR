import secrets
from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError
from backend.database.mongodb import users_collection
from backend.services.auth_service import hash_password, resend_verification_otp
from backend.services.identity_service import normalize_email, email_exists, next_user_id, STAFF_ROLES
from backend.utils.security_audit import security_event

STAFF_FIELDS = {'_id':0,'user_id':1,'name':1,'email':1,'role':1,'is_email_verified':1,'is_active':1,'created_at':1}

def staff_record(user):
    return {**{key:user.get(key) for key in STAFF_FIELDS if key != '_id'}, 'is_active':user.get('is_active', True)}

def list_staff(limit, offset):
    query={'role':{'$in':list(STAFF_ROLES)}}
    rows=users_collection.find(query, STAFF_FIELDS).sort('user_id',1).skip(offset).limit(limit)
    return {'users':[staff_record(user) for user in rows], 'count':users_collection.count_documents(query),
            'librarian_count':users_collection.count_documents({'role':'LIBRARIAN'}), 'limit':limit,'offset':offset}

def create_librarian(name, email, actor_id):
    email=normalize_email(email)
    if email_exists(email): raise ValueError('Email already registered. Existing accounts are unchanged.')
    user={'user_id':next_user_id(), 'name':name.strip(), 'email':email,
          'password_hash':hash_password(secrets.token_urlsafe(32)), 'role':'LIBRARIAN',
          'is_email_verified':False, 'is_active':True, 'password_setup_required':True,
          'created_at':datetime.now(timezone.utc)}
    try:
        users_collection.insert_one(user)
    except DuplicateKeyError:
        raise ValueError('Email or identifier already registered. Existing accounts are unchanged.') from None
    security_event('librarian_created', actor_id, user['user_id'])
    try:
        resend_verification_otp(email)
        sent=True
    except (RuntimeError, ValueError):
        sent=False
    return {'user':staff_record(user), 'verification_sent':sent}

def librarian(user_id):
    user=users_collection.find_one({'user_id':user_id, 'role':'LIBRARIAN'}, STAFF_FIELDS)
    if not user: raise LookupError('Librarian not found.')
    return user

def update_librarian(user_id, changes, actor_id):
    librarian(user_id)
    allowed={key:value for key,value in changes.items() if key in ('name','is_active') and value is not None}
    if not allowed: raise ValueError('No supported changes supplied.')
    users_collection.update_one({'user_id':user_id,'role':'LIBRARIAN'}, {'$set':allowed})
    action='librarian_updated'
    if 'is_active' in allowed: action='librarian_enabled' if allowed['is_active'] else 'librarian_disabled'
    security_event(action, actor_id, user_id)
    return staff_record(librarian(user_id))

def resend_librarian_verification(user_id, actor_id):
    user=librarian(user_id)
    if not user.get('is_active',True): raise ValueError('Enable this librarian before sending verification.')
    resend_verification_otp(user['email'])
    security_event('librarian_verification_resent', actor_id, user_id)
    return {'message':'Verification email sent.'}
