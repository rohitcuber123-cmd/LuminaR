"""HTTP book authorization, independent of the V8 semantic algorithm."""
from fastapi import HTTPException
from backend.dependencies import get_current_user
from backend.services.book_capability_service import authorize_know_more
from rag.book_assets import valid_work_id


def authorize_selection(document_id, work_id, credentials, document_ids):
    if document_id and work_id and document_id != work_id:
        raise HTTPException(400, "document_id and work_id must identify the same source.")
    selected = work_id or document_id
    if not selected:
        return None  # Preserve existing global access.
    if valid_work_id(selected):
        if credentials is None:
            raise HTTPException(401, "Sign in and borrow this book to use Know More.",
                                headers={"WWW-Authenticate": "Bearer"})
        user = get_current_user(credentials)
        authorize_know_more(int(user["sub"]), selected)
        return selected
    if selected in document_ids:
        return None  # Preserve existing uploaded-document access.
    raise HTTPException(404, "Selected source is not available.")
