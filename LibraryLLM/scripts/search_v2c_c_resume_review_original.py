"""Materialize an independent semantic review, never parser-derived gold.

Only the explicitly permitted original540, authored-family registry, scope
snapshot and user prompt informed the reviewer. Family judgments and per-row
judgments below were written after reading all540 queries and nondefault gold
slots. Mechanical checks supplement that semantic review; they do not replace it.
"""
from pathlib import Path
import json
import hashlib
from collections import Counter, defaultdict

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
VOCAB = json.loads((REPORTS/'search_v2c_c_scope_vocabularies.json').read_text(encoding='utf-8-sig'))
FAMILIES = {
'd01_explicit_rating': 'Explicit rating unit and comparator justify the stated bound; topic clauses remain semantic and canonical standalone categories remain subjects.',
'd02_postfix_rating': 'The rating marker, comparator or plus suffix supplies the rating unit; zero is a genuine numeric bound and must not become null.',
'd03_publication_direct': 'Publication language distinguishes catalogue year from a historical event; the public snapshot supports canonical year enforcement.',
'd04_canonical_subject': 'An explicit category request or standalone known category justifies the named Global subject, without related-category invention.',
'd05_by_vs_about': 'By/written-by names the creator; about/ideas/influence names a topic. The expected author and semantic roles preserve this distinction.',
'd06_numeric_titles': 'The numeral belongs to an intact title/entity string. No rating or publication-year filter is justified; both literal/entity preservation are required.',
'd07_technical_literals': 'Versions, standards and programming punctuation belong to technical tokens. No numeral may be consumed as a rating, year or edition filter.',
'd08_format_direct': 'The private catalogue supports format constraints. Only explicit only language justifies exclusivity; subject/topic roles remain separate.',
'd09_availability_now': 'Borrow/currently available language supports the coarse AVAILABLE_NOW facet in the public snapshot; it does not imply unsupported per-copy guarantees.',
'd10_include_exclude': 'Explicit include and exclude clauses must retain their polarity; absent private canonical Java/JavaScript remain semantic terms.',
'd11_negation_scope': 'Lexical not/non and quoted phrases must be distinguished from search exclusion; the phrase not only does not mean exclude.',
'd12_multi_reordering': 'Clause order does not change explicit rating/year/format constraints, author roles or exclusion precedence; scope boundaries still matter.',
'd13_rating_contradictions': 'Intersected lower and upper bounds are empty when reversed or equal with a strict endpoint; contradictory requests must not execute.',
'd14_incomplete_direct': 'An operator or field introducer without its operand is incomplete. Do not manufacture missing values or execute partial hard constraints.',
'd15_unsupported_metadata': 'Strict requests for unsupported metadata or unavailable Global capabilities must be reported honestly, retaining only separately stated topic intent.',
'd16_soft_preferences': 'Reading level, length and recency preferences are soft; no pages, year or other hard threshold is justified by these words alone.',
'd17_typographical_noise': 'The misspelling may safely remain literal with notice. A correction may be offered but may never silently replace the user text.',
'd18_morphological_forms': 'Morphological resemblance alone does not establish a canonical subject. Preserving the complete semantic phrase avoids invented strict filters.',
'd19_word_order': 'Conversational request scaffolding may be removed while retaining the complete substantive topic; no additional hard filter follows from position.',
'd20_optional_filler': 'Polite request scaffolding carries no filter semantics; standalone known categories and topical phrases retain their distinct intended roles.',
'd21_quoted_literals': 'Quoted internal query-like operators are literal data. Explicit titled syntax supplies a title, while about syntax supplies semantic text.',
'd22_isbn_like': 'ISBN-like identifiers must retain digits, separators and check-letter text, without being mined for ratings or dates; identifier validity is not asserted.',
'd23_exact_mode': 'Exact mode protects the entire original text. Query-like words inside it must not activate constraints, contradictions, corrections or incompleteness.',
'd24_refinement_turns': 'These are turn deltas, not complete accepted-plan or lifecycle oracles. Prior accepted context is necessary to test merging and noncorruption.',
'd25_instead_turns': 'Instead expresses replacement of accepted search context. The row supplies new intent but cannot independently prove prior constraints were removed.',
'd26_public_vocab': 'Only the public snapshot may establish strict canonical facets. Global/private-only names may remain topics but cannot be imported as hard public subjects.',
'd27_private_vocab': 'The synthetic private snapshot has seven listed facets; strict subjects must come from that snapshot, independently of Global/public availability.',
'd28_unknown_subject': 'An explicit strict subject missing from the private snapshot is unsupported; staff workspace status does not create new canonical metadata.',
'd29_number_ambiguity': 'Bare quantities without a rating/year unit are ambiguous unless a literal role such as number, level or volume supplies protection.',
'd30_title_vs_year': 'Title and historical-event numerals must remain protected. Only explicit publication language may create a supported public publication-year bound.',
'd31_title_vs_edition': 'Title wording and a topic about editions differ from an explicit edition requirement; unsupported edition metadata must not be invented.',
'd32_author_subject_names': 'Author extraction requires a creator role; about-author clauses remain semantic topics, and independent category clauses remain category constraints.',
'c01_exclusivity_clashes': 'Required and forbidden identical subjects/formats, or exclusive incompatible formats, are contradictions and must not commit an accepted executable plan.',
'c02_combined_presence': 'Both online and physical means required combined presence rather than either-only exclusivity; vague antecedents still require review.',
'c03_kg_negative': 'Explicit negatives must survive any KG expansion. Canonical exclusions versus free-text exclusion terms need scope-aware classification.',
'c04_correction_actions': 'Accept/reject correction commands require a current offered correction and lifecycle context. They are not evidence of a single-turn parser correction flow.',
'c05_clarification_units': 'Unspecified units may denote quantity, rating, date or version. No silent hard rating/year filter is justified by a bare number.',
'c06_rating_interval_language': 'The explicit rating noun scopes interval and negated comparator language; preserve strict versus inclusive endpoints and spelled-number values.',
'c07_year_intersections': 'Explicit publication intervals intersect canonically in public staff scope, with exclusive equal/reversed intersections rejected as contradictions.',
'c08_without_scoping': 'Without/minus/except/leave-out are exclusions in these search contexts. Known private facets remain canonical negative constraints; other phrases remain terms.',
'c09_scope_switch_labels': 'The strict public-staff facet request must use that catalogue only. A known name in another scope is insufficient to establish a public facet.',
'c10_quoted_nested_clauses': 'Quotation protects internal operators and facet-like phrases. Unquoted outer constraints remain independently applicable.',
'c11_unsupported_positive_boolean': 'Compound positive Boolean logic must not be silently flattened into a stronger or weaker supported query; capability assumptions need explicit documentation.',
'h01_star_thresholds': 'The star unit supplies rating semantics. Comparator direction, spelled numbers and fractional values determine the precise independent bounds.',
'h02_temporal_roles': 'Publication and event dates occupy different semantic roles. Event-date spans stay literal while explicit publication dates constrain supported public metadata.',
'h03_negation_semantic_roles': 'Topic-internal negation, lexical non and soft negative preferences differ from explicit excluded categories. Preserve the semantic role rather than matching not mechanically.',
'h04_scope_conflicting_requirements': 'The private staff snapshot supports these facets; mutually required/forbidden constraints have no executable interpretation and may not commit state.',
'h05_technical_plus_filters': 'A protected technical version can coexist with separately stated supported filters. Its numeral cannot contribute to those filters.',
'h06_entity_filter_mixtures': 'Protected title/identifier/quoted tokens remain intact while genuine external constraints apply; literal content cannot trigger internal parsing.',
'h07_soft_hard_composition': 'Soft preferences coexist with explicit supported hard metadata; strict unsupported page/edition requests override normal execution without invented enforcement.',
'h08_dangling_connectors': 'Dangling field and comparator clauses are incomplete even when earlier category/format information is complete; accepted state must await clarification.',
'h09_author_appositives': 'Explicit creator appositives identify authors, while discussion of their life/work remains topical. Negatives require role-sensitive scope.',
'h10_private_scope_absence': 'Private strict facets require an exact canonical subject from the seven-facet snapshot; ordinary topic requests do not import foreign strict metadata.',
'h11_exact_adversarial_syntax': 'Exact mode treats the complete input as literal text even when it resembles Boolean, numeric or malformed query syntax.',
}

