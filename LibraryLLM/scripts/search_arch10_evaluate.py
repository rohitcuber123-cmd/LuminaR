"""Reviewed exposed development scoring. No acceptance or heldout access."""
from pathlib import Path
from dataclasses import asdict
from collections import Counter
import json,sys,time,math,statistics,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scratch.search_architecture_v10 import parser
from scratch.search_architecture_v10.capabilities import mask
from scripts.search_combined8_score_adapter import score
from scripts.search_v2c_c5er_evaluation_adapter_v2 import summary

R=Path('reports')
def write(name,obj):
    with (R/name).open('x',encoding='utf8') as f:json.dump(obj,f,indent=2,ensure_ascii=False)
def metric(n,d,population):return dict(numerator=n,denominator=d,population=population,status='MEASURED',evidence='EXPOSED_DEVELOPMENT')
def lines(path):return [json.loads(x) for x in Path(path).read_text(encoding='utf8').splitlines()]
def capture(q,facets,mode,caps):
    start=time.perf_counter();p=parser.validate(parser.parse_query(q,facets,mode),caps)
    return dict(status='CAPTURED',typed_decision=p.decision['decision_type'],executable=parser.executable(p),
                actual_plan=asdict(p),elapsed_ms=(time.perf_counter()-start)*1000)


def historical(name,gold_path):
    gold=lines(R/gold_path);scopes=json.loads((R/'search_v2c_c5a_capability_matrix.json').read_text())['scopes']
    predictions=[]
    for g in gold:
        c=scopes[g['scope_type']];p=capture(g['query_text'],c['subjects'],g['search_mode'],c['capabilities']);p['case_id']=g['case_id'];predictions.append(p)
    results=[score(g,p) for g,p in zip(gold,predictions)]
    report=dict(population=name,summary=summary(results),evidence='EXPOSED_DEVELOPMENT_NOT_ACCEPTANCE',
        linguistic_families=len({g.get('shared_semantic_pattern_id') or g.get('family_id') for g in gold}),
        false_executions=[r for r in results if not r['expected_execution'] and r['execution']],
        hard_mismatches=[r for r in results if r['critical_executed_operand_mismatches']],
        misses=[r for r in results if r['expected_execution'] and not r['execution']],results=results,
        parser_ms=dict(p50=statistics.median(p['elapsed_ms'] for p in predictions),p95=sorted(p['elapsed_ms'] for p in predictions)[math.ceil(.95*len(predictions))-1]))
    write(name+'_results.json',report)
    with (R/(name+'_predictions.jsonl')).open('x',encoding='utf8') as f:
        for p in predictions:f.write(json.dumps(p,ensure_ascii=False)+'\n')
    print(name,json.dumps(report['summary']))


def reviewed_population():
    authored=lines(R/'search_arch10_realistic_development.jsonl');reviewed=[]
    # The source-only review was completed before these predictions. Preserve
    # authored evidence, create a versioned reconciliation; never relabel to fit.
    for g in authored:
        g['fields']=dict(g['fields'])
        if g['family']=='long_research_request':g['fields']['rating_min_exclusive']=True
        g['review']='SOURCE_ONLY_SEPARATE_AGENT_REVIEWED_WITH_RECONCILIATION'
        g['native_support_condition']='ISOLATED_ENTITLEMENT_ADAPTER_REQUIRED' if g['family']=='negative_format' and g['scope']=='GLOBAL' else 'REGISTRY_V2'
        reviewed.append(g)
    path=R/'search_arch10_realistic_reviewed_r1.jsonl'
    with path.open('x',encoding='utf8') as f:
        for g in reviewed:f.write(json.dumps(g,ensure_ascii=False)+'\n')
    write('search_arch10_label_reconciliation.json',dict(
        reviewed_input='reports/search_arch10_development_label_review.json',population=str(path),
        applied=['046_* strict rating >3.5 field corrected before scoring','Full absence masks for otherwise unasserted hard fields',
          'Semantic oracle includes source advisory text transported by adapter','Global negative ONLINE requires tested isolated adapter',
          'Missing pages INCOMPLETE frozen as operand-first choice; completed page constraints UNSUPPORTED'],
        limits=['No independent book relevance oracle','Only two long query templates','Refinement covered separately by executable contract tests',
                '47 template families is authored taxonomy, not independently measured semantic family equivalence'],
        thresholds_changed_after_scoring=False,independent_acceptance=False))
    return reviewed


