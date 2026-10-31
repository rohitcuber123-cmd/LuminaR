"""Independent packet-only normative annotations, authored from query meanings.

This is annotation transcription; it does not import or invoke production code,
predictions, an evaluator, or other corpus artifacts.
"""
import collections
import hashlib
import json
import pathlib
import re

ROOT = pathlib.Path(r'D:\SDC\LibraryLLM')
SOURCE = ROOT / 'reports/search_comp3_final_blind_reviewer_packet.json'
OUT = ROOT / 'reports/search_comp3_independent_review.json'
raw = SOURCE.read_bytes()
packet = json.loads(raw)
FIELDS = packet['schema']['scalar_fields']
LISTS = set(packet['native_schema']['list_fields'])
BOOLS = {f for f in FIELDS if f.endswith('_exclusive')}


def distance(a, b):
    a, b = a.casefold(), b.casefold()
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j-1] + (x != y)))
        prev = cur
    return prev[-1]


rows = []
repair_evidence = []
for case in packet['cases']:
    q = case['query_text']
    low = q.casefold()
    row = dict(case)
    hard = {f: [] if f in LISTS else False if f in BOOLS else None for f in FIELDS}
    masks = {f: {'status': 'APPLICABLE_ABSENCE', 'reason': 'No mandatory predicate in this native field is asserted.'} for f in FIELDS}
    notes = []
    unadapted = []
    soft = []
    notices = []
    causes = []

    def put(field, value, reason):
        hard[field] = value
        masks[field] = {'status': 'APPLICABLE', 'reason': reason}

    def unknown(field, reason, common=None):
        hard.pop(field, None)
        masks[field] = {'status': 'UNRESOLVED', 'reason': reason}
        if common is not None:
            hard[field] = common

    def assertion(kind, source, **kw):
        unadapted.append({'kind': kind, 'source_text': source, **kw})

    # Literal owned operands are contains operands under the supplied contract.
    author = re.search(r'\bby "([^"]+)"', q, re.I)
    negative_author = 'exclude books by' in low
    if author and not negative_author:
        put('author_text', author.group(1), 'Explicit positive by-field literal, without bibliographic identity inference.')
    title = re.search(r'\btitled "([^"]+)"', q, re.I)
    if title:
        put('title_text', title.group(1), 'Explicit titled-field literal; native contains searches title OR authors.')

    # Categories use only the scoped vocabulary supplied in the packet.
    pos_subject = re.search(r'\b(?:Subject|Category) (?:"([^"]+)"|([A-Za-z]+))', q, re.I)
    if pos_subject:
        literal = pos_subject.group(1) or pos_subject.group(2)
        vocab = packet['scopes'][case['scope_type']]['canonical_subjects']
        if literal in vocab:
            put('subjects', [literal], 'Explicit required scoped canonical category.')
        else:
            ranked = sorted((distance(literal, v), v) for v in vocab)
            assert ranked[0][0] < ranked[1][0], (case['case_id'], ranked)
            fixed = ranked[0][1]
            put('subjects', [fixed], 'Unique close canonical spelling repair within the supplied scope vocabulary.')
            notices.append({'field': 'subjects', 'source': literal, 'canonical': fixed})
            repair_evidence.append({'case_id': case['case_id'], 'source': literal, 'canonical': fixed, 'scope_vocabulary': vocab, 'nearest_edit_distance': ranked[0][0], 'next_nearest_edit_distance': ranked[1][0]})
    neg_subject = re.search(r'exclude category (?:"([^"]+)"|([A-Za-z]+))', q, re.I)
    if neg_subject:
        literal = neg_subject.group(1) or neg_subject.group(2)
        vocab = packet['scopes'][case['scope_type']]['canonical_subjects']
        if literal in vocab:
            fixed = literal
        else:
            ranked = sorted((distance(literal, v), v) for v in vocab)
            assert ranked[0][0] < ranked[1][0]
            fixed = ranked[0][1]
            notices.append({'field': 'exclude_subjects', 'source': literal, 'canonical': fixed})
            repair_evidence.append({'case_id': case['case_id'], 'source': literal, 'canonical': fixed, 'scope_vocabulary': vocab, 'nearest_edit_distance': ranked[0][0], 'next_nearest_edit_distance': ranked[1][0]})
        put('exclude_subjects', [fixed], 'Explicit category exclusion, separately from searchable-text exclusion.' + (' Unique scope-vocabulary typo correction is required.' if fixed != literal else ''))

    term = re.search(r'exclude (?:the )?(?:whole-word searchable text|searchable word) "([^"]+)"', q, re.I)
    if term:
        put('exclude_terms', [term.group(1)], 'Explicit whole-word exclusion over combined title, authors, subjects and description.')
    for field, phrase in [('rating_min', 'at least'), ('rating_max', 'at most')]:
        patterns = [rf'(?:rated|rating) {phrase} (\d+(?:\.\d+)?)', rf'(?<!\w){phrase} (\d+(?:\.\d+)?) stars']
        m = next((m for p in patterns if (m := re.search(p, q, re.I))), None)
        if field == 'rating_max' and not m:
            m = re.search(r'and at most (\d+(?:\.\d+)?)', q, re.I)
        if m:
            put(field, float(m.group(1)), 'Explicit inclusive rating bound.')
            put(field + '_exclusive', False, 'The resolved at-least/at-most comparator is inclusive.')

    year = re.search(r'publication year (\d{4}) onward is (mandatory|optional)', q, re.I)
    if year:
        if year.group(2).lower() == 'mandatory':
            put('year_min', int(year.group(1)), 'Mandatory publication-year onward bound.')
            put('year_min_exclusive', False, 'Onward includes the stated year.')
        else:
            soft.append({'kind': 'publication_year', 'operator': '>=', 'value': int(year.group(1)), 'strength': 'OPTIONAL'})

    # Optional requests remain advice even where the scope lacks that capability.
    for lang, strength in re.findall(r'(English|French) language is (optional|mandatory)', q):
        if strength == 'mandatory':
            put('language', lang, 'Explicit mandatory language.')
        else:
            soft.append({'kind': 'language', 'value': lang, 'strength': 'OPTIONAL'})
    if 'must be available now' in low:
        put('availability', 'AVAILABLE_NOW', 'Explicit mandatory current availability.')
    if 'available now is an optional wish' in low:
        soft.append({'kind': 'availability', 'value': 'AVAILABLE_NOW', 'strength': 'OPTIONAL'})
    for treatment in re.findall(r'(introductory|Research|research|short) treatments are preferred', q):
        soft.append({'kind': 'treatment', 'value': treatment.casefold(), 'strength': 'PREFERRED'})

    # Every online mention in these inspected cases is a positive requirement;
    # the one negative mention is accompanied by an explicit positive only.
    if re.search(r'\bonline\b', q, re.I):
        put('formats', ['ONLINE'], 'Explicit required online format/access.')
    if 'online only' in low:
        put('exclusive_formats', ['ONLINE'], 'Only online is required, excluding other access-format choices.')
    if 'exclude the online format' in low:
        put('excluded_formats', ['ONLINE'], 'Explicit mandatory exclusion of the online format.')

    sort = 'RELEVANCE'
    masks['sort'] = {'status': 'APPLICABLE', 'reason': 'Native RELEVANCE default; no mandatory explicit sort specified.'}
    if 'sort title ascending' in low:
        sort = 'TITLE'
        masks['sort'] = {'status': 'APPLICABLE', 'reason': 'Explicit title-ascending ordering.'}
    if 'sort highest rating first' in low:
        sort = 'RATING'
        masks['sort'] = {'status': 'APPLICABLE', 'reason': 'Explicit highest-rating-first ordering.'}
    remainder = None
    topic = re.search(r'\babout ([^.]+)\.', q, re.I)
    if topic:
        remainder = topic.group(1)
    masks['semantic_remainder'] = {'status': 'APPLICABLE' if remainder is not None else 'NOT_APPLICABLE', 'reason': 'Definite literal topic explicitly asserted after about.' if remainder is not None else 'No definite residual literal topic; optional advice and unresolved/unsupported operands are represented separately.'}
    masks['soft_preferences'] = {'status': 'APPLICABLE' if soft else 'APPLICABLE_ABSENCE', 'reason': 'Structured advisory requests, not hard predicates; evaluate semantic content rather than string identity.' if soft else 'No advisory preference asserted.'}

    # Missing or undecided mandatory values are retained, never silently dropped.
    if 'intended direction remains undecided' in low:
        causes.append('AMBIGUOUS')
        for f in ['rating_min', 'rating_max', 'rating_min_exclusive', 'rating_max_exclusive']:
            unknown(f, 'Boundary 4 is known but assignment to inclusive minimum versus maximum is explicitly undecided.')
        assertion('UNRESOLVED_BOUND_DIRECTION', 'rating boundary 4 is mandatory, but its intended direction remains undecided: at least or at most', boundary=4, alternatives=[{'operator': '>=', 'value': 4}, {'operator': '<=', 'value': 4}])
        notes.append('Mandatory rating direction is explicitly undecided; neither direction may be chosen.')
    if 'exactly one of' in low:
        causes.append('AMBIGUOUS')
        alternatives = re.search(r'exactly one of (\w+) or (\w+)', q).groups()
        unknown('subjects', 'Fiction is independently required; the additional mandatory category is undecided. This is a known common subset, not the complete list.', ['Fiction'])
        assertion('UNRESOLVED_CATEGORY_CHOICE', re.search(r'Subject Fiction[^;]+', q).group(0), common_required=['Fiction'], alternatives=list(alternatives), required_count=1)
        notes.append('Retain Fiction as a common required subset; do not select either additional category.')
    if 'their assignment is undecided' in low:
        causes.append('AMBIGUOUS')
        for f in ['author_text', 'title_text']:
            unknown(f, 'Two literal strings are known, but their required by/titled association is explicitly undecided.')
        assertion('UNRESOLVED_FIELD_ASSOCIATION', q.split('. Sort')[0], literals=re.findall(r'"([^"]+)"', q), fields=['author_text', 'title_text'])
        notes.append('Known strings cannot be assigned to the required author/title fields without resolving the stated association.')
    if 'domain undecided' in low:
        causes.append('AMBIGUOUS')
        for f in ['exclude_subjects', 'exclude_terms']:
            unknown(f, 'Fiction must be excluded, but canonical category versus whole-word text domain is explicitly undecided.')
        assertion('UNRESOLVED_EXCLUSION_DOMAIN', re.search(r'exclude "Fiction"[^;]+', q).group(0), value='Fiction', alternatives=['CANONICAL_CATEGORY', 'WHOLE_WORD_SEARCHABLE_TEXT'])
        notes.append('Do not pick the category or searchable-text negative domain.')
    if 'one required title still undecided' in low:
        causes.append('AMBIGUOUS')
        unknown('title_text', 'Exactly one of two quoted title literals must be selected; required title remains undecided.')
        assertion('UNRESOLVED_TITLE_CHOICE', re.search(r'titled either [^;]+', q).group(0), alternatives=re.findall(r'"([^"]+)"', q))
        notes.append('One mandatory title literal has not been selected; this is not an asserted executable OR.')
    if '[required author value left blank]' in q:
        causes.append('INCOMPLETE')
        unknown('author_text', 'Required author value explicitly left blank.')
        assertion('MISSING_AUTHOR', 'by [required author value left blank]')
        notes.append('The required author operand is missing, not an unknown bibliographic identity.')
    if '[required exclusion value left blank]' in q:
        causes.append('INCOMPLETE')
        unknown('exclude_terms', 'Whole-word negative domain is known, but its required value is blank.')
        assertion('MISSING_SEARCHABLE_TEXT_EXCLUSION', 'exclude whole-word searchable text [required exclusion value left blank]')
        notes.append('Required whole-word negative operand is blank.')
    if '[required value unfilled]' in q:
        causes.append('INCOMPLETE')
        unknown('subjects', 'Required category value is explicitly unfilled.')
        assertion('MISSING_CATEGORY', 'Category [required value unfilled]')
        notes.append('Required category value is missing.')
    if '[mandatory ordering key omitted]' in q:
        causes.append('INCOMPLETE')
        sort = None
        masks['sort'] = {'status': 'UNRESOLVED', 'reason': 'A mandatory ordering key is explicitly omitted; default ordering cannot replace it.'}
        assertion('MISSING_SORT', 'sort [mandatory ordering key omitted]')
        notes.append('Mandatory missing ordering prevents execution despite resolved filters.')
    if '[required number omitted]' in q:
        causes.append('INCOMPLETE')
        unknown('rating_min', 'Required numeric minimum omitted.')
        put('rating_min_exclusive', False, 'At least resolves inclusive strictness even though its numeric operand is missing.')
        assertion('MISSING_RATING_MIN', 'rating at least [required number omitted]', operator='>=')
        notes.append('The minimum comparator is inclusive, but its required number is missing.')

    # Unsupported mandatory operations must block; supported intersections remain.
    if 'require at least' in low and 'pages' in low:
        causes.append('UNSUPPORTED')
        pages = int(re.search(r'require at least (\d+) pages', q).group(1))
        assertion('UNSUPPORTED_PAGE_COUNT', f'require at least {pages} pages', operator='>=', value=pages, field='page_count')
        notes.append('Mandatory page-count metadata has no supported native field.')
    if negative_author:
        causes.append('UNSUPPORTED')
        assertion('UNSUPPORTED_AUTHOR_ONLY_NEGATION', re.search(r'exclude books by [^.]+', q).group(0), value=author.group(1), domain='AUTHOR_ONLY')
        notes.append('Author-only negative filtering is unsupported; whole-word combined searchable-text negation would change its meaning.')
    if 'invented facet cinder_phase' in low:
        causes.append('UNSUPPORTED')
        assertion('UNSUPPORTED_NEGATIVE_FACET', 'without the invented facet cinder_phase set to blue, mandatory', field='cinder_phase', operator='NOT_EQUALS', value='blue')
        notes.append('The mandatory negative invented facet is not enforceable; do not discard its negation.')
    if 'exclude authors with fewer than three' in low:
        causes.append('UNSUPPORTED')
        assertion('UNSUPPORTED_AUTHOR_AGGREGATE', 'exclude authors with fewer than three matching catalog items', operator='AUTHOR_MATCH_COUNT_AT_LEAST', value=3)
        notes.append('Excluding authors by matching-item count requires an unsupported aggregate relation.')
    if 'same page of searchable content' in low:
        causes.append('UNSUPPORTED')
        assertion('UNSUPPORTED_SAME_PAGE_RELATION', 'require these author and title strings to occur together on the same page of searchable content', operands=[hard['author_text'], hard['title_text']])
        notes.append('Author/title contains operands do not establish mandatory same-page occurrence; that relation is unsupported.')

    # Resolve actual logical incompatibility independently of result existence.
    if hard.get('rating_min') is not None and hard.get('rating_max') is not None and hard['rating_min'] > hard['rating_max']:
        causes.append('CONTRADICTORY')
        notes.append('Minimum rating 4.8 exceeds maximum rating 2, an empty resolved interval.')
    if set(hard.get('subjects', [])) & set(hard.get('exclude_subjects', [])):
        causes.append('CONTRADICTORY')
        notes.append('The same canonical Fiction category is both mandatory and excluded.')
    if set(hard.get('exclusive_formats', [])) & set(hard.get('excluded_formats', [])):
        causes.append('CONTRADICTORY')
        notes.append('Required online-only format is simultaneously excluded.')
    for excluded in hard.get('exclude_terms', []):
        for field in ['author_text', 'title_text']:
            literal = hard.get(field)
            if literal:
                # Interior word boundaries are invariant under any containing
                # string, unlike a term touching an operand's outside edge.
                m = re.search(r'(?<!\w)' + re.escape(excluded.casefold()) + r'(?!\w)', literal.casefold())
                if m and m.start() > 0 and m.end() < len(literal):
                    causes.append('CONTRADICTORY')
                    notes.append(f'Positive {field} contains literal {literal!r}, whose interior whole word {excluded!r} is necessarily present in the combined searchable fields; its mandatory exclusion is incompatible. Native title OR authors does not remove this conflict.')

    priority = ['CONTRADICTORY', 'INCOMPLETE', 'AMBIGUOUS', 'UNSUPPORTED']
    decision = next((d for d in priority if d in causes), 'EXECUTABLE_WITH_NOTICE' if notices else 'EXECUTABLE')
    if notices:
        notes.append('Safe scoped category spelling repairs: ' + '; '.join(f"{n['source']} -> {n['canonical']} ({n['field']})" for n in notices) + '. Each repaired spelling is uniquely nearest in the supplied scope vocabulary, with clear category context.')
    if not notes:
        notes.append('All mandatory operands are definite native predicates and form a supported intersection; quoted author/title operands are literals, not identity claims.')
    if soft:
        notes.append('Advisory conditions remain structured preferences and do not add mandatory filters, including unsupported global metadata wishes.')
    if remainder:
        notes.append(f'The asserted literal topic {remainder!r} remains semantic text.')
    row.update(expected_typed_decision=decision, expected_executable=decision in ['EXECUTABLE', 'EXECUTABLE_WITH_NOTICE'], expected_hard_constraints=hard, metric_applicability=masks, expected_semantic_remainder=remainder, expected_soft_preferences=soft, semantic_justification=' '.join(notes), unadapted_mandatory_assertions=unadapted)
    if masks['sort']['status'] != 'UNRESOLVED':
        row['expected_sort'] = sort
    assert len(masks) == 22
    for f in FIELDS:
        assert f in hard or masks[f]['status'] == 'UNRESOLVED', (case['case_id'], f)
    for f in FIELDS:
        if masks[f]['status'] == 'APPLICABLE_ABSENCE':
            assert hard[f] == ([] if f in LISTS else False if f in BOOLS else None)
    rows.append(row)

