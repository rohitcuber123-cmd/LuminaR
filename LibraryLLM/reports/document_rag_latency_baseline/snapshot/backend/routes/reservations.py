from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.dependencies import (
    get_current_user,
    require_roles
)

from backend.services.reservation_service import (
    create_reservation,
    get_user_reservations,
    get_reservation_by_id,
    cancel_reservation,
    get_next_reservation
)


router = APIRouter(
    prefix="/reservations",
    tags=["Reservations"]
)


class ReservationRequest(BaseModel):
    work_id: str


# --------------------------------------------------
# CREATE RESERVATION
# --------------------------------------------------

@router.post("/")
def reserve_book(
    request: ReservationRequest,
    current_user=Depends(get_current_user)
):

    try:

        reservation = create_reservation(
            int(current_user["sub"]),
            request.work_id
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    return {
        "message": "Book reserved successfully",
        "reservation": reservation
    }


# --------------------------------------------------
# MY RESERVATIONS
# --------------------------------------------------

@router.get("/my")
def my_reservations(
    current_user=Depends(get_current_user)
):

    reservations = get_user_reservations(
        int(current_user["sub"])
    )

    return {
        "count": len(reservations),
        "reservations": reservations
    }


# --------------------------------------------------
# ALL RESERVATIONS
# ADMIN + LIBRARIAN
# --------------------------------------------------

@router.get("/all")
def all_reservations(
    current_user=Depends(
        require_roles(
            "ADMIN",
            "LIBRARIAN"
        )
    )
):

    from backend.database.mongodb import reservations_collection

    reservations = list(
        reservations_collection.find(
            {},
            {"_id": 0}
        ).sort(
            "reserved_at",
            -1
        )
    )

    return {
        "count": len(reservations),
        "reservations": reservations
    }


# --------------------------------------------------
# RESERVATION DETAILS
# --------------------------------------------------

@router.get("/{reservation_id}")
def reservation_details(
    reservation_id: int,
    current_user=Depends(get_current_user)
):

    reservation = get_reservation_by_id(
        reservation_id
    )

    if reservation is None:

        raise HTTPException(
            status_code=404,
            detail="Reservation not found"
        )

    # Admin and librarian can view any reservation
    if current_user["role"] in [
        "ADMIN",
        "LIBRARIAN"
    ]:

        return reservation

    # General users can only view their own
    if reservation["user_id"] != int(
        current_user["sub"]
    ):

        raise HTTPException(
            status_code=403,
            detail="You can only view your own reservation"
        )

    return reservation


# --------------------------------------------------
# CANCEL RESERVATION
# --------------------------------------------------

@router.post("/cancel/{reservation_id}")
def cancel(
    reservation_id: int,
    current_user=Depends(get_current_user)
):

    try:

        reservation = cancel_reservation(
            reservation_id,
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
        "message": "Reservation cancelled successfully",
        "reservation": reservation
    }


# --------------------------------------------------
# NEXT RESERVATION
# ADMIN + LIBRARIAN
# --------------------------------------------------

@router.get("/queue/{work_id}")
def next_reservation(
    work_id: str,
    current_user=Depends(
        require_roles(
            "ADMIN",
            "LIBRARIAN"
        )
    )
):

    reservation = get_next_reservation(
        work_id
    )

    if reservation is None:

        return {
            "message": "No active reservations",
            "reservation": None
        }

    return reservation