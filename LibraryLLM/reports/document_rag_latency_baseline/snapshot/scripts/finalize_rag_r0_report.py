"""Finalize R0 using saved scores and post-scoring engineering inspection only."""
from collections import Counter
from pathlib import Path
import time

import pyarrow.parquet as pq
from evaluate_rag_r0_existing_crossencoder import (
    ROOT, TRAIN, REPORTS, CORPUS, OUT, SCORES, read, write, sha, verify_ledger,
    load_frozen_candidates, rerank_raw, analyze, initial_decision, render_report,
)


def main():
    started = time.perf_counter()
    report = read(OUT)
    from huggingface_hub import try_to_load_from_cache
    resolved_weights=try_to_load_from_cache(report['cross_encoder']['model_id'],'model.safetensors')
    assert isinstance(resolved_weights,str)
    assert Path(resolved_weights).resolve()==(Path(report['cross_encoder']['path'])/'model.safetensors').resolve()
    assert sha(resolved_weights)==report['cross_encoder']['model_weights_sha256']
    report['cross_encoder']['default_cache_resolved_weights_path']=resolved_weights
    report['cross_encoder']['matches_existing_default_local_cache']=True
    assert sha(SCORES) == report['score_parquet_sha256']
    score_rows = pq.read_table(SCORES).to_pylist()
    assert len(score_rows) == 2900
    assert {x['cross_encoder_fingerprint'] for x in score_rows} == {report['cross_encoder']['model_weights_sha256']}
    chunks = {x['chunk_id']:{'start':x['source_start_char'],'end':x['source_end_char'],
                             'work_id':x['work_id'],'text':x['text']}
              for x in pq.read_table(CORPUS/'chunks.parquet',columns=['chunk_id','work_id','text','source_start_char','source_end_char']).to_pylist()}
    questions = read(ROOT/'rag/evaluation/rag_retrieval_eval_v1.json')['questions']
    pools, reproduction = load_frozen_candidates(questions,chunks)
    assert reproduction == report['reproduction']
    lookup = {(x['retriever'],x['query_id'],x['chunk_id']):x for x in score_rows}
    assert len(lookup) == 2900
    ranked = {'A':{},'G3':{}}
    for pool in ranked:
        for qid in report['scoring']['encoded_query_ids']:
            candidates = pools[pool][qid]['top50']
            for c in candidates:
                x=lookup[(pool,qid,c['chunk_id'])]
                assert x['dense_rank']==c['rank'] and x['dense_score']==c['similarity']
                assert x['work_id']==pools[pool][qid]['work_id']
            ranked[pool][qid]=rerank_raw(candidates,[lookup[(pool,qid,c['chunk_id'])]['ce_score'] for c in candidates])
            for c in ranked[pool][qid]:assert c['ce_rank']==lookup[(pool,qid,c['chunk_id'])]['ce_rank']
    # Confirm that shared pair caching preserved identical scores across pools.
    for (pool,qid,cid),x in lookup.items():
        other=('G3' if pool=='A' else 'A',qid,cid)
        if other in lookup:assert x['ce_score']==lookup[other]['ce_score']
    analysis=analyze(questions,pools,ranked,chunks,read(CORPUS/'manifest.json')['books'])
    assert analysis['systems']==report['systems'] and analysis['per_query']==report['per_query']
    report.update(analysis)
    audit=read(REPORTS/'rag_r0_reranker_failures.json')
    reasons={
        'v8_08':('RERANKER_DOMAIN_FAILURE',
                 'Top-ranked passages describe Dracula\'s return voyage toward Galatz/Transylvania or Harker\'s coach trip, not the Demeter bringing Dracula to England. The accepted passage explicitly names Demeter, yet remains rank27; all inspected top5 fail to answer the requested voyage.'),
        'pp_02':('RERANKER_DOMAIN_FAILURE',
                 'The CE favors different dancing episodes: Sir William introduces Elizabeth, Elizabeth refuses Darcy, or Darcy invites her to a reel. These reverse the actor/event or describe another scene. The accepted tolerable-but-not-handsome-enough refusal is pushed to rank29/31.'),
        'time_01':('RERANKER_DOMAIN_FAILURE',
                   'The accepted passage spells out A.D. 802701. Top5 passages instead cover dinner, the Traveller\'s disappearance, flowers or the machine model, without the requested year. CE leaves the explicit answer at rank48 in both pools.'),
        'time_02':('AMBIGUOUS_WITH_RELEVANT_ALTERNATIVES',
                   'Rank1 dinner and rank2 character exposition do not name the Eloi friend, and the explicit her-name-was-Weena passage remains rank38. However rank3/4 passages mention Weena and her companionship; useful unaccepted evidence complicates an unqualified domain-failure claim. Kept as a poor accepted-span ranking with relevant alternatives.'),
        'time_05':('LABEL_COVERAGE_LIMITATION',
                   'The metric accepted passage remains rank13, and rank1 describes the sun turning golden during the return journey rather than the far future. But CE rank4 explicitly states the same red sun and huge red-hot dome in the far future. It fails the frozen overlap criterion while giving direct answer evidence; no labels were changed.'),
        'pp_05':('LABEL_COVERAGE_LIMITATION',
                 'The newly admitted accepted passage improves 49→12. Rank1 discusses the Lydia search without naming her companion, but rank2 explicitly names Wickham and Lydia and describes their elopement route. That rank2 passage is already in both A and G3 pools and fails the frozen overlap criterion; this is not clear evidence that CE missed the answer entirely.'),
    }
    expected={('A',q) for q in ['v8_08','pp_02','time_01','time_02','time_05']}|{('G3',q) for q in ['v8_08','pp_02','pp_05','time_01','time_02','time_05']}
    assert {(c['retriever'],c['query_id']) for c in audit['review_cases']}==expected
    notes=[]
    for case in audit['review_cases']:
        classification,reason=reasons[case['query_id']]
        note={'retriever':case['retriever'],'query_id':case['query_id'],
              'dense_rank':case['dense_accepted_rank'],'ce_rank':case['ce_accepted_rank'],
              'classification':classification,'reason':reason}
        case['engineering_inspection']=note
        notes.append(note)
    confirmed=[x for x in notes if x['classification']=='RERANKER_DOMAIN_FAILURE']
    summary={'reviewed_pool_query_instances':len(notes),'reviewed_unique_queries':len({x['query_id'] for x in notes}),
             'confirmed_domain_failure_instances':len(confirmed),
             'confirmed_unique_query_count':len({x['query_id'] for x in confirmed}),
             'confirmed_query_ids':sorted({x['query_id'] for x in confirmed}),
             'confirmed_by_pool':{s:sum(x['retriever']==s for x in confirmed) for s in ['A','G3']},
             'other_inspection_classifications':dict(Counter(x['classification'] for x in notes if x not in confirmed)),
             'conservative_definition':'Accepted first CE rank >10 plus source-confirmed wrong event/entity/context ranked substantially above it; relevant nonaccepted answer alternatives are reported separately.'}
    audit['summary']=summary;audit['status']='complete';audit['labels_modified']=False
    write(REPORTS/'rag_r0_reranker_failures.json',audit)
    report['domain_failure_audit_status']='COMPLETE — all 11 flagged pool/query instances (six unique queries) source-inspected'
    report['domain_failure_audit']=notes;report['domain_failure_summary']=summary
    report['candidate_failure_query_ids']={s:[q for q,m in report['systems'][f'{s} dense']['per_query_metrics'].items() if m['first_rank'] is None] for s in ['A','G3']}
    report['decision']=initial_decision(report)
    assert report['decision']=="A. G3'S EXTRA TOP50 COVERAGE IS USEFUL AFTER EXISTING RERANKING"
    report['decision_reason']='G3+CE exceeds A+CE on every prioritized practical metric: MRR 0.316268→0.357243, Hit@5 34.48%→41.38%, Hit@10 48.28%→51.72%, Hit@20 51.72%→58.62%. The extra v8_06 accepted candidate becomes rank1 with a positive score margin; pp_05 becomes rank12, although both pools already contain a relevant nonaccepted Wickham passage at rank2. The result supports useful candidate admission, especially v8_06, while residual CE failures and DRAFT-label coverage limit broader claims. This does not authorize automatic retraining or production changes.'
    test_log=REPORTS/'rag_r0_contract_tests.log'
    assert '19 passed' in test_log.read_text(encoding='utf-8-sig')
    report['tests']={'result':'19 passed','command':'.\\.venv\\Scripts\\python.exe -m pytest tests\\test_rag_r0_existing_crossencoder.py -q',
                     'log_path':str(test_log),'log_sha256':sha(test_log)}
    report['saved_score_validation']={'score_rows_match_saved_candidates':True,'CE_sorting_reproduced_from_saved_raw_scores':True,
                                      'same_score_for_every_shared_pair':True,'top50_invariants_passed':True}
    report['safety']=verify_ledger(read(REPORTS/'rag_r0_preflight.json')['before_sha256'])
    report['historical_verification']=read(REPORTS/'rag_r0_preflight.json')['historical_verification']
    report['artifacts_created'] += ['scripts/finalize_rag_r0_report.py','datasets/training/reports/rag_r0_reranker_failures.json',
                                    'datasets/training/reports/rag_r0_contract_tests.log','datasets/training/reports/rag_r0_existing_crossencoder.log']
    report['artifacts_created']=sorted(set(report['artifacts_created']))
    report['finalization_runtime_seconds']=time.perf_counter()-started
    write(OUT,report);render_report(report,chunks)
    print(__import__('json').dumps({'decision':report['decision'],'domain_failure_summary':summary,
                                   'safety':report['safety'],'tests':report['tests']},indent=2))


if __name__=='__main__':main()
