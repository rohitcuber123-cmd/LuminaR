"""Reviewed, explicit grants only. Default is a dry run; no legacy role inference."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def positive(value):
    if type(value) is not int or value < 1:
        raise ValueError('user_id must be a positive integer.')
    return value


def reviewed(row):
    if row.get('approved') is not True or not all(isinstance(row.get(k), str) and row[k].strip() for k in ['approved_by', 'approval_ref', 'reason']):
        raise ValueError('Every grant needs explicit approved=true, approved_by, approval_ref and reason.')


def plan(database, mapping):
    if set(mapping) - {'platform_assignments', 'library_memberships'}:
        raise ValueError('Unsupported mapping section; classify it before applying.')
    grants, aliases, seen = [], [], set()
    for kind in ['platform_assignments', 'library_memberships']:
        rows = mapping.get(kind, [])
        if not isinstance(rows, list):
            raise ValueError('Mapping sections must be arrays.')
        for row in rows:
            allowed = {'user_id', 'role', 'approved', 'approved_by', 'approval_ref', 'reason'}
            if kind == 'library_memberships':
                allowed |= {'library_id', 'legacy_library_id'}
            if not isinstance(row, dict) or set(row) - allowed:
                raise ValueError('Unsupported grant field; review required.')
            reviewed(row)
            user_id = positive(row['user_id'])
            user = database.users.find_one({'user_id': user_id})
            if not user or user.get('is_active', True) is not True or not user.get('is_email_verified') or user.get('password_setup_required'):
                raise ValueError(f'Account {user_id} must exist, be active, verified and ready.')
            role = row.get('role')
            if kind == 'platform_assignments':
                if role != 'PLATFORM_ADMIN':
                    raise ValueError('Only explicit PLATFORM_ADMIN grants are supported.')
                key = (kind, user_id)
                old = database.platform_role_assignments.find_one({'user_id': user_id, 'role': role})
                query = {'user_id': user_id, 'role': role}
            else:
                if role not in {'ADMIN', 'LIBRARIAN'}:
                    raise ValueError('Explicit staff membership must be ADMIN or LIBRARIAN.')
                library_id = str(UUID(row['library_id']))
                if not database.institution_libraries.find_one({'library_id': library_id, 'status': 'ACTIVE'}):
                    raise ValueError('The explicitly mapped canonical library must already exist and be active.')
                key = (kind, user_id, library_id)
                query = {'user_id': user_id, 'library_id': library_id}
                old = database.institution_memberships.find_one(query)
                if row.get('legacy_library_id'):
                    alias_query = {'legacy_library_id': row['legacy_library_id']}
                    alias = database.institution_library_aliases.find_one(alias_query)
                    if alias and alias['canonical_library_id'] != library_id:
                        raise ValueError('Existing legacy alias conflicts with the approved mapping.')
                    aliases.append({**alias_query, 'canonical_library_id': library_id,
                                    'approval_ref': row['approval_ref'], 'approved_by': row['approved_by']})
            if key in seen:
                raise ValueError('Duplicate or conflicting grants in mapping.')
            seen.add(key)
            if old and (old.get('status') != 'ACTIVE' or old.get('role') != role):
                raise ValueError('Existing authority differs. Use its explicit revocation/change workflow; migration does not overwrite it.')
            if old and kind == 'platform_assignments' and (not old.get('approval_ref') or not old.get('approved_by') or not old.get('approved_at')):
                raise ValueError('Existing incomplete platform grant needs manual review.')
            grants.append({'kind': kind, 'query': query, 'role': role, 'already_present': bool(old),
                           'approved_by': row['approved_by'], 'approval_ref': row['approval_ref'], 'reason': row['reason']})
    # Conflicting aliases in the input must fail before any write.
    resolved = {}
    for row in aliases:
        if row['legacy_library_id'] in resolved and resolved[row['legacy_library_id']] != row['canonical_library_id']:
            raise ValueError('Conflicting legacy-library mappings in the approved file.')
        resolved[row['legacy_library_id']] = row['canonical_library_id']
    return {'grants': grants, 'aliases': aliases, 'automatic_grants': 0}


def apply(database, proposal):
    # Run only after full plan validation. No role is inferred and no existing grant is overwritten.
    from pymongo.errors import DuplicateKeyError
    lock = {'_id': 'management-authority', 'token': str(uuid4()), 'started_at': datetime.now(timezone.utc)}
    database.authority_migration_locks.insert_one(lock)
    try:
        for grant in proposal['grants']:
            stamp = datetime.now(timezone.utc)
            query = grant['query']
            row = {**query, 'role': grant['role'], 'status': 'ACTIVE', 'approved_by': grant['approved_by'],
                   'approval_ref': grant['approval_ref'], 'reason': grant['reason'], 'approved_at': stamp,
                   'created_at': stamp, 'updated_at': stamp}
            if grant['kind'] == 'platform_assignments':
                row['assignment_id'] = str(uuid4())
                target = database.platform_role_assignments
                target.create_index([('user_id', 1), ('role', 1)], unique=True)
            else:
                row.update({'membership_id': str(uuid4()), 'joined_at': stamp, 'created_by_user_id': None})
                target = database.institution_memberships
                target.create_index([('library_id', 1), ('user_id', 1)], unique=True)
            if grant['already_present']:
                continue
            try:
                target.insert_one(row)
            except DuplicateKeyError:
                raise RuntimeError('Authority changed during apply. Review the recorded grants before retrying.') from None
        database.institution_library_aliases.create_index('legacy_library_id', unique=True)
        for row in proposal['aliases']:
            database.institution_library_aliases.update_one({'legacy_library_id': row['legacy_library_id']}, {'$setOnInsert': row}, upsert=True)
            actual=database.institution_library_aliases.find_one({'legacy_library_id':row['legacy_library_id']})
            if actual['canonical_library_id'] != row['canonical_library_id']:
                raise RuntimeError('Alias changed during apply. Review the partial apply; no conflicting alias was overwritten.')
        return {'applied': True, 'automatic_grants': 0}
    finally:
        database.authority_migration_locks.delete_one({'_id': lock['_id'], 'token': lock['token']})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping', type=Path)
    parser.add_argument('--apply', action='store_true', help='Apply only an explicitly approved mapping file.')
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/dashboard_convergence_account_review.json')
    args = parser.parse_args()
    from backend.database.mongodb import db
    if args.apply and not args.mapping:
        parser.error('--apply requires an explicitly approved --mapping file.')
    mapping = json.loads(args.mapping.read_text(encoding='utf8')) if args.mapping else {}
    proposal = plan(db, mapping)
    review = [{'user_id': u['user_id'], 'legacy_role': u['role'], 'classification': 'UNKNOWN_REVIEW_REQUIRED',
               'automatic_grant': False, 'reason': 'Legacy labels provide no approved platform scope or explicit library mapping.'}
              for u in db.users.find({'role': {'$in': ['ADMIN', 'LIBRARIAN']}}, {'_id': 0, 'user_id': 1, 'role': 1})]
    result = {'mode': 'APPLY' if args.apply else 'DRY_RUN', 'proposal': proposal, 'legacy_accounts': review,
              'legacy_roles_changed': False, 'automatic_grants': 0, 'production_mutations': 0 if not args.apply else 'explicit reviewed grants only'}
    if args.apply:
        result.update(apply(db, proposal))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf8')
    print(f"{result['mode']}: {len(proposal['grants'])} explicit grants; {len(review)} legacy accounts require review; no inferred grants.")


if __name__ == '__main__':
    main()
