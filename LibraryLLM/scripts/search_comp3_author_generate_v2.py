"""Independent AI author, version 2, replacing a sealed-auditor topology collision.

Reads the blind brief, exact pure C2 source, and author's own v1 artifacts for
unchanged-row verification. No candidate, sealed examples, predictions, parser
calls, network, or databases. Original v1 artifacts are never modified.
"""
import collections
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
BRIEF = ROOT / 'reports/search_comp3_blind_author_brief.json'
brief_bytes = BRIEF.read_bytes()
brief = json.loads(brief_bytes)
brief['output'] = 'reports/search_comp3_authored_v2.jsonl'
brief['provenance_output'] = 'reports/search_comp3_author_provenance_v2.json'
SOURCE = ROOT / brief['source_structure_function']
source_bytes = SOURCE.read_bytes()
namespace = {'re': re, 'unicodedata': unicodedata}
exec(compile(source_bytes.decode('utf-8-sig'), str(SOURCE), 'exec'), namespace)
structure = namespace['structure']

LISTS = {'subjects', 'exclude_subjects', 'exclude_terms', 'formats', 'exclusive_formats', 'excluded_formats'}
BOOLS = {'rating_min_exclusive', 'rating_max_exclusive', 'year_min_exclusive', 'year_max_exclusive'}
FIELDS = brief['schema']['scalar_fields']
SCOPES = list(brief['scopes'])


def preference(field, value, relation='PREFER'):
    return {'field': field, 'relation': relation, 'value': value, 'mandatory': False}


def build(scope, number, label, topology, query, values=None, unknown=None,
          partial=None, sort='RELEVANCE', topic=None, soft=None, assertions=None,
          explanation='', notices=None):
    values = dict(values or {})
    unknown = unknown or {}
    partial = partial or {}
    for bound in ['rating_min', 'rating_max', 'year_min', 'year_max']:
        if bound in values or bound in unknown:
            values.setdefault(bound + '_exclusive', False)
    hard = {}
    masks = {}
    for field in FIELDS:
        if field in unknown:
            masks[field] = {'status': 'UNRESOLVED', 'reason': unknown[field]}
        elif field in partial:
            hard[field] = partial[field]['resolved']
            masks[field] = {'status': 'PARTIALLY_APPLICABLE', 'reason': partial[field]['reason']}
        elif field in values:
            hard[field] = values[field]
            masks[field] = {'status': 'APPLICABLE', 'reason': 'Explicit resolved mandatory operand in this query.'}
        else:
            hard[field] = [] if field in LISTS else False if field in BOOLS else None
            masks[field] = {'status': 'APPLICABLE_ABSENCE', 'reason': 'No mandatory operand for this native field is asserted.'}
    masks['sort'] = {'status': 'UNRESOLVED', 'reason': 'Mandatory ordering was requested but its key was omitted.'} if sort is None else {
        'status': 'APPLICABLE' if sort != 'RELEVANCE' else 'APPLICABLE_ABSENCE',
        'reason': 'Explicit requested native ordering.' if sort != 'RELEVANCE' else 'No ordering requested; native default is RELEVANCE.'}
    masks['semantic_remainder'] = {'status': 'APPLICABLE', 'reason': 'A definite required literal topic is asserted independently of facets.'} if topic else {
        'status': 'N/A', 'reason': 'No independently asserted definite literal semantic topic.'}
    masks['soft_preferences'] = {'status': 'APPLICABLE' if soft else 'APPLICABLE_ABSENCE', 'reason': 'Advisory wishes are recorded separately from mandatory operands.' if soft else 'No advisory preference asserted.'}
    row = {
        'case_id': f'COMP3-F{number:02d}-{scope}',
        'query_text': query,
        'scope_type': scope,
        'workspace_type': brief['scopes'][scope]['workspace_type'],
        'search_mode': 'SMART',
        'decision_stratum': label,
        'family_id': f'COMP3-F{number:02d}',
        'structural_component_id': topology,
        'shared_semantic_pattern_id': f'COMP3-INDEPENDENT-{number:02d}',
        'expected_typed_decision': {'CLEAR_EXECUTABLE': 'EXECUTABLE', 'SAFE_UNCERTAIN_EXECUTABLE': 'EXECUTABLE_WITH_NOTICE'}.get(label, label),
        'expected_executable': label in {'CLEAR_EXECUTABLE', 'SAFE_UNCERTAIN_EXECUTABLE'},
        'expected_hard_constraints': hard,
        'metric_applicability': masks,
        'expected_semantic_remainder': topic,
        'expected_soft_preferences': soft or [],
        'unadapted_mandatory_assertions': [
            {'kind': 'resolved_native_operand', 'field': field, 'value': value, 'mandatory': True}
            for field, value in values.items()
        ] + [
            {'kind': 'partially_resolved_native_operand', 'field': field, 'resolved_common_values': detail['resolved'], 'mandatory': True, 'unresolved_reason': detail['reason']}
            for field, detail in partial.items()
        ] + ([{'kind': 'mandatory_order', 'value': sort, 'mandatory': True}] if sort not in {None, 'RELEVANCE'} else [])
          + ([{'kind': 'required_semantic_topic', 'literal': topic, 'mandatory': True}] if topic else [])
          + (assertions or []),
        'expected_notices': notices or [],
        'semantic_justification': explanation,
    }
    if sort is not None:
        row['expected_sort'] = sort
    assert structure(row) == topology, (row['case_id'], structure(row), topology, query)
    assert topology in brief['allowed_fresh_topologies'], (row['case_id'], topology)
    assert len(query) <= 500, (row['case_id'], len(query))
    return row


