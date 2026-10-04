"""Local-only first administrator creation; never run automatically."""
import argparse
import getpass
import secrets
from datetime import datetime, timezone
from pydantic import TypeAdapter, EmailStr, ValidationError
from pymongo.errors import DuplicateKeyError
from backend.database.mongodb import users_collection, db
from backend.services.auth_service import hash_password
from backend.services.identity_service import email_exists, normalize_email, next_user_id, ensure_identity_indexes
from backend.utils.security_audit import security_event

def bootstrap_first_admin(name, email, password):
    email = normalize_email(TypeAdapter(EmailStr).validate_python(email.strip()))
    if not name.strip() or len(name.strip()) > 120:
        raise ValueError('Name must contain 1–120 characters.')
    if len(password) < 8 or len(password.encode('utf-8')) > 72:
        raise ValueError('Password must contain at least 8 characters and at most 72 UTF-8 bytes.')
    ensure_identity_indexes()
    if email_exists(email):
        raise ValueError('Email already registered. No existing account was changed.')
    if users_collection.find_one({'role':'ADMIN'}, {'_id':1}):
        raise ValueError('An administrator already exists. First-admin bootstrap is closed.')
    owner = secrets.token_hex(16)
    marker = {'_id':'first_admin_bootstrap', 'owner':owner, 'created_at':datetime.now(timezone.utc)}
    try:
        db['counters'].insert_one(marker)
    except DuplicateKeyError:
        raise ValueError('Bootstrap is already completed or in progress. No account was changed.') from None
    created = False
    try:
        if users_collection.find_one({'role':'ADMIN'}, {'_id':1}):
            raise ValueError('An administrator already exists. First-admin bootstrap is closed.')
        user = {'user_id':next_user_id(), 'name':name.strip(), 'email':email,
                'password_hash':hash_password(password), 'role':'ADMIN',
                'is_email_verified':True, 'is_active':True, 'created_at':datetime.now(timezone.utc)}
        try:
            users_collection.insert_one(user)
        except DuplicateKeyError:
            raise ValueError('Email or identifier already registered. No account was changed.') from None
        created = True
        security_event('admin_bootstrap_created', target_id=user['user_id'])
        return {'email':email,'role':'ADMIN'}
    finally:
        if not created:
            db['counters'].delete_one({'_id':marker['_id'], 'owner':owner})

def main():
    parser = argparse.ArgumentParser(description='Create the first LuminaR administrator locally.')
    parser.add_argument('--email')
    parser.add_argument('--name')
    args, unknown = parser.parse_known_args()
    if unknown:
        parser.exit(1, 'Unsupported options. Enter passwords only at the private prompt.\n')
    try:
        email = args.email or input('Administrator email: ')
        name = args.name or input('Administrator name: ')
        password = getpass.getpass('Password: ')
        if password != getpass.getpass('Confirm password: '):
            raise ValueError('Passwords do not match.')
        result = bootstrap_first_admin(name, email, password)
    except (ValueError, RuntimeError, ValidationError) as error:
        parser.exit(1, f'{error}\n')
    except Exception:
        parser.exit(1, 'Bootstrap could not complete. Check database availability and operator logs; no secrets are printed.\n')
    print('Created administrator')
    print('email:', result['email'])
    print('role: ADMIN')

if __name__ == '__main__':
    main()
