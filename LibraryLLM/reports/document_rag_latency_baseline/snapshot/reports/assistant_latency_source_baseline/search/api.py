import os
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from search.luminar_search import LuminaRSearchEngine

from backend.utils.jwt_utils import (
    decode_access_token
)

from backend.services.search_history_service import (
    create_search_history,
    get_user_search_history
)


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="LuminaR Search API",
    version="1.0.0"
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
# LOAD SEARCH ENGINE ONCE
# ============================================================

print()
print("=" * 60)
print("STARTING LUMINAR API")
print("=" * 60)

engine = LuminaRSearchEngine()


@app.on_event("startup")
def start_index_sync():
    engine.index_manager.start()
    lexical_writer = getattr(engine, "lexical_writer", None)
    if lexical_writer is not None:
        lexical_writer.start()


@app.on_event("shutdown")
def stop_index_sync():
    engine.close()

print()
print("LuminaR API ready.")
print("=" * 60)


# ============================================================
# REQUEST MODEL
# ============================================================

class SearchRequest(BaseModel):

    # Natural-language search query
    query: str

    # Number of results requested
    top_k: int = 10

    # Optional library filter
    library_id: str | None = None

    # Only return books physically available
    # at the specified library
    available_at_library: bool = False

    # Save search in user's search history
    save_history: bool = True


# ============================================================
# HEALTH
# ============================================================

@app.get("/")
def root():

    return {
        "system": "LuminaR",
        "status": "ready"
    }


@app.get("/health")
def health():

    index_status = engine.index_manager.status()
    lexical_store = getattr(engine, "lexical_store", None)
    try:
        lexical_status = (lexical_store.health() if lexical_store is not None else
                          {"lexical_enabled": False, "lexical_available": False})
        writer = getattr(engine, "lexical_writer", None)
        lexical_status["lexical_worker_enabled"] = bool(
            writer is not None and writer.thread is not None and writer.thread.is_alive())
        lexical_status["lexical_ranking_enabled"] = (
            os.getenv("LEXICAL_SEARCH_ENABLED", "false").lower() == "true")
    except Exception as error:
        lexical_status = {"lexical_enabled": False, "lexical_available": False,
                          "lexical_last_error": type(error).__name__}
    return {
        "status": "healthy" if index_status["index_status"] == "HEALTHY" else "degraded",
        **index_status,
        "system": "LuminaR",
        "device": engine.device,
        "hnsw_vectors": int(
            index_status["active_vectors"]
        ),
        "lexical": lexical_status,
    }


# ============================================================
# JWT AUTHENTICATION
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
# SEARCH
# ============================================================

@app.post("/search")
def search(
    request: SearchRequest,
    authorization: str | None = Header(
        default=None
    )
):

    # --------------------------------------------------------
    # AUTHENTICATE USER
    # --------------------------------------------------------

    user = get_user_from_token(
        authorization
    )

    # --------------------------------------------------------
    # VALIDATE QUERY
    # --------------------------------------------------------

    query = request.query.strip()

    if not query:

        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty."
        )

    # --------------------------------------------------------
    # VALIDATE TOP K
    # --------------------------------------------------------

    if request.top_k < 1:

        raise HTTPException(
            status_code=400,
            detail="top_k must be greater than 0."
        )

    if request.top_k > 50:

        raise HTTPException(
            status_code=400,
            detail="top_k cannot be greater than 50."
        )

    # --------------------------------------------------------
    # VALIDATE LIBRARY FILTER
    # --------------------------------------------------------

    if (
        request.available_at_library
        and not request.library_id
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "library_id is required when "
                "available_at_library is true."
            )
        )

    try:

        # ----------------------------------------------------
        # RUN LUMINAR SEARCH
        # ----------------------------------------------------

        result = engine.search(

            query=query,

            top_k=request.top_k,

            library_id=request.library_id,

            available_at_library=(
                request.available_at_library
            )
        )

        # ----------------------------------------------------
        # SAVE SEARCH HISTORY
        # ----------------------------------------------------

        if request.save_history:

            # user["sub"] contains the string representation of integer user_id
            # e.g., "4" for user_id=4
            # NOT the MongoDB _id ObjectId
            try:
                user_id_int = int(user["sub"])
            except (ValueError, TypeError):
                # If conversion fails, skip history saving
                pass
            else:
                history_record = create_search_history(
                    user_id=user_id_int,
                    query=query,
                    top_k=request.top_k,
                    results=result["results"]
                )
                
                if history_record is None:
                    print(f"[WARN] Search completed but history not saved for user {user_id_int}")

        # ----------------------------------------------------
        # RETURN RESULT
        # ----------------------------------------------------

        return result

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail="LuminaR search is temporarily unavailable."
        )


# ============================================================
# SEARCH HISTORY
# ============================================================

@app.get("/search-history")
def search_history(
    limit: int = 50,

    authorization: str | None = Header(
        default=None
    )
):

    # --------------------------------------------------------
    # AUTHENTICATE USER
    # --------------------------------------------------------

    user = get_user_from_token(
        authorization
    )

    # --------------------------------------------------------
    # VALIDATE LIMIT
    # --------------------------------------------------------

    if limit < 1:

        raise HTTPException(
            status_code=400,
            detail="limit must be greater than 0"
        )

    if limit > 100:

        limit = 100

    # --------------------------------------------------------
    # GET HISTORY
    # --------------------------------------------------------

    # user["sub"] contains the string representation of integer user_id
    # e.g., "4" for user_id=4
    try:
        user_id_int = int(user["sub"])
    except (ValueError, TypeError):
        # If conversion fails, return empty history
        return {
            "count": 0,
            "history": []
        }

    history = get_user_search_history(
        user_id=user_id_int,
        limit=limit
    )

    return {

        "count": len(history),

        "history": history
    }
