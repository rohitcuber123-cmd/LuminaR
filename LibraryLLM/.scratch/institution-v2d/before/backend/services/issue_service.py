"""Read-only historical issues. Canonical lending is library_lending_service."""
from backend.database.mongodb import issues_collection, books_collection, reservations_collection
from backend.services.book_capability_service import with_issue_capabilities
from backend.platform_dependencies import retirement
from backend.services.availability_service import DEFAULT_LIBRARY_ID
LOAN_PERIOD_DAYS = 14

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


def issue_book(user_id, work_id, library_id=DEFAULT_LIBRARY_ID):
    retirement()


def return_book(issue_id, user_id, *, actor_user_id=None):
    retirement()
