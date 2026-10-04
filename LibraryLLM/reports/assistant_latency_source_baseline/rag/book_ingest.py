from pathlib import Path
import json
import re
from rag.book_assets import content_sources, readable_path, valid_work_id


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

PROCESSED_DIR = BASE_DIR / "processed"
CHUNKS_DIR = BASE_DIR / "book_chunks"

CHUNKS_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# CHUNK SETTINGS
# ============================================================

CHUNK_SIZE = 3000
CHUNK_OVERLAP = 400


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text: str) -> str:

    text = text.replace(
        "\r\n",
        "\n"
    )

    text = text.replace(
        "\r",
        "\n"
    )

    # Remove excessive spaces while preserving paragraphs.
    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    # Normalize excessive blank lines.
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    return text.strip()


# ============================================================
# CHAPTER DETECTION
# ============================================================

def find_chapter(text: str, position: int) -> str:

    before = text[:position]

    patterns = [
        r"(?im)^chapter\s+[ivxlcdm0-9]+[^\n]*",
        r"(?im)^chapter\s+\w+[^\n]*",
        r"(?im)^part\s+[ivxlcdm0-9]+[^\n]*",
        r"(?im)^prologue[^\n]*",
        r"(?im)^epilogue[^\n]*"
    ]

    matches = []

    for pattern in patterns:

        found = list(
            re.finditer(
                pattern,
                before
            )
        )

        matches.extend(found)

    if not matches:

        return "Unknown"

    latest = max(
        matches,
        key=lambda match: match.start()
    )

    return latest.group().strip()


# ============================================================
# CHUNK TEXT
# ============================================================

def chunk_text(text: str):

    chunks = []

    start = 0
    text_length = len(text)

    while start < text_length:

        desired_end = min(
            start + CHUNK_SIZE,
            text_length
        )

        if desired_end >= text_length:

            end = text_length

        else:

            # ----------------------------------------------
            # Prefer paragraph boundary
            # ----------------------------------------------

            paragraph_end = text.rfind(
                "\n\n",
                start,
                desired_end
            )

            if (
                paragraph_end >
                start + CHUNK_SIZE // 2
            ):

                end = paragraph_end

            else:

                # ------------------------------------------
                # Otherwise prefer sentence boundary
                # ------------------------------------------

                sentence_matches = list(
                    re.finditer(
                        r"[.!?][\"']?\s",
                        text[start:desired_end]
                    )
                )

                if sentence_matches:

                    last = sentence_matches[-1]

                    end = (
                        start
                        + last.end()
                    )

                else:

                    end = desired_end

        chunk = text[
            start:end
        ].strip()

        if chunk:

            chunks.append(
                {
                    "start": start,
                    "end": end,
                    "text": chunk
                }
            )

        if end >= text_length:

            break

        next_start = (
            end - CHUNK_OVERLAP
        )

        if next_start <= start:

            next_start = end

        start = next_start

    return chunks


# ============================================================
# PROCESS BOOK
# ============================================================

def process_book(book):

    if not valid_work_id(book.get("work_id")):
        raise ValueError("A canonical catalog work_id is required.")
    filename = book["filename"]

    input_file = readable_path(book["work_id"], {book["work_id"]: book})

    if input_file is None:

        print(
            f"  âœ— FILE NOT FOUND: {filename}"
        )

        return None

    print()
    print(
        f"Processing: {book['title']}"
    )

    text = input_file.read_text(
        encoding="utf-8",
        errors="replace"
    )

    text = clean_text(
        text
    )

    raw_chunks = chunk_text(
        text
    )

    chunks = []

    for index, item in enumerate(
        raw_chunks,
        start=1
    ):

        chapter = find_chapter(
            text,
            item["start"]
        )

        chunks.append(
            {
                # Compatible with existing retriever
                "chunk_id": (
                    f"{book['work_id']}_"
                    f"{index:06d}"
                ),

                # Existing RAG field
                # We use Work ID as document ID
                # for book-centric retrieval.
                "document_id":
                    book["work_id"],

                "filename":
                    filename,

                # Books are not page-based.
                # Chapter is stored separately.
                "page":
                    None,

                # New book-centric metadata
                "work_id":
                    book["work_id"],

                "title":
                    book["title"],

                "author":
                    book["author"],

                "chapter":
                    chapter,

                "chunk_index":
                    index,

                "text":
                    item["text"]
            }
        )

    # --------------------------------------------------------
    # SAVE INDIVIDUAL BOOK
    # --------------------------------------------------------

    output_file = (
        CHUNKS_DIR /
        f"{book['work_id']}.json"
    )

    output_data = {
        "document_id":
            book["work_id"],

        "work_id":
            book["work_id"],

        "title":
            book["title"],

        "author":
            book["author"],

        "filename":
            filename,

        "chunk_count":
            len(chunks),

        "chunks":
            chunks
    }

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output_data,
            f,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"  Chunks : {len(chunks)}"
    )

    print(
        f"  Saved  : {output_file.name}"
    )

    return chunks


# ============================================================
# MAIN
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Chunk registered full text by canonical catalog work_id.")
    parser.add_argument("--work-id", help="Ingest only this registered book; omit to discover all registrations.")
    args = parser.parse_args()

    print()
    print("=" * 70)
    print("LUMINAR BOOK RAG INGESTION")
    print("=" * 70)

    books = list(content_sources().values())
    if args.work_id:
        books = [book for book in books if book["work_id"] == args.work_id]
        if not books:
            parser.error("No authorized full-text registration exists for this work_id.")

    print()
    print(
        f"Books in mapping: {len(books)}"
    )

    all_chunks = []

    successful_books = 0

    for book in books:

        chunks = process_book(
            book
        )

        if chunks is not None:

            successful_books += 1

            all_chunks.extend(
                chunks
            )

    # --------------------------------------------------------
    # IMPORTANT
    # --------------------------------------------------------
    # Do NOT create all_chunks.json here.
    #
    # Your existing embed.py expects individual JSON files
    # containing {"chunks": [...]}.
    #
    # Therefore we leave the individual files as the source
    # for the existing embedding pipeline.
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("BOOK INGESTION COMPLETE")
    print("=" * 70)

    print(
        f"Books processed : "
        f"{successful_books}/{len(books)}"
    )

    print(
        f"Total chunks    : "
        f"{len(all_chunks):,}"
    )

    print(
        f"Output directory: "
        f"{CHUNKS_DIR}"
    )

    print()
    print(
        "Next:"
    )

    print(
        "Run the existing rag.embed pipeline "
        "after verifying the chunks."
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
