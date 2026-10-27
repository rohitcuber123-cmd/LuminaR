"""C5A independent output-blind semantic-review ledger materializer.

The reviewer inspected all 600 core queries in separate bounded views. This
utility records those decisions and performs only input-integrity, capability,
span, lexical-topology and structural-diversity checks. It does not invoke a
parser, evaluator, model, policy or any native/heldout/audit artifact.
"""
import copy
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / 'reports/search_v2c_c5a_author_draft.jsonl'
CAPS = ROOT / 'reports/search_v2c_c5a_capability_matrix.json'
BRIEF = ROOT / 'reports/search_v2c_c5a_author_brief.json'
SOURCE_SHA = 'b22a77d71c97b26bbfa1e114f332a8b2af3fa5d4867244c67e27c6a7fb16125f'
REVIEWER = 'independent_output_blind_AI'
REVIEW_ID = 'C5A-independent-semantic-review-v1'

FEATURES = [
    ('rating', r'\b(?:ratings?|rated|stars?)\b|\d\+'),
    ('year', r'\b(?:publish\w*|release\w*|year|after|before|onward)\b'),
    ('author', r'\bby\b'), ('title', r'\btitled\b'),
    ('negative', r'\b(?:not|exclud\w*|without|except)\b'),
    ('include', r'\b(?:include|included|subject|category)\b'),
    ('format', r'\b(?:online|digital\w*|physical\w*|hardcover|binding)\b'),
    ('availability', r'\b(?:available|request|loan|borrow)\b'),
    ('metadata', r'\b(?:page\w*|edition|language|french|dollar|costing|difficulty|audience)\b'),
    ('preference', r'\b(?:beginner\w*|introduct\w*|advanced|research|reference|short\w*)\b'),
    ('sort', r'\b(?:sort|highest|newest|oldest)\b'),
]

AMBIGUITY = {
    1: ('rating-equality-versus-inclusive-floor', ['rating_max'], 'The number 4 and inclusive lower bound are common to exact-4 and at-least-4; whether a ceiling is required remains unresolved.'),
    2: ('rating-floor-versus-ceiling', ['rating_min', 'rating_max'], 'The note explicitly leaves the comparison direction undecided.'),
    3: ('negative-category-intersection-versus-union', ['exclude_subjects'], 'Rejecting a conjunction and rejecting either member exclude different record sets.'),
    4: ('title-boundary-versus-author-credit', ['title_text', 'author_text'], 'The user explicitly leaves the boundary between the title and author credit unresolved.'),
    5: ('joint-authors-versus-author-alternatives', ['author_text'], 'A joint-author requirement and either-author alternatives are materially different.'),
    6: ('negation-grouping', ['subjects', 'exclude_subjects'], 'The lost parentheses determine whether the second category is positive or inside the negation.'),
    7: ('positive-boolean-grouping', ['subjects'], 'The OR/AND grouping is expressly unresolved; no flat mandatory subject list is justified.'),
    8: ('unselected-title-choice', ['title_text'], 'The user expressly has not selected which one-title search is wanted; the supporting clauses do not choose it.'),
    9: ('scope-of-advisory-category-modifier', ['subjects'], 'The first subject is advisory on both stated readings; whether the second is mandatory remains unresolved.'),
    10: ('unspecified-approximate-rating-tolerance', ['rating_min', 'rating_max'], 'Four-ish supplies no exact tolerance. The reviewer does not invent numerical endpoints.'),
    11: ('nonmandatory-or-explicitly-resolved-author-mapping-note', ['expected_typed_decision', 'expected_executable', 'expected_ambiguity'], 'The mapping anecdote does not clearly require an author filter. In staff rows an explicit by clause also selects the author. The claimed blocking ambiguity is not reliable gold.'),
    12: ('format-requirement-versus-format-preference', ['formats', 'exclusive_formats', 'soft_preferences.formats'], 'The mandatory/advisory status of online access is expressly undecided.'),
    13: ('exception-scope', ['subjects', 'exclude_subjects'], 'The user expressly leaves whether the exception overrides just the exclusion or the whole subject condition unresolved.'),
    14: ('unselected-title-choice', ['title_text'], 'A smudged choice between two named titles supplies neither selected literal title.'),
    15: ('strict-versus-inclusive-rating-floor', ['rating_min_exclusive'], 'Both readings use the numeric floor 4; only inclusion of the endpoint is unresolved.'),
    16: ('canonical-category-versus-broad-text-exclusion', ['exclude_subjects', 'exclude_terms'], 'Category membership and occurrence anywhere in record text are expressly different unresolved exclusions.'),
    17: ('joint-authors-versus-author-alternatives', ['author_text'], 'The slash could express coauthorship or alternative writers; the user explicitly disclaims a selection.'),
    18: ('one-compound-title-versus-two-title-requests', ['title_text'], 'The colon is explicitly ambiguous between a full literal title and two title requests.'),
    19: ('mandatory-versus-advisory-rating-floor', ['rating_min', 'rating_min_exclusive', 'soft_preferences.rating_min'], 'A hard threshold and an aspiration cannot be assigned the same hard-filter gold.'),
    20: ('author-alternative-removal-versus-record-exclusion', ['author_text', 'exclude_terms'], 'Removing a writer from alternatives and rejecting a coauthored record have different author/exclusion semantics.'),
}

INCOMPLETE_GLOBAL = [
    'missing-rating-floor', 'missing-rating-ceiling', 'missing-exact-rating',
    'missing-lower-rating-interval-endpoint', 'missing-upper-rating-interval-endpoint',
    'missing-both-rating-interval-endpoints', 'missing-author', 'missing-title',
    'missing-positive-category', 'missing-negative-category', 'missing-broad-exclusion-text',
    'unfinished-author-name', 'unfinished-literal-title', 'missing-additional-positive-category',
    'missing-additional-negative-category', 'missing-title-and-author',
    'missing-title-and-rating-floor', 'missing-positive-and-negative-categories',
    'missing-exclusive-format-operand', 'missing-author-and-negative-category',
]
INCOMPLETE_TENANT = [
    'missing-rating-floor', 'missing-rating-ceiling', 'missing-exact-publication-year',
    'missing-lower-publication-interval-endpoint', 'missing-upper-publication-interval-endpoint',
    'missing-language', 'missing-author', 'missing-title', 'missing-positive-category',
    'missing-negative-category', 'missing-broad-exclusion-text', 'missing-exclusive-format-operand',
    'missing-availability-state', 'missing-additional-positive-category',
    'missing-additional-negative-category', 'missing-title-and-author',
    'missing-title-and-rating-floor', 'missing-positive-and-negative-categories',
    'missing-both-publication-interval-endpoints', 'missing-author-and-language',
]
UNSUPPORTED_GLOBAL = [
    'publication-floor', 'language', 'current-availability', 'physical-exclusivity',
    'both-access-requirement', 'publication-ceiling-and-language', 'on-loan-state',
    'page-count-ceiling', 'edition-number', 'purchase-price-ceiling', 'mandatory-difficulty',
    'audience-age-range', 'publisher-credit', 'translator-credit', 'digital-file-encoding',
    'digital-download-size', 'physical-large-print', 'audio-media-and-narrator',
    'shelf-location', 'isbn-identifier',
]
UNSUPPORTED_TENANT = [
    'page-count-ceiling', 'edition-number', 'purchase-price-ceiling', 'mandatory-difficulty',
    'audience-age-range', 'publisher-credit', 'translator-credit', 'narrator-credit',
    'abridgement-state', 'illustration-color', 'specific-binding', 'print-size',
    'audio-media-and-duration', 'isbn-identifier', 'reuse-license', 'digital-file-encoding',
    'digital-download-size', 'shelf-location', 'inventory-barcode', 'verified-accessibility-tagging',
]
CONTRADICTORY_GLOBAL = [
    'reversed-inclusive-rating-interval', 'open-lower-empty-rating-boundary',
    'open-upper-empty-rating-boundary', 'positive-negative-category-clash',
    'required-subject-conjunction-excluded-member', 'required-title-broad-literal-exclusion',
    'required-author-broad-literal-exclusion', 'required-title-word-exclusion',
    'required-author-surname-exclusion', 'category-clash-and-reversed-rating',
    'two-category-clashes', 'title-exclusion-and-open-lower-rating',
    'author-exclusion-and-category-clash', 'title-word-exclusion-and-category-clash',
    'title-and-author-independent-exclusions', 'two-category-clashes-and-open-upper-rating',
    'required-access-format-excluded', 'exclusive-access-format-excluded',
    'format-clash-and-category-clash', 'both-rating-endpoints-open-at-same-value',
]
CONTRADICTORY_TENANT = [
    'reversed-inclusive-rating-interval', 'open-lower-empty-rating-boundary',
    'open-upper-empty-rating-boundary', 'positive-negative-category-clash',
    'required-subject-conjunction-excluded-member', 'required-title-broad-literal-exclusion',
    'required-author-broad-literal-exclusion', 'reversed-inclusive-publication-interval',
    'open-lower-empty-publication-boundary', 'open-upper-empty-publication-boundary',
    'required-access-format-excluded', 'required-access-format-excluded',
    'both-access-versus-excluded-member', 'category-clash-and-reversed-publication',
    'two-independent-empty-numeric-intervals', 'title-and-author-independent-exclusions',
    'format-clash-and-category-clash', 'two-category-clashes',
    'title-word-exclusion-and-both-open-rating-bounds', 'format-clash-and-category-clash',
]

BASE_HARD_FIELDS = [
    'author_text', 'title_text', 'subjects', 'exclude_subjects', 'exclude_terms',
    'rating_min', 'rating_min_exclusive', 'rating_max', 'rating_max_exclusive',
    'year_min', 'year_min_exclusive', 'year_max', 'year_max_exclusive',
    'formats', 'exclusive_formats', 'excluded_formats', 'language', 'availability',
]
EXPECTED_FIELDS = [
    'expected_typed_decision', 'expected_executable', 'expected_hard_constraints',
    'expected_soft_preferences', 'expected_semantic_remainder', 'expected_ambiguity',
    'expected_incomplete_fields', 'expected_unsupported_fields', 'expected_contradiction',
    'protected_entities', 'capability_profile',
]


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(dump(value).encode('utf-8')).hexdigest()


def lexical_topology(query):
    return 'SMART:' + ','.join(name for name, pattern in FEATURES if re.search(pattern, query, re.I))


def independent_hard_summary(hard):
    pieces = []
    for k, v in hard.items():
        pieces.append(f'{k}={dump(v)}')
    return '; '.join(pieces) or 'no fully resolved hard operands'


def geometry(hard, prefix):
    lo, hi = hard.get(prefix + '_min'), hard.get(prefix + '_max')
    lex = hard.get(prefix + '_min_exclusive', 'UNRESOLVED')
    hex_ = hard.get(prefix + '_max_exclusive', 'UNRESOLVED')
    if lo is None and hi is None:
        return None
    relation = 'floor' if hi is None else 'ceiling' if lo is None else 'equal' if lo == hi else 'forward' if lo < hi else 'reversed'
    return [relation, lex if lo is not None else None, hex_ if hi is not None else None]


