"""Inspect source passages while auditing RAG relevance labels."""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('work_id')
    parser.add_argument('pattern')
    parser.add_argument('--limit', type=int, default=12)
    parser.add_argument('--skip-chunks', type=int, default=0)
    args = parser.parse_args()
    path = ROOT / 'rag' / 'book_index' / 'books' / (args.work_id + '_metadata.json')
    chunks = json.loads(path.read_text(encoding='utf-8'))
    matches = 0
    for chunk in chunks[args.skip_chunks:]:
        found = re.search(args.pattern, chunk['text'], flags=re.IGNORECASE)
        if not found:
            continue
        excerpt = chunk['text'][max(0, found.start() - 190):found.end() + 230]
        print(chunk['chunk_id'], chunk.get('chapter'),
              excerpt.replace('\n', ' '))
        matches += 1
        if matches >= args.limit:
            break
    print('shown', matches)


if __name__ == '__main__':
    main()
