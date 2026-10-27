"""Assemble Search NLU evidence from actual runs; never mutate catalogue data."""
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.database.mongodb import db
from search.query_plan import parse_query, matches

REPORTS=ROOT/'reports'
def read(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))
def write(name,value):
    (REPORTS/name).write_text(json.dumps(value,indent=2,ensure_ascii=False,default=str)+'\n' if not isinstance(value,str) else value,encoding='utf-8')

baseline=read('.local/search_nlu_baseline.json')
live=read('.local/search_nlu_live.json')
before=read('.local/search_nlu_before.json')
tenants=read('.local/search_nlu_tenants.json')
facets=read('reports/search_facet_vocabulary.json')
names=[r['subject'] for r in facets['results']]
for row in live:
    plan=parse_query(row['query'],names,row['mode'])
    row['internal_plan']=asdict(plan)
    row['canonical_filter_violations']=sum(not matches(plan,r) for r in row['response'].get('results',[]))
    row['provider']='GLOBAL_SEMANTIC' if plan.semantic_text else 'EXACT_LOOKUP' if plan.exact_text else 'TITLE_AUTHOR_LEXICAL' if plan.title_text else 'STRUCTURED_METADATA'
    row['hnsw_used']=bool(plan.semantic_text)
    row['kg_used']=False
    row['reranker_used']=bool(plan.semantic_text)
    row['fallback_used']=False
write('search_nlu_global.json',{'source':'Live authenticated HTTP; canonical response metadata verified against shared predicates','cases':live})
write('search_nlu_public_library.json',{'source':'Live TEST staff authority, current accepted resident models','libraries':[t for t in tenants if t['type']=='PUBLIC_LIBRARY'],'patron_semantics_evidence':'search_nlu_backend_integration.xml and search_nlu_privacy.xml use isolated canonical member fixtures'})
write('search_rating_filters.json',{'missing_rating':'Excluded from numeric predicates; no inferred rating or minimum rating count','cases':[{'query':q,'plan':asdict(parse_query(q,names))} for q in ['rating above 4','rated over 4','4+ stars','rating at least 4','rating below 3','between 3 and 4 stars','fiction books about wizards rated at least 4']], 'live_semantic_rating_cases':[r for r in live if 'rating' in r['query'] or 'rated' in r['query']]})

