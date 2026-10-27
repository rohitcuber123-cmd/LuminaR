"""Bounded policy comparisons over retained calibration outputs; no parser calls."""
from collections import Counter
import hashlib,json,math,time
from pathlib import Path
from scripts.search_v2c_c5_prepare import R,P,read,rows,sha,write
from scripts.search_v2c_c5_baseline import rate

CONFIGS=[{'version':'c5-existing-control','rule':'Existing categorical policy unchanged'},
 {'version':'c5-notice-source-certainty-v1','rule':'Typed guard authoritative; notice on repairs, unknown subject or confidence below1','notice_below':1.0},
 {'version':'c5-complete-source-evidence-v1','rule':'Typed guard authoritative; clarify missing supported source evidence, notice repairs or confidence below0.98','notice_below':0.98,'require_source':True}]

def apply(row,config):
    plan=row['actual_plan'];kind=row['decision']
    if kind in ('AMBIGUOUS','INCOMPLETE'):return 'CLARIFY'
    if kind=='UNSUPPORTED':return 'UNSUPPORTED'
    if kind=='CONTRADICTORY':return 'REJECT_CONTRADICTION'
    original=row['assessment']['policy']
    if config['version']=='c5-existing-control':return original
    if config.get('require_source'):
        needed=[]
        fields={'subjects':'subject','exclude_subjects':'excluded_subject','exclude_terms':'exclude','author_text':'author','title_text':'title','exact_text':'exact_text',
                'rating_min':'rating','rating_max':'rating','year_min':'year','year_max':'year','formats':'format','availability':'availability','language':'language'}
        for field,name in fields.items():
            value=plan.get(field)
            if value is not None and value!=[] and value!='' and value is not False:needed.append(name)
        supported=set()
        for candidate in plan['constraint_candidates']:
            start,end=candidate.get('source_span_start'),candidate.get('source_span_end');source=candidate.get('source_query',plan['raw_query'])
            if isinstance(start,int) and isinstance(end,int) and 0<=start<end<=len(source) and candidate.get('source_text')==source[start:end] and candidate.get('support_status')=='SUPPORTED':supported.add(candidate['field'])
        if any(f not in supported for f in needed):return 'CLARIFY'
    if original=='EXECUTE_WITH_NOTICE' or plan.get('unknown_subject') or row['interpretation_confidence']<config['notice_below']:return 'EXECUTE_WITH_NOTICE'
    return 'AUTO_EXECUTE'

def outcome(observations,config):
    policies=[apply(r,config) for r in observations];n=len(policies)
    execute=[p in ('AUTO_EXECUTE','EXECUTE_WITH_NOTICE') for p in policies]
    blocked=[(r,p,e) for r,p,e in zip(observations,policies,execute) if not r['expected_execution']]
    safe=[(r,p,e) for r,p,e in zip(observations,policies,execute) if r['expected_execution']]
    return {'cases':n,'policy_counts':dict(Counter(policies)),
        'blocked_unsafe_auto_parse':rate(sum(r['unsafe_auto_parse'] and e for r,p,e in blocked),len(blocked)),
        'executed_false_hard_filter':rate(sum(bool(r['false_filters']) and e for r,e in zip(observations,execute)),n),
        'auto_execution_coverage':rate(sum(p=='AUTO_EXECUTE' for p in policies),n),'total_execution_coverage':rate(sum(execute),n),
        'notice_rate':rate(sum(p=='EXECUTE_WITH_NOTICE' for p in policies),n),'clarification_rate':rate(sum(p=='CLARIFY' for p in policies),n),
        'false_clarification_rate':rate(sum(p=='CLARIFY' for r,p,e in safe),len(safe)),
        'user_interruption_rate':rate(sum(not e for e in execute),n),
        'supported_contradiction_recall':rate(sum(not e for r,p,e in blocked if r['expected_decision']=='CONTRADICTORY'),sum(r['expected_decision']=='CONTRADICTORY' for r,p,e in blocked))}

