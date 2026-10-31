"""Established structure audit, exposed-only extension and opaque review packet.

No parser/scorer/predictions. Sealed rows stay inside the established auditor.
"""
from pathlib import Path
import ast,json,hashlib,sys
from scripts import search_v2c_c5a_sealed_audit as sealed
R=Path('reports');P='search_proof6_'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,ensure_ascii=False)
def main():
    tag=sys.argv[1] if len(sys.argv)>1 else 'author1';assert tag.isalnum()
    input_path=R/(P+'authored.jsonl');pre=json.loads((R/(P+'preflight.json')).read_text(encoding='utf-8'))
    protected={str(Path(k).resolve()):h for k,h in pre['protected_files'].items()}
    assert sha('scripts/search_v2c_c5a_sealed_audit.py')==protected[str(Path('scripts/search_v2c_c5a_sealed_audit.py').resolve())]
    sealed.PREFIX=P+tag+'_'
    target=R/(P+tag+'_sealed_structural_isolation.json');assert not target.exists()
    result=sealed.audit(input_path.resolve(),target.resolve())
    c2=Path('scripts/search_v2c_c2_benchmark.py');identity,structure=sealed.pure_c2_functions(c2,protected[str(c2.resolve())])
    scope=sealed.load_json(R/'search_v2c_c_scope_vocabularies.json');baseline=[]
    for n in ['search_v2c_c2_v2_development.jsonl','search_v2c_c5b_calibration_cases.jsonl','search_v2c_c5e_independent_authored.jsonl','search_v2c_c5e_independent_authored_v3.jsonl','search_v2c_c5er_authored.jsonl','search_v2c_c5er_authored_v2.jsonl','search_v2c_smarteng_authored.jsonl','search_comp3_authored.jsonl','search_comp3_authored_v2.jsonl']:
        baseline.extend(sealed.projected_rows(R/n))
    conservative=[]
    for d in ['scratch/search_v2c_c5d_repair','scratch/search_v2c_c5d_repair_v2','scratch/search_v2c_c5e','scratch/search_v2c_c5er','scratch/search_smart_engineering','scratch/search_compositional_recovery_v3','scratch/search_proof_recovery_v4','scratch/search_proof_recovery_v5','scratch/search_proof_recovery_v6']:
        for p in Path(d).rglob('test*.py'):
            for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
                if isinstance(n,ast.Constant) and isinstance(n.value,str) and len(n.value)>7:conservative.append({'query_text':n.value,'search_mode':'SMART'})
    topologies={structure(x) for x in baseline+conservative};identities={identity(x,scope) for x in baseline}
    new=list(sealed.projected_rows(input_path,new=True));collisions=[]
    for x in new:
        hits=[]
        if structure(x) in topologies:hits.append('EXPOSED_OPERATION_TOPOLOGY')
        if identity(x,scope) in identities:hits.append('EXPOSED_CANONICAL_CONTEXT')
        if hits:collisions.append({'new_case_id':x['new_case_id'],'collision_kinds':hits})
    actual_topologies=len({structure(x) for x in new})
    status='PASS' if result['status']=='PASS' and not result['collision_counts'] and not collisions and actual_topologies>=30 else 'OVERLAP_BLOCKED'
    write(tag+'_structural_isolation.json',{'status':status,'established_audit':result,'additional_collisions':collisions,'distinct_actual_topologies':actual_topologies,'source_population_sha256':sha(input_path),'exposed_rows':len(baseline),'conservative_test_strings':len(conservative),'heldout_evaluations':0,'heldout_content_emitted':False,'parser_calls':0,'scoring_calls':0})
    if status!='PASS':
        print(json.dumps({'status':status,'established_audit':result,'additional_collisions':collisions,'actual_topologies':actual_topologies}));return
    authored=[json.loads(s) for s in input_path.read_text(encoding='utf-8').splitlines()];brief=json.loads((R/(P+'blind_author_brief.json')).read_text(encoding='utf-8'))
    mapping={};cases=[]
    for i,x in enumerate(authored):
        rid='R'+hashlib.sha256(('v6-review-'+str(i)).encode()).hexdigest()[:16];mapping[rid]=x['case_id']
        row={k:x[k] for k in ['query_text','scope_type','workspace_type','search_mode']};row['review_id']=rid
        if x.get('completion_input'):row['completion_input']=x['completion_input']
        cases.append(row)
    write('reviewer_id_map.json',mapping)
    write('blind_reviewer_packet.json',{'task':'Independent normative review; query/context only. Infer labels and applicability yourself. No author labels, candidate/predictions or desired scores are available.',
        'scopes':brief['scopes'],'normative_rules':brief['normative_rules'],'schema':brief['schema'],'cases':cases,
        'output':'reports/search_proof6_independent_review.json','source_population_sha256':sha(input_path)})
    print(json.dumps({'status':'PASS','contexts':len(authored),'actual_topologies':actual_topologies,'review_packet_ready':True,'sealed_content_emitted':False}))
if __name__=='__main__':main()
