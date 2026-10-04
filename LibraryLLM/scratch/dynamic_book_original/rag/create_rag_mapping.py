import json
from pathlib import Path


BOOKS_DIR = Path("rag/books")
OUTPUT_FILE = Path("rag/rag_book_mapping.json")


BOOKS = [
    {
        "work_id": "OL45326637W",
        "title": "Frankenstein",
        "author": "Mary Shelley",
        "filename": "Frankenstein.txt"
    },
    {
        "work_id": "OL85892W",
        "title": "Dracula",
        "author": "Bram Stoker",
        "filename": "Dracula.txt"
    },
    {
        "work_id": "OL66524W",
        "title": "Pride and Prejudice",
        "author": "Jane Austen",
        "filename": "Pride and Prejudice.txt"
    },
    {
        "work_id": "OL38619874W",
        "title": "Alice's Adventures in Wonderland",
        "author": "Lewis Carroll",
        "filename": "Alice's Adventures in Wonderland.txt"
    },
    {
        "work_id": "OL17494673W",
        "title": "The Adventures of Sherlock Holmes",
        "author": "Arthur Conan Doyle",
        "filename": "The Adventures of Sherlock Holmes.txt"
    },
    {
        "work_id": "OL27039837W",
        "title": "The Time Machine",
        "author": "H. G. Wells",
        "filename": "The Time Machine.txt"
    },
    {
        "work_id": "OL33027136W",
        "title": "The War of the Worlds",
        "author": "H. G. Wells",
        "filename": "The War of the Worlds.txt"
    },
    {
        "work_id": "OL44512357W",
        "title": "The Picture of Dorian Gray",
        "author": "Oscar Wilde",
        "filename": "The Picture of Dorian Gray.txt"
    },
    {
        "work_id": "OL27471326W",
        "title": "Moby-Dick",
        "author": "Herman Melville",
        "filename": "Moby-Dick.txt"
    },
    {
        "work_id": "OL36979234W",
        "title": "Jane Eyre",
        "author": "Charlotte Bronte",
        "filename": "Jane Eyre.txt"
    },
    {
        "work_id": "OL41470186W",
        "title": "Great Expectations",
        "author": "Charles Dickens",
        "filename": "Great Expectations.txt"
    },
    {
        "work_id": "OL43032614W",
        "title": "A Tale of Two Cities",
        "author": "Charles Dickens",
        "filename": "A Tale of Two Cities.txt"
    },
    {
        "work_id": "OL28944494W",
        "title": "The Adventures of Tom Sawyer",
        "author": "Mark Twain",
        "filename": "The Adventures of Tom Sawyer.txt"
    },
    {
        "work_id": "OL35758281W",
        "title": "Adventures of Huckleberry Finn",
        "author": "Mark Twain",
        "filename": "Adventures of Huckleberry Finn.txt"
    },
    {
        "work_id": "OL15933082W",
        "title": "The Strange Case of Dr. Jekyll and Mr. Hyde",
        "author": "Robert Louis Stevenson",
        "filename": "The Strange Case of Dr. Jekyll and Mr. Hyde.txt"
    },
    {
        "work_id": "OL42479046W",
        "title": "The Metamorphosis",
        "author": "Franz Kafka",
        "filename": "The Metamorphosis.txt"
    },
    {
        "work_id": "OL33723557W",
        "title": "The Importance of Being Earnest",
        "author": "Oscar Wilde",
        "filename": "The Importance of Being Earnest.txt"
    }
]


def main():
    if not BOOKS_DIR.exists():
        print(f"ERROR: {BOOKS_DIR} does not exist.")
        return

    print("=" * 60)
    print(" LuminaR RAG BOOK → TEXT MAPPING")
    print("=" * 60)

    missing = []

    for book in BOOKS:
        path = BOOKS_DIR / book["filename"]

        if path.exists():
            print(f"✓ {book['title']}")
        else:
            print(f"✗ MISSING: {book['filename']}")
            missing.append(book["filename"])

    if missing:
        print("\nERROR: Some files are missing.")
        print("Fix the missing files before continuing.")
        return

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(BOOKS, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"✓ All {len(BOOKS)} books mapped successfully.")
    print(f"✓ Created: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()