provenance = {
    'review_kind': 'INDEPENDENT_AI_NORMATIVE_QUERY_CONTEXT_REVIEW',
    'human_review_count': 0,
    'human0': True,
    'actual_model_identity': 'NOT_EXPOSED',
    'read_source': 'reports/search_comp3_final_blind_reviewer_packet.json',
    'packet_sha256': hashlib.sha256(raw).hexdigest(),
    'source_query_artifact_sha256_as_attested_in_packet': packet['source_query_artifact_sha256'],
    'no_prediction_access': True,
    'no_candidate_access': True,
    'no_author_labels_access': True,
    'no_prior_examples_access': True,
    'no_target_rate_access': True,
    'no_sealed_content_access': True,
    'no_network_or_database_access': True,
    'no_production_parser_or_evaluator_calls': True,
    'only_inputs': ['The packet query records, authoritative scoped vocabularies, normative rules and native schema. Parent clarified combined searchable-text exclusion rejects matches in any listed field and confirmed the native format-list serialization convention; clarifications supply no candidate or outcome data.'],
    'annotation_method': 'Read all 150 actual query/context records. Independently decide literal meanings, mandatory/optional force, ambiguity versus missing values, unsupported operations and logical conflicts. Script transcribes these decisions from query content without ID-based expected labels or balance enforcement.',
    'canonical_repair_evidence': repair_evidence,
    'mask_fields': FIELDS + ['sort', 'semantic_remainder', 'soft_preferences'],
    'mask_convention': 'Known absence explicit []/null/false; unknown hard scalar omitted, with UNRESOLVED. An independently known partial list may remain with an UNRESOLVED mask. Inclusive comparator flags false are APPLICABLE, including a missing numeric operand when comparator is resolved. Mandatory missing sort is omitted rather than defaulted.',
    'native_title_semantics': 'Literal title_text contains title OR authors; no bibliographic identity or title-only guarantee.',
    'searchable_text_semantics': 'Whole-word normalization over combined title, authors, subjects and description. An interior excluded word of a positive contains literal is necessarily present, irrespective of bibliographic identity.',
    'representation_notes': ['Plain online mapped to formats=[ONLINE]; online only records its entailed positive inclusion and exclusive_formats=[ONLINE].', 'Language literals preserve query spelling English. Optional requests are structured semantic objects, not an exact-string oracle.', 'NOT_APPLICABLE semantic_remainder means no definite asserted residual literal topic, not a missing mandatory field.'],
    'decision_counts': dict(collections.Counter(r['expected_typed_decision'] for r in rows)),
    'row_count': len(rows),
    'explicit_masks_per_row': 22,
}
uncertainties = []
assert len(rows) == 150
OUT.write_text(json.dumps({'rows': rows, 'provenance': provenance, 'uncertainties': uncertainties}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(json.dumps({'rows': len(rows), 'packet_sha256': provenance['packet_sha256'], 'decision_counts': provenance['decision_counts'], 'uncertainties': uncertainties}, indent=2))
