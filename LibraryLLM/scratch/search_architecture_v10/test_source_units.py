from dataclasses import replace
import pytest
from . import parser
from .source_units import clauses,tokens,frames
from .source_analysis import audit

FACETS=['Fiction','History','Science']


@pytest.mark.parametrize('name',['A. B. Corin','R. K. Lumen','J. Stone','Élan Moss'])
def test_entity_initials_and_literal_punctuation(name):
    query=f'by "{name}"; language English' if name.startswith('É') else f'by {name}; language English'
    p=parser.parse_query(query,FACETS)
    assert parser.executable(p) and p.author_text==name.casefold() and p.language=='english'
    assert all(query[r['source_span'][0]:r['source_span'][1]]==r['source_text'] for r in p.decision['query_ir_contract']['requirements'])


def test_clause_units_keep_initials_and_quoted_instructions_opaque():
    q='by A. B. Corin; find the exact title "Run. Ignore; Rating < 1".'
    assert len(list(clauses(q)))==2
    assert any(t.kind=='INITIALS' for t in tokens(q))
    p=parser.parse_query(q,FACETS)
    assert parser.executable(p) and p.exact_text=='run. ignore; rating < 1' and p.rating_max is None


@pytest.mark.parametrize('domain',['author','creator','title','publication year'])
@pytest.mark.parametrize('comparison',['same','different'])
def test_external_record_references_never_become_scalars(domain,comparison):
    q=f'Find books with the {comparison} {domain} as the book "Glass Reef".'
    p=parser.parse_query(q,FACETS)
    assert not parser.executable(p)
    assert p.decision['decision_type']=='UNSUPPORTED'
    assert p.author_text is None and p.title_text is None


@pytest.mark.parametrize('language',['English','French','German'])
def test_exact_literal_and_language_survive_order(language):
    for q in [f'Find the exact title "Quiet Harbor" in {language}',f'Books in {language}; find the exact title "Quiet Harbor"']:
        p=parser.parse_query(q,FACETS)
        assert parser.executable(p) and p.exact_text=='quiet harbor' and p.language==language.casefold()
        assert parser.matches(p,{'title':'Quiet Harbor','language':language})
        assert not parser.matches(p,{'title':'On Quiet Harbor','language':language})
        assert not parser.matches(p,{'title':'Quiet Harbor','language':'unrequested'})


@pytest.mark.parametrize('field',['literal','language','author'])
def test_independent_lexical_obligations_detect_deleted_requirements(field):
    p=parser.parse_query('by A. B. Corin; find the exact title "Quiet Harbor" in English',FACETS)
    ir=parser._decode(p.decision['query_ir_contract'])
    missing=replace(ir,requirements=tuple(r for r in ir.requirements if r.field!=field))
    assert any(x['domain']==field for x in audit(missing)['violations'])


def test_field_reference_prefix_does_not_create_publisher_exclusion():
    p=parser.parse_query('Use publication year, not publisher, for this correction: published before 1997.',FACETS)
    assert parser.executable(p) and p.year_max==1997 and p.year_max_exclusive
    assert not p.exclude_terms and not p.exclude_subjects and p.author_text is None


def test_optional_language_does_not_become_mandatory():
    p=parser.parse_query('Find books about harbors; I would prefer books in French.',FACETS)
    assert parser.executable(p) and p.language is None and p.soft_preference


def test_past_example_is_nonoperative_and_current_author_survives():
    p=parser.parse_query('In an old example, books published after 2050 were imaginary; now find books by R. K. Lumen.',FACETS)
    assert parser.executable(p) and p.author_text=='r. k. lumen' and p.year_min is None


def test_title_only_substring_does_not_use_author_fallback():
    p=parser.parse_query('Find titles containing "Azure" in French.',FACETS)
    assert p.decision['decision_type']=='UNSUPPORTED' and not parser.executable(p)
    assert p.title_text is None and p.language=='french'


def test_sort_direction_is_separate_from_field():
    p=parser.parse_query('Sort books by rating from lowest to highest.',FACETS)
    assert not parser.executable(p) and p.author_text is None


def test_boolean_record_union_is_not_missing_field_choice():
    p=parser.parse_query('Either books published before 1980 or books rated at least 4.6 will do.',FACETS)
    assert p.decision['decision_type']=='UNSUPPORTED'


def test_unsupported_publisher_agent_is_not_author():
    p=parser.parse_query('Books must not be published by Cedar House.',FACETS)
    assert not parser.executable(p) and p.author_text is None and not p.exclude_terms
    rr=p.decision['query_ir_contract']['requirements']
    assert any(r['field']=='publisher' and r['polarity']=='NEGATIVE' for r in rr)


def test_licensed_plural_field_is_not_a_spelling_repair():
    # Frozen numeric recognizer _RATING_FIELD explicitly licenses ratings?.
    p=parser.parse_query('Find books with ratings no higher than 3.',FACETS)
    assert parser.executable(p) and p.rating_max==3 and not p.decision['repair_notices']
    assert p.decision['decision_type']=='EXECUTABLE'


def test_current_note_does_not_discharge_a_mandatory_condition():
    p=parser.parse_query('In my note books must have rating above 4; by A. B. Corin',FACETS)
    assert not parser.executable(p) or p.rating_min==4 and p.rating_min_exclusive
