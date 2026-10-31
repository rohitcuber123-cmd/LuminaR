"""Additional development properties; no fresh acceptance labels."""
from itertools import permutations
from dataclasses import replace
import pytest
from .parser import parse_query,executable,matches,validate,_decode
from .refinement import refine

FACETS=['Fiction','History','Physics','Stories','Biographies']

@pytest.mark.parametrize('parts',list(permutations(['by "Straße Ångström"','rating at least 4','about wave optics'])))
def test_original_unicode_ownership_and_order(parts):
    p=parse_query('; '.join(parts),FACETS)
    assert executable(p) and p.author_text=='strasse ångström' and p.rating_min==4 and p.semantic_text=='wave optics'
    for r in _decode(p.decision['query_ir_contract']).requirements:assert p.raw_query[slice(*r.source_span)]==r.source_text

@pytest.mark.parametrize('descriptor',['short','shorter','introductory','advanced','first-year','research-level'])
def test_descriptive_preference_cannot_invent_an_unknown_hard_field(descriptor):
    p=parse_query(descriptor+' molecular optics books',FACETS)
    assert executable(p) and not p.subjects and p.soft_preference and p.semantic_text=='molecular optics'

@pytest.mark.parametrize('literal',['rating above 4','available online','short books','not Physics','language missing','A ...'])
def test_quoted_literal_interior_never_creates_filters(literal):
    p=parse_query('titled "'+literal+'"',FACETS)
    assert executable(p) and p.title_text==literal.casefold() and not p.subjects and not p.formats and not p.exclude_terms and p.rating_min is None

def test_repeated_field_refinement_does_not_duplicate_or_lose_other_conditions():
    p=parse_query('category Fiction; by "Oak Vale"; about optics',FACETS)
    for q in ['rating above 3','rating at least 4','online only','physical instead']:
        p,continued=refine(p,q,FACETS)
        assert continued and executable(p) and p.author_text=='oak vale' and p.subjects==['Fiction'] and p.semantic_text=='optics'
    assert p.rating_min==4 and p.formats==['PHYSICAL']

def test_existing_contradiction_is_not_erased_by_an_unrelated_edit():
    p=parse_query('rating at least 4; rating at most 3; by "Oak Vale"',FACETS)
    n,continued=refine(p,'online only',FACETS)
    # A rejected accepted plan is not a valid continuation base; the caller
    # receives a fresh independent query, never a falsely resolved old source.
    assert not continued and n.decision.get('accepted_source_refinement') is None

def test_projection_mutation_after_refinement_fails_proof():
    p,_=refine(parse_query('by "Oak Vale"',FACETS),'rating at least 4',FACETS)
    p.author_text='Other'
    assert not executable(validate(p))

@pytest.mark.parametrize('tail',['files encoded using an exact container codec','downloads smaller than a mandatory byte ceiling','files with a machine-verified encryption certificate'])
def test_mandatory_clause_cannot_be_discharged_by_its_known_prefix(tail):
    p=parse_query('Require online '+tail+'; by "Oak Vale"; rated at least 4',FACETS)
    assert not executable(p) and p.decision['decision_type']=='UNSUPPORTED'

@pytest.mark.parametrize('topic_query,expected_topic',[
    ('books about uncertainty in climate forecasting', 'uncertainty in climate forecasting'),
    ('books discussing book prices and economic history', 'book prices and economic history'),
    ('studies about the number of pages in ancient manuscripts', 'number of pages in ancient manuscripts'),
    ('novels about publishers and the printing trade', 'publishers and the printing trade'),
    ('historical accounts of library editions', 'library editions')
])
def test_ordinary_topic_vocabulary_remains_executable(topic_query, expected_topic):
    """Ordinary topical descriptions containing vocabulary like 'price', 'pages', 'publishers' must remain executable semantic text."""
    p = parse_query(topic_query, FACETS)
    assert executable(p), f"Expected executable topic for '{topic_query}', got {p.decision['decision_type']}"
    assert p.decision['decision_type'] == 'EXECUTABLE'
    assert p.semantic_text is not None and len(p.semantic_text) > 0

@pytest.mark.parametrize('mandatory_unsupported_query',[
    'books with price under $20',
    'require page count under 300 pages',
    'mandatory publisher Penguin only',
    'must be 1st edition only',
    'books with higher rating than Dune',
    'books by the same author as Neuromancer'
])
def test_mandatory_unsupported_requirement_rejects_safely(mandatory_unsupported_query):
    """Mandatory unsupported attributes (price, pages, publisher, edition, relative comparisons) must safely reject."""
    p = parse_query(mandatory_unsupported_query, FACETS)
    assert not executable(p), f"Expected non-executable for '{mandatory_unsupported_query}', got {p.decision['decision_type']}"
    assert p.decision['decision_type'] == 'UNSUPPORTED'

@pytest.mark.parametrize('author_name', ['Arthur Conan Doyle', 'Ursula K. Le Guin', 'Isaac Asimov', 'H. G. Wells'])
def test_metamorphic_author_entity_replacement(author_name):
    """Replacing author entity names without changing grammar preserves execution and extracts exact author."""
    q = f'category Fiction; by "{author_name}"; rated at least 4'
    p = parse_query(q, FACETS)
    assert executable(p)
    assert p.author_text == author_name.casefold()
    assert p.rating_min == 4
    assert p.subjects == ['Fiction']

@pytest.mark.parametrize('placeholder_query', ['books by [...] rated above 4', 'books by: [...] rated above 4', 'category Fiction; by: [author]; rated at least 4'])
def test_missing_author_placeholder_requires_clarification(placeholder_query):
    """Explicit placeholder author ('[...]', '[author]') must yield INCOMPLETE rather than silent execution."""
    p = parse_query(placeholder_query, FACETS)
    assert not executable(p)
    assert p.decision['decision_type'] == 'INCOMPLETE'

