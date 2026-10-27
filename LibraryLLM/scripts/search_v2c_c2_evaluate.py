"""C2 development-only evaluator. There is no calibration/holdout entry point."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time
from collections import Counter
from scripts.search_v2c_c_evaluate import evaluate_case, aggregate, ratio
from scripts.search_v2c_c2_benchmark import read_rows, write

R=Path('reports')
EVALUATOR_VERSION='c2-development-1'


def freeze():
    manifest=json.loads((R/'search_v2c_c2_benchmark_v2_manifest.json').read_text())
    source_files=[str(p) for p in Path('search').glob('query_*.py')]+[
        'search/session_store.py','search/scope_authorization.py','scripts/search_v2c_c_evaluate.py',
        'scripts/search_v2c_c2_evaluate.py','scripts/search_v2c_c2_benchmark.py',
        'reports/search_v2c_c2_evaluator_rules.md']
    data={'version':'V2C-C-Benchmark-v2','status':'FROZEN_DEVELOPMENT_ONLY; future holdout still requires authorization and label readiness',
          'evaluator_version':EVALUATOR_VERSION,'parser_version':__import__('search.query_plan',fromlist=['PARSER_VERSION']).PARSER_VERSION,
          'decision_policy_version':'existing categorical validate/decide; no calibrated policy',
          'source_hashes':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in source_files},
          'corpus_files':manifest['files'],'family_assignment_hash':hashlib.sha256((R/'search_v2c_c2_benchmark_v2_split.json').read_bytes()).hexdigest(),
          'heldout_evaluations':0,'calibration_runs':0,'label_readiness':manifest['sealed_label_review']}
    for file in data['corpus_files']:assert hashlib.sha256(Path(file['path']).read_bytes()).hexdigest()==file['sha256']
    write('holdout_manifest.json',data)
    return data


def main():
    frozen=freeze()
    # Only this fixed, explicit development path is deserialized/evaluated.
    cases=read_rows(R/'search_v2c_c2_v2_development.jsonl')
    assert cases and all(c['split']=='development' and c['benchmark_version']=='V2C-C-Benchmark-v2' for c in cases)
    native=[c for c in cases if c.get('requires_native_execution')]
    actual_native=read_rows(R/'search_v2c_c2_native_current/search_v2c_c2_native_observations.jsonl')
    assert len(actual_native)==len(native) and {r['query_id'] for r in actual_native}=={c['query_id'] for c in native},'Complete all native development rows before final scoring'
    assert len({r['query_id'] for r in actual_native})==len(actual_native),'Never count repeated native attempts as unique cases'
    scopes=json.loads((R/'search_v2c_c_scope_vocabularies.json').read_text())
    observations=[];errors=[];started=time.perf_counter()
    for case in cases:
        if case.get('requires_native_execution'):continue
        try:
            row=evaluate_case(case,scopes)
            row.update(query_text=case['query_text'],benchmark_version=case['benchmark_version'],
                       original_split=case['original_split'],review_status=case['review_status'],
                       source_spans=row['actual_plan']['source_spans'],
                       expected_strict_filters={k:v for k,v in case.items() if k.startswith('expected_')},
                       label_review_concerns=case.get('label_review_concerns',[]))
            observations.append(row)
        except Exception as error:
            errors.append({'query_id':case['query_id'],'error':repr(error),'status':'UNEXECUTED_ERROR'})
    metrics=aggregate(observations)
    metrics['ALL_CASE_UNSAFE_AUTO_PARSE_RATE']=ratio(sum(r['unsafe_auto_parse'] for r in observations),len(observations))
    supported=[r for r in observations if r['expected_decision']=='CONTRADICTORY' and not any(c.get('code')=='rating_domain_assumption' for c in r['label_review_concerns'])]
    metrics['SUPPORTED_CONTRADICTION_RECALL']=ratio(sum(r['decision']=='CONTRADICTORY' for r in supported),len(supported))
    # Fixed raw original-label denominator and same original authored semantics.
    v1=json.loads((R/'search_v2c_c_resume_development_metrics.json').read_text())['metrics']
    old=read_rows(R/'search_v2c_c_resume_development_observations.jsonl')
    retained={c['old_query_id'] for c in cases if c.get('original_split')=='development'}
    dedup_baseline=aggregate([r for r in old if r['query_id'] in retained])
    violations=[]
    for name,operator,limit in [('FALSE_HARD_FILTER_RATE','<=',1),('UNSAFE_AUTO_PARSE_RATE','<',3),
        ('SUPPORTED_CONTRADICTION_RECALL','==',100),('PROTECTED_ENTITY_PRESERVATION','>=',99),
        ('COMPARATOR_ACCURACY','>=',99),('CROSS_SCOPE_VOCABULARY_LEAKAGE_RATE','==',0)]:
        value=metrics[name]['percent']
        passes=value is not None and {'<=':lambda:value<=limit,'<':lambda:value<limit,'>=':lambda:value>=limit,'==':lambda:value==limit}[operator]()
        if not passes:violations.append({'metric':name,'observed':metrics[name],'required':operator+str(limit)})
    native_failed=[r for r in actual_native if r['result']=='FAIL']
    if native_failed:violations.append({'metric':'NATIVE_STATE_ORACLES','failed':len(native_failed)})
    if errors:violations.append({'metric':'UNEXECUTED_ROWS','cases':errors})
    result={'version':EVALUATOR_VERSION,'benchmark_version':'V2C-C-Benchmark-v2','split':'development',
        'development_rows':len(cases),'parser_executed':len(observations),'native_executed':len(actual_native),
        'unexecuted_rows':errors,'strict_raw_original_label_metrics':metrics,
        'atomic_semantics_metrics':{k:v for k,v in metrics.items() if k.startswith(('HARD_','COMPARATOR','NEGATIVE_','FALSE_HARD'))},
        'normalization':'No additional equivalence rule; atomic and strict views retain every extra exclusion error.',
        'historical_raw_v1_metrics':v1,'original_development_dedup_before_changes':dedup_baseline,
        'population_warning':'V2 development includes legacy calibration/heldout components reassigned BEFORE fixes/evaluation for contamination. Parser corrections used only original development failures; no tuning follows this final evaluation.',
        'mandatory_violations':violations,'status':'STOP_MANDATORY_GATE_FAILURE' if violations else 'PARSER_GATES_PASS_ONLY',
        'elapsed_s':time.perf_counter()-started,
        'by_scope':{s:aggregate([r for r in observations if r['scope']==s]) for s in sorted({r['scope'] for r in observations})},
        'heldout_evaluated':False,'calibration_run':False}
    write('development_parser_metrics.json',result)
    (R/'search_v2c_c2_development_observations.jsonl').write_text(''.join(json.dumps(r,default=str)+'\n' for r in observations),encoding='utf8')
    for name,predicate in [
        ('false_hard_filters_after',lambda r:bool(r['false_filters'])),('unsafe_after',lambda r:r['unsafe_auto_parse']),
        ('comparators',lambda r:r['comparator_evaluable']),('contradictions',lambda r:r['expected_decision']=='CONTRADICTORY'),
        ('protected_entities',lambda r:r['protected_count']>0),('incomplete',lambda r:r['expected_decision']=='INCOMPLETE'),
        ('unsupported',lambda r:r['expected_decision']=='UNSUPPORTED'),
        ('negative_constraints',lambda r:bool(r['actual_plan']['exclude_subjects'] or r['actual_plan']['exclude_terms']) or not r['negative_correct'])]:
        rows=[r for r in observations if predicate(r)]
        write(name+'.json',{'population':'Entire deduplicated V2 development parser partition','case_count':len(rows),'cases':rows,
                            'remaining_failures':[r['query_id'] for r in rows if (not r['comparator_correct'] if name=='comparators' else not r['protected_preserved'] if name=='protected_entities' else r['decision']!='CONTRADICTORY' if name=='contradictions' else True)]})
    for name,subset in [('global',['GLOBAL']),('public_tenant',['PUBLIC_PATRON','PUBLIC_STAFF']),('private_tenant',['PRIVATE_PATRON','PRIVATE_STAFF'])]:
        write(name+'.json',{'parser_scope_metrics':{s:result['by_scope'][s] for s in subset},'native_cases':[r['query_id'] for r in actual_native if r['scope'] in subset], 'browser':'search_v2c_c2_browser.json','production_index_rebuild':False})
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in frozen['source_hashes'].items())
    print(json.dumps({'parser_executed':len(observations),'native_executed':len(actual_native),'metrics':metrics,'mandatory_violations':violations},indent=2))


if __name__=='__main__':main()
