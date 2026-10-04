from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from recommendation.recommendation_service import (
    build_user_profile,
    get_recommendations,
    FEEDBACK_WEIGHTS
)
from backend.utils.jwt_utils import (
    decode_access_token
)
from backend.database.mongodb import (
    recommendation_feedbacks_collection
)


from recommendation.ranked_pages import RankedRecommendationPages
ranked_recommendations = RankedRecommendationPages(lambda *args, **kwargs: get_recommendations(*args, **kwargs))

app = FastAPI(
    title="LuminaR Recommendation API",
    version="2.0.0"
)
# ============================================================
# CORS
# ============================================================

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",

    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,

    allow_origins=ALLOWED_ORIGINS,

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)

# ============================================================
# VALID CLIENT FEEDBACK TYPES
#
# ISSUED / RESERVED / RATED come from the library system.
# Clients may only submit behavioral interaction events.
# ============================================================

VALID_CLIENT_FEEDBACK_TYPES = {
    "VIEWED",
    "CLICKED",
    "DISMISSED",
    "NOT_INTERESTED"
}


# ============================================================
# AUTHENTICATION HELPER
# ============================================================

def get_user_from_token(
    authorization
):

    if not authorization:

        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )

    if not authorization.startswith(
        "Bearer "
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header"
        )

    token = authorization.split(
        " ",
        1
    )[1]

    payload = decode_access_token(
        token
    )

    if payload is None:

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    return payload


# ============================================================
# FEEDBACK ID HELPER
# ============================================================

def get_next_feedback_id():

    last = recommendation_feedbacks_collection.find_one(
        {},
        sort=[("feedback_id", -1)]
    )

    if last is None:
        return 1

    return last["feedback_id"] + 1


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "system": "LuminaR Recommendation API",
        "version": "2.0.0",
        "status": "ready"
    }


# ============================================================
# PROFILE
# ============================================================

@app.get("/profile")
def profile(
    authorization: str | None = Header(
        default=None
    )
):

    user = get_user_from_token(
        authorization
    )

    user_profile = build_user_profile(
        int(user["sub"])
    )

    return {
        "user_id": int(
            user["sub"]
        ),
        "queries": user_profile[
            "queries"
        ],
        "work_ids": user_profile[
            "work_ids"
        ],
        "subjects": dict(
            user_profile["subjects"]
        ),
        "authors": dict(
            user_profile["authors"]
        ),
        "search_interests": user_profile.get(
            "search_interests",
            []
        ),
        "feedback_count": len(
            user_profile.get(
                "feedback",
                []
            )
        )
    }


# ============================================================
# RECOMMENDATIONS
# ============================================================

@app.get("/recommendations")
def recommendations(
    limit: int = 10,
    strict_service_errors: bool = False,
    offset: int = 0,
    authorization: str | None = Header(
        default=None
    )
):

    user = get_user_from_token(
        authorization
    )

    try:
        return ranked_recommendations.page(user, authorization,limit,offset,strict_service_errors=strict_service_errors)
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503,"Recommendations cannot be loaded right now.") from exc


# ============================================================
# FEEDBACK — POST (V2.5)
# ============================================================

class SeedRecommendationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    work_id: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')
    limit: int = Field(default=10, ge=1, le=50)
    offset: int = Field(default=0, ge=0, le=50)


@app.post('/recommendations/from-book')
def recommendations_from_book(request: SeedRecommendationRequest,
                              authorization: str | None = Header(default=None)):
    user = get_user_from_token(authorization)
    try:
        return ranked_recommendations.page(user, authorization, request.limit, request.offset,
                                           seed_work_id=request.work_id,strict_service_errors=True)
    except ValueError as exc:
        raise HTTPException(400 if 'limit' in str(exc) else 404,str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503,"Recommendations cannot be loaded right now.") from exc



class FeedbackRequest(BaseModel):
    work_id: str
    feedback_type: str


@app.post("/feedback")
def submit_feedback(
    request: FeedbackRequest,
    authorization: str | None = Header(
        default=None
    )
):

    user = get_user_from_token(
        authorization
    )

    user_id = int(user["sub"])

    # Validate feedback type
    if request.feedback_type not in VALID_CLIENT_FEEDBACK_TYPES:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid feedback_type: "
                f"'{request.feedback_type}'. "
                f"Allowed: "
                f"{sorted(VALID_CLIENT_FEEDBACK_TYPES)}"
            )
        )

    # Validate work_id is not empty
    if not request.work_id.strip():

        raise HTTPException(
            status_code=400,
            detail="work_id must not be empty"
        )

    now = datetime.now(timezone.utc)

    feedback = {
        "feedback_id": get_next_feedback_id(),
        "user_id": user_id,
        "work_id": request.work_id.strip(),
        "feedback_type": request.feedback_type,
        "source": "RECOMMENDATION",
        "created_at": now
    }

    recommendation_feedbacks_collection.insert_one(
        feedback
    )

    feedback.pop("_id", None)

    return {
        "status": "recorded",
        "user_id": user_id,
        "work_id": request.work_id.strip(),
        "feedback_type": request.feedback_type,
        "feedback_id": feedback["feedback_id"]
    }


# ============================================================
# FEEDBACK — GET (V2.5)
# ============================================================

@app.get("/feedback")
def get_feedback(
    limit: int = 50,
    authorization: str | None = Header(
        default=None
    )
):

    user = get_user_from_token(
        authorization
    )

    user_id = int(user["sub"])

    if limit < 1:
        limit = 1

    if limit > 200:
        limit = 200

    feedbacks = list(
        recommendation_feedbacks_collection.find(
            {
                "user_id": user_id
            },
            {
                "_id": 0
            }
        ).sort(
            "created_at",
            -1
        ).limit(limit)
    )

    return {
        "user_id": user_id,
        "count": len(feedbacks),
        "feedbacks": feedbacks
    }