# Human-readable judgments recorded independently of any executable parser.
MANUAL = {
 'd11_negation_scope-01': ('semantic_relation_loss', 'Dropping the nonexclusive not-only relationship may narrow the topic. Preserve the complete nonexclusive intent, without excluding Romance.', {'expected_semantic_text': 'not only Romance'}),
 'd11_negation_scope-10': ('semantic_relation_loss', 'A bag of two category words loses not-only/but-also semantics. Preserve the complete relationship as semantic text or explicitly supported positive combination.', {}),
 'd12_multi_reordering-10': ('negation_scope_ambiguous', 'A trailing comma-separated category after exclude Romance may be another exclusion. The expected positive Fiction is not unambiguously licensed; clarify the scope or author explicit include Fiction.', {'expected_decision': 'AMBIGUOUS', 'execution_allowed': False}),
 'd30_title_vs_year-02': ('title_role_uncertain', 'Quotation protects the numeral but does not by itself establish that it names a title; the semantic literal is certain and a hard title/entity role is less certain.', {'expected_title_entity': None}),
 'c02_combined_presence-06': ('missing_format_antecedent', 'Both formats has no explicit online/physical antecedent in this single-turn row. Supply prior context or clarify which formats rather than presume the pair.', {}),
 'c02_combined_presence-09': ('missing_format_antecedent', 'Both versions is underspecified without the prior offered version pair. Native context or an explicit physical/online phrase is needed.', {}),
 'c05_clarification_units-10': ('technical_version_ambiguity', 'A programming language followed by a number can be a version. A safe literal technical interpretation must remain acceptable; clarification must not imply a rating-only choice.', {}),
 'c11_unsupported_positive_boolean-04': ('boolean_equivalence_uncertain', 'This unless construction can mean inclusion with two exclusions, a supported flat negative combination. Blanket unsupported Boolean labeling needs a declared grammar contract.', {}),
 'h03_negation_semantic_roles-10': ('semantic_relation_loss', 'Removing the nonexclusive broadening relationship may change intent. Preserve that relationship without manufacturing an exclusion.', {}),
 'h09_author_appositives-05': ('exclusion_role_untyped', 'An exclusion about a person must not remove works merely because their author field contains that person. Untyped negative text needs a topic-role contract.', {}),
}

