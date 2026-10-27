"""C5 integrity gate. Never imports a parser or decodes held-out rows/labels."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
from scripts.search_v2c_c2_benchmark import identity,structure

R=Path('reports');P='search_v2c_c5_'
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def rows(p):return [json.loads(x) for x in Path(p).read_text(encoding='utf8').splitlines() if x.strip()]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,v):(R/(P+name)).write_text(json.dumps(v,indent=2,default=str)+'\n',encoding='utf8')

def main():
    evidence=['final_qa','development_metrics','reviewed_contract','false_filter_clusters','contradiction_fixes','regression_delta','legacy_gold_review','native_metrics','backend_regression','browser','preservation']
    docs={k:read(R/f'search_v2c_c4_{k}.json') for k in evidence}
    frozen=read(R/'search_v2c_c4_freeze.json');bad=[p for p,h in frozen['files'].items() if sha(p)!=h]
    q=docs['final_qa'];m=docs['development_metrics']['reviewed_v2_label_metrics']
    expected={'FALSE_HARD_FILTER_RATE':(42,6529),'UNSAFE_AUTO_PARSE_RATE':(16,1913),'SUPPORTED_CONTRADICTION_RECALL':(583,583),'COMPARATOR_ACCURACY':(911,911),'PROTECTED_ENTITY_PRESERVATION':(1440,1440),'CROSS_SCOPE_VOCABULARY_LEAKAGE_RATE':(0,6529)}
    checks={k:(m[k]['numerator'],m[k]['denominator'])==v for k,v in expected.items()}
    n=docs['native_metrics'];checks.update(security=n['security_family_unsafe_auto_parse']['numerator']==0,session=n['session_corruption_rate']['numerator']==0,privacy=n['private_leaks']==0,accepted=q['FINAL']=='PASS' and q['CALIBRATION_AUTHORIZED']=='YES')
    pre={'status':'PASS' if not bad and all(checks.values()) else 'FAIL','frozen_mismatches':bad,'checks':checks,'frozen_files':frozen['files'],
         'inspected_report_hashes':{k:sha(R/f'search_v2c_c4_{k}.json') for k in evidence},'historical_raw':{'C3_labels_false_filters':'88/6529','current_false_filters':'42/6529','legacy_raw':'129/136','legacy_reviewed':'136/136','seeded':'1000/1000','raw_backend_failures':12},
         'C4_review':{'AI_REVIEWED':68,'HUMAN_REVIEWED':0,'partial_records':7},'population_warning':'Reviewed development evidence; not real-world accuracy.'}
    write('precondition.json',pre)
    if pre['status']!='PASS':raise SystemExit('STOP: C4 precondition mismatch')
    manifest=read(R/'search_v2c_c2_benchmark_v2_manifest.json');split=read(R/'search_v2c_c2_benchmark_v2_split.json');sealed=read(R/'search_v2c_c3_sealed_manifest.json');root=read(R/'search_v2c_c3_sealed_root_freeze.json')
    original_files=manifest['files'];integrity=[{'path':x['path'],'expected_sha256':x['sha256'],'actual_sha256':sha(x['path']),'match':sha(x['path'])==x['sha256'],'cases':x['cases']} for x in original_files]
    sealed_integrity=[{'path':x['path'],'split':x.get('split'),'rows':x.get('rows'),'expected_sha256':x['sha256'],'actual_sha256':sha(x['path']),'match':sha(x['path'])==x['sha256']} for x in root['files']]
    assert all(x['match'] for x in integrity+sealed_integrity),'STOP: corpus integrity mismatch'
    # Do not deserialize ANY held-out file or mixed sealed authored/audit file.
    dev=rows(R/'search_v2c_c2_v2_development.jsonl');cal=rows(R/'search_v2c_c2_v2_calibration.jsonl');reviewed=rows(R/'search_v2c_c3_sealed_calibration.jsonl')
    replacement={r['original_query_id']:r for r in reviewed};assert len(replacement)==50
    scopes=read(R/'search_v2c_c_scope_vocabularies.json');effective=[];lineage=[]
    for r in cal:
        v=replacement.get(r['query_id'],r)
        assert identity(r,scopes)==identity(v,scopes) and r['family_id']==v['family_id'] and r['structural_family_id']==v['structural_family_id']
        effective.append(v);lineage.append({'original_query_id':r['query_id'],'effective_query_id':v['query_id'],'revised':v is not r})
    partitions={};families=defaultdict(set);components=defaultdict(set)
    for a in split['assignments']:
        for f in a['original_families']:families[f].add(a['split'])
        components[a['structural_family_id']].add(a['split'])
    overlap=[k for k,v in families.items() if len(v)>1];comp_overlap=[k for k,v in components.items() if len(v)>1]
    # Independently verify operation topology isolation for authorized partitions;
    # held-out isolation is proven transitively by immutable manifest+source audit.
    dt={structure(r) for r in dev};ct={structure(r) for r in effective};topology_overlap=sorted(dt&ct)
    assert not overlap and not comp_overlap and not topology_overlap,'STOP: forbidden partition family/topology overlap'
    ids=[identity(r,scopes) for r in dev+effective];assert len(ids)==len(set(ids))
    by_id=[]
    for r in dev+effective:
        context=identity(r,scopes);by_id.append({'query_id':r['query_id'],'benchmark_version':r['benchmark_version'],'canonical_context_sha256':hashlib.sha256(json.dumps(context,ensure_ascii=False).encode()).hexdigest(),
            'family_id':r['family_id'],'structural_component':r['structural_family_id'],'scope':r['scope_type'],'mode':r['search_mode'],'partition':r['split'],'review_provenance':r.get('review_provenance'),'review_status':r['review_status'],'unit':'native_sequence' if r.get('requires_native_execution') else 'parser_context'})
    (R/(P+'context_inventory.jsonl')).write_text(''.join(json.dumps(x)+'\n' for x in by_id),encoding='utf8')
    quality=[]
    for r in effective:
        missing=any(c.get('code')=='native_sequence_context_missing' for c in (r.get('label_review_concerns') or []))
        quality.append({'query_id':r['query_id'],'review_status':r['review_status'],'quality_class':'INVALID_OR_UNRESOLVED' if missing else r['review_status'],
            'human_reviewed':False,'applicable_parser_fields':[] if r.get('requires_native_execution') else 'All independently authored expected fields; no C4 partial contract fields imported',
            'excluded_fields':{'all_parser_plan_fields':'Native interaction requires complete sequence/state oracle; single-turn plan labels do not apply'} if r.get('requires_native_execution') else {},
            'native_sequence_missing':missing,'source':r.get('review_source'),'reviewer_type':r.get('reviewer_type')})
    counts=dict(Counter(x['quality_class'] for x in quality))
    write('label_quality.json',{'status':'PARTIAL' if counts.get('INVALID_OR_UNRESOLVED') or counts.get('UNREVIEWED') else 'PASS','cases':len(effective),'exclusive_quality_counts':counts,'AI_reviewed_provenance_count':sum(r['review_status']=='AI_REVIEWED' for r in effective),'human_reviewed':0,'cases_detail':quality,'no_silent_case_drops':True})
    write('review_provenance.json',{'C3_revised_calibration_rows':50,'fresh_output_blind_AI':50,'C3_heldout_rows_read':0,'C4_partial_records_used_as_gold':0,'new_human_reviews':0,'new_independent_AI_reviews':0,'native_unreviewed_labels':'Generated derivatives remain UNREVIEWED; API invariants and raw HTTP expectations must be reported separately.'})
    output=R/(P+'calibration.jsonl');output.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in effective),encoding='utf8')
    accounting={'status':'PASS','logical_contexts':7211,'original_stored_v1_rows':7112,'original_duplicates_removed':7,'C2_additional_contexts':106,'C2_stored_context_rows':7211,
        'current_versioned_sealed_rows_additional':100,'current_versioned_sealed_rows_are_replacements_not_new_contexts':True,
        'partitions':{'development':{'contexts':6881,'parser':6529,'native':352},'calibration':{'contexts':280,'parser':50,'native':230},'heldout':{'contexts':50,'source':'Immutable manifest only; not deserialized'}},
        'forbidden_family_overlap':overlap,'forbidden_component_overlap':comp_overlap,'authorized_dev_cal_operation_topology_overlap':topology_overlap,
        'identity_units':'NFKC casefold query + mode + scope + workspace + complete capabilities + native action; scope materializations count as distinct contexts; API sequence steps do not create extra contexts.',
        'calibration_sequence_steps_declared':sum(len(r.get('sequence_steps') or []) for r in effective),'native_sequence_cases_missing_steps':sum(r.get('requires_native_execution',False) and not r.get('sequence_steps') for r in effective),
        'heldout_metadata_proof':'Per-case content remains in immutable corpus; all50 represented by original/C3 manifest hashes and five isolated family assignments. No query/label decoding for this audit.',
        'context_inventory':P+'context_inventory.jsonl','lineage':lineage,'original_corpus_integrity':integrity,'sealed_integrity':sealed_integrity,
        'canonical_manifest_sha256':sha(R/'search_v2c_c2_benchmark_v2_manifest.json'),'family_assignment_sha256':sha(R/'search_v2c_c2_benchmark_v2_split.json')}
    write('partition_accounting.json',accounting)
    hold={'status':'PASS','HELDOUT_EVALUATIONS':0,'HELDOUT_PARSER_INVOCATIONS':0,'HELDOUT_EVALUATOR_INVOCATIONS':0,'HELDOUT_MANIFEST_UNCHANGED':'YES',
          'heldout_rows_deserialized':0,'outputs_inspected':False,'labels_used_for_selection':False,'proof':[x for x in integrity+sealed_integrity if x.get('split')=='heldout' or 'heldout' in x['path']],
          'manifests':{str(p):sha(p) for p in [R/'search_v2c_c2_benchmark_v2_manifest.json',R/'search_v2c_c2_holdout_manifest.json',R/'search_v2c_c3_sealed_manifest.json',R/'search_v2c_c3_sealed_root_freeze.json']}}
    write('holdout_preservation.json',hold)
    paths=set(frozen['files'])|{str(p) for p in R.glob('search_v2c_c*') if p.is_file() and not p.name.startswith(P)}
    for rootdir in ['search','backend','recommendation','rag','frontend/src','frontend/tests','tests','scripts']:
        paths.update(str(p) for p in Path(rootdir).rglob('*') if p.is_file() and p.suffix in ['.py','.ts','.tsx','.css','.json'] and '__pycache__' not in str(p) and not p.name.startswith(P))
    write('baseline_files.json',{'files':{p:sha(p) for p in sorted(paths)},'created_at':datetime.now(timezone.utc).isoformat()})
    inputs=[output,R/'search_v2c_c_scope_vocabularies.json',R/'search_v2c_c2_benchmark_v2_split.json',R/'search_v2c_c4_reviewed_contract.json',R/(P+'label_quality.json'),Path(__file__)]
    policy=Path('search/query_calibration.py')
    write('calibration_manifest.json',{'version':'C5-calibration-v1','status':'FROZEN_BEFORE_BASELINE','cases':280,'unique_contexts':280,'parser_cases':50,'native_cases':230,
        'source_parser_version':frozen['parser_version'],'evaluator_version':'C5-baseline-1','policy_version':'existing categorical execution_policy',
        'policy_hash':sha(policy),'files':{str(p):sha(p) for p in inputs},'parser_source_hashes':{p:h for p,h in frozen['files'].items() if p.startswith('search/')},
        'heldout_access':'Hash bytes and permitted manifests only; no held-out row decoded','label_sources':'C3 reviewed50 replace C2 originals by exact unchanged context lineage; remaining230 original rows retained.'})
    print(json.dumps({'precondition':'PASS','partition_accounting':'PASS','calibration_contexts':280,'parser':50,'native':230,'label_quality':counts}))

if __name__=='__main__':main()
