"""Current V8 controls against preserved, incomplete local Qwen capture (development)."""
from pathlib import Path
from dataclasses import asdict
import json,time
from scratch.search_proof_recovery_v8 import parser
from scratch.search_proof_recovery_v8.restricted import parse as restricted
from scratch.search_proof_recovery_v8.extraction import validate_proposal,compile_proposal

R=Path('reports')


def rate(n,d):
    return dict(numerator=n,denominator=d,percent=100*n/d if d else None,population='EXPOSED_DEVELOPMENT')


def main():
    inputs=[json.loads(s) for s in (R/'search_proof7_pilot_review_packet.jsonl').read_text().splitlines()]
    raw=json.loads((R/'search_proof8a3_model_capture.json').read_text())
    model={x['id']:x for x in raw['records'] if x.get('event')=='prediction' and x.get('phase')=='serial'}
    predictions=[]
    for row in inputs:
        record=dict(row,candidates={})
        for name,call in [('deterministic',lambda:parser.validate(parser.parse_query(row['query'],['Fiction','History','Science']),{})),('restricted',lambda:restricted(row['query'],['Fiction','History','Science']))]:
            st=time.perf_counter();p=call()
            record['candidates'][name]=dict(decision=p.decision['decision_type'],executable=parser.executable(p),plan=asdict(p),elapsed_ms=(time.perf_counter()-st)*1000)
        learned=dict(decision='AMBIGUOUS',executable=False,plan=None,observed=row['id'] in model,fallback=True,status='MISSING_OUTPUT_SAFE_CLARIFICATION')
        if row['id'] in model:
            m=model[row['id']]
            try:
                assert m['status']=='CAPTURED'
                validate_proposal(row['query'],m['raw_output'])
                v=compile_proposal(row['query'],m['raw_output'],['Fiction','History','Science'],{})
                learned['status']=v['status'];learned['reason']=v['reason']
                if v.get('plan'):
                    p=v['plan'];learned.update(decision=p.decision['decision_type'],executable=parser.executable(p),plan=asdict(p),fallback=False)
            except Exception as e:learned.update(status='SCHEMA_OR_RUNTIME_SAFE_REJECTION',error=str(e))
        record['candidates']['learned_proof']=learned;predictions.append(record)
    gold={x['id']:x for x in map(json.loads,(R/'search_proof7r1_pilot_frozen_development_view.jsonl').read_text().splitlines())}
    optional={'v7_dev_pilot_03','v7_dev_pilot_14'}
    def norm(v):
        return ' '.join(v.casefold().split()) if isinstance(v,str) else v
    for row in predictions:
        g=gold[row['id']];row['oracle']=g
        for p in row['candidates'].values():
            p['typed_correct']=p['decision'] in ['EXECUTABLE','EXECUTABLE_WITH_NOTICE'] if row['id'] in optional else p['decision']==g['decision']
            p['execution_correct']=p['executable']==g['executable']
            p['native_fields']=[dict(field=k,expected=v,actual=p['plan'].get(k) if p['plan'] else None,correct=bool(p['plan']) and norm(p['plan'].get(k))==norm(v)) for k,v in g['native_fields'].items()]
    def summarize(rows,name):
        blocked=[x for x in rows if not x['oracle']['executable']];valid=[x for x in rows if x['oracle']['executable']]
        exact=[x for x in rows if x['id'] not in optional];fields=[f for x in rows for f in x['candidates'][name]['native_fields']]
        return dict(typed_policy=rate(sum(x['candidates'][name]['typed_correct'] for x in rows),len(rows)),
                    typed_exact=rate(sum(x['candidates'][name]['typed_correct'] for x in exact),len(exact)),
                    execution=rate(sum(x['candidates'][name]['execution_correct'] for x in rows),len(rows)),
                    false_execution=rate(sum(x['candidates'][name]['executable'] for x in blocked),len(blocked)),
                    missed_valid=rate(sum(not x['candidates'][name]['executable'] for x in valid),len(valid)),
                    native_fields=rate(sum(f['correct'] for f in fields),len(fields)))
    summaries={name:summarize(predictions,name) for name in ['deterministic','restricted','learned_proof']}
    observed=[x for x in predictions if x['id'] in model]
    result=dict(population='18 exposed pilot contexts, not acceptance',candidate=parser.PARSER_VERSION,
                summaries=summaries,common_observed_subset={n:summarize(observed,n) for n in summaries},
                learned_actual_outputs=len(model),learned_missing_outputs=18-len(model),
                learned_capture='Prior standalone V8 pinned Qwen attempt3, reused immutable raw predictions; no new inference',
                learned_limitation='Full-cohort learned_proof includes16 missing-output clarifications, not learned accuracy. Only2 real outputs; neither passed current schema. No complete measured hybrid comparison.',
                optional_notice_policy='reports/search_combined8_semantic_contract.json; original historical gold unmodified',records=predictions)
    with (R/'search_combined8_development_comparison.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,ensure_ascii=False)
    print(json.dumps(dict(summaries=summaries,actual_model_outputs=len(model))))


if __name__=='__main__':main()
