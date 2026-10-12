"""Dry-run by default. Add only library identity/memberships; never domain tenancy.

Direct Mongo client on dry-run avoids importing modules with startup index writes.
"""
import argparse
import getpass
import json
import os
import re
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from pymongo import MongoClient, ReturnDocument

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def plan(database, *, name, slug, access_mode, owner_user_id=None, owner_email=None):
    users = list(database.users.find({}, {'_id': 0, 'user_id': 1, 'role': 1, 'email': 1,
                                          'is_email_verified': 1, 'is_active': 1, 'password_setup_required': 1}))
    if not users:
        raise ValueError('No legacy accounts exist.')
    if owner_user_id is not None:
        owners = [u for u in users if u['user_id'] == owner_user_id]
    elif owner_email:
        owners = [u for u in users if u.get('email', '').strip().lower() == owner_email.strip().lower()]
    else:
        owners = [u for u in users if u.get('role') == 'ADMIN']
    if len(owners) != 1:
        raise ValueError('Select exactly one owner using --owner-user-id or --owner-email; no owner was guessed.')
    owner = owners[0]
    if not owner.get('is_email_verified') or owner.get('is_active', True) is not True or owner.get('password_setup_required'):
        raise ValueError('The owner must have an active, verified account with completed password setup.')
    if any(not isinstance(u.get('user_id'), int) or isinstance(u['user_id'], bool) or u['user_id'] < 1 or u.get('role') not in ('ADMIN', 'LIBRARIAN', 'GENERAL_USER') for u in users):
        raise ValueError('Legacy account IDs or roles require operator review.')
    if len({u['user_id'] for u in users}) != len(users):
        raise ValueError('Duplicate canonical user IDs require operator review.')
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug) or not 3 <= len(slug) <= 80:
        raise ValueError('Use a normalized slug of 3 to 80 characters.')
    if not 2 <= len(name.strip()) <= 200:
        raise ValueError('Library name must contain 2 to 200 characters.')
    marker = database.institution_migrations.find_one({'_id': 'legacy-v1'})
    if marker:
        if marker['owner_user_id'] != owner['user_id'] or marker['slug'] != slug or marker['access_mode'] != access_mode:
            raise ValueError('Migration configuration differs from its saved identity; do not reassign an existing library.')
        library_id = marker['library_id']
    else:
        if database.institution_libraries.find_one({'slug_normalized': slug}):
            raise ValueError('Slug belongs to an existing library; choose another slug.')
        library_id = str(uuid4())
    roles = {str(u['user_id']): ('ADMIN' if u['user_id'] == owner['user_id'] else u['role']) for u in users}
    return {'library_id': library_id, 'name': name.strip(), 'slug': slug, 'owner_user_id': owner['user_id'],
            'access_mode': access_mode, 'memberships': roles, 'already_applied': bool(marker and marker.get('complete')),
            'domain_data_migrated': False}


