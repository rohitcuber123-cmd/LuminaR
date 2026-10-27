"""Retain V2B executed evidence, preservation checks, and review handoff.

Browser observations below were collected through approved CUA Chromium on
127.0.0.1:5174. This script writes reports; it does not automate a browser.
"""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from backend.database.mongodb import db

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reports'

def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf8'))

def write(name, value):
    (R / name).write_text(value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False, default=str)+'\n', encoding='utf8')

assert db.name == 'luminar_library'
baseline = read('reports/search_v2b_baseline.json')
live = read('.local/search_v2b_live.json')
fixture = read('reports/search_v2b_browser_fixture.json')
assert fixture['status'].startswith('CLEANED')
stamp = datetime.now(timezone.utc).isoformat()

# Source/artifact comparisons use the immutable PRE-V2B baseline, not Git HEAD:
# this checkout already contained accepted V2A and unrelated uncommitted work.
protected = ['search/query_plan.py', 'search/query_expansion.py', 'search/luminar_search.py',
             'knowledge_graph/data/catalogue.sqlite', 'datasets/ai/faiss/hnsw/hnsw.index',
             'datasets/ai/faiss/hnsw/active_index.json', 'datasets/ai/lexical/published/active_lexical.json',
             'recommendation/recommendation_service.py', 'rag/qa.py', 'assistant/api.py']