def field_feature(field):
    if field.startswith('rating_'):
        return 'rating'
    if field.startswith('year_'):
        return 'year'
    if field == 'author_text':
        return 'author'
    if field == 'title_text':
        return 'title'
    if field in ('exclude_subjects', 'exclude_terms', 'excluded_formats'):
        return 'negative'
    if field == 'subjects':
        return 'include'
    if field in ('formats', 'exclusive_formats', 'audio_format'):
        return 'format'
    if field == 'availability':
        return 'availability'
    if field not in ('expected_typed_decision', 'expected_executable', 'expected_ambiguity') and not field.startswith('soft_preferences.'):
        return 'metadata'
    if field.startswith('soft_preferences.'):
        return 'preference'
    return None


def semantic_structure(row, concept, unresolved):
    h = row['expected_hard_constraints']
    # Entity strings and numerical operands are deliberately absent. Subject
    # conjunction size, exclusion relation, boundary geometry, exclusivity and
    # genuinely requested extra operations remain meaningful structure.
    shape = {
        'concept': concept,
        'hard_field_presence': sorted(k for k in h if not k.endswith('_exclusive')),
        'subject_conjunction_size': len(h.get('subjects', [])),
        'negative_category_count': len(h.get('exclude_subjects', [])),
        'broad_exclusion_count': len(h.get('exclude_terms', [])),
        'rating_geometry': geometry(h, 'rating'),
        'year_geometry': geometry(h, 'year'),
        'format_requirement': 'both-access' if h.get('formats') == ['BOTH'] else 'one-access' if h.get('formats') else 'none',
        'format_exclusive': bool(h.get('exclusive_formats')),
        'format_excluded': bool(h.get('excluded_formats')),
        'preference_fields': sorted(row['expected_soft_preferences']),
        'incomplete_fields': sorted(row['expected_incomplete_fields']),
        'unsupported_fields': sorted(row['expected_unsupported_fields']),
        'unresolved_fields': sorted(unresolved),
        # Presence of a real topic clause changes semantic interpretation, but
        # topic words themselves are never independent core diversity.
        'has_topical_clause': bool(row['expected_semantic_remainder']),
    }
    fields = set(h) | set(row['expected_incomplete_fields']) | set(row['expected_unsupported_fields']) | set(unresolved)
    sem = {field_feature(k) for k in fields}
    if row['expected_soft_preferences']:
        sem.add('preference')
    # A category exclusion is an explicitly scoped category operation as well
    # as a negation, following the supplied feature ordering.
    if 'exclude_subjects' in fields:
        sem.add('include')
    sem.discard(None)
    topology = 'SMART:' + ','.join(name for name, _ in FEATURES if name in sem)
    return shape, topology


def independent_pattern_group(row, index, global_scope):
    """Conservative broad semantic families, independently of author IDs.

    Full value-free signatures separately reject duplicate core structures.
    These broader groups avoid presenting almost every conjunction as its own
    coverage pattern and have concrete requested-clause interpretations.
    """
    st, h = row['decision_stratum'], row['expected_hard_constraints']
    if st == 'CLEAR_EXECUTABLE':
        if 'author_text' in h and 'title_text' in h:
            group = 'joint-literal-title-and-author-with-additional-filters'
        elif 'title_text' in h:
            group = 'literal-title-with-additional-filters'
        elif 'author_text' in h and h.get('subjects'):
            group = 'author-and-canonical-subject-conjunction'
        elif 'author_text' in h:
            group = 'author-with-other-supported-filters'
        else:
            group = 'canonical-subject-or-metadata-conjunction'
    elif st == 'SAFE_UNCERTAIN_EXECUTABLE':
        group = ('recoverable-rating-comparison' if index <= 5 else
                 'recoverable-positive-canonical-category' if index <= 7 else
                 'recoverable-negative-canonical-category' if index <= 9 else
                 'recoverable-medium-or-exclusivity' if index <= 12 else
                 'recoverable-advisory-modifier' if index <= 16 else
                 'recoverable-broad-text-exclusion' if index == 17 else
                 'recoverable-entity-introducer' if index <= 19 else
                 'recoverable-positive-category-conjunction')
    elif st == 'AMBIGUOUS':
        group = ('numeric-comparison-reading' if index in (1, 2, 15) else
                 'negative-boolean-grouping' if index in (3, 6) else
                 'literal-entity-boundary' if index in (4, 18) else
                 'coauthors-versus-alternative-writers' if index in (5, 17) else
                 'unselected-literal-title' if index in (8, 14) else
                 'mandatory-versus-advisory-scope' if index in (9, 12, 19) else
                 'unspecified-approximate-tolerance' if index == 10 else
                 'unresolved-relevance-of-mapping-anecdote' if index == 11 else
                 'positive-boolean-grouping' if index == 7 else
                 'conditional-exception-scope' if index == 13 else
                 'category-versus-broad-text-exclusion' if index == 16 else
                 'author-alternative-removal-versus-record-rejection')
    elif st == 'INCOMPLETE':
        if global_scope:
            groups = ['scalar-rating-value', 'scalar-rating-value', 'scalar-rating-value',
                      'rating-interval-endpoints', 'rating-interval-endpoints', 'rating-interval-endpoints',
                      'author-identity', 'literal-title', 'positive-category', 'negative-category',
                      'broad-exclusion-text', 'author-identity', 'literal-title', 'positive-category',
                      'negative-category', 'both-title-and-author', 'title-and-numeric-threshold',
                      'positive-and-negative-categories', 'exclusive-access-medium', 'author-and-negative-category']
        else:
            groups = ['scalar-rating-value', 'scalar-rating-value', 'exact-publication-year',
                      'publication-interval-endpoints', 'publication-interval-endpoints', 'language',
                      'author-identity', 'literal-title', 'positive-category', 'negative-category',
                      'broad-exclusion-text', 'exclusive-access-medium', 'availability-state',
                      'positive-category', 'negative-category', 'both-title-and-author',
                      'title-and-numeric-threshold', 'positive-and-negative-categories',
                      'publication-interval-endpoints', 'author-and-language']
        group = groups[index - 1]
    elif st == 'UNSUPPORTED':
        if global_scope:
            groups = ['scope-publication-field', 'scope-language-field', 'scope-availability-field',
                      'scope-access-medium', 'scope-access-medium', 'scope-publication-and-language-fields',
                      'scope-availability-field', 'quantitative-bibliographic-metadata',
                      'edition-or-abridgement-state', 'quantitative-bibliographic-metadata',
                      'reading-level-or-audience', 'reading-level-or-audience', 'publisher-or-contributor-credit',
                      'publisher-or-contributor-credit', 'digital-asset-property', 'digital-asset-property',
                      'physical-copy-property', 'audio-media-or-credit', 'inventory-detail', 'exact-identifier']
        else:
            groups = ['quantitative-bibliographic-metadata', 'edition-or-abridgement-state',
                      'quantitative-bibliographic-metadata', 'reading-level-or-audience',
                      'reading-level-or-audience', 'publisher-or-contributor-credit',
                      'publisher-or-contributor-credit', 'publisher-or-contributor-credit',
                      'edition-or-abridgement-state', 'illustration-property', 'physical-copy-property',
                      'quantitative-bibliographic-metadata', 'audio-media-and-duration', 'exact-identifier',
                      'reuse-rights', 'digital-asset-property', 'digital-asset-property',
                      'inventory-detail', 'inventory-detail', 'verified-accessibility-property']
        group = groups[index - 1]
    elif st == 'CONTRADICTORY':
        if global_scope:
            group = ('empty-rating-interval' if index in (1, 2, 3, 20) else
                     'required-category-and-category-exclusion' if index in (4, 5, 11) else
                     'required-identity-and-broad-text-exclusion' if index in (6, 7, 8, 9) else
                     'required-medium-and-medium-exclusion' if index in (17, 18) else
                     'multiple-independent-contradictions')
        else:
            group = ('empty-rating-interval' if index in (1, 2, 3) else
                     'required-category-and-category-exclusion' if index in (4, 5, 18) else
                     'required-identity-and-broad-text-exclusion' if index in (6, 7) else
                     'empty-publication-interval' if index in (8, 9, 10) else
                     'required-medium-and-medium-exclusion' if index in (11, 12, 13) else
                     'multiple-independent-contradictions')
    return 'c5a-independent-' + st.lower() + '-' + group