def apply_plan(database, proposed, access_code=None):
    os.environ['MONGO_DB_NAME'] = database.name
    # Import only after explicit --apply. Redirect the repository to the selected DB.
    from backend.services import institution_repository as repo
    from backend.services.institution_security import hash_code
    from backend.services.institution_service import membership_document
    repo.db = database
    repo.ensure_indexes()
    marker = database.institution_migrations.find_one_and_update({'_id': 'legacy-v1'}, {'$setOnInsert': {
        'library_id': proposed['library_id'], 'owner_user_id': proposed['owner_user_id'],
        'slug': proposed['slug'], 'access_mode': proposed['access_mode'], 'created_at': repo.now(),
    }}, upsert=True, return_document=ReturnDocument.AFTER)
    library_id = marker['library_id']
    if marker['owner_user_id'] != proposed['owner_user_id'] or marker['slug'] != proposed['slug'] or marker['access_mode'] != proposed['access_mode']:
        raise ValueError('Another migration reserved a different configuration.')
    if marker.get('complete'):
        return {'library_id': library_id, 'already_applied': True, 'memberships_created': 0}
    existing = repo.collection('libraries').find_one({'library_id': library_id})
    security = repo.collection('security').find_one({'library_id': library_id})
    if proposed['access_mode'] == 'private' and not (security and security.get('access_code_hash')) and not access_code:
        raise ValueError('Private migration requires an interactive access code.')
    encoded = hash_code(access_code) if proposed['access_mode'] == 'private' and not security else None
    count = 0
    with repo.library_mutation(library_id):
        if not existing:
            stamp = repo.now()
            mode = 'PUBLIC' if proposed['access_mode'] == 'public' else 'PRIVATE_CODE'
            repo.collection('libraries').insert_one({'library_id': library_id, 'name': proposed['name'], 'slug': proposed['slug'],
                'slug_normalized': proposed['slug'], 'owner_user_id': proposed['owner_user_id'], 'description': 'Legacy LuminaR installation',
                'library_type': 'PUBLIC_LIBRARY' if mode == 'PUBLIC' else 'PRIVATE_INSTITUTION', 'access_mode': mode,
                'status': 'PROVISIONING', 'created_at': stamp, 'updated_at': stamp})
        repo.collection('security').update_one({'library_id': library_id}, {'$setOnInsert': {
            'library_id': library_id, 'access_code_hash': encoded, 'access_code_changed_at': repo.now() if encoded else None,
            'access_code_changed_by': proposed['owner_user_id'] if encoded else None}}, upsert=True)
        for user_id, role in proposed['memberships'].items():
            result = repo.collection('memberships').update_one({'library_id': library_id, 'user_id': int(user_id)},
                {'$setOnInsert': membership_document(library_id, int(user_id), role, proposed['owner_user_id'])}, upsert=True)
            count += result.upserted_id is not None
        owner = repo.collection('memberships').find_one({'library_id': library_id, 'user_id': proposed['owner_user_id'], 'role': 'ADMIN', 'status': 'ACTIVE'})
        if not owner:
            raise ValueError('Owner membership requires operator recovery; existing roles were not overwritten.')
        repo.audit(library_id, 'LIBRARY_REGISTERED', proposed['owner_user_id'], metadata={'migration': 'legacy-v1'}, event_id='migration:legacy-v1')
        repo.collection('libraries').update_one({'library_id': library_id}, {'$set': {'status': 'ACTIVE'}})
        database.institution_migrations.update_one({'_id': 'legacy-v1'}, {'$set': {'complete': True, 'completed_at': repo.now()}})
    return {'library_id': library_id, 'memberships_created': count, 'already_applied': False}


def main():
    load_dotenv(ROOT / '.env')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Explicitly write the selected database.')
    parser.add_argument('--database', default=os.getenv('MONGO_DB_NAME', 'luminar_library'))
    parser.add_argument('--name', default='LuminaR Legacy Library')
    parser.add_argument('--slug', default='luminar-legacy-library')
    parser.add_argument('--access-mode', choices=['public', 'private'], required=True)
    owner = parser.add_mutually_exclusive_group()
    owner.add_argument('--owner-user-id', type=int)
    owner.add_argument('--owner-email')
    parser.add_argument('--prompt-access-code', action='store_true')
    args = parser.parse_args()
    database = MongoClient(os.getenv('MONGO_URI', 'mongodb://127.0.0.1:27017'), serverSelectionTimeoutMS=5000)[args.database]
    try:
        proposed = plan(database, name=args.name, slug=args.slug, access_mode=args.access_mode,
                        owner_user_id=args.owner_user_id, owner_email=args.owner_email)
        code = None
        if args.apply and args.access_mode == 'private' and not proposed['already_applied']:
            if not args.prompt_access_code:
                raise ValueError('Use --prompt-access-code for private apply; never put entry secrets in shell arguments.')
            code = getpass.getpass('New institution access code: ')
            if code != getpass.getpass('Confirm institution access code: '):
                raise ValueError('Access codes do not match.')
        result = apply_plan(database, proposed, code) if args.apply else proposed
        print(json.dumps({'mode': 'APPLY' if args.apply else 'DRY_RUN', 'database': args.database, **result}, indent=2))
    except ValueError as error:
        parser.exit(2, str(error) + '\n')
    finally:
        database.client.close()


if __name__ == '__main__':
    main()
