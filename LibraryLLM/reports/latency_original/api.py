from pathlib import Path

from fastapi import (
    FastAPI,
    HTTPException,
    UploadFile,
    File
)

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

engine = LuminaRAG()

print()
print("Loading document service...")

document_service = DocumentService()

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

        "llm":
            "Qwen2.5-3B-Instruct",

        "retrieval":
            "MiniLM + FAISS",

        "reranker":
            "CrossEncoder",

        "device":
            "cuda"
            if document_service.index
            else "unknown",

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
    request: RAGRequest
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

        result = engine.ask(
            question=query,
            depth=depth,
            document_id=request.document_id,
            work_id=request.work_id
        )

        return result

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

        result = (
            document_service
            .ingest_document(
                destination
            )
        )

        # ----------------------------------------------------
        # HOT RELOAD RETRIEVER
        # ----------------------------------------------------

        print()
        print(
            "Refreshing active RAG retriever..."
        )

        engine.reranker.retriever.reload()

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
    """Return the books that actually exist in the RAG
    book index.  Reads the metadata already loaded by the
    retriever — no extra file I/O or model loading."""

    try:

        retriever = (
            engine.reranker.retriever
        )

        # --------------------------------------------------------
        # Extract unique books from global book metadata
        # --------------------------------------------------------

        seen = set()
        books = []

        for item in retriever.metadata:

            work_id = item.get("work_id")

            if not work_id:
                continue

            if work_id in seen:
                continue

            seen.add(work_id)

            author = item.get("author", "")

            books.append({
                "work_id": work_id,
                "title": item.get("title", ""),
                "authors": (
                    [a.strip() for a in author.split(",")]
                    if author
                    else []
                ),
            })

        # Alphabetical by title for stable ordering
        books.sort(
            key=lambda b: (b["title"] or "").lower()
        )

        return {
            "count": len(books),
            "books": books,
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )