"""Read-only historical reservations. Mutations use library_reservation_service."""
from backend.database.mongodb import reservations_collection
from backend.platform_dependencies import retirement

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


def create_reservation(user_id, work_id):
    retirement()


def cancel_reservation(reservation_id, user_id):
    retirement()
