from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.dependencies import get_current_user
from backend.services.reading_list_service import (
    get_user_reading_list,
    add_to_reading_list,
    remove_from_reading_list
)

router = APIRouter(
    prefix="/reading-list",
    tags=["Reading List"]
)

class ReadingListAddRequest(BaseModel):
    work_id: str = Field(min_length=1, max_length=200)

@router.get("/my")
def my_reading_list(current_user=Depends(get_current_user)):
    user_id = int(current_user["sub"])
    items = get_user_reading_list(user_id)
    return {
        "count": len(items),
        "items": items
    }

@router.post("/")
def add_book_to_reading_list(
    request: ReadingListAddRequest,
    current_user=Depends(get_current_user)
):
    user_id = int(current_user["sub"])
    target_key = add_to_reading_list(user_id, request.work_id)
    return {"message": "Book added to reading list", "target_key": target_key}

@router.delete("/{work_id}")
def remove_book_from_reading_list(
    work_id: str,
    current_user=Depends(get_current_user)
):
    user_id = int(current_user["sub"])
    remove_from_reading_list(user_id, work_id)
    return {"message": "Book removed from reading list"}
