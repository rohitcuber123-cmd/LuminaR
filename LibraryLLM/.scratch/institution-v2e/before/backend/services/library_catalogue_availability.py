"""Shared pure Part 2B projection for individual and bulk reads; never writes stock."""
from backend.services.library_lending_journal import RecoveryRequired


def project(library_id, book, holding, *, pending, active, known, conditions, available, waiting):
    unavailable = holding.get('unavailable_stock', 0) + conditions
    units = holding['total_copies'] - pending - active - unavailable
    if units < 0:
        raise RecoveryRequired('Holding allocation exceeds physical stock.')
    mode = holding.get('allocation_mode', 'AGGREGATE')
    if mode == 'COPY':
        if known != holding['total_copies']:
            raise RecoveryRequired('Copy-mode stock is not fully verified.')
        if available != units:
            raise RecoveryRequired('Copy state and loan/request allocations disagree.')
    status = holding.get('circulation_status', 'CIRCULATING')
    lendable = book['status'] == 'ACTIVE' and status == 'CIRCULATING'
    return {'library_id': library_id, 'library_book_id': book['library_book_id'], 'holding_id': holding['holding_id'],
        'total': holding['total_copies'], 'requestable': units if lendable and not waiting else 0,
        'physical_available': units, 'waiting_queue_has_priority': bool(waiting),
        'pending_holds': pending, 'active_loans': active, 'unavailable_stock': unavailable,
        'allocation_mode': mode, 'circulation_status': status if book['status'] == 'ACTIVE' else 'WITHDRAWN',
        'shelf_location': holding.get('shelf_location'), 'call_number': holding.get('call_number')}