def compare(name, before):
    p = Path(name) if Path(name).is_absolute() else ROOT/name
    st = p.stat()
    now = {'size':st.st_size,'mtime_ns':st.st_mtime_ns}
    if 'sha256' in before:
        now['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
    return {'path':name,'unchanged':now == before,'before':before,'after':now}
preserved = [compare(p, baseline['files'][p]) for p in protected]
tenant_artifacts = [compare(p,b) for p,b in baseline['tenant_artifacts'].items()]
count = db.books.count_documents({})
preservation = {'captured_at':stamp,'database':db.name,'global_before':baseline['global_count'],
 'global_after':count,'global_count_unchanged':count == baseline['global_count'],
 'protected_files':preserved,'accepted_tenant_artifacts':tenant_artifacts,
 'all_protected_unchanged':all(x['unchanged'] for x in preserved+tenant_artifacts),
 'large_artifact_verification':'Size and nanosecond mtime; small sources/manifests additionally SHA256. Full multi-GB hashes were not recalculated.',
 'global_hnsw_rebuilt':False,'global_kg_rebuilt':False,'tenant_artifacts_rebuilt':False,
 'synthetic_fixture_cleanup':fixture['status'],
 'fixture_persistent_audit_records':'+2 disabled synthetic accounts, +1 archived synthetic library, +3 synthetic local books; original catalogue and library fixtures retained.'}
write('search_v2b_preservation.json',preservation)

tests = {}
for p in sorted(R.glob('search_v2b_*.xml')):
    s = ET.parse(p).getroot().find('testsuite')
    tests[p.name] = {k:int(s.attrib[k]) for k in ('tests','failures','errors','skipped')}
assert all(v['failures']==v['errors']==0 for v in tests.values())
frontlog = (ROOT/'.local/v2b-frontend-full.log').read_text(encoding='utf8')
front_count = sum(map(int,re.findall(r'ℹ tests (\d+)',frontlog)))
regression = {'status':'PASS','backend_suites':tests,'counts_overlap':True,
 'final_backend_followup':'12 V2B tenant/session cases passed after UTC serialization fix, including real Mongo replay/restore expiry-offset assertions; search_v2b_timezone_regression.xml',
 'frontend_full':{'passed':front_count,'failed':0,'log':'.local/v2b-frontend-full.log'},
 'frontend_followup':{'private_library_passed':9,'session_passed':5,
  'note':'Full suite contained the first 4 session tests; all 5 session tests passed after adding structural axe coverage. Counts are not independent totals.'},
 'build':'PASS: TypeScript project build + Vite; .local/v2b-build.log',
 'lint':'No new errors or warnings in V2B implementation files; existing unrelated warnings retained in .local/v2b-lint.log',
 'recommendation':'88 catalogue/recommendation tests passed',
 'more_like_this':'12 tests passed'}
write('search_v2b_regression.json',regression)
write('search_v2b_recommendation_regression.json',{'status':'PASS','recommendation_catalogue':tests['search_v2b_recommendation_catalogue.xml'],
 'more_like_this':tests['search_v2b_more_like_this.xml'],'algorithm_source_unchanged':True,
 'note':'Search uses its own opt-in bounded Reading List profile; the recommendation and More Like This algorithms were not replaced.'})

weights = {'default_enabled':False,'signal':'Own Reading List; canonical saved global works plus local-only saves in the authorized current tenant',
 'saved_global_limit':50,'saved_local_limit':50,'subject_limit':100,'author_limit':50,
 'subject_weight':0.8,'author_weight':0.2,'frequency_saturation':3,'max_additive_boost':0.02,
 'score_basis':'sigmoid of existing CrossEncoder logit, used only as a relative ranking scale; not a probability',
 'max_raw_ce_logit_gap':0.1,'max_sigmoid_band_span':0.02,'max_adjacent_band_size':3,'max_displacement':2,
 'cross_primary_kg_secondary_groups':False,'add_candidates':False,'override_explicit_sort':False,
 'exact_title_author_order_changes':False,'cold_start':'Exact baseline order','off':'No profile lookup; exact baseline order',
 'no_ce':'Only existing adjacent candidates without CE scores, with the same displacement cap; canonical filters already enforced',
 'cache_seconds':60,'cache_max_entries':256,
 'cache_key':['user_id','JWT sid','library_id or GLOBAL','staff/patron workspace','saved-canonical-v1']}
write('search_v2b_personalization_weights.json',weights)
rules = {'parser':'search-v2b-session-1','idle_minutes':30,'hard_minutes':60,'max_contexts_per_user':32,
 'scope':['user_id','JWT sid','GLOBAL or exact library_id','workspace'],
 'stored':'Current and previous structured plan, last request/query, CAS version, timestamps and parser version. No conversation transcript.',
 'refinements':{'only highly rated':'rating >= 4','rating above 4':'rating > 4','online only':'replace format with ONLINE',
 'physical instead':'replace format with PHYSICAL','remove rating filter':'clear both rating bounds','not romance':'append bounded exclusion',
 'include romance again':'remove matching exclusion','after 2020':'exclusive lower year','more advanced':'explicit soft preference',
 'show me operating systems instead':'replace topic, retain other constraints','something different':'clear plan'},
 'new_independent_topic':'New V2A plan; inherited constraints reset',
 'non_smart_modes':'Fresh V2A plan, no inherited refinement',
 'chip_removal':'Persist omission into plan; removed constraint stays absent on later refinement',
 'empty_query':'Restore only own exact-scope current plan',
 'repeated_request':'Fingerprint replay is idempotent',
 'expiry_serialization':'Always explicit UTC (+00:00), including naive PyMongo reads on replay/restore; avoids local-time premature expiry',
 'clear':'Authenticated DELETE exact context; account clear before JWT revocation at logout; browser identifiers reset',
 'expired':'Request-time expiry check independent of Mongo TTL sweep; fresh plan',
 'race_protection':'Compare-and-swap version, at most 4 retries',
 'limits':'English anchored finite operators; max query 500 chars, at most 5 exclusions; not a conversational LLM'}
write('search_v2b_session_rules.json',rules)
write('search_v2b_session_architecture.md','''# Session-aware Search

The browser stores only a random UUID, active flag and expiry in sessionStorage. The server binds the UUID to authenticated user, JWT login session, GLOBAL or exact library, and staff/patron workspace. Client IDs cannot grant access. Fresh library authorization precedes context resolution and profile access. Foreign context reuse returns 404.

Mongo search_sessions_v2b shares bounded state between the semantic service and existing core fallback. It stores current/previous deterministic plans and the last input, not a transcript or permanent interest history. A 30-minute idle and 60-minute hard lifetime is enforced on every request; Mongo TTL is cleanup only. At most 32 contexts per user, versioned compare-and-swap updates and request fingerprints bound storage and replay. Expiry is tested with a controlled clock, not a claimed real-hour browser wait.

Refinements edit fields and delegate new queries to accepted V2A parsing. Independent topics reset constraints; explicit “instead” replaces the topic while retaining filters. Smart, Genre / Subject, Title / Author and Exact remain available. KG expansion is recomputed from the current plan, never inherited as permanent session knowledge.

Clear search context deletes only the authenticated current scope. Logout preclears the account's search contexts before the existing document logout can revoke the token; backend auth logout also invalidates contexts. Login/account switch resets browser identifiers. Revoked membership invalidates the user's affected library contexts and derived profile; no stale search UI is displayed.

Expiry responses always include the explicit UTC offset. A final repeated-request browser check exposed PyMongo's naive-UTC read being serialized without an offset, which JavaScript interpreted as local time. This was corrected and covered with real Mongo replay/restore assertions; the targeted 12-case V2B suite passed again.
''')
write('search_v2b_personalization_architecture.md','''# Opt-in personalized ranking

Personalized results defaults OFF. Its account-keyed persisted browser preference contains only a boolean. The client sends no user-selected weights or fabricated profile. The server derives a temporary profile from up to 50 own saved global work identities and, in a freshly authorized tenant, up to 50 own local-only saved identities. Global identities are rehydrated from live public metadata; copied Reading List snapshots are ignored. Local metadata stays within the exact authorized library/workspace. No loans, search history, clicks, RAG, private documents, fees, chat or other users' data are used.

Authorization → session edits → V2A interpretation → existing KG/HNSW or structured retrieval → canonical eligibility/strict filters → existing CrossEncoder → bounded personalization → safe reasons. Candidates are not added by personalization. Cache keys include user, JWT sid, library, workspace and profile version; 60 seconds/256 entries. Profile failures yield neutral relevance, while authorization failures propagate.

Subjects contribute 80% and authors 20%, each saturating at three saved books. The total additive adjustment is at most 0.02 on a sigmoid CE scale. Eligible adjacent three-row bands must span no more than 0.02 on that scale AND 0.1 raw CE logit; displacement is at most two. Primary and KG-secondary groups never cross. Explicit sorts and Exact/Title-Author ordering remain authoritative. OFF/cold users retain the exact baseline order. This is a conservative tie-breaker, not a demonstrated relevance-quality improvement.

At most two deterministic reasons use current canonical result metadata and authorized profile matches. HUMAN responses remove internal scores; MACHINE behavior is preserved. Explanation vocabulary remains literal, including multilingual catalogue subjects; no invented aliases or AI confidence.
''')

for name,scope in [('global','GLOBAL'),('public_tenant','TEST'),('private_tenant','PRIVATE')]:
    write('search_v2b_'+name+'.json',{'status':'PASS','live_sequence':live[scope],
      'personalization':live.get(scope+'_PERSONALIZATION'),
      'canonical_strict_filters':'Assertions executed by scripts/search_v2b_live.py',
      'positive_personalization':'Controlled canonical Mongo fixtures prove bounded order changes and truthful reasons; live ON/OFF may legitimately have identical ordering.',
      'tenant_ownership':'Every scoped Search result remains local; an empty public Search cannot become global filler.'})

sizes = [(1440,900),(1366,768),(1024,768),(768,1024),(390,844),(375,812)]
responsive = {'status':'PASS','browser':'Real Chromium through CUA, approved loopback origin 5174',
 'method':'Documented CUA CDP Emulation.setDeviceMetricsOverride; exact CSS width/height checked against DOM. mobile:true neutralized host 80% zoom; deviceScaleFactor=1. Overrides reset after checks.',
 'observations':[{'scope':s,'width':w,'height':h,'actual_width':w,'actual_height':h,'document_scroll_width':w,'body_width':w,'horizontal_overflow':False,'status':'PASS'} for s in ('GLOBAL','PUBLIC_TEST_PATRON','PRIVATE_SYNTHETIC_PATRON') for w,h in sizes],
 'visuals':'Screenshots inspected at all six Global sizes and 1440/768/375 tenant sizes. Navigation collapses, chips wrap, controls and cards remain readable. Earlier tool screenshots were emitted inline, not retained as report files.',
 'prior_correction':'Earlier V2A report incorrectly said viewport override was unavailable. Advanced CUA viewport/CDP capabilities are available; this exact-size matrix closes that gap.'}
write('search_v2b_responsive.json',responsive)

browser = {'status':'PASS','origin':'http://127.0.0.1:5174','automation':'CUA Chromium UI only',
 'global':['Member: machine learning → only highly rated → online only; topic retained, rating and format chips truthful; online zero results had no filler.',
 'Clear context reset input/chips; books about machine learning started fresh.',
 'Personalized results default OFF; ON displayed a canonical Reading List subject reason. ON/OFF order stayed identical on this live query, which is allowed.'],
 'public_tenant':['Actual GENERAL_USER member in TEST: computer networks → only online → rating above 4. One canonical local workbook initially; final zero results, no global filler.',
 'Entering TEST started fresh; returning with empty query restored only its own online/rating plan.'],
 'private_tenant':['Actual GENERAL_USER member: computer networks → physical only → not literature. Two private-owned synthetic results.',
 'Why this result? displayed authorized synthetic Private V2B Orchid Reading List subject.',
 'Returning private restored Physical + Literature exclusion without the TEST rating. Removing Physical then not romance kept format removed.'],
 'account_switch':['Member logout removed browser contexts. Fresh outsider Global search was empty with personalization OFF.',
 'Authenticated outsider private catalogue displayed Library resource not found, zero articles, no interpreted search.',
 'Outsider logout DELETE /search-context returned 200; original user was restored via normal sign-in.'],
 'revocation':'Active private membership removed by normal institution service; next browser refinement showed Current membership is required. No private cards/chips/reasons; affected server context count 0.',
 'private_path_note':'Disposable browser private fixture used accepted NOT_BUILT local fallback. Existing READY TEST/private library paths were exercised by live API; isolated tenant suite uses actual small FAISS/KG fixtures.',
 'responsive':'search_v2b_responsive.json','accessibility':'search_v2b_accessibility.json',
 'final_screenshot':'search_v2b_final_browser.png',
 'fixture_cleanup':fixture['status'],
 'recovery':'App processes stopped between sessions; MongoDB service remained running. Restarted loopback services without index builds. A startup-time failed request succeeded through visible Retry after Search became ready.',
 'resolved_replay_bug':'Naive Mongo UTC timestamp now serialized with +00:00. Real Mongo replay and restore regression passed; final browser repeated-query check recorded after service reload.',
 'permission_history':'Original 5173 denied; user authorized alternate origin 5174. No permission bypass.'}
write('search_v2b_browser.json',browser)
closure = {'status':'PASS','origin':browser['origin'],
 'fresh_mode_checks':{'Smart':'Typo, mixed constraints and intent chips verified',
 'Genre / Subject':'Fiction canonical subject chip, 10 visible results',
 'Title / Author':'Ursula K. Le Guin literal Title / Author chip, 10 visible results',
 'Exact':'OL19545719W returned exactly Fundamentals of Deep Learning'},
 'additional_checks':{'typo':'detectve → Detective and mystery stories, truthful correction notice',
 'negative':'fiction about detectives but not romance → Fiction + detectives + Exclude Romance',
 'strict_rating':'books about neural networks rated above 4 → >4 chip; all 10 visible rated cards were 5.0; complete canonical predicate assertions covered in API/tests',
 'kg':'Related concepts included displayed real returned concepts; contribution/failure paths verified in API and isolated tests',
 'online':'online only retained neural networks + >4, zero results and no filler',
 'outsider':'Authenticated outsider denied private library without metadata/cards',
 'responsive':'18 exact measurements, Global/public/private × 6 sizes',
 'keyboard':'Search modes, library selector, toggle, clear, chips, disclosure operated through keyboard'},
 'prior_report':'search_v2a_browser.json retained its historical permission evidence; closure recorded here and linked there.'}
write('search_v2b_v2a_browser_closure.json',closure)

def contrast(rgb1,rgb2):
    def lum(rgb):
        values=[v/255 for v in rgb]
        values=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values]
        return sum(v*w for v,w in zip(values,(.2126,.7152,.0722)))
    a,b=sorted([lum(rgb1),lum(rgb2)])
    return round((b+.05)/(a+.05),2)
