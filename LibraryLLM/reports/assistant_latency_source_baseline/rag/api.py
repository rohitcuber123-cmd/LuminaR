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
from rag.services.document_service import (
    DocumentService
)


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

print()
print("Loading document service...")

document_service = DocumentService(embedding_model=engine.reranker.retriever.model)
book_runtime = BookRuntime(engine.reranker.retriever, loaded_book_revision)
optional_auth = HTTPBearer(auto_error=False)
service_loading_ms = (perf_counter() - service_loading_started) * 1000


@app.middleware("http")
async def request_timing(request, call_next):
    started = perf_counter()
    response = await call_next(request)
    response.headers["Server-Timing"] = f"rag;dur={(perf_counter() - started) * 1000:.2f}"
    return response


def ingest_and_refresh(destination):
    # Shared embedding model and index refresh cannot race a question.
    with engine.inference_lock:
        result = document_service.ingest_document(destination)
        engine.reranker.retriever.reload()
        return result

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

        "vectors":
            int(
                document_service.index.ntotal
            )
            if document_service.index
            else 0
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
            selected_book = authorize_selection(
                request.document_id, request.work_id, credentials,
                engine.reranker.retriever.doc_ids,
            )
            if selected_book or not (request.document_id or request.work_id):
                book_runtime.refresh()
            result = engine.ask(
                question=query,
                depth=depth,
                document_id=request.document_id,
                work_id=request.work_id
            )

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
# UPLOAD PDF
# ============================================================

@app.post("/rag/upload")
async def upload_document(
    file: UploadFile = File(...)
):

    # --------------------------------------------------------
    # VALIDATE FILENAME
    # --------------------------------------------------------

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="Filename is required."
        )

    # --------------------------------------------------------
    # VALIDATE PDF
    # --------------------------------------------------------

    if not file.filename.lower().endswith(
        ".pdf"
    ):

        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported."
        )

    # --------------------------------------------------------
    # SAFE FILENAME
    # --------------------------------------------------------

    safe_filename = Path(
        file.filename
    ).name

    document_id = Path(
        safe_filename
    ).stem
    if valid_work_id(document_id):
        raise HTTPException(400, "This filename is reserved for catalog books. Rename the PDF.")

    # --------------------------------------------------------
    # DOCUMENT DIRECTORY
    # --------------------------------------------------------

    documents_dir = (
        document_service.DOCUMENTS_DIR
    )

    documents_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    destination = (
        documents_dir /
        safe_filename
    )

    # --------------------------------------------------------
    # DUPLICATE CHECK
    # --------------------------------------------------------

    if document_service.document_exists(
        document_id
    ):

        raise HTTPException(
            status_code=409,
            detail=(
                f"Document already exists: "
                f"{document_id}"
            )
        )

    # --------------------------------------------------------
    # READ UPLOAD
    # --------------------------------------------------------

    try:

        contents = await file.read()

        if not contents:

            raise HTTPException(
                status_code=400,
                detail="Uploaded PDF is empty."
            )

        # ----------------------------------------------------
        # SAVE PDF
        # ----------------------------------------------------

        with open(
            destination,
            "wb"
        ) as f:

            f.write(
                contents
            )

        print()
        print("=" * 70)
        print("NEW RAG DOCUMENT UPLOAD")
        print("=" * 70)

        print(
            f"Filename    : "
            f"{safe_filename}"
        )

        print(
            f"Document ID : "
            f"{document_id}"
        )

        # ----------------------------------------------------
        # INGEST + EMBED + INDEX
        # ----------------------------------------------------

        result = await run_in_threadpool(ingest_and_refresh, destination)

        # ----------------------------------------------------
        # HOT RELOAD RETRIEVER
        # ----------------------------------------------------

        print()
        print(
            "Refreshing active RAG retriever..."
        )

        print(
            "Active RAG retriever refreshed."
        )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        return {
            "message":
                "PDF uploaded and indexed successfully",

            "document":
                result
        }

    except HTTPException:

        # Only remove the PDF if it was not successfully
        # indexed. If the exception occurs after ingestion,
        # the document may already exist in the index.

        raise

    except Exception as e:

        print()
        print(
            f"Upload error: {e}"
        )

        # ----------------------------------------------------
        # CLEAN FAILED FILE
        # ----------------------------------------------------

        if destination.exists():

            try:

                destination.unlink()

            except Exception:

                pass

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# LIST DOCUMENTS
# ============================================================

@app.get("/rag/documents")
def list_documents():

    try:

        documents = (
            document_service
            .list_documents()
        )

        return {
            "count":
                len(documents),

            "documents":
                documents
        }

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
install_assistant(app, engine, ask, RAGRequest)
