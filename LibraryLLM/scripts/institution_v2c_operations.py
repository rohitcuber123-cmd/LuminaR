"""Offline recovery, reconciliation and conservative pre-use rollback."""
from backend.services.institution_repository import collection, now, library_mutation
from backend.services import library_lending_journal as journal
from backend.services.library_lending_service import scoped
from backend.services.library_fee_service import verify_ledger
from scripts.lending_v2b_operations import reconcile as lending_reconcile


from backend.services.library_v2c_integrity import reconcile


def recover(library_id, *, apply=False, writers_stopped=False):
    plans = list(collection('lending_operations').find(scoped(library_id)).sort('created_at', 1))
    unfinished = [p for p in plans if p['state'] != 'COMMITTED']
    result = {'library_id': library_id, 'apply': apply, 'operation_ids': [p['operation_id'] for p in unfinished]}
    if not apply:
        return {**result, 'reconciliation': reconcile(library_id)}
    if not writers_stopped or not collection('locks').find_one({'_id': library_id}) or not any(p['operation_type'] == 'LENDING_CUTOVER' for p in plans):
        raise ValueError('Stop every writer. A retained gate and proven lending cutover are required; never clear an unrelated lock.')
    for plan in unfinished:
        journal.replay(plan)
    report = reconcile(library_id)
    if not report['ok']:
        return {**result, **report}
    journal.durable('lending_config').update_one(scoped(library_id), {'$set': {'state': 'CANONICAL', 'recovered_at': now()}})
    # Replay includes the Part 2C state decision; recovery never guesses a missing mode.
    journal.durable('locks').delete_one({'_id': library_id})
    return {**result, **report}


def rollback(library_id, *, apply=False, writers_stopped=False):
    plans = list(collection('lending_operations').find(scoped(library_id, operation_type={'$regex': '^(V2C_|RESERVATION_|QUEUE_|FEE_)'})))
    safe = len(plans) == 1 and plans[0]['operation_type'] == 'V2C_CUTOVER' and plans[0]['state'] == 'COMMITTED'
    safe = safe and not collection('reservations').find_one(scoped(library_id)) and not collection('fees').find_one(scoped(library_id))
    # New loans retain policy snapshots, so rollback after issuance is deliberately denied.
    safe = safe and not collection('loans').find_one(scoped(library_id, borrowed_at={'$gte': (plans[0]['created_at'] if plans else now())}))
    result = {'library_id': library_id, 'safe': safe, 'applied': False}
    if not safe:
        return {**result, 'reason': 'Post-cutover financial/queue history or lending exists. Recover and reconcile; retain canonical authority.'}
    if apply:
        if not writers_stopped:
            raise ValueError('Stop every writer before rollback.')
        from uuid import uuid4
        with library_mutation(library_id, wait_seconds=1, durable=True):
            return journal.commit(library_id, 0, uuid4(), 'V2C_ROLLBACK', {},
                [journal.effect('v2c_config', scoped(library_id), {'state': 'LEGACY', 'reservation_mode': 'LEGACY', 'fee_mode': 'LEGACY', 'rolled_back_at': now()})], {**result, 'applied': True})
    return result
