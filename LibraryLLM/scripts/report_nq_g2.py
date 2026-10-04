"""Consolidate executed G2 artifacts and frozen historical G1 context."""
import json
from pathlib import Path
from nq_g2_controls import ROOT, TRAIN, verify, sha

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    safety=verify();rp=TRAIN/'reports';data=TRAIN/'generic/nq_g2'
    d=read(data/'manifest.json');cal=read(data/'calibration.json');audit=read(data/'calibration_audit.json')
    pre=read(rp/'rag_g2_nq_preflight.json');smoke=read(TRAIN/'manifests/minilm_g2_nq_50k_smoke.json');train=read(TRAIN/'manifests/minilm_g2_nq_50k_full.json')
    idx=read(TRAIN/'evaluation_indexes/minilm_g2_nq_50k/manifest.json');ev=read(rp/'rag_g2_nq_eval.json');g1=read(rp/'rag_g1_msmarco_eval.json');generic=read(rp/'rag_g2_nq_generic_validation.json')
    assert sha(data/'manifest.json')==train['dataset_manifest_sha256']
    for f in d['files'].values():assert sha(Path(f['path']))==f['sha256']
    assert sha(Path(train['model_path'])/'model.safetensors')==train['model_weights_sha256']
    index_path=TRAIN/'evaluation_indexes/minilm_g2_nq_50k'
    assert sha(index_path/'faiss.index')==idx['index_sha256']
    assert sha(index_path/'embeddings.npy')==idx['embeddings_sha256']
    gains=[ev['g2'][family][k]-ev['a'][family][k] for family in ['hit','recall'] for k in ['20','50']]
    if all(x>=0 for x in gains) and any(x>0 for x in gains) and ev['g2_no_gold_top50']<=ev['a_no_gold_top50']:
        decision='A. NATURAL QUESTIONS G2 IMPROVES LUMINAR FIRST-STAGE RETRIEVAL'
    elif all(x<=0 for x in gains) and any(x<0 for x in gains) and ev['g2_no_gold_top50']>=ev['a_no_gold_top50']:
        decision='C. NATURAL QUESTIONS G2 REGRESSES LUMINAR RETRIEVAL'
    else:decision='B. NATURAL QUESTIONS G2 IS NEUTRAL / INCONCLUSIVE'
    split_audit=read(rp/'rag_g2_nq_split_audit.json')
    report={'experiment':'G2_NATURAL_QUESTIONS','decision':decision,'interpretation':'Experimental/descriptive: DRAFT DEV labels; G1 frozen historical context; valid primary comparison A vs G2','data':d,'calibration':cal,'audit':audit,'preflight':pre,'smoke':smoke,'training':train,'index':idx,'generic_validation':generic,'dev':ev,'split_audit':split_audit,'historical_g1':{'metrics':g1['g1'],'no_gold_top50':g1['g1_no_gold_top50']},'safety':safety,'TEST_evaluated':False}
    added=[str(p.relative_to(ROOT)) for folder in [ROOT/'scripts',ROOT/'tests',rp] for p in folder.iterdir() if p.is_file() and 'g2' in p.name]
    added=sorted(set(added)|{'datasets/training/reports/rag_g2_nq_final.json','datasets/training/reports/rag_g2_nq_final.md'})
    report['files_added']=added
    (rp/'rag_g2_nq_final.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    lines=['# G2_NATURAL_QUESTIONS — consolidated controlled pilot','',f'**Decision: {decision}.**','',
       'The valid comparison is A → independently initialized NQ G2. G1 is frozen historical context. DEV labels remain DRAFT, so all downstream conclusions are experimental/descriptive. Stop after G2; no next dataset, mixture, or production promotion.','',
       '## Source, inventory, and selection','',
       f"Source: [`{d['dataset_id']}`](https://huggingface.co/datasets/{d['dataset_id']}); configuration `{d['config']}`; revision `{d['revision']}`; split TRAIN; actual schema `{d['schema']}`. Automatic download succeeded without authentication. The initial sandbox request failed with HTTPX ConnectError WinError 10061; the required request outside the sandbox succeeded. Windows symlinks were unavailable, so HF used file copies in the controlled cache. No alternate dataset was used.",'',
       f"Full-source inventory: `{d['inventory']}`.",'',
       f"Selected final pairs: 50,000 = 45,000 TRAIN + 5,000 generic validation; seed 42; normalized-query overlap 0. Initial selection used shuffled normalized-query groups and one seeded positive per group. Full-source alternate positives were preserved for negative exclusion. Technical selection deviation: {d['selection_deviation']}. Replacements: {d['mining']['reserve_replacements']}; full mining attempts: {d['mining']['attempted_queries']}; queries without a safe candidate: {d['mining']['unmineable_queries']}. This conditions the TRAIN sample on safe-negative availability; it is not an unconditional uniform 45k NQ sample.",'',
       'Token counts include tokenizer special tokens and are measured without truncation. Source query/answer distributions and counts over 256 are in the inventory above; the model window stayed at 256. Long passages are truncated at encode/train time.','',
       '| Saved data | Rows | SHA-256 |','|---|---:|---|']
    for name,f in d['files'].items():lines.append(f"| {name} | {f['rows']} | `{f['sha256']}` |")
    lines+=['','## Negative mining and engineering audit','',
      f"Mining model: untouched `sentence-transformers/all-MiniLM-L6-v2` at snapshot `{Path(pre['base_snapshot']).name}`. Installed `sentence_transformers.util.mine_hard_negatives` was used with the full normalized-deduplicated answer corpus ({d['mining']['normalized_corpus_count']} passages), FAISS, batch 32, five internal candidates, and one retained negative per final training query. No G1 or reranker mining.",'',
      f"Calibration attempted 500 queries; {cal['rows']} had safe negatives. Raw score distributions were inspected before selecting the cap. Settings: `{cal['settings']}`; eligible candidate rank slice 10–50. The cap is bounded by the measured positive upper quartile and .80; the .10 relative/.05 absolute margins conservatively require score separation. Settings stayed fixed for full mining. Saved `negative_rank` is the raw 1-based full-corpus rank, which differs from the installed miner's rank after positive/score masking.",'',
      f"Calibration distributions: `{cal['distributions']}`.",f"Full mining distributions: `{d['mining']['distributions']}`.",'',
      f"Safeguards: {d['mining']['false_negative_safeguards']}. Known-positive candidates rejected by postfilter: {d['mining']['known_positive_candidates_excluded']}. Every saved negative is checked against all full-source positives for its normalized query, including normalized-text duplicates.",'',
      f"Deterministic seed-42 source-text audit: 25 negatives; {audit['obviously_not_answer']} OBVIOUSLY_NOT_ANSWER, {audit['possible_false_negative']} POSSIBLE_FALSE_NEGATIVE, {audit['ambiguous']} AMBIGUOUS. The two ambiguous cases concern general Bible authorship and generic climate factors; neither clearly supplies the requested specific answer. This is model engineering sanity inspection, not human training-label review, and cannot estimate a corpus-wide false-negative rate.",'',
      '| Sample | Query | Classification | Reason |','|---|---|---|---|']
    for x in audit['rows']:lines.append(f"| {x['sample']} | {x['query']} | {x['classification']} | {x['reason']} |")
    lines+=['','## Environment, controls, and training','',f"Measured preflight versions: `{pre['versions']}`. CUDA {pre['cuda']}; {pre['gpu']}; total/free VRAM {pre['gpu_total_bytes']:,}/{pre['gpu_free_bytes']:,} bytes; total/available RAM {pre['ram_total_bytes']:,}/{pre['ram_available_bytes']:,} bytes; disk free {pre['disk_free_bytes']:,} bytes. BF16 support: {pre['bf16_supported']}.",'',
      f"G2 was independently loaded from the untouched A snapshot `{train['base_snapshot']}`, not G1. Base `model.safetensors` SHA-256: `{train['base_weights_sha256']}`. All baseline snapshot file hashes are recorded in the preflight. G1 recorded model/data/index hashes passed verification and its full before/after file snapshot has 0 changes.",'',
      'Fresh A reproduction: all 30 DEV questions have exactly matching historical Top50 chunk IDs; 29 are evaluable. Historical records also contain TEST rows, which were filtered out for the comparison; no TEST query was encoded/evaluated. The initial overly strict all-splits ID-set check was corrected to DEV-only; actual DEV rankings never mismatched.','',
      'Explicit-negative contract: focused synthetic trainer/collator/loss test passed (1 test). Query, positive, negative all reach MNRL; changing only the negative changes the loss. Real smoke/full trainer batches also assert all three columns. Metadata score/rank columns are explicitly excluded from the training Dataset. Every training loss is checked for finiteness before backward.','',
      f"Loss `{train['loss']}`; batch sampler `{train['batch_sampler']}`; physical/effective contrastive batch {train['physical_batch']}/{train['effective_contrastive_batch']}; gradient accumulation {train['gradient_accumulation_steps']}; BF16 {train['bf16']}; FP16 {train['fp16']}. Seed42, 1 epoch, lr2e-5, weight decay.01, linear schedule, .05 warmup. No hyperparameter deviation from G1. Accumulation is not used to enlarge the in-batch pool.",'',
      f"Smoke: {smoke['rows']} triplets, {smoke['training_steps']} steps, loss {smoke['final_training_loss']:.6f}; forward/backward, finite BF16 loss, saved-model reload and normalized 384-d encode passed. Minimum GPU free headroom {smoke['vram_headroom_bytes']:,} bytes.",'',
      f"Full: {train['rows']} triplets, {train['training_steps']} steps, {train['training_seconds']:.2f} seconds; training aggregate loss {train['final_training_loss']:.6f}. Peak reserved/allocated VRAM {train['peak_vram_reserved_bytes']:,}/{train['peak_vram_allocated_bytes']:,} bytes; minimum global GPU headroom {train['vram_headroom_bytes']:,} bytes; peak process RSS {train['peak_ram_rss_bytes']:,} bytes. Safety callbacks monitor free GPU memory and finite loss/gradients; no unrelated processes were stopped.",'',
      f"Isolated model `{train['model_path']}`; model weights SHA-256 `{train['model_weights_sha256']}`. Saved reload/window256/dimension384 verification passed.",'',
      '## Generic NQ held-out sanity','',f"{generic['type']}; {generic['queries']} queries; {generic['candidate_count']} candidates. This is actual bounded retrieval, not full-NQ retrieval and not a LuminaR promotion criterion.",'',
      f"Normalized-query overlap is zero; {split_audit['train_validation_normalized_positive_passage_overlap']} distinct positive passages appear in both TRAIN and validation. This is held-out-question sanity, not an unseen-document generalization test.",'',
      '| Metric | A | G2 |','|---|---:|---:|']
    for k in generic['results']['A']:lines.append(f"| {k} | {generic['results']['A'][k]:.4f} | {generic['results']['G2'][k]:.4f} |")
    lines+=['','## Frozen LuminaR DEV result','',
       f"Exact same 16,895 chunks, 18 books, tokens_220. Embedding shape `{idx['embedding_shape']}`, finite/normalized; norm min/max {idx['norm_min']:.10f}/{idx['norm_max']:.10f}. Global and per-book IndexFlatIP, dimension384; global count {idx['index_count']}; {idx['book_count']} per-book indexes. Embeddings SHA-256 `{idx['embeddings_sha256']}`; global index SHA-256 `{idx['index_sha256']}`. Frozen source/label/mapping hashes verified.",'',
       'Original query only, dense-only per-book retrieval, DEV only. No expansion, lexical, union, reranker, Qwen, or answer generation.','',
       '| Metric | A baseline | G1 MS MARCO (historical) | G2 NQ |','|---|---:|---:|---:|',
       f"| MRR | {ev['a']['mrr']:.4f} | {g1['g1']['mrr']:.4f} | {ev['g2']['mrr']:.4f} |"]
    for family,ks in [('hit',['1','3','5','10','20','50']),('recall',['5','10','20','50'])]:
        for k in ks:lines.append(f"| {family.title()}@{k} | {ev['a'][family][k]:.2%} | {g1['g1'][family][k]:.2%} | {ev['g2'][family][k]:.2%} |")
    lines += [f"| No accepted span Top50 | {ev['a_no_gold_top50']} | {g1['g1_no_gold_top50']} | {ev['g2_no_gold_top50']} |",'',
       f"A→G2 movement: `{ev['counts']}`; recovered Top50 {ev['recovered_top50']}; lost Top50 {ev['lost_top50']}. These describe this small DEV sample and do not establish statistical generalization.",'',
       '| Query | Work | Movement | A accepted ranks | G2 accepted ranks |','|---|---|---|---|---|']
    for q in ev['per_query']:lines.append(f"| {q['query_id']} | {q['book']} ({q['work_id']}) | {q['status']} | {q['a_gold_span_ranks']} | {q['g2_gold_span_ranks']} |")
    for q in ev['per_query']:
        if q['recovered_top50'] or q['lost_top50']:
            lines += ['',f"### {'Recovered' if q['recovered_top50'] else 'Lost'}: {q['query_id']} — {q['book']} ({q['work_id']})",'',q['question'],'',
                      f"A accepted ranks: {q['a_gold_span_ranks']}; G2 accepted ranks: {q['g2_gold_span_ranks']}.",'']
            for side in ['a','g2']:
                lines += [f'{side.upper()} diagnostic top passages:','']
                for x in q[f'{side}_nearest']:
                    lines.append(f"- Rank {x['rank']}, `{x['chunk_id']}`: {x['text_excerpt'].replace(chr(10),' ')}")
    lines+=['','Additional machine-readable diagnostics are in `rag_g2_nq_eval.json`.','',
       '### Descriptive check of four G1-lost queries','', '| Query | A accepted ranks | G2 accepted ranks |','|---|---|---|']
    for q in ev['per_query']:
        if q['query_id'] in ['v8_08','v8_10','alice_04','time_02']:lines.append(f"| {q['query_id']} | {q['a_gold_span_ranks']} | {q['g2_gold_span_ranks']} |")
    lines+=['','These four queries were not used to tune G2.','',
       '## Safety and files','', '**TEST evaluated: NO.** Cross-encoder and Qwen untouched. No domain QA training, other dataset training, mixture, production promotion, or G1 rerun.','',
       f"Before/after safety: `{safety}`. Only experiment scripts/test and isolated G2 data/cache/models/checkpoints/manifests/indexes/reports were added. No production or evaluation-label changes. G1 reports remain unchanged; no independent historical report hash ledger exists beyond this run's before/after snapshot.",'',
       *[f'- `{x}`' for x in added], '', f'**FINAL G2 DECISION: {decision}.**']
    (rp/'rag_g2_nq_final.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'decision':decision,'dev':{k:ev[k] for k in ['a','g2','a_no_gold_top50','g2_no_gold_top50','counts','recovered_top50','lost_top50']},'safety':safety},indent=2))
if __name__=='__main__':main()
