import re
from pathlib import Path


BOOKS_DIR = Path("rag/books")
OUTPUT_DIR = Path("rag/processed")


def clean_gutenberg_text(text: str) -> str:
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove Gutenberg start marker and everything before it
    start_patterns = [
        r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK[^\n]*\n",
        r"\*\*\*\s*START OF THE PROJECT GUTENBERG EBOOK[^\n]*\n",
    ]

    for pattern in start_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            text = text[match.end():]
            break

    # Remove Gutenberg end marker and everything after it
    end_patterns = [
        r"\n\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK",
        r"\n\*\*\*\s*END OF THE PROJECT GUTENBERG EBOOK",
    ]

    for pattern in end_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            text = text[:match.start()]
            break

    # Remove excessive spaces
    text = re.sub(r"[ \t]+", " ", text)

    # Normalize excessive blank lines
    text = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", text)

    # Remove whitespace around line boundaries
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)

    return text.strip()


def process_book(input_file: Path):
    print(f"Processing: {input_file.name}")

    text = input_file.read_text(
        encoding="utf-8",
        errors="replace"
    )

    original_length = len(text)

    cleaned = clean_gutenberg_text(text)

    output_file = OUTPUT_DIR / input_file.name

    output_file.write_text(
        cleaned,
        encoding="utf-8"
    )

    print(
        f"  Original: {original_length:,} characters"
    )

    print(
        f"  Cleaned:  {len(cleaned):,} characters"
    )

    print(
        f"  Saved:    {output_file}"
    )

    print()


def main():
    if not BOOKS_DIR.exists():
        print(f"ERROR: {BOOKS_DIR} does not exist.")
        return

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    files = sorted(
        BOOKS_DIR.glob("*.txt")
    )

    if not files:
        print("ERROR: No .txt books found.")
        return

    print("=" * 60)
    print(" LuminaR RAG — BOOK TEXT CLEANER")
    print("=" * 60)
    print()

    for book_file in files:
        process_book(book_file)

    print("=" * 60)
    print(f"✓ Processed {len(files)} books")
    print(f"✓ Output directory: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()