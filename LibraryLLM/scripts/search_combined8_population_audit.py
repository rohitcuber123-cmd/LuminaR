"""Metadata-only wrapper of unchanged sealed auditor plus exposed-history checks."""
from pathlib import Path
import argparse,json,hashlib
from collections import Counter
import scripts.search_v2c_c5a_sealed_audit as established

R=Path('reports')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,d):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(d,f,indent=2)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--tag',required=True);a=ap.parse_args()
    assert a.tag.isalnum();p=Path(a.input).resolve();assert p.parent==R.resolve() and p.name.startswith('search_combined8_')
    protected=json.loads((R/'search_combined8_protected_inventory.json').read_text())['files']
    tool=Path('scripts/search_v2c_c5a_sealed_audit.py')
    expected=next(h for q,h in protected.items() if Path(q).resolve()==tool.resolve());assert sha(tool)==expected
    prefix='search_combined8_'+a.tag+'_';out=R/(prefix+'sealed_structural_isolation.json')
    assert not out.exists() and not (R/(prefix+'sealed_access_audit.json')).exists()
    oldlog=sha(R/'search_v2c_c5a_sealed_access_audit.json')
    established.PREFIX=prefix
    result=established.audit(p,out.resolve())
    assert sha(tool)==expected and sha(R/'search_v2c_c5a_sealed_access_audit.json')==oldlog
    manifest=json.loads((R/'search_v2c_c2_holdout_manifest.json').read_text())
    c2=Path('scripts/search_v2c_c2_benchmark.py')
    h=next(h for q,h in manifest['source_hashes'].items() if q.replace('\\','/')==str(c2).replace('\\','/'))
    identity,structure=established.pure_c2_functions(c2.resolve(),h)
    scopes=json.loads((R/'search_v2c_c_scope_vocabularies.json').read_text())
    exposed=['search_v2c_c5e_reviewed_population_v3.jsonl','search_v2c_c5er_reviewed_population.jsonl','search_v2c_smarteng_reviewed_population.jsonl','search_comp3_reviewed_population.jsonl','search_proof6_reviewed_population.jsonl','search_combined8_c5c_devfinal_parser_inputs.jsonl','search_proof7_pilot_review_packet.jsonl']
    prior={k:set() for k in ['canonical_context_sha256','operation_topology_sha256','family_sha256','component_sha256']}
    def projected(row):
        scope=established.SCOPE_ALIASES.get(row.get('scope_type','GLOBAL'),row.get('scope_type','GLOBAL'))
        return dict(query_text=row.get('query_text',row.get('query')),search_mode=row.get('search_mode','SMART'),scope_type=scope,
                    workspace_type='GLOBAL' if scope=='GLOBAL' else 'STAFF' if scope.endswith('STAFF') else 'PATRON',
                    **{k:row[k] for k in ['family_id','structural_family_id','structural_component_id','requires_native_execution','expected_action'] if k in row})
    for name in exposed:
        for row in map(json.loads,(R/name).read_text(encoding='utf-8').splitlines()):
            fp=established.fingerprints(projected(row),scopes,identity,structure)
            for k,v in fp.items():
                if v:prior[k].add(v)
    new=[json.loads(s) for s in p.read_text(encoding='utf-8').splitlines()]
    collisions=[];topologies=set();contexts=Counter()
    for row in new:
        x=projected(row);fp=established.fingerprints(x,scopes,identity,structure);topologies.add(fp['operation_topology_sha256']);contexts[fp['canonical_context_sha256']]+=1
        kinds=[k for k,v in fp.items() if v and v in prior[k]]
        if kinds:collisions.append(dict(new_case_id=row['case_id'],collision_types=kinds,required_action='DISCARD_NEW_CASE'))
    report=dict(input=str(p),input_sha256=sha(p),established_sealed_result=result,additional_exposed_collisions=collisions,
                contexts=len(new),unique_contexts=len(contexts),duplicate_context_excess=sum(v-1 for v in contexts.values()),
                distinct_actual_topologies=len(topologies),distinct_declared_linguistic_families=len({x['family_id'] for x in new}),
                scope_counts=dict(Counter(x['scope_type'] for x in new)),decision_counts=dict(Counter(x['expected_typed_decision'] for x in new)),
                prior_exposed_paths_sha256={name:sha(R/name) for name in exposed},
                sealed_content_emitted=False,heldout_evaluations=0,candidate_calls=0,algorithms_changed=False,
                namespace_change_only=True,note='Established trace key only_new_c5a_reports_written refers to runtime PREFIX; original C5A log unchanged. Coarse topology isolation excludes many simple/easy formulations.')
    report['structural_pass']=result['status']=='PASS' and not collisions and not report['duplicate_context_excess']
    save(R/(prefix+'structural_isolation.json'),report)
    print(json.dumps({k:report[k] for k in ['contexts','distinct_actual_topologies','distinct_declared_linguistic_families','structural_pass']},ensure_ascii=False))

if __name__=='__main__':main()
