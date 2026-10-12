"""One bounded, read-only Staff Analytics resource; no platform-role fallback."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Response

from backend.dependencies import get_current_user
from backend.services.library_analytics_service import dashboard

router = APIRouter(prefix='/libraries/{library_id}/analytics', tags=['Library analytics'])


@router.get('')
def analytics(library_id: UUID, response: Response, range: Literal['7d', '30d', '90d', 'all'] = '30d',
              actor=Depends(get_current_user)):
    response.headers['Cache-Control'] = 'no-store'
    return dashboard(str(library_id), actor, range)
