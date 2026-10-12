from backend.platform_dependencies import require_platform_admin, has_platform_admin
from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import (
    get_current_user,
)

from backend.services.activity_service import (
    get_user_activity,
    get_all_activity,
    get_activity_by_id
)


router = APIRouter(
    prefix="/activity",
    tags=["Activity"]
)


# --------------------------------------------------
# MY ACTIVITY
# --------------------------------------------------

@router.get("/my")
def my_activity(
    current_user=Depends(get_current_user)
):

    activities = get_user_activity(
        int(current_user["sub"])
    )

    return {
        "count": len(activities),
        "activities": activities
    }


# --------------------------------------------------
# ALL ACTIVITY
# ADMIN + LIBRARIAN
# --------------------------------------------------

@router.get("/all")
def all_activity(
    current_user=Depends(
        require_platform_admin
    )
):

    activities = get_all_activity()

    return {
        "count": len(activities),
        "activities": activities
    }


# --------------------------------------------------
# ACTIVITY DETAILS
# --------------------------------------------------

@router.get("/{activity_id}")
def activity_details(
    activity_id: int,
    current_user=Depends(get_current_user)
):

    activity = get_activity_by_id(
        activity_id
    )

    if activity is None:

        raise HTTPException(
            status_code=404,
            detail="Activity record not found"
        )

    # Admin and librarian can view any activity
    if has_platform_admin(current_user):

        return activity

    # General users can only view their own activity
    if activity["user_id"] != int(
        current_user["sub"]
    ):

        raise HTTPException(
            status_code=403,
            detail="You can only view your own activity"
        )

    return activity
    