"""Evaluate sealed, independently labelled Search cases without modifying labels."""
from collections import Counter,defaultdict
from dataclasses import asdict
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,sys,time,statistics
from search.query_plan import parse_query
from search.query_confidence import validate,executable
from search.query_calibration import assess
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports'
MAPPING={'expected_intent':'intent','expected_subjects':'subjects','expected_excluded_subjects':'exclude_subjects','expected_exclude_terms':'exclude_terms',
 'expected_author':'author_text','expected_exact_text':'exact_text','expected_rating_min':'rating_min','expected_rating_max':'rating_max',
 'rating_min_exclusive':'rating_min_exclusive','rating_max_exclusive':'rating_max_exclusive','expected_year_min':'year_min','expected_year_max':'year_max',
 'year_min_exclusive':'year_min_exclusive','year_max_exclusive':'year_max_exclusive','expected_format':'formats','expected_exclusive_formats':'exclusive_formats',
 'expected_excluded_formats':'excluded_formats','expected_availability':'availability','expected_sort':'sort','expected_semantic_text':'semantic_text','expected_soft_preferences':'soft_preference'}
HARD=('subjects','exclude_subjects','exclude_terms','author_text','title_text','exact_text','rating_min','rating_max','year_min','year_max','formats','exclusive_formats','excluded_formats','availability','language')
def norm(v):
 if isinstance(v,(int,float)) and not isinstance(v,bool):return float(v)
 if isinstance(v,str):return ' '.join(v.casefold().split())
 if isinstance(v,list):return sorted(norm(x) for x in v)
 return v

def expected(case):
 d={field:case[key] for key,field in MAPPING.items() if key in case}
 if 'expected_title_entity' in case:d['title_text']=case['expected_title_entity']
 if 'expected_title' in case:d['title_text']=case['expected_title']
 if 'expected_language' in case:d['language']=case['expected_language']
 # Legacy author schema uses None for an unspecified sort and a list for soft
 # preferences. These are representation adapters, not parser-derived labels.
 if d.get('sort') is None:d['sort']='RELEVANCE'
 return d

def atoms(d,allowed=True):
 if not allowed:return set()
 a=set()
 for k in HARD:
  v=d.get(k)
  if v is not None and v!=[] and v!='':
   for value in v if isinstance(v,list) else [v]:a.add((k,str(norm(value)),bool(d.get(k+'_exclusive')) if k.startswith(('rating','year')) else False))
 return a

def ratio(n,d):return {'numerator':n,'denominator':d,'percent':100*n/d if d else None}
def token_f1(a,b):
 x=Counter(re.findall(r'\w+(?:\+\+|#)?|[^\w\s]',norm(a or '')));y=Counter(re.findall(r'\w+(?:\+\+|#)?|[^\w\s]',norm(b or '')));overlap=sum((x&y).values());total=sum(x.values())+sum(y.values())
 return 2*overlap/total if total else 1.

