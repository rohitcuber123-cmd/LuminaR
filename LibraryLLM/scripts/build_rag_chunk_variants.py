"""Build isolated current and token-aware RAG chunk variants from local books."""
import argparse
from bisect import bisect_right
import hashlib
import json
from pathlib import Path
import re
import sys
import time

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rag.book_ingest import clean_text, chunk_text
from rag.experimental_chunker import VARIANTS, chunk_source, coverage_audit, stable_chunk_id

SOURCE_MAP = ROOT / 'rag' / 'evaluation' / 'source_map_v1.json'
LABELS = ROOT / 'rag' / 'evaluation' / 'rag_retrieval_eval_v1.json'
PRODUCTION_BOOKS = ROOT / 'rag' / 'book_index' / 'books'
EXPERIMENT = ROOT / 'datasets' / 'rag_experiments' / 'chunking_v1'
MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'


def sha_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def chapter_lookup(source):
    pattern = re.compile(r'(?im)^(?:chapter\s+[ivxlcdm0-9]+[^\n]*|chapter\s+\w+[^\n]*|part\s+[ivxlcdm0-9]+[^\n]*|prologue[^\n]*|epilogue[^\n]*)')
    matches = list(pattern.finditer(source))
    positions = [m.start() for m in matches]
    labels = [m.group().strip() for m in matches]

    def at(position):
        index = bisect_right(positions, position) - 1
        return labels[index] if index >= 0 else 'Unknown'

    return at


