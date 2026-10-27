"""Established sealed audit adapter plus all exposed C5C/C5D/C5E structures.

No heldout examples, labels or identities are emitted. No parser is invoked.
"""
import ast,json,hashlib,sys
from pathlib import Path
from scripts import search_v2c_c5a_sealed_audit as sealed
R=Path('reports');P='search_v2c_c5e_'
def main():
    tag=sys.argv[1] if len(sys.argv)>1 else ''
    assert tag in ['', 'v3']
    prefix=P+(tag+'_' if tag else '')
    input_path=R/(P+('independent_authored_v3.jsonl' if tag else 'independent_authored.jsonl'))
    pre=json.loads((R/(P+'preflight.json')).read_text(encoding='utf8'))
    source='scripts/search_v2c_c5a_sealed_audit.py'
    protected={str(Path(k).resolve()):v for k,v in pre['protected_files'].items()}
    assert hashlib.sha256(Path(source).read_bytes()).hexdigest()==protected[str(Path(source).resolve())]
    sealed.PREFIX=prefix
    result=sealed.audit(input_path.resolve(),(R/(prefix+'sealed_structural_isolation.json')).resolve())
    scope=sealed.load_json(R/'search_v2c_c_scope_vocabularies.json')
    source=Path('scripts/search_v2c_c2_benchmark.py')
    identity,structure=sealed.pure_c2_functions(source,hashlib.sha256(source.read_bytes()).hexdigest())
    baseline=[]
    for path in [R/'search_v2c_c5b_calibration_cases.jsonl',R/'search_v2c_c2_v2_development.jsonl']:
        baseline.extend(sealed.projected_rows(path))
    focused=[]
    directories=['scratch/search_v2c_c5d_repair','scratch/search_v2c_c5d_repair_v2','scratch/search_v2c_c5e']
    sources=[]
    for directory in directories:
        for path in Path(directory).rglob('test*.py'):
            sources.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            for node in ast.walk(ast.parse(path.read_text(encoding='utf8'))):
                if isinstance(node,ast.Constant) and isinstance(node.value,str) and len(node.value)>7:
                    # Conservative: every test string is a possible exposed SMART
                    # query. This can reject extra structures but never relaxes C2.
                    focused.append({'query_text':node.value,'search_mode':'SMART','scope_type':'GLOBAL','workspace_type':'GLOBAL'})
    topologies={structure(row) for row in baseline+focused}
    identities={identity(row,scope) for row in baseline}
    matches=[]
    for row in sealed.projected_rows(input_path,new=True):
        kinds=[]
        if structure(row) in topologies:kinds.append('operation_topology')
        if identity(row,scope) in identities:kinds.append('canonical_context')
        if kinds:matches.append({'new_case_id':row['new_case_id'],'collision_kinds':kinds})
    final={'status':'PASS' if result['status']=='PASS' and not matches and not result['collision_counts'] else 'OVERLAP_BLOCKED',
           'established_sealed_summary':result,'exposed_additional_rows':len(baseline),'conservative_test_strings':len(focused),
           'additional_colliding_new_rows':matches,'test_source_hashes':sources,'heldout_queries_labels_ids_topologies_emitted':False,
           'heldout_evaluations':0,'parser_calls':0,'new_scope_identity_shortcuts':False,'methodology_changed':False}
    with (R/(prefix+'structural_isolation.json')).open('x',encoding='utf8') as f:json.dump(final,f,indent=2)
    print(json.dumps({k:final[k] for k in ['status','established_sealed_summary','exposed_additional_rows','conservative_test_strings','additional_colliding_new_rows']}))
if __name__=='__main__':main()