def build_applicability(row, unresolved, partial):
    h = row['expected_hard_constraints']
    u = set(unresolved)
    missing = set(row['expected_incomplete_fields'])
    unsupported = set(row['expected_unsupported_fields'])
    cap = row['capability_profile']['capabilities']
    a = {}
    for field in EXPECTED_FIELDS:
        key = {'expected_typed_decision': 'typed_decision', 'expected_executable': 'executable',
               'expected_hard_constraints': 'hard_constraints', 'expected_soft_preferences': 'soft_preferences',
               'expected_semantic_remainder': 'semantic_remainder', 'expected_ambiguity': 'ambiguity',
               'expected_incomplete_fields': 'incomplete_fields', 'expected_unsupported_fields': 'unsupported_fields',
               'expected_contradiction': 'contradiction'}.get(field, field)
        if partial and field in ('expected_typed_decision', 'expected_executable', 'expected_ambiguity'):
            a[key] = {'status': 'UNRESOLVED', 'reason': 'Independent review cannot establish that the mapping anecdote imposes an unfilled mandatory author condition; not eligible as gold.'}
        else:
            a[key] = {'status': 'APPLICABLE', 'reason': 'Individually inspected against this query and frozen scope. Empty lists/objects mean no additional resolved requirement, not guessed operands.'}
    a['confidence'] = {'status': 'INAPPLICABLE', 'reason': 'No numerical confidence target is warranted or scored.'}
    for field in sorted(set(BASE_HARD_FIELDS) | unsupported | missing | (u - set(EXPECTED_FIELDS))):
        if field.startswith('soft_preferences.'):
            a[field] = {'status': 'UNRESOLVED', 'reason': 'The wording leaves this advisory versus mandatory interpretation unsettled.'}
            continue
        if field in h:
            a[field] = {
                'status': 'PARTIALLY_APPLICABLE' if field in missing or field in u else 'APPLICABLE',
                'resolved_value': h[field],
                'reason': 'The listed operand is explicit and supported. A separately identified missing/ambiguous component is not fabricated.' if field in missing or field in u else 'The scalar/list value is resolved by explicit wording and supported in this scope.',
            }
        elif field in missing:
            a[field] = {'status': 'UNRESOLVED', 'reason': 'The query explicitly leaves this mandatory operand blank or unfinished. No placeholder is gold.'}
        elif field in u:
            a[field] = {'status': 'UNRESOLVED', 'reason': 'The query does not settle this component; only separately resolved common operands may be scored.'}
        elif field in unsupported:
            a[field] = {'status': 'INAPPLICABLE', 'reason': 'A mandatory request exists, but this frozen scope offers no enforceable filter for it. Its detection in unsupported_fields remains applicable.'}
        elif ((field.startswith('year_') and not cap['year']) or (field == 'language' and not cap['language']) or (field == 'availability' and not cap['availability'])):
            a[field] = {'status': 'INAPPLICABLE', 'reason': 'This filter is absent from the frozen scope capability profile and is not asserted as enforceable.'}
        else:
            a[field] = {'status': 'APPLICABLE_ABSENCE', 'reason': 'No resolved request for this operand is made; absence, rather than an invented default, is gold.'}
    # Endpoint flags are meaningful only alongside a supplied or explicitly
    # unresolved bound. A missing number cannot be replaced by a flag-only filter.
    for prefix in ('rating', 'year'):
        for side in ('min', 'max'):
            bound = f'{prefix}_{side}'
            flag = bound + '_exclusive'
            if bound in missing and flag not in h:
                a[flag] = {'status': 'UNRESOLVED', 'reason': 'The comparison syntax may establish endpoint inclusion, but its numeric operand is missing; no flag-only enforceable filter is gold.'}
    for k, v in row['expected_soft_preferences'].items():
        a['soft_preferences.' + k] = {'status': 'APPLICABLE', 'resolved_value': v, 'reason': 'The requested ranking preference is advisory; it is not promoted to a hard filter.'}
    for i, ent in enumerate(row['protected_entities']):
        a[f'protected_entities[{i}]'] = {'status': 'APPLICABLE', 'reason': 'The exact zero-based half-open span and entity role were checked against the query. Literal contents supply no independent operations.'}
    unresolved_operands = [f for f in u if not f.startswith('expected_')]
    if unresolved_operands or missing:
        a['hard_constraints'] = {'status': 'PARTIALLY_APPLICABLE', 'reason': 'Score only resolved per-field components listed below. The whole object is not complete gold for unresolved or missing components.'}
    if row['decision_stratum'] == 'AMBIGUOUS' and int(row['case_id'][-2:]) in (9, 12, 19):
        a['soft_preferences'] = {'status': 'PARTIALLY_APPLICABLE', 'reason': 'Only an explicitly common advisory component is gold. Other advisory versus mandatory components remain unresolved.'}
        if int(row['case_id'][-2:]) == 9:
            a['soft_preferences.subjects.additional'] = {'status': 'UNRESOLVED', 'reason': 'Whether the second named canonical subject is advisory or mandatory is not decided by the query.'}
    return a


