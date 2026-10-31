"""Finalize from captured evidence only; no parser, model or database execution."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import json,hashlib,subprocess,re,ast
import psutil

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reports'


def load(n):return json.loads((R/('search_proof7_'+n+'.json')).read_text(encoding='utf-8'))
def rows(name):return [json.loads(s) for s in (R/name).read_text(encoding='utf-8').splitlines()]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(n,x):
    with (R/('search_proof7_'+n+'.json')).open('x',encoding='utf-8') as f:json.dump(x,f,indent=2,ensure_ascii=False)
def verify(files):
    bad=[p for p,h in files.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    return {'entries':len(files),'verified':not bad,'failures':bad}
def metric(n,d,cohort):return {'numerator':n,'denominator':d,'cohort':cohort}


def main():
    pre=load('preflight');source=load('source_freeze');experiment=load('comparison7_freeze')
    pilot=load('comparison7_results');agreement=load('pilot_freeze');capture=load('comparison7_model_capture')
    devv6=load('qualified_v6_exposed_results');perf=load('recorded_performance');edit=load('recompilation_timing')
    cohort={n:load('qualified_'+n+'_results')['summary'] for n in ['c5e90','c5er150','smarteng150','comp3_150']}
    c5c=rows('search_proof7_c5c_qualified_scored_observations.jsonl')
    v6old={x['case_id']:x for x in rows('search_proof6_independent_predictions.jsonl')}
    v7new=rows('search_proof7_qualified_v6_exposed_predictions.jsonl')
    differences=[]
    for p in v7new:
        q=v6old[p['case_id']]
        delta={f:{'V6':q['actual_plan'].get(f),'V7':p['actual_plan'].get(f)} for f in ['author_text','title_text','exact_text','sort','rating_min','rating_max','rating_min_exclusive','rating_max_exclusive','year_min','year_max','subjects','exclude_subjects','exclude_terms','formats','language','semantic_text'] if q['actual_plan'].get(f)!=p['actual_plan'].get(f)}
        if p['typed_decision']!=q['typed_decision']:delta['typed_decision']={'V6':q['typed_decision'],'V7':p['typed_decision']}
        if delta:differences.append({'case_id':p['case_id'],'changes':delta})
    write('changed_predictions_vs_V6',{'population':'EXPOSED_V6_DEVELOPMENT_ONLY','changed_contexts':len(differences),'denominator':150,'records':differences,'gold_changed':False})

    author={x['id']:x for x in rows('search_proof7_pilot_authored.jsonl')}
    reviewer={x['id']:x for x in rows('search_proof7_pilot_independent_review.jsonl')}
    dimensions=Counter();correct=Counter();annotation_records=[]
    for p in pilot['records']:
        rr=p['candidates']['deterministic']['plan']['decision'].get('query_ir_contract',{}).get('requirements',[])
        for a in author[p['id']]['requirements']:
            matches=[b for b in reviewer[p['id']]['requirements'] if b['span']==a['span']]
            if len(matches)!=1:continue
            b=matches[0];start,end=a['span']
            ir=[r for r in rr if r['field']==a['domain'] and r['source_span'][0]<end and r['source_span'][1]>start]
            if len(ir)>1:
                ir=sorted(ir,key=lambda x:x['source_span'][1]-x['source_span'][0])[:1]
            ir=ir[0] if ir else None
            item={'id':p['id'],'oracle':a,'candidate':ir,'dimensions':{}}
            mapping={'domain':'field','operator':'operator','operand':'value','role':'source_role','modality':'modality','polarity':'polarity'}
            for key,field in mapping.items():
                if a[key]!=b[key]:continue
                dimensions[key]+=1
                norm=lambda v:' '.join(v.casefold().split()) if isinstance(v,str) else v
                ok=ir is not None and norm(ir.get(field))==norm(a[key]);correct[key]+=ok
                item['dimensions'][key]=ok
            dimensions['exact_source_span']+=1;ok=ir is not None and ir['source_span']==a['span'];correct['exact_source_span']+=ok;item['dimensions']['exact_source_span']=ok
            annotation_records.append(item)
    executed=[x for x in pilot['records'] if x['candidates']['deterministic']['executable']]
    losses=[x for x in executed if any(not a['correct'] for a in x['candidates']['deterministic']['field_comparisons'])]
    error={
        'population':'INDEPENDENTLY_AUTHORED_REVIEWED_PILOT_DEVELOPMENT_NOT_ACCEPTANCE',
        'deterministic_metrics':pilot['summaries']['deterministic'],
        'source_annotation_metrics':{k:metric(correct[k],dimensions[k],'Author/reviewer exact-aligned agreed pilot annotation dimensions') for k in dimensions},
        'annotation_records':annotation_records,
        'mandatory_field_mismatch_executed_contexts':metric(len(losses),len(executed),'Pilot deterministic executable outputs, agreed definite native scalar assertions'),
        'loss_contexts':[{'id':x['id'],'query':x['query'],'assertions':x['candidates']['deterministic']['field_comparisons'],'captured_plan':x['candidates']['deterministic']['plan']} for x in losses],
        'safety_failure':{'id':'v7_dev_pilot_11','query':'Find books by the same author as "A Lantern for Winter".','first_wrong_transformation':'An unsupported cross-book author relationship becomes a literal author operand. The source-coverage detector covers date/proximity/known unsupported metadata relations but misses the cross-book author relation. Internal source/projection proof accepts its own incomplete interpretation.','false_execution':'1/7 mutually agreed blocked pilot contexts'},
        'other_causes':[
            'Exact-title and language ownership: unfamiliar explicit exact-title wording is passed as semantic text; required exact_text and language absent in pilot08.',
            'Entity/clauses: punctuation in unquoted N. K. Jemisin is treated as sentence boundaries and author truncates to n in pilot09.',
            'Missing native-language ownership: in English remains semantic rather than hard language in pilot18, even though its typed decision is disputed.',
            'Metalinguistic reference: publication year, not publisher is treated as a negative metadata request rather than a field reference; a valid query blocks in pilot10.',
            'Notice semantics: a source-backed repair produces EXECUTABLE_WITH_NOTICE where both pilot annotators expected EXECUTABLE (pilot16); raw disagreement retained, no post-outcome relabeling.',
        ],
        'coverage_boundary':'Explicit original-source obligation auditing prevents some known omissions. It is bounded, shares ontology assumptions, and cannot prove natural-language completeness. Character coverage and recognizer self-reproduction are insufficient.',
        'learned_results':'N/A: cached model failed resource gate during loading,0 predictions. Comparison generative counts are safe clarification fallbacks only and MUST NOT be presented as learned accuracy.',
        'candidate_tuned_after_pilot_capture':False,'fresh_acceptance_consumed':False,
    }
    write('error_analysis',error)

    protection={'at_utc':datetime.now(timezone.utc).isoformat(),'prior':verify(pre['protected_files']),'source':verify(source['files']),'comparison_pipeline':verify(experiment['files']),
        'tracked_diff':subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).splitlines(),
        'staged_diff':subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT,text=True).splitlines(),
        'remaining_experiment_process_ids':[p for p in capture['observed_process_ids'] if psutil.pid_exists(p)],
        'Mongo_mutations':0,'HNSW_rebuilds':0,'KG_rebuilds':0,'heldout_evaluations':0,'production_activation':False,
        'public_metadata_network':'Official model-card/license and revision-hash metadata only; no query sent to remote inference. Model worker network denied.',
        'runtime_writes':'Only versioned reports/scripts/scratch and isolated search_proof7_runtime_* cache namespaces; no institutional/production database writes.'}
    assert all(protection[k]['verified'] for k in ['prior','source','comparison_pipeline'])
    assert not protection['tracked_diff'] and not protection['staged_diff'] and not protection['remaining_experiment_process_ids']
    write('preservation',protection)

    previous=json.loads((R/'search_proof6_source_freeze.json').read_text(encoding='utf-8'))['files']
    previous={Path(p).name:h for p,h in previous.items() if 'search_proof_recovery_v6' in p}
    changed=[{'path':str(ROOT/p),'sha256':h,'change':'ADDED' if Path(p).name not in previous else 'MODIFIED_FROM_V6'} for p,h in source['files'].items() if 'search_proof_recovery_v7' in p and previous.get(Path(p).name)!=h]
    mapping=[]
    for p,h in source['files'].items():
        tree=ast.parse((ROOT/p).read_text(encoding='utf-8'))
        mapping.append({'path':str(ROOT/p),'sha256':h,'symbols':[{'name':n.name,'line':n.lineno} for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]})
    write('source_map',{'candidate_id':'search-smarteng-disabled-proof-7','files':mapping,'candidate_changes':changed,'runtime_driver':'scripts/search_proof7_process_budget.py (process-tree guard supersedes the historical frozen scalar-RSS sandbox runner)'})

    blockers=[
        'Pilot exposes unsupported cross-book author false execution1/7 blocked contexts and mandatory scalar loss3/10 executed outputs; deterministic interpretation remains unsafe.',
        'Cached3B generative model exceeded the explicit2GiB process-tree RAM budget at2,227,855,360bytes during loading;0 predictions, no measured learned quality/latency. Host initially had4,216,193,024bytes available RAM.',
        'Pilot author/reviewer decision agreement14/18 and native-field agreement16/18; disputed dimensions remain unresolved rather than tuned to predictions.',
        'Source-role/modality interpretation remains partial (550/615 and560/615 on exposed V6 annotations,50excluded).',
        'Production500-character transport, accepted-source lifecycle, real JWT/current membership, durable MongoCAS/one-use, real embedding relevance and operationalSLO remain unqualified.',
    ]
    staging=[
        'Resolve the cross-book relation, exact literal/language ownership and punctuated entity coverage families at the ontology/representation boundary; do not add per-case exception tables. Validate with new reviewed development families and adversarial omission tests.',
        'Adjudicate pilot role/notice/disjunction/title-only enforcement uncertainties independently, retaining both original label sets and their disagreements. Estimate dataset size after a bounded additional annotation pilot; do not generate a large self-labeled corpus.',
        'For a genuine learned comparison, provide sufficient free host RAM while retaining platform reserves, or separately approve a specific smaller public checkpoint after revision/license/tokenizer/resource audit. Reuse the tested process-tree runner and per-task cache allowlist. Do not relax budgets silently, download weights or train automatically.',
        'Freeze the complete selected pipeline, ontology, native/scoring mappings and masks, then author/review a genuinely new structurally isolated acceptance population under pre-registered95%typed/99%execution,zero critical false execution/loss/invention andmiss<=5% gates. The pilot and V6populations are development only; protected heldout stays untouched.',
        'Review/apply the exact transport proposal only in separately authorized integration: ChoiceRequest/frontend150->500, no truncation. Production callback must use backend-issued domain/operator/source span, full accepted source and its digest, IRdigest, parser/accepted version, owner/login/library/workspace/mode,expiry andone-use binding. Preserve submitted command separately.',
        'Obtain explicit isolated Mongo namespace/write authorization before any seed/CAS test. Verify actual JWT/current membership,PUBLIC/PRIVATE patron/staff/outsider concealment,privateA/B isolation and query scope injection rejection against live authenticated endpoints.',
        'Qualify persistent accepted-source/choice lifecycle,atomicCAS,one-use consumption,duplicate/replay/stale/expired requests,crash recovery and rollback; pure adapters are insufficient.',
        'Verify real semantic provider,paired vector/catalog generation,independent relevance judgments,current index health,unavailable-global behavior and linked metadata/enrichment dependencies. No catalog reduction or HNSW/KG rebuild is currently authorized.',
        'Agree full-search/cold/warm/concurrent platform latency and memorySLOs; verify observability,failure recovery,feature flag rollout and rollback before staging PASS. Last recorded health remainsSTALE/degraded,baseline_verified=False; no fresh health check performed.',
    ]
    a=perf['results']['after'];role=devv6['source_roles'];native=devv6['native_completion']
    qa={
        'FINAL':'PARTIAL','STEP_1_STATUS':'HISTORICAL_CRITICAL_GATE_PASSED; PILOT_REVEALED_REMAINING_SEMANTIC_SAFETY_GAPS',
        'STEP_2_STATUS':'SANDBOX_AND_CONTROLS_IMPLEMENTED; LEARNED_COMPARISON_RESOURCE_BLOCKED; FRESH_ACCEPTANCE_INELIGIBLE',
        'CANDIDATE_ID':'search-smarteng-disabled-proof-7','CANDIDATE_DISABLED':True,
        'ARCHITECTURE_SELECTED':'PATH_C_NO_ARCHITECTURE_QUALIFIED; retain proof/authorization boundary, no model selected for integration',
        'PRODUCTION_READINESS':'BLOCKED','STAGING_READINESS':'BLOCKED','REMAINING_BLOCKERS':blockers,
        'ONTOLOGY_MAPPING_VALIDATED':'Shared ontology.py drives IRprojection/edit/scoring;47new ontology/source/schema tests plus inherited contracts pass. Native bound directions and negative domains retained; unknown/ambiguous edit targets reject.',
        'SOURCE_ROLE_COVERAGE':metric(role['correct'],role['denominator'],'ExposedV6 source-role annotations;50excluded'),
        'MODALITY_CORRECTNESS':metric(role['modality_correct'],role['denominator'],'ExposedV6 annotations;50excluded'),
        'MANDATORY_SOURCE_COVERAGE':'Implemented explicit source units and original-source obligations; bounded detector fails cross-book author and unfamiliar literal/language/entity forms on pilot. Not semantically complete.',
        'UNSUPPORTED_RESIDUE_HANDLING':'Known original negative metadata/date/proximity relations remain unsupported before repair; unknown detected mandatory domains block. Pilot11 cross-book author escapes detector and executes.',
        'NEGATIVE_DOMAIN_PRESERVATION':'Original domain/polarity reserved before repair; publisher/price/imprint regressions pass; V6unsupported publisher5/5contexts safely block without invented text exclusions. General relation coverage still incomplete.',
        'HARD_FILTER_INVENTION':'No executed critical hard mismatches in1334 historical exposed contexts. Pilot invented/unsupported relation reinterpretation observed; scalar absence-invention rateN/A where no mutually agreed absence oracle.',
        'HARD_FILTER_OMISSION':error['mandatory_field_mismatch_executed_contexts'],
        'EXECUTION_PROOF_STATUS':'Source/IR/projection/mutation validation and independent bounded obligation audit implemented. Internal proof does not establish linguistic entailment or completeness; pilot execution remains unsafe.',
        'SEMANTIC_PROJECTION_CORRECTNESS':{'V6_exposed_strict':devv6['summary']['strict_scored_fields'],'pilot_agreed_scalar_assertions':pilot['summaries']['deterministic']['agreed_native_field_assertions'],'limits':'Scalar/masked comparison only; structured preference equivalenceN/A; pilot3/10 executed outputs lose definite fields.'},
        'NATIVE_FIELD_IR_MAPPING':'Single canonical mapping with operator-aware native rating_min/max and year_min/max; exclusive flags rejected as independent completion operands; negative categories/text/formats distinct.',
        'NATIVE_EDIT_COMPLETION':metric(native['strict_correct'],native['contexts'],'All20exposedV6 source-owned completion scenarios; corrected stored sort accessor, original gold unchanged'),
        'NATIVE_APPLY_KEEP':'26inherited isolated native adapter tests pass,4native choice projections pass; productionKeep remains historical422, no active integration.',
        'RAW_QUERY_500_150_CONTRACT':'ActiveChoiceRequest/frontend150 unchanged; parser/session500; isolated500DTO tested8boundary checks, exact unapplied proposal retained.',
        'QUERY_RECOMPILATION':{'drafts':metric(edit['successful'],edit['timing']['count'],'Pure exposed edit timing workload'),'timing':edit['timing'],'commits':0,'full_query_reparse':True},
        'CHOICE_DURABILITY_VERIFIED':False,
        'DEVELOPMENT_CONTEXTS':{'historical_exposed':1334,'separate_pilot':18,'pilot_agreed_typed_oracles':14,'pilot_agreed_execution_oracles':17},
        'DEVELOPMENT_TYPED_ACCURACY':metric(1334,1334,'Six historical exposed cohorts; excludes new pilot'),
        'DEVELOPMENT_EXECUTION_ACCURACY':metric(1334,1334,'Six historical exposed cohorts; excludes new pilot'),
        'DEVELOPMENT_FALSE_EXECUTION':metric(0,854,'Historical exposed blocked contexts; pilot separately1/7'),
        'DEVELOPMENT_MISSED_EXECUTION':metric(0,480,'Historical exposed executable contexts; pilot separately2/10'),
        'DEVELOPMENT_STRICT_FIELD_MATCHES':{'C5C':metric(sum(x['all_scored_dimensions_correct'] for x in c5c),644,'OriginalC5C applicability masks'),**{n:d['strict_scored_fields'] for n,d in cohort.items()},'V6_exposed':devv6['summary']['strict_scored_fields']},
        'REGRESSION_TESTS_PASSED':{'reviewed_broad':1667,'additional_process_tree_runtime_tests':7,'historical_assertions_replaced':6,'unmodified_original_tests_preserved':True},
        'REGRESSION_TESTS_FAILED':0,
        'LEARNED_EXTRACTOR_COMPARISON_AUTHORIZED':'Disabled local-only evaluation authorized; additional weight downloads require explicit approval.',
        'MODELS_EVALUATED':{'completed_learned_inference_models':[],'attempted_local_model':'Qwen/Qwen2.5-3B-Instruct','learned_predictions':0,'controls':['FrozenV7deterministic','Restricted-language clarification fallback'],'encoder':'Cached encoders lack trained source-span/role/relation heads; no random-head semantic result reported'},
        'MODEL_VERSIONS':{'Qwen':'aa8e72537993ba99e69dfaafa59ed015b17504d1','runtime':load('model_audit_verified')['runtime']},
        'MODEL_LICENSES_REVIEWED':{'model':'QwenResearchLicense; local research/evaluation only,commercial deployment license not qualified','tokenizer':'Same official pinned repository materials; no separate tokenizer exception found','official_sources':load('model_audit_verified')['official_sources'],'artifact_integrity':'9/9files match official revision LFS_SHA256/gitblob metadata; initial Windows cache-link assumption failed and was retained before official verification'},
        'MODEL_DOWNLOADS_PERFORMED':0,'TRAINING_PERFORMED':False,
        'LABELING_POPULATION':{'contexts':18,'type':'Independent synthetic ontology/development pilot; no private institutional queries; no final acceptance','author_review_agreement':agreement['decision_agreement'],'native_field_agreement':agreement['native_field_agreement'],'aligned_annotations':agreement['aligned_annotation_metrics']},
        'INDEPENDENT_REVIEW_PROVENANCE':{'author':'/root/v7_pilot_author','reviewer':'/root/v7_pilot_reviewer','human_reviewers':0,'actual_runtime_model':'NOT_EXPOSED','blindness':'Reviewer had query-only packet, ontology and permitted active contracts; no candidate/predictions/author labels. Author incidental primary_match exposure disclosed. No post-prediction gold adjudication.'},
        'EXTRACTOR_SCHEMA_VALIDITY':'N/A learned outputs0/0; strict schema/source/adversarial tests passed within47new contracts. Max500input chars,32requirements,24KiB output,4096input tokens/768new tokens configured; full generated-budget adequacy unmeasured.',
        'SOURCE_SPAN_VALIDITY':{'learned':'N/A0/0 outputs','pilot_deterministic_agreed_annotations':error['source_annotation_metrics'].get('exact_source_span')},
        'MANDATORY_OMISSION_RATE':{'model':'N/A0predictions','pilot_deterministic':error['mandatory_field_mismatch_executed_contexts']},
        'MODEL_FALSE_EXECUTION':'N/A0learned predictions; safe resource rejection is not model accuracy.',
        'MODEL_MISSED_EXECUTION':'N/A0learned predictions; all18 workflow clarifications are fallback behavior only.',
        'DETERMINISTIC_COMPARISON':pilot['summaries']['deterministic'],
        'MODEL_RAM_VRAM':{'startup_process_tree_peak_bytes':capture['peak_worker_tree_rss_bytes'],'budget_bytes':capture['max_rss_bytes'],'minimum_platform_available_bytes':capture['minimum_platform_available_bytes'],'status':capture['status'],'GPU_peak':'N/A model did not finish loading','initial_inventory':load('resource_inventory')['memory']},
        'MODEL_P50_P95':'N/A0inferences;23.143seconds to guarded startup stop is not cold-load completion or inference latency.',
        'MODEL_CONCURRENCY':'Configured/tested1worker,queue0; per-query45s soft stop and480s process-tree hard deadline. Actual learned throughput/concurrencyN/A. Resource/timeout/descendant cleanup tests7/7.',
        'SELECTED_ARCHITECTURE_RATIONALE':'Neither deterministic pipeline nor an empirically tested hybrid qualifies. Proof/authorization retained; language extraction and annotation coverage still incomplete, model comparison blocked by current resource budget.',
        'FRESH_ACCEPTANCE_PERFORMED':False,'ACCEPTANCE_POPULATION_SIZE':0,'STRUCTURAL_ISOLATION_VERIFIED':'N/A fresh acceptance not attempted. Pilot is development; no sealed auditor/content/model evaluation used.',
        'INDEPENDENT_TYPED_ACCURACY':'N/A no fresh acceptance','INDEPENDENT_EXECUTION_ACCURACY':'N/A no fresh acceptance',
        'INDEPENDENT_FALSE_EXECUTION':'N/A no fresh acceptance','INDEPENDENT_MISSED_EXECUTION':'N/A no fresh acceptance',
        'INDEPENDENT_MANDATORY_CONSTRAINT_LOSS':'N/A no fresh acceptance','INDEPENDENT_HARD_FILTER_INVENTION':'N/A no fresh acceptance',
        'AMBIGUITY_RECOGNITION':devv6['summary']['per_kind_recall']['AMBIGUOUS'],
        'INCOMPLETE_RECOGNITION':devv6['summary']['per_kind_recall']['INCOMPLETE'],
        'NOTICE_RECOGNITION':devv6['summary']['per_kind_recall']['EXECUTABLE_WITH_NOTICE'],
        'RECOGNITION_COHORT':'ExposedV6development only,25perstratum; not independent acceptance.',
        'SMART_MODE_STATUS':'30pure SMART/EXACT checks pass; historical development strong, pilot semantic safety fails; activeC4unchanged.',
        'EXACT_MODE_STATUS':'Bypasses learned extraction and semantic interpretation; pure/native compatibility passes, production unchanged.',
        'GLOBAL_SEARCH_STATUS':'8actual native-function fixtures pass with synthetic provider; actual embedding relevance/current index health unavailable.',
        'PUBLIC_LIBRARY_STATUS':'PASS within40local native-function fixtures; realJWT/Mongo unverified.',
        'PRIVATE_LIBRARY_STATUS':'PASS within40local native-function fixtures including foreign-row filtering and own institutional rows; actual live auth unverified.',
        'PRIVATE_GLOBAL_INDEPENDENCE':'Own unlinked institutional records remain discoverable with globalEMPTY/INACCESSIBLE in40fixtures,no global reads on those paths. Linked enrichment/recommendation/index dependencies remain separately gated;5Mcatalog count historical,no reduction.',
        'STAFF_PATRON_AUTHORIZATION':'Offline authority doubles only; freshJWT/current membershipN/A.',
        'OUTSIDER_CONCEALMENT':'404in local fixture scenarios; not realJWT/Mongo qualification.',
        'REAL_EMBEDDING_RELEVANCE_VERIFIED':False,'REAL_MONGO_JWT_VERIFIED':False,'CURRENT_RUNTIME_HEALTH_VERIFIED':False,
        'FULL_SEARCH_LATENCY':'N/A; parser-only150exposedC5ERserial p50/p95/max %.3f/%.3f/%.3fms;4workers p95 %.3fms; no agreed operationalSLO.'%(a['serial']['p50_ms'],a['serial']['p95_ms'],a['serial']['max_ms'],a['four_workers']['p95_ms']),
        'STAGING_INTEGRATION_REQUIRED':staging,
        'PRODUCTION_PARSER_CHANGED':False,'C4_POLICY_CHANGED':False,'FRONTEND_CHANGED':False,'MONGO_MUTATIONS':0,'HNSW_REBUILDS':0,'KG_REBUILDS':0,'HELDOUT_EVALUATIONS':0,
        'HISTORICAL_EVIDENCE_PRESERVED':protection['prior'],
        'SOURCE_FILES_CHANGED':changed,
        'NEXT_ACTION':'Preserve V7 disabled. Resolve shared ontology/coverage and pilot annotation disagreements; provide resource headroom or separately approve a smaller audited local checkpoint, then run one bounded comparison. No staging,downloads,training or production activation performed automatically.',
    }
    prompt=Path(r'C:\Users\balak\.codex\attachments\a4dab033-804c-49b6-a434-4aadd1d9e461\Pasted text.txt').read_text(encoding='utf-8')
    required=re.findall(r'^- ([A-Z][A-Z_0-9]+)\s*$',prompt.split('# 22. Mandatory final QA fields')[1].split('# 23.')[0],re.M)
    assert not [k for k in required if k not in qa]
    write('final_qa',qa)

    report=f'''# LuminaR Smart Search — Combined Phase V7

28 October2026, Asia/Calcutta. Candidate `search-smarteng-disabled-proof-7` remains disabled.

**FINAL=PARTIAL. STAGING_READINESS=BLOCKED. PRODUCTION_READINESS=BLOCKED.** Historical contracts recovered, but the new pilot still exposes semantic safety failures. The local learned model never produced a prediction because its guarded startup exceeded the process-tree RAM budget. Neither architecture is qualified for integration.

## Step1 implementation and measured recovery

Recovered and verified all{protection['prior']['entries']} protected V6/prior entries before implementation. No tracked worktree/staged changes, historical gold edits or destructive reset/clean occurred. [Source map](search_proof7_source_map.json) lists exact changed paths, hashes and symbols; [preservation](search_proof7_preservation.json) verifies the41-file source freeze and49-file final comparison freeze unchanged.

The shared `ontology.py` defines canonical domains, native fields, source aliases, operand types, operators, polarity, cardinality, range/completion/scoring mapping and actual enforcement boundaries. `proposals.FAMILIES`, native completion, projection and measurement use that mapping. Min/max direction is retained through operator-aware targets; exclusive flags are not standalone operands. Publisher is distinct from publication date, negative text/category/format remain distinct, and exact literal uses the existing exact-title/identifier matcher rather than semantic similarity. Backend capability checks still control actual support.

`source_analysis.py` owns explicit source structures and audits original-source obligations separately from projected fields. It represents supported, advisory, literal, non-operative, missing, unresolved, unsupported, contradictory and unknown source units. Known negative metadata/date/proximity relations are owned before scalar grammar and spelling repair. Existing domain words cannot be distance-one repaired into another domain. Explicit label declarations can bind a later unambiguous comparator. Shared numeric algebra preserves complemented strict boundaries. Requirement roles distinguish nested filter operands from requested operations.

The parser preserves governing mandatory status, quoted literals and operator direction, with complete accepted-source reparsing. Duplicate missing evidence for one source placeholder is unified; distinct operands still require explicit editing. Whole-word exclusion owns its entire source frame in missing/completed forms, preserving untouched requirements across edits. Native completion accepts projection names through the same ontology and verifies source/IR digest, precise placeholder, full query, owner/login/library/workspace/mode/parser/accepted-version, expiry and consumed state. No client plan/offset or persistent state behavior is invented.

The original six V6 reviewed contract replacements remain unchanged. Broad regressions: **1667/1667 pass**, six exact historical nodes deselected/replaced under the inherited review. This is the1614reviewed V6baseline plus53new tests (47ontology/source/schema +6initial sandbox). A further **7/7 process-tree runtime tests** verify queue/resource/timeout/descendant cleanup behavior. Earlier import/fixture setup failures, the one intermediate association regression and development failures remain preserved. No normative gold was changed.

All six historical exposed cohorts total **1334/1334 typed and execution decisions**, false execution0/854blocked, missed valid0/480, critical executed hard mismatch0/480 under frozen masks. Strict scored context matches: C5C{qa['DEVELOPMENT_STRICT_FIELD_MATCHES']['C5C']['numerator']}/644, C5E45/90, C5ER135/150, SmartEng135/150, Comp3 135/150, exposedV6 150/150. Strict strings/masks do not establish arbitrary semantic equivalence; structured preferences remain incompletely comparable. [Changed V6 predictions](search_proof7_changed_predictions_vs_V6.json) retain every observed field/decision delta on that150cohort.

Exposed V6 source-role agreement is550/615 and modality560/615,50annotations excluded by explicit source/domain applicability rules. These are valid ontology-aware development measurements, not replacements for the frozen V6primary. Completion is **20/20 typed/execution/strict**, no commits. Independent [completion oracle review](search_proof7_completion_oracle_review.json) confirmed that gold stores `expected_completion.sort`; the earlier diagnostic read absent `expected_sort` and defaulted to relevance. V7 uses the stored key. Original V6gold, primary scorer and failed primary remain byte-identical. The earlier V7copied diagnostic with stale metadata/accessor remains historical and is superseded by the authoritative qualified development report.

The historical critical gate passed before model comparison, and candidate source froze. This enabled bounded research comparison; it did not establish generalization readiness. Later pilot failures mean **Step1 semantic recovery remains partial overall**.

## Step2 pilot, controls and local runtime result

Separate AI author/reviewer produced18distinct synthetic development queries, with34reviewed source spans. Reviewer received query-only packet and ontology/native contract slices, with no candidate, predictions, author labels or desired scores. Human reviewers0; exact runtime model identity not exposed. Author incidental exposure to the intervening `primary_match` helper is disclosed. Decision agreement **14/18**, native-field agreement **16/18**. There are28exact-aligned annotations, with domain/operator/modality/polarity28/28, operand26/28, role26/28 and state27/28 author/reviewer agreement. Both label sets are preserved; disputed dimensions were excluded rather than adjusted after predictions. This pilot diagnoses annotation difficulty and is never final acceptance.

On mutually agreed pilot oracles, the frozen deterministic control scores **11/14 typed**, **14/17 execution**, **1/7 false execution**, **2/10 missed valid**, and **18/25 agreed native scalar assertions**. Restricted supported-syntax control safely clarifies outside its declared grammar:0/14typed,7/17execution,0/7false,10/10missed. It is too restrictive for this natural-language pilot. [Comparison results](search_proof7_comparison7_results.json) keep raw model interpretations, proof outcomes and control plans separate.

The deterministic safety failure is `Find books by the same author as "A Lantern for Winter".` An unsupported cross-book author relationship becomes an author literal. The independent source detector covers known metadata/date/proximity structures but misses this relationship, allowing internal proof to accept an incomplete interpretation. Three of10 executable pilot outputs lose definite scalar requirements: unfamiliar exact-title/English wording, the punctuated author N.K.Jemisin (truncated to n), and a language condition in a disputed title-only query. Those hard-field oracles are mutually agreed even where the typed decision is disputed. A metalinguistic publisher reference also wrongly blocks a valid publication query. [Error analysis](search_proof7_error_analysis.json) preserves queries, sourceIR, masks, aligned role/span metrics and first incorrect transformations. No candidate repair was made after this pilot capture.

This is further evidence that source spans, character coverage and internally reproducible recognizers do not prove linguistic completeness. The new coverage layer repairs known omission families but is still bounded. It must not be advertised as a semantic completeness proof.

The disabled extraction interface validates immutable500-character query input, at most32requirements and24KiB output, exact source substrings, strict schema, numeric types/ranges, canonical domain/operator and negative polarity. Unknown authority keys, arbitrary generated database objects, fabricated operands, malformed outputs and omissions of detected mandatory requirements reject. Proposed roles/modality are rechecked against original source; deterministic proof/capabilities remain final gates. The interface performs no search or authorization. A correct alternative extraction can be rejected by its conservative obligation envelope; that usability cost remains to be measured.

Local inventory found cached Qwen2.5-3B-Instruct and encoders. No compatible trained encoder span/role/relation heads were found; pretrained embeddings/router heads are not a ready extraction model, and no random-head quality result was invented. The Qwen checkpoint revision is `aa8e72537993ba99e69dfaafa59ed015b17504d1`; all9cached artifacts match official pinned revision LFS/gitblob metadata. An initial cache-symlink assumption was wrong on Windows and is preserved separately from the successful official verification. [Official model card](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/blob/aa8e72537993ba99e69dfaafa59ed015b17504d1/README.md) and [research license](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct/blob/aa8e72537993ba99e69dfaafa59ed015b17504d1/LICENSE) were reviewed; this is research/evaluation use, with no commercial deployment-license qualification. Tokenizer files belong to the same pinned repository materials; no separate exception was found. Runtime versions and dependencies are recorded in [verified audit](search_proof7_model_audit_verified.json).

The model worker uses local files only, no remote code, scrubbed environment, no model-driven tools/network/application/Mongo access, and only an isolated task cache. Standard Windows platform probing is bootstrapped before query handling; a fixed non-authoritative offline username avoids a Unix-only pwd fallback. Library import/cache guard failures are retained as zero-prediction starts. The historical scalar-RSS runner monitored the Windows launcher rather than its worker; the final active [process-tree runner](../scripts/search_proof7_process_budget.py) supersedes it. Tests verify all descendants terminate on timeout/resource limits. No experiment process remains running.

With one worker, queue0,45s per-query stop,480s hard deadline,2GiB worker-tree RSS cap and2GiB minimum platform free-RAM reserve, the corrected final attempt stopped at **{capture['peak_worker_tree_rss_bytes']:,}bytes** during weight loading after **{capture['wall_ms']/1000:.3f}s**. The initial host had4,216,193,024bytes available of16,438,054,912bytes total RAM. Model loading did not complete and **learned predictions=0**. Cold-load completion, warm/inferencep50/p95, throughput, GPUpeak and semantic quality are **N/A**. Captured `generative` workflow counts are safe clarification fallbacks for absent model output, not learned-model accuracy. Earlier wrapper-RSS figures are not model memory measurements. No additional weights were downloaded, no training/private data/remote inference or live model activation occurred.

## Architecture and acceptance decision

**PathC: no architecture qualified.** Deterministic historical recovery is useful, but unfamiliar source roles/relationships still lose mandatory meaning. The learned alternative has no empirical accuracy result because guarded startup is resource-blocked; it cannot be claimed better or worse. Retain deterministic proof and authenticated backend authority, with no production model selection. Do not keep adding disconnected phrase exceptions or automatically launch large synthetic labeling/training.

The smallest next work is to resolve the shared representation/coverage gaps and independent annotation disagreements, then obtain adequate resource headroom or separately approve a smaller audited local checkpoint. Reuse the bounded local harness; do not silently relax platform reserves or infer capacity from parameter count. A small additional reviewed annotation pilot should establish schema consistency/labeling difficulty before dataset sizing. No automatic large dataset is prescribed.

No fresh final acceptance was performed, no acceptance population consumed and no protected sealed material accessed/evaluated. Model-selection/development pilot observations cannot become fresh acceptance. Only after a complete candidate passes semantic safety, mapping and annotation gates should a new independently authored/reviewed structurally isolated population be frozen and scored under unchanged95%typed/99%execution,zero critical false execution/loss/invention,miss<=5% thresholds.

## Native scope, performance and integration boundaries

Forty hash-verified actual native-function local fixtures coverPUBLIC/PRIVATE patron/staff, own unlinked rows, foreign-row filtering, outsider404 and globalEMPTY/INACCESSIBLE. Eight global fixtures verify filter/topic/hydration/serialization/pagination with a synthetic semantic provider; four choice projections and30pure SMART/EXACT plus8schema boundaries pass. Exact mode bypasses semantic extraction. These fixtures do not qualify actual JWT/current membership, Mongo transactions/CAS or real embedding relevance. Private own unlinked records operate without global reads in the fixtures; linked enrichment/recommendation/generation dependencies remain gated. The5Mglobal count is historical; no reduction occurred.

On the recorded Ryzen7 260 (8cores/16logical),16.4GBRAM, RTX5060LaptopGPU8,151MiB Windows/Python3.11.9 host, matched exposedC5ER150 warm serial +150four-worker runs yield V7p50={a['serial']['p50_ms']:.3f}ms,p95={a['serial']['p95_ms']:.3f}ms,max={a['serial']['max_ms']:.3f}ms;4workerp95={a['four_workers']['p95_ms']:.3f}ms,max={a['four_workers']['max_ms']:.3f}ms. Actual matched V6serialp5027.075ms/p9569.772ms,4workerp95273.568ms. V7errors0/300;serial/concurrent complete plans150/150equal. CPU10,890.625ms,wall11,284.696ms,RSS37,920,768→38,305,792bytes. Pure edit60/60,p5010.868ms,p9514.582ms,max15.555ms. Single shared-host warm measurements have no statisticalCI or agreed operationalSLO; full-search/relevance latency remainsN/A.

The active150-character choice/frontend contract remains unchanged; [exact transport patch](search_proof7_transport_proposal.patch) is unapplied. Widening alone does not implement accepted-source lifecycle. Exact subsequent prerequisites are in [finalQA](search_proof7_final_qa.json): semantic/annotation qualification; a measured bounded extractor comparison if pursued; completely frozen independent acceptance;500-character transport; backend-owned full accepted source/IRdigest/version/owner/library/mode/expiry/one-use state; separately authorized isolated Mongo writes; realJWT/membership/CAS/crash recovery; real paired vectors/relevance/current health; full concurrent platformSLO/observability/featureflag/rollback. Production correctionKeep remains422until reviewed integration.

Production parser/C4/frontend/authentication/Qwen/RAG/recommendations/MoreLikeThis/borrowing/inventory unchanged. Mongo mutations0,HNSW/KGrebuilds0,heldout evaluations0. Last recorded global health remainsSTALE/degraded,baseline_verified=False; no current health claim or side-effecting status poll. All{protection['prior']['entries']}protected entries remain intact. The full required QA fields and cohort denominators are in [finalQA](search_proof7_final_qa.json). Stop before unauthorized staging, download, training or deployment.
'''
    with (R/'search_proof7_final_report.md').open('x',encoding='utf-8') as f:f.write(report)
    paths=set()
    for directory in ['reports','scripts']:
        paths.update(p for p in (ROOT/directory).glob('search_proof7_*') if p.is_file())
    for directory in ['search_proof_recovery_v7','search_proof7_regression','search_proof7_history','search_proof7_runtime_tests']:
        paths.update(p for p in (ROOT/'scratch'/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    # Keep isolated runtime cache files too, excluding unstable bytecode caches.
    for directory in (ROOT/'scratch').glob('search_proof7_runtime_attempt*'):
        paths.update(p for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    manifest={'candidate_id':'search-smarteng-disabled-proof-7','files':{str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)},'previous_protected_entries':protection['prior']['entries'],'self_hash_policy':'Excludes manifest and subsequent verification to avoid cycles','FINAL':'PARTIAL'}
    write('freeze_manifest',manifest);frozen=verify(manifest['files']);assert frozen['verified']
    write('freeze_verification',{'frozen':frozen,'manifest_sha256':sha(R/'search_proof7_freeze_manifest.json'),'preservation':protection,'required_QA_fields':len(required),'all_required_fields_present':True})
    print(json.dumps({'FINAL':'PARTIAL','protected':protection['prior']['entries'],'new_evidence_entries':frozen['entries'],'required_QA_fields':len(required),'pilot':pilot['summaries']['deterministic'],'model_predictions':0,'source_changes':len(changed)}))


if __name__=='__main__':main()
