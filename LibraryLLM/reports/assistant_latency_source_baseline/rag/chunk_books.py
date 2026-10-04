import json
import re
from pathlib import Path


PROCESSED_DIR = Path("rag/processed")
OUTPUT_DIR = Path("rag/chunks")
MAPPING_FILE = Path("rag/rag_book_mapping.json")

# Target chunk size.
# We use characters rather than tokens at this stage because
# the source files are plain text.
CHUNK_SIZE = 1800

# Overlap prevents important information from being cut off
# between two chunks.
CHUNK_OVERLAP = 300


def load_mapping():
    with open(
        MAPPING_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)


def normalize_whitespace(text):
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


def detect_chapter(text, position):
    """
    Find the nearest chapter/section heading before the current
    chunk position.
    """

    before = text[:position]

    patterns = [
        r"(?im)^(chapter\s+[ivxlcdm0-9]+.*?)$",
        r"(?im)^(chapter\s+\w+.*?)$",
        r"(?im)^(prologue.*?)$",
        r"(?im)^(epilogue.*?)$",
        r"(?im)^(part\s+[ivxlcdm0-9]+.*?)$",
    ]

    matches = []

    for pattern in patterns:
        found = list(re.finditer(pattern, before))

        if found:
            matches.extend(found)

    if not matches:
        return "Unknown"

    latest = max(
        matches,
        key=lambda m: m.start()
    )

    return latest.group(1).strip()


def split_text(text):
    """
    Split text into chunks while attempting to end chunks
    at paragraph or sentence boundaries.
    """

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
            # Prefer paragraph boundary.
            paragraph_boundary = text.rfind(
                "\n\n",
                start,
                desired_end
            )

            if (
                paragraph_boundary > start + CHUNK_SIZE // 2
            ):
                end = paragraph_boundary

            else:
                # Otherwise use sentence boundary.
                sentence_matches = list(
                    re.finditer(
                        r"[.!?]\s",
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

        chunk = text[start:end].strip()

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

        # Move backwards slightly for overlap.
        next_start = end - CHUNK_OVERLAP

        # Make sure we always move forward.
        if next_start <= start:
            next_start = end

        start = next_start

    return chunks


def process_book(book):
    filename = book["filename"]

    input_file = PROCESSED_DIR / filename

    if not input_file.exists():
        print(
            f"  ✗ Missing: {input_file}"
        )
        return []

    text = input_file.read_text(
        encoding="utf-8",
        errors="replace"
    )

    text = normalize_whitespace(text)

    raw_chunks = split_text(text)

    output = []

    for index, chunk in enumerate(
        raw_chunks,
        start=1
    ):

        chapter = detect_chapter(
            text,
            chunk["start"]
        )

        output.append(
            {
                "chunk_id": (
                    f"{book['work_id']}_"
                    f"{index:04d}"
                ),

                "work_id": book["work_id"],

                "title": book["title"],

                "author": book["author"],

                "source_file": filename,

                "chunk_index": index,

                "chapter": chapter,

                "text": chunk["text"]
            }
        )

    return output


def main():

    print("=" * 60)
    print(" LuminaR RAG — BOOK CHUNKING")
    print("=" * 60)
    print()

    if not MAPPING_FILE.exists():
        print(
            f"ERROR: {MAPPING_FILE} not found."
        )
        return

    if not PROCESSED_DIR.exists():
        print(
            f"ERROR: {PROCESSED_DIR} not found."
        )
        return

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    books = load_mapping()

    all_chunks = []

    for book in books:

        print(
            f"Processing: {book['title']}"
        )

        chunks = process_book(book)

        print(
            f"  Chunks: {len(chunks)}"
        )

        all_chunks.extend(chunks)

    # --------------------------------------------------------
    # Save individual book chunk files
    # --------------------------------------------------------

    for book in books:

        book_chunks = [
            chunk
            for chunk in all_chunks
            if chunk["work_id"] == book["work_id"]
        ]

        output_file = (
            OUTPUT_DIR
            / f"{book['work_id']}.json"
        )

        with open(
            output_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                book_chunks,
                f,
                indent=2,
                ensure_ascii=False
            )

    # --------------------------------------------------------
    # Save complete corpus
    # --------------------------------------------------------

    combined_file = (
        OUTPUT_DIR
        / "all_chunks.json"
    )

    with open(
        combined_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            all_chunks,
            f,
            indent=2,
            ensure_ascii=False
        )

    print()
    print("=" * 60)
    print(" CHUNKING COMPLETE")
    print("=" * 60)

    print(
        f"Books processed: {len(books)}"
    )

    print(
        f"Total chunks:    {len(all_chunks)}"
    )

    print(
        f"Output directory: {OUTPUT_DIR}"
    )

    print(
        f"Combined corpus: {combined_file}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()