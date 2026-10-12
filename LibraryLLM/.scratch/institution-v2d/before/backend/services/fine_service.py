"""Read-only historical fines. Canonical fees use library_fee_service."""
from backend.database.mongodb import fines_collection
from backend.platform_dependencies import retirement

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
    retirement()
