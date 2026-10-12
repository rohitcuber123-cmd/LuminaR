"""Explicit tenant evidence only. No historical copy identifiers are invented."""
import argparse
import json
import sys
from pathlib import Path
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
from fastapi import HTTPException
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.database.mongodb import db
from backend.services.institution_repository import collection, library_mutation, now
from backend.services.library_lending_service import scoped, update_effect
from backend.services import library_lending_journal as journal


def plan(library_id, legacy_library_id):
    errors = []; loans = []; holdings = []
    alias = collection('library_aliases').find_one({'canonical_library_id': library_id, 'legacy_library_id': legacy_library_id})
    if not alias:
        errors.append('An explicit Part 2A library alias is required; neither LIB001 nor a title is tenant evidence.')
    if not collection('libraries').find_one(scoped(library_id, status='ACTIVE')):
        errors.append('Active canonical library does not exist.')
    for issue in db.issues.find({'library_id': legacy_library_id, 'status': 'ISSUED'}):
        matches = list(collection('library_books').find(scoped(library_id, global_work_id=issue.get('work_id'))))
        if issue.get('inventory_source') != 'physical' or len(matches) != 1:
            errors.append('Issue requires explicit physical source and unique mapped library book: ' + str(issue.get('issue_id'))); continue
        book = matches[0]; holding = collection('holdings').find_one(scoped(library_id, library_book_id=book['library_book_id']))
        if not holding or not issue.get('issued_at') or not issue.get('due_date'):
            errors.append('Issue lacks holding/date evidence: ' + str(issue.get('issue_id'))); continue
        loans.append({'loan_id': str(uuid5(NAMESPACE_URL, f'luminar:{library_id}:legacy-issue:{issue["issue_id"]}')),
            'library_id': library_id, 'library_book_id': book['library_book_id'], 'holding_id': holding['holding_id'],
            'copy_id': None, 'allocation_mode': 'AGGREGATE', 'user_id': issue['user_id'], 'borrower_user_id': issue['user_id'],
            'approved_by_user_id': None, 'borrow_request_id': None, 'borrowed_at': issue['issued_at'], 'due_at': issue['due_date'],
            'returned_at': None, 'status': 'ACTIVE', 'global_work_id': book.get('global_work_id'), 'title': book['title'],
            'accession_number': book['accession_number'], 'renewal_count': issue.get('renewal_count', 0), 'legacy_issue_id': issue['issue_id']})
    identities = [(r['user_id'], r['library_book_id']) for r in loans]
    if len(identities) != len(set(identities)):
        errors.append('Duplicate active legacy user/book loans require operator review.')
    for h in collection('holdings').find(scoped(library_id)):
        active = sum(r['holding_id'] == h['holding_id'] for r in loans)
        copies = list(collection('copies').find(scoped(library_id, holding_id=h['holding_id'])))
        if any(c['status'] in ['BORROWED', 'HELD_FOR_REQUEST', 'RESERVED'] for c in copies):
            errors.append('Existing copy allocations require operator mapping: ' + h['holding_id'])
        unavailable = h['total_copies'] - h['available_copies'] - active - sum(c['status'] != 'AVAILABLE' for c in copies)
        if unavailable < 0:
            errors.append('Snapshot cannot account for active loans: ' + h['holding_id'])
        holdings.append({'holding_id': h['holding_id'], 'unavailable_stock': unavailable, 'active_loans': active})
    return {'library_id': library_id, 'legacy_library_id': legacy_library_id, 'ok': not errors, 'errors': errors, 'loans': loans, 'holdings': holdings, 'read_only': True}


def apply(library_id, legacy_library_id, *, writers_stopped, idempotency_key):
    if not writers_stopped:
        raise ValueError('Stop all writers before migration.')
    with library_mutation(library_id, wait_seconds=1, durable=True):
        payload = {'legacy_library_id': legacy_library_id}; old = journal.receipt(library_id, 0, idempotency_key, 'LENDING_CUTOVER', payload)
        if old is not None:
            return old
        if journal.state(library_id) != 'LEGACY':
            raise HTTPException(409, 'Only LEGACY libraries can begin migration.')
        result = plan(library_id, legacy_library_id)
        if not result['ok']:
            raise HTTPException(409, result['errors'])
        journal.ensure_indexes()
        effects = [journal.effect('lending_config', scoped(library_id), {'library_id': library_id, 'state': 'PREPARING', 'cutover_at': now()}, True)]
        for h in result['holdings']:
            effects.append(update_effect('holdings', library_id, 'holding_id', h['holding_id'], {'allocation_mode': 'AGGREGATE', 'unavailable_stock': h['unavailable_stock'], 'circulation_status': 'CIRCULATING', 'quantity_semantics': 'CANONICAL_CIRCULATION'}))
        for loan in result['loans']:
            effects.append(journal.effect('loans', scoped(library_id, loan_id=loan['loan_id']), loan, True))
        effects.append(journal.effect('lending_config', scoped(library_id), {'state': 'CANONICAL', 'migrated_at': now()}))
        return journal.commit(library_id, 0, idempotency_key, 'LENDING_CUTOVER', payload, effects, {**result, 'read_only': False, 'state': 'CANONICAL'})


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--library-id', type=UUID, required=True)
    parser.add_argument('--legacy-library-id', required=True); parser.add_argument('--apply', action='store_true')
    parser.add_argument('--writers-stopped', action='store_true'); parser.add_argument('--idempotency-key', type=UUID)
    args = parser.parse_args()
    if args.apply and not args.idempotency_key:
        parser.error('--apply requires a durable UUID --idempotency-key')
    result = apply(str(args.library_id), args.legacy_library_id, writers_stopped=args.writers_stopped, idempotency_key=str(args.idempotency_key)) if args.apply else plan(str(args.library_id), args.legacy_library_id)
    print(json.dumps(result, indent=2, default=str)); return 0 if result['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