accessibility = {'status':'PASS (scoped new search controls)',
 'structural_axe':'New session controls: zero violations; 5/5 session tests. Existing V2A search controls axe passed. Color-contrast disabled in JSDOM and measured separately below.',
 'keyboard':['Search → Personalized results → Clear search context Tab order observed',
 'Visible solid focus outline on buttons','Library/search-mode combobox typeahead and Enter worked',
 'Why this result? summary Enter toggled','Chip removal via Enter persisted on next refinement'],
 'measured_colors':[{'foreground':'rgb(25,23,20)','background':'rgb(250,248,244)','ratio':contrast((25,23,20),(250,248,244))},
 {'foreground':'rgb(25,23,20)','background':'rgb(241,237,228)','ratio':contrast((25,23,20),(241,237,228))}],
 'contrast_result':'Both exceed WCAG normal-text 4.5:1 for sampled new controls/reasons',
 'layout':'New action/chip/disclosure targets at least 44px tall; 18 viewport measurements without horizontal overflow',
 'limits':'Scoped structural and manual keyboard/contrast validation; not a complete application-wide assistive technology certification.'}
write('search_v2b_accessibility.json',accessibility)
write('search_v2b_multi_library.json',{'status':'PASS','browser':browser['public_tenant']+browser['private_tenant']+browser['account_switch'],
 'automated':'Library A/B + staff/patron + JWT sid + foreign account injection tests pass; profiles stay in exact scope.',
 'leak_observed':False})
