"""Native predicate, source safety and disabled integration contracts."""
from dataclasses import replace,asdict
import pytest
from .parser import parse_query,validate,executable,PARSER_VERSION
from .capabilities import SCOPES,mask
from .orchestrator import ScopeContext,SmartSearchOrchestrator,ReadOnlyNativeAdapter,ProviderFailure
from .completion import BoundContext
from .contract import digest
from .refinement_workflow import add_filter


@pytest.mark.parametrize('prefix',['Find a title containing the words','title containing','title-only containing'])
def test_reviewed_title_only_migration(prefix):
    p=parse_query(prefix+' "available online"')
    assert not executable(p) and p.decision['decision_type']=='UNSUPPORTED'
    assert not p.formats and not p.availability
    from search.query_plan import matches
    assert not matches(p,dict(title='Different title',authors=['available online']))


def test_native_title_strengths_are_distinct():
    from search.query_plan import QueryPlan,matches
    title=QueryPlan('River','TITLE_AUTHOR');title.title_text='river'
    assert matches(title,dict(title='Other',authors=['River Writer']))
    exact=QueryPlan('Quiet River','EXACT');exact.exact_text='Quiet River'
    assert matches(exact,dict(title=' quiet  river ',authors=['Other']))
    assert not matches(exact,dict(title='Other',authors=['Quiet River']))


@pytest.mark.parametrize('query',[
 'Mystery or Romance? Choose later.','Fiction rated 4: minimum or maximum?',
 'Physics after 2020 and before 2020','Require and exclude the Mystery category',
 'Require both online and physical access. No returned record may offer physical access.',
 'books about biology; under 100 pages','books about biology; price under $10'])
def test_development_safety_families_do_not_execute(query):
    assert not executable(parse_query(query,['Mystery','Romance','Fiction','Physics']))


@pytest.mark.parametrize('query',['books for learning Java','historical mysteries','beginner Python books',
 'books about history after 1945','free-to-borrow books about gardening','books about the history of publishing'])
def test_ordinary_semantics_without_invented_numeric_filters(query):
    p=parse_query(query)
    assert executable(p) and p.semantic_text
    assert p.year_min is None and p.rating_min is None and not p.author_text
    assert p.decision['query_intent']['source_digest']==digest(query)


def context(scope):
    return ScopeContext(scope,'2','fixture-session',None if scope=='GLOBAL' else 'library-a','membership-v1',scope.endswith('_STAFF'))


def adapter(ctx,*,foreign=False,provider_error=False,serialize_bad=False):
    records=[dict(work_id='w1',library_book_id='l1',library_id='library-a',title='Ecology primer',authors=['Ada Researcher'],
                  subjects=['Biology'],average_rating=4.5,rating_count=2,language='spanish',publication_year=2020,has_online=True,has_physical=False),
             dict(work_id='w2',library_book_id='l2',library_id='library-a',title='Ecology workbook',authors=['Other'],
                  subjects=['Biology'],average_rating=2.5,rating_count=2,language='english',publication_year=2010,has_online=False,has_physical=True)]
    if foreign:records[0]['library_id']='foreign-library'
    calls=[]
    def retrieve(**kw):
        calls.append(kw)
        if provider_error:raise OSError('index unavailable')
        return [r['work_id'] if ctx.scope=='GLOBAL' else r['library_book_id'] for r in records]
    def serialize(**kw):
        rows=kw['rows']
        if serialize_bad and rows:rows[0]['average_rating']=1
        return rows
    obj=ReadOnlyNativeAdapter(authorize=lambda c:c==ctx,retrieve=retrieve,
        hydrate=lambda **kw:records,serialize=serialize,entitlements=lambda c:{'w1'})
    return obj,calls


@pytest.mark.parametrize('scope',SCOPES)
def test_scope_transport_filter_hydration_pagination(scope):
    ctx=context(scope);a,calls=adapter(ctx);o=SmartSearchOrchestrator(a,fixture_enabled=True)
    r=o.search('beginner books about ecology; rating above 4; online format',ctx,limit=1)
    assert len(r['results'])==1 and r['results'][0]['title']=='Ecology primer'
    assert not r['has_more'] and r['completeness']=='BOUNDED_CANDIDATE_SET_ONLY'
    assert calls[0]['context']==ctx and 'ecology' in calls[0]['semantic_text']
    assert 'beginner' in calls[0]['semantic_text']
    r=o.search('books about ecology; rating above 4; online format',ctx,offset=1,limit=1)
    assert r['results']==[]


