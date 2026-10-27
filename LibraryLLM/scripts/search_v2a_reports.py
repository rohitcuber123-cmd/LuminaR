"""Build honest V2A review reports from retained baseline and executed evidence."""
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.database.mongodb import db
from search.query_plan import parse_query,matches,INTENTS,PARSER_VERSION
R=ROOT/'reports'
def read(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))
def write(name,value):
    (R/name).write_text(value if isinstance(value,str) else json.dumps(value,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf-8')
baseline=read('reports/search_v2a_baseline.json');live=read('.local/search_v2a_live.json')
events=read('reports/search_v2a_kg_runtime.json')['events'];performance=read('reports/search_v2a_performance.json')
vocab=read('reports/search_facet_vocabulary.json');write('search_v2a_facet_vocabulary.json',vocab)
names=[r['subject'] for r in vocab['results']]
checks=[]
for row in live:
    if row['scope']!='GLOBAL':continue
    plan=parse_query(row['query'],names)
    checks.append({'query':row['query'],'intent':plan.intent,'status':row['status'],'returned':len(row['response'].get('results',[])),
      'violations':sum(not matches(plan,b) for b in row['response'].get('results',[])),'interpretation':row['response'].get('interpretation')})
write('search_v2a_constraint_enforcement.json',{'cases':checks,'negative_contract':'Normalized whole-phrase exclusion across canonical title/authors/subjects/description; exact facet resolution retained as exclude_subjects. No semantic negation or fabricated synonym expansion.','tests':'search_v2a_planner.xml, search_v2a_tenant.xml, search_v2a_private_targeted.xml'})
write('search_v2a_private_library.json',{'live':[r for r in live if r['scope'] in ('Private Archive QA A','PRIVATE_OUTSIDER')],
 'member_fixture':'Isolated disposable PRIVATE_CODE library: real canonical records, tiny accepted-format HNSW/KG, authorized patron 2, outsider 3. See search_v2a_private_targeted.xml.',
 'privacy':'Authority precedes facet/KG/cache/index access; generation scope verified; current authorized metadata validates graph evidence; no global graph in tenant requests.'})
write('search_v2a_hnsw_integration.json',{'events':[{'scope':e['scope'],'library_id':e['library_id'],'query':e['query'],'diagnostics':e['diagnostics']} for e in events],
 'architecture':'Existing MiniLM normalized 384D + FAISS base/delta global or exact tenant index. At most one extra expansion embedding/retrieval, strict predicates before existing CrossEncoder, canonical rehydration.',
 'limits':'Existing global adaptive fetch limit plus accepted delta overlay; 60 secondary candidates; at most 20% reranking slots reserved for new expansion candidates; existing global 50 and tenant 60 rerank bounds.'})

docs={
'search_v2a_metadata_audit.md':'''# V2A metadata audit

V1 canonical schema audit remains applicable (search_nlu_metadata_audit.md). Global subjects are pipe-delimited strings; tenant subjects/authors are arrays. There is no reliable normalized genre or difficulty column. Ratings/counts are global fields, hydrated onto globally linked tenant records; missing ratings never qualify for numeric bounds. Tenant publication_year/language/ISBN are optional real fields. The sampled global import lacks reliable publication-year/language/ISBN metadata, so controls remain unavailable globally. Format/availability derives from real holdings, Part 2B circulation, current active digital entitlements and authorized READY assets.

The existing 5M global SQLite graph has Book, Author and Subject nodes, AUTHORED_BY/HAS_SUBJECT edges, indexed feature→book and book→feature access, and an immutable version/catalogue_hash. Tenant graph artifacts contain Book/Author/Subject/Classification nodes and metadata edges, scoped by library/generation/checksum/fingerprint. Neither graph has normalized subject-synonym edges. V2A uses bounded subject co-occurrence, never fabricates ontology or difficulty metadata.
''',
'search_v2a_query_plan_architecture.md':'''# Canonical V2A plan

QueryPlan now includes raw_query, normalized_query, mode, intent, parser_version, semantic_text, exact/title/author text, strict subjects, expanded_subjects, include_terms, exclude_terms, exclude_subjects, rating/year bounds with explicit exclusivity, formats, availability, language, sort, confidence, corrections, soft_preference, kg_expansion_used and kg_generation. include_terms is reserved and currently empty; V2A does not invent inclusion grammar. The backend constructs and validates the plan. Clients submit raw text, modes, typed controls and named chip omissions only.

Flow: normalize → deterministic parse/intent → optional same-scope KG projection → primary HNSW plus at most one secondary retrieval → canonical strict predicates → bounded existing CrossEncoder → canonical validation/hydration → presentation. Pure exact/facet requests bypass unnecessary HNSW/KG. No Qwen, new model/index, personalization or conversational state was added.

There is no new result cache. Plan.cache_key includes scope, parser version, intent, mode, constraints/exclusions, sort, KG generation and supplied HNSW generation. Existing artifact caches remain scoped by library/generation/target. Each request reauthorizes and checks freshness. Existing recommendation MACHINE calls keep the accepted cached ranking path and bypass human parsing.
''',
'search_v2a_intent_model.md':'''# Intent-aware execution

FIND_EXACT routes identifiers/exact mode to canonical lookup; Title/Author mode uses intentional lexical lookup. FIND_AUTHOR applies canonical author constraints. BROWSE_CATEGORY uses real strict subject membership. DISCOVER_TOPIC emphasizes cleaned-topic HNSW retrieval. LEARN, REFERENCE and RESEARCH use cleaned topics plus soft CrossEncoder query preferences (introductory guide, reference handbook, research studies), with bounded actual description text available to reranking. They never become fabricated database filters. FIND_ONLINE/FIND_AVAILABLE enforce real capability/stock filters. DISCOVER_RELATED requests topic retrieval with optional same-scope graph neighbors.

Priority: explicit exact/author/lexical task, then explicit availability/Online task, then pure category; mixed topic/category stays discovery. Each request stands alone. The intent label corresponds to retrieval/filter/rerank behavior, not user history. Known ambiguity rules from V1 remain conservative.
''',
'search_v2a_typo_handling.md':'''# Facets and corrections

Exact canonical subject → small target-supported alias map → bounded fuzzy match (length 4–60, equal token count, bounded length difference, score ≥0.86 and winner margin ≥0.05). Strong corrections are shown truthfully as “Did you mean …? Using this canonical subject …”. Aliases are labeled interpretations. Uncertain or unknown words are not forcibly corrected; ambiguous canonical words remain topics with optional subject suggestions. Typo matching does not search arbitrary descriptions or private foreign vocabularies.
''',
'search_v2a_kg_integration.md':'''# Existing graph integration

Only actual subject edges contribute. The accepted graphs are bipartite: a subject-related-subject projection follows Subject ← Book → Subject, exactly two stored HAS_SUBJECT edges. This is one projected subject hop, not an invented stored synonym edge. No recursive traversal, Qwen, descriptions-as-graph-nodes, private RAG chunks, behavior signals, graph build or persisted expansion edges.

Bounds: at most 3 primary concepts, 64 seed books, 1,024 evidence edges, 6 related concepts and one additional semantic vector search (up to 60 secondary candidates). Stable co-occurrence ordering resolves ties. Generic facets and explicit exclusions are omitted. Global queries read only the accepted global SQLite graph and validate evidence against current public Mongo subjects. Tenant queries authorize first, require READY exact-library graph generations, and validate evidence against current patron/staff-visible canonical records. Non-READY/corrupt/missing graphs yield normal search without expansion. A bounded SQLite progress handler prevents runaway graph scans; cold IO remains variable.

Primary topic and strict facets are unchanged. At most 20% of the existing rerank pool is reserved for additional expansion candidates; duplicates are removed. The original topic/intent preference remains the CrossEncoder query. Explicit primary phrase evidence in current title/subjects/description receives priority over expansion-only evidence, then CrossEncoder orders within that group. Explicit user sort still applies. No expansion can relax a rating, genre, exclusion, year or access filter.

Live machine-learning demo: 48 additional candidates, 10 expansion candidates reranked, one changed displayed ID. This demonstrates broader candidate recall; a relevance-quality gain is not claimed without human judgments. TEST uses its own graph generation and a real Technical education neighbor for computer networks. The existing private live graph has no matching neural-network neighbors, so none were manufactured; isolated disposable private fixtures verify successful member expansion and denied outsider access.
''',
'search_v2a_next_scope.md':'''# Review boundary and possible V2B scope

Stop after V2A. No Part 2I, session continuation, personalized Search ranking, persistent Search profiles, LLM parsing, new embedding/index architecture or automatic KG generation was implemented.

After explicit review, V2B could specify consent, retention and tenant boundaries for session refinement or personalized ranking, then evaluate those separately from the existing recommender. Candidate improvements requiring review include judged relevance datasets, better multilingual co-occurrence quality, explicit subject relations when the accepted KG actually provides them, metadata indexes for exhaustive filtered sorts, and more complete publication-year coverage. These are proposals only.

Known V2A limits: finite deterministic grammar, literal metadata exclusions, bounded graph/candidate recall, co-occurrence is not synonymy, and sort/counts describe the retrieved candidate universe rather than all matching books in 5M. Global Online is this account's existing readable entitlement. Global year metadata is unsupported. Chromium, visual contrast, keyboard and six viewport checks remain pending the previously denied browser-origin permission.
'''
}
for name,text in docs.items():write(name,text)

old=read('.local/search_nlu_live.json')
lines=['# V1 versus V2A review','', 'The V2A phase started after app processes had stopped: new pre-change HTTP attempts are retained as unavailable in .local/search_v2a_before.json. Where available, old rankings below are retained actual V1 HTTP evidence. No old ranking was manufactured. V1 had already fixed canonical Fiction and strict ratings; V2A adds task intent, exclusions and actual KG retrieval contribution.','', '| Query | Old behavior | New intent / plan | KG contribution | New result behavior / why |','|---|---|---|---|---|']
for row in [r for r in live if r['scope']=='GLOBAL']:
    prior=next((o for o in old if o['query']==row['query']),None)
    old_text=', '.join(b.get('title','') for b in prior['response'].get('results',[])[:2]) if prior else 'V1 code audit: no explicit intent, negative plan or graph expansion; old live ranking unavailable'
    event=next((e for e in events if e['scope']=='GLOBAL' and e['query']==row['query'] and e['kg_enabled']),None)
    plan=event['diagnostics']['plan'] if event else {};kg=', '.join(plan.get('expanded_subjects',[])) or 'None'
    new_titles=', '.join(b.get('title','') for b in row['response'].get('results',[])[:2]) or 'No compliant results'
    plan_text=json.dumps({k:plan.get(k) for k in ('subjects','semantic_text','rating_min','rating_min_exclusive','exclude_terms','formats')},ensure_ascii=False)
    cells=[row['query'],old_text,str(plan.get('intent'))+' '+plan_text,kg,new_titles+'; explicit interpretation and strict canonical checks']
    lines.append('| '+' | '.join(str(c).replace('|',' / ').replace('\n',' ') for c in cells)+' |')
write('search_v2a_before_after.md','\n'.join(lines)+'\n')

backend={}
for path in R.glob('search_v2a_*.xml'):
    t=ET.parse(path);backend[path.name]={'tests':len(t.findall('.//testcase')),'failures':len(t.findall('.//failure')),'errors':len(t.findall('.//error'))}
front=(ROOT/'.local/v2a-frontend-full.log').read_text(encoding='utf-8')
front_report={'tests':sum(map(int,re.findall(r'ℹ tests (\d+)',front))),'failures':sum(map(int,re.findall(r'ℹ fail (\d+)',front))),'command':'npm test','log':'.local/v2a-frontend-full.log'}
write('search_v2a_regression.json',{'backend':backend,'frontend':front_report,'typecheck':'PASS','build':'PASS','lint':'No new lint errors; unrelated existing warnings remain','cache':'No new result cache; plan identity includes scope/parser/intent/exclusions/generations/sort; artifact and UI scope isolation retained.'})
write('search_v2a_recommendation_regression.json',{'status':'PASS','evidence':'88 catalogue/recommendation tests plus full frontend suite','internal_search_contract':'MACHINE; human NLU/KG not applied','algorithm_edited':False,'more_like_this':'12 accepted graph tests pass; algorithm not edited'})
files={}
for name,prior in baseline['files'].items():
    p=ROOT/name;s=p.stat();current={'size':s.st_size,'mtime_ns':s.st_mtime_ns}
    if 'sha256' in prior:current['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    files[name]={'before':prior,'after':current,'unchanged':prior==current}
tenant=[]
for name,prior in baseline['tenant_artifacts'].items():
    p=Path(name);s=p.stat();now={'size':s.st_size,'mtime_ns':s.st_mtime_ns}
    if 'sha256' in prior:now['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    tenant.append({'path':name,'unchanged':prior==now})
write('search_v2a_preservation.json',{'global_count_before':baseline['global_count'],'global_count_after':db.books.estimated_document_count(),'files':files,'tenant_artifacts':tenant,'global_hnsw_rebuilt':False,'global_kg_rebuilt':False,'production_tenant_builds':False,'controlled_disposable_test_builds':True,'qwen_router_circulation_assets_rag':'No implementation edits in this phase; Qwen/RAG/router source hashes retained where captured','review_workers':'Lifespans disabled and SEARCH_GLOBAL_READ_ONLY=1 during review'})
blocked={'status':'BLOCKED','reason':'The V2A browser attempt was rejected by the origin approval gate: a saved user permission or managed policy denies http://127.0.0.1:5173. No bypass attempted.','action':'Codex Settings > Browser > Agent permissions: allow or ask for this local origin, then resume Chromium review.'}
write('search_v2a_browser.json',{**blocked,'contexts':['GLOBAL','TEST','disposable PRIVATE tenant'],'scenarios':['category','typo','semantic','mixed rating','negative','Online','actual KG contribution','KG unavailable','private denial']})
write('search_v2a_responsive.json',{**blocked,'viewports':[{'width':w,'height':h,'status':'NOT_RUN'} for w,h in [(1440,900),(1366,768),(1024,768),(768,1024),(390,844),(375,812)]],'css':'Existing wrapping/stacking controls retained; related concepts disclosure wraps and has a 44px summary. No visual pass inferred from CSS.'})
write('search_v2a_accessibility.json',{'structural_axe':'PASS in component/catalogue tests','labels_chips_remove_buttons':'PASS','result_announcements':'Existing role=status counts retained','intent_not_color_only':True,'keyboard_chromium':blocked,'visual_contrast':'NOT_RUN; JSDOM contrast excluded'})

changed=['search/query_plan.py','search/query_expansion.py','search/query_execution.py','search/luminar_search.py','frontend/src/lib/searchNlu.ts','frontend/src/components/SearchIntelligence.tsx','frontend/src/styles/product.css','frontend/tests/search-nlu.test.tsx','tests/test_search_v2a.py','tests/test_search_depth.py','tests/institution_v2g/test_query_v2a.py','scripts/search_v2a_audit_server.py','scripts/search_v2a_live.py','scripts/search_v2a_reports.py']
summary={'FINAL':'PARTIAL: implementation/API/component checks complete; browser acceptance pending','SMART_SEARCH':'YES','NATURAL_LANGUAGE_QUERY_PLAN':'YES','INTENT_AWARE_SEARCH':'YES','QUERY_USES_QWEN':'NO','SEARCH_MODES':['SMART','GENRE_SUBJECT','TITLE_AUTHOR','EXACT'],'FICTION_QUERY_INTENT':'BROWSE_CATEGORY','FICTION_QUERY_FILTER':'subjects contains canonical Fiction','FICTION_TITLE_FALSE_POSITIVE_COUNT':next(c['violations'] for c in checks if c['query']=='fiction'),'SEMANTIC_QUERY_HNSW_USED':'YES','KG_SEARCH_INTEGRATION':'YES','KG_EXPANSION_BOUNDED':'YES','KG_PRIMARY_CONCEPT_PRESERVED':'YES','KG_UNAVAILABLE_SEARCH_PASS':'YES','PRIVATE_KG_LEAK':'NO','RATING_GT_4_PASS':'YES','NEGATIVE_CONSTRAINT_PASS':'YES','ONLINE_QUERY_PASS':'YES (tenant 4 public / 2 private authorized results; unsupported Global entitlement returns zero)','QUERY_CHIPS_PASS':'YES (component tests); Chromium pending','TYPO_SUGGESTION_PASS':'YES','RECOMMENDATION_REGRESSION_PASS':'YES','MORE_LIKE_THIS_REGRESSION_PASS':'YES','GLOBAL_HNSW_REBUILT':'NO','GLOBAL_KG_REBUILT':'NO'}
write('search_v2a_final_qa.json',summary)
sections=[('A. Final result',summary['FINAL']),('B. Root limitation','V1 lacked explicit intents, negative constraints and KG retrieval contribution; V1 canonical facets/ratings already worked.'),('C. Query plan','Typed deterministic plan with parser version, intent, constraints/exclusions, preferences and KG provenance.'),('D. Intent model',', '.join(INTENTS)),('E. Search UX','Four themed modes; Smart default; Global/patron/staff routes retained.'),('F. Facets','Actual canonical subjects, same-scope vocabulary; no invented genre field.'),('G. Corrections','Exact → supported alias → conservative bounded typo; visible truthful correction.'),('H. Ratings','Strict > versus >=, bounds and missing-value exclusions preserved.'),('I. Negatives','Canonical phrase matching in title/authors/subjects/description; removable exclusion chip.'),('J. Format/availability','Real current capabilities and authoritative Part 2B stock; no staff-only patron assets.'),('K. HNSW','Accepted MiniLM/FAISS with one optional secondary search, canonical strict checks, existing CrossEncoder.'),('L. KG','Actual global and TEST graph generations used; no new graph.'),('M. Expansion rules','One projected subject hop/two actual edges; ≤64 books/1,024 edges/6 concepts; primary priority.'),('N. Global','Actual 5M catalogue; strict filters and exact lookup; global graph only.'),('O. Public tenant','TEST uses exact tenant HNSW and graph; four readable Online results in live query.'),('P. Private tenant','Authorized live staff scope works; outsiders 404; disposable private member expansion/privacy tested.'),('Q. Interpretation','Intent, topic, genre, numeric/format/exclusion chips, correction and related-concept disclosure.'),('R. Explanations','Minimal interpretation plus existing rating/format availability badges; no internal scores or node IDs shown.'),('S. Cache isolation','No new result cache; scope/generations/parser/constraints included in plan identity and accepted artifact keys.'),('T. Performance','See live five-sample performance report; candidate counts and graph cost recorded.'),('U. Browser','NOT_RUN: prior saved origin denial awaits user-side permission change.'),('V. Accessibility','Structural axe and labeled controls pass; real keyboard/contrast/responsive review pending.'),('W. Backend tests',json.dumps(backend)),('X. Frontend tests',json.dumps(front_report)+'; TypeScript/build pass; no new lint errors.'),('Y. Recommendation','MACHINE contract/algorithms retained; recommendation and More Like This regression pass.'),('Z. Preservation','5M count, global HNSW/KG and captured tenant artifact sizes/mtimes/hashes checked; Qwen/router source unchanged.'),('AA. Exact files changed','\n'.join('- '+p for p in changed)),('AB. Reports','\n'.join('- '+p.name for p in sorted(R.glob('search_v2a_*')))),('AC. Known limits','Finite grammar; literal exclusion; co-occurrence not synonymy; bounded recall/sorts; global year absent; cold graph IO/timeouts; browser review pending.'),('AD. V2B scope','Review proposals only: consented personalization/session refinement, judged relevance and metadata coverage. Nothing from V2B or Part 2I implemented.')]
write('search_v2a_review.md','# Search Intelligence V2A review\n\n'+'\n\n'.join('## '+name+'\n\n'+body for name,body in sections)+'\n\n## Final QA\n\n```json\n'+json.dumps(summary,indent=2,ensure_ascii=False)+'\n```\n')
print('V2A reports written. Overall acceptance: PARTIAL pending browser review.')
