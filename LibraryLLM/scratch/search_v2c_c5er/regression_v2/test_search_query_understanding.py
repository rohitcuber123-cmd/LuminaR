"""Deterministic planning and canonical constraints; no models or production writes."""
import pytest
from scratch.search_v2c_c5er.candidate_search_v2.query_plan import parse_query, matches, FacetVocabulary, sort_books
FACETS = ['Fiction', 'Science fiction', 'History', 'Biography', 'Poetry', 'Fantasy', 'Detective and mystery stories', 'Folktales', 'Science']

@pytest.mark.parametrize('query,field,value,exclusive', [('rating above 4', 'rating_min', 4, True), ('rated over 4', 'rating_min', 4, True), ('rating at least 4', 'rating_min', 4, False), ('rating >= 4', 'rating_min', 4, False), ('rated 4+', 'rating_min', 4, False), ('4+ stars', 'rating_min', 4, False), ('fiction books rated 4 or higher', 'rating_min', 4, False), ('rating below 3', 'rating_max', 3, True), ('rating at most 3', 'rating_max', 3, False), ('history books published after 2015', 'year_min', 2015, True), ('before 2010', 'year_max', 2010, True), ('published in 2020', 'year_min', 2020, False)])
def test_bound_parser(query, field, value, exclusive):
    plan = parse_query(query, FACETS)
    assert getattr(plan, field) == value and getattr(plan, field + '_exclusive') == exclusive

@pytest.mark.parametrize('query,subject', [('fiction', 'Fiction'), ('SCI-FI', 'Science fiction'), ('detectve', 'Detective and mystery stories'), ('folktail', 'Folktales'), ('bio', 'Biography')])
def test_facets(query, subject):
    assert parse_query(query, FACETS).subjects == [subject]

def test_genre_subject_false_positive():
    plan = parse_query('fiction', FACETS, 'GENRE_SUBJECT')
    assert matches(plan, {'title': 'Unrelated title', 'subjects': 'History | Fiction'})
    assert not matches(plan, {'title': 'Fiction studies', 'subjects': ['History']})

def test_mixed_semantic_remainder():
    plan = parse_query('fiction books about wizards rated above 4', FACETS)
    assert plan.subjects == ['Fiction'] and plan.semantic_text == 'wizards'
    assert plan.rating_min == 4 and plan.rating_min_exclusive

def test_between_ratings():
    plan = parse_query('books about wizards between 3 and 4 stars', FACETS)
    assert (plan.rating_min, plan.rating_max, plan.semantic_text) == (3, 4, 'wizards')

@pytest.mark.parametrize('rating,count,expected', [(3.9, 5, False), (4, 5, False), (4.01, 1, True), (None, 10, False), (0, 0, False), (float('nan'), 2, False)])
def test_rating_strict_and_missing(rating, count, expected):
    assert matches(parse_query('rating above 4'), {'average_rating': rating, 'rating_count': count}) == expected

def test_explicit_filter_overrides_and_chip_removal():
    query = 'fiction books about wizards rated above 4'
    plan = parse_query(query, FACETS, filters={'rating_min': 3}, omit=['subject'])
    assert plan.raw_query == query and plan.subjects == [] and (plan.rating_min == 3) and (not plan.rating_min_exclusive)
    removed = parse_query(query, FACETS, omit=['rating_min', 'topic'])
    assert removed.semantic_text is None and removed.rating_min is None and (removed.subjects == ['Fiction'])

def test_unknown_and_ambiguous_not_forced():
    assert parse_query('xylophonetransport', FACETS).subjects == []
    plan = parse_query('science', FACETS)
    assert plan.subjects == [] and plan.suggested_subject == 'Science' and (plan.semantic_text == 'science')
    assert parse_query('xylophonetransport', FACETS, 'GENRE_SUBJECT').unknown_subject
    assert FacetVocabulary(['History']).resolve('detective')[0] is None

def test_title_author_no_semantic():
    plan = parse_query('Tolkien', FACETS, 'TITLE_AUTHOR')
    assert plan.semantic_text is None and matches(plan, {'authors': ['J. R. R. Tolkien']})
    assert not matches(plan, {'title': 'Wizard world', 'authors': ['Other']})
    assert parse_query('books by Tolkien rating above 4', FACETS).author_text == 'tolkien'

@pytest.mark.parametrize('mode,text,record', [('SMART', '978-1-234-56789-0', {'isbn_13': '9781234567890'}), ('EXACT', 'AC-007', {'accession_number': 'AC-007'}), ('EXACT', 'Exact Title', {'title': 'exact title'}), ('SMART', 'OL123W', {'work_id': 'OL123W'})])
def test_exact_identifiers(mode, text, record):
    plan = parse_query(text, FACETS, mode)
    assert plan.exact_text and plan.semantic_text is None and matches(plan, record)

@pytest.mark.parametrize('query,record,expected', [('online books about robotics', {'has_online': True}, True), ('online books about robotics', {'has_online': False}, False), ('physical + online', {'has_online': True, 'has_physical': False}, False), ('physical + online', {'has_online': True, 'has_physical': True}, True), ('available to request', {'has_online': True}, False), ('available now', {'has_online': True}, True), ('available to request', {'circulation_status': 'CIRCULATING', 'requestable_count': 1}, True), ('after 2020', {'publication_year': 2020}, False), ('after 2020', {'publication_year': 2021}, True), ('after 2020', {}, False)])
def test_format_availability_year(query, record, expected):
    assert matches(parse_query(query, FACETS), record) == expected

@pytest.mark.parametrize('filters', [{'rating_min': 6}, {'year_min': 999}, {'format': 'FAKE'}, {'sort': 'FAKE'}])
def test_invalid_filters_rejected(filters):
    with pytest.raises(ValueError):
        parse_query('fiction', FACETS, filters=filters)

def test_sort_after_filtering():
    rows = [{'title': 'Z', 'average_rating': 5, 'publication_year': 2000}, {'title': 'A', 'average_rating': 4, 'publication_year': 2020}]
    for sort, title in [('TITLE', 'A'), ('RATING', 'Z'), ('NEWEST', 'A')]:
        assert sort_books(rows, parse_query('', filters={'sort': sort}))[0]['title'] == title

def test_invalid_natural_number_not_partially_parsed():
    assert parse_query('rating above 40').rating_min is None
