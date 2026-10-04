"""GooAQ supported mining; preserve every frozen TRAIN question."""
import argparse
from collections import defaultdict
import hashlib
import random
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import torch
import faiss
from datasets import Dataset
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import mine_hard_negatives
from gooaq_g3_controls import *

def dist(v):
    a=np.asarray(v,dtype=float)
    return dict(zip(['min','p10','median','p90','p95','max'],map(float,np.quantile(a,[0,.1,.5,.9,.95,1]))))|{'mean':float(a.mean()),'count':len(a)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--calibrate',type=int);ap.add_argument('--train',action='store_true');ap.add_argument('--seed',type=int,default=42);args=ap.parse_args()
    assert args.seed==42 and (args.train or args.calibrate==500)
    verify();source=read(DATA/'source_manifest.json')
    for f in source['files'].values():assert sha(Path(f['path']))==f['sha256']
    torch.manual_seed(42);np.random.seed(42);random.seed(42);faiss.omp_set_num_threads(4)
    if torch.cuda.mem_get_info()[0]<4*1024**3:raise MemoryError('Unsafe mining GPU headroom; STOP')
    records=pq.read_table(DATA/'gooaq_g3_source_records.parquet').to_pylist();known=defaultdict(set)
    for x in records:known[norm(x['question'])].add(norm(x['positive']))
    del records
    corpus=pq.read_table(DATA/'gooaq_g3_answer_corpus.parquet',columns=['positive'])['positive'].to_pylist()
    assert len(corpus)>=200000 and len({norm(x) for x in corpus})==len(corpus)
    pairs=pq.read_table(DATA/'gooaq_g3_pairs_train.parquet').to_pylist()
    if args.calibrate:pairs=pairs[:500]
    model=SentenceTransformer(str(local_base_model()),device='cuda',local_files_only=True)
    assert model.max_seq_length==256 and model.get_embedding_dimension()==384
    cache=DATA/'mining_cache'
    corpus_index={text:i for i,text in enumerate(corpus)}
    def run(rows,settings,end):
        torch.manual_seed(42);random.seed(42)
        # Observe the supported miner's native FAISS searches to preserve raw
        # ranks without repeating the expensive full-corpus search. Restore the
        # original method immediately; no retrieval/scoring behavior changes.
        captured=[];native_search=faiss.IndexFlatIP.search
        def record_search(index,*search_args,**search_kwargs):
            scores,ids=native_search(index,*search_args,**search_kwargs)
            captured.append(ids.copy())
            return scores,ids
        faiss.IndexFlatIP.search=record_search
        try:
            result=list(mine_hard_negatives(Dataset.from_list(rows),model,anchor_column_name='question',positive_column_name='positive',corpus=corpus,
                range_min=10,range_max=end,num_negatives=5,sampling_strategy='random',output_scores=True,batch_size=32,faiss_batch_size=256,use_faiss=True,cache_folder=str(cache),**settings))
        finally:faiss.IndexFlatIP.search=native_search
        raw_ids=np.concatenate(captured);assert len(raw_ids)==len(rows)
        row_lookup={x['question']:i for i,x in enumerate(rows)}
        for x in result:
            loc=np.where(raw_ids[row_lookup[x['question']]]==corpus_index[x['negative']])[0]
            assert len(loc)==1
            x['raw_rank']=int(loc[0]+1)
        return result
    if args.calibrate:
        raw=run(pairs,{},100)
        rawstats={'positive':dist([x['scores'][0] for x in raw]),'negative':dist([x['scores'][1] for x in raw]),'margin':dist([x['scores'][0]-x['scores'][1] for x in raw])}
        abs_margin=float(np.clip(rawstats['margin']['p10']*.5,.01,.04))
        settings={'absolute_margin':abs_margin,'relative_margin':float(np.clip(abs_margin/max(rawstats['positive']['median'],.01),.02,.08)),
                  'max_score':float(min(.85,np.quantile([x['scores'][1] for x in raw],.99)+.03,np.quantile([x['scores'][0] for x in raw],.75)))}
        settings_reason='GooAQ raw calibration: absolute margin = clipped half p10 observed gap [.01,.04]; relative margin = absolute/median positive clipped [.02,.08]; cap = min(.85, negative p99+.03, positive p75)'
        if (DATA/'calibration_policy.json').exists():
            policy=read(DATA/'calibration_policy.json')
            settings.update(policy['settings_override'])
            settings_reason += '; '+policy['reason']
    else:
        audit=read(DATA/'calibration_audit.json');assert audit['approved']
        cal=read(DATA/'calibration.json');settings=cal['settings'];settings_reason=cal['settings_reason'];rawstats=None
    chosen={};excluded=0
    def consume(candidates,window):
        nonlocal excluded
        for x in candidates:
            if norm(x['negative']) in known[norm(x['question'])]:excluded+=1;continue
            if x['question'] not in chosen:chosen[x['question']]=x|{'negative_kind':'HARD','mining_window_max':window}
    consume(run(pairs,settings,100),100)
    missing=[x for x in pairs if x['question'] not in chosen]
    initial_missing=len(missing)
    if missing:consume(run(missing,settings,500),500)
    missing=[x for x in pairs if x['question'] not in chosen]
    fallback_count=len(missing)
    if args.train and fallback_count/len(pairs)>.05:
        write(DATA/'mining_stop.json',{'reason':'G3 negative-mining design not comparable / insufficient: >5% random fallback required','fallback_count':fallback_count,'train_count':len(pairs),'fraction':fallback_count/len(pairs),'settings':settings})
        raise RuntimeError(f'{fallback_count}/{len(pairs)} random fallbacks required (>5%); STOP')
    # Use the exact cached normalized embeddings/order from the installed miner
    # for diagnostics and tagged safe-random fallback; retrieval mining itself
    # remains the installed ST implementation.
    name=model.model_card_data.base_model or ''
    ch=hashlib.sha256((name+''.join(corpus)).encode()).hexdigest();qh=hashlib.sha256((name+''.join(x['question'] for x in pairs)).encode()).hexdigest()
    ce=np.load(cache/f'corpus_embeddings_{ch}.npy',mmap_mode='r');qe=np.load(cache/f'query_embeddings_{qh}.npy',mmap_mode='r')
    cidx={x:i for i,x in enumerate(corpus)};qidx={x['question']:i for i,x in enumerate(pairs)}
    rng=random.Random(42)
    for x in missing:
        qi=qidx[x['question']];pos=float(qe[qi]@ce[cidx[x['positive']]])
        found=None
        for attempt in range(10):
            candidates=[rng.randrange(len(corpus)) for _ in range(1024)];scores=np.asarray(ce[candidates])@qe[qi]
            for ni,neg in zip(candidates,scores):
                if norm(corpus[ni]) in known[norm(x['question'])]:continue
                if neg<=settings['max_score'] and pos-neg>=settings['absolute_margin'] and neg<=pos-abs(pos)*settings['relative_margin']:
                    found=x|{'negative':corpus[ni],'scores':[pos,float(neg)],'negative_kind':'RANDOM_FALLBACK','mining_window_max':None};break
            if found:break
        if not found:raise RuntimeError('Cannot obtain safe random fallback; STOP')
        chosen[x['question']]=found
    rows=[]
    for start in range(0,len(pairs),256):
        for offset,pair in enumerate(pairs[start:start+256]):
            x=chosen[pair['question']];pos,neg=x['scores']
            assert norm(x['negative']) not in known[norm(x['question'])]
            assert neg<=settings['max_score']+1e-5 and pos-neg>=settings['absolute_margin']-1e-5
            rank=x['raw_rank'] if x['negative_kind']=='HARD' else None
            if x['negative_kind']=='HARD':assert rank is not None
            rows.append({'question':pair['question'],'positive':pair['positive'],'negative':x['negative'],'negative_kind':x['negative_kind'],
                         'negative_rank':rank,'positive_score':pos,'negative_score':neg,'score_margin':pos-neg,'mining_window_max':x['mining_window_max']})
        if start%5000<256:print(f'diagnostic ranks {min(start+256,len(pairs))}/{len(pairs)}',flush=True)
    report={'mining_model':'sentence-transformers/all-MiniLM-L6-v2','base_snapshot':str(local_base_model()),'corpus_count':len(corpus),'settings':settings,'settings_reason':settings_reason,
            'initial_window':[10,100],'wider_window':[10,500],'window_note':'installed miner applies rank slice to eligible candidates after score/positive masking; stored ranks are raw 1-based corpus ranks',
            'candidates_per_query':5,'retained_per_query':1,'initial_unmineable':initial_missing,'wider_window_hard_count':sum(x['mining_window_max']==500 for x in rows),
            'hard_count':sum(x['negative_kind']=='HARD' for x in rows),'random_fallback_count':fallback_count,'random_fallback_fraction':fallback_count/len(rows),
            'known_positive_candidates_excluded':excluded,'raw_calibration_distributions':rawstats,
            'distributions':{k:dist([x[k] for x in rows if x[k] is not None]) for k in ['positive_score','negative_score','score_margin','negative_rank']},
            'safeguards':'all normalized positives/alternates discoverable in bounded source records excluded; rank floor10, calibrated ceiling/margins; fixed safe wider window; random fallback also score/margin screened; no query replacement',
            'rows':len(rows),'query_replacements':0,'software_versions':source['versions']}
    target=DATA/('gooaq_g3_calibration.parquet' if args.calibrate else 'gooaq_g3_train_triplets.parquet')
    if target.exists():raise FileExistsError(target)
    pq.write_table(pa.Table.from_pylist(rows),target,compression='zstd');report['file']={'path':str(target),'rows':len(rows),'sha256':sha(target)}
    if args.calibrate:report['audit_sample']=random.Random(42).sample(rows,25)
    write(DATA/('calibration.json' if args.calibrate else 'mining.json'),report)
    if args.train:
        assert [{'question':x['question'],'positive':x['positive']} for x in rows]==pairs
        source['mining']=report;source['files']['train']=report['file']
        val=DATA/'gooaq_g3_validation_pairs.parquet';pq.write_table(pq.read_table(DATA/'gooaq_g3_pairs_validation.parquet'),val,compression='zstd')
        source['files']['validation']={'path':str(val),'rows':5000,'sha256':sha(val)}
        write(DATA/'manifest.json',source)
    print(__import__('json').dumps({k:v for k,v in report.items() if k!='audit_sample'},indent=2),flush=True)
if __name__=='__main__':main()
