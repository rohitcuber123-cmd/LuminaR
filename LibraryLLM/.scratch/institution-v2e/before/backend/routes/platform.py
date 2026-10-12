from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StrictBool
from typing import Literal
from uuid import UUID
from backend.dependencies import get_current_user
from backend.platform_dependencies import current_account, platform_assignments, require_platform_admin
from backend.services import platform_account_service as accounts
from backend.services import platform_library_service as libraries

router = APIRouter(prefix='/platform', tags=['Platform Console'], dependencies=[Depends(require_platform_admin)])
access_router = APIRouter(tags=['Explicit platform authority'])


class LibraryLifecycleCommand(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    reason: str = Field(min_length=1,max_length=500)
    expected_status: Literal['ACTIVE','SUSPENDED','REMOVED']
    idempotency_key: UUID


@router.get('/libraries')
def library_directory(limit: int = Query(20,ge=1,le=50), offset: int = Query(0,ge=0,le=1000000),
                      q: str = Query('',max_length=120), status: Literal['ACTIVE','SUSPENDED','REMOVED'] | None = None,
                      library_type: Literal['PUBLIC_LIBRARY','PRIVATE_INSTITUTION'] | None = None):
    return libraries.directory(limit,offset,q,status,library_type)


@router.get('/libraries/{library_id}')
def library_detail(library_id: UUID):
    return libraries.detail(str(library_id))


@router.get('/libraries/{library_id}/audit')
def library_audit(library_id: UUID,limit: int = Query(20,ge=1,le=50),offset: int = Query(0,ge=0,le=1000000)):
    libraries.library_record(str(library_id))
    return libraries.audit_rows(str(library_id),limit,offset)


@router.post('/libraries/{library_id}/{action}')
def library_lifecycle(library_id: UUID,action: Literal['suspend','remove','restore'],body: LibraryLifecycleCommand,actor=Depends(require_platform_admin)):
    try:return libraries.lifecycle(str(library_id),action,body,actor)
    except HTTPException:raise
    except Exception:raise HTTPException(503,'Platform lifecycle outcome needs operator recovery; library access is safely gated.') from None


@access_router.get('/me/platform-access')
def access(payload=Depends(get_current_user)):
    user = current_account(payload)
    return {'roles': ['PLATFORM_ADMIN'] if platform_assignments(user['sub']) else []}


@router.get('/accounts')
def directory(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), q: str = Query('', max_length=120)):
    return accounts.directory(limit, offset, q)


class CreateAccount(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr


class UpdateAccount(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: StrictBool | None = None


@router.post('/accounts', status_code=201)
def create(body: CreateAccount, actor=Depends(require_platform_admin)):
    try:
        return accounts.create(body.name, body.email, int(actor['sub']))
    except ValueError as error:
        raise HTTPException(409, str(error))
    except RuntimeError:
        raise HTTPException(503, 'Account provisioning needs operator review.')


@router.patch('/accounts/{user_id}')
def update(user_id: int, body: UpdateAccount, actor=Depends(require_platform_admin)):
    try:
        return {'user': accounts.update(user_id, body.model_dump(exclude_unset=True), int(actor['sub']))}
    except LookupError:
        raise HTTPException(404, 'Account not found.')
    except ValueError as error:
        raise HTTPException(400, str(error))


@router.post('/accounts/{user_id}/resend-verification')
def resend(user_id: int, actor=Depends(require_platform_admin)):
    try:
        return accounts.resend(user_id, int(actor['sub']))
    except LookupError:
        raise HTTPException(404, 'Account not found.')
    except ValueError as error:
        raise HTTPException(400, str(error))
    except RuntimeError:
        raise HTTPException(503, 'Unable to send verification email.')


@router.get('/health')
def health():
    from backend.database.mongodb import db
    db.command('ping')
    return {'status': 'ok', 'database': 'available'}


@router.get('/migration-review')
def migration_review(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    from backend.database.mongodb import db
    query = {'role': {'$in': ['ADMIN', 'LIBRARIAN']}}
    rows = list(db.users.find(query, {'_id': 0, 'user_id': 1, 'role': 1}).sort('user_id', 1).skip(offset).limit(limit))
    for row in rows:
        row['legacy_role'] = row.pop('role')
        row['classification'] = 'UNKNOWN_REVIEW_REQUIRED'
        row['platform_assigned'] = bool(platform_assignments(row['user_id']))
        row['library_memberships'] = db.institution_memberships.count_documents({'user_id': row['user_id'], 'status': 'ACTIVE'})
        row['automatic_grant'] = False
    return {'results': rows, 'total': db.users.count_documents(query), 'offset': offset, 'limit': limit}
