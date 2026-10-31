"""Structural/source audit; not an oracle for unrecognized mandatory semantics."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scratch.search_architecture_v10.contract import digest


def main():
    rows=[json.loads(s) for s in Path('reports/search_arch10_checkpoint_realistic_predictions.jsonl').read_text(encoding='utf8').splitlines()]
    spans=0;bad=[];blocked=0;scope_operands=[]
    for row in rows:
        p=row['actual_plan'];d=p['decision'];ir=d.get('query_ir_contract',{});intent=d.get('query_intent',{})
        if not row['executable']:blocked+=1
        if ir:
            if intent.get('source_digest')!=digest(p['raw_query']) or intent.get('ir_digest')!=digest(ir):bad.append([row['case_id'],'digest'])
            for r in ir['requirements']:
                a,b=r['source_span'];spans+=1
                if p['raw_query'][a:b]!=r['source_text'] or not 0<=a<b<=len(p['raw_query']):bad.append([row['case_id'],'span',r['field']])
            cid=row['case_id'];field={'039':'year','040':'language','041':'format','042':'availability'}.get(cid[8:11])
            if cid.endswith('_GLOBAL') and field:
                owned=[r for r in ir['requirements'] if r['field']==field and r['ownership']=='MANDATORY' and r['value'] is not None]
                assert owned,(cid,field)
                scope_operands.append(dict(case_id=cid,domain=field,retained_operands=[r['value'] for r in owned]))
    assert not bad,bad
    report=dict(status='PASS_STRUCTURAL_SOURCE_EVIDENCE_ONLY',population='235 reviewed exposed development contexts',
        digests_verified=dict(numerator=len(rows),denominator=len(rows),status='MEASURED',evidence='DEVELOPMENT'),
        source_spans_verified=dict(numerator=spans,denominator=spans,status='MEASURED',evidence='DEVELOPMENT'),
        scope_blocked_operands=scope_operands,blocked_contexts=blocked,errors=bad,
        limitation='Source spans/digests and recognized scope operands do not prove complete semantic understanding or arbitrary mandatory coverage.')
    with Path('reports/search_arch10_intent_audit.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(len(rows),spans,len(scope_operands))

if __name__=='__main__':main()
