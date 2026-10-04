from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.dependencies import require_roles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from backend.services.inventory_service import (
    add_inventory,
    get_inventory,
    get_inventory_book,
    update_inventory,
    delete_inventory
)
from fastapi import UploadFile, File
from backend.services.inventory_import_service import (
    create_preview
)
from backend.services.inventory_import_service import (
    confirm_inventory_import,
)
router = APIRouter(
    prefix="/inventory",
    tags=["Library Inventory"]
)


class InventoryCreateRequest(BaseModel):

    library_id: str

    work_id: str

    isbn: str | None = None

    total_copies: int = 1

    available_copies: int = 1

    shelf_location: str | None = None


class InventoryUpdateRequest(BaseModel):

    isbn: str | None = None

    total_copies: int | None = None

    available_copies: int | None = None

    shelf_location: str | None = None


# ============================================================
# ADD PHYSICAL BOOK
# ============================================================

@router.post("/")
def create_inventory(
    request: InventoryCreateRequest,

    current_user=Depends(
        require_roles(
            "ADMIN",
            "LIBRARIAN"
        )
    )
):

    try:

        result = add_inventory(
            **request.model_dump()
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    return {
        "message": "Book added to library inventory",
        "inventory": result
    }


# ============================================================
# GET LIBRARY INVENTORY
# ============================================================

@router.get("/")
def list_inventory(
    library_id: str,

    limit: int = Query(
        20,
        ge=1,
        le=100
    ),

    offset: int = Query(
        0,
        ge=0
    )
):

    results = get_inventory(
        library_id,
        limit,
        offset
    )

    return {
        "library_id": library_id,
        "count": len(results),
        "limit": limit,
        "offset": offset,
        "results": results
    }


# ============================================================
# GET ONE PHYSICAL BOOK
# ============================================================

@router.get("/{library_id}/{work_id}")
def get_one_inventory_book(
    library_id: str,
    work_id: str
):

    result = get_inventory_book(
        library_id,
        work_id
    )

    if result is None:

        raise HTTPException(
            status_code=404,
            detail="Book is not present in this library's inventory"
        )

    return result


# ============================================================
# UPDATE PHYSICAL INVENTORY
# ============================================================

@router.put("/{library_id}/{work_id}")
def update_one_inventory_book(
    library_id: str,
    work_id: str,

    request: InventoryUpdateRequest,

    current_user=Depends(
        require_roles(
            "ADMIN",
            "LIBRARIAN"
        )
    )
):

    try:

        result = update_inventory(
            library_id,
            work_id,
            **request.model_dump(
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
            detail="Book is not present in this library's inventory"
        )

    return {
        "message": "Library inventory updated",
        "inventory": result
    }


# ============================================================
# DELETE PHYSICAL INVENTORY
# ============================================================

@router.delete("/{library_id}/{work_id}")
def delete_one_inventory_book(
    library_id: str,
    work_id: str,

    current_user=Depends(
        require_roles("ADMIN")
    )
):

    try:
        result = delete_inventory(library_id, work_id)
    except ValueError as error:
        raise HTTPException(
            status_code=404 if str(error) == "Inventory record not found" else 409,
            detail=str(error),
        )

    if result is None:

        raise HTTPException(
            status_code=404,
            detail="Book is not present in this library's inventory"
        )

    return {
        "message": "Book removed from library inventory"
    }
@router.post("/import/preview")
async def preview_inventory_import(
    library_id: str,
    file: UploadFile = File(...),

    current_user=Depends(
        require_roles(
            "ADMIN",
            "LIBRARIAN"
        )
    )
):

    try:

        file_bytes = await file.read()

        result = create_preview(
            library_id,
            file.filename,
            file_bytes
        )

        return result

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )
@router.post("/import/confirm")
def confirm_import(
    preview_id: str = Form(...),
    library_id: str = Form(...),
    current_user=Depends(
        require_roles("ADMIN", "LIBRARIAN")
    ),
):
    try:
        result = confirm_inventory_import(
            preview_id=preview_id,
            library_id=library_id,
        )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )
