"""Keep global compatibility mutations away from explicitly canonical tenants."""
from fastapi import HTTPException
from backend.database.mongodb import db
from backend.services.institution_repository import collection


def blocked(library_id):
    alias = collection('library_aliases').find_one({'legacy_library_id': library_id})
    identity = alias['canonical_library_id'] if alias else library_id
    config = collection('v2c_config').find_one({'library_id': identity})
    if config and config.get('state') in ['PREPARING', 'CANONICAL', 'RECOVERY_REQUIRED']:
        raise HTTPException(409, 'Use the selected library’s reservations and fees API.')


def guard_reserve(user_id):
    for member in collection('memberships').find({'user_id': user_id, 'status': 'ACTIVE'}):
        blocked(member['library_id'])


def guard_reservation(row):
    if collection('reservations').find_one({'legacy_reservation_id': row['reservation_id']}):
        raise HTTPException(409, 'This reservation was migrated. Use its canonical library queue.')
    if row.get('library_id'):
        blocked(row['library_id'])


def guard_fee(row):
    if collection('fees').find_one({'legacy_fine_id': row['fine_id']}):
        raise HTTPException(409, 'This fine was migrated. Library staff must record payment against the canonical fee.')
    issue = db.issues.find_one({'issue_id': row.get('issue_id')}) or {}
    loan = collection('loans').find_one({'legacy_issue_id': row.get('issue_id')})
    if loan:
        blocked(loan['library_id'])
    if row.get('library_id') or issue.get('library_id'):
        blocked(row.get('library_id') or issue.get('library_id'))