def realistic(tag=''):
    gold=lines(R/'search_arch10_realistic_reviewed_r1.jsonl') if (R/'search_arch10_realistic_reviewed_r1.jsonl').exists() else reviewed_population();results=[];predictions=[]
    hard_defaults=dict(subjects=[],include_terms=[],exclude_subjects=[],exclude_terms=[],formats=[],exclusive_formats=[],excluded_formats=[],
        author_text=None,title_text=None,exact_text=None,rating_min=None,rating_max=None,rating_min_exclusive=False,rating_max_exclusive=False,
        year_min=None,year_max=None,year_min_exclusive=False,year_max_exclusive=False,language=None,availability=None,physical_available_only=False,sort='RELEVANCE')
    for g in gold:
        p=capture(g['query_text'],['Biology','Mystery','Romance','Physics','Fiction'],g['mode'],mask(g['scope']))
        p['case_id']=g['case_id'];predictions.append(p)
        plan=p['actual_plan'];expected={**hard_defaults,**g['fields']};errors={}
        # Blocked plans are never execution payloads. Keep IR separately for
        # missing/unsupported operand tests; do not score dropped native fields
        # as runtime predicate loss when no execution occurs.
        if p['executable']:
            for k,v in expected.items():
                got=plan[k]
                equal=got.casefold()==v.casefold() if isinstance(got,str) and isinstance(v,str) else got==v
                if not equal:errors[k]=dict(expected=v,actual=got)
        text='; '.join([str(plan.get('semantic_text') or ''),*[r['source_text'] for r in plan['decision'].get('query_ir_contract',{}).get('requirements',[]) if r['ownership']=='ADVISORY']]).casefold()
        missing=[w for w in g['semantic_contains'] if w.casefold() not in text] if p['executable'] else []
        expected_exec=g['expected_decision'] in ('EXECUTABLE','EXECUTABLE_WITH_NOTICE')
        r=dict(case_id=g['case_id'],family=g['family'],scope=g['scope'],complexity=g['complexity'],length_bucket=g['length_bucket'],
               expected_decision=g['expected_decision'],actual_decision=p['typed_decision'],expected_execution=expected_exec,execution=p['executable'],
               typed_correct=p['typed_decision']==g['expected_decision'],execution_correct=p['executable']==expected_exec,
               hard_field_mismatches=errors,semantic_missing=missing,elapsed_ms=p['elapsed_ms'])
        results.append(r)
    def metrics(rows,label):
        n=len(rows);blocked=sum(not r['expected_execution'] for r in rows);valid=n-blocked;executed=sum(r['execution'] for r in rows)
        return dict(contexts=n,typed=metric(sum(r['typed_correct'] for r in rows),n,label),
            execution=metric(sum(r['execution_correct'] for r in rows),n,label),
            false_execution=metric(sum(r['execution'] and not r['expected_execution'] for r in rows),blocked,label+' expected nonexecuting'),
            missed_valid=metric(sum(not r['execution'] and r['expected_execution'] for r in rows),valid,label+' expected executing'),
            hard_field_mismatch_cases=metric(sum(bool(r['hard_field_mismatches']) for r in rows),executed,label+' executed plans'),
            semantic_preserved=metric(sum(not r['semantic_missing'] for r in rows if r['execution']),executed,label+' executed plans; token/advisory transport oracle only'))
    report=dict(evidence='EXPOSED_REVIEWED_DEVELOPMENT_NOT_INDEPENDENT_ACCEPTANCE',summary=metrics(results,'realistic V10 development'),
        distinct_authored_linguistic_families=len({g['family'] for g in gold}),
        strata={key:{value:metrics([r for r in results if r[key]==value],key+'='+value) for value in sorted({r[key] for r in results})}
                for key in ['scope','length_bucket','complexity','expected_decision']},
        failures=[r for r in results if not r['typed_correct'] or not r['execution_correct'] or r['hard_field_mismatches'] or r['semantic_missing']],
        latency=dict(p50=statistics.median(p['elapsed_ms'] for p in predictions),p95=sorted(p['elapsed_ms'] for p in predictions)[math.ceil(.95*len(predictions))-1]),
        relevance='UNVERIFIED_NO_REAL_BOOK_ORACLE',full_search_latency='UNMEASURED',results=results)
    write('search_arch10_'+tag+'realistic_results.json',report)
    with (R/('search_arch10_'+tag+'realistic_predictions.jsonl')).open('x',encoding='utf8') as f:
        for p in predictions:f.write(json.dumps(p,ensure_ascii=False)+'\n')
    print('realistic',json.dumps(report['summary']))


if __name__=='__main__':
    tag=sys.argv[1] if len(sys.argv)>1 else 'final'
    if tag.startswith('realistic'):realistic(tag[len('realistic'):]+'_' if tag!='realistic' else '')
    else:
        historical('search_arch10_'+tag+'_dev72','search_arch9_dev_reviewed.jsonl')
        historical('search_arch10_'+tag+'_v8exposed205','search_combined8_reviewed_population_r1.jsonl')
