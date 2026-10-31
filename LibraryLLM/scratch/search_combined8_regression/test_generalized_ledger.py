import pytest
from scratch.search_proof_recovery_v8.parser import parse_query,matches
from scratch.search_proof_recovery_v8.parser import executable,validate
FACETS=['History','Physics','Fiction','Detective Fiction']

@pytest.mark.parametrize('q,kind',[
 ('by "Aster Vale"; a required author slot is empty','INCOMPLETE'),
 ('the mandatory rating box is empty; include History','INCOMPLETE'),
 ('by [empty required creator value]; online only','INCOMPLETE'),
 ('category "History" must be chosen between "History" and "Physics"; that choice remains undecided','AMBIGUOUS'),
 ('the exclusion instruction has unsettled status: mandatory or advisory, choice pending; online only','AMBIGUOUS'),
 ('admit works only when their author has an average rating of at least 4 across all works','UNSUPPORTED'),
 ('exclude a work when two terms occur within 3 words; this proximity condition is strict','UNSUPPORTED'),
 ('include a match of the whole word "map"; exclude the whole word "map"','CONTRADICTORY'),
 ('by "Aster Vale"; titled exactly "An Amber Ledger"; category "History"; online only','EXECUTABLE'),
 ('include subject "Detectve Fiction"; prefer short works','EXECUTABLE_WITH_NOTICE')])
def test_generalized_requirements(q,kind):assert parse_query(q,FACETS).decision['decision_type']==kind

def test_advisory_author_does_not_authorize_hard_author():
    p=parse_query('prefer by "Aster Vale"; include History',FACETS)
    assert executable(p) and p.author_text is None and p.subjects==['History']

def test_advice_after_author_does_not_erase_author():
    p=parse_query('by "Aster Vale", advanced explanations are optional',FACETS)
    assert executable(p) and p.author_text=='aster vale' and p.soft_preference

@pytest.mark.parametrize('q',['sort titles A to Z','sort by title','titled "Sort Titles"; prefer short works'])
def test_legitimate_grammar_is_not_repaired(q):
    p=parse_query(q,FACETS)
    assert executable(p) and not p.decision.get('repair_notices')

def test_whole_word_and_literal_boundary():
    p=parse_query('by "Marsh"; exclude the whole word "ar"',FACETS)
    assert executable(p) and matches(p,{'title':'A Book','authors':['Marsh']})
    p=parse_query('titled "Online: A. Ledger". by "Aster Vale". include History',FACETS)
    assert p.title_text=='online: a. ledger' and p.author_text=='aster vale' and p.formats==[]

def test_ledger_source_and_owner_offsets():
    q='online onyl; prefer beginner explanations; by "Aster Vale"'
    p=parse_query(q,FACETS)
    for r in p.decision['requirements']:
        a,b=r['source_span'];x,y=r['owning_clause_span']
        assert q[a:b]==r['source_text'] and q[x:y]==r['owning_clause'] and x<=a<=b<=y