def test_global_negative_online_entitlement_is_computed():
    ctx=context('GLOBAL');a,calls=adapter(ctx)
    r=SmartSearchOrchestrator(a,fixture_enabled=True).search('books about ecology; exclude online format',ctx)
    assert [x['work_id'] for x in r['results']]==['w2']


@pytest.mark.parametrize('scope',SCOPES[1:])
def test_foreign_hydration_fails_closed(scope):
    ctx=context(scope);a,_=adapter(ctx,foreign=True)
    with pytest.raises(ProviderFailure):SmartSearchOrchestrator(a,fixture_enabled=True).search('books about ecology',ctx)


@pytest.mark.parametrize('option',['provider_error','serialize_bad'])
def test_errors_never_return_broader_results(option):
    ctx=context('GLOBAL');a,_=adapter(ctx,**{option:True})
    with pytest.raises(ProviderFailure):SmartSearchOrchestrator(a,fixture_enabled=True).search('books about ecology; rating above 4',ctx)


def test_disabled_default_and_clarification_never_call_retrieval():
    ctx=context('GLOBAL');a,calls=adapter(ctx)
    with pytest.raises(RuntimeError):SmartSearchOrchestrator(a).search('ecology',ctx)
    o=SmartSearchOrchestrator(a,fixture_enabled=True)
    for q,kind in [('books about ecology; by [author]','INCOMPLETE'),('books about ecology; under 80 pages','UNSUPPORTED')]:
        r=o.search(q,ctx);assert r['decision']==kind and r['results']==[]
    assert not calls


def test_refinement_preserves_source_and_binding():
    p=validate(parse_query('books about ecology; rating above 4'),mask('GLOBAL'))
    c=BoundContext('2','session',None,'GLOBAL',PARSER_VERSION,'SMART',digest(p.raw_query),1,100)
    r=add_filter(p,'author','Ada Researcher',c,c,now=1,facets=(),capabilities=mask('GLOBAL'),authorized=True)
    assert r.plan.rating_min==4 and r.plan.rating_min_exclusive and r.plan.author_text=='ada researcher'
    assert r.original_query==p.raw_query and r.accepted_plan_version==2 and not r.durable
    for other in [replace(c,owner='foreign'),replace(c,used=True),replace(c,base_version=2)]:
        with pytest.raises(ValueError):add_filter(p,'format','ONLINE',c,other,now=1,facets=(),capabilities=mask('GLOBAL'),authorized=True)


def test_empty_objective_and_explicit_reset_remain_distinct():
    from .refinement import refine
    empty=parse_query('')
    assert not executable(empty)
    assert empty.decision['query_intent']['source_digest']==digest('')
    p=validate(parse_query('books about ecology; rating at least 4'))
    reset,continued=refine(p,'start over',())
    assert executable(validate(reset)) and not continued and reset.rating_min is None


@pytest.mark.parametrize('low,high',[(0,5),(3.1,4.7),(4,4)])
def test_source_owned_rating_range_is_not_an_unknown_second_number(low,high):
    p=parse_query(f'books rated {low} to {high}')
    assert executable(p) and p.rating_min==low and p.rating_max==high
    from search.query_plan import matches
    assert matches(p,dict(average_rating=(low+high)/2,rating_count=1))
    assert not matches(p,dict(average_rating=high+.01,rating_count=1))


@pytest.mark.parametrize('query',['A Quiet River','9781234567890','rating above 4','switch library'])
def test_exact_projection_unchanged(query):
    from scratch.search_architecture_v9.parser import parse_query as previous
    from .proof import projection
    old=previous(query,mode='EXACT');new=parse_query(query,mode='EXACT')
    assert projection(old)==projection(new) and old.semantic_text==new.semantic_text
