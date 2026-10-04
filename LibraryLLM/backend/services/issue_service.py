from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4

from pymongo.errors import DuplicateKeyError

from backend.database.mongodb import (
    books_collection,
    library_inventory_collection,
    issues_collection,
    borrow_locks_collection,
    reservations_collection
)

from backend.services.reservation_service import (
    mark_next_reservation_ready
)

from backend.services.fine_service import (
    create_fine
)

from backend.services.activity_service import (
    create_activity
)
from backend.services.availability_service import (
    DEFAULT_LIBRARY_ID,
    get_availability_context,
)
from backend.services.book_capability_service import with_issue_capabilities


LOAN_PERIOD_DAYS = 14
_issue_creation_lock = Lock()

def get_next_issue_id():

    last_issue = issues_collection.find_one(
        {},
        sort=[("issue_id", -1)]
    )

    if last_issue is None:
        return 1

    return last_issue["issue_id"] + 1


def issue_book(user_id, work_id, library_id=DEFAULT_LIBRARY_ID):
    """Serialize issue creation so duplicate checks remain race-safe.

    The existing Mongo-backed validation and creation path stays authoritative.
    A local lock covers concurrent threads and a short MongoDB lease covers
    multiple API workers before they reach the existing duplicate check.
    """
    with _issue_creation_lock:
        now = datetime.now(timezone.utc)
        lock_id = f"{int(user_id)}:{work_id}"
        token = uuid4().hex
        # A crashed process cannot block this title forever.
        borrow_locks_collection.delete_one({
            "_id": lock_id,
            "expires_at": {"$lte": now},
        })
        try:
            borrow_locks_collection.insert_one({
                "_id": lock_id,
                "token": token,
                "expires_at": now + timedelta(minutes=5),
            })
        except DuplicateKeyError:
            raise ValueError("Borrowing this book is already in progress")
        try:
            return _issue_book(user_id, work_id, library_id)
        finally:
            borrow_locks_collection.delete_one({"_id": lock_id, "token": token})


def _issue_book(
    user_id,
    work_id,
    library_id=DEFAULT_LIBRARY_ID
):

    # ---------------------------------------------------------
    # 1. Find catalogue book
    # ---------------------------------------------------------

    book = books_collection.find_one(
        {
            "work_id": work_id
        }
    )

    if book is None:

        raise ValueError(
            "Book not found"
        )

    # ---------------------------------------------------------
    # 2. Resolve the same availability source returned by the book API.
    # ---------------------------------------------------------

    availability = get_availability_context(book, library_id)
    inventory = availability["inventory"]
    inventory_source = availability["source"]
    current_available = availability["available_copies"]

    if current_available <= 0:
        if inventory_source == "physical":
            raise ValueError(
                "No physical copies of this book "
                "are currently available at this library"
            )

        raise ValueError(
            "No copies of this book are currently available"
        )

    # ---------------------------------------------------------
    # 4. Check reservations
    # ---------------------------------------------------------

    reserved_book = reservations_collection.find_one(
        {
            "user_id": user_id,
            "work_id": work_id,
            "status": "READY_FOR_PICKUP"
        }
    )

    if reserved_book is None:

        ready_count = (
            reservations_collection.count_documents(
                {
                    "work_id": work_id,
                    "status": "READY_FOR_PICKUP"
                }
            )
        )

        if ready_count >= current_available:

            raise PermissionError(
                "This book is reserved for another user"
            )

    # ---------------------------------------------------------
    # 5. Prevent duplicate active issue
    # ---------------------------------------------------------

    existing_issue = issues_collection.find_one(
        {
            "user_id": user_id,
            "work_id": work_id,
            "status": "ISSUED"
        }
    )

    if existing_issue is not None:

        raise ValueError(
            "You already have this book issued"
        )

    # ---------------------------------------------------------
    # 6. Dates
    # ---------------------------------------------------------

    now = datetime.now(timezone.utc)

    due_date = (
        now + timedelta(
            days=LOAN_PERIOD_DAYS
        )
    )

    issue_id = get_next_issue_id()

    # ---------------------------------------------------------
    # 7. Create issue record
    # ---------------------------------------------------------

    issue = {
        "issue_id": issue_id,
        "user_id": user_id,
        "book_id": book["book_id"],
        "work_id": book["work_id"],
        "title": book["title"],

        # NEW
        "inventory_source": inventory_source,
        "library_id": library_id,

        "issued_at": now,
        "due_date": due_date,
        "returned_at": None,
        "status": "ISSUED",
        "fine_amount": 0
    }

    # ---------------------------------------------------------
    # 8. Decrease availability from the correct source
    # ---------------------------------------------------------

    if inventory_source == "physical":

        result = library_inventory_collection.update_one(
            {
                "library_id": library_id,
                "work_id": work_id,
                "available_copies": {
                    "$gt": 0
                }
            },
            {
                "$inc": {
                    "available_copies": -1
                }
            }
        )

    else:

        result = books_collection.update_one(
            {
                "work_id": work_id,
                "available_copies": {
                    "$gt": 0
                }
            },
            {
                "$inc": {
                    "available_copies": -1
                }
            }
        )

    if result.modified_count == 0:

        raise ValueError(
            "Book is no longer available"
        )

    # ---------------------------------------------------------
    # 9. Create issue record
    # ---------------------------------------------------------

    issues_collection.insert_one(
        issue
    )

    issue.pop("_id", None)

    # ---------------------------------------------------------
    # 10. Fulfill reservation
    # ---------------------------------------------------------

    if reserved_book is not None:

        reservations_collection.update_one(
            {
                "_id": reserved_book["_id"],
                "status": "READY_FOR_PICKUP"
            },
            {
                "$set": {
                    "status": "FULFILLED",
                    "fulfilled_at": now
                }
            }
        )

        create_activity(
            user_id=user_id,
            activity_type="RESERVATION_FULFILLED",
            description=(
                f"Reservation fulfilled: {book['title']}"
            ),
            reservation_id=reserved_book["reservation_id"],
            issue_id=issue_id,
            work_id=work_id,
            actor_user_id=user_id, title=book['title']
        )

    # ---------------------------------------------------------
    # 11. Activity
    # ---------------------------------------------------------

    create_activity(
        user_id=user_id,
        activity_type="BOOK_ISSUED",
        description=(
            f"Book issued: {book['title']}"
        ),
        issue_id=issue_id,
        work_id=work_id,
        actor_user_id=user_id, title=book['title']
    )

    return issue


