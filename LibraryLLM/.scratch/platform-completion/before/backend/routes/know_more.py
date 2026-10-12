from fastapi import APIRouter, Depends, Response
from backend.dependencies import get_current_user
from backend.services.book_capability_service import get_know_more_books

router = APIRouter(prefix="/know-more", tags=["Know More"])


@router.get("/books")
def my_books(response: Response, current_user=Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    books = get_know_more_books(int(current_user["sub"]))
    return {"count": len(books), "books": books}