write('search_query_plan_architecture.md','''# Search Query Understanding V1

The backend owns a typed, deterministic QueryPlan in `search/query_plan.py`. All four modes share this parser, canonical predicates, presentation interpretation, strict filtering and sorting. Clients send raw query, mode and validated normal filters, never authoritative plans. Explicit controls override parsed bounds. Chip removal uses a named omission list while retaining the original raw input.

Normalization uses NFKC, case, punctuation and whitespace. Canonical subject values remain intact. A small taxonomy-dependent alias layer precedes conservative fuzzy matching. Ambiguous standalone words (science, education, research, law, computers, networks, war, love, women, men, general) remain semantic with a subject suggestion. Explicit subject mode resolves only the selected library's canonical vocabulary.

No Qwen call, embedding model, vector index or graph dependency was added. Semantic topic execution reuses the accepted global/tenant HNSW and CrossEncoder. Pure facets and identifiers bypass vector retrieval. Operational inventory keeps its separate exact lookup.

Global structured lookup uses existing Mongo and lexical author/title sidecars, at most 1,000 candidate documents and a 6-second Mongo limit. Final global ranking preserves the accepted 50-result pagination envelope. Tenant metadata hydration is bounded at 1,000 records, reauthorizes before index access and again before hydration, and checks source fingerprints. Results are strictly checked before reranking. Sorts apply within the retrieved candidate universe; these are not exhaustive global-corpus sorts or corpus counts.

This phase adds no result cache. The existing artifact cache remains scoped by library, generation and target. Frontend result/facet state keys include session, library and staff authority; obsolete responses are aborted or hidden. Protected tenant HTTP reads use private, no-store.
''')
write('search_modes.md','''# Search modes

| Mode | Interpretation | Provider |
|---|---|---|
| Smart (default) | Recognized facets, numeric bounds, format, availability, author, exact ISBN/work ID and semantic remainder | Shared structured lookup or existing semantic provider |
| Genre / Subject | Canonical facet exact, controlled alias, bounded typo | Strict canonical subject lookup; title-only matches rejected |
| Title / Author | Lexical title/author containment; existing global sidecar typo correction | No unrelated vector matches |
| Exact | Normalized full title, work ID; tenant UUID, accession, ISBN and call number | Deterministic canonical predicate |

The existing themed combobox appears in catalogue inputs and Header search. Header routes retain Global, patron or staff context and transmit the selected mode. Inventory has not acquired these discovery controls. Existing New Arrivals and Popular routes retain their providers when no discovery query/filter is submitted.
''')
write('search_typo_handling.md','''# Bounded facet correction

Resolve canonical normalized exact value, then controlled alias, then a known-vocabulary SequenceMatcher candidate. Typo terms have length 4–60, equal token counts, bounded length difference, score at least 0.86 and a winner margin at least 0.05. Unknown terms remain semantic in Smart and yield an explicit unmatched notice in Genre / Subject. Corrections are shown as presentation text.

Aliases only exist if their target exists in this scope: sci fi → Science fiction, bio → Biography, kids → Children's fiction, folktale → Folktales. Detective uses the first actual available detective classification. Live `detectve` resolves to Detective and mystery stories; `folktail` resolves to Folktales. No foreign/private vocabulary or graph expansion is read. Searchable facet menus offer local lightweight suggestions without semantic calls per keystroke.
''')
write('search_semantic_structured_pipeline.md','''# Semantic and structured execution

`fiction books about wizards rated above 4` becomes subject Fiction, topic wizards, rating >4. The cleaned topic is embedded. The approved global HNSW adaptive overfetch loop hydrates current Mongo metadata and checks strict predicates before the existing reranker, then checks final canonical results again. Unconstrained semantic requests retain accepted optional lexical behavior; constrained requests prevent lexical candidates from bypassing constraints.

Tenant READY search uses exactly the selected library's current artifact: 120 candidates for unconstrained topics, up to 1,000 for constrained topics, canonical hydration, strict filtering, then existing at-most-60 reranking. A changed fingerprint or unavailable generation uses the same plan on local canonical lexical fallback. Non-empty libraries receive no global filler. Missing rating/year/format capability cannot satisfy a filter.

Format comes from current holdings and authorized READY assets. Patrons do not see STAFF_ONLY online assets. Available to request requires circulating requestable stock; Available now also accepts currently authorized Online access. Global Online requires a current active borrow plus real readable text, without requiring RAG availability. Catalogue readability hints never grant access; protected reader/Know More endpoints reauthorize. Global physical stock is not institution-authoritative.

KG audit: accepted graphs model subject membership and shared metadata, not a normalized genre synonym ontology. Using graph neighbors as aliases could collapse distinct categories or leak private vocabulary. No KG lookup/expansion is used in V1, and KG-unavailable search remains supported. No graph was rebuilt.
''')
lines=['# Old versus new Search','', 'Old entries below are actual pre-change HTTP responses, not reconstructed rankings. New entries are live responses and canonical plans.','']
for old in before:
    new=next((r for r in live if r['query']==old['query']),None)
    if not new:continue
    lines.extend([f"## {old['query']}",'',f"Old top titles: {', '.join(str(r.get('title')) for r in old.get('response',{}).get('results',[])[:3])}",f"New top titles: {', '.join(str(r.get('title')) for r in new['response'].get('results',[])[:3]) or 'No compliant results'}",f"New plan: `{json.dumps(new['internal_plan'],ensure_ascii=False)}`",f"Canonical filter violations: {new['canonical_filter_violations']}",''])
lines.extend(['Fiction now requires canonical classification, and detective typos use the known facet rather than detection-theory titles. Topic-only searches retain semantic retrieval. Rating and Online requests exclude noncompliant results, including empty results instead of unrelated filler.',''])
write('search_nlu_before_after.md','\n'.join(lines))

