"""Numeric boundary and source-evidence safety contracts (development only)."""
import pytest
from scratch.search_proof_recovery_v7.parser import parse_query, matches
from scratch.search_proof_recovery_v7.parser import executable
from scratch.search_v2c_c5er.candidate_search_v4.query_numeric import range_contradiction, valid_numeric_domain

@pytest.mark.parametrize('phrase,accepted', [('rated above four', [False, False, True]), ('rating higher than 4', [False, False, True]), ('rating exceeding four', [False, False, True]), ('rating no less than 4', [False, True, True]), ('minimum review rating 4', [False, True, True]), ('no fewer than four stars', [False, True, True]), ('four stars or better', [False, True, True]), ('rating below four', [True, False, False]), ('rating lower than 4', [True, False, False]), ('fewer than four stars', [True, False, False]), ('maximum rating 4', [True, True, False]), ('rating not above four', [True, True, False]), ('rating of four or less', [True, True, False]), ('4+', [False, True, True]), ('rated 4+ stars', [False, True, True]), ('rating = 4', [False, True, False]), ('four-star books', [False, True, False])])
def test_rating_boundary_eligibility(phrase, accepted):
    plan = parse_query(phrase)
    assert executable(plan), plan.decision
    assert [matches(plan, {'title': 'Control', 'average_rating': rating, 'rating_count': 1}) for rating in (3.99, 4, 4.01)] == accepted
    assert not matches(plan, {'title': 'Unrated'})
    assert any((c['field'] == 'rating' and c['source_text'] for c in plan.constraint_candidates))

@pytest.mark.parametrize('query,low,high', [('rating between 3 and 4', 3, 4), ('keep ratings from 2.5 through 4.5', 2.5, 4.5), ('a rating within 4 to 5', 4, 5), ('three-and-a-half stars or higher', 3.5, None), ('below four and a half stars', None, 4.5), ('above 3 and under 5', 3, 5), ('rating must exceed 3 but stay below 4', 3, 4), ('rating no more than 4 but no less than 2', 2, 4)])
def test_rating_intersections_and_fractional_words(query, low, high):
    plan = parse_query(query)
    assert executable(plan), plan.decision
    assert (plan.rating_min, plan.rating_max) == (low, high)

@pytest.mark.parametrize('query', ['rating at least 4.5 but below 4.5', 'rating must be higher than four and lower than four', 'rating no more than 1 and no less than 4', 'publication year from 2021 to 2020', 'published strictly after 2020 but by 2020', 'published before 1999 and since 1999', 'the publication must precede 2020 and follow 2021'])
def test_empty_intersection_never_executes(query):
    plan = parse_query(query)
    assert plan.decision['decision_type'] == 'CONTRADICTORY'
    assert not executable(plan)
    assert not matches(plan, {'average_rating': 4.5, 'publication_year': 2021})

@pytest.mark.parametrize('query,low,high,lower_exclusive,upper_exclusive', [('publication from 2000 through 2010', 2000, 2010, False, False), ('published no earlier than 1990 and no later than 1995', 1990, 1995, False, False), ('publication year > 2017 and <= 2019', 2017, 2019, True, False), ('publication after 1980, at most 1990', 1980, 1990, True, False), ('books issued no earlier than 2012 about 1980s music', 2012, None, False, False), ('printed before 1990 about the year 2000', None, 1990, False, True), ('a publication dating to 2018 on Route 66', 2018, 2018, False, False), ('books from publication year 2004 about harbours', 2004, 2004, False, False), ('before 2018 in publication year', None, 2018, False, True), ('books published after 2020 about events after 1945', 2020, None, True, False)])
def test_publication_field_and_contiguous_year_clauses(query, low, high, lower_exclusive, upper_exclusive):
    plan = parse_query(query)
    assert (plan.year_min, plan.year_max) == (low, high)
    for candidate in plan.constraint_candidates:
        if candidate['field'] == 'year':
            assert query[candidate['source_span_start']:candidate['source_span_end']] == candidate['source_text']
    if low is not None:
        assert plan.year_min_exclusive is lower_exclusive
    if high is not None:
        assert plan.year_max_exclusive is upper_exclusive

@pytest.mark.parametrize('query', ['Python 3', 'Windows 11', '1984', 'Catch-22', 'history after 1945', 'books about events between 1940 and 1950', 'history from 2020 onward', 'books about Python 3 and Windows 11', 'books by Four Stars', 'books called Five-Star Memories', 'books about "rating above 4"', 'books about "publication after 2020"', 'books about altitude above 3 and below 5'])
def test_topic_and_entity_numbers_do_not_invent_numeric_filters(query):
    plan = parse_query(query)
    assert all((getattr(plan, field) is None for field in ('rating_min', 'rating_max', 'year_min', 'year_max')))

@pytest.mark.parametrize('query', ['rating above 6', 'rating below -1', 'published after 9999', 'published in 2020.5'])
def test_invalid_domains_are_blocked_without_clamping(query):
    plan = parse_query(query)
    assert not executable(plan)
    assert plan.decision['decision_type'] == 'UNSUPPORTED'

@pytest.mark.parametrize('low,high,lower_exclusive,upper_exclusive,expected', [(4, 4, False, False, False), (4, 4, True, False, True), (4, 4, False, True, True), (4.5, 4.5, True, True, True), (4, 3, False, False, True), (3, 4, True, True, False), (None, 4, True, True, False), (4, None, True, True, False)])
def test_range_boundary_mathematics(low, high, lower_exclusive, upper_exclusive, expected):
    assert range_contradiction(low, high, lower_exclusive, upper_exclusive) is expected

@pytest.mark.parametrize('field,value,expected', [('rating', 0, True), ('rating', 5, True), ('rating', 5.01, False), ('rating', float('nan'), False), ('year', 1000, True), ('year', 2100, True), ('year', 2020.5, False), ('year', 999, False), ('year', True, False)])
def test_numeric_domain(field, value, expected):
    assert valid_numeric_domain(field, value) is expected
