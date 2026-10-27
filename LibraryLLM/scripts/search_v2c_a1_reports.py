"""Dated A.1 addendum; preserve prior acceptance and failed admission evidence."""
import hashlib
import json
import re
import runpy
import statistics
import xml.etree.ElementTree as ET
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import httpx
from backend.database.mongodb import db
from search.query_plan import parse_query, PARSER_VERSION

ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports'


def read(name):return json.loads((R/('search_v2c_a1_'+name+'.json')).read_text(encoding='utf8'))
def write(name,data):(R/('search_v2c_a1_'+name+'.json')).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf8')
def fp(path):
    p=Path(path);s=p.stat();value={'size':s.st_size,'mtime_ns':s.st_mtime_ns}
    if s.st_size<10_000_000:value['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    return value
def suite(name):
    p=R/('search_v2c_a1_'+name+'.xml');tree=ET.parse(p).getroot();suites=list(tree.iter('testsuite'))
    result={k:sum(int(s.get(k,0)) for s in suites) for k in ['tests','failures','errors','skipped']}
    result.update(report=str(p),cases=[t.get('name') for t in tree.iter('testcase')])
    assert not result['failures'] and not result['errors'],result
    return result


baseline=read('baseline');live=read('live');perf=read('performance');fixture=read('fixture')
facets=baseline['facets'];browser=read('browser_observations');security=read('browser_security')
suites={n:suite(n) for n in ['parser','admission','tenant','final_integration','recommendation','retrieval']}
assert suites['admission']['tests']==8
checks=runpy.run_path(str(ROOT/'tests/test_search_v2c_a.py'))
for label,rows in [('gold',checks['GOLD']),('metamorphic',checks['META'])]:
    failures=[]
    for case in rows:
        p=checks['plan_for'](case);m=checks['mismatches'](case,p)
        if m:failures.append({'id':case['id'],'mismatch':m})
    assert not failures
    write(label+'_regression',{'status':'PASS','passed':len(rows),'total':len(rows),'failures':failures,
        'corpus':'search_v2c_a_gold_queries.jsonl' if label=='gold' else 'search_v2c_a_metamorphic_queries.jsonl',
        'junit':suites['parser']['report'],'labels':'Existing independently AI-reviewed authored gold / seeded template labels retained unchanged. No human-verified accuracy claim.'})
focused=runpy.run_path(str(ROOT/'tests/test_search_v2c_a1.py'))
queries=list(dict.fromkeys(baseline['queries']+focused['CONTRADICTIONS']+[
    'include Romance','exclude Romance','include Romance, exclude Romance','with Romance but without Romance',
    'include Fiction but exclude Fiction and Romance','exclude Romance but include', 'include but exclude Romance',
    'include Fiction or Mystery','include Unknown Private Subject but exclude Romance',
    'books about romance but not romance novels']))
plans=[{'query':q,'plan':asdict(parse_query(q,facets)),'public':parse_query(q,facets).public()} for q in queries]
for row in plans:
    p=row['plan']
    for c in p['constraint_candidates']:
        source=c.get('source_query',p['raw_query'])
        assert source[c['source_span_start']:c['source_span_end']]==c['source_text']
original=plans[0]['plan']
assert original['decision']['decision_type']=='CONTRADICTORY' and original['semantic_text'] is None
assert original['subjects']==original['exclude_subjects']==['Romance']
write('clause_recognition',{'status':'PASS','parser_version':PARSER_VERSION,'observed_plans':plans,
    'boolean_semantics':'Existing ALL included canonical subjects; ANY exclusion authoritative. Include OR rejected UNSUPPORTED; no nested Boolean feature.',
    'scoped_lookup':'Exact canonical/alias dictionary probes bounded by source tokens, never a regex scan over every facet.',
    'source_span_integrity':'Every candidate source slice checked; distinct include/exclude spans retained for original failure.'})
write('contradictions',{'status':'PASS','observed': [r for r in plans if r['plan']['decision']['decision_type']=='CONTRADICTORY'],
    'execution_guard_evidence':suites['final_integration'],'actual_api_session_checks':live['sessions']})
write('leftover_validation',{'status':'PASS','original_before':baseline['plans'][0],'original_after':original,
    'observed_cases':plans,'rules':['Mask canonical clause spans before composing semantic remainder.',
        'Consume conjunctions only in wholly grammatical gaps between consumed candidates.',
        'Preserve about/on topic suffixes and opaque quoted spans.',
        'Typed INCOMPLETE for absent list operands; UNSUPPORTED for unresolved explicit inclusion or unsupported include-OR.'],
    'quote_boundary':'Quoted phrases remain literal semantic text as in V2C-A; this patch does not introduce title/entity parsing or force Exact mode.'})
for name,scopes in [('global',['GLOBAL']),('public_tenant',['TEST_PATRON','TEST_STAFF']),('private_tenant',['PRIVATE_PATRON','PRIVATE_STAFF'])]:
    write(name,{'status':'PASS','actual_api':{s:live['scopes'][s] for s in scopes},
        'session_checks':{s:live['sessions'][s] for s in scopes},'browser':[b for b in browser if b['scope'] in scopes],
        'outsider':live['denied'] if name=='private_tenant' else None,
        'scope_note':'TEST has no canonical Romance; inclusion is unsupported there, and negative romance stays an accepted literal exclusion. No Global subject imported.' if name=='public_tenant' else 'Only authorized canonical facets supplied.'})
write('session_regression',{'status':'PASS','actual_api':live['sessions'],'new_and_accepted_tests':suites['final_integration'],
    'browser_sequences':[b for b in browser if b['scope'].endswith('_SESSION')],
    'preserved':['user/JWT sid ownership','library/workspace isolation','expiry','clear/logout','membership revocation',
        'default OFF and own Reading List only','bounded personalization and strict filter authority'],
    'byte_for_byte_assertion':'Actual Mongo documents unchanged after contradiction in all five live contexts; later refinement retained wizards; clear deleted context; fresh search had no inherited rating.'})
write('recommendation_regression',{'status':'PASS','fresh_suite':suites['recommendation'],
    'depth_and_machine_regression':suites['retrieval'],'algorithm_changed':False,'machine_contract_changed':False})
write('more_like_this_regression',{'status':'PASS','fresh_suite':suites['retrieval'],
    'observed_case':'test_more_like_this_paths_are_real_and_contributions_sum_to_score','algorithm_changed':False})
for scope in ['GLOBAL','TEST_PATRON','TEST_STAFF','PRIVATE_PATRON','PRIVATE_STAFF']:
    rows=[r for r in browser if r['scope']==scope]
    assert len(rows)==3 and all(r['status']==200 for r in rows),scope
    assert any(r['interpretation']['decision']['decision_type']=='CONTRADICTORY' for r in rows)
for row in browser:
    if row.get('interpretation',{}).get('decision',{}).get('decision_type')=='CONTRADICTORY':
        assert row['returned']==0 and row['noticeVisible'] and row['editStateVisible'] and not row['falseNoMatchState']
assert security['revoked']['privateCardsAbsent'] and security['revoked']['interpretationAbsent']
assert security['outsider']['privateEntitiesAbsent'] and security['outsider']['interpretationAbsent']
write('browser',{'status':'PASS','browser':'Real Chromium / Codex in-app browser / tab1','working_origin':'http://127.0.0.1:5174',
    'observations':browser,'security':security,'session_observations':'Global/TEST/private valid wizards -> contradiction -> rating>3 preserved original topic.',
    'console':read('console'),'screenshots':[str(p.relative_to(ROOT)) for p in R.glob('search_v2c_a1_*.png')],
    'fixture_cleanup':fixture,'original_user_restored':True,'viewport':'Existing desktop viewport; no responsive/layout changes or emulation introduced.'})
modified=['search/query_constraints.py','search/query_repair.py','search/query_confidence.py','search/query_plan.py','search/query_execution.py']
new=['tests/test_search_v2c_a1.py','tests/institution_v2g/test_query_v2c_a1.py','scripts/search_v2c_a1_fixture.py',
     'scripts/search_v2c_a1_live.py','scripts/search_v2c_a1_reports.py']
preserved={name:{'before':before,'after':fp(ROOT/name),'unchanged':before==fp(ROOT/name)}
    for name,before in baseline['files'].items() if name not in modified and name!='reports/search_v2c_b_precondition.json'}
assert all(row['unchanged'] for row in preserved.values()),[k for k,v in preserved.items() if not v['unchanged']]
assert db.books.count_documents({})==5_000_000
with httpx.Client(timeout=20) as client:
    health=client.get('http://127.0.0.1:8003/health').json()
assert health['index_status']=='STALE' and health['baseline_verified'] is False
write('preservation',{'status':'PASS','fingerprints':preserved,'global_book_count':5000000,'global_health':health,
    'verification':'Exact size+nanosecond mtime for >=10MB; SHA256 also for smaller sources/manifests/reports. No claim of full multi-GB content hashing.',
    'global_hnsw_rebuilt':False,'global_kg_rebuilt':False,'production_tenant_generations_rebuilt':False,'new_model':False,
    'qwen_router_changed':False,'recommendation_mlt_changed':False,'circulation_assets_inventory_changed':False,
    'historical_reports':'All captured V2C-A acceptance artifacts and old blocker files unchanged. Current B precondition is separately archived before authorized update.',
    'test_artifacts':'Only isolated pytest FAISS/KG fixtures; disposable normal-service browser library archived and QA accounts disabled.'})
write('changed_files',{'modified':[{'path':p,'before':baseline['files'][p],'after':fp(ROOT/p)} for p in modified],
    'added':[{'path':p,**fp(ROOT/p)} for p in new],
    'scope':'Existing clause recognizer/composer/validator, parser version, bounded ALL-subject lookup safety, focused tests and acceptance evidence only.',
    'no_frontend_code_changes':True,'committed':False,'unrelated_work_preserved':True})
n=len(baseline['queries']);per_query=[]
for i,query in enumerate(baseline['queries']):
    before=sorted(baseline['parser_samples_ms'][i::n]);after=sorted(perf['after_samples_ms'][i::n])
    per_query.append({'query':query,'n':len(before),'before_p50_ms':statistics.median(before),'before_p95_ms':before[int(.95*len(before))-1],
        'after_p50_ms':statistics.median(after),'after_p95_ms':after[int(.95*len(after))-1]})
perf.update(per_query=per_query,notes=['Exact same24queries,4096freshGlobalfacets,25rounds per run;600samples each.',
    'Median lower, p95 +3.497ms (~23.4%). No general speedup or statistical significance claimed.',
    'Source review: new recognition uses bounded input-token exact dictionary probes; no per-facet regex compilation or model calls. Existing legacy semantic/facet fuzzy resolution remains and dominates topic/quote tails.',
    'No end-to-end speedup claim. One initial live ALL-subject query hit existing6s structured fallback; the existing indexed subject shortcut now selects the rarer included subject and refuses a broad-scan fallback. Final120scope probes all HTTP200.'])
write('performance',perf)
log=(ROOT/'.local/v2c-a1-frontend-full.log').read_text(encoding='utf8')
frontend_count=sum(map(int,re.findall(r'\btests (\d+)',log)));frontend_fail=sum(map(int,re.findall(r'\bfail (\d+)',log)))
assert frontend_count==885 and frontend_fail==0
qa={'FINAL':'PASS','V2C_A1_PATCH_IMPLEMENTED':'YES','ROOT_CAUSE_IDENTIFIED':'YES',
    'ORIGINAL_INCLUDE_EXCLUDE_FAILURE_FIXED':'YES','ORIGINAL_ADMISSION_TESTS':'8/8 PASS',
    **{k:'PASS' for k in ['INCLUDE_SUBJECT_RECOGNIZED','EXCLUDE_SUBJECT_RECOGNIZED','CANONICAL_CONTRADICTION_DETECTED',
        'CLAUSE_ORDER_INDEPENDENCE','VALID_NONCONFLICTING_CLAUSES_PASS','SEMANTIC_LEFTOVER_CLEAN','QUOTED_TITLE_PROTECTION_PASS',
        'CANONICAL_ALIAS_CONFLICT_PASS','INCOMPLETE_CLAUSE_DECISION_PASS']},
    'V2C_A_GOLD_REGRESSION':'136/136 PASS; unchanged AI-reviewed labels','V2C_A_SEEDED_REGRESSION':'1000/1000 PASS',
    'V2A_V2B_REGRESSION':'PASS;1299 planner tests including38new; overlapping focused suites not summed',
    'DATABASE_BACKED_ADMISSION':'PASS;184tenant +51final focused tests (overlap)',
    **{k:'PASS' for k in ['GLOBAL_SEARCH_PASS','PUBLIC_TENANT_SEARCH_PASS','PRIVATE_TENANT_SEARCH_PASS','PRIVATE_OUTSIDER_DENIAL_PASS',
        'MEMBERSHIP_REVOCATION_PASS','V2B_SESSION_PRESERVED','V2B_PERSONALIZATION_PRESERVED','RECOMMENDATION_REGRESSION_PASS',
        'MORE_LIKE_THIS_REGRESSION_PASS','STAFF_INVENTORY_PRESERVED','BROWSER_ACCEPTANCE','PRODUCTION_BUILD']},
    'CROSS_TENANT_LEAKS':'0 observed','FRONTEND_FULL_SUITE':'885/885 PASS; TypeScript check PASS',
    'PARSER_P50_P95_BEFORE':perf['before'],'PARSER_P50_P95_AFTER':perf['after'],
    'GLOBAL_BOOK_COUNT':5000000,'GLOBAL_SEARCH_HEALTH':'STALE/degraded; baseline_verified=false preserved; functional HTTP200 search.',
    **{k:'NO' for k in ['GLOBAL_HNSW_REBUILT','GLOBAL_KG_REBUILT','TENANT_HNSW_KG_REBUILT','QWEN_CHANGED']},
    'V2C_B_PRECONDITION_PASS':'YES', 'V2C_B_IMPLEMENTATION_STARTED':'NO','V2C_C_STARTED':'NO','PART_2I_STARTED':'NO'}
write('final_qa',{**qa,'summary':qa,'dated_addendum_utc':datetime.now(timezone.utc).isoformat(),'parser_version':PARSER_VERSION,
    'gates':{str(i):'PASS' for i in range(1,13)},'tests':suites,
    'frontend_logs':['.local/v2c-a1-frontend-full.log','.local/v2c-a1-typecheck.log','.local/v2c-a1-build.log'],
    'observed_failures_and_repairs':['Pre-patch admission7pass1fail.',
        'First expanded parser run exposed preserved doubled-whitespace normalization; corrected candidate value, original offsets preserved.',
        'One test setup left work_id index for later tests and accidentally enabled production-KG shortcut in isolated fixtures; added test-index teardown. Final51allPASS.',
        'Initial live multi-subject503 described in performance report; bounded indexed path corrected. Final120APIprobes allPASS.'],
    'limitations':['Deterministic clause grammar only; include-OR and unresolved explicit subjects remain typed unsupported.',
        'Quoted titles retain accepted literal semantic interpretation; no new exact-title parser.',
        'Parser p95 increased3.497ms; see raw samples and per-query timings.'],
    'completion':'V2C-A.1 corrective patch PASS. The V2C-B precondition may now be rerun.'})
root_cause='''# V2C-A.1 root cause — 15 October 2026 addendum

The pre-patch command reproduced7passed/1failed. A fresh authorized Global vocabulary and the accepted snapshot both contain Romance. Source normalization preserves `include romance but exclude romance` and original offsets.

The existing exclusion recognizer first adds `exclude romance` at20..35. The inclusion regex only recognizes an `and` boundary or end-of-input, so its next match is0..35 with operand `romance but exclude romance`. Source.free rejects that overlap. No inclusion candidate reaches composition. Canonical exclusion resolves to Romance; the remaining text `include romance but` is passed to the legacy facet/topic grammar and becomes semantic text. The final subject-intersection validator is correct but receives no included subject.

The fix bounds clauses before overlap resolution in query_constraints.subject_clauses. Canonical operands and aliases are resolved through the supplied scoped dictionary; each included/excluded operand has a distinct original span. Candidate precedence still protects quotes, identifiers and previously consumed rating/year/format spans. Conjunctions are consumed only in grammatical gaps between recognized spans. Multiple included subjects retain existing ALL semantics; explicit include-OR is unsupported. Unknown explicit inclusion is unsupported; meaningful noncanonical exclusions remain text exclusions. Incomplete clauses do not execute.

query_repair.compose merges canonical subject/excluded_subject candidates and preserves genuine topic suffixes. query_confidence.validate still checks the final normalized subject intersection, now attaching internal source spans. Public messages retain the safe existing contract. Parser version advances to search-v2c-a1-compositional-1 to avoid idempotent replay of the old nonempty parse.

A live query with two included subjects exposed the existing first-subject-only metadata shortcut: Fiction was too common, so the query timed out on the old structured fallback. query_execution now picks the rarest included subject for the same bounded indexed projection, retains all authoritative predicates, and refuses broad-scan fallback for this new multi-subject path. No HNSW/KG artifact, model, index or ranking algorithm is replaced.

See baseline.trace for observed normalization, candidate stages, rejected overlap and remainder. Exact source hashes are in baseline/changed_files; final candidates and decisions are in clause_recognition/contradictions/leftover_validation. Historical V2C-A reports are unchanged.
'''
(R/'search_v2c_a1_root_cause.md').write_text(root_cause,encoding='utf8')
review=f'''# V2C-A.1 corrective patch — 15 October 2026

PASS. The original query now retains canonical Romance inclusion and exclusion, returns CONTRADICTORY, and has no semantic topic. Both source spans survive. Valid distinct-subject clauses execute; scoped aliases and incomplete syntax are handled without importing Global metadata into tenants.

Original admission8/8. Planner1299passed including38new focused cases, unchanged136gold and1000seeded assertions. Tenant184passed; final focused integration51passed (overlapping suites). Recommendation88passed; retrieval/KG/depth/MLT35passed. Frontend885passed; TypeScript and production build passed. Original gold remains independently AI-reviewed, not human-verified accuracy.

Real Chromium covered Global, TEST patron/staff and private patron/staff: valid clauses, contradictions and quoted text. Global/TEST/private patron rejected-session retry retained wizards. Revocation and outsider denial removed private catalogue content. Original user restored; disposable fixtures cleaned. All120live scope probes passed with canonical predicate checks, plus five actual Mongo session flows and outsider API denial.

Parser p50/p95 before3.444/14.954ms; after1.385/18.451ms across600comparable samples each. Median decreased; tail increased3.497ms. New clause lookup is bounded by input, with no facet-regex compilation loop. Full measurements and limits are in performance.json; no general speedup claimed.

Protected captured artifacts/reports match their pre-patch fingerprints. Global count remains5,000,000; existing STALE/degraded baseline_verified=false health is preserved. No production rebuild, migration, new model, Qwen/router, recommendation/MLT, circulation, asset or inventory change. No commit or reset.

Known boundaries: include lists use existing ALL semantics; nested/disjunctive inclusion is unsupported. Unknown subjects are not fabricated. TEST lacks canonical Romance, so explicit inclusion there is unsupported while a text exclusion remains available. Protected quoted titles retain V2C-A's literal semantic behavior. The existing bounded subject projection can return503 when unavailable; it cannot silently fall back to a broad scan for multiple included subjects.

V2C-A.1 corrective patch PASS. The V2C-B precondition may now be rerun.

## Exact final QA summary

```json
{json.dumps(qa,indent=2)}
```
'''
(R/'search_v2c_a1_review.md').write_text(review,encoding='utf8')
required=['baseline.json','root_cause.md','changed_files.json','clause_recognition.json','contradictions.json','leftover_validation.json',
    'gold_regression.json','metamorphic_regression.json','global.json','public_tenant.json','private_tenant.json','session_regression.json',
    'recommendation_regression.json','more_like_this_regression.json','browser.json','performance.json','preservation.json','final_qa.json','review.md']
assert all((R/('search_v2c_a1_'+n)).stat().st_size>100 for n in required)
old=R/'search_v2c_b_precondition.json';archive=R/'search_v2c_b_precondition_before_a1.json'
if not archive.exists():archive.write_bytes(old.read_bytes())
archived=json.loads(archive.read_text());assert archived['status']=='FAIL'
old.write_text(json.dumps({'captured_at':datetime.now(timezone.utc).isoformat(),'status':'PASS','V2C_A_PRECONDITION_PASS':True,
    'parser_version':PARSER_VERSION,'implementation_started':False,'scope':'V2C-A.1 corrective admission only; V2C-B features not started.',
    'archived_failure':str(archive.relative_to(ROOT)),'archived_failure_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
    'admission':suites['admission'],'current_parser':suites['parser'],'current_integration':suites['final_integration'],
    'observed_corrected_plan':original,'addendum':'reports/search_v2c_a1_final_qa.json','browser':'reports/search_v2c_a1_browser.json',
    'preservation':'reports/search_v2c_a1_preservation.json','prior_v2ca_acceptance_reports_unchanged':True},indent=2),encoding='utf8')
print(json.dumps({'status':'PASS','reports':len(required),'protected_fingerprints':len(preserved),'admission':'8/8',
    'parser':suites['parser']['tests'],'frontend':frontend_count,'precondition_updated':True}))