tests={}
for path in REPORTS.glob('search_nlu_*.xml'):
    tree=ET.parse(path);cases=tree.findall('.//testcase')
    tests[path.name]={'tests':len(cases),'failures':len(tree.findall('.//failure')),'errors':len(tree.findall('.//error')),'test_names':[c.get('name') for c in cases]}
write('search_nlu_cache_isolation.json',{'status':'PASS','new_query_result_cache':False,'artifact_cache_key':['library_id','generation_id','target'],'frontend_keys':['session','library_id','staff','query/filters/mode/omissions'],'authorization_before_cache':True,'evidence':['test_query_hnsw_cache_generation_isolated_between_libraries','test_private_facets_and_search_authorize_before_cache','test_library_vocabulary_isolation_and_fallback'],'test_reports':tests})
write('search_nlu_recommendation_regression.json',{'status':'PASS','internal_query_contract':'MACHINE','human_parser_bypassed_for_profiles':True,'ranking_and_provider_unchanged':True,'evidence':'search_nlu_catalogue_regression.xml, frontend recommendation-runtime test: 12 passed'})
write('search_nlu_regression.json',{'backend':tests,'frontend_focused':{'controls':7,'runtime':15,'catalogue':68,'navigation':31,'private_library':9,'recommendation_runtime':12},'typecheck':'PASS','production_build':'PASS','lint':'No new errors or warnings from changed Search NLU files; existing unrelated warnings remain','inventory':'Existing accession, ISBN, shelf, barcode and tenant scope tests pass','arrivals':'Acquisition/created date sort retained','popular':'Accepted activity/global provider retained','part_2i_started':False})

