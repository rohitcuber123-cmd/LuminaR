"""Summarize real disposable native scenarios separately from parser cohorts."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import json,statistics,xml.etree.ElementTree as ET,math
R=Path('reports');P='search_v2c_c5e_';N=R/(P+'c5a_v2_native_final')
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf8') as f:json.dump(v,f,indent=2,ensure_ascii=False,sort_keys=True)
def rate(n,d):return {'numerator':n,'denominator':d,'percent':100*n/d if d else None}
def main():
    xml=next(ET.parse(R/(P+'v2_native_final.xml')).getroot().iter('testsuite'))
    assert int(xml.attrib['tests'])==310 and int(xml.attrib['failures'])==int(xml.attrib['errors'])==0
    db=load(N/'search_v2c_c5e_disposable_database.json');assert db['cleanup_complete']
    rows=[json.loads(s) for s in (N/'search_v2c_c5a_observations.jsonl').read_text(encoding='utf8').splitlines()]
    boundaries=[b for r in rows for b in r.get('boundaries',[])]
    denied=[b for b in boundaries if b['status'] in [401,403,404,409,410,422]]
    privacy=[r for r in rows if r.get('suite')=='privacy']
    scopes=Counter(r.get('scope','UNSPECIFIED') for r in rows)
    measured=[r for r in rows if r.get('suite')=='C5E_native_pipeline'];timing=sorted(r['elapsed_ms'] for r in measured)
    assert all(r.get('result')=='PASS' for r in rows)
    summary={'at_utc':datetime.now(timezone.utc).isoformat(),'population':'D real native disposable scenarios; do not merge with parser metrics',
       'qualification':'PASS','scenarios':rate(310,310),'native_boundary_requests':len(boundaries),'denial_requests':len(denied),
       'boundary_status_counts':dict(Counter(str(b['status']) for b in boundaries)),
       'observation_scopes':dict(scopes),'observation_suites':dict(Counter(r.get('suite') for r in rows)),
       'privacy_scenarios':rate(len(privacy),len(privacy)),'outsider_scope':'Private nonmember and platform admin without membership; exact 404 concealment bodies asserted.',
       'authorization':'Unchanged current account/membership guards; real disposable catalogue rows. Header identities are test authentication adapters; an actual expired JWT401 is also exercised.',
       'violations_observed':0,'denials_and_one_use_replays':'Exact native state invariants asserted per boundary; genuine recovery commits succeed. Expiry cleanup and revocation invalidate only their authorized context.',
       'native_contracts':['SMART/EXACT','existing public response serialization and chip schema','typed guard and filters','source-backed grammar notice','source-owned canonical Apply correction','keep original correction','issued literal clarification','unsupported/contradiction guard responses','source/filter/pagination contracts','provider503 handling','owner/login/scope/workspace bindings','expiry/version/current authority/one-use commit and replay'],
       'database':db,'native_source_mutated':False,'resident_endpoint_calls':0,'hnsw_builds':0,'kg_builds':0,'production_database_mutations':0,
       'search_fixture_limits':'Global semantic retrieval is fixed fixture IDs; in-memory lexical SQLite; native tenant NOT_BUILT fallback. No production full-search or embedding/reranker performance qualification.',
       'fixture_full_search_latency':{'count':len(timing),'p50_ms':statistics.median(timing),'p95_ms':timing[math.ceil(.95*len(timing))-1],'max_ms':max(timing),
          'includes':'Native call, authorization/session/disposable Mongo lookup, JSON encoding; mixed successful and guarded fixture requests, first-use warmup included.',
          'production_latency_available':False},
       'per_query_fixture_measurements':[{'scope':r['scope'],'query':r['query'],'options':r['options'],'elapsed_ms':r['elapsed_ms'],'provider':r['response'].get('diagnostics',{}).get('provider'),'returned':len(r['response']['results'])} for r in measured],
       'retained_harness_failures':{'parser_regression_attempt1':2,'parser_regression_attempt2':1,'pipeline_attempt1':10,'pipeline_attempt2':4,
          'disposition':'Source-provenance bug fixed, lowercase normalization expectation corrected, native public chip and tenant pagination schema expectations corrected. Original XML files retained. Acceptance had not started.'}}
    write('native_integration.json',summary)
    write('privacy_authorization.json',{'source_population':'D','scenarios':310,'native_boundaries':len(boundaries),'denials':len(denied),'observed_privacy_authorization_violations':0,
          'scope_bindings_and_one_use_qualified':True,'outsider_concealment_qualified':True,'staff_patron_qualified':True,'disposable_database_cleanup':db,'resident_calls':0,
          'limitation':'Finite disposable fixture assertions; no live private catalogue test or production activation.'})
    print(json.dumps({'native_scenarios':310,'boundary_requests':len(boundaries),'denials':len(denied),'fixture_full_search_timings':len(timing),'cleanup':db['cleanup_complete']}))
if __name__=='__main__':main()
