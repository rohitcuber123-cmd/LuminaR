"""V2C-B admission probes use independent expected labels, not parser-derived labels."""
import json
from pathlib import Path

import pytest

from search.query_plan import parse_query

FACETS = [row['subject'] for row in json.loads(
    (Path(__file__).resolve().parents[1] / 'reports/search_v2a_facet_vocabulary.json').read_text(encoding='utf8'))['results']]


@pytest.mark.parametrize('query,expected', [
    ('fiction books above rating of 3', 'EXECUTABLE'),
    ('fiction about wizards above rating of 3', 'EXECUTABLE'),
    ('fiction 4', 'AMBIGUOUS'),
    ('books rated above 4 and below 3', 'CONTRADICTORY'),
    ('after 2020 before 2000', 'CONTRADICTORY'),
    ('online only and physical only', 'CONTRADICTORY'),
    ('fiction rating above', 'INCOMPLETE'),
    ('include romance but exclude romance', 'CONTRADICTORY'),
])
def test_v2c_b_parser_admission(query, expected):
    plan = parse_query(query, FACETS)
    assert plan.decision['decision_type'] == expected
    if query == 'fiction books above rating of 3':
        assert plan.subjects == ['Fiction']
        assert plan.rating_min == 3 and plan.rating_min_exclusive
        assert plan.semantic_text is None
    if query == 'fiction about wizards above rating of 3':
        assert plan.subjects == ['Fiction']
        assert plan.rating_min == 3 and plan.rating_min_exclusive
        assert plan.semantic_text == 'wizards'
