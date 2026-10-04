"""Verify all local book index/metadata pairs without loading an ML model."""
import json
from pathlib import Path
import faiss

ROOT = Path(__file__).resolve().parents[1]
rows = []
for path in sorted((ROOT / 'rag/book_index/books').glob('*.index')):
    work_id = path.stem
    metadata = json.loads(path.with_name(work_id + '_metadata.json').read_text(encoding='utf-8'))
    index = faiss.read_index(str(path))
    aligned = len(metadata) == index.ntotal
    isolated = all(m.get('work_id') == work_id and m.get('document_id') == work_id for m in metadata)
    unique = len({m['chunk_id'] for m in metadata}) == len(metadata)
    rows.append({'work_id': work_id, 'vectors': index.ntotal,
                 'aligned': aligned, 'isolated': isolated, 'unique_chunk_ids': unique})
    assert aligned and isolated and unique, work_id
(ROOT / 'reports/rag_latency_index_integrity.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
print(f'{len(rows)} book indexes passed alignment, isolation, and unique chunk checks.')
