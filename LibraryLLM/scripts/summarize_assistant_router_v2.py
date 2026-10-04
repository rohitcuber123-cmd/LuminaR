"""Consolidate measured V2 evidence without touching any prior reports."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from evaluate_assistant_router_v2 import metrics,write


def main():
    experiments=json.loads((ROOT/'reports/assistant_router_v2_experiments.json').read_text())
    variants=experiments['variants']
    assert set('ABCDEF')<=set(variants),'Complete controlled matrix first'
    for label,record in variants.items():
        raw=json.loads((ROOT/'reports'/record['case_report']).read_text())
        assert raw['complete'] and len(raw['cases'])==116
        record['metrics']=metrics(raw['cases'])
    chosen=max(variants,key=lambda k:(variants[k]['metrics']['strict']['percent'],
        variants[k]['metrics']['critical_context']['percent'],-variants[k]['metrics']['median_ms']))
    experiments['chosen']=chosen
    best=variants[chosen]
    primary=json.loads((ROOT/'reports'/best['case_report']).read_text())
    hidden=json.loads((ROOT/'reports/assistant_router_v2_hidden_cases.json').read_text())
    assert hidden['complete'] and hidden['architecture']==best['architecture'] and hidden['retry']==best['retry']
    assert len(hidden['cases'])>=100
    seal=json.loads((ROOT/'reports/assistant_router_v2_hidden_manifest.json').read_text())
    assert all(r['message']==s['message'] for r,s in zip(hidden['cases'],seal['cases']))
    hidden['metrics']=metrics(hidden['cases'])
    primary.update(chosen=chosen,acceptance_threshold_percent=90)
    hidden.update(acceptance_threshold_percent=85,heldout_seal_sha256=seal['sha256'])
    live=json.loads((ROOT/'reports/assistant_router_v2_live.json').read_text())
    existing_score=best['metrics']['strict']['percent'];hidden_score=hidden['metrics']['strict']['percent']
    critical_rows=[r for r in primary['cases']+hidden['cases'] if r['context'] in {'selected','comparison','changed','page'} and r['category'] not in {'explicit_entity','search'}]
    critical={'passed':sum(r['pass'] for r in critical_rows),'total':len(critical_rows),
        'percent':100*sum(r['pass'] for r in critical_rows)/len(critical_rows)}
    adequate=existing_score>=85 and hidden_score>=80
    quality=existing_score>=90 and hidden_score>=85 and critical['percent']>=95
    safe=all(m['fuzzy_false_positives']==0 and m['unrelated_search_fallbacks']==0 for m in (best['metrics'],hidden['metrics']))
    live_pass=live.get('complete') and live['passed']==live['total']
    experiments.update(critical_combined=critical,model_adequacy={'pass':adequate,'existing_minimum':85,'hidden_minimum':80},
        acceptance={'existing_90':existing_score>=90,'hidden_85':hidden_score>=85,'critical_95':critical['percent']>=95,
            'safety_zero_false_positives':safe,'live_chains':live_pass},
        status='PASS' if quality and safe and live_pass else 'FAIL' if not adequate or not safe else 'PARTIAL',complete=True)
    write('assistant_router_v2_experiments.json',experiments)
    write('assistant_router_v2_cases.json',primary)
    write('assistant_router_v2_hidden_cases.json',hidden)
    latency={'variants':{k:{name:v['metrics'][name] for name in ('median_ms','p90_ms','median_input_tokens','median_output_tokens','qwen_calls_per_request','max_qwen_calls','prose_calls','retry_requests')} for k,v in variants.items()},
        'hidden':hidden['metrics'],'chosen':chosen,
        'historical_semantic_median_ms':2880.72,'current_compact_rerun_median_ms':variants['A']['metrics']['median_ms'],
        'note':'Current matrix uses unchanged model/settings. Historical timing is separate; current A is the controlled comparator.'}
    for label in (chosen,'hidden'):
        rows=primary['cases'] if label==chosen else hidden['cases']
        retries=[r for r in rows if r['telemetry'].get('retry_used')]
        latency.setdefault('focused_retries',{})[label]={'requests':len(retries),'total':len(rows),
            'strict_passed_after_retry':sum(r['pass'] for r in retries),
            'median_total_ms':statistics.median([r['profile']['total_ms'] for r in retries]) if retries else None,
            'median_retry_ms':statistics.median([r['telemetry'].get('retry_ms',0) for r in retries]) if retries else None}
    write('assistant_router_v2_latency.json',latency)
    baseline=json.loads((ROOT/'reports/assistant_router_v2_baseline.json').read_text())
    frozen_changes=[name for name,digest in baseline['frozen_services'].items()
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest]
    old_report_changes=[name for name,record in baseline['reports_preserved_in_place'].items()
        if not (ROOT/name).exists() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=record['sha256']]
    suites={}
    for name in ('assistant','security','admin','notifications','circulation_graph'):
        tree=ET.parse(ROOT/f'reports/assistant_router_v2_{name}.xml').getroot();tests=list(tree.iter('testcase'))
        suites[name]={'tests':len(tests),'failures':sum(t.find('failure') is not None for t in tests),
            'errors':sum(t.find('error') is not None for t in tests),'skipped':sum(t.find('skipped') is not None for t in tests)}
        suites[name]['passed']=len(tests)-sum(suites[name][k] for k in ('failures','errors','skipped'))
    regression=json.loads((ROOT/'reports/assistant_router_v2_regression.json').read_text())
    regression.update(suites=suites,total_passed=sum(s['passed'] for s in suites.values()),
        frozen_source_changes=frozen_changes,prior_reports_checked=len(baseline['reports_preserved_in_place']),
        prior_report_changes=old_report_changes,
        source_changes=[name for name,digest in baseline['assistant_sources'].items()
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest],
        added_sources=['assistant/router_v2.py','assistant/router_v2_legacy.py',
            'scripts/evaluate_assistant_router_v2.py','scripts/assistant_router_v2_corpus.py',
            'scripts/check_assistant_router_v2_live.py','scripts/summarize_assistant_router_v2.py',
            'scripts/check_assistant_router_v2_parity.py','scripts/check_assistant_router_v2_restored.py',
            'tests/test_assistant_router_v2.py'])
    assert not frozen_changes and not old_report_changes,'Frozen evidence must stay unchanged'
    write('assistant_router_v2_regression.json',regression)
    print(json.dumps({'chosen':chosen,'existing':best['metrics']['strict'],'hidden':hidden['metrics']['strict'],
        'critical':critical,'adequacy':adequate,'status':experiments['status'],'live':(live['passed'],live['total'])},indent=2))


if __name__=='__main__':main()
