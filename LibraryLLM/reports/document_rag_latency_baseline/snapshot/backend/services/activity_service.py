from datetime import datetime, timezone

from backend.database.mongodb import activity_collection


def get_next_activity_id():

    last_activity = activity_collection.find_one(
        {},
        sort=[("activity_id", -1)]
    )

    if last_activity is None:
        return 1

    return last_activity["activity_id"] + 1


def create_activity(
    user_id,
    activity_type,
    description,
    issue_id=None,
    reservation_id=None,
    fine_id=None,
    work_id=None
):

    activity = {
        "activity_id": get_next_activity_id(),
        "user_id": user_id,
        "activity_type": activity_type,
        "description": description,
        "issue_id": issue_id,
        "reservation_id": reservation_id,
        "fine_id": fine_id,
        "work_id": work_id,
        "created_at": datetime.now(timezone.utc)
    }

    activity_collection.insert_one(
        activity
    )

    activity.pop("_id", None)

    return activity


def get_user_activity(user_id):

    activities = list(
        activity_collection.find(
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

    return activities


def get_all_activity():

    activities = list(
        activity_collection.find(
            {},
            {
                "_id": 0
            }
        ).sort(
            "created_at",
            -1
        )
    )

    return activities


def get_activity_by_id(activity_id):

    activity = activity_collection.find_one(
        {
            "activity_id": activity_id
        },
        {
            "_id": 0
        }
    )

    return activity