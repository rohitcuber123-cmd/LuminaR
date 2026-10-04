from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import (
    get_current_user,
    require_roles
)

from backend.services.fine_service import (
    get_fine_by_id,
    get_user_fines,
    get_all_fines,
    pay_fine
)


router = APIRouter(
    prefix="/fines",
    tags=["Fines"]
)


# --------------------------------------------------
# MY FINES
# --------------------------------------------------

@router.get("/my")
def my_fines(
    current_user=Depends(get_current_user)
):

    fines = get_user_fines(
        int(current_user["sub"])
    )

    total_unpaid = sum(
        fine["amount"]
        for fine in fines
        if fine["status"] == "UNPAID"
    )

    return {
        "count": len(fines),
        "total_unpaid": total_unpaid,
        "fines": fines
    }


# --------------------------------------------------
# ALL FINES
# ADMIN + LIBRARIAN
# --------------------------------------------------

@router.get("/all")
def all_fines(
    current_user=Depends(
        require_roles(
            "ADMIN",
            "LIBRARIAN"
        )
    )
):

    fines = get_all_fines()

    total_unpaid = sum(
        fine["amount"]
        for fine in fines
        if fine["status"] == "UNPAID"
    )

    return {
        "count": len(fines),
        "total_unpaid": total_unpaid,
        "fines": fines
    }


# --------------------------------------------------
# FINE DETAILS
# --------------------------------------------------

@router.get("/{fine_id}")
def fine_details(
    fine_id: int,
    current_user=Depends(get_current_user)
):

    fine = get_fine_by_id(
        fine_id
    )

    if fine is None:

        raise HTTPException(
            status_code=404,
            detail="Fine not found"
        )

    # Admin and librarian can view any fine
    if current_user["role"] in [
        "ADMIN",
        "LIBRARIAN"
    ]:

        return fine

    # General users can only view their own fine
    if fine["user_id"] != int(
        current_user["sub"]
    ):

        raise HTTPException(
            status_code=403,
            detail="You can only view your own fine"
        )

    return fine


# --------------------------------------------------
# PAY FINE
# --------------------------------------------------

@router.post("/pay/{fine_id}")
def pay(
    fine_id: int,
    current_user=Depends(get_current_user)
):

    try:

        fine = pay_fine(
            fine_id,
            int(current_user["sub"])
        )

    except PermissionError as error:

        raise HTTPException(
            status_code=403,
            detail=str(error)
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    return {
        "message": "Fine paid successfully",
        "fine": fine
    }