def build(variant):
    source_map = json.loads(SOURCE_MAP.read_text(encoding='utf-8'))['books']
    model = SentenceTransformer(MODEL_NAME, local_files_only=True, device='cpu')
    tokenizer = model.tokenizer
    max_seq_length = model.max_seq_length
    if max_seq_length != 256:
        raise ValueError(f'Unexpected MiniLM input window: {max_seq_length}')
    max_total = VARIANTS.get(variant, {}).get('max_total_tokens')
    if max_total is not None and max_total > max_seq_length:
        raise ValueError('Variant exceeds model window')
    started = time.perf_counter()
    all_rows = []
    book_stats = {}
    seen_ids = set()
    for number, (work_id, book) in enumerate(sorted(source_map.items()), 1):
        source = clean_text((ROOT / book['source_file']).read_text(
            encoding='utf-8', errors='replace'))
        source_sha = hashlib.sha256(source.encode('utf-8')).hexdigest()
        if source_sha != book['source_sha256'] or len(source) != book['source_length']:
            raise ValueError(f'Source changed since evaluation map: {work_id}')
        stored = json.loads((PRODUCTION_BOOKS / f'{work_id}_metadata.json').read_text(
            encoding='utf-8'))
        author = stored[0]['author']
        filename = stored[0]['filename']
        if variant == 'current_baseline':
            raw = chunk_text(source)
            if len(raw) != len(stored):
                raise ValueError(f'Production chunk count differs: {work_id}')
            intervals = []
            for original, indexed, mapped in zip(raw, stored, book['chunks']):
                if original['text'] != indexed['text'] or original['start'] != mapped['start'] or original['end'] != mapped['end']:
                    raise ValueError(f'Production chunk differs: {work_id}')
                start = original['start']
                end = original['end']
                while start < end and source[start].isspace():
                    start += 1
                while end > start and source[end-1].isspace():
                    end -= 1
                intervals.append({'start': start, 'end': end, 'text': source[start:end],
                                  'chunk_id': indexed['chunk_id'],
                                  'chapter': indexed['chapter']})
        else:
            intervals = chunk_source(source, tokenizer, **VARIANTS[variant])
            chapter_at = chapter_lookup(source)
            for item in intervals:
                item['chunk_id'] = stable_chunk_id(work_id, variant, item['start'],
                                                   item['end'], source_sha)
                item['chapter'] = chapter_at(item['start'])
        checks = coverage_audit(source, intervals)
        if checks['uncovered_meaningful_chars'] or checks['invalid_offsets_or_text'] or checks['empty_chunks']:
            raise ValueError(f'Invalid source coverage: {work_id} {checks}')
        if variant != 'current_baseline' and (checks['midword_starts'] or checks['midword_ends']):
            raise ValueError(f'Mid-word boundary: {work_id} {checks}')
        for ordinal, item in enumerate(intervals, 1):
            cid = item['chunk_id']
            if cid in seen_ids:
                raise ValueError(f'Duplicate ID: {cid}')
            seen_ids.add(cid)
            count = item.get('token_count') or len(tokenizer(
                item['text'], add_special_tokens=True, truncation=False)['input_ids'])
            if max_total is not None and count > max_total:
                raise ValueError(f'Token cap exceeded: {cid} {count}>{max_total}')
            all_rows.append({
                'chunk_id': cid, 'work_id': work_id, 'document_id': work_id,
                'title': book['book_title'], 'author': author, 'filename': filename,
                'page': None, 'chapter': item['chapter'], 'chunk_index': ordinal,
                'source_start_char': item['start'], 'source_end_char': item['end'],
                'source_sha256': source_sha, 'token_count': count,
                'variant': variant, 'text': item['text'],
            })
        book_stats[work_id] = {'title': book['book_title'], 'chunks': len(intervals),
                               'source_sha256': source_sha, **checks}
        print(f'{number}/{len(source_map)} {work_id}: {len(intervals)} chunks', flush=True)
    lengths = np.asarray([r['token_count'] for r in all_rows], dtype=int)
    stats = {'chunk_count': len(all_rows), 'mean': float(lengths.mean()),
             'median': float(np.median(lengths)), 'p90': float(np.percentile(lengths, 90)),
             'p95': float(np.percentile(lengths, 95)), 'p99': float(np.percentile(lengths, 99)),
             'max': int(lengths.max()), 'over_256': int((lengths > 256).sum()),
             'over_256_percent': float((lengths > 256).mean() * 100),
             'midword_starts': sum(x['midword_starts'] for x in book_stats.values()),
             'midword_ends': sum(x['midword_ends'] for x in book_stats.values()),
             'uncovered_meaningful_chars': sum(x['uncovered_meaningful_chars'] for x in book_stats.values()),
             'invalid_offsets_or_text': sum(x['invalid_offsets_or_text'] for x in book_stats.values())}
    target = EXPERIMENT / variant
    target.mkdir(parents=True, exist_ok=True)
    chunks_path = target / 'chunks.parquet'
    mapping_path = target / 'mapping.json'
    mapping_text = json.dumps({r['chunk_id']: {
        'work_id': r['work_id'], 'start': r['source_start_char'],
        'end': r['source_end_char'], 'source_sha256': r['source_sha256']}
        for r in all_rows}, separators=(',', ':'))
    existing_manifest_path = target / 'manifest.json'
    existing_manifest = (json.loads(existing_manifest_path.read_text(encoding='utf-8'))
                         if existing_manifest_path.exists() else {})
    if (target / 'faiss.index').exists():
        if not chunks_path.exists() or not mapping_path.exists():
            raise ValueError('Existing index lacks its chunk/mapping inputs')
        if pq.read_table(chunks_path).to_pylist() != all_rows or mapping_path.read_text(
                encoding='utf-8') != mapping_text:
            raise ValueError('Rebuild changed chunks; refuse to stale an existing index')
    else:
        pq.write_table(pa.Table.from_pylist(all_rows), chunks_path, compression='zstd')
        mapping_path.write_text(mapping_text, encoding='utf-8')
    manifest = {
        'format_version': 'rag_chunking_v1', 'variant': variant,
        'definition': VARIANTS.get(variant, {'production_chunker': 'rag.book_ingest.chunk_text 3000/400'}),
        'model_name': MODEL_NAME, 'model_max_seq_length': max_seq_length,
        'special_token_count': tokenizer.num_special_tokens_to_add(pair=False),
        'embedding_dimension': model.get_embedding_dimension(),
        'source_map_sha256': sha_file(SOURCE_MAP),
        'evaluation_labels_sha256': sha_file(LABELS),
        'chunks_parquet_sha256': sha_file(chunks_path),
        'mapping_sha256': sha_file(mapping_path),
        'statistics': stats, 'books': book_stats,
        'chunk_build_seconds': round(time.perf_counter() - started, 2),
        'status': 'EXPLORATORY_ONLY_DRAFT_LABELS',
    }
    if 'index_build' in existing_manifest:
        manifest['index_build'] = existing_manifest['index_build']
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2),
                                          encoding='utf-8')
    print(target / 'manifest.json')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--variant', choices=['current_baseline', *VARIANTS], required=True)
    args = parser.parse_args()
    build(args.variant)
