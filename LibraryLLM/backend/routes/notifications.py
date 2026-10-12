from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StrictInt
from backend.dependencies import get_current_user
from backend.platform_dependencies import require_platform_admin, retirement
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
    return require_platform_admin(identity)


router = APIRouter(prefix='/notifications', tags=['Notifications'], dependencies=[Depends(account)])
admin_router = APIRouter(prefix='/admin', tags=['Platform API compatibility'], dependencies=[Depends(admin)])
platform_router = APIRouter(prefix='/platform', tags=['Platform operations and notifications'], dependencies=[Depends(admin)])


class SendRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    recipient_user_ids: list[Annotated[StrictInt, Field(gt=0)]] = Field(default_factory=list, max_length=50)
    recipient_emails: list[EmailStr] = Field(default_factory=list, max_length=50)
    title: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=1000)
    request_id: UUID


@router.get('')
def list_notifications(limit: int=Query(20, ge=1, le=50), offset: int=Query(0, ge=0, le=1000000), user=Depends(account)):
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


@router.get('/{notification_id}')
def detail_notice(notification_id: str, user=Depends(account)):
    try:
        return ns.get_own(int(user['sub']), notification_id)
    except LookupError as error:
        raise HTTPException(404, str(error))


@router.get('/{notification_id}/action')
def notice_action(notification_id: str, user=Depends(account)):
    # Fresh action resolution prevents a stale bell item redirecting after a
    # membership or lifecycle change. The destination itself remains guarded.
    return detail_notice(notification_id, user)


@platform_router.get('/users')
def users(q: str=Query('', max_length=120), limit: int=Query(20, ge=1, le=50),
          offset: int=Query(0, ge=0)):
    return ns.directory(q, limit, offset)


@platform_router.get('/summary')
def summary():
    from backend.database.mongodb import db
    from backend.services.event_service import scope_match
    return {'users': db.users.count_documents({}), 'books': db.books.estimated_document_count(),
            'platform_admins': db.platform_role_assignments.count_documents({'role': 'PLATFORM_ADMIN', 'status': 'ACTIVE'}),
            'events': db.events.count_documents(scope_match())}


@platform_router.get('/operations')
def operations(limit: int=Query(20, ge=1, le=50), offset: int=Query(0, ge=0),
               user_id: int | None=Query(None, gt=0), email: str=Query('', max_length=120),
               work_id: str=Query('', max_length=120), title: str=Query('', max_length=200),
               operation_type: str=Query('')):
    if operation_type and operation_type not in ops.TYPES:
        raise HTTPException(422, 'Unsupported operation type.')
    return ops.operations(limit, offset, user_id, email, work_id, title, operation_type)


@platform_router.get('/users/{user_id}/activity')
def activity(user_id: int):
    try:
        return ops.user_activity(user_id)
    except LookupError as error:
        raise HTTPException(404, str(error))


@platform_router.post('/notifications', status_code=201)
def send(request: SendRequest, actor=Depends(admin)):
    try:
        return ns.send_admin(int(actor['sub']), request.recipient_user_ids, request.recipient_emails,
                             request.title, request.message, str(request.request_id))
    except ValueError as error:
        raise HTTPException(400, str(error))


@platform_router.get('/notifications/sent')
def sent(limit: int=Query(20, ge=1, le=50), offset: int=Query(0, ge=0)):
    return ns.sent(limit, offset)


@platform_router.post('/operations/return/{issue_id}')
def assisted_return(issue_id: int, actor=Depends(admin)):
    retirement()


@admin_router.api_route('/{path:path}', methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'])
def platform_compatibility(path: str, request: Request):
    from fastapi.responses import RedirectResponse
    target = '/platform/' + path
    if request.url.query:
        target += '?' + request.url.query
    return RedirectResponse(target, status_code=307)
