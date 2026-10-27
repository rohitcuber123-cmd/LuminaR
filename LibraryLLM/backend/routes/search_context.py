"""Clears only short-lived Search state. Never touches account or reading data."""
from uuid import UUID
from fastapi import APIRouter, Depends, Response
from backend.dependencies import get_current_user
from search.session_store import clear

router = APIRouter(prefix='/search-context',tags=['Search context'])

@router.delete('')
def clear_account_contexts(response:Response,actor=Depends(get_current_user)):
    from search.session_store import invalidate
    from search.personalization import invalidate as invalidate_profile
    response.headers['Cache-Control']='private, no-store'
    invalidate(actor)
    invalidate_profile(actor)
    return {'cleared':True}

@router.delete('/{session_id}')
def clear_context(session_id:UUID,response:Response,library_id:UUID|None=None,staff:bool=False,actor=Depends(get_current_user)):
    response.headers['Cache-Control'] = 'private, no-store'
    if library_id:
        from backend.services.library_catalogue_experience import read_context
        with read_context(str(library_id),actor,staff=staff):
            clear(str(session_id),actor,str(library_id),staff)
    else:
        clear(str(session_id),actor)
    return {'cleared':True}
