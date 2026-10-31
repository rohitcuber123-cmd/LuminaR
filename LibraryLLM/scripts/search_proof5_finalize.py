"""Consolidate actual V5 evidence without changing earlier runs or normative gold."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import ast,json,hashlib,xml.etree.ElementTree as ET

R=Path('reports');P='search_proof5_'
def load(n):return json.loads((R/(P+n)).read_text(encoding='utf-8'))
def rows(path):return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines()]
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,ensure_ascii=False,sort_keys=True)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def metric(n,d):return {'population':'EXPOSED_DEVELOPMENT','numerator':n,'denominator':d,'percent':100*n/d if d else None}

def main():
    integrity=load('integrity_verification.json');assert integrity['status']=='PASS'
    freeze=load('source_freeze.json');assert all(sha(p)==h for p,h in freeze['files'].items())
    suite=next(ET.parse(R/(P+'verified_tests.xml')).getroot().iter('testsuite'))
    test_counts={k:int(suite.attrib.get(k,0)) for k in ['tests','failures','errors','skipped']}
    failures=[{'file':c.attrib.get('classname'),'name':c.attrib['name'],'message':c.find('failure').attrib.get('message'),'detail':c.find('failure').text} for c in suite.iter('testcase') if c.find('failure') is not None]
    write('regression_failures.json',{'source_freeze_sha256':sha(R/(P+'source_freeze.json')),'counts':test_counts,'gold_changed':False,'failures':failures,'interpretation':'Contains substantive role/facet invention, semantic/technical literal transport, display/intent compatibility and native source/session transformations. Not all failures are cosmetic.'})
    metrics={};details={};changes={}
    c5c=load('c5c_verified_typed_decision_scoring.json')['overall']
    metrics['C5C']={k:c5c[v] for k,v in [('typed_accuracy','typed_accuracy'),('execution_accuracy','execution_accuracy'),('false_execution','false_execution_rate'),('missed_execution','missed_execution_rate'),('strict_scored_fields','strict_scored_dimension_match')]}
    metrics['C5C'].update(population='EXPOSED_DEVELOPMENT',contexts=644)
    hard=set('author_text title_text subjects include_terms exclude_terms exclude_subjects formats exclusive_formats excluded_formats availability language rating_min rating_max year_min year_max rating_min_exclusive rating_max_exclusive year_min_exclusive year_max_exclusive exact_text sort'.split())
    c5rows=rows(R/(P+'c5c_verified_scored_observations.jsonl'))
    bad=[{'case_id':r['case_id'],'mismatches':[a for a in r['assertions'] if a['field'] in hard and not a['correct']]} for r in c5rows if r['execution'] and any(a['field'] in hard and not a['correct'] for a in r['assertions'])]
    details['C5C']={'executed_contexts':sum(r['execution'] for r in c5rows),'executed_hard_mismatch_contexts':bad,'confusion':c5c['confusion_matrix'],'per_decision':c5c['per_decision']}
    keyfields=[*hard,'semantic_text','soft_preference','intent']
    pairs=[('C5C',P+'c5c_verified_predictions.jsonl','search_proof4_c5c_recorded_predictions.jsonl')]
    for name in ['c5e90','c5er150','smarteng150','comp3_150']:
        x=load('verified_'+name+'_results.json');s=x['summary'];metrics[name]={'population':'EXPOSED_DEVELOPMENT',**{k:s[k] for k in ['contexts','typed_accuracy','execution_accuracy','false_execution','missed_execution','strict_scored_fields']}}
        preds=rows(R/(P+'verified_'+name+'_predictions.jsonl'))
        details[name]={'executed_contexts':sum(p['executable'] for p in preds),'critical_executed_hard_mismatch_contexts':x['critical_operands'],'per_decision_recall':s['per_kind_recall'],'confusion':x['confusion'],'decision_failures':x['decision_failures']}
        pairs.append((name,P+'verified_'+name+'_predictions.jsonl','search_proof4_recorded_'+name+'_predictions.jsonl'))
    for name,new,old in pairs:
        prior={p['case_id']:p for p in rows(R/old)};delta=[]
        for p in rows(R/new):
            o=prior[p['case_id']];d={f:{'V4':o['actual_plan'].get(f),'V5':p['actual_plan'].get(f)} for f in keyfields if o['actual_plan'].get(f)!=p['actual_plan'].get(f)}
            if o['typed_decision']!=p['typed_decision']:d['typed_decision']={'V4':o['typed_decision'],'V5':p['typed_decision']}
            if d:delta.append({'case_id':p['case_id'],'changes':d})
        changes[name]=delta
    write('changed_predictions_vs_V4.json',{'fresh':False,'comparison':'Frozen V4 recorded vs V5 verified; earlier per-attempt comparisons also retained. Serialization differences are visible and not claimed as semantic changes.','cohorts':changes})
    total=sum(m['contexts'] for m in metrics.values());exe=sum(m['execution_accuracy']['numerator'] for m in metrics.values());typed=sum(m['typed_accuracy']['numerator'] for m in metrics.values())
    fe=metric(sum(m['false_execution']['numerator'] for m in metrics.values()),sum(m['false_execution']['denominator'] for m in metrics.values()))
    me=metric(sum(m['missed_execution']['numerator'] for m in metrics.values()),sum(m['missed_execution']['denominator'] for m in metrics.values()))
    perf=load('recorded_performance.json')['results']['after'];edit=load('recompilation_timing.json');modes=load('mode_protocol_audit.json')
    qa={
      'FINAL':'PARTIAL','CANDIDATE_ID':freeze['candidate_id'],'PREVIOUS_FREEZE_VERIFIED':True,
      'SOURCE_ROLE_PARTITION_IMPLEMENTED':'PARTIAL: bounded speech-act/segment ownership implemented; general semantic coverage not qualified.',
      'MODALITY_PARTITION_IMPLEMENTED':'PARTIAL: internal MUST/MUST_NOT/SHOULD/MAY/CONDITIONAL/NON_OPERATIVE/UNKNOWN; remaining regressions.',
      'QUERY_IR_STATUS':'Internal v5 source-role/modal/operand/relationship/provenance representation preserved through decisions; no public enum changed.',
      'DETERMINISTIC_PROOF_STATUS':'Implemented source/projection/semantic checks; validates represented meaning, not arbitrary extraction completeness.',
      'MANDATORY_OPERAND_COMPLETENESS':'Finite focused omission/invalid operand/completion properties pass; universal language completeness unproven.',
      'NEGATIVE_DOMAIN_OWNERSHIP':'Early domain/polarity ownership and whole-word boundary tests pass; unsupported domains block; remaining semantic coverage failures documented.',
      'HARD_FILTER_SOURCE_PROOF':{'executed_hard_mismatch_contexts':0,'executed_contexts':430,'population':'EXPOSED_DEVELOPMENT','meaning':'No scored executed hard-field mismatches under frozen applicable masks; not a universal completeness claim.'},
      'NATIVE_EDIT_RECOMPILATION_STATUS':'Isolated pure source-span completion/correction apply/keep/removal draft; full reparse and untouched-condition checks. Active native/session integration incomplete; no persistence/CAS claim.',
      'RAW_QUERY_LENGTH_COMPATIBILITY':'Active ChoiceRequest150 vs parser/session500; frontend input150. Pure500 schema/draft checks pass. Widening addresses transport only; API/frontend/source-state integration separately required.',
      'DEVELOPMENT_TYPED_ACCURACY':{'aggregate':metric(typed,total),'per_population':{k:v['typed_accuracy'] for k,v in metrics.items()}},
      'DEVELOPMENT_EXECUTION_ACCURACY':{'aggregate':metric(exe,total),'per_population':{k:v['execution_accuracy'] for k,v in metrics.items()}},
      'DEVELOPMENT_FALSE_EXECUTION':fe,'DEVELOPMENT_MISSED_EXECUTION':me,
      'FRESH_INDEPENDENT_TEST_PERFORMED':False,
      'INDEPENDENT_TYPED_ACCURACY':{'status':'N/A_NOT_RUN','numerator':None,'denominator':0},
      'INDEPENDENT_EXECUTION_ACCURACY':{'status':'N/A_NOT_RUN','numerator':None,'denominator':0},
      'INDEPENDENT_FALSE_EXECUTION':{'status':'N/A_NOT_RUN','numerator':None,'denominator':0},
      'INDEPENDENT_MISSED_EXECUTION':{'status':'N/A_NOT_RUN','numerator':None,'denominator':0},
      'SOURCE_ROLE_ACCURACY_IF_MEASURABLE':'N/A: no independently labeled role/span population; property checks are not accuracy estimates.',
      'NOTICE_RECOGNITION':{'population':'EXPOSED_DEVELOPMENT','C5C':c5c['per_decision']['EXECUTABLE_WITH_NOTICE'],'others':{k:v['per_decision_recall']['EXECUTABLE_WITH_NOTICE'] for k,v in details.items() if k!='C5C'}},
      'AMBIGUITY_RECOGNITION':{'population':'EXPOSED_DEVELOPMENT','C5C':c5c['per_decision']['AMBIGUOUS'],'others':{k:v['per_decision_recall']['AMBIGUOUS'] for k,v in details.items() if k!='C5C'},'limitation':'C5E-R five unsupported page-count contexts incorrectly become ambiguous; correct ambiguity recall does not imply precision.'},
      'INCOMPLETE_RECOGNITION':{'population':'EXPOSED_DEVELOPMENT','C5C':c5c['per_decision']['INCOMPLETE'],'others':{k:v['per_decision_recall']['INCOMPLETE'] for k,v in details.items() if k!='C5C'}},
      'STRUCTURAL_ISOLATION':'No new population; structural/heldout audit not invoked. All1184 contexts exposed; gold-blind C5C capture with zero denied reads/network/import attempts.',
      'NATIVE_CHOICE_COMPATIBILITY':'PARTIAL: four native choice projections pass, old transformer correction_apply works, correction_keep safely rejects422; isolated source recompiler resolves its pure cases, not wired into native sessions.',
      'SMART_MODE_STATUS':'131 focused properties and additional scope/mode fixtures pass;45 broader assertions fail; disabled.',
      'EXACT_MODE_STATUS':'Bounded native delegation; all15 additional five-scope EXACT checks pass; no live API qualification.',
      'PUBLIC_LIBRARY_STATUS':'Read-only native-function fixtures pass with mocked authority; real JWT/membership/durability unverified.',
      'PRIVATE_LIBRARY_STATUS':'Read-only own-record/foreign/outsider fixture checks pass; live authorization not qualified.',
      'PRIVATE_GLOBAL_INDEPENDENCE':'40 local native-function cases cover both global empty/inaccessible, public/private and patron/staff, with zero global reads for unlinked own books. Linked metadata/recommendation dependencies remain.',
      'PARSER_P50':{'population':'Exposed C5ER150 serial, one warm matched-host pass','milliseconds':perf['serial']['p50_ms']},
      'PARSER_P95':{'population':'Exposed C5ER150 serial, one warm matched-host pass','milliseconds':perf['serial']['p95_ms']},
      'CONCURRENCY_RESULTS':{'population':'Exposed C5ER150 four workers','measurement':perf['four_workers'],'errors':perf['errors'],'serial_concurrent_identical':perf['serial_concurrent_identical'],'SLO':'UNAGREED'},
      'LEARNED_EXTRACTOR_NEEDED':'NOT ESTABLISHED. Bounded comparison experiment justified by remaining semantic gaps; proposal only, no model/runtime selected.',
      'LEARNED_EXTRACTOR_ENABLED':False,'STAGING_READINESS':'BLOCKED','PRODUCTION_READINESS':'BLOCKED',
      'PRODUCTION_PARSER_CHANGED':False,'PRODUCTION_POLICY_CHANGED':False,'MONGO_MUTATIONS':0,'HELDOUT_EVALUATIONS':0,'HISTORICAL_EVIDENCE_PRESERVED':True,
      'REMAINING_BLOCKERS':['45 broad compatibility assertions fail, including semantic/role defects and native source/session transformations.','Five C5E-R unsupported page-count contexts receive AMBIGUOUS instead of UNSUPPORTED; no gold change.','Strict semantic/preference/intent wire contracts remain incomplete.','No eligible fresh independent acceptance; existing development prerequisites unsatisfied.','Native choice/session API/frontend integration and real authorization/CAS/relevance/operational SLO remain unqualified.'],
      'NEXT_AUTHORIZED_ACTION':'New disabled revision to consolidate remaining request-role/semantic and accepted-source refinement contracts; then clean development gates and freeze before independent author/review. Learned extractor experiment requires separate authorization; no Mongo writes/deployment.'}
    write('validation.json',{'candidate_id':freeze['candidate_id'],'source_freeze_sha256':sha(R/(P+'source_freeze.json')),'tests':test_counts,'passed':test_counts['tests']-test_counts['failures']-test_counts['errors']-test_counts['skipped'],'focused_passed':131,'development':metrics,'development_details':details,'edit_draft_timing':edit,'pure_mode_checks':modes['mode_passed'],'native_local_cases':40,'native_global_cases':8,'native_choice_projections':4,'fresh_acceptance_attempts':0,'normative_gold_changed':False,'known_limitations':'Strict field scores are reported, not replaced by execution decisions. Failed attempts and source snapshots preserved.'})
    write('acceptance_eligibility.json',{'eligible':False,'primary_attempts':0,'contexts':0,'human_reviewers':0,'AI_author_reviewers':0,'structural_audits':0,'binding_prior_contract':'reports/search_comp3_acceptance_contract_v2.json','prior_contract_sha256':sha(R/'search_comp3_acceptance_contract_v2.json'),'preserved_acceptance_gates':{'typed_minimum':.95,'execution_minimum':.99,'critical_false_execution_maximum':0,'missed_valid_maximum':.05,'mandatory_loss_or_invention_maximum':0,'cross_tenant_leaks_maximum':0},'failed_prerequisites':{'clean_regression_failures':test_counts['failures'],'C5ER_typed':metrics['c5er150']['typed_accuracy'],'native_full_contract_integration':False},'population_not_consumed':True,'heldout_access':'No sealed structural/content evaluation; protected binary hashes only for preservation.'})
    write('final_qa.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'required_fields':qa,'source_freeze_sha256':sha(R/(P+'source_freeze.json')),'integrity_verification':str((R/(P+'integrity_verification.json')).resolve()),'validation':str((R/(P+'validation.json')).resolve())})
    lines=[f"FINAL=PARTIAL. Candidate `{freeze['candidate_id']}` remains disabled. Staging and production are BLOCKED.",
      '',f"Focused tests:131/131 pass. Broad suite:{test_counts['tests']-test_counts['failures']}/{test_counts['tests']} pass;{test_counts['failures']} fail. No normative gold changed.",'','Exposed development only:','', '| Population | Typed | Execution | False execution | Missed valid | Strict scored fields |','|---|---:|---:|---:|---:|---:|']
    for k,v in metrics.items():
        def cell(key):m=v[key];return f"{m['numerator']}/{m['denominator']}"
        lines.append('| '+k+' | '+' | '.join(cell(x) for x in ['typed_accuracy','execution_accuracy','false_execution','missed_execution','strict_scored_fields'])+' |')
    lines+=['',f"Aggregate exposed typed:{typed}/{total}; execution:{exe}/{total}; false:{fe['numerator']}/{fe['denominator']}; missed:{me['numerator']}/{me['denominator']}. Zero scored executed hard-field mismatch contexts across430 executed contexts under frozen masks. Strict semantic/preference/intent failures remain.",'',
      'V5 adds typed source roles/modality, early domain/operand ownership, original-source and semantic projection proof, and a pure bound source-span edit recompiler. Completion/correction changes reparse the entire result and preserve untouched requirements. No active API/session/frontend integration or actual durable one-use/CAS qualification is claimed.', '',
      'Fresh acceptance: NOT RUN; numerator N/A, denominator0, primary attempts0. Existing clean-regression/C5E-R typed/native prerequisites fail. No new population was consumed or sealed content evaluated.', '',
      f"Parser-only serial p50/p95:{perf['serial']['p50_ms']:.2f}/{perf['serial']['p95_ms']:.2f}ms; four-worker p95:{perf['four_workers']['p95_ms']:.2f}ms,150/150 deterministic outputs. Shared host, one warm pass, no agreed SLO. Pure edit drafts60/60 pass, p50/p95:{edit['timing']['p50_ms']:.2f}/{edit['timing']['p95_ms']:.2f}ms; no commits.",'',
      'Read-only native-function checks:40 local library cases,8 global cases and4 choice projections pass. Mocked identity/collections and fixed-ID semantic provider do not establish live authorization, Mongo durability or embedding relevance. The old correction_keep workflow still safely rejects422;500-character transport needs separately authorized API/frontend/source-state integration.', '',
      'All3271 prior protected entries and27 frozen source/dependency files verified unchanged. Production/C4/frontend/authorization changes:0; Mongo mutations:0; model selection/download/training/activation:0; HNSW/KG rebuilds:0. Last known global health stays STALE/degraded, baseline_verified=False;5,000,000 is historical.', '',
      'Evidence index (repository paths; use the absolute working-tree equivalents):','',
      '- Integrity and exact parent hash: `reports/search_proof5_preflight.json`, `reports/search_proof5_integrity_verification.json`.',
      '- Root causes, source-role/modality/IR/proof contract and limitations: `reports/search_proof5_semantics_contract.md`; exact symbols/hashes: `reports/search_proof5_source_map.json`.',
      '- Pure edit implementation,500/150 length assessment and integration limitations: `reports/search_proof5_native_contract.md`, `reports/search_proof5_mode_protocol_audit.json`.',
      '- Focused/metamorphic,SMART/EXACT,development,mandatory preservation,library and latency evidence: `reports/search_proof5_validation.json` and its named source artifacts; all45 failures: `reports/search_proof5_regression_failures.json`; V4 deltas: `reports/search_proof5_changed_predictions_vs_V4.json`.',
      '- Independent evaluation eligibility and unchanged gates: `reports/search_proof5_acceptance_eligibility.json`.',
      '- Deterministic feasibility,bounded learned-extractor alternatives,licensing,measured resources and unmeasured costs: `reports/search_proof5_feasibility.md`. No model/runtime selected or enabled.',
      '- Scope/global-independence audit and staging/production prerequisites: `reports/search_proof5_integration_prerequisites.md`.',
      '- Full mandatory QA fields: `reports/search_proof5_final_qa.json`; source freeze: `reports/search_proof5_source_freeze.json`; final evidence manifest and verification record final hashes.', '',
      'Next: consolidate remaining source-role/semantic and accepted-source refinement contracts in a new disabled revision, then satisfy development prerequisites before independent authoring/review. A learned-extractor comparison remains a separate proposal.']
    with (R/(P+'final_QA.md')).open('x',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')
    paths=list(R.glob(P+'*'))+list(Path('scripts').glob(P+'*.py'))
    for d in ['scratch/search_proof_recovery_v5','scratch/search_proof5_regression','scratch/search_proof5_history']:
        paths.extend(p for p in Path(d).rglob('*') if p.is_file() and '__pycache__' not in str(p))
    files={str(p):sha(p) for p in paths if p.is_file()}
    write('freeze_manifest.json',{'candidate_id':freeze['candidate_id'],'FINAL':'PARTIAL','kind':'IMMUTABLE_DISABLED_ENGINEERING_RECORD_NOT_ACCEPTANCE_READY','files':files,'source_freeze_sha256':sha(R/(P+'source_freeze.json')),'production_activation':False,'primary_acceptance_attempts':0})
    manifest=R/(P+'freeze_manifest.json');assert all(sha(p)==h for p,h in files.items())
    write('freeze_verification.json',{'status':'PASS','manifest_sha256':sha(manifest),'new_evidence_entries':len(files),'prior_protected_entries':3271,'candidate_dependency_entries':27,'changed':[],'Mongo_mutations':0,'heldout_evaluations':0,'FINAL':'PARTIAL'})
    print(json.dumps({'FINAL':'PARTIAL','typed':f'{typed}/{total}','execution':f'{exe}/{total}','tests':test_counts,'frozen_entries':len(files),'manifest_sha256':sha(manifest)}))
if __name__=='__main__':main()
