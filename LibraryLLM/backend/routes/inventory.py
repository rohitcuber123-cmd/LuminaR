from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.platform_dependencies import retirement
from backend.dependencies import get_current_user
from backend.institution_dependencies import require_library_staff
from backend.services.institution_repository import collection
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
        get_current_user
    )
):

    retirement()


# ============================================================
# GET LIBRARY INVENTORY
# ============================================================

@router.get("/")
def list_inventory(
    library_id: str,
    current_user=Depends(get_current_user),

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

    legacy_staff_context(library_id, current_user)
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
    work_id: str,
    current_user=Depends(get_current_user)
):

    legacy_staff_context(library_id, current_user)
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
        get_current_user
    )
):

    retirement()


# ============================================================
# DELETE PHYSICAL INVENTORY
# ============================================================

@router.delete("/{library_id}/{work_id}")
def delete_one_inventory_book(
    library_id: str,
    work_id: str,

    current_user=Depends(
        get_current_user
    )
):

    retirement()
@router.post("/import/preview")
async def preview_inventory_import(
    library_id: str,
    file: UploadFile = File(...),

    current_user=Depends(
        get_current_user
    )
):

    retirement()
@router.post("/import/confirm")
def confirm_import(
    preview_id: str = Form(...),
    library_id: str = Form(...),
    current_user=Depends(
        get_current_user
    ),
):
    retirement()


def legacy_staff_context(library_id, actor):
    alias = collection('library_aliases').find_one({'legacy_library_id': library_id})
    canonical = alias['canonical_library_id'] if alias else library_id
    if not collection('libraries').find_one({'library_id': canonical, 'status': 'ACTIVE'}):
        retirement()
    return require_library_staff(canonical, actor)
