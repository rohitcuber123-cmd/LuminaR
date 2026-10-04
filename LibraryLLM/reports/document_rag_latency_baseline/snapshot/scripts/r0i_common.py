"""Shared R0I controls; frozen models, exact passages, raw CE and variable-K metrics."""
from __future__ import annotations
from collections import Counter
import math
import os
from pathlib import Path
import statistics
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.evaluate_rag_r0_existing_crossencoder import (
    TRAIN, REPORTS, CORPUS, MODEL_ID, CE_CACHE, read, write, sha, verify_ledger, dev_evaluable,
)
from rag.evaluation.metrics import overlaps
KS=(20,30,40,50,60,80)
RAW=REPORTS/'rag_r0i_raw_k.json'
OUT=REPORTS/'rag_r0i_candidate_pool.json'
SCORES=TRAIN/'evaluation/rag_r0i_candidate_pool_scores.parquet'
POLICY='Maximize candidate Recall@K, then candidate Hit@K, then CE Hit@20 and Hit@10; among tied quality choose lowest measured retrieval+CE milliseconds/query, then higher MRR, then smaller K. No query-specific K tuning.'


def freeze():
    r0=read(REPORTS/'rag_r0_existing_crossencoder.json')
    pre=read(REPORTS/'rag_r0_preflight.json')
    verify_ledger(pre['before_sha256'])
    assert r0['decision']=="A. G3'S EXTRA TOP50 COVERAGE IS USEFUL AFTER EXISTING RERANKING"
    assert sha(TRAIN/'evaluation/rag_r0_crossencoder_scores.parquet')==r0['score_parquet_sha256']
    paths={Path(p) for p in pre['before_sha256']}
    paths.update(p for p in REPORTS.iterdir() if p.is_file() and p.name.startswith('rag_r0_'))
    paths.update([ROOT/'scripts/evaluate_rag_r0_existing_crossencoder.py',ROOT/'scripts/finalize_rag_r0_report.py',
                  ROOT/'tests/test_rag_r0_existing_crossencoder.py',TRAIN/'evaluation/rag_r0_crossencoder_scores.parquet',
                  ROOT/'rag/evidence.py',ROOT/'rag/reranker.py',ROOT/'rag/retriever.py'])
    ledger={str(p):sha(p) for p in sorted(paths)}
    return ledger,r0


def prefix(rows,k):
    selected=[dict(x) for x in rows[:k]]
    assert len(selected)==k and len({x['chunk_id'] for x in selected})==k
    assert [x['rank'] for x in selected]==list(range(1,k+1))
    return selected


def rerank(candidates,scores):
    if len(candidates)!=len(scores) or not all(math.isfinite(float(s)) for s in scores):
        raise RuntimeError('Invalid CE scores; STOP')
    before=Counter(c['chunk_id'] for c in candidates)
    assert len(before)==len(candidates)
    rows=[{**c,'ce_score':float(s)} for c,s in zip(candidates,scores)]
    rows.sort(key=lambda c:(-c['ce_score'],c['chunk_id']))
    for i,c in enumerate(rows,1):c['ce_rank']=i
    if Counter(c['chunk_id'] for c in rows)!=before:raise RuntimeError('Candidate membership changed; STOP')
    return rows


def query_metrics(q,rows,chunks,k):
    spans=[p for p in q['accepted_passages'] if p['relevance_grade']==2]
    if not spans:return None
    ranks=[next((i for i,c in enumerate(rows,1) if overlaps(chunks[c['chunk_id']],p)),None) for p in spans]
    first=min((x for x in ranks if x is not None),default=None)
    depths=sorted(set([1,3,5,10,20,k]))
    return {'first_rank':first,'mrr':1/first if first else 0.,'span_ranks':ranks,
            'hit':{str(d):int(first is not None and first<=d) for d in depths},
            'recall':{str(d):sum(x is not None and x<=d for x in ranks)/len(spans) for d in depths},
            'accepted_span_count':len(spans),'admitted_span_count':sum(x is not None for x in ranks)}


