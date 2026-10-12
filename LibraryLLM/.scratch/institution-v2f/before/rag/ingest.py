from pathlib import Path
import json
import re

import fitz


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DOCUMENTS_DIR = BASE_DIR / "documents"
EXTRACTED_DIR = BASE_DIR / "extracted"
CHUNKS_DIR = BASE_DIR / "chunks"

EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# CHUNK SETTINGS
# ============================================================

CHUNK_SIZE = 3000
CHUNK_OVERLAP = 400


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text: str) -> str:

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

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
# CHUNK TEXT
# ============================================================

def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP
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

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        start = end - overlap

    return chunks


# ============================================================
# PROCESS ONE PDF
# ============================================================

def process_pdf(pdf_path: Path):

    print()
    print("=" * 70)
    print(f"PROCESSING: {pdf_path.name}")
    print("=" * 70)

    document_id = pdf_path.stem

    pdf = fitz.open(str(pdf_path))

    page_records = []

    print(f"Pages: {len(pdf)}")

    # --------------------------------------------------------
    # EXTRACT PAGE TEXT
    # --------------------------------------------------------

    for page_number, page in enumerate(
        pdf,
        start=1
    ):

        text = page.get_text("text")

        text = clean_text(text)

        page_records.append(
            {
                "document_id": document_id,
                "filename": pdf_path.name,
                "page": page_number,
                "text": text
            }
        )

    pdf.close()

    # --------------------------------------------------------
    # SAVE PAGE-LEVEL EXTRACTION
    # --------------------------------------------------------

    extracted_path = (
        EXTRACTED_DIR /
        f"{document_id}.json"
    )

    with open(
        extracted_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            {
                "document_id": document_id,
                "filename": pdf_path.name,
                "page_count": len(page_records),
                "pages": page_records
            },
            f,
            ensure_ascii=False,
            indent=2
        )

    # --------------------------------------------------------
    # CREATE CHUNKS
    # --------------------------------------------------------

    chunks = []

    chunk_id = 0

    for page in page_records:

        page_text = page["text"]

        if not page_text:
            continue

        page_chunks = chunk_text(
            page_text
        )

        for chunk in page_chunks:

            chunk_id += 1

            chunks.append(
                {
                    "chunk_id": (
                        f"{document_id}_"
                        f"{chunk_id:06d}"
                    ),
                    "document_id": document_id,
                    "filename": pdf_path.name,
                    "page": page["page"],
                    "text": chunk
                }
            )

    # --------------------------------------------------------
    # SAVE CHUNKS
    # --------------------------------------------------------

    chunks_path = (
        CHUNKS_DIR /
        f"{document_id}.json"
    )

    with open(
        chunks_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            {
                "document_id": document_id,
                "filename": pdf_path.name,
                "chunk_count": len(chunks),
                "chunks": chunks
            },
            f,
            ensure_ascii=False,
            indent=2
        )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    total_characters = sum(
        len(page["text"])
        for page in page_records
    )

    pages_with_text = sum(
        1
        for page in page_records
        if page["text"]
    )

    print(
        f"Pages with text  : {pages_with_text}"
    )

    print(
        f"Characters       : {total_characters}"
    )

    print(
        f"Chunks           : {len(chunks)}"
    )

    print(
        f"Extracted file   : {extracted_path}"
    )

    print(
        f"Chunks file      : {chunks_path}"
    )

    return {
        "document_id": document_id,
        "filename": pdf_path.name,
        "pages": len(page_records),
        "pages_with_text": pages_with_text,
        "characters": total_characters,
        "chunks": len(chunks)
    }


# ============================================================
# FIND ALL PDF FILES
# ============================================================

def find_pdf_files():

    return sorted(
        [
            path
            for path in DOCUMENTS_DIR.iterdir()
            if path.is_file()
            and path.suffix.lower() == ".pdf"
        ]
    )


# ============================================================
# MAIN
# ============================================================

def main():

    pdf_files = find_pdf_files()

    print()
    print("=" * 70)
    print("LUMINAR RAG DOCUMENT INGESTION")
    print("=" * 70)

    print(
        f"Documents directory: {DOCUMENTS_DIR}"
    )

    print(
        f"PDF files found    : {len(pdf_files)}"
    )

    for pdf in pdf_files:

        print(
            f"  - {pdf.name}"
        )

    if not pdf_files:

        print()
        print("No PDF files found.")

        return

    summaries = []

    for pdf_path in pdf_files:

        try:

            summary = process_pdf(
                pdf_path
            )

            summaries.append(
                summary
            )

        except Exception as e:

            print()
            print(
                f"ERROR processing "
                f"{pdf_path.name}: {e}"
            )

    # --------------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("RAG INGESTION COMPLETE")
    print("=" * 70)

    total_pages = sum(
        x["pages"]
        for x in summaries
    )

    total_text_pages = sum(
        x["pages_with_text"]
        for x in summaries
    )

    total_characters = sum(
        x["characters"]
        for x in summaries
    )

    total_chunks = sum(
        x["chunks"]
        for x in summaries
    )

    print(
        f"Documents processed : {len(summaries)}"
    )

    print(
        f"Total pages         : {total_pages}"
    )

    print(
        f"Pages with text     : {total_text_pages}"
    )

    print(
        f"Total characters    : {total_characters}"
    )

    print(
        f"Total chunks        : {total_chunks}"
    )

    print()
    print(
        "Next stage:"
    )

    print(
        "Review extracted text/chunks "
        "before creating embeddings."
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()