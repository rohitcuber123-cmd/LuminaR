"""Every ID is a canonical UUID; request roles never supply actor authority."""
from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Depends, Query

from backend.dependencies import get_current_user
from backend.institution_dependencies import require_library_membership
from backend.schemas.institutions import (
    RegisterLibrary, JoinLibrary, RotateCode, AccessRequest, InviteStaff,
    InvitationAction, MembershipChange, LibraryProfile,
)
from backend.services import institution_service as service

router = APIRouter(tags=['Institutions'], dependencies=[])


@router.post('/libraries/register', status_code=201)
def register(request: RegisterLibrary, current_user=Depends(get_current_user)):
    return service.register_library(request, current_user)


@router.get('/libraries')
def discovery(search: str = Query('', max_length=100), kind: Literal['all', 'public', 'private', 'mine'] = 'all',
              offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100), current_user=Depends(get_current_user)):
    return service.discover(current_user, search.strip(), kind, offset, limit)


@router.get('/me/libraries')
def mine(offset: int = Query(0, ge=0, le=100000), limit: int = Query(100, ge=1, le=100), current_user=Depends(get_current_user)):
    return service.my_libraries(current_user, offset, limit)


@router.get('/me/invitations')
def pending(offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100), current_user=Depends(get_current_user)):
    return service.pending_invitations(current_user, offset, limit)


@router.get('/libraries/{library_id}')
def profile(library_id: UUID, current_user=Depends(get_current_user)):
    return service.public_library(service.get_library(str(library_id)))


@router.get('/libraries/{library_id}/context')
def context(library_id: UUID, current_user=Depends(get_current_user)):
    library, membership = require_library_membership(str(library_id), current_user)
    return {'library': service.public_library(library), 'membership': service.public_membership(membership, library)}


@router.post('/libraries/{library_id}/join')
def join(library_id: UUID, request: JoinLibrary, current_user=Depends(get_current_user)):
    return service.join_library(str(library_id), request, current_user)


@router.patch('/libraries/{library_id}')
def edit_profile(library_id: UUID, request: LibraryProfile, current_user=Depends(get_current_user)):
    return service.update_profile(str(library_id), request, current_user)


@router.get('/libraries/{library_id}/access')
def access(library_id: UUID, current_user=Depends(get_current_user)):
    return service.access_settings(str(library_id), current_user)


@router.put('/libraries/{library_id}/access-code')
def rotate(library_id: UUID, request: RotateCode, current_user=Depends(get_current_user)):
    return service.change_code(str(library_id), request, current_user)


@router.put('/libraries/{library_id}/access')
def mode(library_id: UUID, request: AccessRequest, current_user=Depends(get_current_user)):
    return service.change_access(str(library_id), request, current_user)


@router.get('/libraries/{library_id}/memberships')
def members(library_id: UUID, staff_only: bool = False, offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100), current_user=Depends(get_current_user)):
    return service.list_staff(str(library_id), current_user, offset, limit, staff_only)


@router.patch('/libraries/{library_id}/memberships/{membership_id}')
def membership(library_id: UUID, membership_id: UUID, request: MembershipChange, current_user=Depends(get_current_user)):
    return service.change_membership(str(library_id), str(membership_id), request, current_user)


@router.get('/libraries/{library_id}/invitations')
def invitations(library_id: UUID, offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100), current_user=Depends(get_current_user)):
    return service.list_invitations(str(library_id), current_user, offset, limit)


@router.post('/libraries/{library_id}/invitations', status_code=201)
def invite(library_id: UUID, request: InviteStaff, current_user=Depends(get_current_user)):
    return service.invite_staff(str(library_id), request, current_user)


@router.post('/libraries/{library_id}/invitations/{invitation_id}/revoke')
def revoke(library_id: UUID, invitation_id: UUID, current_user=Depends(get_current_user)):
    return service.revoke_invitation(str(library_id), str(invitation_id), current_user)


@router.post('/invitations/{invitation_id}/accept')
def accept(invitation_id: UUID, request: InvitationAction, current_user=Depends(get_current_user)):
    return service.respond_invitation(str(invitation_id), request, current_user)


@router.post('/invitations/{invitation_id}/decline')
def decline(invitation_id: UUID, request: InvitationAction, current_user=Depends(get_current_user)):
    return service.respond_invitation(str(invitation_id), request, current_user, accept=False)


@router.get('/libraries/{library_id}/audit')
def audit(library_id: UUID, offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100), current_user=Depends(get_current_user)):
    return service.audit_events(str(library_id), current_user, offset, limit)


@router.get('/libraries/{library_id}/staff/activity')
def operational_activity(library_id: UUID, offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100), current_user=Depends(get_current_user)):
    return service.operational_activity(str(library_id),current_user,offset,limit)