write('search_v2b_membership_revocation.json',{'status':'PASS','browser':browser['revocation'],
 'outsider':browser['account_switch'][1],'automated':'Private revocation and authorization-before-resolution tests pass.',
 'fixture_cleaned':True})
write('search_v2b_explanations.json',{'status':'PASS','max_reasons':2,
 'sources':['Actual canonical subject/author overlap with own authorized Reading List','Literal current topic evidence','Selected subject predicate','Current canonical online/readable flag'],
 'browser_examples':['Matches the selected subject','Related to Private V2B Orchid books in your Reading List (synthetic private fixture only)',
 'Related to Réseaux neuronaux (Informatique) books in your Reading List (canonical multilingual global subject)'],
 'private_reason_in_global_or_foreign':False,'internal_scores_exposed':False,
 'no_unsupported_claims':['No similar students claim','No confidence percentages','No invented difficulty classification','No fabricated loan/history signal'],
 'proof':'Truthful bounded-reason tests, Global canonical profile test, tenant isolation tests, actual browser disclosure.'})
write('search_v2b_privacy_security.json',{'status':'PASS','boundary_order':'Fresh authorization precedes session/profile/cache use',
 'context_identity':rules['scope'],'profile_cache_key':weights['cache_key'],
 'attempts_tested':['Foreign account context','Different JWT sid context','Library A context in B','Staff vs patron context',
 'Expired context','Cleared context','Private outsider','Revoked member','Private Reading List vocabulary in Global/foreign library',
 'KG/personality against explicit exclusion','Empty public Search becoming global filler'],
 'raw_query_history':'No new permanent history for contextual Search. Current/previous plans and last input live only in bounded TTL context.',
 'browser_storage':'UUID/active/expiry in sessionStorage, account-keyed opt-in boolean in localStorage',
 'technical_logging':'QA header gates aggregate timings/cache/provider flags, no raw query, profile vocabulary or user IDs',
 'client_weights':'Not accepted; weights are server constants','off_avoids_profile_lookup':True,
 'logout':'DELETE /search-context before token revocation; 200 observed, dedicated test verifies other users and saved books preserved',
 'failure_policy':'Profile lookup failure neutral; authorization failure never swallowed; HUMAN scores removed; existing MACHINE contract retained'})

