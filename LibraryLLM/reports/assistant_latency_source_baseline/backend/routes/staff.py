from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StrictBool
from backend.dependencies import require_roles
from backend.services import staff_service

router=APIRouter(prefix='/staff', tags=['Staff management'], dependencies=[Depends(require_roles('ADMIN'))])

class CreateLibrarianRequest(BaseModel):
    model_config=ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr

class UpdateLibrarianRequest(BaseModel):
    model_config=ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: StrictBool | None = None

@router.get('/')
def directory(limit: int=Query(20,ge=1,le=100), offset: int=Query(0,ge=0)):
    return staff_service.list_staff(limit, offset)

@router.post('/librarians', status_code=201)
def create(request: CreateLibrarianRequest, actor=Depends(require_roles('ADMIN'))):
    try:
        return staff_service.create_librarian(request.name, request.email, int(actor['sub']))
    except ValueError as error:
        raise HTTPException(409, str(error))
    except RuntimeError:
        raise HTTPException(503, 'Staff creation is unavailable. An operator must check the identity configuration.')

@router.patch('/{user_id}')
def update(user_id: int, request: UpdateLibrarianRequest, actor=Depends(require_roles('ADMIN'))):
    try:
        return {'user':staff_service.update_librarian(user_id, request.model_dump(exclude_unset=True), int(actor['sub']))}
    except LookupError:
        raise HTTPException(404, 'Librarian not found.')
    except ValueError as error:
        raise HTTPException(400, str(error))

@router.post('/{user_id}/resend-verification')
def resend(user_id: int, actor=Depends(require_roles('ADMIN'))):
    try:
        return staff_service.resend_librarian_verification(user_id,int(actor['sub']))
    except LookupError:
        raise HTTPException(404, 'Librarian not found.')
    except ValueError as error:
        raise HTTPException(400,str(error))
    except RuntimeError:
        raise HTTPException(503,'Unable to send verification email. Please try again later.')