def metrics(questions,pools,chunks,k):
    per={q['query_id']:query_metrics(q,pools[q['query_id']],chunks,k) for q in dev_evaluable(questions)}
    assert all(v is not None for v in per.values())
    vals=list(per.values())
    return {'evaluated':len(vals),'mrr':statistics.mean(x['mrr'] for x in vals),
            'hit':{d:statistics.mean(x['hit'][d] for x in vals) for d in vals[0]['hit']},
            'recall':{d:statistics.mean(x['recall'][d] for x in vals) for d in vals[0]['recall']},
            'candidate_Hit':statistics.mean(x['first_rank'] is not None for x in vals),
            'candidate_Recall':statistics.mean(x['admitted_span_count']/x['accepted_span_count'] for x in vals),
            'covered_queries':sum(x['first_rank'] is not None for x in vals),
            'no_gold_candidate_count':sum(x['first_rank'] is None for x in vals),
            'admitted_spans':sum(x['admitted_span_count'] for x in vals),'total_accepted_spans':sum(x['accepted_span_count'] for x in vals),
            'per_query':per}


def select_k(results):
    def priority(r):
        d=r['candidate_metrics'];c=r['CE_metrics'];t=r['timing']
        return (d['candidate_Recall'],d['candidate_Hit'],c['hit']['20'],c['hit']['10'],
                -t['average_retrieval_plus_CE_ms_per_query'],c['mrr'],-r['k'])
    return max(results,key=priority)['k']


def dense_preserving_union(dense,expansion,extra=20):
    seen={c['chunk_id'] for c in dense}
    out=[dict(c) for c in dense]
    added=0
    for c in expansion:
        if c['chunk_id'] not in seen and added<extra:
            out.append(dict(c));seen.add(c['chunk_id']);added+=1
    assert {c['chunk_id'] for c in dense}.issubset({c['chunk_id'] for c in out})
    return out


class Memory:
    def __init__(self,torch,psutil):self.torch=torch;self.psutil=psutil
    def __enter__(self):
        self.torch.cuda.reset_peak_memory_stats();self.free=self.torch.cuda.mem_get_info()[0]
        self.rss=self.psutil.Process().memory_info().rss;self.stop=threading.Event()
        def observe():
            while not self.stop.wait(.05):
                self.free=min(self.free,self.torch.cuda.mem_get_info()[0]);self.rss=max(self.rss,self.psutil.Process().memory_info().rss)
        self.thread=threading.Thread(target=observe,daemon=True);self.thread.start();return self
    def __exit__(self,*exc):
        self.stop.set();self.thread.join(timeout=2)
        self.free=min(self.free,self.torch.cuda.mem_get_info()[0])
        self.result={'peak_allocated_VRAM_bytes':self.torch.cuda.max_memory_allocated(),
                     'peak_reserved_VRAM_bytes':self.torch.cuda.max_memory_reserved(),
                     'minimum_global_free_VRAM_bytes':self.free,'peak_process_RSS_bytes':self.rss}
        if self.free<1.5*1024**3:raise MemoryError('Unsafe GPU headroom; STOP')


