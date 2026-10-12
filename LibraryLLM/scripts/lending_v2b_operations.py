"""Read-only reconciliation, explicit offline recovery and pre-use rollback."""
from backend.services.institution_repository import collection, now, library_mutation
from uuid import uuid5, NAMESPACE_URL
from backend.services import library_lending_journal as journal
from backend.services.library_lending_service import availability_locked, scoped


def reconcile(library_id):
    problems = []; holdings = []
    for holding in collection('holdings').find(scoped(library_id)):
        try:
            holdings.append(availability_locked(library_id, holding['library_book_id']))
        except Exception as error:
            problems.append(str(error))
    for request in collection('lending_requests').find(scoped(library_id, request_type='BORROW', status='APPROVED')):
        loan = collection('loans').find_one(scoped(library_id, loan_id=request.get('loan_id')))
        if not loan or any(loan.get(k) != request.get(k) for k in ['library_book_id', 'holding_id', 'copy_id', 'user_id']):
            problems.append('Approved borrow request has no matching canonical allocation: ' + request['lending_request_id'])
    for request in collection('lending_requests').find(scoped(library_id, request_type='BORROW', status='PENDING')):
        holding = collection('holdings').find_one(scoped(library_id, holding_id=request['holding_id'], library_book_id=request['library_book_id']))
        if not holding:
            problems.append('Pending hold has invalid canonical holding: ' + request['lending_request_id'])
        if request.get('copy_id') and not collection('copies').find_one(scoped(library_id, copy_id=request['copy_id'], library_book_id=request['library_book_id'], holding_id=request['holding_id'], status='HELD_FOR_REQUEST', lending_request_id=request['lending_request_id'])):
            problems.append('Pending hold copy identity is inconsistent: ' + request['lending_request_id'])
    for loan in collection('loans').find(scoped(library_id)):
        book = collection('library_books').find_one(scoped(library_id, library_book_id=loan['library_book_id']))
        holding = collection('holdings').find_one(scoped(library_id, holding_id=loan['holding_id'], library_book_id=loan['library_book_id']))
        if not book or not holding:
            problems.append('Loan has an invalid tenant book/holding reference: ' + loan['loan_id'])
        if loan.get('pending_return_request_id'):
            request = collection('lending_requests').find_one(scoped(library_id, lending_request_id=loan['pending_return_request_id'], request_type='RETURN', status='PENDING', loan_id=loan['loan_id']))
            if not request or loan['status'] != 'ACTIVE':
                problems.append('Loan pending return request is inconsistent: ' + loan['loan_id'])
        if loan.get('copy_id') and loan['status'] == 'ACTIVE':
            copy = collection('copies').find_one(scoped(library_id, copy_id=loan['copy_id'], status='BORROWED', loan_id=loan['loan_id']))
            if not copy:
                problems.append('Active loan copy allocation is inconsistent: ' + loan['loan_id'])
    return {'library_id': library_id, 'ok': not problems, 'problems': problems, 'holdings': holdings}


def recover(library_id, *, apply=False, writers_stopped=False):
    plans = list(collection('lending_operations').find(scoped(library_id)).sort('created_at', 1))
    unfinished = [p for p in plans if p['state'] != 'COMMITTED']
    result = {'library_id': library_id, 'operation_ids': [p['operation_id'] for p in unfinished], 'apply': apply}
    if not apply:
        return {**result, 'reconciliation': reconcile(library_id)}
    if not writers_stopped:
        raise ValueError('Stop every API/worker writer and supply --writers-stopped before applying recovery.')
    if not collection('locks').find_one({'_id': library_id}) or not plans:
        raise ValueError('No durable lending plan and retained gate exist. Do not clear an unrelated V1/V2A lock.')
    if not any(p['operation_type'] == 'LENDING_CUTOVER' for p in plans):
        raise ValueError('Cutover origin is unproven; operator reconciliation is required.')
    for plan in unfinished:
        journal.replay(plan)
    report = reconcile(library_id)
    if not report['ok']:
        return {**result, **report}
    target_state = 'LEGACY' if plans[-1]['operation_type'] == 'LENDING_ROLLBACK' else 'CANONICAL'
    journal.durable('lending_config').update_one(scoped(library_id), {'$set': {'state': target_state, 'recovered_at': now()}})
    journal.durable('locks').delete_one({'_id': library_id})
    return {**result, **report}


def rollback(library_id, *, apply=False, writers_stopped=False):
    plans = list(collection('lending_operations').find(scoped(library_id)).sort('created_at', 1))
    if plans and plans[-1]['operation_type'] == 'LENDING_ROLLBACK' and plans[-1]['state'] == 'COMMITTED' and journal.state(library_id) == 'LEGACY':
        return journal.response_value(plans[-1]['result']) if apply else {'library_id': library_id, 'safe': True, 'applied': False, 'already_rolled_back': True}
    safe = bool(plans) and all(p['operation_type'] == 'LENDING_CUTOVER' and p['state'] == 'COMMITTED' for p in plans)
    safe = safe and collection('loans').count_documents(scoped(library_id)) == 0 and collection('lending_requests').count_documents(scoped(library_id)) == 0
    if not safe:
        return {'library_id': library_id, 'safe': False, 'applied': False, 'reason': 'Post-cutover operations exist or cutover is unfinished. Recover/reconcile; never roll stock back blindly.'}
    if apply:
        if not writers_stopped or collection('locks').find_one({'_id': library_id}):
            raise ValueError('Stop writers; clear pending operations by recovery before rollback.')
        key = str(uuid5(NAMESPACE_URL, 'luminar-rollback:' + plans[-1]['operation_id']))
        with library_mutation(library_id, wait_seconds=1, durable=True):
            effects = [journal.effect('lending_config', scoped(library_id), {'state': 'LEGACY', 'rolled_back_at': now()})]
            for holding in collection('holdings').find(scoped(library_id)):
                effects.append(journal.effect('holdings', scoped(library_id, holding_id=holding['holding_id']), {'quantity_semantics': 'INVENTORY_SNAPSHOT_NOT_CIRCULATION'}))
            return journal.commit(library_id, 0, key, 'LENDING_ROLLBACK', {}, effects, {'library_id': library_id, 'safe': True, 'applied': True, 'state': 'LEGACY'})
    return {'library_id': library_id, 'safe': safe, 'applied': apply}
