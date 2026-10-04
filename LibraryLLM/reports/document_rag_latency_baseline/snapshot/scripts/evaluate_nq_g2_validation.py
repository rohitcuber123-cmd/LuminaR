"""Held-out NQ actual retrieval against 5k distinct validation passages."""
import json
from pathlib import Path
import faiss
import numpy as np
import pyarrow.parquet as pq
from sentence_transformers import SentenceTransformer
from nq_g2_controls import ROOT, TRAIN, verify, sha
from train_nq_biencoder_g2 import local_base_model
from prepare_nq_g2 import norm

def main():
    verify()
    data=TRAIN/'generic/nq_g2'
    m=json.loads((data/'manifest.json').read_text())
    path=Path(m['files']['validation']['path']);assert sha(path)==m['files']['validation']['sha256']
    pairs=pq.read_table(path).to_pylist()
    canonical={}
    for x in pairs:canonical.setdefault(norm(x['positive']),x['positive'])
    corpus=list(canonical.values())
    gold={norm(x):i for i,x in enumerate(corpus)}
    report={'type':'actual held-out retrieval; candidate corpus = deduplicated 5k validation positives; not full NQ corpus','queries':len(pairs),'candidate_count':len(corpus),'results':{}}
    for name,path in [('A',local_base_model()),('G2',TRAIN/'models/minilm_g2_nq_50k_full')]:
        model=SentenceTransformer(str(path),device='cuda',local_files_only=True)
        ce=model.encode(corpus,batch_size=32,normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=True)
        qe=model.encode([x['query'] for x in pairs],batch_size=32,normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=True)
        idx=faiss.IndexFlatIP(384);idx.add(ce);_,ids=idx.search(qe,50)
        ranks=[]
        for x,found in zip(pairs,ids):
            loc=np.where(found==gold[norm(x['positive'])])[0];ranks.append(int(loc[0]+1) if len(loc) else None)
        report['results'][name]={'MRR@50':float(np.mean([1/r if r else 0 for r in ranks])),**{f'Hit@{k}':float(np.mean([r is not None and r<=k for r in ranks])) for k in [1,5,10,20,50]}}
        del model,ce,qe
    (TRAIN/'reports/rag_g2_nq_generic_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
