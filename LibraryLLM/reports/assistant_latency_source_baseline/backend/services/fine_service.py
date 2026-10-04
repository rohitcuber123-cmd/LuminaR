from datetime import datetime, timezone

from backend.database.mongodb import fines_collection

from backend.services.activity_service import (
    create_activity
)


FINE_PER_DAY = 5


def get_next_fine_id():

    last_fine = fines_collection.find_one(
        {},
        sort=[("fine_id", -1)]
    )

    if last_fine is None:
        return 1

    return last_fine["fine_id"] + 1


def create_fine(
    user_id,
    issue_id,
    work_id,
    title,
    overdue_days
):

    # No fine if the book is returned on time
    if overdue_days <= 0:
        return None

    # Calculate fine
    amount = overdue_days * FINE_PER_DAY

    # Prevent duplicate fine for the same issue
    existing_fine = fines_collection.find_one(
        {
            "issue_id": issue_id
        }
    )

    if existing_fine is not None:

        existing_fine.pop("_id", None)

        return existing_fine

    now = datetime.now(timezone.utc)

    fine = {
        "fine_id": get_next_fine_id(),
        "user_id": user_id,
        "issue_id": issue_id,
        "work_id": work_id,
        "title": title,
        "overdue_days": overdue_days,
        "amount": amount,
        "status": "UNPAID",
        "created_at": now,
        "paid_at": None
    }

    # Create fine
    fines_collection.insert_one(
        fine
    )

    fine.pop("_id", None)

    # Activity: fine created
    create_activity(
        user_id=user_id,
        activity_type="FINE_CREATED",
        description=f"Fine created: ₹{amount}",
        issue_id=issue_id,
        fine_id=fine["fine_id"],
        work_id=work_id
    )

    return fine


def get_fine_by_id(fine_id):

    return fines_collection.find_one(
        {
            "fine_id": fine_id
        },
        {
            "_id": 0
        }
    )


def get_user_fines(user_id):

    fines = list(
        fines_collection.find(
            {
                "user_id": user_id
            },
            {
                "_id": 0
            }
        ).sort(
            "created_at",
            -1
        )
    )

    return fines


def get_all_fines():

    fines = list(
        fines_collection.find(
            {},
            {
                "_id": 0
            }
        ).sort(
            "created_at",
            -1
        )
    )

    return fines


def pay_fine(fine_id, user_id):

    # Find fine
    fine = fines_collection.find_one(
        {
            "fine_id": fine_id
        }
    )

    if fine is None:

        raise ValueError(
            "Fine not found"
        )

    # Make sure the user owns the fine
    if fine["user_id"] != user_id:

        raise PermissionError(
            "You can only pay your own fine"
        )

    # Prevent paying an already-paid fine
    if fine["status"] == "PAID":

        raise ValueError(
            "This fine has already been paid"
        )

    now = datetime.now(timezone.utc)

    # Mark fine as paid
    result = fines_collection.update_one(
        {
            "fine_id": fine_id,
            "status": "UNPAID"
        },
        {
            "$set": {
                "status": "PAID",
                "paid_at": now
            }
        }
    )

    if result.modified_count == 0:

        raise ValueError(
            "Unable to process fine payment"
        )

    # Activity: fine paid
    create_activity(
        user_id=user_id,
        activity_type="FINE_PAID",
        description=f"Fine paid: ₹{fine['amount']}",
        fine_id=fine_id,
        work_id=fine.get("work_id")
    )

    return get_fine_by_id(
        fine_id
    )