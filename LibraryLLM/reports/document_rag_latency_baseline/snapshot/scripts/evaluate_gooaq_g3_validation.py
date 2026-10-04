"""Held-out GooAQ actual retrieval against 5k distinct validation passages."""
import json
from pathlib import Path
import faiss
import numpy as np
import pyarrow.parquet as pq
import psutil
import torch
from sentence_transformers import SentenceTransformer
from gooaq_g3_controls import ROOT, TRAIN, verify, sha
from gooaq_g3_controls import local_base_model
from gooaq_g3_controls import norm

def main():
    verify()
    faiss.omp_set_num_threads(4)
    data=TRAIN/'generic/gooaq_g3'
    m=json.loads((data/'manifest.json').read_text())
    path=Path(m['files']['validation']['path']);assert sha(path)==m['files']['validation']['sha256']
    pairs=pq.read_table(path).to_pylist()
    canonical={}
    for x in pairs:canonical.setdefault(norm(x['positive']),x['positive'])
    corpus=list(canonical.values())
    gold={norm(x):i for i,x in enumerate(corpus)}
    train=pq.read_table(data/'gooaq_g3_pairs_train.parquet',columns=['question','positive']).to_pylist()
    overlap=len({norm(x['positive']) for x in train}&{norm(x['positive']) for x in pairs})
    assert not {norm(x['question']) for x in train}&{norm(x['question']) for x in pairs}
    report={'type':'actual held-out retrieval; candidate corpus = deduplicated 5k validation positives; not full GooAQ corpus','queries':len(pairs),'candidate_count':len(corpus),'train_validation_document_overlap':overlap,'train_validation_normalized_query_overlap':0,'results':{}}
    full=json.loads((TRAIN/'manifests/minilm_g3_gooaq_50k_full.json').read_text())
    assert sha(TRAIN/'models/minilm_g3_gooaq_50k_full/model.safetensors')==full['model_weights_sha256']
    min_free=[]
    def encode(model,texts):
        vectors=np.empty((len(texts),384),dtype=np.float32)
        for start in range(0,len(texts),32):
            free=torch.cuda.mem_get_info()[0];min_free.append(free)
            if free<1.5*1024**3:raise MemoryError('Unsafe GPU headroom; STOP')
            if psutil.virtual_memory().available<1.5*1024**3:raise MemoryError('Unsafe RAM headroom; STOP')
            batch=texts[start:start+32]
            vectors[start:start+len(batch)]=model.encode(batch,batch_size=32,normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False)
        assert np.isfinite(vectors).all() and np.allclose(np.linalg.norm(vectors,axis=1),1,atol=1e-4)
        return vectors
    for name,path in [('A',local_base_model()),('G3',TRAIN/'models/minilm_g3_gooaq_50k_full')]:
        model=SentenceTransformer(str(path),device='cuda',local_files_only=True)
        assert model.max_seq_length==256 and model.get_embedding_dimension()==384
        ce=encode(model,corpus)
        qe=encode(model,[x['question'] for x in pairs])
        idx=faiss.IndexFlatIP(384);idx.add(ce);_,ids=idx.search(qe,50)
        ranks=[]
        for x,found in zip(pairs,ids):
            loc=np.where(found==gold[norm(x['positive'])])[0];ranks.append(int(loc[0]+1) if len(loc) else None)
        report['results'][name]={'MRR@50':float(np.mean([1/r if r else 0 for r in ranks])),**{f'Hit@{k}':float(np.mean([r is not None and r<=k for r in ranks])) for k in [1,5,10,20,50]}}
        del model,ce,qe
        torch.cuda.empty_cache()
        print(f'{name} held-out retrieval complete',flush=True)
    report['minimum_global_free_vram_bytes']=min(min_free)
    (TRAIN/'reports/rag_g3_gooaq_generic_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
