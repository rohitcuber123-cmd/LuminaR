"""Register provided, authorized full text against an existing catalog work_id.

Run: python -m rag.create_rag_mapping --work-id <catalog ID> --source <text file>
     --rights public-domain --source-url <provenance URL>
Then: python -m rag.book_ingest && python -m rag.embed
No book-specific source edits are required. This command never downloads content.
"""
import argparse
import json
from pathlib import Path
from backend.database.mongodb import books_collection
from rag.book_assets import BASE_DIR, valid_work_id
from rag.clean_books import clean_gutenberg_text


def register_book(work_id, source, rights, source_url=None, author=None):
    if not valid_work_id(work_id):
        raise ValueError("Use the catalog's canonical Open Library work_id.")
    if rights not in {"public-domain", "authorized"}:
        raise ValueError("Confirm the supplied full text is public-domain or authorized.")
    book = books_collection.find_one({"work_id": work_id}, {"_id": 0})
    if book is None:
        raise ValueError("Add the book to the catalog before registering full text.")
    raw = Path(source).read_text(encoding="utf-8-sig")
    text = clean_gutenberg_text(raw)
    if not text.strip():
        raise ValueError("The provided full text is empty.")
    filename = f"{work_id}.txt"
    for folder, content in [("books", raw), ("processed", text)]:
        directory = BASE_DIR / folder
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / filename
        temp = target.with_suffix(".txt.tmp")
        temp.write_text(content, encoding="utf-8")
        temp.replace(target)
    authors = author or book.get("authors") or ""
    manifest = {
        "work_id": work_id, "title": book["title"],
        "author": ", ".join(authors) if isinstance(authors, list) else authors,
        "filename": filename, "full_text": True, "rights": rights,
        "source_url": source_url,
    }
    target = BASE_DIR / "processed" / f"{work_id}.book.json"
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(target)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-id", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--rights", choices=["public-domain", "authorized"], required=True)
    parser.add_argument("--source-url")
    parser.add_argument("--author", help="Author credited in the supplied full text, if catalog credits combine editions.")
    args = parser.parse_args()
    print(json.dumps(register_book(args.work_id, args.source, args.rights, args.source_url, args.author), indent=2))


if __name__ == "__main__":
    main()
