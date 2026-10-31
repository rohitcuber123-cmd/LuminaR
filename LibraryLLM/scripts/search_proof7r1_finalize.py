"""Finalize the authorized V7 continuation without replacing any prior evidence."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,re,ast,subprocess,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports';P='search_proof7r1_'
def load(name):return json.loads((R/(P+name+'.json')).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def write(name,data):
    with (R/(P+name+'.json')).open('x',encoding='utf-8') as stream:json.dump(data,stream,indent=2,ensure_ascii=False)
def verify(files):
    bad=[p for p,h in files.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    return {'entries':len(files),'verified':not bad,'failures':bad}


def main():
    pre=load('preflight');frozen=load('source_freeze');pilot=load('pilot_frozen_results');resource=load('model_resource_gate')
    v6=load('frozen_v6_exposed_results');perf=load('recorded_performance')['results'];edit=load('recompilation_timing')
    tests=next(ET.parse(R/(P+'frozen_tests.xml')).getroot().iter('testsuite')).attrib
    assert tests['failures']==tests['errors']=='0' and int(tests['tests'])==1696
    assert pilot['execution']=={'numerator':18,'denominator':18} and pilot['native_field_assertions']['numerator']==29
    cohorts={k:load('frozen_'+k+'_results')['summary'] for k in ['c5e90','c5er150','smarteng150','comp3_150']}
    assert all(d['typed_accuracy']['numerator']==d['contexts'] and not d['critical_executed_operand_case_ids'] for d in cohorts.values())
    c5c=[json.loads(s) for s in (R/(P+'c5c_frozen_scored_observations.jsonl')).read_text(encoding='utf-8').splitlines()]
    assert len(c5c)==644 and all(x['typed_correct'] and x['execution_correct'] for x in c5c)
    preserved={'at_utc':datetime.now(timezone.utc).isoformat(),'prior':verify(pre['protected_files']),'candidate_source':verify(frozen['files']),
        'tracked_diff':subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).splitlines(),
        'staged_diff':subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT,text=True).splitlines(),
        'production_activation':False,'Mongo_mutations':0,'HNSW_rebuilds':0,'KG_rebuilds':0,'heldout_evaluations':0,'model_downloads':0,'training':False,'new_model_inferences':0}
    assert preserved['prior']['verified'] and preserved['candidate_source']['verified'] and not preserved['tracked_diff'] and not preserved['staged_diff']
    write('preservation',preserved)
    parent=json.loads((R/'search_proof7_source_freeze.json').read_text(encoding='utf-8'))['files']
    byname={Path(p).name:h for p,h in parent.items() if 'search_proof_recovery_v7' in p}
    changed=[{'path':str(ROOT/p),'sha256':h,'change':'ADDED' if Path(p).name not in byname else 'MODIFIED_FROM_FROZEN_V7'} for p,h in frozen['files'].items() if 'search_proof_recovery_v7r1' in p and byname.get(Path(p).name)!=h]
    symbols=[]
    for p,h in frozen['files'].items():
        tree=ast.parse((ROOT/p).read_text(encoding='utf-8'));symbols.append({'path':str(ROOT/p),'sha256':h,'symbols':[{'name':n.name,'line':n.lineno} for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]})
    write('source_map',{'candidate_id':'search-smarteng-disabled-proof-7r1','files':symbols,'changed_files':changed})
    old=json.loads((R/'search_proof7_comparison7_results.json').read_text(encoding='utf-8'));current={x['id']:x for x in pilot['records']}
    raw_known=[x for x in old['records'] if x['decision_oracle'] is not None];raw_exe=[x for x in old['records'] if x['executable_oracle'] is not None]
    comparison={'population':'EXPOSED_PILOT_DEVELOPMENT_ONLY','original_V7_oracles_unchanged':True,'raw_comparable':{
        'V7_typed':{'numerator':11,'denominator':14},'R1_typed':{'numerator':sum(current[x['id']]['actual_decision']==x['decision_oracle'] for x in raw_known),'denominator':len(raw_known)},
        'V7_execution':{'numerator':14,'denominator':17},'R1_execution':{'numerator':sum(current[x['id']]['actual_execution']==x['executable_oracle'] for x in raw_exe),'denominator':len(raw_exe)}},
        'adjudicated_R1':{k:pilot[k] for k in ['typed','execution','false_execution','missed_execution','native_field_assertions','critical_executed_field_mismatches']},
        'review_limit':'Adjudicator was original independent reviewer, blind to outcomes; not a third reviewer.07/18 unsupported enforcement and13diagnostic bounds resolved from active contracts;03/14 exact notice subtype remains excluded. Original gold untouched.',
        'fresh_acceptance':False,'learned_quality':'N/A;0new inferences, resource preflight blocked'}
    write('comparison',comparison)
    write('step1_exit_gate',{'candidate_id':'search-smarteng-disabled-proof-7r1','status':'PASS_KNOWN_EXPOSED_CRITICAL_DEVELOPMENT_GATES','regression_passed':1696,'regression_failed':0,'reviewed_legacy_replacements':6,'historical_exposed':'1334/1334typed/execution;0/854false;0/480missed and critical executed mismatch','pilot':comparison['adjudicated_R1'],'native_completion':'20/20typed/execution/strict','source_files':43,'generalization_qualified':False,'fresh_acceptance_eligible':False,'reason':'Learned comparison unavailable; source-role agreement incomplete; exposed development cannot establish independent generalization.'})
    qa=json.loads((R/'search_proof7_final_qa.json').read_text(encoding='utf-8'))
    blockers=['Learned comparison remains unavailable: current freeRAM %.3fGiB is below the proposed3GiB worker-tree budget plus2GiB platform reserve and0.5GiB startup margin. No new model process or prediction.'%(resource['available_RAM_bytes']/1024**3),
        'No fresh independent acceptance; historical and18pilot cases are exposed development. Two pilot notice subtypes remain unscored, not forced to match predictions.',
        'Source-role/modality agreement remains550/615 and560/615 on exposedV6 annotations,50excluded. Coverage is finite and does not prove arbitrary semantic completeness.',
        'Production500-character transport/accepted-source lifecycle, realJWT/current membership, MongoCAS/one-use durability, real vector relevance/current health and operationalSLO remain unqualified.']
    qa.update({
        'FINAL':'PARTIAL','STEP_1_STATUS':'PASS_KNOWN_EXPOSED_CRITICAL_DEVELOPMENT_GATES; GENERALIZATION_UNQUALIFIED','STEP_2_STATUS':'INTERFACE_AND_PILOT_RECOVERED; LEARNED_COMPARISON_RESOURCE_BLOCKED; FRESH_ACCEPTANCE_NOT_PERFORMED',
        'CANDIDATE_ID':'search-smarteng-disabled-proof-7r1','CANDIDATE_DISABLED':True,'ARCHITECTURE_SELECTED':'DISABLED_DETERMINISTIC_CONTROL; NO_INTEGRATION_ARCHITECTURE_QUALIFIED',
        'PRODUCTION_READINESS':'BLOCKED','STAGING_READINESS':'BLOCKED','REMAINING_BLOCKERS':blockers,
        'ONTOLOGY_MAPPING_VALIDATED':'Inherited shared ontology plus explicit sort-direction capabilities and licensed ratings plural. New lexical source nodes distinguish scalar operands, external record references, explicit record unions, field-reference prefixes and unsupported enforcement. 1696reviewed tests pass.',
        'MANDATORY_SOURCE_COVERAGE':'Source-unit and lexical-frame obligations checked independently against IR field/operator/value/spans. New deletion tests cover exact literal, language and initialled author. Pilot0/10executed scalar mismatches; finite language/reference grammar only, not an NLP completeness proof.',
        'UNSUPPORTED_RESIDUE_HANDLING':'Cross-record references and record unions block as unsupported. Publisher-agent requests cannot become authors; unsupported sort directions cannot become author operands. Unknown detected mandatory obligations still block.',
        'NEGATIVE_DOMAIN_PRESERVATION':'Original negative publisher/domain and explicitNOT polarity preserved before scalar extraction/repair; new publisher-agent test confirms no author/text exclusion invention. General semantic completeness unproven.',
        'HARD_FILTER_INVENTION':'No critical executed hard mismatch in1334historical contexts or10executed pilot outputs under frozen/adjudicated masks. No universal absence/invention rate asserted for partially applicable historical blocked fields.',
        'HARD_FILTER_OMISSION':pilot['critical_executed_field_mismatches'],
        'EXECUTION_PROOF_STATUS':'Source/IR/projection checks plus independent lexical obligations pass known development. Source ownership/reference graph and native enforcement checked before projection; no general linguistic completeness claim.',
        'SEMANTIC_PROJECTION_CORRECTNESS':{'V6_exposed':v6['summary']['strict_scored_fields'],'pilot':pilot['native_field_assertions'],'pilot_executed_mismatch':pilot['critical_executed_field_mismatches'],'limits':'Masked scalar metrics only; structured preference equivalence unavailable.'},
        'NATIVE_FIELD_IR_MAPPING':'Shared operator-aware ontology remains authoritative; exact-title equality distinct from title_text title-or-author lookup. Explicit title-only substring requests safely reject because native enforcement is broader.',
        'NATIVE_EDIT_COMPLETION':{'numerator':20,'denominator':20,'cohort':'All exposedV6 completions; typed/execution/strict each20/20; no persistent commit'},
        'QUERY_RECOMPILATION':{'drafts':{'numerator':edit['successful'],'denominator':edit['timing']['count']},'timing':edit['timing'],'full_reparse':True,'commits':0},
        'DEVELOPMENT_CONTEXTS':{'historical_exposed':1334,'pilot_separate':18,'adjudicated_pilot_typed_oracles':16,'pilot_execution_oracles':18},
        'DEVELOPMENT_STRICT_FIELD_MATCHES':{'C5C':{'numerator':sum(x['all_scored_dimensions_correct'] for x in c5c),'denominator':644},**{k:v['strict_scored_fields'] for k,v in cohorts.items()},'V6_exposed':v6['summary']['strict_scored_fields']},
        'REGRESSION_TESTS_PASSED':{'reviewed_broad':1696,'six_reviewed_replacements_unchanged':True,'included_process_tree_tests':7,'new_source_unit_tests':28},'REGRESSION_TESTS_FAILED':0,
        'MODELS_EVALUATED':{'new_learned_models':[],'new_learned_predictions':0,'existing_candidate_audited_in_V7':'Qwen/Qwen2.5-3B-Instruct at pinned revision','controls':'V7 and7r1 on same exposed pilot','encoder':'No trained search span/role/relation heads available'},
        'LABELING_POPULATION':{'contexts':18,'type':'Existing exposed development pilot; no new acceptance population','original_decision_agreement':'14/18','original_native_field_agreement':'16/18','adjudication':'5disputed rows source-reviewed; 2notice subtypes remain unresolved; new derived view preserves originals'},
        'INDEPENDENT_REVIEW_PROVENANCE':{'original_author':'/root/v7_pilot_author','original_reviewer_and_adjudicator':'/root/v7_pilot_reviewer','human_reviewers':0,'actual_runtime_model':'NOT_EXPOSED','adjudication_blind_to_candidate_outcomes':True,'independence_limit':'Same original reviewer, not a third independent adjudicator; known development only'},
        'EXTRACTOR_SCHEMA_VALIDITY':'N/A0new learned outputs; inherited strict500-character/32requirement/24KiB schema and adversarial tests pass. Actual generated token-budget adequacy remains unmeasured.',
        'SOURCE_SPAN_VALIDITY':'Exact source/unit tests pass for quoted punctuation, initials, Unicode and lexical obligations; learned output0/0N/A. No broad source-role accuracy inferred from span validity.',
        'MANDATORY_OMISSION_RATE':{'learned':'N/A0predictions','pilot_executed_scalar_mismatches':pilot['critical_executed_field_mismatches']},
        'MODEL_FALSE_EXECUTION':'N/A0new learned predictions','MODEL_MISSED_EXECUTION':'N/A0new learned predictions',
        'DETERMINISTIC_COMPARISON':comparison,
        'MODEL_RAM_VRAM':resource,'MODEL_P50_P95':'N/A; resource preflight blocked before child launch. Prior V7failed startup is preserved and is not inference latency.',
        'MODEL_CONCURRENCY':'One worker,queue0,full process-tree memory/timeout/cleanup in candidate sandbox.py;7tests pass. New learned concurrency/throughputN/A.',
        'SELECTED_ARCHITECTURE_RATIONALE':'Known pilot safety failures repaired through lexical operand/reference ownership and backend capability checks. Exposed success does not establish generalization; no empirical learned comparison or fresh acceptance available.',
        'FULL_SEARCH_LATENCY':'N/A. Matched150exposedC5ER warm parser-only: R1p50 %.3fms,p95 %.3fms,max %.3fms;4workerp95 %.3fms. No agreed operationalSLO.'%(perf['after']['serial']['p50_ms'],perf['after']['serial']['p95_ms'],perf['after']['serial']['max_ms'],perf['after']['four_workers']['p95_ms']),
        'SMART_MODE_STATUS':'Historical andpilot exposed critical gates pass;40local/8global native fixtures and30mode checks pass. ActiveC4unchanged; independent generalization unqualified.',
        'HISTORICAL_EVIDENCE_PRESERVED':preserved['prior'],'SOURCE_FILES_CHANGED':changed,
        'NEXT_ACTION':'Provide adequate RAM headroom for a bounded local comparison of existing pinned weights, or explicitly approve a smaller audited public checkpoint if needed; do not download automatically. Resolve remaining notice/source-role contract gaps, freeze the selected complete pipeline, and use a genuinely new independent acceptance population before staging.',
    })
    qa['STAGING_INTEGRATION_REQUIRED'][0]='Do not treat the repaired exposed pilot as independent generalization. Complete a resource-safe learned comparison if pursued, validate remaining role/notice contracts, then qualify a frozen selected pipeline on genuinely new independent acceptance.'
    qa['STAGING_INTEGRATION_REQUIRED'][2]='Provide RAM headroom for the prior pinned3B checkpoint under an explicit worker-tree budget/platform reserve, or separately approve a smaller audited checkpoint. Current resource gate blocked; no weights downloaded, no training or remote inference.'
    # Do not inherit the prior failure counts or any claim that a model ran now.
    required=re.findall(r'^- ([A-Z][A-Z_0-9]+)\s*$',Path(r'C:\Users\balak\.codex\attachments\ca716b6a-f7e3-458e-8b51-40b7b3599e67\Pasted text.txt').read_text(encoding='utf-8').split('# 22. Mandatory final QA fields')[1].split('# 23.')[0],re.M)
    assert not [k for k in required if k not in qa]
    write('final_qa',qa)
    report=f'''# LuminaR — V7 continuation, disabled revision7r1

28October2026 (Asia/Calcutta). **FINAL=PARTIAL. STAGING_READINESS=BLOCKED. PRODUCTION_READINESS=BLOCKED.**

The resubmitted attachment is byte-identical to the earlier V7prompt. This continuation preserves frozenV7 and repairs its remaining known pilot safety families in `search-smarteng-disabled-proof-7r1`; it does not restart fromV6 or overwrite prior evidence. All{preserved['prior']['entries']}protected entries verify unchanged. No production parser/C4/frontend/authentication/Qwen/RAG/database/index changes, weight downloads, training, remote inference or heldout evaluation occurred.

## What changed

`source_units.py` supplies source-preserving tokens, quoted/initialled entity boundaries, clause spans and typed operand/reference frames. Initials and quoted punctuation no longer become sentence boundaries. A comparative domain referring to another book stays a cross-record relation, rather than becoming an author/title scalar. Complete record-predicate unions are distinct from an unresolved operand choice. Field/concept reference prefixes do not become publisher exclusions. Explicit exact-title and finite supported-language frames carry enforceable operands, while unsupported title-only substring and sort-direction requests retain their enforcement limitations. `title_text` still has the active title-or-author predicate; this revision does not pretend it can enforce title-only substring matching.

The original-source coverage audit checks these lexical frames against represented field/operator/value/span obligations. Deleting a literal,language or initialled author requirement causes proof rejection in mutation tests. Background example scope survives commas; an unqualified current note cannot silently discharge a mandatory requirement. Publisher agents remain distinct from authors, andNOTpolarity survives the pipeline. The ontology now records fixed native sort directions and the already licensed plural `ratings`; valid inflection no longer creates a spurious spelling-repair notice. Shared numeric source `_RATING_FIELD` already licenses ratings?, so no test gold was changed to obtain that behavior.

The process-tree runner is now directly incorporated in the disabled candidate; its7queue/resource/timeout/descendant-cleanup tests pass. The strict extraction interface and source-bound edit compiler remain isolated and disabled. [Source map](search_proof7r1_source_map.json) contains exact file changes, hashes and symbol locations. Source coverage is finite, with a finite language vocabulary; valid spans and complete character coverage do not prove arbitrary linguistic completeness.

## Development validation

**1696/1696 reviewed regression tests pass**, including28new lexical/source-unit tests and7process-tree tests. The original six reviewed V6replacement assertions remain unchanged; six exact historical nodes are still transparently deselected in the inherited migration ledger. The intermediate1691/1693run exposed background comma scope and publisher-prefix ownership defects; its evidence and source snapshot remain preserved. These were repaired before the final freeze.

All six historical exposed cohorts retain **1334/1334 typed and execution decisions**, false execution0/854blocked, missed valid0/480, and zero critical executed hard mismatches under the frozen masks. Strict scored context matches remain C5C235/644,C5E45/90,C5ER135/150,SmartEng135/150,Comp3 135/150,exposedV6 150/150. Strict scalar equality is not universal semantic equivalence, and structured preferences remain incompletely comparable. ExposedV6 source-role/modality agreement remains550/615 and560/615,50annotations excluded. Native source-owned completion remains **20/20 typed/execution/strict**, with full-query reparse and no persistent commits. Pure edit drafts remain60/60. Original gold and frozen failed primary results are unchanged.

On the **same original mutually agreed pilot oracles**, typed agreement improves11/14→14/14 and execution14/17→17/17. Separately, a source-only contract adjudication resolves the explicit recordOR and title-only enforcement cases asUNSUPPORTED and retains contradiction diagnostic bounds. The adjudicator is the original independent reviewer, blind to candidate outcomes, not a third reviewer. Both original author/reviewer label sets remain intact. Rows03/14 notice subtype remainsUNRESOLVED and excluded; their executable eligibility and definite fields are resolved. No human review is claimed.

Under that explicitly versioned **development-only derived view**, the final revision achieves **16/16 scored typed decisions**, **18/18 execution**, **0/8 false executions**, **0/10 missed valid**, **29/29 definite scalar assertions**, and **0/10 critical executed field mismatches**. Thus the prior cross-book false execution and three executed field-loss contexts are repaired. [Pilot comparison](search_proof7r1_comparison.json), [complete pilot observations](search_proof7r1_pilot_frozen_results.json) and [contract adjudication](search_proof7r1_pilot_contract_adjudication.json) make the changed oracle applicability and raw comparable denominators explicit. These18queries are exposed development, not fresh acceptance. No new acceptance population was consumed.

## Learned comparison and architecture boundary

The prior official model/revision/license/runtime audit is preserved: cachedQwen2.5-3B-Instruct at`aa8e72537993ba99e69dfaafa59ed015b17504d1`, with9artifact hashes verified against official revision metadata. Its research-license/commercial-integration limitations remain unresolved for production. Cached encoders still lack trained search span/role/relation heads; no random-head extraction result or training was invented.

Current preflight observes **{resource['available_RAM_bytes']:,}bytes available RAM**. The proposed bounded worker budget3GiB plus2GiB platform reserve and0.5GiB startup margin requires{resource['required_available_bytes']:,}bytes available. That proposed headroom follows the preserved V7startup failure above2GiB; it is not a capacity guarantee. The [resource gate](search_proof7r1_model_resource_gate.json) blocks before launching a child: **new model predictions0**, downloads0,training0. Learned accuracy,source-span quality,malformed-output rate,warm/cold inference latency,CPU/GPUload and throughput areN/A. No reserve was silently relaxed and no other application was closed.

Keep the deterministic proof/compiler as the disabled control. No production/integration architecture is qualified yet: successful exposed repairs do not demonstrate unfamiliar-language generalization, and the learned comparison still has no measured predictions. Additional public weights require explicit approval; sufficient RAM headroom may allow testing the already cached checkpoint without a download. Any future extractor may only propose requirements; it cannot choose tenant authority, execute tools, access institutional data/Mongo or bypass source/proof/capability checks. EXACT continues to bypass semantic extraction.

## Native compatibility, performance and next gates

Current final-source qualification passes40local actual native-function fixtures (PUBLIC/PRIVATE patron/staff, foreign filtering, outsider404,own unlinked rows with globalEMPTY/INACCESSIBLE),8global fixtures using a synthetic semantic provider,4choice projections,30SMART/EXACT mode checks and8schema-boundary checks. These are offline doubles around hash-verified functions, not actualJWT/current membership,MongoCAS/one-use durability or real embedding relevance. Private own unlinked records remain independent of global fixture size; linked enrichment/recommendation/index dependencies are separately gated. No historical5Mcatalog reduction occurred.

Matched150exposedC5ERwarm serial+150four-worker parses compare frozenV7with7r1. V7serialp50/p95={perf['before']['serial']['p50_ms']:.3f}/{perf['before']['serial']['p95_ms']:.3f}ms;7r1={perf['after']['serial']['p50_ms']:.3f}/{perf['after']['serial']['p95_ms']:.3f}ms,max={perf['after']['serial']['max_ms']:.3f}ms. Four-workerp95={perf['after']['four_workers']['p95_ms']:.3f}ms,max={perf['after']['four_workers']['max_ms']:.3f}ms;errors0/300,serial/concurrent complete-plan equality150/150. Pure edit60draftsp50/p95/max={edit['timing']['p50_ms']:.3f}/{edit['timing']['p95_ms']:.3f}/{edit['timing']['max_ms']:.3f}ms. Shared-host warm measurements have no statisticalCI or agreed operationalSLO. Full-search/relevance latency remainsN/A; last recorded LuminaRhealth staysSTALE/degraded,baseline_verified=False,with no side-effecting health poll.

The unchanged active150-character choice/frontend limit still needs separately authorized500-character integration. The inherited exact unapplied patch and staging prerequisites remain available through [complete finalQA](search_proof7r1_final_qa.json): accepted full source/IRdigest/version/owner/library/mode/expiry/one-use lifecycle; explicit isolated Mongo-write authorization; realJWT/membership/CAS/replay/crash recovery; real paired vectors/relevance/current health; full concurrent platformSLO,observability,featureflag and rollback. No staging or deployment was performed.

Next: obtain resource headroom or separately approve a smaller audited local checkpoint, complete the actual bounded comparison, resolve remaining role/notice contract uncertainty, and freeze the selected complete pipeline before a genuinely new independent acceptance population. All83mandatory QA fields and cohort denominators are in [finalQA](search_proof7r1_final_qa.json). [Preservation audit](search_proof7r1_preservation.json) verifies prior evidence and current43source/dependency files.
'''
    with (R/(P+'final_report.md')).open('x',encoding='utf-8') as stream:stream.write(report)
    paths=set()
    for directory in ['reports','scripts']:paths.update(p for p in (ROOT/directory).glob('search_proof7r1_*') if p.is_file())
    for directory in ['search_proof_recovery_v7r1','search_proof7r1_regression','search_proof7r1_history']:
        paths.update(p for p in (ROOT/'scratch'/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    manifest={'candidate_id':'search-smarteng-disabled-proof-7r1','files':{str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)},'previous_protected_entries':preserved['prior']['entries'],'self_hash_policy':'Excludes self and subsequent verification to avoid cycles','FINAL':'PARTIAL'}
    write('freeze_manifest',manifest);checked=verify(manifest['files']);assert checked['verified']
    write('freeze_verification',{'frozen':checked,'manifest_sha256':sha(R/(P+'freeze_manifest.json')),'preservation':preserved,'required_QA_fields':len(required),'all_present':True})
    print(json.dumps({'FINAL':'PARTIAL','previous_verified':preserved['prior']['entries'],'new_frozen':checked['entries'],'regression_passed':1696,'pilot':comparison['adjudicated_R1'],'model_calls':0,'QA_fields':len(required)}))


if __name__=='__main__':main()
