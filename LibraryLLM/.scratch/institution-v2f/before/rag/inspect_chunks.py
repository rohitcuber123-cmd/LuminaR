from pathlib import Path

TARGETS = {
    "OL45326637W_000043",
    "OL45326637W_000044",
    "OL45326637W_000045",
    "OL45326637W_000046",
    "OL45326637W_000047",
    "OL45326637W_000051",
}

root = Path(".")

for path in root.rglob("*"):
    if not path.is_file():
        continue

    # Skip large/binary files
    if path.suffix.lower() not in {".json", ".jsonl", ".txt", ".pkl"}:
        continue

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue

    found = [chunk_id for chunk_id in TARGETS if chunk_id in text]

    if found:
        print("\n" + "=" * 80)
        print(f"FILE: {path}")
        print("FOUND:", ", ".join(found))
        print("=" * 80)