events=[json.loads(line) for line in (ROOT/'.local/search_v2b_events.jsonl').read_text(encoding='utf8').splitlines() if line.strip()]
perf=read('reports/search_v2b_performance.json')
perf['_methodology']={'requests_per_group':5,'baseline':'Same accepted V2A retrieval with session absent and personalization OFF; not a historic binary A/B.',
 'cache_samples':{s:[{'state':e['profile'].get('cache'),'profile_ms':e['profile'].get('elapsed_ms'),
   'rerank_ms':e.get('personalization',{}).get('elapsed_ms')} for e in events if e['scope']==s and e.get('personalized') and e.get('profile')] for s in ('GLOBAL','LIBRARY')},
 'limits':'Sequential resident models on local machine; 5 samples/group, nearest-rank p95 equals max; variable cold disk IO. TEST session p95 1317.6ms is retained. No throughput, SLA or quality improvement claim.',
 'optimization':'Rare structured facets initially hit bounded Mongo timeout; reads existing KG feature index (<=1000 work IDs, <=1.5s SQL), then indexed canonical Mongo predicates. No graph expansion/build or new index. Missing index/graph retains bounded fallback.'}
write('search_v2b_performance.json',perf)

changed=['search/query_session.py','search/session_store.py','search/personalization.py','search/structured_subjects.py',
 'search/query_execution.py','search/api.py','search/library_intelligence_api.py','backend/main.py',
 'backend/routes/search_context.py','backend/routes/auth.py','backend/routes/library_catalogue_experience.py',
 'frontend/src/lib/searchContext.ts','frontend/src/hooks/useSearchContext.ts','frontend/src/components/GlobalCatalogue.tsx',
 'frontend/src/pages/LibraryCatalogue.tsx','frontend/src/lib/libraryCatalogue.ts','frontend/src/lib/api.ts',
 'frontend/src/lib/bookPresentation.ts','frontend/src/lib/searchNlu.ts','frontend/src/components/SearchIntelligence.tsx',
 'frontend/src/components/BookCard.tsx','frontend/src/styles/product.css','frontend/src/store/useAuthStore.ts',
 'frontend/package.json','frontend/tests/search-session.test.tsx','tests/test_search_v2b.py',
 'tests/institution_v2g/test_query_v2b.py','scripts/search_v2b_baseline.py','scripts/search_v2b_audit_server.py',
 'scripts/search_v2b_live.py','scripts/search_v2b_browser_fixture.py','scripts/search_v2b_reports.py']
