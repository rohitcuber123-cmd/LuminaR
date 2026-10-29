"""V7 measurement adapters use the SAME ontology as compilation and editing."""
from .ontology import target,NATIVE,DOMAINS


def completion_oracle(gold):
    o=gold['expected_completion'];decision=o.get('decision',o.get('expected_typed_decision'))
    return {'case_id':gold['case_id']+':completion','scope_type':gold['scope_type'],
        'decision_stratum':decision,'expected_typed_decision':decision,
        'expected_executable':decision in ['EXECUTABLE','EXECUTABLE_WITH_NOTICE'],
        'expected_hard_constraints':o.get('hard_constraints',o.get('expected_hard_constraints',{})),
        'metric_applicability':o.get('metric_applicability',{}),
        'expected_sort':o.get('expected_sort',o.get('sort','RELEVANCE')),
        'expected_semantic_remainder':o.get('expected_semantic_remainder')}


def score_roles(query,annotations,requirements):
    results=[]
    for o in annotations:
        text=o.get('source_text',o.get('text',''));field=o.get('field',o.get('domain'))
        try:domain=target(field).domain
        except ValueError:
            domain=NATIVE.get(field) # boolean flag may be annotated but never edited as an operand
        if not domain or not text or query.count(text)!=1 or o.get('status') in ['N/A','UNRESOLVED']:
            results.append({'applicable':False,'oracle':o,'reason':'No unique registered source/domain oracle'});continue
        a=query.index(text);b=a+len(text)
        matches=[r for r in requirements if (r['field']==domain or domain=='semantic' and r['field']=='semantic_residue') and (r['source_span'][0]<=a<b<=r['source_span'][1] or a<=r['source_span'][0]<r['source_span'][1]<=b)]
        roles=sorted({r['source_role'] for r in matches});modalities=sorted({r['modality'] for r in matches})
        results.append({'applicable':True,'oracle':o,'domain':domain,'actual_roles':roles,'actual_modalities':modalities,'role_correct':roles==[o['role']],'modality_correct':modalities==[o['modality']]})
    return results
