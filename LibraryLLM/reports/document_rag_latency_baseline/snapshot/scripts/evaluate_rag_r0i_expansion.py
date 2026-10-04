"""Audit unchanged production query/merge logic with isolated G3 and raw CE."""
import argparse
import ast
import copy
from functools import lru_cache
import time
from r0i_common import *


@lru_cache(maxsize=1)
def existing_builder():
    """Execute the actual pre-CE production AST; only expose its final cap as a budget."""
    source=(ROOT/'rag/reranker.py').read_text(encoding='utf-8')
    tree=ast.parse(source)
    per_branch=next(n.value.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CANDIDATE_K' for t in n.targets))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='RAGReranker')
    fn=copy.deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='search'))
    cut=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.If) and isinstance(n.test,ast.UnaryOp)
             and isinstance(n.test.op,ast.Not) and isinstance(n.test.operand,ast.Name) and n.test.operand.id=='candidates')
    fn.body=fn.body[:cut];fn.name='existing_candidate_prefix';fn.decorator_list=[]
    cap=next(n for n in fn.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MAX_MULTIQ_CANDIDATES' for t in n.targets))
    literal_cap=cap.value.value
    assert per_branch==15 and literal_cap==40
    cap.value=ast.Name(id='final_budget',ctx=ast.Load())
    fn.args.kwonlyargs.append(ast.arg(arg='final_budget'));fn.args.kw_defaults.append(ast.Constant(value=literal_cap))
    fn.body.append(ast.parse("return {'candidates':candidates,'uncapped_candidates':list(best_scores.values()),'retrieval_queries':retrieval_queries}").body[0])
    from rag.evidence import generate_expanded_queries
    final_k=next(n.value.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FINAL_K' for t in n.targets))
    namespace={'time':time,'CANDIDATE_K':per_branch,'FINAL_K':final_k,'generate_expanded_queries':generate_expanded_queries}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),str(ROOT/'rag/reranker.py'),'exec'),namespace)
    return namespace[fn.name],{'source_path':str(ROOT/'rag/reranker.py'),'source_sha256':sha(ROOT/'rag/reranker.py'),
                               'evidence_source_sha256':sha(ROOT/'rag/evidence.py'),'per_branch_depth':15,'production_literal_cap':40,
                               'only_controlled_override':'MAX_MULTIQ_CANDIDATES = frozen provisional K; no other generation changes',
                               'merge':'actual production AST: first-seen chunk dedupe, original query first, no sorting by dense score',
                               'hash_seed':os.environ.get('PYTHONHASHSEED'),'generation_note':'existing family set iteration is process-hash-seed dependent; freeze seed42 and record all generated strings'}


def generation(rt,q,k):
    class Retriever:
        def search(self,query,top_k,document_id=None,work_id=None):
            assert work_id==q['work_id'] and top_k==15
            rows=rt.retrieve(q,top_k,text=query)
            return {'results':[{**c,'text':rt.chunks[c['chunk_id']]['text']} for c in rows],'timing_ms':{}}
    class Instance:retriever=Retriever()
    fn,policy=existing_builder()
    result=fn(Instance(),q['question'],work_id=q['work_id'],final_budget=k)
    for c in result['uncapped_candidates']:
        assert c['text']==rt.chunks[c['chunk_id']]['text']
    return result,policy


