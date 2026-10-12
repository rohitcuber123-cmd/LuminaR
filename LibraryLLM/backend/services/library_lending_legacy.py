"""Narrow cutover guard; no canonical inventory is ever written through legacy APIs."""
from fastapi import HTTPException
from contextlib import contextmanager, ExitStack
from backend.services.institution_repository import collection, require_readable, library_mutation


def blocked_library(library_id):
    aliases = collection('library_aliases').find_one({'legacy_library_id': library_id})
    canonical = aliases['canonical_library_id'] if aliases else library_id
    config = collection('lending_config').find_one({'library_id': canonical})
    if config and config.get('state') in ['PREPARING', 'CANONICAL', 'RECOVERY_REQUIRED']:
        raise HTTPException(409, 'Use this library’s approval circulation API.')


def guard_issue(user_id, library_id, *, locked=False):
    blocked_library(library_id)
    for member in collection('memberships').find({'user_id': user_id, 'status': 'ACTIVE'}):
        if not locked:
            require_readable(member['library_id'])
        config = collection('lending_config').find_one({'library_id': member['library_id']})
        if config and config.get('state') in ['PREPARING', 'CANONICAL', 'RECOVERY_REQUIRED']:
            raise HTTPException(409, 'Select your library inventory and Request Book for staff approval.')


@contextmanager
def legacy_gates(user_id, library_id):
    libraries = {m['library_id'] for m in collection('memberships').find({'user_id': user_id, 'status': 'ACTIVE'})}
    alias = collection('library_aliases').find_one({'legacy_library_id': library_id})
    if alias:
        libraries.add(alias['canonical_library_id'])
    if collection('libraries').find_one({'library_id': library_id}):
        libraries.add(library_id)
    with ExitStack() as stack:
        for identity in sorted(libraries):
            stack.enter_context(library_mutation(identity, wait_seconds=30))
        yield


def guard_loan(loan):
    if collection('loans').find_one({'legacy_issue_id': loan.get('issue_id')}):
        raise HTTPException(409, 'This historical issue has a canonical library loan; use approval circulation.')
    if loan.get('canonical_loan_id'):
        raise HTTPException(409, 'This historical issue was migrated; use its canonical library loan.')
    blocked_library(loan.get('library_id', 'LIB001'))