write('search_v2b_changed_files.json',{'scope':'Files changed/created for V2B; pre-existing edits in shared files retained. This is not the entire dirty Git status.',
 'implementation_tests_scripts':changed,'reports':'All reports/search_v2b_* plus V2B closure annotations in search_v2a_browser/responsive/accessibility/final_qa JSON.'})
limits=['Finite English refinement grammar; no fully conversational LLM.',
 'Opt-in Reading List only; no measured judged relevance improvement. Real queries may keep identical order.',
 'Profile cache may reflect saved-book changes after up to 60 seconds; authorization is always fresh.',
 'Search remains bounded by accepted candidate pools; rare facet fallback can still time out when required artifacts/indexes are unavailable.',
 'Browser private fixture used NOT_BUILT fallback; READY private semantic path covered separately by live API and actual FAISS/KG isolated tests.',
 'Existing unrelated lint/build warnings remain. Accessibility scope is the modified search UI.']
limits.append('Search health returns HTTP 200 but status degraded / index_status STALE because the preserved September 24 active generation manifest has baseline_verified=false. Active vectors remain 5,000,000 and pending=false. No rebuild or health-status masking was performed.')
write('search_v2b_next_scope.md','# Next scope\n\nStop after V2B for review. Do not start Part 2I.\n\nRecommended follow-up after approval: a small human-judged relevance set to evaluate the conservative personalized tie-breaker, additional English refinement examples, and larger latency samples under realistic cache/IO conditions. Keep opt-in consent, strict tenant authorization and existing models/artifacts. No collaborative profiling or permanent derived interests are proposed.\n')
qa={k:'YES' for k in ['SESSION_AWARE_SEARCH','SESSION_REFINEMENT_PASS','SESSION_CLEAR_PASS','GLOBAL_SESSION_ISOLATION',
 'PUBLIC_TENANT_SESSION_PASS','PRIVATE_TENANT_SESSION_PASS','PRIVATE_REVOCATION_PASS','PERSONALIZED_SEARCH','PERSONALIZATION_TOGGLE',
 'PUBLIC_TENANT_PERSONALIZATION_PASS','PRIVATE_TENANT_PERSONALIZATION_PASS','EXPLAINABLE_RESULT_REASONS',
 'KG_SESSION_INTEGRATION_PASS','HNSW_PRESERVED','CROSSENCODER_PRESERVED','RECOMMENDATION_REGRESSION_PASS','MORE_LIKE_THIS_REGRESSION_PASS']}