def evaluate_case(c,scopes):
 assert not c.get('requires_native_execution'), 'Stateful/security cases require a native executor'
 scope=scopes[c['scope_type']];mode=c.get('search_mode','SMART');mode={'semantic':'SMART','exact':'EXACT','genre_subject':'GENRE_SUBJECT','title_author':'TITLE_AUTHOR'}.get(mode,mode)
 p=validate(parse_query(c.get('query_text',c.get('query')),scope['subjects'],mode),scope['capabilities']);a=asdict(p);e=expected(c)
 a['semantic_text']=p.semantic_text or ''
 a['soft_preference']=[] if not p.soft_preference else [p.soft_preference]
 actual_kind=p.decision.get('decision_type','EXECUTABLE');allow=executable(p);wanted=c['execution_allowed']
 expected_kind={'AUTO_EXECUTE':'EXECUTABLE','EXECUTE_WITH_NOTICE':'EXECUTABLE_WITH_NOTICE'}.get(c['expected_decision'],c['expected_decision'])
 mismatch={k:{'expected':v,'actual':a.get(k)} for k,v in e.items() if norm(a.get(k))!=norm(v)}
 if actual_kind!=expected_kind:mismatch['decision']={'expected':expected_kind,'actual':actual_kind}
 if allow!=wanted:mismatch['execution_allowed']={'expected':wanted,'actual':allow}
 for label,kind in [('expected_unsupported_fields','UNSUPPORTED'),('expected_incomplete_fields','INCOMPLETE'),('expected_contradiction_fields','CONTRADICTORY')]:
  if label in c:
   actual=p.decision.get('affected_fields',[]) if actual_kind==kind else []
   if norm(actual)!=norm(c[label]):mismatch[label]={'expected':c[label],'actual':actual}
 ea=atoms(e,wanted);aa=atoms(a,allow);textually_justified=atoms(e,True)
 protected=c.get('protected_spans',[]);literal=' '.join(str(a.get(k) or '') for k in ['semantic_text','title_text','exact_text','author_text'])
 preserved=all(norm(span['text']) in norm(literal) for span in protected)
 comp_expected=[k for k in ('rating_min','rating_max') if e.get(k) is not None]
 comp_ok=all(a.get(k)==e[k] and a.get(k+'_exclusive')==e.get(k+'_exclusive',False) for k in comp_expected)
 extra=aa-textually_justified
 # Missing a desired typed decision is reported separately from inventing a
 # hard constraint. Executing a contradiction is always unsafe. Silently
 # dropping an explicit unsupported strict field is also unsafe.
 unsafe=allow and not wanted and (bool(extra) or expected_kind=='CONTRADICTORY' or expected_kind=='UNSUPPORTED' and actual_kind!='EXECUTABLE_WITH_NOTICE')
 foreign=[s for s in p.subjects+p.exclude_subjects if norm(s) not in set(map(norm,scope['subjects']))]
 return {'query_id':c['query_id'],'family_id':c['family_id'],'split':c['split'],'category':c['category'],'scope':c['scope_type'],
 'expected_decision':expected_kind,'decision':actual_kind,'expected_execution':wanted,'execution':allow,'exact':not mismatch,'mismatches':mismatch,
 'unsafe_auto_parse':unsafe,'safe_typed_decision_miss':allow and not wanted and not unsafe,
 'hard_tp':len(ea&aa),'hard_fp':len(aa-ea),'hard_fn':len(ea-aa),'false_filters':[list(x) for x in sorted(extra)],'comparator_evaluable':bool(comp_expected) and wanted,
 'comparator_correct':comp_ok,'negative_correct':all(norm(a.get(k))==norm(e.get(k)) for k in ('exclude_subjects','exclude_terms') if k in e),
 'subjects_correct':norm(p.subjects)==norm(e.get('subjects',[])),'semantic_exact':norm(a['semantic_text'])==norm(e.get('semantic_text')),
 'semantic_f1':token_f1(p.semantic_text,e.get('semantic_text')),'protected_count':len(protected),'protected_preserved':preserved,
 'foreign_canonical_values':foreign,'assessment':assess(p),'actual_plan':a}