def get_user_issues(user_id):

    issues = list(
        issues_collection.find(
            {
                "user_id": user_id
            },
            {
                "_id": 0
            }
        ).sort(
            "issued_at",
            -1
        )
    )

    from backend.services.loan_renewal_service import with_renewal_policy
    return with_renewal_policy(with_issue_capabilities(issues, user_id))


def get_issue_by_id(issue_id):

    issue = issues_collection.find_one(
        {
            "issue_id": issue_id
        },
        {
            "_id": 0
        }
    )

    return issue


def return_book(issue_id, user_id, *, actor_user_id=None):

    # ---------------------------------------------------------
    # 1. Find issue
    # ---------------------------------------------------------

    issue = issues_collection.find_one(
        {
            "issue_id": issue_id
        }
    )

    if issue is None:

        raise ValueError(
            "Issue record not found"
        )

    # ---------------------------------------------------------
    # 2. Verify ownership
    # ---------------------------------------------------------

    if issue["user_id"] != user_id:

        raise PermissionError(
            "You can only return books issued to you"
        )

    # ---------------------------------------------------------
    # 3. Verify active issue
    # ---------------------------------------------------------

    if issue["status"] != "ISSUED":

        raise ValueError(
            "This book has already been returned"
        )

    now = datetime.now(timezone.utc)

    # ---------------------------------------------------------
    # 4. Calculate fine
    # ---------------------------------------------------------

    due_date = issue["due_date"]

    if due_date.tzinfo is None:

        due_date = due_date.replace(
            tzinfo=timezone.utc
        )

    fine_amount = 0
    overdue_days = 0

    if now > due_date:

        overdue_days = (
            now.date()
            - due_date.date()
        ).days

        fine_amount = overdue_days * 5

    # ---------------------------------------------------------
    # 5. Mark issue returned
    # ---------------------------------------------------------

    result = issues_collection.update_one(
        {
            "issue_id": issue_id,
            "status": "ISSUED",
            "user_id": user_id,
            "due_date": issue['due_date']
        },
        {
            "$set": {
                "returned_at": now,
                "status": "RETURNED",
                "fine_amount": fine_amount
            }
        }
    )

    if result.modified_count == 0:

        raise ValueError(
            "Unable to return this book"
        )

    # ---------------------------------------------------------
    # 6. Create fine
    # ---------------------------------------------------------

    fine = create_fine(
        user_id=issue["user_id"],
        issue_id=issue["issue_id"],
        work_id=issue["work_id"],
        title=issue["title"],
        overdue_days=overdue_days
    )

    # ---------------------------------------------------------
    # 7. Activity
    # ---------------------------------------------------------

    create_activity(
        user_id=user_id,
        activity_type="BOOK_RETURNED",
        description=(
            f"Book returned: {issue['title']}"
        ),
        issue_id=issue_id,
        work_id=issue["work_id"],
        actor_user_id=user_id if actor_user_id is None else actor_user_id, title=issue['title']
    )

    # ---------------------------------------------------------
    # 8. Return copy to the SAME inventory source
    # ---------------------------------------------------------

    inventory_source = issue.get(
        "inventory_source",
        "catalogue"
    )

    library_id = issue.get(
        "library_id",
        DEFAULT_LIBRARY_ID
    )

    if inventory_source == "physical":

        library_inventory_collection.update_one(
            {
                "library_id": library_id,
                "work_id": issue["work_id"]
            },
            {
                "$inc": {
                    "available_copies": 1
                }
            }
        )

    else:

        books_collection.update_one(
            {
                "work_id": issue["work_id"]
            },
            {
                "$inc": {
                    "available_copies": 1
                }
            }
        )

    # ---------------------------------------------------------
    # 9. Check reservation queue
    # ---------------------------------------------------------

    ready_reservation = (
        mark_next_reservation_ready(
            issue["work_id"]
        )
    )

    # ---------------------------------------------------------
    # 10. Get updated issue
    # ---------------------------------------------------------

    updated_issue = issues_collection.find_one(
        {
            "issue_id": issue_id
        },
        {
            "_id": 0
        }
    )

    from backend.services.loan_notification_service import reconcile_loan_notifications
    reconcile_loan_notifications(issue_id, reason='LOAN_RETURNED', now=now)

    return {
        "issue": updated_issue,
        "fine": fine,
        "reservation_ready": ready_reservation
    }