rows = []
for scope_index, scope in enumerate(SCOPES):
    glob = scope == 'GLOBAL'
    private = scope.startswith('PRIVATE')
    author = ['Mira Cedar Sol', 'Nila Rowan Bose', 'Omar Juniper Vale', 'Ira Hazel Wren', 'Sana Elm Kale'][scope_index]
    other_author = ['Tariq Moss Reed', 'Kavi Fern Lake', 'Lea Pine Ash', 'Ravi Birch Hill', 'Asha Oak Dawn'][scope_index]
    title = ['The Lantern Archive', 'The Copper Almanac', 'The Indigo Orchard', 'The Silver Estuary', 'The Amber Observatory'][scope_index]
    missing_title = ['Missing Bells', 'Empty Atlas', 'Null Harbor', 'Unknown Garden', 'Blank Constellation'][scope_index]
    alt_subjects = ['Mystery', 'Wizards'] if private or glob else ['History', 'Physics']
    scope_subject = 'Wizards' if private else 'Astronomy' if glob else 'Community archives'
    scope_typo = 'Wizadrs' if private else 'Astronmy' if glob else 'Community archvies'
    exclusion_subject = 'Mystery' if private or glob else 'History'
    exclusion_typo = 'Mystrey' if private or glob else 'Histroy'
    topics = ['urban wetlands', 'oral storytelling', 'coastal resilience', 'seed dispersal', 'orbital photography']
    topic = topics[scope_index]
    negative_word = ['volcano', 'earthquake', 'glacier', 'tornado', 'wildfire'][scope_index]
    ambiguous_floor = round(3 + scope_index * 0.1, 1)
    incomplete_floor = round(3.2 + scope_index * 0.1, 1)
    page_floor = 250 + scope_index * 10
    aggregate_year = 2015 + scope_index

    def add(number, label, topology, query, **kwargs):
        rows.append(build(scope, number, label, topology, query, **kwargs))

    def year_clause(year):
        return f'publication year {year} onward is optional' if glob else f'publication year {year} onward is mandatory'

    def year_values(year):
        return {} if glob else {'year_min': year}

    def year_soft(year):
        return [preference('year_min', year, 'AT_LEAST')] if glob else []

    available_clause = 'available now is an optional wish' if glob else 'must be available now'
    available_values = {} if glob else {'availability': 'AVAILABLE_NOW'}
    available_soft = [preference('availability', 'AVAILABLE_NOW')] if glob else []
    language_clause = 'English language is optional' if glob else 'English language is mandatory'
    language_values = {} if glob else {'language': 'English'}
    language_soft = [preference('language', 'English')] if glob else []

    # Five executable semantic families: intersect literal operands, hard facets,
    # whole-word negatives, advisory metadata, and a definite semantic topic.
    add(1, 'CLEAR_EXECUTABLE', 'SMART:rating,author,format,preference',
        f'Find books by "{author}" rated at least 4 in online format; introductory treatments are preferred.',
        values={'author_text': author, 'rating_min': 4, 'formats': ['ONLINE']},
        soft=[preference('audience', 'INTRODUCTORY')],
        explanation='Literal author contains, inclusive rating floor, and online access intersect. Introductory treatment is advisory.')
    add(2, 'CLEAR_EXECUTABLE', 'SMART:title,negative,include,sort',
        f'Category Fiction; titled "{title}"; exclude the whole-word searchable text "drought". Sort title ascending.',
        values={'subjects': ['Fiction'], 'title_text': title, 'exclude_terms': ['drought']}, sort='TITLE',
        explanation='A canonical positive category, literal titled operand, and broad whole-word text negative have distinct native meanings.')
    add(3, 'CLEAR_EXECUTABLE', 'SMART:author,title,metadata,sort',
        f'Books by "{author}" titled "{missing_title}"; {language_clause}. Sort title ascending.',
        values={'author_text': author, 'title_text': missing_title, **language_values}, soft=language_soft, sort='TITLE',
        explanation='The two quoted bibliographic fields are complete literal contains operands. Missing-like title words stay literal; no identity inference is needed. Global language is advisory.')
    add(4, 'CLEAR_EXECUTABLE', 'SMART:rating,title,availability,sort',
        f'Titled "{missing_title}", at most 4 stars; {available_clause}. Sort highest rating first.',
        values={'title_text': missing_title, 'rating_max': 4, **available_values}, soft=available_soft, sort='RATING',
        explanation='An inclusive rating ceiling and literal titled operand are resolved. Tenant availability is enforceable; Global availability was explicitly optional.')
    add(5, 'CLEAR_EXECUTABLE', 'SMART:rating,include,metadata,preference',
        f'Subject Fiction, rated at least 3.5, about {topic}. French language is optional; introductory treatments are preferred.',
        values={'subjects': ['Fiction'], 'rating_min': 3.5}, topic=topic,
        soft=[preference('language', 'French'), preference('audience', 'INTRODUCTORY')],
        explanation='The definite topic remains semantic, while Fiction and the rating floor are hard. Optional language and introductory treatment stay advisory.')

    # Five safe normalization families. Scope-specific canonical lists are the
    # only authority for spelling corrections; bibliography is never repaired.
    add(6, 'SAFE_UNCERTAIN_EXECUTABLE', 'SMART:rating,author,include,metadata,sort',
        f'Subject "Fictiom"; by "{author}"; rated at least 4.2; English language is optional. Sort highest rating first.',
        values={'subjects': ['Fiction'], 'author_text': author, 'rating_min': 4.2}, soft=[preference('language', 'English')], sort='RATING',
        notices=[{'kind': 'CANONICAL_CORRECTION', 'field': 'subjects', 'input': 'Fictiom', 'canonical': 'Fiction'}],
        assertions=[{'kind': 'canonical_correction', 'field': 'subjects', 'raw': 'Fictiom', 'resolved': 'Fiction', 'authority': 'scope canonical_subjects'}],
        explanation='Fictiom is a unique one-letter repair to authoritative Fiction. Preserve the exact author string and rating; disclose the category repair.')
    add(7, 'SAFE_UNCERTAIN_EXECUTABLE', 'SMART:author,negative,include,availability,sort',
        f'Category Fiction; exclude category "{exclusion_typo}"; books by "{author}"; {available_clause}. Sort title ascending.',
        values={'subjects': ['Fiction'], 'exclude_subjects': [exclusion_subject], 'author_text': author, **available_values},
        soft=available_soft, sort='TITLE',
        notices=[{'kind': 'CANONICAL_CORRECTION', 'field': 'exclude_subjects', 'input': exclusion_typo, 'canonical': exclusion_subject}],
        assertions=[{'kind': 'canonical_correction', 'field': 'exclude_subjects', 'raw': exclusion_typo, 'resolved': exclusion_subject, 'authority': 'scope canonical_subjects'}],
        explanation='The misspelled negative category uniquely repairs to a local canonical category. It stays a category exclusion, never a broad text exclusion.')
    add(8, 'SAFE_UNCERTAIN_EXECUTABLE', 'SMART:year,title,include,preference',
        f'Category "Ficton", titled "{missing_title}"; {year_clause(2016)}. Research treatments are preferred.',
        values={'subjects': ['Fiction'], 'title_text': missing_title, **year_values(2016)},
        soft=year_soft(2016) + [preference('audience', 'RESEARCH')],
        notices=[{'kind': 'CANONICAL_CORRECTION', 'field': 'subjects', 'input': 'Ficton', 'canonical': 'Fiction'}],
        assertions=[{'kind': 'canonical_correction', 'field': 'subjects', 'raw': 'Ficton', 'resolved': 'Fiction', 'authority': 'scope canonical_subjects'}],
        explanation='Unique Fiction spelling repair can execute with a notice. The quoted Missing-like literal is complete. Global publication year is an explicit wish.')
    add(9, 'SAFE_UNCERTAIN_EXECUTABLE', 'SMART:negative,include,metadata,sort',
        f'Subject "{scope_typo}"; exclude whole-word searchable text "{negative_word}"; {language_clause}. Sort title ascending.',
        values={'subjects': [scope_subject], 'exclude_terms': [negative_word], **language_values}, soft=language_soft, sort='TITLE',
        notices=[{'kind': 'CANONICAL_CORRECTION', 'field': 'subjects', 'input': scope_typo, 'canonical': scope_subject}],
        assertions=[{'kind': 'canonical_correction', 'field': 'subjects', 'raw': scope_typo, 'resolved': scope_subject, 'authority': 'scope canonical_subjects'}],
        explanation='The local canonical category uniquely resolves the spelling. The explicit searchable-word exclusion retains its broad text domain; language is hard only in tenants.')
    add(10, 'SAFE_UNCERTAIN_EXECUTABLE', 'SMART:rating,title,include,format,metadata,sort',
        f'Titled "{title}"; category "Fictoin"; online only; rated at most 4.7; English language is optional. Sort title ascending.',
        values={'title_text': title, 'subjects': ['Fiction'], 'formats': ['ONLINE'], 'exclusive_formats': ['ONLINE'], 'rating_max': 4.7},
        soft=[preference('language', 'English')], sort='TITLE',
        notices=[{'kind': 'CANONICAL_CORRECTION', 'field': 'subjects', 'input': 'Fictoin', 'canonical': 'Fiction'}],
        assertions=[{'kind': 'canonical_correction', 'field': 'subjects', 'raw': 'Fictoin', 'resolved': 'Fiction', 'authority': 'scope canonical_subjects'}],
        explanation='A unique transposition repairs the category. Online-only must retain both the positive and exclusive native format lists, alongside literal title and rating ceiling.')

    # Five ambiguities: rating direction, partial category choice, field ownership,
    # exclusion domain, and title choice. Other resolved constraints survive.
    add(31, 'AMBIGUOUS', 'SMART:rating,year,author,include,format,metadata,preference',
        f'By "{author}", subject Fiction, online; rating boundary 4 is mandatory, but its intended direction remains undecided: at least or at most. {year_clause(2012 + scope_index)}; English language is optional; research treatments are preferred.',
        values={'author_text': author, 'subjects': ['Fiction'], 'formats': ['ONLINE'], **year_values(2012 + scope_index)},
        unknown={'rating_min': 'The inclusive rating boundary is 4, but it is undecided whether this is a lower bound.', 'rating_max': 'The inclusive rating boundary is 4, but it is undecided whether this is an upper bound.'},
        soft=year_soft(2012 + scope_index) + [preference('language', 'English'), preference('audience', 'RESEARCH')],
        assertions=[{'kind': 'unresolved_comparison_direction', 'field': 'rating', 'boundary': 4, 'alternatives': ['GTE', 'LTE'], 'select': 'ONE', 'mandatory': True}],
        explanation='The mandatory rating comparison has a supplied number and known inclusivity, but an unresolved comparison direction. This is ambiguity rather than a missing value. The literal author, canonical category, online access and tenant year remain resolved; advisory language/research and Global year stay separate.')
    add(12, 'AMBIGUOUS', 'SMART:year,title,include,metadata',
        f'Subject Fiction is required together with exactly one of {alt_subjects[0]} or {alt_subjects[1]}, choice undecided; titled "{title}"; {year_clause(2018)}; English language is optional.',
        values={'title_text': title, **year_values(2018)},
        partial={'subjects': {'resolved': ['Fiction'], 'reason': f'Fiction is a mandatory common item, but one additional subject from {alt_subjects} remains undecided.'}},
        soft=year_soft(2018) + [preference('language', 'English')],
        assertions=[{'kind': 'unresolved_alternatives', 'field': 'subjects', 'common': ['Fiction'], 'alternatives': alt_subjects, 'select': 'ONE_ADDITIONAL'}],
        explanation='The common Fiction category is retained explicitly; an additional mandatory canonical-category choice blocks execution. Optional Global year and language create no extra hard requirements.')
    add(13, 'AMBIGUOUS', 'SMART:author,title,format,sort',
        f'Online books: "{author}" and "{title}" fill the by and titled fields, one each, but their assignment is undecided. Sort title ascending.',
        values={'formats': ['ONLINE']},
        unknown={'author_text': 'Two literals have unresolved author/title field ownership.', 'title_text': 'Two literals have unresolved author/title field ownership.'}, sort='TITLE',
        assertions=[{'kind': 'unresolved_association', 'fields': ['author_text', 'title_text'], 'literals': [author, title], 'bijection_required': True}],
        explanation='Two complete literals do not resolve which field owns each. Preserve online access and the requested order, without guessing bibliographic identities.')
    add(14, 'AMBIGUOUS', 'SMART:rating,negative,availability,preference',
        f'At least {ambiguous_floor} stars; exclude "Fiction", with its domain undecided between a catalog facet and a whole-word searchable text operand; {available_clause}. Research treatments are preferred.',
        values={'rating_min': ambiguous_floor, **available_values},
        unknown={'exclude_subjects': 'The mandatory Fiction exclusion could address the canonical facet.', 'exclude_terms': 'The mandatory Fiction exclusion could address whole-word searchable text.'},
        soft=available_soft + [preference('audience', 'RESEARCH')],
        assertions=[{'kind': 'unresolved_exclusion_domain', 'literal': 'Fiction', 'alternatives': ['exclude_subjects', 'exclude_terms']}],
        explanation='The domain ambiguity changes which records can pass. The category and whole-word text operations must never be silently interchanged.')
    add(15, 'AMBIGUOUS', 'SMART:title,include,format,metadata,preference',
        f'Category Fiction, online; titled either "{title}" or "{missing_title}", with one required title still undecided. English language is optional; short treatments are preferred.',
        values={'subjects': ['Fiction'], 'formats': ['ONLINE']},
        unknown={'title_text': 'One mandatory literal title must be selected from the two unresolved alternatives.'},
        soft=[preference('language', 'English'), preference('length', 'SHORT')],
        assertions=[{'kind': 'unresolved_alternatives', 'field': 'title_text', 'alternatives': [title, missing_title], 'select': 'ONE'}],
        explanation='The unresolved single title choice is mandatory. Optional language and a short-treatment preference cannot supply the missing selection.')

    # Five explicit omissions. Missing operands are unscored, not invented as
    # text, while independently resolved scalar operands remain gold.
    add(16, 'INCOMPLETE', 'SMART:rating,year,author,metadata',
        f'Rated at least 3.8; {year_clause(2014 + scope_index)}; by [required author value left blank]; English language is optional.',
        values={'rating_min': 3.8, **year_values(2014 + scope_index)}, unknown={'author_text': 'The required author operand is explicitly blank.'},
        soft=year_soft(2014 + scope_index) + [preference('language', 'English')],
        assertions=[{'kind': 'missing_required_value', 'field': 'author_text', 'raw_marker': '[required author value left blank]'}],
        explanation='The author slot is structurally missing. Its bracketed marker is an omission instruction, unlike complete quoted entity literals containing Missing or Empty.')
    add(17, 'INCOMPLETE', 'SMART:title,negative,include,format,availability',
        f'Category Fiction; titled "{missing_title}"; online; {available_clause}; exclude whole-word searchable text [required exclusion value left blank].',
        values={'subjects': ['Fiction'], 'title_text': missing_title, 'formats': ['ONLINE'], **available_values}, soft=available_soft,
        unknown={'exclude_terms': 'A whole-word text exclusion is mandatory but its operand is explicitly omitted.'},
        assertions=[{'kind': 'missing_required_value', 'field': 'exclude_terms', 'raw_marker': '[required exclusion value left blank]'}],
        explanation='The complete quoted title stays literal. The separate mandatory exclusion slot has no supplied value, so it cannot execute.')
    add(18, 'INCOMPLETE', 'SMART:rating,include,availability,metadata',
        f'Category [required value unfilled]; rated at least {incomplete_floor}; {available_clause}; English language is optional.',
        values={'rating_min': incomplete_floor, **available_values}, unknown={'subjects': 'The mandatory category value is explicitly unfilled.'},
        soft=available_soft + [preference('language', 'English')],
        assertions=[{'kind': 'missing_required_value', 'field': 'subjects', 'raw_marker': '[required value unfilled]'}],
        explanation='The required category is absent, not an unknown category name. The independent rating and supported availability operands remain resolved.')
    add(19, 'INCOMPLETE', 'SMART:year,author,format,sort',
        f'Books by "{author}", online; {year_clause(2011)}; sort [mandatory ordering key omitted].',
        values={'author_text': author, 'formats': ['ONLINE'], **year_values(2011)}, soft=year_soft(2011), sort=None,
        assertions=[{'kind': 'missing_required_value', 'field': 'sort', 'raw_marker': '[mandatory ordering key omitted]'}],
        explanation='A mandatory explicit sorting slot is blank; treating it as default relevance would silently discard a requirement. Author, format, and tenant year are resolved.')
    add(20, 'INCOMPLETE', 'SMART:rating,title,metadata,preference',
        f'Titled "{missing_title}"; rating at least [required number omitted]; English language is optional; introductory treatments are preferred.',
        values={'title_text': missing_title}, unknown={'rating_min': 'An inclusive rating floor is mandatory but its number is omitted.'},
        soft=[preference('language', 'English'), preference('audience', 'INTRODUCTORY')],
        assertions=[{'kind': 'missing_required_value', 'field': 'rating_min', 'inclusive': True, 'raw_marker': '[required number omitted]'}],
        explanation='The rating operation is known and inclusive, but its boundary is absent. The complete title string and optional wishes cannot supply that numeric operand.')

    # Five unsupported operation families: page threshold, field-local negative,
    # invented facet, aggregate/relational exclusion, and same-page proximity.
    add(21, 'UNSUPPORTED', 'SMART:rating,year,format,metadata',
        f'Online books rated at least 4; {year_clause(2019)}; require at least {page_floor} pages.',
        values={'formats': ['ONLINE'], 'rating_min': 4, **year_values(2019)}, soft=year_soft(2019),
        assertions=[{'kind': 'unsupported_metadata_predicate', 'field': 'pages', 'operator': 'GTE', 'value': page_floor, 'mandatory': True}],
        explanation='A strict page-count threshold has no native hard field. Preserve the valid rating, online, and tenant-year operands but block rather than discard pages.')
    add(22, 'UNSUPPORTED', 'SMART:author,negative,include,sort',
        f'Category Fiction; exclude books by "{author}" using the author field alone. Sort title ascending.',
        values={'subjects': ['Fiction']}, sort='TITLE',
        assertions=[{'kind': 'unsupported_field_specific_negative', 'field': 'author_text', 'operator': 'NOT_CONTAINS', 'value': author, 'mandatory': True}],
        explanation='A mandatory author-field-only exclusion is unsupported. No positive author operand or broad searchable-text exclusion was requested; both native fields are correctly absent.')
    add(23, 'UNSUPPORTED', 'SMART:title,negative,format,availability,metadata',
        f'Titled "{title}", online; {available_clause}; without the invented facet cinder_phase set to blue, mandatory. English language is optional.',
        values={'title_text': title, 'formats': ['ONLINE'], **available_values},
        soft=available_soft + [preference('language', 'English')],
        assertions=[{'kind': 'unsupported_invented_facet', 'field': 'cinder_phase', 'operator': 'NEQ', 'value': 'blue', 'mandatory': True, 'explicitly_invented': True}],
        explanation='An invented strict facet has no native implementation. Its negative cannot become a word exclusion or semantic topic; resolved title/format/tenant availability stay intact.')
    add(24, 'UNSUPPORTED', 'SMART:year,negative,include,format,sort',
        f'Category Fiction, online; {year_clause(aggregate_year)}; exclude authors with fewer than three matching catalog items. Sort title ascending.',
        values={'subjects': ['Fiction'], 'formats': ['ONLINE'], **year_values(aggregate_year)}, soft=year_soft(aggregate_year), sort='TITLE',
        assertions=[{'kind': 'unsupported_group_aggregate', 'group_key': 'author', 'aggregate': 'COUNT_MATCHING_CATALOG_ITEMS', 'operator': 'GTE', 'value': 3, 'mandatory': True}],
        explanation='The requirement counts matching records per author, so a per-item filter cannot enforce it. Do not manufacture an author string or text negative from the aggregate.')
    add(25, 'UNSUPPORTED', 'SMART:rating,author,title,availability,metadata',
        f'By "{author}", titled "{title}", rated at least 3.6; {available_clause}; require these author and title strings to occur together on the same page of searchable content.',
        values={'author_text': author, 'title_text': title, 'rating_min': 3.6, **available_values}, soft=available_soft,
        assertions=[{'kind': 'unsupported_proximity', 'operands': [author, title], 'relation': 'SAME_PAGE_OF_SEARCHABLE_CONTENT', 'mandatory': True}],
        explanation='Literal bibliographic filters do not establish same-page text proximity. That separate mandatory relation is unsupported even though the constituent fields are complete.')

    # Five contradiction families. Interior words in contains literals guarantee
    # broad searchable-text negatives conflict, even under native title OR author
    # matching. Global unsupported year and availability remain advisory.
    add(26, 'CONTRADICTORY', 'SMART:rating,year,author,negative,metadata',
        f'By "{author}"; rated at least 4.8 and at most 2; {year_clause(2017)}; exclude searchable word "drought"; English language is optional.',
        values={'author_text': author, 'rating_min': 4.8, 'rating_max': 2, 'exclude_terms': ['drought'], **year_values(2017)}, soft=year_soft(2017) + [preference('language', 'English')],
        assertions=[{'kind': 'incompatible_bounds', 'field': 'rating', 'minimum': 4.8, 'maximum': 2}],
        explanation='The resolved inclusive rating interval is empty. The independent author, negative word, and tenant-year predicates do not repair it.')
    add(27, 'CONTRADICTORY', 'SMART:year,title,negative,format,sort',
        f'Titled "{title}"; online only, and exclude the online format; {year_clause(2013)}. Sort title ascending.',
        values={'title_text': title, 'formats': ['ONLINE'], 'exclusive_formats': ['ONLINE'], 'excluded_formats': ['ONLINE'], **year_values(2013)}, soft=year_soft(2013), sort='TITLE',
        assertions=[{'kind': 'positive_negative_conflict', 'field': 'formats', 'required': ['ONLINE'], 'excluded': ['ONLINE']}],
        explanation='The sole required format is also explicitly forbidden. Global uses a supported ONLINE predicate and an advisory year, so its blocker is the same resolved contradiction.')
    add(28, 'CONTRADICTORY', 'SMART:author,negative,include,metadata,preference',
        f'By "{author}"; category Fiction is required; exclude category Fiction; {language_clause}; research treatments are preferred.',
        values={'author_text': author, 'subjects': ['Fiction'], 'exclude_subjects': ['Fiction'], **language_values}, soft=language_soft + [preference('audience', 'RESEARCH')],
        assertions=[{'kind': 'positive_negative_conflict', 'field': 'subjects', 'required': ['Fiction'], 'excluded': ['Fiction']}],
        explanation='The identical canonical category is both required and forbidden. This is a category contradiction, not a broad-word negative or author exclusion.')
    add(29, 'CONTRADICTORY', 'SMART:rating,title,negative,metadata,sort',
        f'Titled "{title}"; rated at least 3; exclude the whole-word searchable text "{title.split()[1]}"; English language is optional. Sort title ascending.',
        values={'title_text': title, 'rating_min': 3, 'exclude_terms': [title.split()[1]]}, soft=[preference('language', 'English')], sort='TITLE',
        assertions=[{'kind': 'literal_contains_text_exclusion_conflict', 'field': 'title_text', 'literal': title, 'excluded_whole_word': title.split()[1]}],
        explanation='The native literal contains operand necessarily supplies the excluded interior whole word in title or author searchable text. The broad whole-word negative forbids every such match.')
    add(30, 'CONTRADICTORY', 'SMART:rating,author,title,negative,include,format,sort',
        f'Category Fiction; by "{author}", titled "{title}"; online, rated at least 2.5; exclude whole-word searchable text "{author.split()[1]}". Sort title ascending.',
        values={'subjects': ['Fiction'], 'author_text': author, 'title_text': title, 'formats': ['ONLINE'], 'rating_min': 2.5, 'exclude_terms': [author.split()[1]]}, sort='TITLE',
        assertions=[{'kind': 'literal_contains_text_exclusion_conflict', 'field': 'author_text', 'literal': author, 'excluded_whole_word': author.split()[1]}],
        explanation='The positive author literal necessarily contains the excluded interior whole word. Author text is in the searchable domain, so no record satisfies this full intersection.')