def main():
    p=argparse.ArgumentParser();p.add_argument('--retriever',required=True,choices=['g3'])
    p.add_argument('--use-provisional-k',required=True,action='store_true')
    p.add_argument('--compare',required=True,choices=['original,existing-expansion,dense-preserving-union'])
    p.add_argument('--raw-cross-encoder-only',required=True,action='store_true');p.add_argument('--split',required=True,choices=['dev'])
    p.parse_args()
    if OUT.exists():raise FileExistsError('Final R0I report already exists; inspect before rerun')
    assert os.environ.get('PYTHONHASHSEED')=='42','Launch expansion with PYTHONHASHSEED=42'
    raw=read(RAW);raw_sha=sha(RAW);ledger=read(REPORTS/'rag_r0i_preflight.json')['before_sha256']
    verify_ledger(ledger)
    assert raw['phase']=='raw predefined K sweep COMPLETE' and raw['predefined_K']==list(KS)
    assert sha(raw['raw_score_path'])==raw['raw_score_sha256']
    r0=read(REPORTS/'rag_r0_existing_crossencoder.json');rt=Runtime(r0)
    top80,reproduction=reproduce(rt,r0);rt.warm(top80)
    k=raw['provisional_K'];assert k==select_k(raw['results'])
    results=[];losses=[];all_info={};newrows=[]
    original_rank={qid:{c['chunk_id']:c['rank'] for c in rows} for qid,rows in top80.items()}
    for system in ['original','existing-expansion','dense-preserving-union']:
        with Memory(rt.torch,rt.psutil) as memory:
            rt.torch.cuda.synchronize();start=time.perf_counter();pools={};info={}
            for q in rt.evaluable:
                qid=q['query_id']
                dense=rt.retrieve(q,k) if system!='existing-expansion' else prefix(top80[qid],k)
                if system=='original':candidates=dense
                else:
                    gen,policy=generation(rt,q,k);info[qid]={'queries':gen['retrieval_queries'],
                      'uncapped_count':len(gen['uncapped_candidates']),'at_literal_40_count':min(40,len(gen['uncapped_candidates'])),
                      'at_budget_K_count':len(gen['candidates']),'uncapped_candidates':gen['uncapped_candidates']}
                    candidates=gen['candidates'] if system=='existing-expansion' else dense_preserving_union(dense,gen['uncapped_candidates'],20)
                    if system=='existing-expansion':
                        final_ids={c['chunk_id'] for c in candidates};uncapped={c['chunk_id']:i for i,c in enumerate(gen['uncapped_candidates'],1)}
                        for c in dense:
                            if c['chunk_id'] not in final_ids:
                                gold=any(overlaps(rt.chunks[c['chunk_id']],s) for s in q['accepted_passages'] if s['relevance_grade']==2)
                                losses.append({'query_id':qid,'book':rt.books[q['work_id']]['title'],'chunk_id':c['chunk_id'],
                                  'original_dense_rank':c['rank'],'accepted_overlapping':gold,
                                  'reason':'FINAL_BUDGET_CAP' if c['chunk_id'] in uncapped else 'NOT_IN_ANY_QUERY_VARIANT_TOP15',
                                  'uncapped_arrival_rank':uncapped.get(c['chunk_id'])})
                pools[qid]=[{**c,'rank':i,'original_dense_rank':original_rank[qid].get(c['chunk_id'])} for i,c in enumerate(candidates,1)]
                if system=='dense-preserving-union':
                    assert {c['chunk_id'] for c in dense}.issubset({c['chunk_id'] for c in pools[qid]})
                    assert len(pools[qid])<=k+20
            rt.torch.cuda.synchronize();retrieval=time.perf_counter()-start
            result,rows=evaluate_pool(rt,pools,k,system,retrieval,start)
        result['memory']=memory.result;results.append(result);newrows.extend(rows);all_info[system]=info
        print(__import__('json').dumps({'system':system,'K':k,'covered':result['candidate_metrics']['covered_queries'],
              'candidate_Recall':result['candidate_metrics']['candidate_Recall'],'MRR':result['CE_metrics']['mrr'],
              'Hit10':result['CE_metrics']['hit']['10'],'Hit20':result['CE_metrics']['hit']['20'],
              'timing':result['timing'],'memory':result['memory']}),flush=True)
    original,expansion,union=results
    old=next(r for r in raw['results'] if r['k']==k)
    assert original['candidate_metrics']==old['candidate_metrics'] and original['CE_metrics']==old['CE_metrics']
    for qid in all_info['existing-expansion']:
        assert all_info['existing-expansion'][qid]['queries']==all_info['dense-preserving-union'][qid]['queries']
    lost_queries=[qid for qid,m in original['candidate_metrics']['per_query'].items()
                  if m['first_rank'] is not None and expansion['candidate_metrics']['per_query'][qid]['first_rank'] is None]
    label_notes=[]
    known={'pp_05':'OL66524W__tokens_220__d4ff028b2f8aa974','time_05':'OL27039837W__tokens_220__2928e5046c948f13'}
    for r in raw['results']+results:
        for qid,cid in known.items():
            found=next((c for c in r['ranked_candidates'][qid] if c['chunk_id']==cid),None)
            if found:
                q=next(q for q in rt.evaluable if q['query_id']==qid)
                assert not any(overlaps(rt.chunks[cid],s) for s in q['accepted_passages'] if s['relevance_grade']==2)
                label_notes.append({'system':r['system'],'query_id':qid,'chunk_id':cid,'CE_rank':found['ce_rank'],
                  'classification':'POSSIBLE_LABEL_COVERAGE_LIMITATION','text':rt.chunks[cid]['text'],
                  'reason':'Names Wickham and Lydia and describes their elopement route; R0 source-inspected answer evidence outside accepted-span coverage.' if qid=='pp_05' else 'Explicitly describes the same red sun and red-hot dome in the far future; R0 source-inspected answer evidence outside accepted-span coverage.'})
    decision=('D. CURRENT EXPANSION/CAPPING DESTROYS USEFUL G3 CANDIDATES — FIX CANDIDATE CONSTRUCTION BEFORE INTEGRATION'
              if lost_queries else {50:'A. G3 + EXISTING CE INTEGRATION IS VIABLE WITH K50',
                                    60:'B. G3 + EXISTING CE BENEFITS FROM K60',80:'C. G3 + EXISTING CE BENEFITS FROM K80'}.get(k,'F. R0I INCONCLUSIVE'))
    import pyarrow.parquet as pq
    rawrows=pq.read_table(raw['raw_score_path']).to_pylist();write_scores(rawrows+newrows)
    assert sha(RAW)==raw_sha and sha(raw['raw_score_path'])==raw['raw_score_sha256']
    report={'experiment':'R0I','decision':decision,'raw_sweep':raw,'expansion_phase':{'frozen_budget_K':k,
               'union_temporary_max_budget':k+20,'policy':policy,'results':results,'generation_details':all_info,
               'original_queries_losing_all_accepted_candidates':lost_queries,'candidate_losses':losses,
               'loss_reason_counts':dict(Counter(c['reason'] for c in losses))},
            'possible_label_coverage_limitations':label_notes,'label_diagnostic_instance_count':len(label_notes),
            'label_diagnostic_unique_queries':sorted({n['query_id'] for n in label_notes}),
            'safety':verify_ledger(ledger),'score_parquet_sha256':sha(SCORES),'score_rows':len(rawrows)+len(newrows),
            'TEST_evaluated':False,'training_performed':False,'downloads_performed':False,
            'expansion_retrieval_encoded_queries':rt.encoded,'raw_phase_unchanged':True,
            'artifacts_added':['scripts/r0i_common.py','scripts/evaluate_rag_r0i_candidate_pool.py','scripts/evaluate_rag_r0i_expansion.py',
              'tests/test_rag_r0i_candidate_pool.py','datasets/training/reports/rag_r0i_preflight.json',
              str(RAW.relative_to(ROOT)),str(OUT.relative_to(ROOT)),str(OUT.with_suffix('.md').relative_to(ROOT)),str(SCORES.relative_to(ROOT)),
              str(Path(raw['raw_score_path']).relative_to(ROOT)),'datasets/training/reports/rag_r0i_expansion_candidate_loss.json']}
    write(REPORTS/'rag_r0i_expansion_candidate_loss.json',report['expansion_phase'])
    write(OUT,report);render(report)
    print('FINAL',decision,flush=True)


