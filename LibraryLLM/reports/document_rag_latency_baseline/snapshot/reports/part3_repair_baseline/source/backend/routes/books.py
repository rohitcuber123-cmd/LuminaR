from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from backend.services.book_service import (
    get_books,
    get_top_categories,
    get_book_by_work_id,
    create_book,
    update_book,
    delete_book
)

from backend.services.book_service import (
    get_books,
    get_top_categories,
    get_popular_books,
    get_new_arrivals,
    get_book_by_work_id,
    create_book,
    update_book,
    delete_book
)

from backend.dependencies import get_current_user, require_roles
from backend.services.book_capability_service import (
    with_capabilities, catalog_capabilities, get_readable_book,
)


router = APIRouter(
    prefix="/books",
    tags=["Books"]
)


class BookCreateRequest(BaseModel):
    work_id: str
    title: str
    authors: str | None = None
    subjects: str | None = None
    description: str | None = None
    average_rating: float = 0
    rating_count: int = 0
    reading_log_count: int = 0
    shelf_location: str | None = None
    total_copies: int = 1
    available_copies: int = 1


class BookUpdateRequest(BaseModel):
    title: str | None = None
    authors: str | None = None
    subjects: str | None = None
    description: str | None = None
    average_rating: float | None = None
    rating_count: int | None = None
    reading_log_count: int | None = None
    shelf_location: str | None = None
    total_copies: int | None = None
    available_copies: int | None = None


@router.get("/")
def books(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):

    results, total_count = get_books(
        limit,
        offset
    )

    return {
        "count": total_count,
        "limit": limit,
        "offset": offset,
        "results": with_capabilities(results)
    }


@router.get("/categories")
def categories():

    results = get_top_categories()

    return {
        "count": len(results),
        "categories": results
    }
@router.get("/popular")
def popular_books(
    limit: int = Query(10, ge=1, le=50)
):

    results = get_popular_books(
        limit
    )

    return {
        "count": len(results),
        "results": with_capabilities(results)
    }


@router.get("/new-arrivals")
def new_arrivals(
    limit: int = Query(10, ge=1, le=50)
):

    results = get_new_arrivals(
        limit
    )

    return {
        "count": len(results),
        "results": with_capabilities(results)
    }

class CapabilityRequest(BaseModel):
    work_ids: list[str]


@router.post("/capabilities")
def book_capabilities(request: CapabilityRequest):
    if len(request.work_ids) > 100:
        raise HTTPException(400, "Request at most 100 book capabilities at once.")
    return {"books": catalog_capabilities(request.work_ids)}


@router.get("/{work_id}/read")
def read_book(work_id: str, current_user=Depends(get_current_user)):
    return get_readable_book(int(current_user["sub"]), work_id)


@router.get("/{work_id}")
def book(work_id: str):

    result = get_book_by_work_id(
        work_id
    )

    if result is None:

        raise HTTPException(
            status_code=404,
            detail="Book not found"
        )

    return with_capabilities([result])[0]


@router.post("/")
def create(
    request: BookCreateRequest,
    current_user=Depends(
        require_roles(
            "ADMIN",
            "LIBRARIAN"
        )
    )
):

    try:

        result = create_book(
            request.model_dump()
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    return {
        "message": "Book created successfully",
        "book": result
    }


@router.put("/{work_id}")
def update(
    work_id: str,
    request: BookUpdateRequest,
    current_user=Depends(
        require_roles(
            "ADMIN",
            "LIBRARIAN"
        )
    )
):

    try:

        result = update_book(
            work_id,
            request.model_dump(
                exclude_unset=True
            )
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    if result is None:

        raise HTTPException(
            status_code=404,
            detail="Book not found"
        )

    return {
        "message": "Book updated successfully",
        "book": result
    }


@router.delete("/{work_id}")
def delete(
    work_id: str,
    current_user=Depends(
        require_roles("ADMIN")
    )
):

    try:
        result = delete_book(work_id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))

    if result is None:

        raise HTTPException(
            status_code=404,
            detail="Book not found"
        )

    return {
        "message": "Book deleted successfully"
    }