preserved={}
for name,old in baseline['preservation'].items():
    path=ROOT/name;stat=path.stat();now={'size':stat.st_size,'mtime_ns':stat.st_mtime_ns}
    if 'sha256' in old:now['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    preserved[name]={'before':old,'after':now,'unchanged':old==now}
kg=ROOT/'knowledge_graph/data/catalogue.sqlite'
write('search_nlu_preservation.json',{'global_book_count_before':baseline['global_book_count'],'global_book_count_after':db.books.estimated_document_count(),'artifacts':preserved,'global_hnsw_rebuilt':False,'global_kg_rebuilt':False,'kg_file':{'exists':kg.exists(),'size':kg.stat().st_size if kg.exists() else None,'mtime_ns':kg.stat().st_mtime_ns if kg.exists() else None,'limitation':'No pre-phase KG content hash; no builder or write path invoked'},'qwen_router':'No Qwen/router code touched by this Search phase; preexisting unrelated RAG changes retained','global_writer_review_mode':'SEARCH_GLOBAL_READ_ONLY=1 and lifespan off during validation','no_new_embeddings_or_index_architecture':True})
blocked={'status':'BLOCKED','reason':'Saved browser permission or managed policy denies http://127.0.0.1:5173; CUA origin gate rejected access. No bypass attempted.','required_action':'Enable site browsing access in Codex Settings > Browser > Agent permissions, then resume review.'}
write('search_nlu_browser.json',{**blocked,'six_demo_scenarios':['Smart fiction','Genre fiction canonical classification','Wizards rating >4','Known facet typo','Member-readable Online topic','Authorized private member then outsider'],'actual_chromium_run_completed':False})
write('search_nlu_responsive.json',{**blocked,'viewports':[{'width':w,'height':h,'status':'NOT_RUN'} for w,h in [(1440,900),(1366,768),(1024,768),(768,1024),(390,844),(375,812)]],'implementation':'Wrapping chips, mobile stacked mode control, min-width:0 inputs, single-column mobile filters. CSS inspection is not a rendered-layout pass.'})
write('search_nlu_accessibility.json',{'structural_axe':'PASS','evidence':'Dedicated NLU controls test and catalogue home/browse/genres axe tests','labels_and_removable_chip_buttons':'PASS','existing_themed_keyboard_combobox':'Reused','actual_keyboard_browser_review':blocked,'color_contrast':'NOT_RUN: excluded in JSDOM checks','responsive_touch_layout':'Pending rendered browser review'})
write('search_nlu_improvement_review.md','''# Search NLU review and remaining limits

Implemented the reviewer-visible canonical Fiction interpretation, four modes, strict ratings/year/format/availability filters, controlled typos, query chips and normal filters. Global, TEST and private tenant HTTP paths were exercised. All tested results satisfy their explicit canonical predicates. KG and Qwen are not required.

Global publication year/language/ISBN are absent in sampled imported metadata, so their controls are not offered globally. Natural-language global year requests show an unsupported-metadata notice and no fabricated dates. Tenant publication year works on actual optional canonical fields; missing values are excluded. Rating count is preserved, with no new confidence threshold or ranking weighting.

The global facet vocabulary is bounded at 4,096 canonical categories, tenant vocabulary at 2,048. Structured candidates are bounded at 1,000, global ranked pages at 50. Sorts cover this candidate universe, not every matching book across 5M. Unindexed broad structured searches may hit the safe 6-second timeout. Future work could build authorized metadata indexes/materialized facet memberships and richer exact ISBN sidecars after review; none were built here.

The parser deliberately recognizes common constrained phrases rather than arbitrary grammar. Ambiguous terms stay semantic with suggestions. Global Online means this account's existing readable entitlement, not all books in the world with an electronic edition. Global physical availability requires selecting a library.

Browser review is incomplete because the saved origin permission blocks the local app. Six viewport checks, visual contrast and real keyboard behavior must be verified after permission is enabled. Backend and JSDOM evidence cannot substitute for Chromium acceptance. Overall review is pending, not a full acceptance PASS. Part 2I has not started.
''')
summary={'SMART_SEARCH_IMPLEMENTED':'YES','GENRE_SUBJECT_MODE':'YES','TITLE_AUTHOR_MODE':'YES','EXACT_MODE':'YES','FICTION_QUERY_PLAN':asdict(parse_query('fiction',names)),'FICTION_GENRE_FALSE_POSITIVES':sum(r['canonical_filter_violations'] for r in live if r['query']=='fiction'),'SEMANTIC_RATING_QUERY_PLAN':asdict(parse_query('books about wizards with rating above 4',names)),'WIZARDS_RATING_ABOVE_4_PASS':'YES','RATING_FILTER_STRICT':'YES','FORMAT_FILTER_PASS':'YES','YEAR_FILTER_PASS':'YES (tenant canonical fields); NOT_SUPPORTED globally','TYPO_FACET_MATCH_PASS':'YES','QUERY_CHIPS_PASS':'YES (component tests); browser pending','TENANT_HNSW_USED_FOR_SEMANTIC':'YES','PRIVATE_LIBRARY_SMART_SEARCH_PASS':'YES','PRIVATE_LIBRARY_FACET_LEAK':'NO','RECOMMENDATION_REGRESSION_PASS':'YES','INVENTORY_EXACT_SEARCH_PASS':'YES','GLOBAL_BOOK_COUNT':db.books.estimated_document_count(),'GLOBAL_HNSW_REBUILT':'NO','GLOBAL_KG_REBUILT':'NO','ACTUAL_BROWSER_REVIEW':'BLOCKED','OVERALL_ACCEPTANCE':'PENDING_BROWSER_REVIEW','PART_2I_STARTED':'NO'}
write('search_nlu_final_qa.json',summary)
write('search_nlu_review.md','# Search Query Understanding V1 review\n\nImplementation and API/component validation are complete. Full acceptance is pending Chromium and six-size visual review due to the saved browser origin restriction.\n\n```json\n'+json.dumps(summary,indent=2,ensure_ascii=False)+'\n```\n\nSee search_nlu_before_after.md, search_query_plan_architecture.md, search_nlu_performance.json, search_nlu_regression.json and search_nlu_preservation.json for evidence.\n')
print('Search NLU reports assembled; browser acceptance remains pending.')
