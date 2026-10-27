"""Inventory exact immutable C3 failures before changing C4 parser behavior."""
from collections import Counter,defaultdict
import hashlib,json
from pathlib import Path
R=Path('reports')
DEFS={
 'literal_mode_contract':('MODE_LITERAL_GOLD_CONTRACT','Explicit TITLE_AUTHOR mode is source evidence for the complete literal operand; original SMART-oriented title label disputes require independent review.','CONTRACT_REVIEW'),
 'identifier_contract':('IDENTIFIER_GOLD_CONTRACT','Complete ISBN syntax is accepted exact identity evidence; semantic-only labels require independent review.','CONTRACT_REVIEW'),
 'fuzzy_subject':('ALIAS_OVERMATCH','Fuzzy correction is accepted legacy behavior but the benchmark requires semantic fallback; do not force contract changes for score.','HIGH'),
 'fieldless_comparator_negated':('SPAN_OVERLAP_PRECEDENCE','Negation consumes the no in a fieldless numeric comparator, hiding the number from ambiguity handling.','HIGH'),
 'comma_negative_boundary':('NEGATION_SCOPE_ERROR','Comma followed by just starts an affirmative subject clause, not another free-text negative operand.','HIGH'),
 'category_negative_boundary':('CLAUSE_BOUNDARY_OVERREACH','Negative subject list crosses a following in-category or when-finding category clause.','HIGH'),
 'generic_topic_subject':('SOFT_TOPIC_AS_STRICT_SUBJECT','Generic catalogue head nouns before about/on introduce topical prose, not an explicit canonical subject filter.','HIGH'),
 'comma_list_ambiguity':('NEGATION_SCOPE_ERROR','A mixed constraint query has an unresolved comma-only excluded-subject list boundary.','HIGH'),
 'unsupported_boolean':('UNSUPPORTED_FIELD_AS_STRICT_FILTER','Conditional otherwise subject logic is not representable as a conjunctive plan.','HIGH'),
}
def cluster(row):
 f=row['family_id'];q=row['query_text'].casefold()
 if f=='resume_title_author_mode':return 'literal_mode_contract'
 if f=='d22_isbn_like':return 'identifier_contract'
 if f=='d17_typographical_noise':return 'fuzzy_subject'
 if f=='c05_clarification_units':return 'fieldless_comparator_negated'
 if f=='d12_multi_reordering':return 'comma_list_ambiguity'
 if f=='c11_unsupported_positive_boolean':return 'unsupported_boolean'
 if f=='d05_by_vs_about' or 'stories on ' in q:return 'generic_topic_subject'
 if ', just ' in q:return 'comma_negative_boundary'
 return 'category_negative_boundary'
