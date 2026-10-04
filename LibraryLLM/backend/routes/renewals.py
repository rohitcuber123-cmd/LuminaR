from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from backend.dependencies import get_current_user
from backend.services.identity_service import current_identity
from backend.services import loan_renewal_service as service

router = APIRouter(prefix='/issues', tags=['Loan renewal'])
admin_router = APIRouter(prefix='/admin/operations', tags=['Admin renewal'])


def account(payload=Depends(get_current_user)):
    try:
        user = current_identity(payload)
    except (ValueError, KeyError, TypeError):
        user = None
    if not user:
        raise HTTPException(401, 'Account is unavailable.')
    return user


def admin(user=Depends(account)):
    if user['role'] != 'ADMIN':
        raise HTTPException(403, 'Administrator access required.')
    return user


class RenewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    expected_due_date: datetime


def perform(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except service.RenewalError as error:
        raise HTTPException(error.status, {'code': error.code, 'message': str(error)})


@router.get('/{issue_id}/renewal')
def eligibility(issue_id: int, user=Depends(account)):
    return perform(service.renewal_eligibility, issue_id, int(user['sub']))


@router.post('/{issue_id}/renew')
def renew(issue_id: int, request: RenewRequest, user=Depends(account)):
    return perform(service.renew_loan, issue_id, int(user['sub']), str(request.request_id), request.expected_due_date)


@admin_router.post('/renew/{issue_id}')
def assisted(issue_id: int, request: RenewRequest, user=Depends(admin)):
    return perform(service.renew_loan, issue_id, int(user['sub']), str(request.request_id), request.expected_due_date, assisted=True)