def review_core(original, caps, deny):
    r = copy.deepcopy(original)
    case = r['case_id']
    scope_i, stratum_i, index = map(int, case.split('-')[1:])
    global_scope = scope_i == 1
    st = r['decision_stratum']
    q = r['query_text']
    amendments = []
    unresolved = []
    partial = st == 'AMBIGUOUS' and index == 11
    reasons = []

    def amend(field, new, why):
        old = copy.deepcopy(r[field])
        if old != new:
            amendments.append({'field': field, 'author_value': old, 'reviewed_value': copy.deepcopy(new), 'reason': why})
            r[field] = new

    if st == 'CLEAR_EXECUTABLE':
        concept = 'explicit-supported-conjunction'
        reasons.append('Every mandatory clause has a resolved supported operand; title constraints have explicit titled wording and free about text remains semantic.')
    elif st == 'SAFE_UNCERTAIN_EXECUTABLE':
        # Each exact correction was read in the query and independently accepted;
        # this extracts the already-inspected quoted pair for the audit ledger.
        m = re.search(r"interpret '([^']+)' as '([^']+)'", r['label_confidence_or_review_notes'])
        assert m, case
        typo, correction = m.groups()
        assert typo in q, case
        role = ['inclusive-rating-floor', 'inclusive-rating-ceiling', 'strict-rating-floor',
                'exact-rating', 'two-sided-rating-interval', 'positive-category',
                'positive-category', 'negative-category', 'negative-category',
                'exclusive-online-medium', 'online-medium', 'medium-exclusivity',
                'advisory-level', 'advisory-level', 'advisory-length', 'advisory-purpose',
                'broad-exclusion', 'literal-title-introducer', 'author-introducer',
                'positive-category-conjunction'][index - 1]
        concept = 'recoverable-spelling-' + role
        reasons.append(f"Independently accept the visible correction {typo!r} to {correction!r}: its surrounding clause uniquely fixes the role, keeps supplied entity/value operands, and needs a correction notice. No confidence float is justified.")
        r['reviewed_interpretation_notice'] = {'original_fragment': typo, 'interpreted_fragment': correction, 'basis': 'Visible recoverable spelling or transposition in a semantically fixed request clause.'}
    elif st == 'AMBIGUOUS':
        concept, unresolved, reason = AMBIGUITY[index]
        unresolved = list(unresolved)
        reasons.append(reason)
        if index == 1:
            h = copy.deepcopy(r['expected_hard_constraints'])
            h.update(rating_min=4.0, rating_min_exclusive=False)
            amend('expected_hard_constraints', h, 'Both stated readings require rating >= 4. Only the upper bound differs; preserve the common resolved lower bound.')
        elif index == 9:
            first = re.search(r'include subject "([^"]+)" preferably', q).group(1)
            soft = copy.deepcopy(r['expected_soft_preferences'])
            soft['subjects'] = [first]
            amend('expected_soft_preferences', soft, 'The first canonical subject is a soft preference on both stated readings. Only the second subject\'s hard/advisory status is unsettled.')
        elif index == 10:
            amb = copy.deepcopy(r['expected_ambiguity'])
            amb[0]['interpretations'] = [
                'a broader, unspecified neighborhood around 4 stars',
                'a narrower, unspecified neighborhood around 4 stars',
            ]
            amb[0]['reason'] = 'Approximate intent is explicit, but no tolerance or endpoint is supplied. These are qualitative alternatives, not numerical gold intervals.'
            amb[0]['unresolved_parameters'] = ['rating_min', 'rating_max']
            amend('expected_ambiguity', amb, 'The author invented 3.5/4.5 and 3.9/4.1 endpoints. Remove precise ranges absent from the query.')
        elif index == 11:
            amend('expected_typed_decision', None, 'The independent reviewer cannot establish that the anecdote blocks the explicitly requested title search. Staff rows also explicitly name the requested author.')
            amend('expected_executable', None, 'No reliable binary executability gold is asserted for this internally qualified mapping anecdote.')
            amend('expected_ambiguity', None, 'The author-mapping uncertainty exists as an anecdote; its relevance as a mandatory search condition is not established.')
        elif index == 15:
            h = copy.deepcopy(r['expected_hard_constraints'])
            h['rating_min'] = 4.0
            amend('expected_hard_constraints', h, 'Both stated readings share numeric lower endpoint 4; only rating_min_exclusive remains unresolved.')
    elif st == 'INCOMPLETE':
        concept = (INCOMPLETE_GLOBAL if global_scope else INCOMPLETE_TENANT)[index - 1]
        unresolved = list(r['expected_incomplete_fields'])
        reasons.append('The query explicitly leaves mandatory operand(s) blank/unfinished: ' + ', '.join(unresolved) + '. Preserve separately supplied endpoints, canonical members and other supported clauses; invent no missing value.')
    elif st == 'UNSUPPORTED':
        concept = 'mandatory-unsupported-' + (UNSUPPORTED_GLOBAL if global_scope else UNSUPPORTED_TENANT)[index - 1]
        if not global_scope and index == 13:
            u = list(r['expected_unsupported_fields'])
            if 'audio_format' not in u:
                u.insert(0, 'audio_format')
            amend('expected_unsupported_fields', u, 'An audio running-time requirement also selects audio media. Neither audio media subtype nor duration is an enforceable capability; retain any supported physical/online access requirement separately.')
        reasons.append('The mandatory unsupported request cannot be silently converted to relevance or a preference: ' + ', '.join(r['expected_unsupported_fields']) + '. The remaining hard operands are independently supported.')
    elif st == 'CONTRADICTORY':
        concept = (CONTRADICTORY_GLOBAL if global_scope else CONTRADICTORY_TENANT)[index - 1]
        reasons.append('The listed resolved operands are individually supported and cannot all hold: ' + r['expected_contradiction']['reason'])
    else:
        raise AssertionError(st)

    cap = caps[r['scope_type']]
    assert r['workspace_type'] == cap['workspace_type'], case
    assert r['capability_profile']['capabilities'] == cap['capabilities'], case
    for field in ('subjects', 'exclude_subjects'):
        for subject in r['expected_hard_constraints'].get(field, []):
            assert subject in cap['subjects'], (case, field, subject)
    for subject in r['expected_soft_preferences'].get('subjects', []):
        assert subject in cap['subjects'], (case, subject)
    for field, value in r['expected_hard_constraints'].items():
        capability = 'year' if field.startswith('year_') else 'rating' if field.startswith('rating_') else field
        if capability in ('rating', 'year', 'language', 'availability'):
            assert cap['capabilities'][capability], (case, field)
        if field in ('formats', 'exclusive_formats', 'excluded_formats'):
            assert all(v in cap['capabilities']['formats'] for v in value), (case, field)
    for entity in r['protected_entities']:
        assert q[entity['start']:entity['end']] == entity['text'], (case, entity)
    for field, kind in (('title_text', 'TITLE'), ('author_text', 'AUTHOR')):
        if field in r['expected_hard_constraints']:
            assert any(e['kind'] == kind and e['text'] == r['expected_hard_constraints'][field] for e in r['protected_entities']), (case, field)

    masked = list(q)
    for e in r['protected_entities']:
        masked[e['start']:e['end']] = ' ' * (e['end'] - e['start'])
    raw_topology = lexical_topology(q)
    literal_safe_topology = lexical_topology(''.join(masked))
    assert raw_topology == original['operation_topology'], case
    assert original['structural_component_id'] == 'c5a-structure-' + hashlib.sha256(raw_topology.encode()).hexdigest()[:16], case
    shape, semantic_topology = semantic_structure(r, concept, unresolved)
    r['metric_applicability'] = build_applicability(r, unresolved, partial)
    r['review_status'] = 'PARTIAL' if partial else 'AI_REVIEWED'
    r['reviewer_type'] = REVIEWER
    r['parser_output_visible'] = False
    r['review_complete'] = not partial
    r['core_eligible'] = not partial
    r['reviewed_pattern_id'] = 'c5a-meaningful-' + digest(shape)[:20]
    r['independent_pattern_id'] = independent_pattern_group(r, index, global_scope)
    r['reviewed_pattern_signature'] = shape
    r['semantic_operation_topology'] = semantic_topology
    r['review_unresolved_fields'] = unresolved
    r['review_required_decision_safety_resolved'] = not partial
    r['review_unresolved_decision_safety_labels'] = ['expected_typed_decision', 'expected_executable'] if partial else []
    r['semantic_review_notes'] = reasons
    r['review_provenance'] = {
        'review_id': REVIEW_ID, 'reviewer_type': REVIEWER, 'reviewed_case_individually': True,
        'parser_output_visible': False, 'source_draft_sha256': SOURCE_SHA,
        'original_case_sha256': digest(original), 'human_review_claimed': False,
        'reads': ['search_v2c_c5a_author_draft.jsonl', 'search_v2c_c5a_capability_matrix.json', 'search_v2c_c5a_author_brief.json'],
    }
    r['label_confidence_or_review_notes'] = 'Independent output-blind AI semantic review. ' + ' '.join(reasons)
    if r['expected_semantic_remainder']:
        reasons.append('The free topical request is retained exactly as relevance text: ' + repr(r['expected_semantic_remainder']) + '; it is not a literal title or unsupported hard filter.')
    reasons.append('Individually verified hard components: ' + independent_hard_summary(r['expected_hard_constraints']) + '.')
    reasons.append('Canonical negative categories are category-only; broad exclude_terms appear only where the words explicitly reject text anywhere in a record.')
    record = {
        'case_id': case, 'scope_type': r['scope_type'], 'decision_stratum': st,
        'semantic_verdict': 'PARTIAL_UNRESOLVED_GOLD' if partial else 'ACCEPT_WITH_AMENDMENTS' if amendments else 'ACCEPT',
        'review_status': r['review_status'], 'reviewer_type': REVIEWER,
        'parser_output_visible': False, 'review_complete': r['review_complete'], 'core_eligible': r['core_eligible'],
        'query_text': q, 'source_case_sha256': digest(original), 'source_draft_sha256': SOURCE_SHA,
        'field_amendments': amendments, 'unresolved_labels': unresolved,
        'unresolved_required_decision_safety_labels': ['expected_typed_decision', 'expected_executable'] if partial else [],
        'unresolved_semantic_operand_fields': [f for f in unresolved if not f.startswith('expected_')],
        'required_decision_safety_resolved': not partial,
        'reasons': reasons, 'reviewed_pattern_id': r['reviewed_pattern_id'],
        'independent_pattern_id': r['independent_pattern_id'],
        'meaningful_pattern_signature': shape,
        'topology_review': {
            'author_lexical_topology': raw_topology, 'protected_entity_masked_lexical_topology': literal_safe_topology,
            'protected_entity_feature_inflation': raw_topology != literal_safe_topology,
            'lexical_denylist_collision': literal_safe_topology in deny,
            'actual_requested_semantic_topology': semantic_topology,
            'semantic_denylist_collision': semantic_topology in deny,
            'notes': 'Lexical bookkeeping is retained as specified in the brief. Meaningful diversity uses actual requested clauses and the value-free signature; note narration and literal entity words do not create operations.',
        },
        'metric_applicability': r['metric_applicability'], 'provenance': r['review_provenance'],
    }
    return r, record


