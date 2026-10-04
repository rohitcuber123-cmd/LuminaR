"""Predefined original-query G3 candidate-K sweep; no expansion or training."""
import argparse
import time
from pathlib import Path
from r0i_common import *


def main():
    p=argparse.ArgumentParser();p.add_argument('--retriever',required=True,choices=['g3'])
    p.add_argument('--candidate-k',required=True,choices=['20,30,40,50,60,80'])
    p.add_argument('--cross-encoder',required=True,choices=[MODEL_ID])
    p.add_argument('--raw-cross-encoder-only',required=True,action='store_true');p.add_argument('--split',required=True,choices=['dev'])
    p.parse_args()
    for path in [RAW,OUT,SCORES,REPORTS/'rag_r0i_preflight.json']:
        if path.exists():raise FileExistsError(f'R0I artifact exists; inspect before rerun: {path}')
    ledger,r0=freeze()
    write(REPORTS/'rag_r0i_preflight.json',{'before_sha256':ledger,'predefined_K':KS,'selection_policy':POLICY,
          'temporary_union_budget':'provisional K + up to 20 first-seen unique expansion additions; preserve every original dense TopK candidate',
          'CE_batch_size':16,'warmup_pairs':16,'TEST_evaluated':False})
    rt=Runtime(r0);top80,reproduction=reproduce(rt,r0);rt.warm(top80)
    results=[];allrows=[]
    for k in KS:
        with Memory(rt.torch,rt.psutil) as memory:
            rt.torch.cuda.synchronize();start=time.perf_counter()
            pools={q['query_id']:rt.retrieve(q,k) for q in rt.evaluable}
            rt.torch.cuda.synchronize();retrieval=time.perf_counter()-start
            for qid,rows in pools.items():
                assert [c['chunk_id'] for c in rows]==[c['chunk_id'] for c in top80[qid][:k]]
            result,rows=evaluate_pool(rt,pools,k,f'G3 raw K{k}',retrieval,start)
        result['memory']=memory.result;results.append(result);allrows.extend(rows)
        print(__import__('json').dumps({'K':k,'covered':result['candidate_metrics']['covered_queries'],
              'candidate_Recall':result['candidate_metrics']['candidate_Recall'],'MRR':result['CE_metrics']['mrr'],
              'Hit10':result['CE_metrics']['hit']['10'],'Hit20':result['CE_metrics']['hit']['20'],
              'timing':result['timing'],'memory':result['memory']}),flush=True)
    k50=next(r for r in results if r['k']==50)
    assert k50['CE_metrics']['mrr']==r0['systems']['G3+CE']['metrics']['mrr']
    for family in ['hit','recall']:
        for depth,value in k50['CE_metrics'][family].items():assert value==r0['systems']['G3+CE']['metrics'][family][depth]
    import pyarrow as pa
    import pyarrow.parquet as pq
    old=pq.read_table(TRAIN/'evaluation/rag_r0_crossencoder_scores.parquet').to_pylist()
    oldrank={q['query_id']:[] for q in rt.evaluable}
    for x in sorted(old,key=lambda x:x['ce_rank']):
        if x['retriever']=='G3':oldrank[x['query_id']].append(x['chunk_id'])
    assert all([c['chunk_id'] for c in k50['ranked_candidates'][q]]==ids for q,ids in oldrank.items())
    oldscore={(x['query_id'],x['chunk_id']):x['ce_score'] for x in old if x['retriever']=='G3'}
    max_score_delta=max(abs(c['ce_score']-oldscore[(q,c['chunk_id'])]) for q,rows in k50['ranked_candidates'].items() for c in rows)
    chosen=select_k(results)
    bands=[]
    for a,b in zip(results,results[1:]):
        da,db=a['candidate_metrics'],b['candidate_metrics'];ca,cb=a['CE_metrics'],b['CE_metrics']
        recovered=[qid for qid,m in da['per_query'].items() if m['first_rank'] is None and db['per_query'][qid]['first_rank'] is not None]
        details=[{'query_id':qid,'book':rt.books[next(q['work_id'] for q in rt.evaluable if q['query_id']==qid)]['title'],
                  'accepted_dense_rank':db['per_query'][qid]['first_rank'],'CE_rank':cb['per_query'][qid]['first_rank']} for qid in recovered]
        bands.append({'from':a['k'],'to':b['k'],'additional_covered_queries':db['covered_queries']-da['covered_queries'],
                      'additional_accepted_spans':db['admitted_spans']-da['admitted_spans'],
                      'candidate_Recall_gain':db['candidate_Recall']-da['candidate_Recall'],
                      'CE_Hit20_change':cb['hit']['20']-ca['hit']['20'],
                      'latency_ms_per_query_increase':b['timing']['average_retrieval_plus_CE_ms_per_query']-a['timing']['average_retrieval_plus_CE_ms_per_query'],
                      'newly_covered_queries':details})
    tracking={}
    for qid in ['v8_06','pp_05','v8_08','pp_02','time_01']:
        tracking[qid]=[{'K':r['k'],'accepted_present':r['candidate_metrics']['per_query'][qid]['first_rank'] is not None,
                        'dense_accepted_rank':r['candidate_metrics']['per_query'][qid]['first_rank'],
                        'CE_accepted_rank':r['CE_metrics']['per_query'][qid]['first_rank']} for r in results]
    raw_path=TRAIN/'evaluation/rag_r0i_raw_k_scores.parquet'
    raw_path.parent.mkdir(parents=True,exist_ok=True);pq.write_table(pa.Table.from_pylist(allrows),raw_path,compression='zstd')
    write_scores(allrows)
    report={'experiment':'R0I','phase':'raw predefined K sweep COMPLETE','result_label':'EXPERIMENTAL / DESCRIPTIVE — DRAFT DEV labels',
            'freeze':verify_ledger(ledger),'G3':rt.g3_info,'CE':rt.ce_info,'environment':rt.environment,'reproduction':reproduction,
            'predefined_K':list(KS),'selection_policy':POLICY,'provisional_K':chosen,'results':results,'incremental_bands':bands,
            'critical_query_tracking':tracking,'historical_R0_systems':r0['systems'],
            'R0_K50_CE_ranks_and_metrics_reproduced':True,'R0_K50_max_CE_score_absolute_delta':max_score_delta,
            'warmup_pairs':16,'batch_size':16,'raw_score_path':str(raw_path),'raw_score_sha256':sha(raw_path),
            'total_raw_score_rows':len(allrows),'TEST_evaluated':False,'training_performed':False,'downloads_performed':False,
            'retrieval_encoded_queries':rt.encoded,'stop_after':'R0I'}
    write(RAW,report)
    print('RAW SWEEP COMPLETE; provisional K=',chosen,flush=True)


if __name__=='__main__':main()
