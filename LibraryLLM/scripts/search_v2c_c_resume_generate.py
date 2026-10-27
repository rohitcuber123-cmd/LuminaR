"""Sealed label-preserving derivatives. No parser/evaluator imports or outputs."""
from pathlib import Path
from copy import deepcopy
from collections import Counter,defaultdict
import json,hashlib,itertools
R=Path('reports')
def load(p):return [json.loads(l) for l in p.read_text(encoding='utf-8-sig').splitlines() if l.strip()]
def dump(p,rows):p.write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows),encoding='utf8',newline='\n')
assert json.loads((R/'search_v2c_c_preflight_security.json').read_text())['status']=='PASS'
original_manifest=json.loads((R/'search_v2c_c_resume_history/search_v2c_c_holdout_manifest.json').read_text())
for f in original_manifest['files']:assert hashlib.sha256(Path(f['path']).read_bytes()).hexdigest()==f['sha256']
reviews={r['query_id']:r for r in load(R/'search_v2c_c_resume_label_review.jsonl')};assert len(reviews)==540
core=[]
for split in ['development','calibration','heldout']:
 for original in load(R/f'search_v2c_c_gold_{split}.jsonl'):
  r=deepcopy(original);review=reviews[r['query_id']];r.update(query_text=r['query'],template_id=r['family_id']+'_authored',variant_seed=None,workspace_type='GLOBAL' if r['scope_type']=='GLOBAL' else 'STAFF' if 'STAFF' in r['scope_type'] else 'PATRON',authoring_source=r['authored_by'],review_source='independent output-blind reviewer; search_v2c_c_resume_label_review.jsonl',review_status=review['review_status'],reviewer_type='AI',human_reviewed=False,expected_execution_allowed=r['execution_allowed'],expected_title=r.get('expected_title_entity'),expected_ambiguity=r['expected_ambiguous_spans'],expected_contradiction=r['expected_contradiction_fields'],label_review_concerns=review['concerns'],generation_safe=review['generation_safe'])
  r['requires_native_execution']=review.get('requires_native_execution',False) or r['family_id'] in ['d24_refinement_turns','d25_instead_turns'];r['parser_evaluable']=not r['requires_native_execution']
  core.append(r)
core+=load(R/'search_v2c_c_resume_additional_core.jsonl');assert len(core)==612
used=set()
def key(r):return (r['query_text'].casefold(),r['scope_type'],r['search_mode'],r.get('expected_action'),r['family_id'] if r.get('requires_native_execution') else None)
for r in core:used.add(key(r))
prefixes=['Please find ','Find me ','Show me ','Could you find ','Can you show me ','I am looking for ','I would like ','Please search for ','Help me find ','Give me ','Please show me ','Search for ','Could you show me ','I want to find ','Please help me find ','I would like to find ']
suffixes=['','?','.',' please',' please?',' please.']
seeded=[];category_parents={}
def hard_count(r):return len(r.get('expected_subjects',[]))+sum(r.get(k) is not None for k in ['expected_rating_min','expected_rating_max','expected_year_min','expected_year_max','expected_author'])+len(r.get('expected_format',[]))+len(r.get('expected_excluded_subjects',[]))
base=[r for r in core if r.get('generation_safe',r.get('parser_evaluable',True)) and not r.get('requires_native_execution') and r['search_mode'].upper()!='EXACT']
selections={
 'paraphrase_word_order':(2000,base),
 'noisy_malformed':(1000,base),
 'contradiction_negative':(750,[r for r in base if r['expected_decision']=='CONTRADICTORY' or r.get('expected_exclude_terms') or r.get('expected_excluded_subjects')]),
 'ambiguous_incomplete':(750,[r for r in base if r['expected_decision'] in ['AMBIGUOUS','INCOMPLETE','CLARIFY']]),
 'multi_constraint':(1000,[r for r in base if hard_count(r)>=2]),
 'entity_number_protection':(500,[r for r in base if r.get('protected_spans')]),
 'tenant_security_scope':(500,[r for r in core if r.get('requires_native_execution') and r.get('security_case')])}