def main():
    source = DRAFT.read_bytes()
    assert hashlib.sha256(source).hexdigest() == SOURCE_SHA
    rows = [json.loads(line) for line in source.splitlines()]
    caps = json.loads(CAPS.read_text(encoding='utf-8'))['scopes']
    brief = json.loads(BRIEF.read_text(encoding='utf-8'))
    core = [r for r in rows if r['example_class'] == 'CORE']
    assert len(core) == 600 and len(rows) == 750
    assert {r['case_id'] for r in core} == {f'C5A-{s}-{t}-{i:02d}' for s in range(1, 6) for t in range(1, 7) for i in range(1, 21)}
    assert len({r['case_id'] for r in rows}) == len(rows)
    out, records = [], []
    seen = defaultdict(dict)
    for original in rows:
        if original['example_class'] == 'DERIVATIVE':
            d = copy.deepcopy(original)
            d.update(review_status='UNREVIEWED', reviewer_type='UNREVIEWED_DERIVATIVE_NO_INDEPENDENT_REVIEW',
                     parser_output_visible=False, review_complete=False, core_eligible=False)
            d['metric_applicability'] = {
                k: {'status': 'UNREVIEWED', 'reason': 'Inherited author labels have not been independently inspected; excluded from reviewed core metrics.'}
                for k in sorted(set(original['metric_applicability']) | set(EXPECTED_FIELDS))
            }
            d['review_provenance'] = {'review_id': REVIEW_ID, 'source_draft_sha256': SOURCE_SHA,
                                      'reviewed_case_individually': False, 'parser_output_visible': False,
                                      'human_review_claimed': False, 'parent_core_id': original['parent_core_id']}
            out.append(d)
            continue
        r, record = review_core(original, caps, set(brief['development_topology_denylist']))
        cell = (r['scope_type'], r['decision_stratum'])
        sig = r['reviewed_pattern_id']
        duplicate = seen[cell].get(sig)
        if r['core_eligible'] and duplicate:
            r.update(review_status='REJECTED_CORE_DIVERSITY', review_complete=False, core_eligible=False)
            reason = 'This value-free semantic structure duplicates ' + duplicate + ' in the same cell; entity/value substitutions do not supply independent core coverage.'
            r['semantic_review_notes'].append(reason)
            r['metric_applicability']['independent_core_coverage'] = {'status': 'INAPPLICABLE', 'reason': reason}
            record.update(semantic_verdict='REJECTED_CORE_DIVERSITY', review_status=r['review_status'], review_complete=False, core_eligible=False)
            record['reasons'].append(reason)
            record['duplicate_of'] = duplicate
        elif r['core_eligible']:
            seen[cell][sig] = r['case_id']
        # Structural isolation applies independently of semantic correctness.
        if r['core_eligible'] and record['topology_review']['semantic_denylist_collision']:
            r.update(review_status='REJECTED_CORE_TOPOLOGY', review_complete=False, core_eligible=False)
            reason = 'The actual requested operation topology is exposed in the supplied DEVELOPMENT denylist; lexical narration cannot manufacture an isolated core family.'
            r['semantic_review_notes'].append(reason)
            r['metric_applicability']['independent_core_coverage'] = {'status': 'INAPPLICABLE', 'reason': reason}
            record.update(semantic_verdict='REJECTED_CORE_TOPOLOGY', review_status=r['review_status'], review_complete=False, core_eligible=False)
            record['reasons'].append(reason)
        if 'independent_core_coverage' not in r['metric_applicability']:
            r['metric_applicability']['independent_core_coverage'] = {
                'status': 'APPLICABLE' if r['core_eligible'] else 'UNRESOLVED',
                'reason': 'Individually reviewed core with distinct value-free semantic structure in its cell.' if r['core_eligible'] else 'Partial semantic review is excluded from every core minimum.',
            }
        record['metric_applicability'] = r['metric_applicability']
        out.append(r)
        records.append(record)
    by_cell = []
    for scope in brief['scopes']:
        for stratum in brief['strata']:
            group = [r for r in out if r['example_class'] == 'CORE' and r['scope_type'] == scope and r['decision_stratum'] == stratum]
            accepted = [r for r in group if r['core_eligible']]
            patterns = sorted({r['independent_pattern_id'] for r in accepted})
            by_cell.append({
                'scope_type': scope, 'decision_stratum': stratum, 'authored_core': len(group),
                'individually_inspected_core': len(group), 'accepted_independently_reviewed_core': len(accepted),
                'meaningful_pattern_count': len(patterns), 'meaningful_pattern_ids': patterns,
                'distinct_value_free_structures': len({r['reviewed_pattern_id'] for r in accepted}),
                'pattern_group_members': {p: [r['case_id'] for r in accepted if r['independent_pattern_id'] == p] for p in patterns},
                'accepted_case_ids': [r['case_id'] for r in accepted],
                'excluded_case_ids': [r['case_id'] for r in group if not r['core_eligible']],
                'minimum_15_met_before_sealed_isolation': len(accepted) >= 15,
                'minimum_4_patterns_met': len(patterns) >= 4,
            })
    minimums_met = all(c['minimum_15_met_before_sealed_isolation'] and c['minimum_4_patterns_met'] for c in by_cell)
    status = 'PARTIAL' if any(not r['review_complete'] for r in out if r['example_class'] == 'CORE') or not minimums_met else 'COMPLETE'
    report = {
        'review_id': REVIEW_ID, 'status': status, 'reviewer_type': REVIEWER,
        'parser_output_visible': False, 'human_review_claimed': False,
        'source_draft_sha256': SOURCE_SHA, 'source_draft_preserved': True,
        'allowed_input_files': [str(DRAFT), str(CAPS), str(BRIEF)],
        'independence': {'parser_calls': 0, 'evaluator_calls': 0, 'model_calls': 0, 'policy_calls': 0,
                         'production_source_reads': 0, 'heldout_reads': 0, 'sealed_audit_reads': 0,
                         'old_report_reads': 0, 'native_output_reads': 0},
        'review_method': 'An independent AI context read every core query with its normative labels, then separately checked all capabilities, canonical subjects, required entity spans, lexical topology and value-free meaningful patterns. The utility materializes those semantic decisions and deterministic integrity checks; no parser prediction was used as evidence.',
        'rubric': ['Typed decision and executability follow actual requested clauses.',
                   'Only explicit supported operands enter hard constraints; unresolved/missing/unsupported operands have field masks.',
                   'Canonical negative categories do not silently create broad text exclusions.',
                   'Strict title constraints require titled/called/named wording; topical text remains semantic.',
                   'Safe-uncertain rows require a real visible recoverable interpretation and notice; no numerical confidence targets.',
                   'Every contradiction uses individually supported operands.',
                   'Entity strings, numerical values, quoted content and inert narration do not create meaningful core diversity.',
                   'Derivatives remain unreviewed and never count toward core coverage.'],
        'diversity_rationale': 'independent_pattern_id uses conservative broad requested-clause families (for example literal-title, author-plus-subject, negative Boolean grouping, missing interval endpoints, unsupported inventory detail, or required-medium-versus-exclusion). The more detailed value-free signatures separately reject within-cell substitution duplicates. Author pattern IDs, entity strings, numerical values, literal quoted content and mere wording changes do not establish independent coverage.',
        'summary': {
            'authored_core': 600, 'core_individually_inspected': len(records),
            'accepted_reviewed_core': sum(r['core_eligible'] for r in out),
            'partial_core': sum(r['review_status'] == 'PARTIAL' for r in out),
            'rejected_core': sum(r['review_status'].startswith('REJECTED') for r in out),
            'unreviewed_derivatives': sum(r['example_class'] == 'DERIVATIVE' for r in out),
            'core_with_normative_amendments': sum(bool(r['field_amendments']) for r in records),
            'all_30_cells_meet_15_and_4_before_sealed_isolation': minimums_met,
            'minimum_accepted_core_per_cell': min(c['accepted_independently_reviewed_core'] for c in by_cell),
            'minimum_meaningful_patterns_per_cell': min(c['meaningful_pattern_count'] for c in by_cell),
            'quoted_entity_topology_inflation_count': sum(r['topology_review']['protected_entity_feature_inflation'] for r in records),
            'semantic_denylist_collision_count': sum(r['topology_review']['semantic_denylist_collision'] for r in records),
        },
        'limitations': ['Five author/title mapping-note cases retain unresolved gold and are not core eligible.',
                        'Counts precede separate sealed/native checks. The reviewer neither reads those outputs nor claims post-isolation success.',
                        'This is independent AI review, not human review.'],
        'cells': by_cell, 'per_case_reviews': records,
        'derivative_disposition': {'status': 'UNREVIEWED', 'count': 150, 'independently_reviewed': False, 'core_count': 0},
    }
    reviewed_path = ROOT / 'reports/search_v2c_c5a_reviewed_draft.jsonl'
    reviewed_path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in out), encoding='utf-8')
    report['reviewed_draft_sha256'] = hashlib.sha256(reviewed_path.read_bytes()).hexdigest()
    review_path = ROOT / 'reports/search_v2c_c5a_core_review.json'
    review_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert hashlib.sha256(DRAFT.read_bytes()).hexdigest() == SOURCE_SHA
    print(json.dumps({'status': status, **report['summary'], 'reviewed_draft_sha256': report['reviewed_draft_sha256']}, indent=2))
    print('EXCLUDED', json.dumps([(r['case_id'], r['semantic_verdict']) for r in records if not r['core_eligible']]))


if __name__ == '__main__':
    main()