structures = {structure(row) for row in rows}
original_path = ROOT / 'reports/search_comp3_authored.jsonl'
original_bytes = original_path.read_bytes()
original_rows = [json.loads(line) for line in original_bytes.decode('utf-8-sig').splitlines() if line.strip()]
old_kept = {r['case_id']: r for r in original_rows if r['family_id'] != 'COMP3-F11'}
new_kept = {r['case_id']: r for r in rows if r['family_id'] != 'COMP3-F31'}
assert len(old_kept) == len(new_kept) == 145
assert old_kept == new_kept, 'All non-rejected authored rows must be unchanged.'
assert not any(r['family_id'] == 'COMP3-F11' for r in rows)
assert len([r for r in rows if r['family_id'] == 'COMP3-F31']) == 5
assert len(rows) == 150
assert len(structures) == 30, len(structures)
assert len({row['query_text'] for row in rows}) == 150
assert len({row['case_id'] for row in rows}) == 150
assert len({row['family_id'] for row in rows}) == 30
assert all(len({r['structural_component_id'] for r in rows if r['family_id'] == family}) == 1 for family in {r['family_id'] for r in rows})
cells = collections.Counter((r['scope_type'], r['decision_stratum']) for r in rows)
assert len(cells) == 30 and set(cells.values()) == {5}
for row in rows:
    assert set(FIELDS) <= set(row['metric_applicability'])
    for field in FIELDS:
        status = row['metric_applicability'][field]['status']
        if status == 'UNRESOLVED':
            assert field not in row['expected_hard_constraints']
        else:
            assert field in row['expected_hard_constraints']
    for field in LISTS:
        if field in row['expected_hard_constraints']:
            assert isinstance(row['expected_hard_constraints'][field], list)
    for field in BOOLS:
        if field in row['expected_hard_constraints']:
            assert isinstance(row['expected_hard_constraints'][field], bool)
    if row['scope_type'] == 'GLOBAL':
        h = row['expected_hard_constraints']
        assert h.get('year_min') is None and h.get('year_max') is None
        assert h.get('language') is None and h.get('availability') is None
        assert all(f == 'ONLINE' for f in h.get('formats', []))
    assert set(brief['schema']['keys']) <= set(row)