for category,(target,parents) in selections.items():
 assert parents,category
 count=0;source_ids=set()
 # Round robin sources before adding a second transform to any parent.
 for transform_id,(prefix,suffix) in enumerate(itertools.product(prefixes,suffixes)):
  for parent in parents:
   r=deepcopy(parent);q=parent['query_text'];new=prefix+q+suffix
   framing=prefix;ending=suffix
   if category=='noisy_malformed':framing=prefix.rstrip()+',  ';ending=' ??' if transform_id%2 else ' !?';new=framing+q+ending
   assert len(new)<=500
   r.update(query_id=f'v2cc-seeded-{category}-{count+1:04}',query=new,query_text=new,parent_query_id=parent['query_id'],category=category,template_id=parent['family_id']+'_polite_noise_invariance',variant_seed=26015+len(seeded),authoring_source='deterministic label-invariant derivative of independently authored parent',review_source='UNREVIEWED generated derivative; parent independently AI-reviewed',review_status='UNREVIEWED',reviewer_type=None,human_reviewed=False,transformation={'prefix':framing,'suffix':ending,'kind':'nonliteral polite framing and terminal punctuation; no operator/entity/negation edits'})
   if key(r) in used:continue
   for span in r.get('protected_spans',[]):
    span['start']+=len(framing);span['end']+=len(framing);assert new[span['start']:span['end']]==span['text']
   for step in r.get('sequence_steps',[]):
    if 'query_text' in step:step['query_text']=new
   used.add(key(r));seeded.append(r);source_ids.add(parent['query_id']);count+=1
   if count==target:break
  if count==target:break
 assert count==target,(category,count,target,len(parents));category_parents[category]={'cases':count,'distinct_authored_parents':len(source_ids),'eligible_parent_count':len(parents)}
rows=core+seeded;assert len(rows)==7112 and len({r['query_id'] for r in rows})==7112
family_splits=defaultdict(set)
for r in rows:family_splits[r['family_id']].add(r['split'])
assert all(len(s)==1 for s in family_splits.values())
dump(R/'search_v2c_c_gold.jsonl',core);dump(R/'search_v2c_c_adversarial.jsonl',seeded)
files=[]
for split in ['development','calibration','heldout']:
 p=R/f'search_v2c_c_resume_{split}.jsonl';selected=[r for r in rows if r['split']==split];dump(p,selected);files.append({'path':str(p),'split':split,'count':len(selected),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
manifest={'version':'V2C-C-resume-1','status':'FROZEN_LABELS_BEFORE_FIRST_EVALUATION; not accepted','total':len(rows),'unique_query_texts':len({r['query_text'] for r in rows}),'families':len(family_splits),'splits':dict(Counter(r['split'] for r in rows)),'review_counts':dict(Counter(r['review_status'] for r in rows)),'human_reviewed':0,'independently_authored':612,'seeded':len(seeded),'categories':category_parents,'files':files,'legacy_original_manifest':original_manifest,'original_draft_unchanged':True,'heldout_evaluated':False,'policy':'Every derivative stays in original parent family/split. Exact-mode originals are never polite-prefix transformed. Generated rows remain UNREVIEWED. Independent review concerns stay attached and original labels are never replaced.','exposure':'Main agent inadvertently saw10 originalh11 source rows; recorded pre-exposed, excluded from generation. No parser tuning based on them; no heldout evaluation yet. Two contextual exact-text overlap groups flagged by blind reviewer; not claimed strictly unseen query text.'}
(R/'search_v2c_c_holdout_manifest.json').write_text(json.dumps(manifest,indent=2))
(R/'search_v2c_c_query_families.json').write_text(json.dumps({'families':[{'family_id':fam,'split':next(iter(splits)),'count':sum(r['family_id']==fam for r in rows)} for fam,splits in sorted(family_splits.items())]},indent=2))
scope_matrix={scope:{'cases':sum(r['scope_type']==scope for r in rows),'families':sorted({r['family_id'] for r in rows if r['scope_type']==scope})} for scope in sorted({r['scope_type'] for r in rows})}
(R/'search_v2c_c_scope_matrix.json').write_text(json.dumps({'scopes':scope_matrix,'note':'Offline canonical snapshots are scope-specific. Does not claim every family has native execution in every applicable scope; coverage gaps remain explicit. Native rows must not be evaluated through parser-only harness.'},indent=2))
print(json.dumps({k:manifest[k] for k in ['total','unique_query_texts','families','splits','review_counts','seeded','categories']},indent=2))