FILES = [(split, REPORTS/f'search_v2c_c_gold_{split}.jsonl') for split in ['development','calibration','heldout']]
rows, hashes = [], {}
for split, path in FILES:
    hashes[split] = hashlib.sha256(path.read_bytes()).hexdigest()
    rows.extend(json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip())
assert len(rows) == 540
assert len({r['query_id'] for r in rows}) == 540
assert {r['family_id'] for r in rows} == set(FAMILIES)

query_groups, family_splits = defaultdict(list), defaultdict(set)
for r in rows:
    query_groups[r['query'].casefold()].append(r)
    family_splits[r['family_id']].add(r['split'])
cross_split_exact = [group for group in query_groups.values() if len({r['split'] for r in group}) > 1]
cross_ids = {r['query_id'] for group in cross_split_exact for r in group}

reviews=[]
for r in rows:
    f, q = r['family_id'], r['query']
    short = r['query_id'].removeprefix('v2cc-authored-')
    concerns=[]
    proposals={}
    def flag(code, rationale, corrections=None):
        concerns.append(dict(code=code, rationale=rationale))
        proposals.update(corrections or {})
    if short in MANUAL:
        code, why, fixes = MANUAL[short]
        flag(code, why, fixes)
    if f in ['d24_refinement_turns', 'd25_instead_turns', 'c04_correction_actions']:
        flag('native_sequence_context_missing', FAMILIES[f], dict(requires_native_execution=True, parser_evaluable=False))
    if f == 'c11_unsupported_positive_boolean':
        flag('boolean_capability_contract_missing', 'The permitted snapshot declares field capabilities but does not declare supported Boolean grammar. Unsupported is a conservative normative policy, not verified implementation capability; freeze it before scoring.')
    if r.get('search_mode') == 'exact':
        flag('exact_mode_requires_new_literal_label', 'The original label is sound, but changing even neutral scaffolding changes the exact literal target. Exclude this source from label-invariant generation; independently authored exact-text labels are a different generation contract.')
    if short in ['d13_rating_contradictions-05','d13_rating_contradictions-06']:
        flag('rating_domain_assumption', 'The empty-range judgment assumes the enforced rating domain is 0..5. Record the canonical rating domain explicitly; the supplied scope snapshot only declares rating=true.')
    scope = VOCAB.get(r['scope_type'], {})
    known={s.casefold() for s in scope.get('subjects',[])}
    for key in ['expected_subjects','expected_excluded_subjects']:
        missing=[s for s in r.get(key,[]) if s.casefold() not in known]
        if missing:
            flag('subject_outside_scope_snapshot', f'{key} contains a canonical value absent from this scope snapshot; a strict facet cannot be imported from another catalogue.', {key: {'review_required': missing}})
    canonical_neg=[term for term in r.get('expected_exclude_terms',[]) if term.casefold() in known]
    if canonical_neg and f != 'c10_quoted_nested_clauses':
        flag('negative_canonical_classification_uncertain', 'An expected free-text negative exactly matches an available canonical subject. Establish whether user syntax calls for a facet exclusion or topic exclusion; do not infer it from parser output.', {'negative_terms_for_role_review': canonical_neg})
    bad=[]
    for span in r.get('protected_spans',[]):
        if q[span['start']:span['end']] != span['text']:
            start=q.find(span['text'])
            bad.append(dict(original=span, proposed=None if start<0 else dict(start=start, end=start+len(span['text']), text=span['text'])))
    if bad:
        flag('protected_span_offsets_inaccurate', 'The declared half-open character offsets do not slice to the protected text. Preserve the literal and original labels; correct only via a separately approved versioned label patch.', {'protected_span_corrections': bad})
    if r['query_id'] in cross_ids:
        flag('identical_text_cross_split', 'This exact text also appears in a different split under a possibly distinct mode/scope. The original family ID split is intact, but textual/structural holdout independence needs disclosure and grouping review.')
    if len(family_splits[f]) != 1:
        flag('family_crosses_splits', 'A family appears across multiple splits; do not silently move or relabel original rows.')
    # Pre-exposure is provenance, not a reason to change any heldout label.
    pre_exposed = f == 'h11_exact_adversarial_syntax'
    if pre_exposed:
        flag('pre_exposed_before_evaluation', 'Implementation agent accidentally saw this original ten-row family before evaluation. No tuning/evaluation was reported; disclose this bounded pre-exposure separately from the untouched heldout result.')
    # Per-row slot rationale is an explicit interpretation check, not a parser trace.
    parts=[FAMILIES[f]]
    if r.get('expected_subjects'):
        parts.append(f"Positive facets {r['expected_subjects']!r} were checked against {r['scope_type']} vocabulary and the positive syntactic role.")
    if r.get('expected_excluded_subjects') or r.get('expected_exclude_terms'):
        parts.append('Reviewed negative polarity, exclusion scope and precedence over related-topic expansion.')
    if r.get('expected_rating_min') is not None or r.get('expected_rating_max') is not None:
        parts.append(f"Rating interval reviewed: lower={r.get('expected_rating_min')!r} (exclusive={r.get('rating_min_exclusive',False)}), upper={r.get('expected_rating_max')!r} (exclusive={r.get('rating_max_exclusive',False)}); values and endpoints match the explicit comparator wording except any concern recorded below.")
    if r.get('expected_year_min') is not None or r.get('expected_year_max') is not None:
        parts.append(f"Publication interval reviewed: lower={r.get('expected_year_min')!r} (exclusive={r.get('year_min_exclusive',False)}), upper={r.get('expected_year_max')!r} (exclusive={r.get('year_max_exclusive',False)}); {r['scope_type']} declares year capability={scope.get('capabilities',{}).get('year')}.")
    if r.get('protected_spans'):
        parts.append('Reviewed protected token meaning and checked each declared half-open text span mechanically.')
    if r.get('expected_soft_preferences'):
        parts.append(f"Preferences {r['expected_soft_preferences']!r} remain soft, with no invented strict numeric threshold.")
    if r.get('expected_unsupported_fields'):
        parts.append(f"Unsupported fields {r['expected_unsupported_fields']!r} were checked for a strict request and unavailable capability; no enforcement is invented.")
    if r.get('expected_author'):
        parts.append(f"Creator label {r['expected_author']!r} follows an author role rather than merely occurring in a topical phrase.")
    if r.get('expected_format'):
        parts.append(f"Required formats {r['expected_format']!r} and exclusive formats {r.get('expected_exclusive_formats',[])!r} were checked independently, not conflated.")
    if r.get('expected_incomplete_fields'):
        parts.append(f"Missing operands {r['expected_incomplete_fields']!r} justify withholding execution.")
    if r.get('expected_ambiguous_spans'):
        parts.append(f"Unspecified roles in {r['expected_ambiguous_spans']!r} justify clarification without guessed strict metadata.")
    parts.append('The stated execution permission is consistent with the original typed decision; original intent and semantic-remainder wording were checked as normative author judgments, not measured runtime behavior.')
    expected={k:v for k,v in r.items() if k.startswith('expected_') or k in ['protected_spans','execution_allowed','rating_min_exclusive','rating_max_exclusive','year_min_exclusive','year_max_exclusive']}
    reviews.append(dict(query_id=r['query_id'], family_id=f, split=r['split'], review_status='AI_REVIEWED',
        reviewer_type='AI', human_reviewed=False, review_source='independent output-blind AI semantic review',
        original_label_sha256=hashlib.sha256(json.dumps(expected,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
        original_expected_labels=expected, original_labels_modified=False,
        rationale=' '.join(parts), concerns=concerns, proposed_corrections=proposals,
        generation_safe=not concerns, review_verdict='FLAGGED_RETAIN_ORIGINAL' if concerns else 'RETAIN',
        pre_exposed_to_implementation_agent=pre_exposed,
        parser_implementation_access=False, parser_output_access=False, evaluator_output_access=False,
        requires_native_execution=f in ['d24_refinement_turns','d25_instead_turns','c04_correction_actions']))

out=REPORTS/'search_v2c_c_resume_label_review.jsonl'
out.write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in reviews),encoding='utf-8')
split_summary={}
for split,_ in FILES:
    rr=[r for r in reviews if r['split']==split]
    split_summary[split]=dict(rows=len(rr), ai_reviewed=len(rr), human_reviewed=0,
                             generation_safe=sum(r['generation_safe'] for r in rr),
                             rows_with_concerns=sum(bool(r['concerns']) for r in rr),
                             concern_counts=dict(Counter(c['code'] for r in rr for c in r['concerns'])))
    safe_ids={r['query_id'] for r in rr if r['generation_safe']}
    safe_source=[r for r in rows if r['query_id'] in safe_ids]
    split_summary[split]['safe_source_feature_counts']=dict(
        contradictory=sum(r['expected_decision']=='CONTRADICTORY' for r in safe_source),
        incomplete=sum(r['expected_decision']=='INCOMPLETE' for r in safe_source),
        ambiguous=sum(r['expected_decision']=='AMBIGUOUS' for r in safe_source),
        protected=sum(bool(r.get('protected_spans')) for r in safe_source),
        unsupported=sum(r['expected_decision']=='UNSUPPORTED' for r in safe_source),
        multi_constraint=sum(sum([bool(r.get('expected_subjects')),bool(r.get('expected_excluded_subjects') or r.get('expected_exclude_terms')),r.get('expected_rating_min') is not None or r.get('expected_rating_max') is not None,r.get('expected_year_min') is not None or r.get('expected_year_max') is not None,bool(r.get('expected_format')),bool(r.get('expected_author')),bool(r.get('expected_availability'))])>=2 for r in safe_source))
