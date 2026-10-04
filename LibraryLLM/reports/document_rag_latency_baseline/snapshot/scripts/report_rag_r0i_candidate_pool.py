"""Verify and finalize saved R0I artifacts; never encode queries or score models."""
from collections import defaultdict
import pyarrow.parquet as pq
from r0i_common import *
from evaluate_rag_r0i_expansion import render


def main():
    r=read(OUT);raw=r['raw_sweep'];phase=r['expansion_phase']
    assert read(RAW)==raw and sha(raw['raw_score_path'])==raw['raw_score_sha256']
    assert sha(SCORES)==r['score_parquet_sha256']
    rows=pq.read_table(SCORES).to_pylist()
    assert len(rows)==r['score_rows']==13467
    assert {c['cross_encoder_sha256'] for c in rows}=={raw['CE']['model_weights_sha256']}
    assert {c['g3_sha256'] for c in rows}=={raw['G3']['weights_sha256']}
    chunks={c['chunk_id']:{'start':c['source_start_char'],'end':c['source_end_char'],'text':c['text'],'work_id':c['work_id']}
            for c in pq.read_table(CORPUS/'chunks.parquet',columns=['chunk_id','source_start_char','source_end_char','text','work_id']).to_pylist()}
    questions=[q for q in read(ROOT/'rag/evaluation/rag_retrieval_eval_v1.json')['questions'] if q['split']=='DEV']
    evaluable={q['query_id'] for q in dev_evaluable(questions)};allowed={q['query_id'] for q in questions}
    assert len(evaluable)==29 and {c['query_id'] for c in rows}==evaluable
    assert all(q['query_id'] in allowed for q in raw['retrieval_encoded_queries']+r['expansion_retrieval_encoded_queries'])
    grouped=defaultdict(lambda:defaultdict(list))
    for c in rows:grouped[c['system']][c['query_id']].append(c)
    allresults=raw['results']+phase['results']
    for result in allresults:
        pools={};ranked={}
        for qid,candidates in grouped[result['system']].items():
            assert len(candidates)==result['candidate_counts_by_query'][qid]
            assert len(candidates)==len({c['chunk_id'] for c in candidates})
            candidates=sorted(candidates,key=lambda c:c['input_rank'])
            assert [c['input_rank'] for c in candidates]==list(range(1,len(candidates)+1))
            pools[qid]=candidates
            ranked[qid]=sorted(candidates,key=lambda c:(-c['ce_score'],c['chunk_id']))
            assert [c['ce_rank'] for c in ranked[qid]]==list(range(1,len(candidates)+1))
            assert [c['chunk_id'] for c in ranked[qid]]==[c['chunk_id'] for c in result['ranked_candidates'][qid]]
        assert metrics(questions,pools,chunks,result['k'])==result['candidate_metrics']
        assert metrics(questions,ranked,chunks,result['k'])==result['CE_metrics']
    for qid in evaluable:
        base=sorted(grouped['G3 raw K80'][qid],key=lambda c:c['input_rank'])
        for k in KS:
            selected=sorted(grouped[f'G3 raw K{k}'][qid],key=lambda c:c['input_rank'])
            assert [c['chunk_id'] for c in selected]==[c['chunk_id'] for c in base[:k]]
        dense={c['chunk_id'] for c in grouped['original'][qid]};union={c['chunk_id'] for c in grouped['dense-preserving-union'][qid]}
        assert dense.issubset(union) and len(union)<=raw['provisional_K']+20
    saved={q['query_id']:q for q in read(TRAIN/'evaluation_indexes/minilm_g3_gooaq_50k/dense_dev_evaluation.json')['queries']}
    tracking=[]
    for qid in ['v8_06','pp_05','v8_08','pp_02','time_01']:
        first=saved[qid]['first_accepted'];cid=first['chunk_id']
        for system in ['original','existing-expansion','dense-preserving-union']:
            c=next((c for c in grouped[system][qid] if c['chunk_id']==cid),None)
            tracking.append({'query_id':qid,'system':system,'target_chunk_id':cid,'original_dense_rank':first['rank'],
                             'candidate_present':c is not None,'CE_rank':c['ce_rank'] if c else None})
    r['critical_expansion_target_tracking']=tracking
    span_admissions=[];byk={a['k']:a for a in raw['results']}
    books=read(CORPUS/'manifest.json')['books'];qmap={q['query_id']:q for q in questions}
    for lo,hi in zip(KS,KS[1:]):
        a=byk[lo];b=byk[hi]
        for qid,old in a['candidate_metrics']['per_query'].items():
            new=b['candidate_metrics']['per_query'][qid]
            for index,(before,after) in enumerate(zip(old['span_ranks'],new['span_ranks'])):
                if before is None and after is not None:
                    span_admissions.append({'from':lo,'to':hi,'query_id':qid,'book':books[qmap[qid]['work_id']]['title'],
                       'accepted_span_index':index,'dense_rank':after,'CE_rank':b['CE_metrics']['per_query'][qid]['span_ranks'][index]})
    r['incremental_span_admissions']=span_admissions
    assert len(span_admissions)==sum(b['additional_accepted_spans'] for b in raw['incremental_bands'])
    r['decision_reason']='The fixed per-variant Top15 request loses seven previously covered queries before the final cap: v8_08, v8_09, pp_02, pp_05, time_03, time_05 and war_05. At the frozen budget80 the existing expansion pools contain only16–40 candidates. No candidate is lost by a cap in this audit; all1,764 missing original dense IDs were never returned by any variant\'s Top15. v8_06 is preserved and remains CE rank1; pp_05\'s accepted target is omitted. Original/expansion/union accepted-evidence coverage is23/29,17/29,24/29; macro candidate recall74.14%,55.17%,77.59%. Expansion\'s slightly higher MRR does not outweigh lost accepted evidence. Dense-preserving union retains the complete original80 quota and restores it, while adding one covered query. These are frozen DRAFT-span metrics, not a claim that every nonaccepted passage is irrelevant.'
    r['provisional_K_reason']='K80 maximizes candidate coverage/Recall under the rule saved before the sweep (23 covered,74.14% recall). K60 is the practical quality/latency tradeoff: CE Hit20 is62.07% versus58.62% at80, and CE time105.88 versus142.82ms/query. The sole newly covered K60→80 query is time_03, whose accepted CE rank is54; v8_09 falls from CE19 atK60 to beyond20 atK80. The K80 recommendation is coverage-first and provisional, not an unqualified claim that80 gives better useful ranks than60.'
    testlog=REPORTS/'rag_r0i_contract_tests.log';assert '20 passed' in testlog.read_text(encoding='utf-8-sig')
    r['tests']={'result':'20 passed','log_sha256':sha(testlog),'path':str(testlog)}
    r['final_artifact_checks']={'score_rows_and_metrics_recomputed_from_saved_parquet':True,
       'all_K_nested_and_original_order_preserved':True,'raw_CE_sort_only':True,
       'union_preserves_every_original_dense_candidate':True,'same_G3_and_CE_fingerprint_all_systems':True,
       'TEST_never_encoded':True,'raw_phase_files_unchanged':True}
    r['safety']=verify_ledger(read(REPORTS/'rag_r0i_preflight.json')['before_sha256'])
    r['raw_report_sha256']=sha(RAW)
    r['artifacts_added']+=['scripts/report_rag_r0i_candidate_pool.py','datasets/training/reports/rag_r0i_contract_tests.log',
                          'datasets/training/reports/rag_r0i_raw_k.log','datasets/training/reports/rag_r0i_expansion.log']
    r['artifacts_added']=sorted(set(r['artifacts_added']))
    write(OUT,r);render(r)
    print(__import__('json').dumps({'decision':r['decision'],'provisional_K':raw['provisional_K'],
          'tests':r['tests'],'safety':r['safety'],'final_artifact_checks':r['final_artifact_checks']},indent=2))


if __name__=='__main__':main()
