"""Embed isolated chunk variants with unchanged MiniLM and IndexFlatIP."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import faiss
import numpy as np
import psutil
import pyarrow.parquet as pq
import torch
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'datasets' / 'rag_experiments' / 'chunking_v1'
MODEL_NAME = 'sentence-transformers/all-MiniLM-L6-v2'
VARIANTS = ('current_baseline', 'tokens_180', 'tokens_220', 'tokens_240')
BATCH_SIZE = 32


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_variant(variant, model, device):
    folder = BASE / variant
    manifest_path = folder / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    chunks_path = folder / 'chunks.parquet'
    if manifest['chunks_parquet_sha256'] != file_hash(chunks_path):
        raise ValueError(f'Chunk artifact changed: {variant}')
    if not (folder / 'visibility.json').exists():
        raise ValueError(f'Visibility audit required before embedding: {variant}')
    rows = pq.read_table(chunks_path, columns=['chunk_id', 'work_id', 'text']).to_pylist()
    if len(rows) != manifest['statistics']['chunk_count']:
        raise ValueError(f'Chunk count mismatch: {variant}')
    if model.max_seq_length != manifest['model_max_seq_length'] or model.get_embedding_dimension() != 384:
        raise ValueError('Model/window/dimension mismatch')
    vectors = np.empty((len(rows), 384), dtype='float32')
    process = psutil.Process()
    peak_rss = process.memory_info().rss
    if device == 'cuda':
        torch.cuda.reset_peak_memory_stats()
    embed_start = time.perf_counter()
    for start in range(0, len(rows), BATCH_SIZE):
        if psutil.virtual_memory().available < 1.5 * (1024 ** 3):
            raise MemoryError('Available RAM below 1.5 GiB; aborting experimental embedding')
        batch = [row['text'] for row in rows[start:start+BATCH_SIZE]]
        vectors[start:start+len(batch)] = np.asarray(model.encode(
            batch, batch_size=BATCH_SIZE, convert_to_numpy=True,
            normalize_embeddings=True, show_progress_bar=False), dtype='float32')
        peak_rss = max(peak_rss, process.memory_info().rss)
        if start // BATCH_SIZE % 50 == 0:
            print(f'{variant} embedded {min(start+BATCH_SIZE,len(rows))}/{len(rows)}', flush=True)
    embed_seconds = time.perf_counter() - embed_start
    norms = np.linalg.norm(vectors, axis=1)
    if not np.all(np.isfinite(vectors)) or not np.allclose(norms, 1, atol=1e-4):
        raise ValueError(f'Embeddings not finite/unit length: {variant}')
    embeddings_path = folder / 'embeddings.npy'
    np.save(embeddings_path, vectors)
    index_start = time.perf_counter()
    index = faiss.IndexFlatIP(384)
    index.add(vectors)
    if index.d != 384 or index.ntotal != len(rows):
        raise ValueError('Global index shape/count mismatch')
    faiss.write_index(index, str(folder / 'faiss.index'))
    book_dir = folder / 'books'
    book_dir.mkdir(exist_ok=True)
    by_book = {}
    for position, row in enumerate(rows):
        by_book.setdefault(row['work_id'], []).append(position)
    for work_id, positions in by_book.items():
        sub = faiss.IndexFlatIP(384)
        sub.add(vectors[np.asarray(positions, dtype=int)])
        if sub.ntotal != len(positions):
            raise ValueError(f'Book index count mismatch: {work_id}')
        faiss.write_index(sub, str(book_dir / f'{work_id}.index'))
    index_seconds = time.perf_counter() - index_start
    manifest['index_build'] = {
        'model_name': MODEL_NAME, 'device': device, 'batch_size': BATCH_SIZE,
        'embedding_count': len(rows), 'embedding_dimension': 384,
        'normalized_min': float(norms.min()),
        'normalized_max': float(norms.max()),
        'faiss_type': 'IndexFlatIP', 'index_ntotal': index.ntotal,
        'per_book_index_count': len(by_book),
        'embedding_seconds': round(embed_seconds, 2),
        'index_seconds': round(index_seconds, 2),
        'peak_process_rss_bytes': peak_rss,
        'peak_torch_gpu_allocated_bytes': (
            torch.cuda.max_memory_allocated() if device == 'cuda' else None),
        'peak_torch_gpu_reserved_bytes': (
            torch.cuda.max_memory_reserved() if device == 'cuda' else None),
        'embeddings_npy_bytes': embeddings_path.stat().st_size,
        'global_index_bytes': (folder / 'faiss.index').stat().st_size,
        'per_book_index_bytes': sum(p.stat().st_size for p in book_dir.glob('*.index')),
        'embeddings_sha256': file_hash(embeddings_path),
        'global_index_sha256': file_hash(folder / 'faiss.index'),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'{variant}: {len(rows)} normalized vectors, embedding {embed_seconds:.1f}s, index {index_seconds:.1f}s', flush=True)
    return manifest['index_build']


def main(names):
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = SentenceTransformer(MODEL_NAME, device=device, local_files_only=True)
    model.encode(['warm up'], convert_to_numpy=True, normalize_embeddings=True)
    for name in names:
        build_variant(name, model, device)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--all', action='store_true')
    group.add_argument('--variant', choices=VARIANTS)
    args = parser.parse_args()
    main(VARIANTS if args.all else (args.variant,))