class Runtime:
    def __init__(self,r0):
        os.environ['HF_HUB_OFFLINE']='1';os.environ['HF_DATASETS_OFFLINE']='1'
        import numpy as np
        import faiss
        import torch
        import psutil
        import pyarrow.parquet as pq
        from sentence_transformers import SentenceTransformer,CrossEncoder
        import subprocess
        self.np=np;self.torch=torch;self.psutil=psutil;faiss.omp_set_num_threads(4)
        free,total=torch.cuda.mem_get_info()
        if free<4*1024**3 or psutil.virtual_memory().available<2*1024**3:raise MemoryError('Insufficient current shared-machine headroom; STOP')
        self.environment={'python_executable':sys.executable,'GPU':torch.cuda.get_device_name(0),'total_VRAM_bytes':total,
                          'free_VRAM_bytes':free,'RAM_total_bytes':psutil.virtual_memory().total,
                          'RAM_available_bytes':psutil.virtual_memory().available,'CUDA':torch.version.cuda,
                          'torch':torch.__version__,'other_GPU_usage':subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name,used_gpu_memory','--format=csv,noheader'],capture_output=True,text=True).stdout.strip()}
        g3=read(TRAIN/'manifests/minilm_g3_gooaq_50k_full.json')
        self.g3_info={'path':g3['model_path'],'weights_sha256':g3['model_weights_sha256'],'max_length':256,'dimension':384}
        assert sha(Path(g3['model_path'])/'model.safetensors')==g3['model_weights_sha256']
        snapshot=Path(r0['cross_encoder']['path'])
        for f,h in r0['cross_encoder']['files_sha256'].items():assert sha(snapshot/f)==h
        self.ce_info=r0['cross_encoder'];self.batch_size=16
        self.g3=SentenceTransformer(g3['model_path'],device='cuda',local_files_only=True)
        self.ce=CrossEncoder(str(snapshot),device='cuda',local_files_only=True,model_kwargs={'dtype':torch.float32})
        self.ce.eval()
        assert self.g3.max_seq_length==256 and self.g3.get_embedding_dimension()==384
        assert self.ce.max_length==512 and next(self.ce.parameters()).dtype==torch.float32
        rows=pq.read_table(CORPUS/'chunks.parquet',columns=['chunk_id','work_id','text','source_start_char','source_end_char']).to_pylist()
        self.chunks={r['chunk_id']:{'work_id':r['work_id'],'text':r['text'],'start':r['source_start_char'],'end':r['source_end_char']} for r in rows}
        self.books=read(CORPUS/'manifest.json')['books'];self.bybook={}
        for r in rows:self.bybook.setdefault(r['work_id'],[]).append(r)
        self.indexes={w:faiss.read_index(str(TRAIN/f'evaluation_indexes/minilm_g3_gooaq_50k/books/{w}.index')) for w in self.bybook}
        self.questions=[q for q in read(ROOT/'rag/evaluation/rag_retrieval_eval_v1.json')['questions'] if q['split']=='DEV']
        self.evaluable=dev_evaluable(self.questions);self.allowed={q['query_id'] for q in self.questions};self.encoded=[]
        assert len(self.questions)==30 and len(self.evaluable)==29

    def guard(self):
        if self.torch.cuda.mem_get_info()[0]<1.5*1024**3 or self.psutil.virtual_memory().available<1024**3:raise MemoryError('Unsafe shared-machine headroom; STOP')

    def retrieve(self,q,k,text=None):
        if q['split']!='DEV' or q['query_id'] not in self.allowed:raise RuntimeError('Protected query attempted; STOP')
        self.guard();self.encoded.append({'query_id':q['query_id'],'text':q['question'] if text is None else text})
        v=self.g3.encode([q['question'] if text is None else text],normalize_embeddings=True,convert_to_numpy=True)
        scores,positions=self.indexes[q['work_id']].search(self.np.asarray(v,dtype='float32'),k)
        assert len(positions[0])==k and (positions>=0).all()
        rows=self.bybook[q['work_id']]
        return [{'rank':i,'chunk_id':rows[int(p)]['chunk_id'],'similarity':float(s),
                 'work_id':q['work_id'],'source_start':rows[int(p)]['source_start_char'],'source_end':rows[int(p)]['source_end_char']}
                for i,(p,s) in enumerate(zip(positions[0],scores[0]),1)]

    def score(self,pairs):
        out=[]
        for start in range(0,len(pairs),self.batch_size):
            self.guard()
            out.extend(float(x) for x in self.ce.predict(pairs[start:start+self.batch_size],batch_size=self.batch_size,
                       activation_fn=self.torch.nn.Identity(),apply_softmax=False,show_progress_bar=False,convert_to_numpy=True))
        assert all(math.isfinite(x) for x in out)
        return out

    def warm(self,top80):
        q=self.evaluable[0]
        self.score([(q['question'],self.chunks[c['chunk_id']]['text']) for c in top80[q['query_id']][:16]])


def evaluate_pool(runtime,pools,k,name,retrieval_seconds,start):
    queries=runtime.evaluable
    pairs=[(q['question'],runtime.chunks[c['chunk_id']]['text']) for q in queries for c in pools[q['query_id']]]
    runtime.torch.cuda.synchronize();t=time.perf_counter();scores=runtime.score(pairs)
    runtime.torch.cuda.synchronize();ce_seconds=time.perf_counter()-t
    ranked={};rows=[];offset=0
    for q in queries:
        candidates=pools[q['query_id']];n=len(candidates)
        ranked[q['query_id']]=rerank(candidates,scores[offset:offset+n]);offset+=n
        for c in ranked[q['query_id']]:
            rows.append({'system':name,'candidate_budget':k,'query_id':q['query_id'],'work_id':q['work_id'],
                         'chunk_id':c['chunk_id'],'input_rank':c['rank'],'original_dense_rank':c.get('original_dense_rank',c['rank']),
                         'dense_score':c['similarity'],'ce_score':c['ce_score'],'ce_rank':c['ce_rank'],
                         'cross_encoder_sha256':runtime.ce_info['model_weights_sha256'],'g3_sha256':runtime.g3_info['weights_sha256']})
    dense=metrics(queries,pools,runtime.chunks,k);ce=metrics(queries,ranked,runtime.chunks,k)
    for field in ['candidate_Hit','candidate_Recall','no_gold_candidate_count','admitted_spans']:
        assert dense[field]==ce[field]
    timing={'logical_CE_pairs':len(pairs),'unique_CE_pairs':len({p for p in pairs}),
            'actual_scored_CE_pairs':len(pairs),'retrieval_seconds':retrieval_seconds,'CE_scoring_seconds':ce_seconds,
            'total_query_batch_seconds':time.perf_counter()-start,'average_CE_ms_per_query':1000*ce_seconds/len(queries),
            'average_retrieval_plus_CE_ms_per_query':1000*(ce_seconds+retrieval_seconds)/len(queries)}
    return {'k':k,'system':name,'candidate_metrics':dense,'CE_metrics':ce,'timing':timing,
            'candidate_counts_by_query':{q:len(c) for q,c in pools.items()},'ranked_candidates':ranked},rows


def reproduce(runtime,r0):
    saved={q['query_id']:q for q in read(TRAIN/'evaluation_indexes/minilm_g3_gooaq_50k/dense_dev_evaluation.json')['queries']}
    top80={}
    for q in runtime.questions:
        rows=runtime.retrieve(q,80);top80[q['query_id']]=rows
        if [c['chunk_id'] for c in rows[:50]]!=[c['chunk_id'] for c in saved[q['query_id']]['top50']]:raise RuntimeError('G3 Top50 reproduction failed; STOP')
    return top80,{'all_DEV_queries':30,'evaluable':29,'exact_Top50_ID_match':True,'protected_TEST_encoded':False}


def write_scores(rows):
    import pyarrow as pa
    import pyarrow.parquet as pq
    SCORES.parent.mkdir(parents=True,exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows),SCORES,compression='zstd')


def md_metrics(lines,results):
    lines += ['| System | Candidate Hit | Candidate Recall | No gold | MRR | Hit1 | Hit3 | Hit5 | Hit10 | Hit20 | Recall5 | Recall10 | Recall20 |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in results:
        d=r['candidate_metrics'];c=r['CE_metrics']
        v=[r['system'],f"{d['candidate_Hit']:.2%}",f"{d['candidate_Recall']:.2%}",str(d['no_gold_candidate_count']),f"{c['mrr']:.4f}"]
        v += [f"{c['hit'][str(k)]:.2%}" for k in [1,3,5,10,20]]+[f"{c['recall'][str(k)]:.2%}" for k in [5,10,20]]
        lines.append('| '+' | '.join(v)+' |')
