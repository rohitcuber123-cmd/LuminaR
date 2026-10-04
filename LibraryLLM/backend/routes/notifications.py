from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StrictInt
from backend.dependencies import get_current_user
from backend.services.identity_service import current_identity
from backend.services import notification_service as ns, admin_operation_service as ops


def account(payload=Depends(get_current_user)):
    try:
        identity = current_identity(payload)
    except (ValueError, KeyError, TypeError):
        identity = None
    if not identity:
        raise HTTPException(401, 'Account is unavailable.')
    return identity


def admin(identity=Depends(account)):
    if identity['role'] != 'ADMIN':
        raise HTTPException(403, 'Administrator access required.')
    return identity


router = APIRouter(prefix='/notifications', tags=['Notifications'], dependencies=[Depends(account)])
admin_router = APIRouter(prefix='/admin', tags=['Admin operations and notifications'], dependencies=[Depends(admin)])


class SendRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    recipient_user_ids: list[Annotated[StrictInt, Field(gt=0)]] = Field(default_factory=list, max_length=50)
    recipient_emails: list[EmailStr] = Field(default_factory=list, max_length=50)
    title: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=1000)
    request_id: UUID


@router.get('')
def list_notifications(limit: int=Query(20, ge=1, le=50), offset: int=Query(0, ge=0), user=Depends(account)):
    return ns.list_own(int(user['sub']), limit, offset)


@router.get('/unread-count')
def unread_count(user=Depends(account)):
    return {'unread_count': ns.unread(int(user['sub']))}


@router.post('/read-all')
def read_all(user=Depends(account)):
    return ns.read_all(int(user['sub']))


@router.patch('/{notification_id}/read')
def read_notice(notification_id: str, user=Depends(account)):
    try:
        return ns.mark_read(int(user['sub']), notification_id)
    except LookupError as error:
        raise HTTPException(404, str(error))


@admin_router.get('/users')
def users(q: str=Query('', max_length=120), limit: int=Query(20, ge=1, le=50),
          offset: int=Query(0, ge=0)):
    return ns.directory(q, limit, offset)


@admin_router.get('/summary')
def summary():
    from backend.database.mongodb import db
    unpaid = list(db['fines'].aggregate([{'$match': {'status': 'UNPAID'}},
                                        {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}]))
    return {'users': db['users'].count_documents({}),
            'books': db['books'].estimated_document_count(),
            'librarians': db['users'].count_documents({'role': 'LIBRARIAN', 'is_active': {'$ne': False}}),
            'active_loans': db['issues'].count_documents({'status': 'ISSUED'}),
            'reservations': db['reservations'].count_documents({'status': {'$in': ['ACTIVE', 'READY_FOR_PICKUP']}}),
            'unpaid': unpaid[0]['total'] if unpaid else 0}


@admin_router.get('/operations')
def operations(limit: int=Query(20, ge=1, le=50), offset: int=Query(0, ge=0),
               user_id: int | None=Query(None, gt=0), email: str=Query('', max_length=120),
               work_id: str=Query('', max_length=120), title: str=Query('', max_length=200),
               operation_type: str=Query('')):
    if operation_type and operation_type not in ops.TYPES:
        raise HTTPException(422, 'Unsupported operation type.')
    return ops.operations(limit, offset, user_id, email, work_id, title, operation_type)


@admin_router.get('/users/{user_id}/activity')
def activity(user_id: int):
    try:
        return ops.user_activity(user_id)
    except LookupError as error:
        raise HTTPException(404, str(error))


@admin_router.post('/notifications', status_code=201)
def send(request: SendRequest, actor=Depends(admin)):
    try:
        return ns.send_admin(int(actor['sub']), request.recipient_user_ids, request.recipient_emails,
                             request.title, request.message, str(request.request_id))
    except ValueError as error:
        raise HTTPException(400, str(error))


@admin_router.get('/notifications/sent')
def sent(limit: int=Query(20, ge=1, le=50), offset: int=Query(0, ge=0)):
    return ns.sent(limit, offset)


@admin_router.post('/operations/return/{issue_id}')
def assisted_return(issue_id: int, actor=Depends(admin)):
    from backend.services.issue_service import get_issue_by_id, return_book
    loan = get_issue_by_id(issue_id)
    if not loan:
        raise HTTPException(404, 'Issue not found.')
    try:
        return return_book(issue_id, loan['user_id'], actor_user_id=int(actor['sub']))
    except (ValueError, PermissionError) as error:
        raise HTTPException(400, str(error))
