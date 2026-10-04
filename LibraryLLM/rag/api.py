from pathlib import Path
from time import perf_counter
from starlette.concurrency import run_in_threadpool

from fastapi import (
    FastAPI,
    HTTPException,
    UploadFile,
    File,
    Depends
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from rag.services.book_access import authorize_selection
from rag.services.book_runtime import BookRuntime
from rag.book_assets import indexed_books, valid_work_id, index_revision

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, model_validator

from rag.qa import LuminaRAG


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="LuminaR RAG API",
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
# LOAD SERVICES ONCE
# ============================================================

print()
print("=" * 70)
print("STARTING LUMINAR RAG API")
print("=" * 70)

print()
print("Loading RAG QA engine...")

service_loading_started = perf_counter()
loaded_book_revision = index_revision()
engine = LuminaRAG()
from rag.document_latency import install_document_latency
install_document_latency(engine)

print()
print("Loading document service...")

from rag.services.private_documents import PrivateDocuments
from rag.services.private_document_routes import install_private_documents
from backend.dependencies import get_current_user
import contextlib
private_documents = PrivateDocuments(Path(__file__).resolve().parent / 'private_documents',
    engine.reranker.retriever.model, engine.reranker.retriever, engine._document_latency)
install_private_documents(app, private_documents, engine)
book_runtime = BookRuntime(engine.reranker.retriever, loaded_book_revision)
optional_auth = HTTPBearer(auto_error=False)
service_loading_ms = (perf_counter() - service_loading_started) * 1000


@app.middleware("http")
async def request_timing(request, call_next):
    started = perf_counter()
    response = await call_next(request)
    response.headers["Server-Timing"] = f"rag;dur={(perf_counter() - started) * 1000:.2f}"
    return response


print()
print("=" * 70)
print("LUMINAR RAG API READY")
print("=" * 70)


# ============================================================
# REQUEST MODEL
# ============================================================

class RAGRequest(BaseModel):

    query: str | None = None

    question: str | None = None

    depth: str = "normal"

    document_id: str | None = None

    work_id: str | None = None

    # --------------------------------------------------------
    # RESOLVE QUERY / QUESTION ALIAS
    #
    # The frontend may send either "query" or "question".
    # We normalize to query for internal use.
    # --------------------------------------------------------

    @model_validator(mode="after")
    def resolve_query_alias(self):

        if (
            not self.query
            and self.question
        ):

            self.query = self.question

        return self


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "system": "LuminaR",
        "module": "RAG",

        "status": "ready"
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "healthy",

        "system": "LuminaR",

        "module": "RAG",

        "model_loading_ms": round(service_loading_ms, 2),

        "llm":
            "Qwen2.5-3B-Instruct",

        "retrieval":
            "MiniLM + FAISS",

        "reranker":
            "CrossEncoder",

        "device":
            str(getattr(engine.llm.model, "device", "unavailable")),

        "vectors": int(engine.reranker.retriever.index.ntotal),
        "private_document_cache_enabled": private_documents.cache.enabled
    }


# ============================================================
# ASK
# ============================================================

@app.post("/rag/ask")
def ask(
    request: RAGRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_auth),
):

    query = (
        request.query or ""
    ).strip()

    if not query:

        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty."
        )

    allowed_depths = {
        "concise",
        "normal",
        "detailed",
        "comprehensive"
    }

    depth = request.depth.lower().strip()

    if depth not in allowed_depths:

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid depth. Choose one of: "
                "concise, normal, detailed, "
                "comprehensive."
            )
        )

    try:

        with engine.inference_lock:
            if request.document_id and request.work_id and request.document_id != request.work_id:
                raise HTTPException(400, "document_id and work_id must identify the same source.")
            selected = request.work_id or request.document_id
            private_documents.clear_runtime()
            document_scope = contextlib.nullcontext()
            selected_book = None
            if selected and not valid_work_id(selected):
                if credentials is None:
                    raise HTTPException(401, 'Sign in to use private documents.')
                user = get_current_user(credentials)
                private_documents.owned(selected, user)
                document_scope = private_documents.selected(selected, user)
            else:
                selected_book = authorize_selection(request.document_id, request.work_id, credentials, set())
                book_runtime.refresh()
            with document_scope:
                result = engine.ask(question=query, depth=depth,
                    document_id=selected if selected and not valid_work_id(selected) else request.document_id,
                    work_id=request.work_id if not (selected and not valid_work_id(selected)) else None)

            # A scoped retrieval that explicitly reports no source information
            # is an unsupported question, even if the legacy validator labels
            # the generated refusal as supported. This keeps cross-book
            # isolation observable to clients without changing V8 generation.
            answer = str(result.get("answer") or "").casefold()
            if selected_book and (
                "no information provided" in answer
                or "not enough information" in answer
                or "cannot answer" in answer
            ):
                result["verdict"] = "NOT_SUPPORTED"

        return result

    except HTTPException:
        raise
    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# LIST RAG-INDEXED BOOKS
# ============================================================

@app.get("/rag/books")
def list_rag_books():
    """Technical discovery only. User eligibility is /know-more/books."""
    books = [
        {"work_id": work_id, "title": row.get("title", ""),
         "authors": [a.strip() for a in row.get("author", "").split(",") if a.strip()]}
        for work_id, row in indexed_books().items()
    ]
    books.sort(key=lambda book: book["title"].casefold())
    return {"count": len(books), "books": books}


# Assistant shares the already resident engine.llm and inference_lock. All
# existing RAG handlers above keep their implementation and access checks.
from assistant.api import install_assistant
app.state.assistant = install_assistant(app, engine, ask, RAGRequest)