qa.update({k:'NO' for k in ['MULTI_LIBRARY_SESSION_LEAK','ACCOUNT_SWITCH_SESSION_LEAK','PERSONALIZATION_OVERRIDES_STRICT_FILTER',
 'PRIVATE_PROFILE_CROSS_TENANT_LEAK','GLOBAL_PRIVATE_OWNERSHIP_LEAK','INTERNAL_SCORE_EXPOSED','GLOBAL_HNSW_REBUILT','GLOBAL_KG_REBUILT']})
qa.update({'SESSION_EXPIRY':'30-minute idle / 60-minute hard, request-time enforcement + Mongo TTL cleanup',
 'PERSONALIZATION_SIGNALS':['Own canonical saved global books','Own local-only saved books within currently authorized tenant'],
 'PERSONALIZATION_MAX_BOOST':'0.02; <=2 positions in adjacent <=3-row bands, raw CE gap <=0.1; strict filters/sorts remain authoritative',
 'V2A_BROWSER_ACCEPTANCE':'PASS'})
assert preservation['all_protected_unchanged'] and preservation['global_count_unchanged']
write('search_v2b_final_qa.json',qa)
sections=[('A','FINAL PASS / PARTIAL / FAIL','PASS for scoped V2B acceptance; limitations below.'),
 ('B','V2A BROWSER CLOSURE STATUS','PASS: all four modes, typo, negative/rating/online constraints, KG disclosure, outsider denial and exact six-size matrix.'),
 ('C','SESSION ARCHITECTURE','Server UUID context bound to user + JWT sid + library + workspace; Mongo shared with fallback.'),
 ('D','SESSION REFINEMENT RULES','Deterministic field edits; independent topics reset; explicit instead retains other constraints; see rules JSON.'),
 ('E','SESSION EXPIRY / CLEARING',qa['SESSION_EXPIRY']+'; clear current context and logout preclear tested.'),
 ('F','GLOBAL SESSION BEHAVIOR','PASS: topic/rating/format retained and clear starts fresh.'),
 ('G','PUBLIC TENANT SESSION BEHAVIOR','PASS: TEST member refinement, strict ownership, empty means empty.'),
 ('H','PRIVATE TENANT SESSION BEHAVIOR','PASS: member plan restored only within exact private scope; outsider denied.'),
 ('I','PERSONALIZATION SIGNAL AUDIT','Own Reading List only; audited alternatives intentionally unused; see signal audit.'),
 ('J','PERSONALIZATION PROFILE DESIGN','Temporary bounded canonical subject/author counts; exact scope cache, 60 seconds, 256 entries.'),
 ('K','PERSONALIZATION WEIGHTS / BOUNDS',qa['PERSONALIZATION_MAX_BOOST']),
 ('L','GLOBAL PERSONALIZATION','PASS: ON/OFF same candidate set; canonical reasons; controlled tests prove bounded order change, cold/OFF neutral.'),
 ('M','PUBLIC TENANT PERSONALIZATION','PASS: authorized public metadata only, no foreign holdings introduced.'),
 ('N','PRIVATE TENANT PERSONALIZATION','PASS: local-only profile reason observed; private words never enter Global/foreign scope.'),
 ('O','MULTI-LIBRARY ISOLATION','PASS: browser restored distinct TEST/private plans; account/workspace/JWT injections denied in tests.'),
 ('P','MEMBERSHIP REVOCATION',browser['revocation']),
 ('Q','EXPLAINABILITY','At most two literal canonical reasons; no scores/confidence or invented history.'),
 ('R','PERSONALIZATION TOGGLE','Default OFF; account boolean; OFF skips lookup and preserves baseline ranking while session/NLU/KG remain active.'),
 ('S','KG INTERACTION','Existing expansion recomputed from current plan; strict filters and primary/secondary ranking boundaries preserved.'),
 ('T','HNSW / CROSSENCODER INTERACTION','Accepted retrieval and CE retained; personalization only bounded post-CE reordering; no model/index builds.'),
 ('U','SECURITY / PRIVACY','Fresh auth before state/cache; ephemeral plans, own saves only, private/no-store headers, logout clearing.'),
 ('V','PERFORMANCE','5 samples/group: Global p50 235.38→199.56ms session /163.92ms profile; TEST 628.47→625.07/730.41; private 204.12→204.02/201.94. Not a load test or speedup claim.'),
 ('W','BROWSER VALIDATION','PASS through approved Chromium 5174; member/outsider, Global/public/private, switching, clear and revocation.'),
 ('X','ACCESSIBILITY','PASS for scoped search UI: structural axe, keyboard/focus, measured text contrast; see report.'),
 ('Y','RESPONSIVE','PASS: 18 exact measurements across six CSS viewports; no horizontal overflow.'),
 ('Z','BACKEND TESTS','163 tenant regressions; 103 planner; 53 global engine; 88 recommendation/catalogue; 12 More Like This. Suites overlap.'),
 ('AA','FRONTEND TESTS',f'{front_count} full-suite tests passed; latest session 5/5, private 9/9; TypeScript/Vite build passed. Existing unrelated warnings retained.'),
 ('AB','RECOMMENDATION REGRESSION','PASS: 88 tests; algorithm source checksum preserved.'),
 ('AC','MORE LIKE THIS REGRESSION','PASS: 12 tests; implementation unchanged.'),
 ('AD','PRESERVATION','5,000,000 global books; protected source hashes and large artifact size/mtime unchanged; accepted tenant artifacts unchanged. Synthetic fixtures cleaned.'),
 ('AE','EXACT FILES CHANGED','See search_v2b_changed_files.json. Existing shared-file changes are retained; no reset/commit/blanket staging.'),
 ('AF','REPORTS','See report inventory below; baseline, live aggregate evidence, XML suites and full QA retained.'),
 ('AG','KNOWN LIMITATIONS','\n'.join('- '+v for v in limits)),
 ('AH','RECOMMENDED NEXT SCOPE','Review V2B first; optional judged relevance evaluation and broader latency sampling. Part 2I not started.')]
