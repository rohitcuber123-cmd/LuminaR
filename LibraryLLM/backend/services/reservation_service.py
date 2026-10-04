from datetime import datetime, timezone

from backend.database.mongodb import (
    books_collection,
    reservations_collection
)

from backend.services.activity_service import (
    create_activity
)
from backend.services.availability_service import (
    get_availability_context,
)


def get_next_reservation_id():

    last_reservation = reservations_collection.find_one(
        {},
        sort=[("reservation_id", -1)]
    )

    if last_reservation is None:
        return 1

    return last_reservation["reservation_id"] + 1


def create_reservation(user_id, work_id):

    # Find book
    book = books_collection.find_one(
        {
            "work_id": work_id
        }
    )

    if book is None:

        raise ValueError(
            "Book not found"
        )

    # Reservation eligibility must use the same inventory source as issuing.
    availability = get_availability_context(book)

    # Reservation only makes sense when no copies are currently available.
    if availability["available_copies"] > 0:

        raise ValueError(
            "Book is currently available. You can issue it instead."
        )

    # Prevent duplicate active reservation
    existing_reservation = reservations_collection.find_one({
        "user_id": user_id,
        "work_id": work_id,
        "status": "ACTIVE"
    })

    if existing_reservation is not None:

        raise ValueError(
            "You already have an active reservation for this book"
        )

    now = datetime.now(timezone.utc)

    reservation_id = get_next_reservation_id()

    reservation = {
        "reservation_id": reservation_id,
        "user_id": user_id,
        "book_id": book["book_id"],
        "work_id": book["work_id"],
        "title": book["title"],
        "reserved_at": now,
        "status": "ACTIVE",
        "fulfilled_at": None,
        "cancelled_at": None
    }

    # Create reservation
    reservations_collection.insert_one(
        reservation
    )

    reservation.pop("_id", None)

    # Activity: reservation created
    create_activity(
        user_id=user_id,
        activity_type="RESERVATION_CREATED",
        description=(
            f"Reservation created: {book['title']}"
        ),
        reservation_id=reservation_id,
        work_id=work_id,
        actor_user_id=user_id, title=book['title']
    )

    return reservation


def get_user_reservations(user_id):

    reservations = list(
        reservations_collection.find(
            {
                "user_id": user_id
            },
            {
                "_id": 0
            }
        ).sort(
            "reserved_at",
            -1
        )
    )

    return reservations


def get_reservation_by_id(reservation_id):

    reservation = reservations_collection.find_one(
        {
            "reservation_id": reservation_id
        },
        {
            "_id": 0
        }
    )

    return reservation


def cancel_reservation(
    reservation_id,
    user_id
):

    reservation = reservations_collection.find_one(
        {
            "reservation_id": reservation_id
        }
    )

    if reservation is None:

        raise ValueError(
            "Reservation not found"
        )

    if reservation["user_id"] != user_id:

        raise PermissionError(
            "You can only cancel your own reservation"
        )

    if reservation["status"] not in (
        "ACTIVE",
        "READY_FOR_PICKUP"
    ):

        raise ValueError(
            "This reservation is no longer active"
        )

    now = datetime.now(timezone.utc)

    result = reservations_collection.update_one(
        {
            "reservation_id": reservation_id,
            "status": {
                "$in": [
                    "ACTIVE",
                    "READY_FOR_PICKUP"
                ]
            }
        },
        {
            "$set": {
                "status": "CANCELLED",
                "cancelled_at": now
            }
        }
    )

    if result.modified_count == 0:

        raise ValueError(
            "Unable to cancel reservation"
        )

    # Activity: reservation cancelled
    create_activity(
        user_id=reservation["user_id"],
        activity_type="RESERVATION_CANCELLED",
        description=(
            f"Reservation cancelled: "
            f"{reservation['title']}"
        ),
        reservation_id=reservation_id,
        work_id=reservation["work_id"],
        actor_user_id=user_id, title=reservation['title']
    )

    return get_reservation_by_id(
        reservation_id
    )


def get_next_reservation(work_id):

    reservation = reservations_collection.find_one(
        {
            "work_id": work_id,
            "status": "ACTIVE"
        },
        {
            "_id": 0
        },
        sort=[
            ("reserved_at", 1)
        ]
    )

    return reservation


def mark_next_reservation_ready(work_id):

    reservation = reservations_collection.find_one(
        {
            "work_id": work_id,
            "status": "ACTIVE"
        },
        sort=[
            ("reserved_at", 1)
        ]
    )

    if reservation is None:

        return None

    now = datetime.now(timezone.utc)

    result = reservations_collection.update_one(
        {
            "_id": reservation["_id"],
            "status": "ACTIVE"
        },
        {
            "$set": {
                "status": "READY_FOR_PICKUP"
            }
        }
    )

    if result.modified_count == 0:

        return None

    # Activity: reservation ready
    from backend.services.notification_service import notify_reservation_available
    notify_reservation_available(reservation)
    create_activity(
        user_id=reservation["user_id"],
        activity_type="RESERVATION_READY",
        description=(
            f"Reservation ready for pickup: "
            f"{reservation['title']}"
        ),
        reservation_id=reservation["reservation_id"],
        work_id=reservation["work_id"],
        title=reservation['title']
    )

    return get_reservation_by_id(
        reservation["reservation_id"]
    )
