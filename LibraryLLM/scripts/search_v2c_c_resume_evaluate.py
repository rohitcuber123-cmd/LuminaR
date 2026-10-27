"""Split-isolated evaluation with explicit safety stop and one-shot holdout fence."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import json,hashlib,sys,time
from scripts.search_v2c_c_evaluate import evaluate_case,aggregate,ratio
R=Path('reports');split=sys.argv[1]
assert json.loads((R/'search_v2c_c_preflight_security.json').read_text())['status']=='PASS'
manifest=json.loads((R/'search_v2c_c_holdout_manifest.json').read_text());selected=[f for f in manifest['files'] if f['split']==split];assert len(selected)==1
if split=='heldout':
 freeze=json.loads((R/'search_v2c_c_parser_freeze.json').read_text());assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in freeze['files'].items())
 marker=R/'search_v2c_c_heldout_opened.json';assert not marker.exists(),'One heldout evaluation only';marker.write_text(json.dumps({'opened_at':datetime.now(timezone.utc).isoformat()}))
f=selected[0];p=Path(f['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==f['sha256']
cases=[json.loads(l) for l in p.read_text(encoding='utf8').splitlines()];native=[c for c in cases if c.get('requires_native_execution')];parser=[c for c in cases if not c.get('requires_native_execution')]
scopes=json.loads((R/'search_v2c_c_scope_vocabularies.json').read_text());rows=[];start=time.perf_counter()
for c in parser:
 r=evaluate_case(c,scopes);r.update(authoring_source=c['authoring_source'],review_status=c['review_status'],label_review_concerns=c.get('label_review_concerns',[]),query_text=c['query_text']);rows.append(r)
metrics=aggregate(rows);violations=[]
def threshold(key,op,limit):
 value=metrics[key]['percent']
 if value is not None and not op(value,limit):violations.append({'metric':key,'observed':metrics[key],'required':limit})
threshold('FALSE_HARD_FILTER_RATE',lambda a,b:a<=b,1)
threshold('UNSAFE_AUTO_PARSE_RATE',lambda a,b:a<b,3)
threshold('CONTRADICTION_RECALL',lambda a,b:a==b,100)
threshold('PROTECTED_ENTITY_PRESERVATION',lambda a,b:a>=b,99)
threshold('COMPARATOR_ACCURACY',lambda a,b:a>=b,99)
threshold('CROSS_SCOPE_VOCABULARY_LEAKAGE_RATE',lambda a,b:a==b,0)
result={'version':manifest['version'],'split':split,'corpus_split_rows':len(cases),'parser_evaluated':len(rows),'native_not_executed':len(native),'metrics':metrics,'mandatory_violations':violations,'status':'SAFETY_THRESHOLD_STOP' if violations else 'PASS_THIS_SPLIT','elapsed_s':time.perf_counter()-start,'by_scope':{s:aggregate([r for r in rows if r['scope']==s]) for s in sorted({r['scope'] for r in rows})},'by_family':{s:aggregate([r for r in rows if r['family_id']==s]) for s in sorted({r['family_id'] for r in rows})},'by_provenance':{s:aggregate([r for r in rows if r['review_status']==s]) for s in sorted({r['review_status'] for r in rows})},'safety_definition':'False hard filters compare enforced actual atoms against textually justified gold atoms, even on blocked gold. Hard precision/recall separately use execution-eligible gold atoms. Unsafe means executable blocked gold with invented hard atoms, a contradiction, or silently ignored unsupported strict metadata; safe literal typed-decision misses are separate. Rates include numerator/denominator; no parser-derived gold.','native_case_ids':[c['query_id'] for c in native]}
(R/f'search_v2c_c_resume_{split}_metrics.json').write_text(json.dumps(result,indent=2))
(R/f'search_v2c_c_resume_{split}_observations.jsonl').write_text(''.join(json.dumps(r,default=str)+'\n' for r in rows))
if violations:(R/'search_v2c_c_resume_stop.json').write_text(json.dumps({'stop':'MANDATORY_SAFETY_THRESHOLD_FAILURE','split':split,'violations':violations,'parser_changes_allowed_after_this':False,'heldout_evaluated':False,'calibration_run':False,'observed_at':datetime.now(timezone.utc).isoformat()},indent=2))
print(json.dumps({k:result[k] for k in ['split','corpus_split_rows','parser_evaluated','native_not_executed','status','metrics','mandatory_violations']},indent=2))
