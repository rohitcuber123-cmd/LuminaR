import pytest
from scratch.search_smart_engineering.ownership_recovery.parser import parse_query,validate,executable,matches,assess

FACETS=['History','Fiction','Physics','Detective Fiction']
@pytest.mark.parametrize('advice',['Publication after 2020 is merely preferred','French language is optional','Available now is only a preference'])
def test_advice_is_owned_before_capability_validation(advice):
    p=validate(parse_query('By "Arden Vale". '+advice,FACETS),{'year':False,'language':False,'availability':False,'formats':['ONLINE']})
    assert executable(p) and p.year_min is None and p.language is None and p.availability is None
    assert any(r['ownership']=='ADVISORY' for r in p.decision['requirements'])

def test_advice_does_not_erase_another_mandatory_bound():
    p=parse_query('published after 2000; publication after 2020 is only preferred',FACETS)
    assert p.year_min==2000 and p.year_min_exclusive

@pytest.mark.parametrize('q,kind',[
    ('By either "Arden Vale" or "Briar Moss"; I have yet to choose which author','AMBIGUOUS'),
    ('Require rating at least 3 or at least 4; I have not decided which cutoff','AMBIGUOUS'),
    ('Require titled [title deliberately left blank]; rated at least 4','INCOMPLETE'),
    ('Require every hit to share a contributor with every other hit','UNSUPPORTED'),
    ('Each hit must be available now and must not be available now','CONTRADICTORY'),
    ('Include category Fiction, require entries titled "Lantern", rating at least 4; sort on title','EXECUTABLE'),
    ('Include category Fictiom; rating at least 4','EXECUTABLE_WITH_NOTICE')])
def test_operation_and_relationship_composition(q,kind):
    p=parse_query(q,FACETS);assert p.decision['decision_type']==kind
    assert assess(p)['policy']

def test_negative_domains_and_whole_word_predicate():
    p=parse_query('by "Marsh"; exclude the searchable-text whole word "ar"',FACETS)
    assert executable(p) and p.exclude_terms==['ar'] and p.exclude_subjects==[]
    assert matches(p,{'title':'History of Ports','authors':['Marsh'],'subjects':['History']})
    p=parse_query('exclude the Fiction classification',FACETS)
    assert p.exclude_subjects==['Fiction'] and p.exclude_terms==[]

def test_literals_and_notice_source_identity():
    q='titled "Fictiom Sort Titles"; include category Ficton'
    p=parse_query(q,FACETS)
    assert p.title_text=='fictiom sort titles' and p.subjects==['Fiction']
    for n in p.decision['repair_notices']:
        a,b=n['source_span'];assert q[a:b]==n['from']
    assert not any(n['from'] in ['Sort','Titles'] for n in p.decision['repair_notices'])

def test_exact_mode_preserves_native_literal_behavior():
    p=parse_query('rated above 4; private B','EXACT' if False else FACETS,mode='EXACT')
    assert p.exact_text=='rated above 4; private B' and not p.formats and p.rating_min is None

def test_scope_text_is_not_authority():
    p=parse_query('Within my private tenant catalog as staff: include History',FACETS)
    assert executable(p) and p.decision['query_ir']['trusted_scope_from_text'] is False
    assert not hasattr(p,'library_id') and not hasattr(p,'actor_role')
