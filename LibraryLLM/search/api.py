import os
from typing import Literal
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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

@app.middleware('http')
async def private_search_responses(request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'private, no-store'
    return response

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
from search.ranked_pages import RankedSearchPages, SEARCH_MAX_RETURN_RESULTS
ranked_search = RankedSearchPages(engine)
from search.query_execution import GlobalQuerySearch, global_facets
human_search = GlobalQuerySearch(engine)
from search.library_intelligence_api import install as install_tenant_intelligence
install_tenant_intelligence(app,engine)
from search.interaction_api import install as install_search_interactions
install_search_interactions(app,engine)


@app.on_event("startup")
def start_index_sync():
    if os.getenv('SEARCH_GLOBAL_READ_ONLY')=='1':
        return  # Explicit review mode freezes global writers; tenant jobs are independent.
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
    limit: int | None = None
    offset: int = 0

    # Optional library filter
    library_id: str | None = None

    # Only return books physically available
    # at the specified library
    available_at_library: bool = False

    # Save search in user's search history
    save_history: bool = True
    category: str = Field(default='', max_length=200)
    author: str = Field(default='', max_length=150)
    mode: Literal['SMART','GENRE_SUBJECT','TITLE_AUTHOR','EXACT'] = 'SMART'
    query_contract: Literal['HUMAN','MACHINE'] = 'HUMAN'
    rating_min: float | None = Field(default=None, ge=0, le=5)
    rating_max: float | None = Field(default=None, ge=0, le=5)
    year_min: int | None = Field(default=None, ge=1000, le=2100)
    year_max: int | None = Field(default=None, ge=1000, le=2100)
    format: Literal['','ONLINE','PHYSICAL','BOTH'] = ''
    availability: Literal['','AVAILABLE_NOW','REQUESTABLE'] = ''
    language: str = Field(default='',max_length=60)
    sort: Literal['RELEVANCE','RATING','NEWEST','TITLE'] = 'RELEVANCE'
    omit: list[str] = Field(default_factory=list,max_length=12)
    session_id: str | None = Field(default=None,max_length=36)
    personalized: bool = False


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

    if not query and (request.query_contract == 'MACHINE' or not request.session_id and not any(
        [request.category,request.author,request.rating_min is not None,request.rating_max is not None,
         request.year_min is not None,request.year_max is not None,request.format,request.availability,request.language,request.sort!='RELEVANCE'])):

        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty."
        )

    # --------------------------------------------------------
    # VALIDATE TOP K
    # --------------------------------------------------------

    requested_limit = request.limit if request.limit is not None else request.top_k
    if requested_limit < 1:

        raise HTTPException(
            status_code=400,
            detail="top_k must be greater than 0."
        )

    if requested_limit > SEARCH_MAX_RETURN_RESULTS or request.offset < 0 or request.offset + requested_limit > SEARCH_MAX_RETURN_RESULTS:

        raise HTTPException(
            status_code=400,
            detail="limit must be 1–50 and offset + limit must not exceed 50."
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

        if request.query_contract == 'HUMAN':
            filters={key:getattr(request,key) for key in ('rating_min','rating_max','year_min','year_max','format','availability','language','sort','author')}
            filters['subject']=request.category
            try:result=human_search.search(query,user,mode=request.mode,filters=filters,omit=request.omit,offset=request.offset,limit=requested_limit,session_id=request.session_id,personalized=request.personalized)
            except ValueError as error:raise HTTPException(422,str(error)) from error

        # ----------------------------------------------------
        # RUN LUMINAR SEARCH
        # ----------------------------------------------------

        else:result = ranked_search.search(

            query=query,

            limit=requested_limit,
            offset=request.offset,

            library_id=request.library_id,

            available_at_library=(
                request.available_at_library
            ),
            **({'category': request.category, 'author': request.author} if request.category or request.author else {})
        )

        # ----------------------------------------------------
        # SAVE SEARCH HISTORY
        # ----------------------------------------------------

        if request.save_history and request.offset == 0 and not request.session_id and result.get('interpretation',{}).get('decision',{}).get('decision_type','EXECUTABLE') in ('EXECUTABLE','EXECUTABLE_WITH_NOTICE'):

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
                    top_k=requested_limit,
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


@app.get('/facets')
def facets(authorization: str | None = Header(default=None)):
    get_user_from_token(authorization)
    return global_facets(engine)


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
