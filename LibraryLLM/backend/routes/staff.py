"""Retired account-role provisioning API; use Platform Console identities and library invitations."""
from fastapi import APIRouter, Depends
from backend.dependencies import get_current_user
from backend.platform_dependencies import retirement
router = APIRouter(prefix='/staff', tags=['Retired staff account API'], dependencies=[Depends(get_current_user)])
@router.api_route('/', methods=['GET'])
@router.api_route('/librarians', methods=['POST'])
@router.api_route('/{user_id}', methods=['PATCH'])
@router.api_route('/{user_id}/resend-verification', methods=['POST'])
def retired(user_id: int | None = None):
    retirement()
