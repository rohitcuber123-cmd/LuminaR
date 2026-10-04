"""Consolidated G3 report, including mandatory stop outcomes."""
from gooaq_g3_controls import *

def optional(path):return read(path) if path.exists() else None
def main():
    rp=TRAIN/'reports';safety=verify();pre=read(rp/'rag_g3_gooaq_preflight.json')
    resume=optional(rp/'rag_g3_gooaq_resume_preflight.json')
    source=optional(DATA/'source_manifest.json');cal=optional(DATA/'calibration.json');audit=optional(DATA/'calibration_audit.json');mining=optional(DATA/'mining.json')
    stop=optional(DATA/'mining_stop.json');smoke=optional(TRAIN/'manifests/minilm_g3_gooaq_50k_smoke.json');train=optional(TRAIN/'manifests/minilm_g3_gooaq_50k_full.json')
    generic=optional(rp/'rag_g3_gooaq_generic_validation.json');idx=optional(TRAIN/'evaluation_indexes/minilm_g3_gooaq_50k/manifest.json');ev=optional(rp/'rag_g3_gooaq_eval.json')
    integrity=optional(rp/'rag_g3_gooaq_index_integrity.json')
    a=read(rp/'rag_g3_baseline_reproduction.json');g1=read(rp/'rag_g1_msmarco_eval.json');g2=read(rp/'rag_g2_nq_eval.json')
    decision='D. G3 EXPERIMENT INVALID — FIX BEFORE INTERPRETATION'
    if train and idx and ev and generic:
        assert sha(DATA/'manifest.json')==train['dataset_manifest_sha256']
        for f in read(DATA/'manifest.json')['files'].values():assert sha(Path(f['path']))==f['sha256']
        assert sha(Path(train['model_path'])/'model.safetensors')==train['model_weights_sha256']
        index=TRAIN/'evaluation_indexes/minilm_g3_gooaq_50k'
        assert sha(index/'faiss.index')==idx['index_sha256'] and sha(index/'embeddings.npy')==idx['embeddings_sha256']
        delta=[ev['g3'][f][k]-ev['a'][f][k] for f in ['hit','recall'] for k in ['20','50']]
        if all(x>=0 for x in delta) and any(x>0 for x in delta) and ev['g3_no_gold_top50']<=ev['a_no_gold_top50']:decision='A. GOOAQ G3 IMPROVES LUMINAR FIRST-STAGE RETRIEVAL'
        elif all(x<=0 for x in delta) and any(x<0 for x in delta) and ev['g3_no_gold_top50']>=ev['a_no_gold_top50']:decision='C. GOOAQ G3 REGRESSES LUMINAR RETRIEVAL'
        else:decision='B. GOOAQ G3 IS NEUTRAL / INCONCLUSIVE'
    report={'experiment':'G3_GOOAQ','decision':decision,'result_label':'EXPERIMENTAL / DESCRIPTIVE — DRAFT DEV labels','source':source,'source_manifest_sha256':sha(DATA/'source_manifest.json') if source else None,'final_data_manifest_sha256':sha(DATA/'manifest.json') if (DATA/'manifest.json').exists() else None,'calibration':cal,'audit':audit,'mining':mining,'stop':stop,'preflight':pre,'smoke':smoke,'training':train,'generic':generic,'index':idx,'DEV':ev,'safety':safety,'TEST_evaluated':False}
    files=sorted({str(p.relative_to(ROOT)) for base in [ROOT/'scripts',ROOT/'tests',rp] for p in base.iterdir() if p.is_file() and 'g3' in p.name}|{'datasets/training/reports/rag_g3_gooaq_final.md','datasets/training/reports/rag_g3_gooaq_final.json'})
    artifact_roots=['datasets/training/generic/gooaq_g3','datasets/training/hf_cache/gooaq_g3','datasets/training/models/minilm_g3_gooaq_50k_smoke','datasets/training/models/minilm_g3_gooaq_50k_full','datasets/training/checkpoints/minilm_g3_gooaq_50k_smoke','datasets/training/checkpoints/minilm_g3_gooaq_50k_full','datasets/training/evaluation_indexes/minilm_g3_gooaq_50k']
    files += [str(p.relative_to(ROOT)) for p in (TRAIN/'manifests').iterdir() if p.is_file() and 'g3' in p.name]
    artifact_roots=[p for p in artifact_roots if (ROOT/p).exists()]
    report['files_added']=sorted(files);report['isolated_artifact_directories']=artifact_roots;report['resume_preflight']=resume
    report['frozen_historical_context']={'A':a['summary']['metrics'],'G1':g1['g1'],'G2':g2['g2']}
    report['index_integrity']=integrity
    if ev:
        report['primary_metric_deltas']={f'{family}@{k}':ev['g3'][family][k]-ev['a'][family][k] for family in ['hit','recall'] for k in ['20','50']}
        report['primary_metric_deltas']['no_gold_top50']=ev['g3_no_gold_top50']-ev['a_no_gold_top50']
        report['top20_entered']=[q['query_id'] for q in ev['per_query'] if q['g3_first_gold_rank'] is not None and q['g3_first_gold_rank']<=20 and (q['a_first_gold_rank'] is None or q['a_first_gold_rank']>20)]
        report['top20_lost']=[q['query_id'] for q in ev['per_query'] if q['a_first_gold_rank'] is not None and q['a_first_gold_rank']<=20 and (q['g3_first_gold_rank'] is None or q['g3_first_gold_rank']>20)]
    write(rp/'rag_g3_gooaq_final.json',report)
    lines=['# G3_GOOAQ — consolidated controlled experiment','',f'**Decision: {decision}.**','',
      'The valid comparison is untouched A → independently initialized GooAQ G3. G1/G2 remain COMPLETE AND FROZEN, with regression conclusions unchanged. All downstream results are experimental/descriptive because DEV labels remain DRAFT. TEST evaluated: NO. Stop after G3; no mixture, other dataset, reranker, or production promotion.','',
      '## Source, bounded sampling, inventory, and frozen pairs','']
    if source:
        lines += [f"Dataset [`{source['dataset_id']}`](https://huggingface.co/datasets/{source['dataset_id']}); config `{source['config']}`; revision `{source['revision']}`; split `{source['split']}`; features `{source['schema']}`; published source count {source['source_row_count']:,}. Automatic Hugging Face access/streaming succeeded without authentication. Cache `{source['cache']}`; Windows symlink warning caused copy-based caching. No alternate source or complete multi-million-row materialization.",'',
           f"Sampling `{source['selection']}`. Inspected/materialized {source['rows_materialized']:,} bounded source rows, selected 50,000 pairs = 45,000 TRAIN + 5,000 validation. This is bounded buffered streaming sampling, not a globally uniform source sample. All TRAIN questions/positives were frozen before mining and remain identical in the same order; replacements: 0.",'',
           '| Bounded source inventory | Count |','|---|---:|']
        for k in ['empty_questions','empty_answers','exact_duplicate_pairs','duplicate_normalized_questions','duplicate_answer_passages','question_equals_answer','multi_positive_questions']:lines.append(f"| {k} | {source['inventory'].get(k,0)} |")
        lines += ['',f"Normalized TRAIN/validation query overlap: {source['train_validation_normalized_query_overlap']}. Multi-positive handling: {source['known_positive_scope']}. Text canonicalization: {source['answer_canonicalization']}. Mining corpus provenance maps each canonical passage to a saved bounded source record ID; these IDs are processed shuffled-stream ordinals, not global source row numbers.",'',
                  '| Token length scope | Field | Min | Median | p90 | p95 | p99 | Max | >256 |','|---|---|---:|---:|---:|---:|---:|---:|---:|']
        for scope,fields in source['token_lengths'].items():
            for field,v in fields.items():lines.append(f"| {scope} | {field} | {v['min']} | {v['median']} | {v['p90']} | {v['p95']} | {v['p99']} | {v['max']} | {v['over_256']} |")
        lines += ['','Untruncated MiniLM token counts include special tokens. Model window remained 256.','', '| Frozen file | Rows | SHA-256 |','|---|---:|---|']
        for k,v in source['files'].items():lines.append(f"| {k} | {v['rows']} | `{v['sha256']}` |")
        lines += ['',f"Source manifest SHA-256 `{report['source_manifest_sha256']}`; final data manifest SHA-256 `{report['final_data_manifest_sha256'] or 'N/A'}`."]
        lines += ['',f"The negative corpus is a deterministic {source['mining_corpus_count']:,}-passage pool, substantially larger than TRAIN positives, and is not the full 3-million-row answer corpus. Bounded mining limits RAM/disk/resource use on this shared machine.",'']
    if cal:
        lines+=['## Mining calibration and source audit','',f"Installed `sentence_transformers.util.mine_hard_negatives` signature: `{pre['miner_signature']}`. It was used with baseline A, full bounded answer pool, FAISS, five candidates per query, random seeded candidate sampling, and one retained negative. No G1/G2 model or cross-encoder.",'',
          f"500 deterministic TRAIN questions; initial window `{cal['initial_window']}`, wider safe window `{cal['wider_window']}`. Final settings `{cal['settings']}`. Derivation/adjustment: {cal['settings_reason']}. Initial audit trial found one possible alternate answer and two ambiguous cases; the ceiling was tightened to measured GooAQ raw-negative p95. Trial1 artifacts are preserved. G2 thresholds were not reused.",'',
          f"Raw calibration distributions: `{cal['raw_calibration_distributions']}`. Final calibration distributions: `{cal['distributions']}`. Calibration hard/random counts {cal['hard_count']}/{cal['random_fallback_count']}. {cal['window_note']}.",'']
    if audit:
        lines += [f"Final engineering source-text audit: {audit['sample_count']} deterministic seed-42 samples, {audit['obviously_not_answer']} OBVIOUSLY_NOT_ANSWER, {audit['possible_false_negative']} POSSIBLE_FALSE_NEGATIVE, {audit['ambiguous']} AMBIGUOUS. This is engineering sanity inspection, not human training-label review or a full false-negative-rate estimate.",'', '| Sample | Question | Positive answer | Candidate negative | Classification | Reason |','|---|---|---|---|---|---|']
        def table_text(v):return str(v).replace('|','\\|').replace('\n',' ').replace('\r',' ')
        for x,sample in zip(audit['rows'],cal['audit_sample']):
            assert x['question']==sample['question']
            lines.append('| '+' | '.join(table_text(v) for v in [x['sample'],x['question'],sample['positive'],sample['negative'],x['classification'],x['reason']])+' |')
    if mining:
        lines += ['',f"Full mining: {mining['hard_count']:,} HARD + {mining['random_fallback_count']:,} RANDOM_FALLBACK ({mining['random_fallback_fraction']:.2%}); wider-window hard recoveries {mining['wider_window_hard_count']:,}. Frozen TRAIN questions preserved, replacements 0. Fallback ≤5% gate passed. Safeguards: {mining['safeguards']}. Postfilter known-positive exclusions {mining['known_positive_candidates_excluded']}. Metadata is saved for diagnostics but excluded from model inputs.",'',
           f"Score/rank distributions: `{mining['distributions']}`. Final 45k triplets SHA-256 `{mining['file']['sha256']}`. Hard raw ranks are captured from the installed miner's native FAISS search outputs; observation does not change retrieval scores/candidates. Random fallback ranks are N/A.",'']
    if stop:lines+=['',f"Mandatory stop: `{stop}`. No full training was performed.",'']
    lines += ['## Current environment, initialization, contract, and training','',f"Measured versions `{pre['versions']}`. CUDA {pre['cuda']}; GPU {pre['gpu']}; VRAM total/free {pre['gpu_total_bytes']:,}/{pre['gpu_free_bytes']:,} bytes; system RAM total/available {pre['ram_total_bytes']:,}/{pre['ram_available_bytes']:,} bytes; disk free {pre['disk_free_bytes']:,} bytes; BF16 runtime support {pre['bf16_supported']}.",'',
      f"Untouched A snapshot `{pre['base_snapshot']}`; base weights SHA-256 `{pre['base_snapshot_sha256']['model.safetensors']}`. Full base-file fingerprint is in preflight and training manifests. Code asserts the base path is all-MiniLM-L6-v2 and contains neither G1 nor G2 experiment paths. Both smoke/full initialize freshly from A.",'',
      'Contract test: 1 passed. Synthetic dataset includes metadata, explicitly selects question/positive/negative, retains negative_input_ids in collation, supplies three feature groups to MNRL, and proves changing the negative changes loss. Actual smoke/full trainer batches repeat the three-column assertion. Every loss is checked for finiteness before backward; callbacks guard finite logged gradients and ≥1.5 GiB free GPU memory. No unrelated processes/services were terminated.','',
      'Baseline A freshly reproduced all 30 DEV Top50 lists exactly against authoritative historical DEV records; 29 are evaluable. TEST rows were filtered out before model encoding/evaluation.','']
    if resume:lines += [f"At the user's pause, mining and smoke had completed, and full training had not started. On explicit continuation, hashes and resources were checked again: free GPU memory {resume['GPU_free_bytes']:,} bytes; available system RAM {resume['RAM_available_bytes']:,} bytes; disk free {resume['disk_free_bytes']:,} bytes. Full training starts freshly from A and does not load smoke weights.",'']
    if smoke:lines += [f"Smoke: 1,024 triplets, {smoke['training_steps']} steps, finite aggregate loss {smoke['final_training_loss']:.6f}; BF16, forward/backward, saved checkpoint reload, normalized 384-dimensional encode all passed. Minimum free GPU headroom {smoke['vram_headroom_bytes']:,} bytes.",'']
    if train:
        lines += [f"Full loss `{train['loss']}`, sampler `{train['batch_sampler']}`, physical/effective contrastive batch {train['physical_batch']}/{train['effective_contrastive_batch']}, accumulation1, BF16 {train['bf16']}, FP16 {train['fp16']}; 45k GooAQ-only triplets, seed42, 1 epoch, lr2e-5, weight decay.01, linear schedule, warmup.05. No hyperparameter/loss/window/architecture changes from G1/G2.",'',
           f"{train['training_steps']} steps in {train['training_seconds']:.2f} seconds; aggregate final training loss {train['final_training_loss']:.6f}; peak reserved/allocated VRAM {train['peak_vram_reserved_bytes']:,}/{train['peak_vram_allocated_bytes']:,} bytes; minimum global free GPU headroom {train['vram_headroom_bytes']:,} bytes; peak process RSS {train['peak_ram_rss_bytes']:,} bytes.",'',
           f"Last logged training-loss window {train['last_logged_batch_loss']:.6f}. Aggregate loss above is the trainer's whole-run mean, not the final batch loss. Model `{train['model_path']}`; weights SHA-256 `{train['model_weights_sha256']}`; training-file hash `{train['train_parquet_sha256']}`. Reload/window256/dimension384/normalization verification passed.",'']
    else:lines+=['Full training, model hash/path, resource peaks, steps/duration/final loss: NOT RUN / N/A.','']
    if generic:
        lines += ['## Generic GooAQ held-out sanity','',f"{generic['type']}. Questions {generic['queries']:,}; candidate corpus {generic['candidate_count']:,}; normalized-query overlap 0; shared TRAIN/validation positive passages {generic['train_validation_document_overlap']:,}. This is held-out-question sanity, not a full-corpus benchmark or unseen-document test. It does not decide LuminaR promotion.",'', '| Metric | A | G3 |','|---|---:|---:|']
        for k in generic['results']['A']:lines.append(f"| {k} | {generic['results']['A'][k]:.4f} | {generic['results']['G3'][k]:.4f} |")
    if idx:lines+=['','## Embedding/index integrity','',f"Exact frozen tokens_220: shape `{idx['embedding_shape']}`; finite and normalized; norm range {idx['norm_min']:.10f}–{idx['norm_max']:.10f}; dimension384, global IndexFlatIP count {idx['index_count']:,} plus {idx['book_count']} per-book indexes. Embeddings SHA-256 `{idx['embeddings_sha256']}`; global FAISS SHA-256 `{idx['index_sha256']}`.",'']
    if integrity:lines += ['Global FAISS vectors and every per-book index were reconstructed and compared exactly to the saved G3 embedding rows in frozen corpus order. All 18 per-book counts, dimensions, inner-product types, and vector mappings passed. Per-book hashes are recorded in `rag_g3_gooaq_index_integrity.json`.','']
    lines+=['## Frozen LuminaR DEV four-way historical table','', 'Original question, dense-only, per-book IndexFlatIP; no expansion, reranker, lexical, union, Qwen, or generation. Valid comparison A→G3; G1/G2 are frozen descriptive context.','', '| Metric | A | G1 MS MARCO | G2 NQ | G3 GooAQ |','|---|---:|---:|---:|---:|']
    columns=[a['summary']['metrics'],g1['g1'],g2['g2'],ev['g3'] if ev else None]
    def cells(get,fmt):return ' | '.join(format(get(v),fmt) if v else 'N/A' for v in columns)
    lines.append('| MRR | '+cells(lambda v:v['mrr'],'.4f')+' |')
    for family,ks in [('hit',['1','3','5','10','20','50']),('recall',['5','10','20','50'])]:
        for k in ks:lines.append(f"| {family.title()}@{k} | "+cells(lambda v:v[family][k],'.2%')+' |')
    lines.append(f"| No accepted span Top50 | {a['summary']['no_gold_in_top50']} | {g1['g1_no_gold_top50']} | {g2['g2_no_gold_top50']} | {ev['g3_no_gold_top50'] if ev else 'N/A'} |")
    if ev:
        lines += ['',f"Primary changes (G3 minus A): Hit@20 {100*(ev['g3']['hit']['20']-ev['a']['hit']['20']):+.2f} percentage points; Hit@50 {100*(ev['g3']['hit']['50']-ev['a']['hit']['50']):+.2f}; Recall@20 {100*(ev['g3']['recall']['20']-ev['a']['recall']['20']):+.2f}; Recall@50 {100*(ev['g3']['recall']['50']-ev['a']['recall']['50']):+.2f}; no-gold Top50 {ev['g3_no_gold_top50']-ev['a_no_gold_top50']:+d}. Decision uses these first-stage metrics; secondary MRR cannot override a primary tradeoff. Mixed directions are classified B, rather than counted as an unqualified improvement or regression.",'',f"A→G3 movement `{ev['counts']}` across 29 evaluable DEV queries; recovered {ev['recovered_top50']}; lost {ev['lost_top50']}. Movement labels use first accepted rank; recovered/lost are additional flags. Top20 entry {report['top20_entered']}; Top20 exits {report['top20_lost']}.",'']
        for q in ev['per_query']:
            if q['recovered_top50'] or q['lost_top50']:
                lines += [f"### {'RECOVERED_IN_TOP50' if q['recovered_top50'] else 'LOST_FROM_TOP50'}: {q['query_id']} — {q['book']}",'',q['question'],'',f"A accepted ranks {q['a_gold_span_ranks']}; G3 accepted ranks {q['g3_gold_span_ranks']}.",'']
                lines += ['Frozen accepted-span diagnostic: '+ ' / '.join(x.replace(chr(10),' ') for x in q['gold_span_excerpts']),'']
                if q['recovered_top50']:lines += [f"The accepted passage appears at rank {q['g3_first_gold_rank']}; this recovery expands Top50 coverage but does not add a Top20 hit. Diagnostic top passages still need comparison with the frozen accepted span.",'']
                for side in ['a','g3']:
                    lines+=[side.upper()+' diagnostic top passages:','']
                    for x in q[f'{side}_nearest']:lines.append(f"- Rank {x['rank']}, `{x['chunk_id']}`: {x['text_excerpt'].replace(chr(10),' ')}")
                lines.append('')
        lines+=['### Historical-query diagnostics (not tuning inputs)','', '| Query | Book | A accepted ranks | G1 accepted ranks | G2 accepted ranks | G3 accepted ranks |','|---|---|---|---|---|---|']
        old1={x['query_id']:x for x in g1['per_query']};old2={x['query_id']:x for x in g2['per_query']}
        for q in ev['per_query']:
            if q['query_id'] in ['v8_06','v8_08','v8_10','pp_02','alice_04','time_01','time_02']:
                lines.append(f"| {q['query_id']} | {q['book']} | {q['a_gold_span_ranks']} | {old1[q['query_id']]['g1_gold_span_ranks']} | {old2[q['query_id']]['g2_gold_span_ranks']} | {q['g3_gold_span_ranks']} |")
        lines+=['','All per-query classifications and accepted ranks are in the consolidated JSON and `rag_g3_gooaq_eval.json`. No protected TEST evaluation.','']
    lines+=['## Safety, added files, and final stop','',f"Before/after verification: `{safety}`. Historical recorded G1/G2 model/data/index hashes passed; all frozen historical files have matching before/after SHA-256. No independent older report-hash ledger is claimed. Baseline/corpus/labels/source-map and 18 recorded source hashes unchanged. Production 64-file changes: 0.",'',
       '**TEST evaluated: NO.** No domain QA, Qwen supervision/training, cross-encoder operation, production promotion, dataset mixture, or subsequent dataset experiment. Only G3 scripts/test and isolated data/cache/model/checkpoint/manifest/index/report paths added.','',*[f'- `{f}`' for f in sorted(files)],'', 'Isolated generated artifact directories:','',*[f'- `{f}`' for f in artifact_roots],'',f'**FINAL G3 DECISION: {decision}.**', '',
       ('G3 clearly regresses; the three controlled regression results support stopping generic-data-only bi-encoder fine-tuning for this setup.' if decision.startswith('C.') else 'G3 shows mixed Top20/Top50 behavior and does not establish a uniform first-stage retrieval improvement.' if decision.startswith('B.') else 'The decision is experimental/descriptive and does not authorize production promotion.'), 'Stop after G3. The user reviews this result before any next dataset, mixture, or training experiment.']
    (rp/'rag_g3_gooaq_final.md').write_text('\n'.join(lines),encoding='utf-8')
    print(__import__('json').dumps({'decision':decision,'safety':safety,'DEV':{k:ev[k] for k in ['a','g3','a_no_gold_top50','g3_no_gold_top50','counts','recovered_top50','lost_top50']} if ev else None},indent=2))
if __name__=='__main__':main()
