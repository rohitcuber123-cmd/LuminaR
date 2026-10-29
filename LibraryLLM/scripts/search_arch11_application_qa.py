"""Exposed application QA through actual ASGI routes with mocked authority/data.

No live app initialization, Mongo operations, models or sealed material. Source
policy migrations are declared by the source-only review, never fitted to scores.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import importlib.util,json,sys,time,math,statistics
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('v11_fixture',ROOT/'tests/test_search_arch11_integration.py');fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
from scripts.search_combined8_score_adapter import score
from scripts.search_v2c_c5er_evaluation_adapter_v2 import summary
R=ROOT/'reports'
def lines(name):return [json.loads(s) for s in (R/name).read_text(encoding='utf8').splitlines()]
def measured(n,d,pop):return dict(numerator=n,denominator=d,population=pop,evidence='EXPOSED_DEVELOPMENT',integration='ASGI_HTTP_NATIVE_EXECUTION_WITH_MOCK_AUTHORITY_AND_COLLECTIONS',status='MEASURED')
def latency(values,pop):
    a=sorted(values)
    return dict(samples=len(a),p50_ms=statistics.median(a),p95_ms=a[math.ceil(.95*len(a))-1],population=pop,status='MEASURED_MOCK_HTTP_IN_PROCESS')


def capture(a,g,realistic=False):
    scope=g['scope'] if realistic else g['scope_type'];query=g['query_text'];mode=g['mode'] if realistic else g['search_mode']
    body=dict(query=query,mode=mode)
    if scope!='GLOBAL':body.update(library_id=fixture.LID,staff=scope.endswith('_STAFF'))
    started=time.perf_counter();response=a.client.post('/query/preview',json=body);elapsed=(time.perf_counter()-started)*1000
    if response.status_code!=200:
        return dict(case_id=g['case_id'],status='ERROR',typed_decision='UNSUPPORTED',executable=False,actual_plan=None,http_status=response.status_code,elapsed_ms=elapsed,error=response.json())
    result=response.json();state=result['preview'];plan=a.store.rows[state['state_id']]['plan']
    return dict(case_id=g['case_id'],status='CAPTURED',typed_decision=state['decision'],executable=state['decision'].startswith('EXECUTABLE'),
        actual_plan=plan,http_status=200,elapsed_ms=elapsed,returned=len(result['results']),coverage=result.get('coverage'),accepted_source=state['accepted_query'])


def realistic():
    gold=lines('search_arch10_realistic_reviewed_r1.jsonl');predictions=[];results=[]
    defaults=dict(subjects=[],include_terms=[],exclude_subjects=[],exclude_terms=[],formats=[],exclusive_formats=[],excluded_formats=[],author_text=None,
        title_text=None,exact_text=None,rating_min=None,rating_max=None,rating_min_exclusive=False,rating_max_exclusive=False,year_min=None,year_max=None,
        year_min_exclusive=False,year_max_exclusive=False,language=None,availability=None,physical_available_only=False,sort='RELEVANCE')
    with pytest.MonkeyPatch.context() as mp:
        a=fixture.application.__wrapped__(mp)
        a.collection.database.book_categories.rows=[dict(name=x,count=3) for x in ['Biology','Mystery','Romance','Physics','Fiction']]
        for g in gold:
            p=capture(a,g,True);predictions.append(p)
            expected='UNSUPPORTED' if g['family']=='missing_unsupported_operand' else g['expected_decision']
            expected_exec=expected.startswith('EXECUTABLE');errors={}
            if p['executable']:
                for k,v in {**defaults,**g['fields']}.items():
                    actual=p['actual_plan'][k]
                    same=actual.casefold()==v.casefold() if isinstance(actual,str) and isinstance(v,str) else actual==v
                    if not same:errors[k]=dict(expected=v,actual=actual)
            results.append(dict(case_id=g['case_id'],family=g['family'],scope=g['scope'],complexity=g['complexity'],length=g['length_bucket'],
                expected_decision=expected,original_v10_decision=g['expected_decision'],actual_decision=p['typed_decision'],
                typed_correct=p['status']=='CAPTURED' and p['typed_decision']==expected,execution_correct=p['status']=='CAPTURED' and p['executable']==expected_exec,
                expected_execution=expected_exec,execution=p['executable'],hard_mismatches=errors,http_status=p['http_status']))
    def metrics(rows,pop):
        return dict(typed=measured(sum(r['typed_correct'] for r in rows),len(rows),pop),
            execution=measured(sum(r['execution_correct'] for r in rows),len(rows),pop),
            false_execution=measured(sum(r['execution'] and not r['expected_execution'] for r in rows),sum(not r['expected_execution'] for r in rows),pop+' expected blocked'),
            missed_valid=measured(sum(not r['execution'] and r['expected_execution'] for r in rows),sum(r['expected_execution'] for r in rows),pop+' expected valid'),
            hard_field_mismatch_cases=measured(sum(bool(r['hard_mismatches']) for r in rows),sum(r['execution'] for r in rows),pop+' currently executed'))
    return dict(population='235 exposed realistic contexts, 47 authored families',summary=metrics(results,'realistic ASGI development235'),
        strata={k:{v:metrics([r for r in results if r[k]==v],k+'='+v) for v in sorted({r[k] for r in results})} for k in ['scope','complexity','length']},
        source_only_policy_migrations=['Missing page-count operand: UNSUPPORTED capability-first, 5 contexts. Missing state retained; no completion can enable it.'],
        review='reports/search_arch11_contract_review.json',predictions=predictions,results=results,
        failures=[r for r in results if not r['typed_correct'] or not r['execution_correct'] or r['hard_mismatches']],
        latency=latency([p['elapsed_ms'] for p in predictions],'realistic235 in-process ASGI requests; mocked services'))


def historical(name,path):
    gold=lines(path);predictions=[]
    caps=json.loads((R/'search_v2c_c5a_capability_matrix.json').read_text())['scopes']
    with pytest.MonkeyPatch.context() as mp:
        a=fixture.application.__wrapped__(mp)
        for g in gold:
            a.collection.database.book_categories.rows=[dict(name=x,count=3) for x in caps[g['scope_type']]['subjects']]
            predictions.append(capture(a,g))
    results=[score(g,p) for g,p in zip(gold,predictions)]
    return dict(population=name,evidence='EXPOSED_DEVELOPMENT_RAW_HISTORICAL_MASKS_UNEDITED',integration='ACTUAL_ASGI_HTTP_NATIVE_FUNCTIONS_MOCK_AUTHORITY_AND_DATA',
        summary=summary(results),critical_field_cases=[r for r in results if r['critical_executed_operand_mismatches']],
        predictions=predictions,results=results,latency=latency([p['elapsed_ms'] for p in predictions],name+' in-process ASGI mock services'))


def performance():
    with pytest.MonkeyPatch.context() as mp:
        a=fixture.application.__wrapped__(mp)
        queries=['books about biology','books about biology; rating above 4; online format','books about biology; by [author]']
        observations=[]
        for mode in ['SMART','EXACT']:
            for q in queries:
                for i in range(6):
                    started=time.perf_counter();r=fixture.search(a,q,mode=mode);elapsed=(time.perf_counter()-started)*1000
                    observations.append(dict(mode=mode,query=q,condition='first_context' if i==0 else 'warm_process',elapsed_ms=elapsed,status=r.status_code))
        def worker(i):
            started=time.perf_counter();r=fixture.search(a,'books about biology; rating above 4');return (time.perf_counter()-started)*1000,r.status_code
        with ThreadPoolExecutor(max_workers=4) as pool:concurrent=list(pool.map(worker,range(24)))
    return dict(layer='MOCK_DEPENDENCY_APPLICATION_HTTP_NOT_LIVE_FULL_SERVICE',observations=observations,
        first_context=latency([r['elapsed_ms'] for r in observations if r['condition']=='first_context'],'6 first query contexts; process already initialized'),
        warm=latency([r['elapsed_ms'] for r in observations if r['condition']=='warm_process'],'30 warm-process ASGI contexts'),
        concurrency=dict(workers=4,**latency([r[0] for r in concurrent],'24 mock HTTP searches at four workers')),
        unexpected_http_errors=measured(sum(r['status']!=200 for r in observations)+sum(s!=200 for _,s in concurrent),len(observations)+len(concurrent),'mock HTTP performance requests'),
        full_live_api='NOT_MEASURED',real_embedding_latency='NO_NEW_MODEL_INFERENCE; V10 cold/warm evidence not relabeled',production_slo='NOT_SET')


def main():
    r=realistic();d=historical('V9 dev72','search_arch9_dev_reviewed.jsonl');e=historical('V8 exposed205','search_combined8_reviewed_population_r1.jsonl');p=performance()
    report=dict(status='DEVELOPMENT_COMPLETE_NOT_INDEPENDENT_ACCEPTANCE',realistic=r,dev72=d,v8_exposed205=e,performance=p,
        fresh_acceptance_performed=False,real_relevance='NOT_QUALIFIED_NO_INDEPENDENT_JUDGMENTS',real_jwt=False,live_mongo=False)
    tag=sys.argv[1] if len(sys.argv)>1 else ''
    assert not tag or tag.isalnum()
    with (R/('search_arch11_application_qa'+('_'+tag if tag else '')+'.json')).open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(dict(realistic=r['summary'],dev72=d['summary'],v8_exposed205=e['summary'],performance=p['warm'])))

if __name__=='__main__':main()
