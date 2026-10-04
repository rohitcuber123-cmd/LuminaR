"""Installed ST miner with full NQ corpus and known-positive protections."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import torch
import faiss
from datasets import Dataset
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import mine_hard_negatives
from prepare_nq_g2 import OUT, ROOT, norm
from prepare_msmarco_g1 import local_base_model, sha256

def dist(values):
    a=np.asarray(values)
    return {k:float(v) for k,v in zip(['min','p10','median','p90','p95','max'],np.quantile(a,[0,.1,.5,.9,.95,1]))}|{'mean':float(a.mean()),'count':len(a)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--calibrate',type=int);ap.add_argument('--train',action='store_true');ap.add_argument('--seed',type=int,default=42);args=ap.parse_args()
    assert args.seed==42 and (args.train or args.calibrate==500)
    torch.manual_seed(42);np.random.seed(42);random.seed(42)
    if torch.cuda.mem_get_info()[0]<4*1024**3:raise MemoryError('Unsafe mining GPU headroom')
    full=pq.read_table(OUT/'nq_g2_source_pairs.parquet').to_pylist()
    known=defaultdict(set)
    for x in full:known[norm(x['query'])].add(norm(x['positive']))
    # Canonicalize normalized duplicate corpus passages, preserving positive
    # texts for the installed miner and excluding all normalized known positives.
    canonical={}
    for x in full:canonical.setdefault(norm(x['positive']),x['positive'])
    corpus=list(canonical.values())
    pairs=pq.read_table(OUT/'nq_g2_pairs_train.parquet').to_pylist()
    if args.calibrate:
        pairs=pairs[:500]
    else:
        validation=pq.read_table(OUT/'nq_g2_pairs_validation.parquet').to_pylist()
        blocked={norm(x['query']) for x in pairs+validation}
        reserves=[x for x in full if norm(x['query']) not in blocked]
        random.Random(42).shuffle(reserves)
        pairs=pairs+reserves[:5000]
    model=SentenceTransformer(str(local_base_model()),device='cuda',local_files_only=True)
    assert model.max_seq_length==256 and model.get_embedding_dimension()==384
    cache=OUT/'mining_cache'
    def run(settings,num):
        return mine_hard_negatives(Dataset.from_list(pairs),model,
            anchor_column_name='query',positive_column_name='positive',corpus=corpus,
            range_min=10,range_max=50,num_negatives=num,sampling_strategy='random',
            output_scores=True,batch_size=32,faiss_batch_size=256,use_faiss=True,
            cache_folder=str(cache),**settings)
    if args.calibrate:
        raw=list(run({},5))
        rawstats={k:dist(v) for k,v in {
            'positive':[x['scores'][0] for x in raw],
            'negative':[x['scores'][1] for x in raw],
            'margin':[x['scores'][0]-x['scores'][1] for x in raw]}.items()}
        # Data-informed cap: bounded by the positive-score upper quartile and
        # .80; impose 10% relative and .05 absolute separation for this pilot.
        settings={'max_score':float(min(.8,np.quantile([x['scores'][0] for x in raw],.75))),
                  'relative_margin':.10,'absolute_margin':.05}
    else:
        audit=json.loads((OUT/'calibration_audit.json').read_text())
        assert audit['approved'] and audit['possible_false_negative']==0
        settings=json.loads((OUT/'calibration.json').read_text())['settings'];rawstats=None
    candidates=list(run(settings,5))
    selected={};excluded=0
    for x in candidates:
        if norm(x['negative']) in known[norm(x['query'])]:excluded+=1;continue
        if x['query'] not in selected:selected[x['query']]=x
    missing=[x['query'] for x in pairs if x['query'] not in selected]
    # Keep thresholds fixed. Calibration records coverage; full training uses
    # seed-42 reserve NQ queries to reach 45k safely, never validation queries.
    if missing:
        (OUT/('calibration_missing.json' if args.calibrate else 'mining_missing.json')).write_text(json.dumps(missing,indent=2),encoding='utf-8')
        if args.train and len(selected)<45000:
            raise RuntimeError(f'Only {len(selected)} safe queries after reserve mining; STOP')
    # Diagnostic raw ranks from the exact installed miner cache ordering.
    merged=list(dict.fromkeys(corpus+[x['positive'] for x in pairs]))
    name=model.model_card_data.base_model or ''
    ch=hashlib.sha256((name+''.join(merged)).encode()).hexdigest()
    qh=hashlib.sha256((name+''.join(x['query'] for x in pairs)).encode()).hexdigest()
    ce=np.load(cache/f'corpus_embeddings_{ch}.npy');qe=np.load(cache/f'query_embeddings_{qh}.npy')
    idx=faiss.IndexFlatIP(384);idx.add(ce);mapping={x:i for i,x in enumerate(merged)}
    rows=[]
    for start in range(0,len(pairs),256):
        _,indices=idx.search(qe[start:start+256],51)
        for offset,pair in enumerate(pairs[start:start+256]):
            if pair['query'] not in selected:continue
            x=selected[pair['query']];target=mapping[x['negative']]
            matches=np.where(indices[offset]==target)[0]
            assert len(matches)==1
            pos,neg=x['scores'];assert pos-neg>=.05-1e-5 and neg<=settings['max_score']+1e-5
            assert norm(x['negative']) not in known[norm(x['query'])]
            rows.append({'query':x['query'],'positive':x['positive'],'negative':x['negative'],
                         'negative_rank':int(matches[0]+1),'positive_score':pos,'negative_score':neg,'margin':pos-neg})
    attempted_count=len(pairs)
    retained_candidates=len(rows)
    if args.train:rows=rows[:45000]
    initial_queries={p['query'] for p in pairs[:45000]}
    report={'attempted_queries':attempted_count,'unmineable_queries':len(missing),'safe_candidate_queries':retained_candidates,'reserve_replacements':sum(x['query'] not in initial_queries for x in rows) if args.train else 0,'settings':settings,'range_min':10,'range_max':50,'rank_semantics':'installed miner ranks eligible candidates after positive/score masking; saved negative_rank is raw 1-based full-corpus rank',
            'candidates_per_query':5,'retained_per_query':1,'rows':len(rows),'normalized_corpus_count':len(corpus),'miner_corpus_count':len(merged),'known_positive_candidates_excluded':excluded,
            'raw_calibration_distributions':rawstats,'distributions':{k:dist([x[k] for x in rows]) for k in ['positive_score','negative_score','margin','negative_rank']},
            'mining_model':'sentence-transformers/all-MiniLM-L6-v2','false_negative_safeguards':'all full-source alternate positives by normalized query/text excluded; 10% relative + .05 absolute margin; data-informed max_score; ranks 10–50 of eligible candidates; no cross-encoder'}
    if args.calibrate:
        target=OUT/'nq_g2_calibration.parquet'
        report['audit_sample']=random.Random(42).sample(rows,25)
        reportpath=OUT/'calibration.json'
    else:
        target=OUT/'nq_g2_train_triplets.parquet';reportpath=OUT/'mining.json'
    if target.exists():raise FileExistsError(target)
    pq.write_table(pa.Table.from_pylist(rows),target,compression='zstd')
    report['file']={'path':str(target),'sha256':sha256(target),'rows':len(rows)}
    reportpath.write_text(json.dumps(report,indent=2),encoding='utf-8')
    if args.train:
        m=json.loads((OUT/'manifest.json').read_text());m['mining']=report;m['files']['train']=report['file'];m['files']['validation']=m['files']['pairs_validation']
        finalpairs=OUT/'nq_g2_pairs_train_final.parquet'
        pq.write_table(pa.Table.from_pylist([{'query':x['query'],'positive':x['positive']} for x in rows]),finalpairs,compression='zstd')
        m['files']['pairs_train_initial']=m['files']['pairs_train'];m['files']['pairs_train']={'path':str(finalpairs),'rows':45000,'sha256':sha256(finalpairs)}
        assert not {norm(x['query']) for x in rows}&{norm(x['query']) for x in validation}
        m['selection_deviation']='Unmineable initial TRAIN queries replaced with seed-42 shuffled NQ reserve queries; margins/window unchanged; validation unchanged; final 45k/5k'
        (OUT/'manifest.json').write_text(json.dumps(m,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='audit_sample'},indent=2),flush=True)
if __name__=='__main__':main()