def aggregate(rows):
 n=len(rows);ex=lambda flag:sum(bool(r[flag]) for r in rows)
 blocked=[r for r in rows if not r['expected_execution']];safe=[r for r in rows if r['expected_execution']]
 comparator=[r for r in rows if r['comparator_evaluable']];protected=[r for r in rows if r['protected_count']]
 tp=sum(r['hard_tp'] for r in rows);fp=sum(r['hard_fp'] for r in rows);fn=sum(r['hard_fn'] for r in rows)
 metrics={'EXACT_PLAN_MATCH':ratio(ex('exact'),n),'DECISION_ACCURACY':ratio(sum(r['decision']==r['expected_decision'] for r in rows),n),
 'HARD_CONSTRAINT_PRECISION':ratio(tp,tp+fp),'HARD_CONSTRAINT_RECALL':ratio(tp,tp+fn),'COMPARATOR_ACCURACY':ratio(sum(r['comparator_correct'] for r in comparator),len(comparator)),
 'SUBJECT_EXACTNESS':ratio(ex('subjects_correct'),n),'NEGATIVE_CONSTRAINT_ACCURACY':ratio(ex('negative_correct'),n),
 'SEMANTIC_REMAINDER_EXACT_MATCH':ratio(ex('semantic_exact'),n),'SEMANTIC_REMAINDER_TOKEN_F1':{'numerator':sum(r['semantic_f1'] for r in rows),'denominator':n,'percent':100*sum(r['semantic_f1'] for r in rows)/n if n else None},
 'PROTECTED_ENTITY_PRESERVATION':ratio(sum(r['protected_preserved'] for r in protected),len(protected)),
 'UNSAFE_AUTO_PARSE_RATE':ratio(sum(r.get('unsafe_auto_parse',r['execution']) for r in blocked),len(blocked)),
 'FALSE_HARD_FILTER_RATE':ratio(sum(bool(r['false_filters']) for r in rows),n),
 'FALSE_CLARIFICATION_RATE':ratio(sum(r['decision'] in ('AMBIGUOUS','INCOMPLETE') for r in safe),len(safe)),
 'CROSS_SCOPE_VOCABULARY_LEAKAGE_RATE':ratio(sum(bool(r['foreign_canonical_values']) for r in rows),n)}
 for kind,key in [('AMBIGUOUS','AMBIGUITY_RECALL'),('CONTRADICTORY','CONTRADICTION_RECALL'),('INCOMPLETE','INCOMPLETE_RECALL'),('UNSUPPORTED','UNSUPPORTED_HONESTY')]:
  subset=[r for r in rows if r['expected_decision']==kind];metrics[key]=ratio(sum(r['decision']==kind for r in subset),len(subset))
 return metrics

def run(split,phase):
 manifest=json.loads((R/'search_v2c_c_holdout_manifest.json').read_text());scopes=json.loads((R/'search_v2c_c_scope_vocabularies.json').read_text())
 if split=='heldout':
  freeze=R/'search_v2c_c_parser_freeze.json';assert freeze.exists(),'Freeze before opening heldout';f=json.loads(freeze.read_text())
  assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h for path,h in f['files'].items()),'Parser changed after freeze'
  marker=R/'search_v2c_c_heldout_opened.json';assert not marker.exists(),'Heldout can only be evaluated once; do not tune against observed answers'
  marker.write_text(json.dumps({'opened_at':datetime.now(timezone.utc).isoformat(),'phase':phase}))
 cases=[]
 for file in manifest['files']:
  p=ROOT/file['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==file['sha256']
  cases.extend(c for line in p.read_text().splitlines() if (c:=json.loads(line))['split']==split)
 rows=[];start=time.perf_counter()
 for c in cases:
  try:rows.append(evaluate_case(c,scopes))
  except Exception as error:raise RuntimeError('Evaluation error in '+c['query_id']) from error
 out={'split':split,'phase':phase,'cases':len(rows),'metrics':aggregate(rows),'elapsed_s':time.perf_counter()-start,
      'by_family':{fam:aggregate([r for r in rows if r['family_id']==fam]) for fam in sorted({r['family_id'] for r in rows})},
      'by_scope':{scope:aggregate([r for r in rows if r['scope']==scope]) for scope in sorted({r['scope'] for r in rows})}}
 (R/f'search_v2c_c_{split}_{phase}_metrics.json').write_text(json.dumps(out,indent=2));(R/f'search_v2c_c_{split}_{phase}_observations.jsonl').write_text('\n'.join(json.dumps(r,default=str) for r in rows)+'\n')
 print(json.dumps({'split':split,'cases':len(rows),'metrics':out['metrics']},indent=2))
if __name__=='__main__':run(sys.argv[1],sys.argv[2])
