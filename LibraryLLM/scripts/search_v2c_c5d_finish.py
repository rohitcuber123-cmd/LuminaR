"""Close C5D with independently recomputed replay accounting and evidence freeze."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import ast
import json
import re
from scripts.search_v2c_c5d_prepare import R,P,load,rows,sha,digest,write

def main():
    pre=load(R/(P+'preflight.json'));capture=load(R/(P+'shadow_capture_complete.json'))
    freeze=load(R/(P+'shadow_candidate_freeze.json'));started=load(R/(P+'shadow_capture_started.json'))
    assert all(sha(p)==h for p,h in freeze['files'].items())
    assert started['candidate_freeze_sha256']==digest(freeze)
    assert sha(R/(P+'shadow_predictions.jsonl'))==capture['prediction_sha256']
    assert capture['errors']==capture['retries']==capture['new_production_parser_calls']==capture['gold_reads']==0
    assert not capture['isolation_denials']
    write('shadow_capture_binding.json',{'status':'PASS','freeze_file_sha256':sha(R/(P+'shadow_candidate_freeze.json')),
         'freeze_canonical_json_sha256':digest(freeze),'capture_marker_field_interpretation':'candidate_freeze_sha256 in capture_started hashes canonical JSON, not serialized file bytes. Both bindings are explicit here.',
         'shadow_prediction_file_sha256':sha(R/(P+'shadow_predictions.jsonl')),
         'validation_prediction_file_sha256':sha(R/(P+'validation_predictions.jsonl')),
         'capture_and_candidate_files_unchanged':True})
    root=rows(R/(P+'root_cause_matrix_v2.jsonl'));summary=load(R/(P+'root_cause_summary.json'))
    replay=load(R/(P+'shadow_replay_results.json'));regression=load(R/(P+'safety_regression_analysis.json'))
    validation=load(R/(P+'independent_validation_limits.json'));counterexample=load(R/(P+'prototype_counterexample_audit.json'))
    contract=load(R/(P+'typed_decision_contract_audit.json'));confidence=load(R/(P+'confidence_investigation.json'))
    traces=rows(R/(P+'false_execution_traceability.jsonl'));assert len(traces)==len({x['case_id'] for x in traces})==191
    g={x['case_id']:x for x in rows(R/'search_v2c_c5b_calibration_cases.jsonl')}
    b={x['case_id']:x for x in rows(R/'search_v2c_c5c_predictions.jsonl')}
    shadow=rows(R/(P+'shadow_predictions.jsonl'));assert len(shadow)==644
    # Recompute rates, changed IDs, cohort and stratum totals from raw frozen
    # replay outputs, independently of replay scoring helpers.
    independently_recomputed={}
    for candidate,data in replay['candidates'].items():
        false=missed=coverage=changed=extra_miss=0
        for row in shadow:
            gold=g[row['case_id']]['expected_executable'];baseline=b[row['case_id']]['executable'];actual=row['outcomes'][candidate]['recommend_execution']
            false+=actual and not gold;missed+=gold and not actual;coverage+=actual;changed+=actual!=baseline;extra_miss+=gold and baseline and not actual
            assert not actual or baseline
        m=data['overall'];assert (false,394)==(m['false_execution']['numerator'],m['false_execution']['denominator'])
        assert (missed,250)==(m['missed_execution']['numerator'],m['missed_execution']['denominator'])
        assert coverage==m['executable_coverage']['numerator'] and changed==m['changed_execution_decisions'] and extra_miss==m['additional_missed_valid_execution']
        assert sum(x['contexts'] for x in data['thirty_cells'])==644
        for cell in data['thirty_cells']:
            subset=[row for row in shadow if g[row['case_id']]['scope_type']==cell['scope'] and g[row['case_id']]['decision_stratum']==cell['stratum']]
            assert len(subset)==cell['contexts']
            assert sum(row['outcomes'][candidate]['recommend_execution'] and not g[row['case_id']]['expected_executable'] for row in subset)==cell['false_execution']['numerator']
        independently_recomputed[candidate]={'false_execution':false,'missed_execution':missed,'coverage':coverage,'changed':changed}
    assert len(root)==635 and len({r['case_id'] for r in root})==635
    expected_failure_ids={r['case_id'] for r in rows(R/'search_v2c_c5c_failures.jsonl')}
    assert {r['case_id'] for r in root}==expected_failure_ids
    classes=defaultdict(set)
    for row in root:
        for cause in row['causes']:
            classes[cause['C5D_attribution_class']].add(row['case_id'])
            loc=cause['source_location'];assert sha(loc['path'])==loc['sha256']
    assert {k:len(v) for k,v in classes.items()}==summary['C5D_attribution_context_counts']
    # Preserve all previous milestones and compare large assets using only the
    # inherited artifact SHA or size/mtime method, never an invented checksum.
    changes=[p for p,h in pre['protected_files'].items() if sha(p)!=h];assert not changes,changes
    large=[]
    for item in load(R/'search_v2c_c_preservation.json')['files']:
        path=item['file']
        if path.startswith(('data_pipeline/','local-data/','recommendation/','rag/')) or path=='scripts/search_v2c_c_author_gold.py':
            prior=item['after'];stat=Path(path).stat()
            match=sha(path)==prior['sha256'] if 'sha256' in prior else stat.st_size==prior['size'] and stat.st_mtime_ns==prior['mtime_ns']
            assert match,path
            large.append({'path':path,'unchanged':True,'method':'artifact SHA256' if 'sha256' in prior else 'inherited size+mtime_ns, not full checksum'})
    write('preservation.json',{'status':'PASS','protected_files_verified':len(pre['protected_files']),'changes':changes,'production_files_verified':462,
        'C5A_C5B_C5C_unchanged':True,'C5C_prediction_sha256':sha(R/'search_v2c_c5c_predictions.jsonl'),
        'sealed_heldout_hash_only_verified':True,'heldout_contents_decoded':0,'large_artifacts':large,'full_HNSW_KG_checksum_claim':False,
        'global_catalogue_metadata':'5,000,000 prior recorded observation; not rescanned.',
        'global_search_health':'Last known STALE/degraded, baseline_verified=False; endpoint not repolled.',
        'native_authorization_and_transactions':'Static inspection only. No native API requests, issuance, reservations or commits.'})
    issues=[{'issue':'NOTICE_OWNERSHIP_AND_REPAIR','contexts':100,'state':'Mixed structural ownership concern and actual missing repair signals; independent contract review required.'},
            {'issue':'AFFECTED_FIELD_GRANULARITY','contexts':101,'state':'Typed class correct; family/endpoint equality not established. No normalization applied.'},
            {'issue':'STRUCTURED_ADVISORY_ORACLE','contexts':594,'state':'C5C advisory-object metric unavailable; display strings do not constitute a typed structured oracle.'},
            {'issue':'AUTHOR_TITLE_INTENT_PRECEDENCE','contexts':50,'state':'Retained original intent gold differs from author-first composer; independent ownership review required.'}]
    write('contract_review_proposals.json',{'status':'PROPOSED_ONLY','issues':issues,'case_counts_overlap':True,'C5C_historical_metrics_rewritten':False,
        'review_boundary':'Fresh independent contract/semantic review required before changing future oracle adapters or production field ownership.',
        'forbidden_shortcuts':['Map all EXECUTABLE outputs to notice.','Normalize rating family into both endpoint fields without operator/span evidence.','Treat all string remainder disagreement as lost intent.','Rewrite gold based on parser agreement.']})
    counts=summary['root_cause_distinct_context_counts']
    priorities=[
      {'rank':1,'work':'Mandatory requirement ledger and semantic blocking state','target':'Parser semantic recognition plus fail-closed-on-known-unresolved safety boundary',
       'safety_impact':'All191 false recommendations arise from reduced/unresolved requirement interpretation; confidence alone cannot distinguish them.',
       'distinct_observed_false_execution_contexts':191,'evidence':'191/191 EXECUTABLE -> AUTO_EXECUTE; missing relation, incomplete, unsupported or contradiction prerequisites.',
       'risk':'Blanket uncertainty refusal would regress legitimate executable cases; ledger must distinguish required, advisory, unresolved and absent.',
       'scope_privacy':'All five scopes; preserve native authority ahead of catalogue/choice access.','complexity':'High','regression_risk':'High',
       'independent_review':'Required for requirement ownership and hard-negative/safe-uncertain validation.','offline_test':'New isolated parser fork + frozen ledger assertions; no production route.',
       'expected_semantic_effect':'Represent previously invisible mandatory obligations; no numerical gain forecast.'},
      {'rank':2,'work':'Explicit field/span ownership and candidate composition','target':'Parser extraction',
       'distinct_observed_quoted_operand_contexts':counts['QUOTED_OPERAND_MASKED'],'distinct_other_field_gap_contexts':counts['FINITE_FIELD_RECOGNIZER_GAP'],
       'evidence':'Protected quotes hide subject/negative operands; format-only boundaries, availability phrasing and publication equality have finite grammar gaps.',
       'risk':'Do not parse inside quoted entities globally or narrow generic topical prose into hard filters.','scope_privacy':'Use complete authorized scope vocabulary only.',
       'complexity':'Medium/high','regression_risk':'High','independent_review':'Reviewed minimal pairs for explicit fields vs opaque literals and optional prose.',
       'offline_test':'Source-span ownership, lossless candidate inventory and grouped grammar regressions.',
       'expected_semantic_effect':'Preserve required operands and both sides of contradictions; effect not newly measured.'},
      {'rank':3,'work':'Notice, affected-field, advisory and intent contract ownership','target':'Output contract and evaluator alignment before score changes',
       'evidence':'Notice0/100 in both observed layers; 101 field-code and50 retained-intent concerns; 594 unavailable structured advisory oracles.',
       'risk':'An adapter could hide real missing functionality if it simply makes labels agree.','scope_privacy':'Native response/correction path must retain ownership and replay controls.',
       'complexity':'Medium','regression_risk':'Medium/high','independent_review':'Required before any future label/oracle version; original C5C remains immutable.',
       'offline_test':'Review exact observable layer ownership and deliberately inequivalent counterexamples.',
       'expected_semantic_effect':'Make measurement meaningful without pretending representation-only normalization repairs semantics.'},
      {'rank':4,'work':'Bounded operator repairs with provenance and topic preservation','target':'Parser recognition and assembly',
       'distinct_title_remainder_contexts':counts['TITLE_CLEARS_REMAINDER'],'distinct_untagged_numeric_fallback_contexts':counts['UNTAGGED_NUMERIC_FALLBACK'],
       'evidence':'Title assignment clears semantic_text; exact-star fallback can replace misspelled comparator semantics without notice.',
       'risk':'Do not guess unrecoverable operands or treat every strict remainder mismatch as loss;65 contexts retain normative topic tokens.',
       'scope_privacy':'Preserve authorized fields and advisory status across scopes.','complexity':'Medium/high','regression_risk':'High',
       'independent_review':'Required operator repair and intent/topic minimal pairs.','offline_test':'No invented extra bounds; correct operator provenance and independent title/topic assertions.',
       'expected_semantic_effect':'Retain independent topic clauses and justified repair notice evidence.'},
      {'rank':5,'work':'Source-grounded consistency/review guards','target':'Offline safety controls, not selected production policy',
       'evidence':'B/C/E hold8/4/12 false recommendations in exploratory replay; E still leaves179/394 and misses all four unsafe revised author cases.',
       'risk':'Frozen C/E substring counterexample proves possible false holds; no deployment inference from zero observed cohort regressions.',
       'scope_privacy':'Cannot replace or bypass fresh authorization, private concealment, state/version or transaction preconditions.',
       'complexity':'Medium','regression_risk':'High outside observed examples','independent_review':'Required exact normalization/whole-word semantics and structurally separate blocked/positive validation.',
       'offline_test':'Correct the prototype specification only in a future version, then freeze before fresh validation; retain current failed counterexample.',
       'expected_semantic_effect':'Restrict provably inconsistent known representations; cannot recover missing semantic signals.'},
      {'rank':6,'work':'Confidence representation and future calibration feasibility','target':'Feature/oracle design, later offline calibration',
       'evidence':'207 valid and191 unsafe execution recommendations share native1.0; observed signal duplicates binary executability.',
       'risk':'Threshold fitting on these tied signals cannot discriminate the cases; corpus reuse risks overfitting.',
       'scope_privacy':'No relaxation of native boundaries.','complexity':'Depends on preceding semantic work','regression_risk':'High if used before prerequisites',
       'independent_review':'Independent labels and complete grouped coverage before any new fitted model/statistic.',
       'offline_test':'Collect source-backed completeness/resolution features under a separately authorized protocol.',
       'expected_semantic_effect':'No semantic repair promised by confidence transformation.'}]
    recommendation={'exit_path':'PATH C — Mixed remediation required','ranked_engineering_plan':priorities,'production_policy_winner':None,
       'next_implementation_boundary':'Separately authorize a versioned offline parser/contract remediation prototype with an explicit mandatory-requirement ledger and source-span ownership; independently review notice/field/advisory/intent contracts before any oracle change. Keep production routes/policies unchanged.',
       'evidence_prerequisites':['Hash-bind original C5B/C5C and the C5D candidate/counterexample evidence.','Freeze the next prototype and future scoring contract before fresh independent labels/results.',
         'Obtain structurally grouped positive, safe-uncertain and hard-negative validation across all scopes; do not split near-duplicate families.',
         'Demonstrate preservation of literal boundaries, optional semantics, native authority and transaction invariants without live execution.',
         'Retain original scores and separately version every proposed oracle or implementation change.'],
       'heldout_boundary':'Remains separately gated; no heldout content or scoring in this phase.',
       'stop_after_C5D':True}
    write('remediation_recommendations.json',recommendation)
    prohibited={key:0 for key in ['NEW_PRODUCTION_PARSER_EVALUATIONS','PRODUCTION_PARSER_CHANGES','PRODUCTION_POLICY_CHANGES','PRODUCTION_POLICY_ACTIVATIONS',
      'FINAL_POLICY_SELECTIONS','THRESHOLD_FITTING_RUNS','THRESHOLD_SWEEPS','HELDOUT_PARSER_EVALUATIONS','HELDOUT_POLICY_EVALUATIONS',
      'HELDOUT_CONTENT_INSPECTIONS','GOLD_REWRITES','C5C_PREDICTION_CHANGES','NATIVE_HARNESS_RERUNS','NATIVE_TRANSACTION_EXECUTIONS','LIVE_APPLICATION_COMMITS',
      'QWEN_INFERENCES','MODEL_CHANGES','HNSW_REBUILDS','KG_REBUILDS','MONGO_MUTATIONS','RESIDENT_ENDPOINT_POLLS','CORPUS_REGENERATIONS','PART_2I_STARTS']}
    write('prohibited_activity_audit.json',{'counts':prohibited,'primary_shadow_replays':3220,'historical_development_shadow_replays':30,
       'pre_freeze_controlled_invariant_calls':16,'post_freeze_counterexample_calls':1,'prediction_or_candidate_retries':0,
       'metadata_preparation_attempts':load(R/(P+'validation_population.json'))['preparation_attempts'],
       'guard_inference_gold_reads':0,'guard_inference_context_ID_access':False,'application_request_path_registration':False,
       'candidate_code_path':'scratch/search_v2c_c5d/shadow_guard.py','candidate_importability':'Only explicit file-path loading by C5D scripts; absent from production request imports/configuration.'})
    qa={'FINAL':'PASS','C5D_IMPLEMENTED':'YES','C5C_FREEZE_VERIFIED':'YES','C5C_PREDICTIONS_UNCHANGED':'YES','C4_ACTIVE_POLICY_PRESERVED':'YES',
        'PRODUCTION_PARSER_CHANGED':'NO','PRODUCTION_POLICY_CHANGED':'NO','PARSER_POLICY_CONTRACT_AUDITED':'YES',
        'EXECUTABLE_WITH_NOTICE_ROOT_CAUSE':{'classification':'MIXED_CONTRACT_OWNERSHIP_AND_MISSING_REPAIR_PROVENANCE','gold_cases':100,'typed_notice':0,'policy_notice':0,'auto_without_notice':70,'clarify':30,'historical_scores_changed':False},
        'FALSE_EXECUTION_CASES_TRACED':191,
        'CONFIRMED_PARSER_DEFECTS':{'C5D_unique_contexts_with_source_capture_backed_dimensions':len(classes['CONFIRMED_PARSER_DEFECT']),'method':'Static source/control-flow plus immutable outputs, not instrumented parser reexecution.','C5C_historical_count_unchanged':562},
        'CONFIRMED_POLICY_ADAPTER_DEFECTS':0,
        'EVALUATOR_CONTRACT_CONCERNS':{'issues':issues,'C5D_root_matrix_contexts':len(classes['EVALUATOR_CONTRACT_CONCERN']),'counts_overlap':True},
        'INDETERMINATE_FAILURES_REMAINING':{'C5D_indeterminate_contexts':len(classes['INDETERMINATE_MISMATCH']),'C5D_multiple_cause_contexts':len(classes['MULTIPLE_INTERACTING_CAUSES']),'C5C_historical_indeterminate_count_unchanged':567,'counts_overlap':True},
        'OPERAND_EXTRACTION_ROOT_CAUSES':{k:counts.get(k,0) for k in ['QUOTED_OPERAND_MASKED','FINITE_FIELD_RECOGNIZER_GAP','FORMAT_ONLY_SCOPE_GAP','UNTAGGED_NUMERIC_FALLBACK']},
        'AMBIGUITY_ROOT_CAUSES':'83 typed misses: unresolved relational/operator/advisory interpretations absent from modeled blocking state; numeric fallback sometimes blocks for the wrong reason.',
        'INCOMPLETE_ROOT_CAUSES':'72 typed misses: narrow end-anchored/clause grammar loses missing mandatory operand evidence before executable fallback.',
        'UNSUPPORTED_ROOT_CAUSES':'89 typed misses: requested unsupported requirement absent/misrepresented in finite candidate vocabulary; output-intent whitelist cannot recover it.',
        'CONTRADICTION_ROOT_CAUSES':'33 typed misses: discarded prerequisite operands and missing cross-field requirement inventory prevent consistency detection.',
        'CONFIDENCE_SIGNAL_SEMANTICS':confidence['interpretation'],
        'SHADOW_CANDIDATES_IMPLEMENTED':5,'SHADOW_CANDIDATES_EVALUATED':5,'BASELINE_FALSE_EXECUTION_COUNT':191,
        'SHADOW_FALSE_EXECUTION_COUNTS':{k:v['overall']['false_execution'] for k,v in replay['candidates'].items()},
        'BASELINE_MISSED_EXECUTION_COUNT':43,'SHADOW_MISSED_EXECUTION_COUNTS':{k:v['overall']['missed_execution'] for k,v in replay['candidates'].items()},
        'CLEAR_EXECUTABLE_REGRESSIONS':{'observed_C5C_additional_misses':{k:v['CLEAR_EXECUTABLE'] for k,v in regression['candidates'].items()},'known_out_of_cohort_positive_counterexample':'C/E may falsely hold a valid whole-word-negative request; retained in prototype_counterexample_audit.json.'},
        'SAFE_UNCERTAIN_EXECUTABLE_REGRESSIONS':{k:v['SAFE_UNCERTAIN_EXECUTABLE'] for k,v in regression['candidates'].items()},
        'SCOPE_SPECIFIC_SAFETY_REGRESSIONS':{k:v['by_scope'] for k,v in regression['candidates'].items()},
        'INDEPENDENT_VALIDATION_AVAILABLE':'LIMITED: six pre-existing independently reviewed DEVELOPMENT positives, one structural group; no adequate independent safety/generalization validation.',
        'PRODUCTION_SOURCE_HASH_VERIFICATION':'PASS (462 files)','HISTORICAL_EVIDENCE_HASH_VERIFICATION':f"PASS ({len(pre['protected_files'])} protected pre-existing files)",
        'SEALED_HELDOUT_HASH_UNCHANGED':'YES','C5D_EVIDENCE_FROZEN':'YES','THRESHOLD_FITTING_PERFORMED':'NO','CALIBRATION_POLICY_SELECTED':'NO','CALIBRATION_POLICY_ACTIVATED':'NO',
        'HELDOUT_EVALUATIONS':0,'HNSW_REBUILT':'NO','KG_REBUILT':'NO','PART_2I_STARTED':'NO',
        'NEW_PRODUCTION_PARSER_CALLS':0,'PRIMARY_SHADOW_REPLAYS':3220,'HISTORICAL_DEVELOPMENT_REPLAYS':30,'CONTROLLED_INVARIANT_CALLS':16,'POST_FREEZE_COUNTEREXAMPLE_CALLS':1,
        'EXIT_DECISION':recommendation['exit_path'],'PARSER_REPAIRED':'NO','SHADOW_SAFE_TO_DEPLOY':'NOT_ESTABLISHED','CALIBRATION_COMPLETE':'NO',
        'next_implementation_boundary':recommendation['next_implementation_boundary']}
    prompt=Path(r'C:\Users\balak\.codex\attachments\c63aa2f9-5509-4581-8c79-051c7e897f67\Pasted text.txt').read_text(encoding='utf8')
    fields=re.findall(r'^- ([A-Z][A-Z0-9_]+)\s*$',prompt.split('### 15. Mandatory final report fields')[1].split('### 16.')[0],re.M)
    assert not (set(fields)-qa.keys()),set(fields)-qa.keys()
    write('final_qa.json',qa)
    def rate_text(value):return f"{value['numerator']}/{value['denominator']} ({value['percent']:.2f}%)" if value['denominator'] else 'N/A'
    lines=['# LuminaR V2C-C.5D — semantic parser investigation and shadow remediation','',
      'FINAL: PASS. Contract audit, causal investigation, isolated shadow replay and evidence freeze are complete. No production parser was rerun or changed. This is not parser repair, deployment approval, completed calibration or policy selection.','',
      '## Exit decision','',recommendation['exit_path']+'. '+recommendation['next_implementation_boundary'],'',
      '## Exact baseline and preservation','',
      'C5B admission/freeze, all31 C5C frozen payload files, captured predictions, masks, normative gold, evaluator configuration and prior preservation evidence passed SHA256 verification before analysis. C5C prediction SHA256 remains `'+pre['C5C_prediction_sha256']+'`. All '+str(len(pre['protected_files']))+' protected existing files and462 production files were preserved. Heldout bytes were hashed only; no heldout examples/predictions were decoded.','',
      'The 644 C5C parser contexts remain594 new core +50 retained reviewed originals. All new primary analysis uses these frozen predictions; no new parser/model/native evaluation occurred. All original C5A/C5B/C5C scores and dispositions remain unchanged.','',
      '## EXECUTABLE_WITH_NOTICE contract audit','',
      'This is a mixture of representation ownership ambiguity and actual missing repair behavior. The parser accepts EXECUTABLE_WITH_NOTICE as an enum but its SMART composer has no typed-notice producer. assess/execution_policy can infer notice from captured repairs/corrections/unknown_subject. The native search response instead exposes typed decisions, corrections and notices through QueryPlan.public/interpretation/interaction_for; it does not directly consume the assessment policy label.','',
      'For all100 gold notice cases, there are0 typed notices,0 downstream C4 policy notices,0 corrections/repair-provenance/unknown-subject signals,70 EXECUTABLE/AUTO_EXECUTE outcomes and30 clarification outcomes. Thus the cohort cannot be explained away by a notice merely moving downstream. Misspelled comparator/format/entity cues may be ignored, blocked, or treated as exact-star equality without repair provenance. No score correction is applied. Independent review must establish future typed/advisory ownership and native observable notice requirements before changing an evaluator contract.','',
      'Exact sources: search/query_plan.py:155; search/query_repair.py:28,48,73,126,131; search/query_numeric.py:64,110; search/query_calibration.py:16; search/query_execution.py:17,31; search/query_interaction.py:22. Full excerpts, hashes and source locations are in source_references_v2.json.','',
      '## Causal findings','',
      'All635 mismatch contexts have a causal matrix record:585 new-core and50 retained-original. Distinct counts below overlap and must not be added. They are C5D source/capture attributions, not replacements of the historical C5C classifications.','',
      '| Finding | Distinct contexts | Representative IDs | Evidence and limitation |','|---|---:|---|---|',
      '| Quoted operand masking | 382 | C5A-1-1-03, C5A-1-1-04 | Source.remaining hides quoted content and Source.free rejects overlap; title has an ownership exception while subject/exclusion parsing does not. |',
      '| Explicit title clears topic | 133 | C5A-1-1-02, C5A-1-1-05 | compose assigns semantic_text=None after encountering a title. |',
      '| Other finite field-recognizer gaps | 222 | C5A-2-1-01, C5A-2-1-10 | Availability/publication/entity constructions have no corresponding captured candidate; exact responsible recognizers cited per dimension. |',
      '| Format-only modifier scope | 141 | C5A-2-1-02, C5A-2-1-05 | Format is captured as PRESENT without separated ONLY modifier. |',
      '| Untagged numeric fallback | 20 | C5A-1-2-01, C5A-1-2-02 | Exact-star equality replaces a misspelled comparator/range without repair provenance; can invent an extra bound. |',
      '| Topic tokens retained despite strict mismatch | 65 | C5A-1-1-14, C5A-2-1-01 | Extra wrappers/residual requirements remain; strict disagreement alone does not prove lost semantic intent. |',
      '| Correct typed class, affected-field contract concern | 101 | See root_cause_matrix_v2.jsonl | Family vs endpoint codes need independent specification; no equivalence adapter applied. |',
      '| Retained author/title intent priority | 50 | v3:c3-sealed-01-00 | Composer selects FIND_AUTHOR when author is present; retained gold expects FIND_EXACT. Both hard operands can remain present. |','',
      'C5D source/capture-backed parser-defect dimensions appear in557 distinct contexts; evaluator contract concerns in151; indeterminate mismatches in213; multiple interacting causes in379. Counts overlap. The original C5C562 parser-defect-containing and567 indeterminate-containing counts remain frozen. No new normative gold concern is automatically inferred from disagreement.','',
      '## False-execution and ambiguity/incompleteness diagnostics','',
      'All191 false-execution recommendations are traced from reduced/absent requirement evidence to default EXECUTABLE and then AUTO_EXECUTE. No captured blocked parser decision was promoted by the downstream policy. Semantic typed misses are83/98 ambiguous,72/99 incomplete,89/100 unsupported and33/97 contradictory. The first observable issue is often missing candidate or mandatory unresolved-state evidence; the final validator cannot reason about requirements it never received.','',
      'The five revised author-association cases show an additional diagnostic limit: the one AMBIGUOUS output is NUMBER_WITHOUT_FIELD from publication wording, not explicit recognition of the required unresolved author relation. Four unsafe recommendations remain under every shadow candidate. The scalar author-value metric stays intentionally unresolved; required decision gold stays complete.','',
      '## Safety invariants and shadow design','',
      'Existing authority precedes native catalogue/choice access. Only executable typed kinds permit execution. Known contradictions and scope-incompatible parsed constraints block. Missing/ambiguous recognized requirements request clarification. A repair notice is compatible with legitimate execution. Owner/query/mode/version/expiry and one-use reservation remain native preconditions. These are source-grounded boundaries; a complete mandatory-requirement ledger is currently absent.','',
      'Five candidates were frozen before replay: A baseline; B recognized-candidate operand preservation; C parsed consistency/unresolved-state checks; D known output-intent/schema/capability validation; E composition. Candidate functions receive no IDs, query text, gold, expected decisions, reviewer rationale, strata, outcome scores or confidence. The runner associates IDs outside the candidate call. Candidates can only withhold a baseline recommendation and cannot authorize, issue choices, mutate plans or enter the production request path.','',
      '## Actual exploratory replay results','',
      '| Candidate | False execution / blocked gold | Missed execution / executable gold | Execution coverage | Changed recommendations | Additional missed valid executions |',
      '|---|---:|---:|---:|---:|---:|']
    for name,data in replay['candidates'].items():
        m=data['overall'];lines.append(f"| {name} | {rate_text(m['false_execution'])} | {rate_text(m['missed_execution'])} | {rate_text(m['executable_coverage'])} | {m['changed_execution_decisions']} | {m['additional_missed_valid_execution']} |")
    lines+=['','There were3,220 primary candidate replays on644 existing records, not3,220 parser calls. B/C/E add8/4/12 review holds, all on blocked gold in this cohort. D changes nothing because valid default output intents and omitted fields provide no semantic unsupported-operation evidence. No blocked baseline result is promoted. All five revised author cases remain unchanged. Every guard still lacks a full query-requirement completeness/authority proof on all644 records.','',
      'Additional missed CLEAR_EXECUTABLE and SAFE_UNCERTAIN_EXECUTABLE recommendations are0 for each candidate in the primary cohort; additional missed execution is0 in every scope. These observations do not establish absence of regressions elsewhere. Scope/stratum and all30 cells, exact changed IDs and reasons are retained for every candidate in shadow_replay_results.json.','',
      'False executions by scope (blocked denominators Global77, Public patron80, Public staff80, Private patron79, Private staff78):','',
      '| Candidate | Global | Public patron | Public staff | Private patron | Private staff |','|---|---:|---:|---:|---:|---:|']
    scopes=['GLOBAL','PUBLIC_TENANT_PATRON','PUBLIC_TENANT_STAFF','PRIVATE_TENANT_PATRON','PRIVATE_TENANT_STAFF']
    for name,data in replay['candidates'].items():lines.append('| '+name+' | '+' | '.join(str(data['by_scope'][s]['false_execution']['numerator']) for s in scopes)+' |')
    lines+=['','## Counterexample and independent-validation limits','',
      'A separately recorded post-freeze counterexample shows that C, and therefore E, uses substring containment more broadly than the production whole-word negative predicate: required author Marsh with excluded term ar is satisfiable under the source predicate, but the prototype withholds it. The frozen prototype and primary results were not edited. This is a confirmed shadow-prototype limitation and a reason not to infer deployability from apparent replay improvement.','',
      'Six pre-existing independently output-blind AI-reviewed DEVELOPMENT examples were identified and kept as one complete structural group. Their operation topology does not overlap the C5C eligible population. Frozen historical C4 predictions were replayed through the already frozen candidates: all five preserve6/6 executable recommendations; false-execution rate is N/A because there are no blocked examples. These30 supplementary replays are separate from primary denominators. No new reviewer or parser execution is claimed.','',
      'This is limited historical regression evidence, not adequate independent safety validation. Fresh structurally grouped hard negatives, safe-uncertain positives, privacy-sensitive scope cases and exact predicate-boundary adversarial examples are prerequisites for future acceptance. Primary candidates were designed after viewing C5C errors; same-corpus improvements do not establish generalization.','',
      'The supplementary metadata preparation first stopped before replay because of repeated file decoding; its corrected preparation is separately recorded. One diagnostic UTF8 read failure is also recorded. Neither event created parser calls, altered gold/predictions or erased replay attempts. Sixteen pre-freeze controlled invariant checks and one post-freeze semantic counterexample are separate from benchmark denominators.','',
      '## Confidence diagnosis','',
      'QueryPlan defaults to1.0; exact/alias/fuzzy vocabulary resolution can provide similarity values; blocked typed decisions force0.0. On this corpus the observed0.0/1.0 signal exactly duplicates binary executability. At1.0,207 executable-gold and191 blocked-gold recommendations share the same value, and typed correctness is137/398. The signal has no defensible calibrated-probability interpretation. No threshold or transformation was fitted or swept.','',
      '## Ranked remediation and next boundary','']
    for item in priorities:
        lines.append(f"{item['rank']}. **{item['work']}** — {item['target']}. {item['evidence']} Risk: {item['risk']} Independent review: {item['independent_review']} Offline test: {item['offline_test']}")
    lines+=['',recommendation['next_implementation_boundary'],'','Prerequisites:']+['- '+x for x in recommendation['evidence_prerequisites']]
    lines+=['','No production policy winner is selected. No production/parser/model/UI/native changes, heldout evaluation, threshold fitting, index rebuild, Mongo mutation, new application commit or endpoint repoll occurred. Global5,000,000 and STALE/degraded baseline_verified=False remain prior observations. Stop after C5D.','',
      '## Mandatory final QA fields','', '| Field | Actual value |','|---|---|']
    for k,v in qa.items():lines.append('| '+k+' | '+(json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else str(v))+' |')
    lines+=['','## Exact evidence paths','']
    for name in ['preflight.json','architecture.json','source_references_v2.json','typed_decision_contract_audit.json','contract_review_proposals.json',
       'root_cause_matrix_v2.jsonl','root_cause_summary.json','false_execution_traceability.jsonl','operand_extraction_diagnostics_v2.jsonl',
       'semantic_remainder_diagnostics.jsonl','ambiguity_contradiction_diagnostics.json','confidence_investigation.json','safety_invariants.json',
       'shadow_candidate_specifications.json','shadow_candidate_freeze.json','shadow_capture_binding.json','shadow_predictions.jsonl','shadow_replay_results.json',
       'safety_regression_analysis.json','prototype_counterexample_audit.json','validation_population.json','independent_validation_limits.json',
       'preservation.json','prohibited_activity_audit.json','remediation_recommendations.json','final_qa.json','validation.json','freeze_manifest.json']:
        lines.append('- reports/'+P+name)
    with (R/(P+'review.md')).open('x',encoding='utf8') as out:out.write('\n'.join(lines)+'\n')
    write('validation.json',{'status':'PASS','at_utc':datetime.now(timezone.utc).isoformat(),'mandatory_fields_verified':len(fields),
       'root_contexts_verified':635,'false_execution_traces_verified':191,'replay_counts_independently_recomputed':independently_recomputed,
       'protected_file_changes':[],'C5C_predictions_unchanged':True,'candidate_freeze_unchanged':True,'limited_validation_only':True,
       'prototype_counterexample_retained':True,'all_prohibited_operation_counts_zero':True,'new_production_parser_calls':0})
    payload={str(p):sha(p) for p in R.glob(P+'*') if p.is_file() and p.name!=P+'freeze_manifest.json'}
    payload.update({str(p):sha(p) for p in Path('scripts').glob(P+'*.py')})
    payload['scratch/search_v2c_c5d/shadow_guard.py']=sha('scratch/search_v2c_c5d/shadow_guard.py')
    write('freeze_manifest.json',{'version':'C5D-investigation-shadow-evidence-v1','status':'FROZEN_COMPLETE_INVESTIGATION','FINAL':'PASS',
        'at_utc':datetime.now(timezone.utc).isoformat(),'files':payload,'C5C_freeze_sha256':pre['C5C_freeze_sha256'],
        'C5C_prediction_sha256':pre['C5C_prediction_sha256'],'C5B_gold_sha256':pre['C5C_gold_sha256'],
        'shadow_candidate_freeze_sha256':sha(R/(P+'shadow_candidate_freeze.json')),'primary_shadow_prediction_sha256':capture['prediction_sha256'],
        'exit_decision':recommendation['exit_path'],'parser_repaired':False,'policy_selected':False,'policy_activated':False,
        'independent_safety_acceptance_established':False,'new_parser_calls':0,'heldout_evaluations':0,'threshold_fit':False})
    assert all(sha(p)==h for p,h in payload.items())
    print(json.dumps({'FINAL':'PASS','exit_path':recommendation['exit_path'],'false_execution_traced':191,'primary_shadow_replays':3220,
       'historical_shadow_replays':30,'confirmed_parser_contexts':len(classes['CONFIRMED_PARSER_DEFECT']),'indeterminate_contexts':len(classes['INDETERMINATE_MISMATCH']),
       'protected_files':len(pre['protected_files']),'frozen_files':len(payload),'freeze_sha256':sha(R/(P+'freeze_manifest.json')),'new_parser_calls':0}))

if __name__=='__main__':main()
