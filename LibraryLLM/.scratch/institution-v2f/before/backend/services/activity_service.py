from datetime import datetime, timezone
from threading import Lock
from pymongo.errors import DuplicateKeyError

from backend.database.mongodb import activity_collection

_activity_creation_lock = Lock()


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
    work_id=None,
    actor_user_id=None,
    title=None,
    old_due_date=None,
    new_due_date=None,
    event_key=None,
    occurred_at=None
):

    activity = {
        "activity_id": get_next_activity_id(),
        "user_id": user_id,
        "actor_user_id": actor_user_id,
        "title": title,
        "activity_type": activity_type,
        "description": description,
        "issue_id": issue_id,
        "reservation_id": reservation_id,
        "fine_id": fine_id,
        "work_id": work_id,
        "created_at": occurred_at or datetime.now(timezone.utc)
    }

    if old_due_date is not None:
        activity.update(old_due_date=old_due_date, new_due_date=new_due_date)
    if event_key:
        activity['event_key'] = event_key
    with _activity_creation_lock:
        for _ in range(5):
            activity['activity_id'] = get_next_activity_id()
            try:
                if event_key:
                    activity_collection.update_one({'event_key': event_key}, {'$setOnInsert': activity}, upsert=True)
                    return activity_collection.find_one({'event_key': event_key}, {'_id': 0})
                activity_collection.insert_one(activity)
                activity.pop('_id', None)
                return activity
            except DuplicateKeyError:
                if event_key:
                    existing = activity_collection.find_one({'event_key': event_key}, {'_id': 0})
                    if existing:
                        return existing
    raise RuntimeError('Unable to allocate activity record.')


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