output = ROOT / brief['output']
output.write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows), encoding='utf-8')
provenance = {
    'author': {'kind': 'AI', 'actual_model_identity': 'NOT_EXPOSED', 'human_authors': 0},
    'independence': {
        'candidate_source_read': False, 'prior_cases_or_gold_read': False,
        'predictions_or_outcomes_read': False, 'acceptance_thresholds_read': False,
        'sealed_content_read': False, 'network_or_database_calls': False,
        'parser_or_model_api_calls': False,
        'reads': [str(BRIEF.relative_to(ROOT)).replace('\\', '/'), str(SOURCE.relative_to(ROOT)).replace('\\', '/'), 'scripts/search_comp3_author_generate.py', 'reports/search_comp3_authored.jsonl'],
        'normative_clarifications_from_parent_only': [
            'Native scalar and list types, mask vocabulary, typed notice decision, and unresolved-value omission were supplied without candidate outputs.',
            'Whole-word searchable-text negatives cover normalized title, authors, subjects, and description using non-word boundaries.',
            'Native title_text matches title OR author text; authored gold preserves that contract and makes no bibliography-identity assertion.'
        ],
        'topology_function': 'Exact supplied pure C2 source executed unchanged in isolated namespace.',
        'authorship_method': 'Thirty independently specified semantic families manually authored, each parameterized over all five authoritative scopes. No optimization against candidate behavior.'
    },
    'input_sha256': {str(BRIEF.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(brief_bytes).hexdigest(), str(SOURCE.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(source_bytes).hexdigest(), 'reports/search_comp3_authored.jsonl': hashlib.sha256(original_bytes).hexdigest()},
    'version': 2,
    'revision_provenance': {
        'trigger': 'Established sealed structural auditor reported operation-topology collision in exactly five COMP3-F11-<scope> rows before any prediction capture.',
        'feedback_received': 'Rejected identifiers and collision fact only; no sealed contents, predictions, outcomes, or acceptance target rates.',
        'retired_family': 'COMP3-F11',
        'replacement_family': 'COMP3-F31',
        'replacement_semantics': 'Unresolved mandatory rating comparison direction at a fully supplied inclusive boundary, rather than single-author choice.',
        'replacement_topology': 'SMART:rating,year,author,include,format,metadata,preference',
        'unchanged_rows_verified': 145,
        'new_rows': 5,
        'original_artifact_helper_and_provenance_preserved': True,
        'prediction_capture_or_candidate_calls': False
    },
    'schema_conventions': {
        'unknown': 'Mandatory unresolved fields omitted from expected_hard_constraints, explicit UNRESOLVED applicability mask without a resolved_value.',
        'partial_lists': 'Resolved common values retained with PARTIALLY_APPLICABLE and explicit alternatives in unadapted_mandatory_assertions.',
        'absence': 'Every known absent scalar/list/bool asserted as None/[]/False with APPLICABLE_ABSENCE.',
        'formats': 'formats/exclusive_formats/excluded_formats are string lists. ONLINE only asserts ONLINE in both formats and exclusive_formats.',
        'availability': 'AVAILABLE_NOW for mandatory available-now tenant requests; Global availability is explicitly advisory.',
        'notices': 'Canonical spelling correction carries raw and canonical operands plus source authority, independently of field gold.',
        'preferences': 'Structured field/relation/value/mandatory=false objects, preserved separately from hard constraints.',
        'unadapted_assertions': 'Unsupported, missing, alternative, association, repair, and contradictory requirements are preserved without forcing them into native fields.'
    },
    'counts': {'contexts': len(rows), 'families': 30, 'distinct_allowed_topologies': len(structures), 'scopes': len(SCOPES), 'scope_decision_cells': len(cells), 'contexts_per_cell': 5, 'human_authors': 0},
    'stratum_counts': dict(collections.Counter(r['decision_stratum'] for r in rows)),
    'topologies': sorted(structures),
    'scope_decision_counts': {scope + '/' + stratum: n for (scope, stratum), n in sorted(cells.items())},
    'validation': {'exact_structure_allowlist_membership': True, 'query_length_max500': True, 'all_scalar_masks_present': True, 'known_absence_explicit': True, 'unknown_values_not_invented': True, 'global_unsupported_capabilities_never_hard': True, 'max_query_chars': max(map(lambda r: len(r['query_text']), rows))},
    'normative_uncertainties': [
        'The brief does not prescribe a wire schema for preference or notice objects; explicit self-describing structured objects are used.',
        'Spelling corrections are independent judgments of unique canonical repair, not observed parser behavior.',
        'No execution was used to establish how unsupported or incomplete requests expose partial resolved operands; gold asserts normative meanings and applicability independently.'
    ],
    'artifacts': [brief['output'], brief['provenance_output'], 'scripts/search_comp3_author_generate_v2.py']
}
(ROOT / brief['provenance_output']).write_text(json.dumps(provenance, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
print(json.dumps({'output': brief['output'], 'provenance': brief['provenance_output'], 'contexts': len(rows), 'topologies': len(structures), 'cells': len(cells), 'max_query_chars': provenance['validation']['max_query_chars']}))
