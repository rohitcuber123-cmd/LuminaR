"""Established sealed structural audit and all exposed C5E-R inputs."""
from pathlib import Path
import json,ast,hashlib,sys
from scripts import search_v2c_c5a_sealed_audit as sealed
R=Path('reports');P='search_v2c_smarteng_'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    tag=sys.argv[1] if len(sys.argv)>1 else ''
    assert tag in ['', 'v2']
    output=P+(tag+'_' if tag else '')
    input_path=R/(P+('authored_v2.jsonl' if tag else 'authored.jsonl'))
    pre=json.loads((R/(P+'preflight.json')).read_text(encoding='utf8'));protected={str(Path(k).resolve()):h for k,h in pre['protected_files'].items()}
    assert sha('scripts/search_v2c_c5a_sealed_audit.py')==protected[str(Path('scripts/search_v2c_c5a_sealed_audit.py').resolve())]
    sealed.PREFIX=output
    result=sealed.audit(input_path.resolve(),(R/(output+'sealed_structural_isolation.json')).resolve())
    c2=Path('scripts/search_v2c_c2_benchmark.py');identity,structure=sealed.pure_c2_functions(c2,protected[str(c2.resolve())])
    scope=sealed.load_json(R/'search_v2c_c_scope_vocabularies.json')
    baseline=[];paths=[R/n for n in ['search_v2c_c2_v2_development.jsonl','search_v2c_c5b_calibration_cases.jsonl',
        'search_v2c_c5e_independent_authored.jsonl','search_v2c_c5e_independent_authored_v3.jsonl','search_v2c_c5er_authored.jsonl','search_v2c_c5er_authored_v2.jsonl']]
    for p in paths:baseline.extend(sealed.projected_rows(p))
    conservative=[];sources=[]
    for d in ['scratch/search_v2c_c5d_repair','scratch/search_v2c_c5d_repair_v2','scratch/search_v2c_c5e','scratch/search_v2c_c5er','scratch/search_smart_engineering']:
        for p in Path(d).rglob('test*.py'):
            sources.append({'path':str(p),'sha256':sha(p)})
            for n in ast.walk(ast.parse(p.read_text(encoding='utf8'))):
                if isinstance(n,ast.Constant) and isinstance(n.value,str) and len(n.value)>7:conservative.append({'query_text':n.value,'search_mode':'SMART'})
    topologies={structure(x) for x in baseline+conservative};identities={identity(x,scope) for x in baseline}
    collisions=[];new=list(sealed.projected_rows(input_path,new=True))
    for x in new:
        hits=[]
        if structure(x) in topologies:hits.append('OPERATION_TOPOLOGY')
        if identity(x,scope) in identities:hits.append('CANONICAL_CONTEXT')
        if hits:collisions.append({'new_case_id':x['new_case_id'],'collision_kinds':hits})
    out={'status':'PASS' if result['status']=='PASS' and not result['collision_counts'] and not collisions else 'OVERLAP_BLOCKED',
        'established_audit':result,'additional_collisions':collisions,'exposed_population_rows':len(baseline),'conservative_test_strings':len(conservative),
        'candidate_test_sources':sources,'source_population_sha256':sha(input_path),'distinct_actual_topologies':len({structure(x) for x in new}),
        'heldout_evaluations':0,'heldout_content_emitted':False,'parser_calls':0,'scoring_calls':0}
    with (R/(output+'structural_isolation.json')).open('x',encoding='utf8') as f:json.dump(out,f,indent=2)
    brief=json.loads((R/(P+'blind_author_brief.json')).read_text(encoding='utf8'))
    packet={'task':'Independent normative review of150 query-only contexts. Do not infer desired labels from IDs; judge user semantics and actual scope contracts.',
        'scopes':brief['scopes'],'normative_rules':brief['normative_rules'],'schema':brief['schema'],
        'cases':[],
        'output':'reports/search_v2c_smarteng_independent_review.json','source_query_artifact_sha256':sha(input_path)}
    # Standard JSON decoding projects only query/context; no labels in packet.
    packet['cases']=[{k:x[k] for k in ['case_id','query_text','scope_type','workspace_type','search_mode']} for x in [json.loads(s) for s in input_path.read_text(encoding='utf8').splitlines()]]
    with (R/(output+'blind_reviewer_packet.json')).open('x',encoding='utf8') as f:json.dump(packet,f,indent=2,ensure_ascii=False)
    print(json.dumps({k:out[k] for k in ['status','established_audit','additional_collisions','distinct_actual_topologies']}))
if __name__=='__main__':main()
