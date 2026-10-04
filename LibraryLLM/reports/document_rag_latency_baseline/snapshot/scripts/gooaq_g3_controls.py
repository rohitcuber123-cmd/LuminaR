"""G3 utilities and read-only historical freeze checks."""
import hashlib
import json
from pathlib import Path
import unicodedata

ROOT=Path(__file__).resolve().parents[1]
TRAIN=ROOT/'datasets/training'
DATA=TRAIN/'generic/gooaq_g3'
CACHE=TRAIN/'hf_cache/gooaq_g3'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,value):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,indent=2),encoding='utf-8')
def norm(s):return ' '.join(unicodedata.normalize('NFKC',s).casefold().split())
def local_base_model():return Path(read(TRAIN/'reports/rag_g3_gooaq_preflight.json')['base_snapshot'])
def lengths(tokenizer,values):
    counts=[]
    for i in range(0,len(values),512):
        counts.extend(map(len,tokenizer(values[i:i+512],add_special_tokens=True,truncation=False,padding=False)['input_ids']))
    ordered=sorted(counts)
    def pct(p):return ordered[int((len(ordered)-1)*p)]
    return {'min':ordered[0],'median':pct(.5),'p90':pct(.9),'p95':pct(.95),'p99':pct(.99),'max':ordered[-1],'over_256':sum(x>256 for x in counts)}
def verify():
    pre=read(TRAIN/'reports/rag_g3_gooaq_preflight.json')
    prod=read(ROOT/'datasets/rag_experiments/chunking_v1/reports/production_before_sha256.json')
    for p,h in {**prod,**pre['historical_before_sha256']}.items():
        if not (ROOT/p).exists() or sha(ROOT/p)!=h:raise RuntimeError(f'Historical/production drift: {p}')
    for p,h in pre['base_snapshot_sha256'].items():
        if sha(Path(pre['base_snapshot'])/p)!=h:raise RuntimeError(f'Baseline drift: {p}')
    c=read(TRAIN/'manifests/control_v1.json');corpus=ROOT/'datasets/rag_experiments/chunking_v1/tokens_220'
    for p,k in [(corpus/'chunks.parquet','chunks_parquet_sha256'),(corpus/'mapping.json','mapping_sha256'),(corpus/'manifest.json','manifest_sha256'),(ROOT/'rag/evaluation/source_map_v1.json','source_map_sha256'),(ROOT/'rag/evaluation/rag_retrieval_eval_v1.json','evaluation_labels_sha256')]:
        if sha(p)!=c[k]:raise RuntimeError(f'Frozen evaluation drift: {p}')
    assert {w:b['source_sha256'] for w,b in read(corpus/'manifest.json')['books'].items()}==c['source_hashes']
    return {'production_files':len(prod),'production_changed':0,'historical_files':len(pre['historical_before_sha256']),'G1_G2_changed':0,'baseline_unchanged':True,'corpus_labels_sources_unchanged':True}
