from pathlib import Path
import json
import re
import time

import fitz
import numpy as np
import faiss
import torch

from sentence_transformers import SentenceTransformer


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DOCUMENTS_DIR = BASE_DIR / "documents"
EXTRACTED_DIR = BASE_DIR / "extracted"
CHUNKS_DIR = BASE_DIR / "chunks"
INDEX_DIR = BASE_DIR / "index"

DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# SETTINGS
# ============================================================

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

DEVICE = (
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)

CHUNK_SIZE = 3000
CHUNK_OVERLAP = 400

INDEX_PATH = INDEX_DIR / "rag.index"
METADATA_PATH = INDEX_DIR / "rag_metadata.json"


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text: str):

    text = text.replace(
        "\r\n",
        "\n"
    )

    text = text.replace(
        "\r",
        "\n"
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    return text.strip()


# ============================================================
# CHUNKING
# ============================================================

def chunk_text(
    text: str,
    chunk_size=CHUNK_SIZE,
    overlap=CHUNK_OVERLAP
):

    if not text:

        return []

    chunks = []

    start = 0

    text_length = len(text)

    while start < text_length:

        end = min(
            start + chunk_size,
            text_length
        )

        chunk = text[
            start:end
        ].strip()

        if chunk:

            chunks.append(
                chunk
            )

        if end >= text_length:

            break

        start = end - overlap

    return chunks


# ============================================================
# DOCUMENT SERVICE
# ============================================================

class DocumentService:

    def __init__(self):

        print()
        print("=" * 70)
        print("INITIALIZING LUMINAR DOCUMENT SERVICE")
        print("=" * 70)
        self.DOCUMENTS_DIR = DOCUMENTS_DIR
        print(
            f"Device : {DEVICE}"
        )

        # ----------------------------------------------------
        # LOAD EMBEDDING MODEL ONCE
        # ----------------------------------------------------

        print(
            "Loading MiniLM..."
        )

        start = time.perf_counter()

        self.model = SentenceTransformer(
            MODEL_NAME,
            device=DEVICE
        )

        elapsed = (
            time.perf_counter()
            - start
        )

        print(
            f"MiniLM load : "
            f"{elapsed:.2f} seconds"
        )

        # ----------------------------------------------------
        # LOAD EXISTING INDEX
        # ----------------------------------------------------

        self.index = None

        if INDEX_PATH.exists():

            print(
                "Loading existing FAISS index..."
            )

            self.index = faiss.read_index(
                str(INDEX_PATH)
            )

            print(
                f"Existing vectors : "
                f"{self.index.ntotal}"
            )

        else:

            print(
                "No existing FAISS index found."
            )

        # ----------------------------------------------------
        # LOAD EXISTING METADATA
        # ----------------------------------------------------

        self.metadata = []

        if METADATA_PATH.exists():

            with open(
                METADATA_PATH,
                "r",
                encoding="utf-8"
            ) as f:

                self.metadata = json.load(
                    f
                )

        print(
            f"Existing metadata : "
            f"{len(self.metadata)}"
        )

        print(
            "Document service ready."
        )


    # ========================================================
    # CHECK DUPLICATE
    # ========================================================

    def document_exists(
        self,
        document_id
    ):

        for item in self.metadata:

            if item.get(
                "document_id"
            ) == document_id:

                return True

        return False


    # ========================================================
    # EXTRACT PDF
    # ========================================================

    def extract_pdf(
        self,
        pdf_path
    ):

        document_id = pdf_path.stem

        pdf = fitz.open(
            str(pdf_path)
        )

        page_records = []

        for page_number, page in enumerate(
            pdf,
            start=1
        ):

            text = page.get_text(
                "text"
            )

            text = clean_text(
                text
            )

            page_records.append(
                {
                    "document_id":
                        document_id,

                    "filename":
                        pdf_path.name,

                    "page":
                        page_number,

                    "text":
                        text
                }
            )

        pdf.close()

        return page_records


    # ========================================================
    # SAVE EXTRACTION
    # ========================================================

    def save_extraction(
        self,
        document_id,
        filename,
        pages
    ):

        path = (
            EXTRACTED_DIR /
            f"{document_id}.json"
        )

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                {
                    "document_id":
                        document_id,

                    "filename":
                        filename,

                    "page_count":
                        len(pages),

                    "pages":
                        pages
                },
                f,
                ensure_ascii=False,
                indent=2
            )

        return path


    # ========================================================
    # CREATE CHUNKS
    # ========================================================

    def create_chunks(
        self,
        document_id,
        filename,
        pages
    ):

        chunks = []

        chunk_id = 0

        for page in pages:

            page_text = page[
                "text"
            ]

            if not page_text:

                continue

            page_chunks = chunk_text(
                page_text
            )

            for chunk in page_chunks:

                chunk_id += 1

                chunks.append(
                    {
                        "chunk_id":
                            f"{document_id}_"
                            f"{chunk_id:06d}",

                        "document_id":
                            document_id,

                        "filename":
                            filename,

                        "page":
                            page["page"],

                        "text":
                            chunk
                    }
                )

        return chunks


    # ========================================================
    # SAVE CHUNKS
    # ========================================================

    def save_chunks(
        self,
        document_id,
        filename,
        chunks
    ):

        path = (
            CHUNKS_DIR /
            f"{document_id}.json"
        )

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                {
                    "document_id":
                        document_id,

                    "filename":
                        filename,

                    "chunk_count":
                        len(chunks),

                    "chunks":
                        chunks
                },
                f,
                ensure_ascii=False,
                indent=2
            )

        return path


    # ========================================================
    # EMBED CHUNKS
    # ========================================================

    def embed_chunks(
        self,
        chunks
    ):

        texts = [
            chunk["text"]
            for chunk in chunks
        ]

        embeddings = self.model.encode(
            texts,
            batch_size=32,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True
        )

        return np.asarray(
            embeddings,
            dtype="float32"
        )


    # ========================================================
    # ADD TO FAISS
    # ========================================================

    def add_to_index(
        self,
        embeddings
    ):

        if self.index is None:

            dimension = (
                embeddings.shape[1]
            )

            self.index = faiss.IndexFlatIP(
                dimension
            )

        self.index.add(
            embeddings
        )

        faiss.write_index(
            self.index,
            str(INDEX_PATH)
        )


    # ========================================================
    # SAVE METADATA
    # ========================================================

    def save_metadata(
        self
    ):

        with open(
            METADATA_PATH,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                self.metadata,
                f,
                ensure_ascii=False,
                indent=2
            )


    # ========================================================
    # UPLOAD / INGEST ONE DOCUMENT
    # ========================================================

    def ingest_document(
        self,
        source_path
    ):

        source_path = Path(
            source_path
        )

        if not source_path.exists():

            raise FileNotFoundError(
                "Uploaded file does not exist."
            )

        if source_path.suffix.lower() != ".pdf":

            raise ValueError(
                "Only PDF files are supported."
            )

        document_id = (
            source_path.stem
        )

        # ----------------------------------------------------
        # DUPLICATE CHECK
        # ----------------------------------------------------

        if self.document_exists(
            document_id
        ):

            raise ValueError(
                f"Document already exists: "
                f"{document_id}"
            )

        # ----------------------------------------------------
        # EXTRACT
        # ----------------------------------------------------

        print()
        print(
            f"Processing PDF: "
            f"{source_path.name}"
        )

        start = time.perf_counter()

        pages = self.extract_pdf(
            source_path
        )

        extraction_time = (
            time.perf_counter()
            - start
        )

        # ----------------------------------------------------
        # SAVE EXTRACTION
        # ----------------------------------------------------

        self.save_extraction(
            document_id,
            source_path.name,
            pages
        )

        # ----------------------------------------------------
        # CHUNK
        # ----------------------------------------------------

        chunks = self.create_chunks(
            document_id,
            source_path.name,
            pages
        )

        self.save_chunks(
            document_id,
            source_path.name,
            chunks
        )

        if not chunks:

            raise ValueError(
                "No text could be extracted "
                "from this PDF."
            )

        # ----------------------------------------------------
        # EMBEDDINGS
        # ----------------------------------------------------

        start = time.perf_counter()

        embeddings = self.embed_chunks(
            chunks
        )

        embedding_time = (
            time.perf_counter()
            - start
        )

        # ----------------------------------------------------
        # ADD TO FAISS
        # ----------------------------------------------------

        self.add_to_index(
            embeddings
        )

        # ----------------------------------------------------
        # ADD METADATA
        # ----------------------------------------------------

        for chunk in chunks:

            self.metadata.append(
                {
                    "chunk_id":
                        chunk["chunk_id"],

                    "document_id":
                        chunk["document_id"],

                    "filename":
                        chunk["filename"],

                    "page":
                        chunk["page"]
                }
            )

        self.save_metadata()

        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        pages_with_text = sum(
            1
            for page in pages
            if page["text"]
        )

        return {
            "document_id":
                document_id,

            "filename":
                source_path.name,

            "pages":
                len(pages),

            "pages_with_text":
                pages_with_text,

            "chunks":
                len(chunks),

            "vectors_added":
                len(embeddings),

            "total_vectors":
                int(
                    self.index.ntotal
                ),

            "extraction_seconds":
                round(
                    extraction_time,
                    3
                ),

            "embedding_seconds":
                round(
                    embedding_time,
                    3
                ),

            "status":
                "ready"
        }


    # ========================================================
    # LIST DOCUMENTS
    # ========================================================

    def list_documents(self):

        documents = {}

        for item in self.metadata:

            document_id = item.get(
                "document_id"
            )

            if document_id not in documents:

                documents[
                    document_id
                ] = {
                    "document_id":
                        document_id,

                    "filename":
                        item.get(
                            "filename"
                        ),

                    "chunks":
                        0,

                    "pages":
                        set()
                }

            documents[
                document_id
            ]["chunks"] += 1

            documents[
                document_id
            ]["pages"].add(
                item.get("page")
            )

        result = []

        for document in documents.values():

            result.append(
                {
                    "document_id":
                        document[
                            "document_id"
                        ],

                    "filename":
                        document[
                            "filename"
                        ],

                    "chunks":
                        document[
                            "chunks"
                        ],

                    "pages":
                        len(
                            document[
                                "pages"
                            ]
                        )
                }
            )

        return result