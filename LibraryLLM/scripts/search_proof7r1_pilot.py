"""Exposed development pilot; original gold and all V7 results remain immutable."""
from pathlib import Path
from dataclasses import asdict
import json,hashlib,time
from scratch.search_proof_recovery_v7r1 import parser

R=Path('reports')


def main():
    read=lambda name:[json.loads(s) for s in (R/name).read_text(encoding='utf-8').splitlines()]
    a=read('search_proof7_pilot_authored.jsonl');b={x['id']:x for x in read('search_proof7_pilot_independent_review.jsonl')}
    adjudication=json.loads((R/'search_proof7r1_pilot_contract_adjudication.json').read_text(encoding='utf-8'))
    findings={x['id']:x for x in adjudication['findings']}
    view=[]
    for x in a:
        other=b[x['id']];f=findings.get(x['id'])
        decision=f['resolved_decision_or_UNRESOLVED'] if f else x['decision'] if x['decision']==other['decision'] else 'UNRESOLVED'
        executable=f['resolved_executable'] if f else x['executable'] if x['executable']==other['executable'] else None
        fields=f['resolved_native_field_assertions'] if f else {k:v for k,v in x['expected_native_fields'].items() if other['expected_native_fields'].get(k)==v}
        view.append({'id':x['id'],'query':x['query'],'decision':None if decision=='UNRESOLVED' else decision,'executable':executable,'native_fields':fields,'provenance':'blind_source_contract_adjudication' if f else 'original_author_reviewer_agreement'})
    with (R/'search_proof7r1_pilot_development_view.jsonl').open('x',encoding='utf-8') as stream:
        for x in view:stream.write(json.dumps(x,ensure_ascii=False)+'\n')
    results=[]
    for x in view:
        start=time.perf_counter();p=parser.validate(parser.parse_query(x['query'],['Fiction','History','Science']),{})
        fields=[]
        norm=lambda v:' '.join(v.casefold().split()) if isinstance(v,str) else v
        for key,expected in x['native_fields'].items():
            actual=getattr(p,key);fields.append({'field':key,'expected':expected,'actual':actual,'correct':norm(expected)==norm(actual)})
        results.append({**x,'actual_decision':p.decision['decision_type'],'actual_execution':parser.executable(p),'typed_correct':p.decision['decision_type']==x['decision'] if x['decision'] else None,'execution_correct':parser.executable(p)==x['executable'] if x['executable'] is not None else None,'fields':fields,'plan':asdict(p),'elapsed_ms':(time.perf_counter()-start)*1000})
    known=[x for x in results if x['typed_correct'] is not None];exe=[x for x in results if x['execution_correct'] is not None]
    blocked=[x for x in results if x['executable'] is False];valid=[x for x in results if x['executable'] is True];executed=[x for x in results if x['actual_execution']]
    fields=[f for x in results for f in x['fields']]
    report={'population':'EXPOSED_V7_PILOT_DEVELOPMENT_ONLY','fresh_acceptance':False,'gold_edited':False,'view_policy':'New explicit derived view; original author/reviewer and V7metrics preserved. Notice subtype on03/14 remains excluded. Contract adjudicator was original reviewer, blind to candidate results; not a third reviewer.',
        'typed':{'numerator':sum(x['typed_correct'] for x in known),'denominator':len(known)},'execution':{'numerator':sum(x['execution_correct'] for x in exe),'denominator':len(exe)},
        'false_execution':{'numerator':sum(x['actual_execution'] for x in blocked),'denominator':len(blocked)},'missed_execution':{'numerator':sum(not x['actual_execution'] for x in valid),'denominator':len(valid)},
        'native_field_assertions':{'numerator':sum(f['correct'] for f in fields),'denominator':len(fields)},'critical_executed_field_mismatches':{'numerator':sum(any(not f['correct'] for f in x['fields']) for x in executed),'denominator':len(executed)},
        'source_files':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('scratch/search_proof_recovery_v7r1').glob('*.py')},'records':results}
    with (R/'search_proof7r1_pilot_results.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2,ensure_ascii=False)
    print(json.dumps({k:v for k,v in report.items() if k not in ['records','source_files']}))


if __name__=='__main__':main()