def main():
    observations=rows(R/(P+'baseline_observations.jsonl'));assert len(observations)==50
    manifest=read(R/(P+'calibration_manifest.json'))
    manifest['candidate_policy_evaluator_hash']=sha(__file__);manifest['candidate_configs']=CONFIGS
    write('calibration_manifest.json',manifest)
    families=sorted({r['family_id'] for r in observations})
    # Whole structural families stay together. Report every fold; no random row split.
    candidates=[]
    for config in CONFIGS:
        candidates.append({'configuration':config,'configuration_sha256':hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest(),
            'aggregate':outcome(observations,config),
            'by_scope':{s:outcome([r for r in observations if r['scope']==s],config) for s in ['GLOBAL','PUBLIC_PATRON','PUBLIC_STAFF','PRIVATE_PATRON','PRIVATE_STAFF']},
            'by_family':{f:outcome([r for r in observations if r['family_id']==f],config) for f in families},
            'family_internal_validation':[{'validation_family':f,'selection_families':[x for x in families if x!=f],'selection':outcome([r for r in observations if r['family_id']!=f],config),'validation':outcome([r for r in observations if r['family_id']==f],config)} for f in families],
            'selection_status':'NOT_DEFENSIBLE: zero blocked/contradictory/incomplete/unsupported parser contexts; no Global/public/staff parser cases. Cannot establish mandatory safety gates or a medium-confidence threshold.'})
    write('policy_candidates.json',{'status':'COMPARISON_COMPLETE_NO_SELECTION','candidates':candidates,'parser_calls':0,'heldout_calls':0,
        'validation':'Leave-one-structural-family-out, five folds of10cases. All five share the same title/author core; folds are dependent, not an independent accuracy estimate.',
        'typed_decision_guards':'No candidate may promote a blocked typed decision to execution. None edits an extracted field.'})
    selected={'status':'NO_DEFENSIBLE_CANDIDATE','selected':False,'active_policy':'Existing C4 categorical policy retained unchanged','POLICY_VERSION':'existing categorical execution_policy',
        'POLICY_HASH':sha('search/query_calibration.py'),'PARSER_VERSION':'search-v2c-c4-deterministic-1','PARSER_SOURCE_CHANGED':False,
        'reason':'The calibration parser population contains only50 executable, confidence1.0, private-patron queries. Three policies have identical observed routing. Missing applicability cannot count as passing blocked/contradiction safety. Native lifecycle cases do not fill these parser decision strata. No activation is justified.',
        'production_integration_performed':False,'new_feature_flag':False,'final_heldout_authorized':False}
    write('selected_policy.json',selected)
    base=candidates[0]['aggregate']
    for name in ['risk_coverage.json','false_clarification.json','auto_execution_coverage.json']:
        write(name,{'baseline':base,'candidates':{c['configuration']['version']:c['aggregate'] for c in candidates},'selected_policy':None,
            'coverage_lost_observed':{c['configuration']['version']:0 for c in candidates},'note':'No policy activated. After values describe candidate simulation over the same50 retained outputs, not a rollout.'})
    # Pure policy overhead over saved observations; comparable sample counts only.
    def pct(v,p):return sorted(v)[max(0,math.ceil(len(v)*p)-1)]
    perf={}
    for config in CONFIGS:
        samples=[]
        for i in range(1000):
            start=time.perf_counter_ns();apply(observations[i%50],config);samples.append((time.perf_counter_ns()-start)/1e6)
        perf[config['version']]={'n':1000,'p50_ms':pct(samples,.5),'p95_ms':pct(samples,.95),'p99_ms':pct(samples,.99)}
    write('performance.json',{'policy_simulation':perf,'parser_plus_policy':'NOT MEASURED: no new policy selected/integrated','Global_Search':'NOT MEASURED','public_Search':'NOT MEASURED','private_Search':'NOT MEASURED',
        'calibration_parser_baseline_samples_ms':read(R/(P+'baseline_metrics.json'))['parser_samples_ms'],
        'C4_historical_parser_ms':{'n':1000,'p50':1.092,'p95':15.156,'p99':17.203},'speedup_claim':False,'new_model_calls':0,'full_catalogue_scans':0})
    print(json.dumps({'candidates':3,'selected':False,'policy_unchanged':True,'routing':{c['configuration']['version']:c['aggregate']['policy_counts'] for c in candidates}}))

if __name__=='__main__':main()
