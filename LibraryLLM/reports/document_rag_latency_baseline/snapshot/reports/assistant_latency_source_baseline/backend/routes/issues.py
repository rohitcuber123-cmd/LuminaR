from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.dependencies import (
    get_current_user,
    require_roles
)

from backend.services.issue_service import (
    issue_book,
    get_user_issues,
    get_issue_by_id,
    return_book
)

from backend.database.mongodb import (
    issues_collection
)


router = APIRouter(
    prefix="/issues",
    tags=["Issues"]
)


class IssueRequest(BaseModel):
    work_id: str


# --------------------------------------------------
# ISSUE BOOK
# --------------------------------------------------

@router.post("/issue")
def issue(
    request: IssueRequest,
    current_user=Depends(get_current_user)
):

    try:

        result = issue_book(
            int(current_user["sub"]),
            request.work_id
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
        "message": "Book issued successfully",
        "issue": result
    }


# --------------------------------------------------
# MY ISSUES
# --------------------------------------------------

@router.get("/my")
def my_issues(
    current_user=Depends(get_current_user)
):

    issues = get_user_issues(
        int(current_user["sub"])
    )

    return {
        "count": len(issues),
        "issues": issues
    }


# --------------------------------------------------
# ALL ISSUES
# ADMIN + LIBRARIAN
# --------------------------------------------------

@router.get("/all")
def all_issues(
    current_user=Depends(
        require_roles(
            "ADMIN",
            "LIBRARIAN"
        )
    )
):

    issues = list(
        issues_collection.find(
            {},
            {
                "_id": 0
            }
        ).sort(
            "issued_at",
            -1
        )
    )

    return {
        "count": len(issues),
        "issues": issues
    }


# --------------------------------------------------
# ISSUE DETAILS
# --------------------------------------------------

@router.get("/{issue_id}")
def issue_details(
    issue_id: int,
    current_user=Depends(get_current_user)
):

    issue = get_issue_by_id(
        issue_id
    )

    if issue is None:

        raise HTTPException(
            status_code=404,
            detail="Issue record not found"
        )

    # Admin and librarian can view any issue
    if current_user["role"] in [
        "ADMIN",
        "LIBRARIAN"
    ]:

        return issue

    # General users can only view their own issue
    if issue["user_id"] != int(
        current_user["sub"]
    ):

        raise HTTPException(
            status_code=403,
            detail="You can only view your own issue"
        )

    return issue


# --------------------------------------------------
# RETURN BOOK
# --------------------------------------------------

@router.post("/return/{issue_id}")
def return_issued_book(
    issue_id: int,
    current_user=Depends(get_current_user)
):

    try:

        result = return_book(
            issue_id,
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
    "message": "Book returned successfully",
    "issue": result["issue"],
    "fine": result["fine"],
    "reservation_ready": result["reservation_ready"]
}