def render(r):
    raw=r['raw_sweep'];phase=r['expansion_phase'];k=raw['provisional_K']
    lines=['# R0I — G3 candidate pool integration','',f"**FINAL R0I DECISION: {r['decision']}.**",'',
      'Experimental/descriptive; frozen DEV labels remain DRAFT. No training, model/dataset downloads, Qwen, learned score mixing, or production changes. TEST evaluated: NO.','',
      '## Controls and fingerprints','',f"Frozen before/after verification: `{r['safety']}`; production 64-file snapshot unchanged. G1/G2/G3/R0 and CE cache unchanged. SHA ledger in `rag_r0i_preflight.json`.",'',
      f"G3 `{raw['G3']}`; existing R0 CE `{raw['CE']}`. Current raw-phase environment `{raw['environment']}`. G3 window256/dimension384, normalized embeddings; per-book IndexFlatIP; CE512/float32, batch16, explicit Identity logits, score-descending sort with chunk-ID tie break.",'',
      f"G3 reproduction `{raw['reproduction']}`. All 30 DEV Top50 ID lists reproduced exactly; 29 evaluable queries scored. K50 CE ranks/metrics reproduce R0 exactly; max floating-score difference {raw['R0_K50_max_CE_score_absolute_delta']:.9g}. No TEST encoded. Six K values and selection rule saved before evaluation; 16 DEV-only CE warmup pairs, then actual fresh retrieval/scoring for every K without cross-K score reuse.",'',
      '## Frozen R0 context','', '| Metric | A dense | A+CE Top50 | G3 dense | G3+CE Top50 |','|---|---:|---:|---:|---:|']
    for fam,dep in [('mrr',None),('hit',5),('hit',10),('hit',20),('hit',50),('recall',50)]:
        names=['A dense','A+CE','G3 dense','G3+CE'];label='MRR' if dep is None else f'{fam.title()}@{dep}'
        vals=[raw['historical_R0_systems'][n]['metrics'][fam] if dep is None else raw['historical_R0_systems'][n]['metrics'][fam][str(dep)] for n in names]
        lines.append('| '+label+' | '+' | '.join(f'{v:.4f}' if dep is None else f'{v:.2%}' for v in vals)+' |')
    lines+=['','## Raw original-query predefined K sweep','', 'Candidate Hit/Recall use the complete TopK pool. Reranking metrics use CE order inside that same pool. Candidate membership/coverage is invariant through CE; no expansion, evidence, lexical, union or mixed scoring in this phase.','']
    md_metrics(lines,raw['results'])
    lines+=['','## Incremental candidate bands','', '| Band | Extra covered queries | Extra accepted spans | Recall gain | CE Hit20 change | Latency ms/query change |','|---|---:|---:|---:|---:|---:|']
    for b in raw['incremental_bands']:
        lines.append(f"| {b['from']}→{b['to']} | {b['additional_covered_queries']} | {b['additional_accepted_spans']} | {b['candidate_Recall_gain']:+.2%} | {b['CE_Hit20_change']:+.2%} | {b['latency_ms_per_query_increase']:+.3f} |")
    lines+=['','Newly covered queries by band:','']
    for b in raw['incremental_bands']:
        for q in b['newly_covered_queries']:lines.append(f"- {b['from']}→{b['to']}: `{q['query_id']}` ({q['book']}), dense accepted rank {q['accepted_dense_rank']}, CE rank after Top{b['to']} {q['CE_rank']}.")
    lines += ['', '| Newly admitted span band | Query | Span index | Dense rank | CE rank |', '|---|---|---:|---:|---:|']
    for a in r.get('incremental_span_admissions',[]):lines.append(f"| {a['from']}→{a['to']} | {a['query_id']} | {a['accepted_span_index']} | {a['dense_rank']} | {a['CE_rank']} |")
    lines+=['','## Critical recovery and domain-failure tracking','', '| Query | K | Accepted candidate present | Dense accepted rank | CE accepted rank |','|---|---:|---|---:|---:|']
    for qid,rows in raw['critical_query_tracking'].items():
        for q in rows:lines.append(f"| {qid} | {q['K']} | {q['accepted_present']} | {q['dense_accepted_rank']} | {q['CE_accepted_rank']} |")
    lines+=['','Candidate-absent failures and poor CE ranking are distinct. Carry-forward R0 domain failures: v8_08, pp_02, time_01; increasing K can admit evidence but cannot guarantee understanding.','',
            '## Measured latency and shared-GPU memory','', '| System | Logical pairs | Unique pairs | Actual scored | Retrieval s | CE s | Total batch s | CE ms/query | Peak allocated bytes | Peak reserved bytes | Minimum free bytes |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for a in raw['results']+phase['results']:
        t=a['timing'];m=a['memory']
        lines.append('| '+' | '.join(str(x) if not isinstance(x,float) else f'{x:.6f}' for x in [a['system'],t['logical_CE_pairs'],t['unique_CE_pairs'],t['actual_scored_CE_pairs'],t['retrieval_seconds'],t['CE_scoring_seconds'],t['total_query_batch_seconds'],t['average_CE_ms_per_query'],m['peak_allocated_VRAM_bytes'],m['peak_reserved_VRAM_bytes'],m['minimum_global_free_VRAM_bytes']])+' |')
    lines+=['',f"**Provisional raw candidate K: {k}.** Frozen selection rule: {raw['selection_policy']} All timings are actual one-pass measurements on this shared machine; small differences can contain runtime noise. Peak memory includes both resident frozen models. No unrelated GPU workloads were terminated.",'',
      '## Existing expansion construction and dense-preserving control','',f"Existing policy: `{phase['policy']}`. Execute the actual pre-CE AST from production RAGReranker.search; no production instance or composite score is run. Only its final cap is exposed as the same provisional K budget. The unchanged function uses 15 per branch and first-seen dedupe; at most three variants gives ≤45 candidates before dedupe, so the K ceiling can remain underfilled. Actual query strings/counts and literal-cap40 counts are saved in JSON. Original source text is never rewritten.",'',
      f"Union control: retain every original dense Top{k} candidate, append at most20 unique existing expansion candidates in first-seen order; temporary pool ceiling {k+20}. No original candidate is sacrificed. All three systems were separately retrieved and CE-scored to measure actual runtime.",'']
    lines += [r.get('provisional_K_reason',''),'']
    md_metrics(lines,phase['results'])
    lines += ['', '| System | Candidate count min / mean / max |', '|---|---:|']
    for a in phase['results']:
        counts=list(a['candidate_counts_by_query'].values())
        lines.append(f"| {a['system']} | {min(counts)} / {statistics.mean(counts):.2f} / {max(counts)} |")
    lines += ['', '| Critical target | System | Original dense rank | Candidate present | CE target rank |', '|---|---|---:|---|---:|']
    for x in r.get('critical_expansion_target_tracking',[]):lines.append(f"| {x['query_id']} | {x['system']} | {x['original_dense_rank']} | {x['candidate_present']} | {x['CE_rank']} |")
    lines += ['',f"Original queries losing all accepted candidates under expansion: `{phase['original_queries_losing_all_accepted_candidates']}`. Lost original dense candidate rows {len(phase['candidate_losses'])}; reason counts `{phase['loss_reason_counts']}`. Every lost ID, original dense rank, gold-overlap flag and determinable cause is in `rag_r0i_expansion_candidate_loss.json`.",'']
    for c in phase['candidate_losses']:
        if c['accepted_overlapping']:lines.append(f"- {c['query_id']} ({c['book']}): accepted-overlapping `{c['chunk_id']}`, original dense rank {c['original_dense_rank']}, loss reason {c['reason']}.")
    lines += ['',r.get('decision_reason',''),'']
    lines += ['','## Label coverage diagnostics','',f"Engineering-only POSSIBLE_LABEL_COVERAGE_LIMITATION instances: {r['label_diagnostic_instance_count']}; unique queries `{r['label_diagnostic_unique_queries']}`. Carried-forward source-inspected Wickham/Lydia and red-sun passages directly support answers but fail frozen accepted-span overlap. No label or metric was changed, and these are not counted as gold. Exact passage text and observed CE rank for each pool are in JSON.",'',
      '## Integrity and stop','',f"Tests: `{r.get('tests')}`. Final artifact checks: `{r.get('final_artifact_checks')}`.",'', f"Final candidate-score parquet: {r['score_rows']} rows, SHA-256 `{r['score_parquet_sha256']}`. Raw sweep report and raw scores remain unchanged after expansion. All historical/R0/model/label/source-map and 64 production files have zero changes. TEST evaluated: NO.",'',
      'Artifacts added:','',*[f'- `{x}`' for x in r['artifacts_added']],'',f"**FINAL R0I DECISION: {r['decision']}.**",'',
      'Stop after R0I. The provisional raw K is an engineering recommendation, not a production change. Candidate construction must preserve useful original dense evidence before integration; no composite-reranker experiment or CE fine-tuning was started.']
    OUT.with_suffix('.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':main()