def main():
 ff=json.loads((R/'search_v2c_c3_false_hard_filters_after.json').read_text())['cases'];assert len(ff)==194
 groups=defaultdict(list)
 for r in ff:
  cid=cluster(r);taxonomy,reason,severity=DEFS[cid];a=r['actual_plan'];fields={x[0] for x in r['false_filters']}
  groups[cid].append({'query_id':r['query_id'],'query':r['query_text'],'family':r['family_id'],'expected_decision':r['expected_decision'],'actual_decision':r['decision'],'expected_hard_fields':r['expected_strict_filters'],'actual_hard_fields':{k:a.get(k) for k in ['subjects','exclude_subjects','exclude_terms','title_text','author_text','exact_text','rating_min','rating_max','year_min','year_max','formats','availability']},'invented_fields_and_values':r['false_filters'],'source_spans_used':a['constraint_candidates'],'source_span_sufficient':None if severity=='CONTRACT_REVIEW' else False,'proof_issue':reason,'candidate_set_impact':'Can reject records satisfying the authored contract; mode/identifier disputes may establish that the authored contract is defective' if severity=='CONTRACT_REVIEW' else 'An additional hard predicate rejects otherwise eligible records, or a blocked query executes','severity':severity})
 result={'basis':'Exact immutable C3 reviewed-view failure report; no C4 parser execution','cases':194,'clustered_cases':sum(map(len,groups.values())),'clusters':[{'cluster_id':k,'taxonomy':DEFS[k][0],'count':len(v),'families':dict(Counter(r['family'] for r in v)),'reason':DEFS[k][1],'representative_examples':v[:3],'cases':v} for k,v in sorted(groups.items(),key=lambda kv:-len(kv[1]))],'miscellaneous_cases':0,'taxonomy_not_observed':['BARE_NUMBER_AS_RATING','YEAR_AS_PUBLICATION_YEAR','VERSION_AS_RATING','TITLE_NUMBER_AS_FILTER','EDITION_LIKE_NUMBER','TOPIC_AS_AUTHOR','FORMAT_INFERENCE_WITHOUT_EXPLICIT_SOURCE','AVAILABILITY_INFERENCE_WITHOUT_EXPLICIT_SOURCE']}
 (R/'search_v2c_c4_false_filter_clusters.json').write_text(json.dumps(result,indent=2))
 contradictions=json.loads((R/'search_v2c_c3_contradictions.json').read_text())['cases'];miss=[r for r in contradictions if r['decision']!='CONTRADICTORY' and not any(c.get('code')=='rating_domain_assumption' for c in r.get('label_review_concerns',[]))];assert len(miss)==26
 rows=[]
 for r in miss:
  fmt=r['family_id']=='c01_exclusivity_clashes'
  rows.append({'query_id':r['query_id'],'query':r['query_text'],'family':r['family_id'],'resolved_constraints':r['actual_plan']['constraint_candidates'],'expected_contradiction_type':'FORMAT_INCLUDE_EXCLUDE' if fmt else 'SUBJECT_INCLUDE_EXCLUDE','expected_hard_fields':r['expected_strict_filters'],'actual_decision':r['decision'],'why_missed':'except is absent from format-negative operators; positive scanner consumes its operand first, leaving a false missing-subject cue' if fmt else 'terminal request punctuation remains on the required subject operand before canonical lookup','root_cause_id':'format_except_precedence' if fmt else 'subject_requirement_punctuation'})
 (R/'search_v2c_c4_remaining_contradictions_before.json').write_text(json.dumps({'supported_denominator':583,'misses':26,'cases':rows,'no_reclassification_or_denominator_change':True},indent=2))
 # Query/capability-only independent semantic input, without original labels,
 # parser outputs, scores, current source or failure information.
 scopes=json.loads((R/'search_v2c_c_scope_vocabularies.json').read_text());gold=[json.loads(l) for l in (R/'search_v2c_a_gold_queries.jsonl').read_text().splitlines()]
 queries=[]
 for c in gold:
  if c['id'] in ['gold-065','gold-066','gold-069','gold-094','gold-095']:queries.append({'review_id':c['id'],'query':c['query'],'scope':'CANONICAL_REVIEW','mode':'SMART'})
 for key,q,prior in [('mixed_refinement','not romance rated above 4','books about machine learning'),('kg_negative','books about neural networks but not romance rated above 4',None),('chip_removal_without_session','include Fiction and Mystery but exclude Romance and Biography rated above 3',None),('chip_removal_with_session','include Fiction and Mystery but exclude Romance and Biography rated above 3',None)]:
  queries.append({'review_id':key,'query':q,'scope':'CANONICAL_REVIEW','mode':'SMART','prior_query':prior,'post_action':{'remove_subject':'Fiction','remove_excluded_subject':'Romance'} if key.startswith('chip_removal') else None})
 for i,q in enumerate(['not romance','but not romance','excluding romance','without romance','except romance','not about romance','not only romance','non-fiction','Java but not JavaScript','AI excluding deep learning']):queries.append({'review_id':f'natural-{i+1:02}','query':q,'scope':'CANONICAL_REVIEW','mode':'SMART'})
 dev={r['query_id']:r for l in (R/'search_v2c_c2_v2_development.jsonl').read_text().splitlines() if (r:=json.loads(l))}
 for r in ff:
  if cluster(r) in ['literal_mode_contract','identifier_contract']:
   c=dev[r['query_id']];queries.append({'review_id':c['query_id'],'query':c['query_text'],'scope':c['scope_type'],'mode':c.get('search_mode','SMART')})
 review={'version':'C4-query-only-independent-semantic-review','queries':queries,'scopes':scopes,'CANONICAL_REVIEW':{'subjects':['Fiction','Romance','Military History','History','Mystery','Biography','Java','JavaScript','Deep learning'],'capabilities':{'rating':True,'year':True,'formats':['ONLINE','PHYSICAL','BOTH']}},'normative_contract':{'SMART':'Explicit canonical subject exclusions and literal text negatives are distinct predicates. Do not infer both without semantic justification. About concerns content/topic rather than a catalogue category. Not only is not a prohibition. A subject exclusion rejects any matching canonical subject; text negatives search title/author/subjects/description.','TITLE_AUTHOR':'Complete supplied literal is matched against title OR author; SMART grammar is not applied. Do not drop request prefixes or punctuation.','EXACT_IDENTIFIER':'Complete ISBN10/13 or OL work ID is accepted identity syntax in SMART; identity existence is not needed for executable status.','session':'Explicit refinements preserve unrelated accepted fields; chip removal removes only addressed items.'},'requested_output':'For each review_id independently author only justified expected fields and decision/execution; include semantic reason, candidate eligibility example and AI_REVIEWED provenance. Do not read original labels or parser/source/results. Freeze authored values before any comparison. Use production field names title_text/author_text/exact_text/subjects/exclude_subjects/exclude_terms/rating_min/rating_max, decision and executable. Partial unresolved fields must stay visible.'}
 (R/'search_v2c_c4_review_query_only_input.json').write_text(json.dumps(review,indent=2))
 print(json.dumps({'false_filter_clusters':{k:len(v) for k,v in groups.items()},'contradiction_causes':dict(Counter(r['root_cause_id'] for r in rows)),'review_queries':len(queries)}))
if __name__=='__main__':main()
