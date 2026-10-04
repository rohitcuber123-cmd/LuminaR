"""Pinned NQ inventory and seed-42 query-disjoint bounded selection."""
import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import random
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'datasets/training/generic/nq_g2'
CACHE = ROOT / 'datasets/training/hf_cache/nq_g2'
os.environ['HF_HOME'] = str(CACHE)
os.environ['HF_DATASETS_CACHE'] = str(CACHE / 'datasets')
from datasets import load_dataset
import pyarrow as pa
import pyarrow.parquet as pq
from sentence_transformers import SentenceTransformer
from prepare_msmarco_g1 import local_base_model, lengths, sha256

def norm(s):
    return ' '.join(unicodedata.normalize('NFKC', s).casefold().split())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rows', type=int, default=50000)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    assert args.rows == 50000 and args.seed == 42
    if (OUT / 'manifest.json').exists(): raise FileExistsError(OUT)
    source = json.loads((ROOT / 'datasets/training/reports/rag_g2_nq_source_probe_retry.json').read_text())
    assert source['status'] == 'accessible'
    ds = load_dataset(source['dataset_id'], 'pair', split='train', revision=source['revision'], cache_dir=str(CACHE / 'datasets'))
    assert set(ds.features) == {'query', 'answer'}
    assert all(ds.features[c].dtype == 'string' for c in ds.features)
    raw = list(ds)
    stats = {'total_rows':len(raw), 'empty_queries':sum(not (x['query'] or '').strip() for x in raw),
             'empty_answers':sum(not (x['answer'] or '').strip() for x in raw)}
    nonempty = [(x['query'].strip(), x['answer'].strip()) for x in raw if (x['query'] or '').strip() and (x['answer'] or '').strip()]
    stats.update(exact_duplicate_pairs=sum(v-1 for v in Counter(nonempty).values()),
                 duplicate_queries=sum(v-1 for v in Counter(q for q,p in nonempty).values()),
                 duplicate_answer_passages=sum(v-1 for v in Counter(p for q,p in nonempty).values()),
                 query_equals_answer=sum(norm(q)==norm(p) for q,p in nonempty))
    pairs=list(dict.fromkeys((q,p) for q,p in nonempty if norm(q)!=norm(p)))
    model=SentenceTransformer(str(local_base_model()),device='cpu',local_files_only=True)
    assert model.max_seq_length==256 and model.get_embedding_dimension()==384
    stats['token_lengths']={'query':lengths(model.tokenizer,[q for q,p in nonempty]),'answer':lengths(model.tokenizer,[p for q,p in nonempty])}
    groups=defaultdict(list)
    for q,p in pairs:groups[norm(q)].append({'query':q,'positive':p})
    stats['multi_positive_queries']=sum(len({norm(x['positive']) for x in rows})>1 for rows in groups.values())
    keys=list(groups);random.Random(42).shuffle(keys)
    # One random positive per normalized query for bounded pilot; preserve every
    # known alternate in the full source mapping used by mining safeguards.
    rng=random.Random(42)
    selected=[rng.choice(groups[k]) for k in keys[:50000]]
    assert len(selected)==50000
    train,val=selected[:45000],selected[45000:]
    assert not {norm(x['query']) for x in train}&{norm(x['query']) for x in val}
    OUT.mkdir(parents=True,exist_ok=True)
    files={}
    for name,rows in [('pairs_train',train),('pairs_validation',val),('source_pairs',[{'query':q,'positive':p} for q,p in pairs])]:
        path=OUT/f'nq_g2_{name}.parquet';pq.write_table(pa.Table.from_pylist(rows),path,compression='zstd')
        files[name]={'path':str(path),'rows':len(rows),'sha256':sha256(path)}
    pre=json.loads((ROOT/'datasets/training/reports/rag_g2_nq_preflight.json').read_text())
    m={'experiment':'G2_NATURAL_QUESTIONS','dataset_id':source['dataset_id'],'revision':source['revision'],'config':'pair','split':'train','schema':{c:ds.features[c].dtype for c in ds.features},'download_status':'SUCCESS after sandbox-network escalation; public unauthenticated source','inventory':stats,'selection_seed':42,'selected_rows':50000,'selection_policy':'uniform shuffled normalized-query groups; one seeded random positive per query; all source positives retained for exclusion','train_validation_normalized_query_overlap':0,'files':files,'versions':pre['versions']}
    (OUT/'manifest.json').write_text(json.dumps(m,indent=2),encoding='utf-8')
    print(json.dumps(m,indent=2),flush=True)
if __name__=='__main__':main()
