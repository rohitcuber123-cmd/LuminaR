"""Read-only freeze checks shared by G2 stages."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TRAIN=ROOT/'datasets/training'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def verify():
    pre=json.loads((TRAIN/'reports/rag_g2_nq_preflight.json').read_text())
    prod=json.loads((ROOT/'datasets/rag_experiments/chunking_v1/reports/production_before_sha256.json').read_text())
    for p,h in {**prod,**pre['g1_before_sha256']}.items():
        if not (ROOT/p).exists() or sha(ROOT/p)!=h:raise RuntimeError(f'Frozen production/G1 drift: {p}')
    for p,h in pre['base_snapshot_sha256'].items():
        if sha(Path(pre['base_snapshot'])/p)!=h:raise RuntimeError(f'Baseline drift: {p}')
    c=json.loads((TRAIN/'manifests/control_v1.json').read_text());corpus=ROOT/'datasets/rag_experiments/chunking_v1/tokens_220'
    for p,k in [(corpus/'chunks.parquet','chunks_parquet_sha256'),(corpus/'mapping.json','mapping_sha256'),(corpus/'manifest.json','manifest_sha256'),(ROOT/'rag/evaluation/source_map_v1.json','source_map_sha256'),(ROOT/'rag/evaluation/rag_retrieval_eval_v1.json','evaluation_labels_sha256')]:
        if sha(p)!=c[k]:raise RuntimeError(f'Frozen evaluation drift: {p}')
    m=json.loads((corpus/'manifest.json').read_text())
    assert {w:b['source_sha256'] for w,b in m['books'].items()}==c['source_hashes']
    return {'production_files':len(prod),'production_changed':0,'g1_files':len(pre['g1_before_sha256']),'g1_changed':0,'baseline_unchanged':True,'corpus_labels_sources_unchanged':True}