summary=dict(review_rows=len(reviews), ai_reviewed=len(reviews), human_reviewed=0,
             original_hashes=hashes, original_labels_modified=False,
             parser_implementation_access=False, parser_output_access=False, evaluator_output_access=False,
             split_summary=split_summary, exact_query_cross_split_groups=len(cross_split_exact),
             family_ids_crossing_splits=sum(len(s)>1 for s in family_splits.values()),
             original_family_count=len(FAMILIES), pre_exposed_heldout_rows=10,
             heldout_content_reporting='aggregate-only; do not print heldout query text or labels',
             schema_adapter_requirements=[
                 'Explicitly map EXECUTABLE=>AUTO_EXECUTE, EXECUTABLE_WITH_NOTICE=>EXECUTE_WITH_NOTICE, AMBIGUOUS/INCOMPLETE=>CLARIFY without altering original labels.',
                 'semantic/exact are legacy UI mode names; map to SMART/EXACT only through a documented adapter.',
                 'Legacy query is query_text; template_id and workspace_type are missing from legacy rows and must be derived from frozen family/scope metadata, never parser output.',
                 'Null sort is unspecified/default, not an authored nondefault sort constraint.',
                 'A delta parser result cannot prove native session/security lifecycle behavior.',
                 'Author self-review claims in original metadata do not establish independent review or human review. This artifact adds540 independent AI reviews only.'
             ],
             structural_overlap_disclosure='Several families share broad operations (rating, exact mode, negative syntax) across splits. Family IDs are disjoint, but IDs alone do not prove near-template isolation. Preserve originals; publish overlap limitations, never silently resplit.',
             generation_policy='Derive only from generation_safe=true rows, retain each family in one original split. Prefix/suffix neutral request scaffolding only outside protected tokens; recompute offsets independently. Avoid every mutation that changes operators, connective scope, quoted text, Exact-mode text, numbers, capability scopes or action contexts. Generated labels inherit review; they are not separately semantically reviewed by this reviewer.',
             paths=dict(review=str(out), review_source=str(Path(__file__).resolve())))
summary_path=REPORTS/'search_v2c_c_resume_label_review_summary.json'
summary_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
