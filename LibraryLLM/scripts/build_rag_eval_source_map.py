"""Reconstruct evaluation-only chunk offsets from authoritative local source.

The current indexed metadata must match the existing production chunker
exactly. This script writes only rag/evaluation/source_map_v1.json.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rag.book_ingest import clean_text, chunk_text

BOOKS = ROOT / 'rag' / 'book_index' / 'books'
OUT = ROOT / 'rag' / 'evaluation' / 'source_map_v1.json'


def build():
    books = {}
    for path in sorted(BOOKS.glob('*_metadata.json')):
        metadata = json.loads(path.read_text(encoding='utf-8'))
        if not metadata:
            raise ValueError(f'Empty metadata: {path.name}')
        work_id = metadata[0]['work_id']
        source_path = ROOT / 'rag' / 'processed' / metadata[0]['filename']
        source = clean_text(source_path.read_text(encoding='utf-8', errors='replace'))
        reconstructed = chunk_text(source)
        if len(reconstructed) != len(metadata):
            raise ValueError(f'Chunk count mismatch: {work_id}')
        rows = []
        for stored, expected in zip(metadata, reconstructed):
            if stored['text'] != expected['text'] or stored['work_id'] != work_id:
                raise ValueError(f'Chunk text mismatch: {stored["chunk_id"]}')
            rows.append({'chunk_id': stored['chunk_id'],
                         'chunk_index': stored['chunk_index'],
                         'chapter': stored.get('chapter'),
                         'start': expected['start'], 'end': expected['end']})
        books[work_id] = {
            'book_title': metadata[0]['title'],
            'source_file': str(source_path.relative_to(ROOT)).replace('\\', '/'),
            'source_sha256': hashlib.sha256(source.encode('utf-8')).hexdigest(),
            'source_length': len(source), 'chunks': rows,
        }
    result = {'format_version': 'source_map_v1',
              'normalization': 'rag.book_ingest.clean_text',
              'chunker': 'rag.book_ingest.chunk_text (current 3000/400)',
              'book_count': len(books), 'books': books}
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    return result


if __name__ == '__main__':
    data = build()
    print(f"Mapped {data['book_count']} books and "
          f"{sum(len(x['chunks']) for x in data['books'].values())} chunks")
