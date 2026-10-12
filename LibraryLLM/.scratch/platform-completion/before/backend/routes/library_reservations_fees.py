from datetime import datetime
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from backend.dependencies import get_current_user
from backend.schemas.library_lending import Command
from backend.schemas.library_reservations_fees import Reservation, Reason, Adjustment, Payment, Policy
from backend.services import library_reservation_service as reservations, library_fee_service as fees

router = APIRouter(prefix='/libraries/{library_id}', tags=['Library reservations and fees'])


@router.get('/reservations-fees/config')
def config(library_id: UUID, actor=Depends(get_current_user)):
    from backend.services.library_inventory_access import require_library_membership
    from backend.services.institution_repository import collection
    require_library_membership(str(library_id), actor)
    return {'library_id': str(library_id), 'state': (collection('v2c_config').find_one({'library_id': str(library_id)}) or {}).get('state', 'LEGACY'), 'max_active_reservations': 5, 'waiting_expiry_days': None}


@router.post('/staff/reservations-fees/activate')
def activate(library_id: UUID, request: Command, actor=Depends(get_current_user)):
    return reservations.activate(str(library_id), actor, request)


@router.post('/reservations', status_code=201)
def reserve(library_id: UUID, request: Reservation, actor=Depends(get_current_user)):
    return reservations.create(str(library_id), actor, request)


@router.get('/inventory/{library_book_id}/reservation-status')
def book_state(library_id: UUID, library_book_id: UUID, actor=Depends(get_current_user)):
    from backend.services import library_lending_service as lending
    from backend.services.institution_repository import collection, library_mutation
    from backend.institution_dependencies import actor_id
    from backend.services.library_v2c_plan import enabled
    identity, book_id = str(library_id), str(library_book_id)
    with library_mutation(identity, wait_seconds=30, durable=True):
        lending.access_locked(identity, actor, patron=True); lending.book_holding(identity, book_id)
        if not enabled(identity):
            return {'state': 'LEGACY', 'reservation': None}
        reservations.advance_locked(identity, book_id)
        scope = lending.scoped(identity, library_book_id=book_id, user_id=actor_id(actor))
        row = collection('reservations').find_one({**scope, 'status': {'$in': ['WAITING', 'CONVERTED']}}, sort=[('queue_sequence', -1)])
        pending = collection('lending_requests').find_one({**scope, 'request_type': 'BORROW', 'status': 'PENDING'})
        loan = collection('loans').find_one({**scope, 'status': 'ACTIVE'})
        if row:
            row = lending.clean(row)
            queue_scope = lending.scoped(identity, library_book_id=book_id, status='WAITING')
            row['queue_position'] = collection('reservations').count_documents({**queue_scope, 'queue_sequence': {'$lte': row['queue_sequence']}}) if row['status'] == 'WAITING' else None
            row['queue_length'] = collection('reservations').count_documents(queue_scope)
        return {'state': 'CANONICAL', 'reservation': row, 'pending_request_id': pending['lending_request_id'] if pending else None, 'active_loan': bool(loan)}


@router.post('/reservations/{reservation_id}/cancel')
def cancel(library_id: UUID, reservation_id: UUID, request: Command, actor=Depends(get_current_user)):
    return reservations.cancel(str(library_id), str(reservation_id), actor, request)


@router.get('/me/reservations')
def mine(library_id: UUID, library_book_id: UUID | None = None, offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100), actor=Depends(get_current_user)):
    return reservations.rows(str(library_id), actor, book_id=str(library_book_id) if library_book_id else None, offset=offset, limit=limit)


@router.get('/staff/reservations')
def queue(library_id: UUID, status: Literal['all', 'WAITING', 'CONVERTED', 'FULFILLED', 'CANCELLED', 'EXPIRED'] = 'all', search: str = Query('', max_length=150),
          offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100), actor=Depends(get_current_user)):
    return reservations.rows(str(library_id), actor, staff=True, status=status, search=search, offset=offset, limit=limit)


@router.get('/me/fees')
def mine_fees(library_id: UUID, offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100), actor=Depends(get_current_user)):
    return fees.rows(str(library_id), actor, offset=offset, limit=limit)


@router.get('/me/fees/{fee_id}')
def own_fee(library_id: UUID, fee_id: UUID, actor=Depends(get_current_user)):
    return fees.details(str(library_id), str(fee_id), actor)


@router.get('/staff/fees')
def staff_fees(library_id: UUID, status: Literal['all', 'OPEN', 'PARTIALLY_PAID', 'PAID', 'WAIVED', 'CANCELLED'] = 'all', fee_type: Literal['all', 'OVERDUE', 'DAMAGE', 'LOST', 'MANUAL_ADJUSTMENT'] = 'all',
              search: str = Query('', max_length=150), since: datetime | None = None, until: datetime | None = None,
              offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100), actor=Depends(get_current_user)):
    return fees.rows(str(library_id), actor, staff=True, status=status, fee_type=fee_type, search=search, since=since, until=until, offset=offset, limit=limit)


@router.get('/staff/fees/{fee_id}')
def staff_fee(library_id: UUID, fee_id: UUID, actor=Depends(get_current_user)):
    return fees.details(str(library_id), str(fee_id), actor, staff=True)


@router.post('/staff/fees/{fee_id}/waive')
def waive(library_id: UUID, fee_id: UUID, request: Reason, actor=Depends(get_current_user)):
    return fees.mutate(str(library_id), str(fee_id), actor, request, 'waive')


@router.post('/staff/fees/{fee_id}/adjust')
def adjust(library_id: UUID, fee_id: UUID, request: Adjustment, actor=Depends(get_current_user)):
    return fees.mutate(str(library_id), str(fee_id), actor, request, 'adjust')


@router.post('/staff/fees/{fee_id}/payments')
def payment(library_id: UUID, fee_id: UUID, request: Payment, actor=Depends(get_current_user)):
    return fees.mutate(str(library_id), str(fee_id), actor, request, 'payments')


@router.post('/staff/loans/{loan_id}/fees/reconcile')
def generate(library_id: UUID, loan_id: UUID, request: Command, actor=Depends(get_current_user)):
    return fees.generate(str(library_id), str(loan_id), actor, request)


@router.get('/settings/fee-policy')
def policy(library_id: UUID, actor=Depends(get_current_user)):
    return fees.policy(str(library_id), actor)


@router.post('/settings/fee-policy')
def update_policy(library_id: UUID, request: Policy, actor=Depends(get_current_user)):
    return fees.policy(str(library_id), actor, request)