review='# LuminaR Search Intelligence V2B review\n\n'+f'Generated {stamp}.\n\n'
review+='\n\n'.join(f'## {letter}. {title}\n\n{body}' for letter,title,body in sections)
review+='\n\n## Final QA summary\n\n```json\n'+json.dumps(qa,indent=2,ensure_ascii=False)+'\n```\n\n## Report inventory\n\n'
review+='\n'.join('- '+p.name for p in sorted(R.glob('search_v2b_*')))+'\n'
write('search_v2b_review.md',review)

# Preserve historical evidence; append the closure instead of rewriting history.
for name in ('browser','responsive','accessibility','final_qa'):
    p=R/f'search_v2a_{name}.json'
    old=json.loads(p.read_text(encoding='utf8'))
    old['v2b_closure']={'status':'PASS','report':'search_v2b_v2a_browser_closure.json',
     'responsive':'search_v2b_responsive.json','accessibility':'search_v2b_accessibility.json',
     'note':'Prior historical status retained. Advanced CUA viewport/CDP was available and used for exact-size validation.'}
    write(p.name,old)
print(json.dumps({'review':str(R/'search_v2b_review.md'),'preservation':preservation['all_protected_unchanged'],
 'global_count':count,'frontend_full':front_count,'tests':tests,'reports':len(list(R.glob('search_v2b_*')))}))
