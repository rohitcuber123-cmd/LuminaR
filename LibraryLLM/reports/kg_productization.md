# LuminaR KG productization validation — 2026-10-03T06:41:42.193114+00:00

A. **PARTIAL overall; product PASS.** Existing implementation verified and small gaps closed. Ontology evaluation complete; usefulness FAIL means stop at pilot. No full V2 build/promotion or KG4.

B. **Screen flow:** Book Detail → More Like This beside Reading List → loading state → up to10 inline cards → deterministic Why related → Show connection for the actual book pair → Explore full graph → existing seeded experimental Graph Lab. Live metadata, rating, availability and shelf come from Core. View and Select for AI remain available. No normal-UI similarity score or fabricated continuation. Empty: “No graph relationships are available for this title yet.” Recommend Similar fallback is an explicit separate action. Hide/refresh/retry/auth/stale behavior retained.

C. **Frontend changed this turn:** frontend/src/components/MoreLikeThisSection.tsx (empty/link wording), frontend/src/lib/knowledgeGraph.ts (optional additive trace fields), frontend/tests/kg-product.test.tsx (wording assertions). Existing BookDetailPage, RelatedBookCard/WhyRelated/BookConnectionGraph, useMoreLikeThis, BookDiscoveryMenu and card-menu placements were already implemented; no new page or duplicated query logic. Full architecture audit: kg_productization_audit.md.

D. **Backend/KG changed this turn:** assistant/kg_routing.py (two requested graph phrases), knowledge_graph/core.py (trace fields derived from published feature weights; scoring SQL unchanged), tests/test_assistant_kg.py, tests/test_kg_product.py. Added scripts/revalidate_kg_metadata.py, scripts/revalidate_kg_product.py and scripts/write_kg_productization_reports.py; .gitignore excludes the disposable test credential file. backend/routes/knowledge_graph.py is the preserved product implementation. No schema/query/ranking/model change.

E. **Endpoint:** authenticated GET /kg/books/{work_id}/more-like-this?limit=10 on Core8002; frontend /api/kg/books/{work_id}/more-like-this through the existing proxy. Canonical work_id, max50, current10. has_more=false; candidate_count is diagnostic. Excludes seed, active loans/reservations, stale/deleted/inactive candidates; seed metadata changes produce friendly409. API rehydrates live Mongo metadata and physical LIB001 inventory precedence. Topic description hashes are supported for future vetted artifacts.

F. **Qwen calls:0.** Product route tests forbid Qwen and the existing recommender. Real assistant orchestrator/HTTP adapter calls live Core with forbidden Qwen/RAG/recommender sentinels and returns10 books with0 model/recommender calls. This is not a live port8005 end-to-end request. Exact phrases “more like this”, “show related books”, “what books are connected to this?” and structured MORE_LIKE_THIS are preserved/covered.

G. **V1 preserved and active:** 5,000,000 books; 2,454,492 author-name nodes; 975,785 subject nodes; 29,406,707 edges; 5,871,624,192bytes; original build882.81s. SHA2560d5c6603f8cb5cf720b46eaac5d1cf6f1ef9952b3d668a69395cf1afb57921fc reproduced. Read-only SQLite queries. Frozen KG3 seed/evaluation/build report hashes match. Search, recommendation formula/weights/paging, assistant SHOW_MORE and Know More lifecycle/cache sources match pre-edit hashes.

H. **Metadata audit:** fresh full5M scan265.15s; all structured series/publisher/language/year/genre/format/edition/ISBN/classification aliases absent. Description34.64674% present,25.8296% usable≥20 tokens; language unknown. Full coverage/type/normalization/duplicate/degree/source-excerpt evidence: kg_v2_metadata_audit.md/json.

I. **Accepted:** existing author-name and subject-label relations in production; verified deterministic description topics only in pilot.

J. **Rejected:** absent structured relations; shelf location as semantics; created_at as publication era; title-parsed series; weak-only matches; noisy/incidental topics as production evidence.

K. **Description topics:** global bounded deterministic2–3-word TF-IDF phrase policy; refined vocabulary from full V1 subjects; original phrase/hash provenance. No LLM/new model. Refined15,642 topic-bearing books,33,736 topic edges,4,789 topic nodes. Eight topic-only recommendations survived nominal eligibility, but source-reason review fails semantic usefulness. “machine learning” is plausible; incidental “medical doctor” and French “qui est” are failures. No independent reader utility labels exist.

L. **V2 counts:** same100,040-book pilot as V1, with all40 frozen KG3 seeds. V1pilot105,107authors +93,867subjects /587,074edges. InitialV2 adds16,623topics /656,478edges. RefinedV2 adds4,789topics /620,810edges. These are pilot counts, not full5M V2 counts.

M. **Size:** V1pilot126,763,008bytes; initialV2145,911,808bytes; refinedV2138,604,544bytes. Linear refined full estimate6.93GB plus staging reserve20.78GB; degree/vocabulary/index growth can be nonlinear. Actual free disk recorded in kg_v2_build.json. Production V1 retained.

N. **Original measured build times, reused:** V1pilot10.14s; initialV2 enrichment+compaction50.09s; refined61.28s. No rebuild this turn. Full linear enrichment estimate3018.33s is a projection, not a measured build. Published pilot SQLite quick_check returnsok.

O. **Weights:** explicit knowledge_graph/relations.py author2,subject1,topic0.5; importance=1+ln((N+1)/(degree+1)); stored feature_weight=relation_weight×importance; cosine contribution=feature_weight²/(seed_norm×candidate_norm). Additive reasons expose each value, typed node IDs, predicates, original labels and source provenance; sum(contribution)=score. Runtime relation multipliers are derived from the artifact, never retroactively substituted. Ranking/ties remain score DESC / internal book_id ASC.

P. **Weak qualification:** weak-only matches cannot qualify. No publisher/language/era weak edges were built; weak-only result count0. Topics are nominally moderate in the experimental policy, so topic-only pilot pairs exist and require semantic review before promotion.

Q. **Comparable V1/V2:** identical systematic100,040-book population including all40 frozen KG3 seeds; not full5M V1 versus a small V2. IDs/order/scores exactly reproduce the earlier refined evaluation;1,224 paths verified. Mean top10 overlap0.8575; paired subject-diversity delta+0.001910 over paired seeds. Original full KG3 evidence is unchanged.

| Metric | Same-population V1 | Refined V2 |
|---|---:|---:|
| seed_coverage | 0.875 | 0.9 |
| top10_completeness | 0.775 | 0.775 |
| unique_candidates | 313 | 321 |
| mean_subject_diversity | 0.8464816758916885 | 0.8527235069104323 |
| same_seed_author_concentration_mean | 0.06 | 0.058333333333333334 |
| relationship_type_diversity_mean | 1.0124223602484472 | 1.0333333333333334 |
| reason_count_mean | 1.8850931677018634 | 1.8696969696969696 |
| generic_reason_fraction_degree_at_least_1_percent | 0.1070840197693575 | 0.10048622366288493 |
| strong_or_moderate_reason_fraction | 1 | 1 |
| topic_only_recommendations | 0 | 8 |
| latency_median_ms | 9.033049999743525 | 9.869900000012422 |
| latency_p90_ms | 34.88689999903727 | 37.554200000158744 |
| latency_p95_ms | 46.28899999988789 | 47.287599998526275 |
| latency_max_ms | 65.77560000005178 | 69.00020000102813 |

Nominal strong/moderate fraction1.0 means relation eligibility, not validated semantic quality. Mean contribution shares V1 author3.58%/subject96.42%; V2 author3.49%/subject93.73%/topic2.78%. kg_v1_vs_v2.json retains the original initial-pilot report; kg31_v1_vs_v2_subject_vocab.json retains refined evidence; kg_productization_v1_vs_v2_current.json holds the fresh reproduction.

R. **Live product latency:** first observed+3 warm authenticated Core requests per seed; metadata verification outside timing. No process-cold claim. Warm24-request median254.50ms/p902239.65ms/p952280.33ms/max2297.87ms. Broad History degree571,286 yields572,162 candidates; first finance request2675ms. High-degree expansion remains a known cost, with IDF downweighting preserved. The pilot SQLite timing table above excludes HTTP/Mongo hydration and must not be equated to product timings.

| Case | Work ID | Cards | First observed ms | Warm range ms |
|---|---|---:|---:|---:|
| finance | OL2010879W | 10 | 2675.1 | 295.9–351.9 |
| fiction/literature | OL11359361W | 10 | 687.2 | 428.9–479.7 |
| technical | OL19545719W | 10 | 706.4 | 553.2–582.0 |
| no authors | OL24712944W | 10 | 77.9 | 47.4–51.8 |
| no subjects | OL25339037W | 4 | 35.6 | 22.1–24.8 |
| isolated | OL23058018W | 0 | 18.6 | 13.7–18.9 |
| same-author | OL2000134W | 10 | 315.0 | 198.9–213.1 |
| high-degree generic subject | OL19513321W | 10 | 2651.7 | 2239.7–2297.9 |

S. **Why related examples:** Rich Dad, Poor Dad → Sharon L. Lechter/Robert T. Kiyosaki + Personal Finance/Investments → El juego del dinero; Over the side → Jean-Pierre Andrieux/Prohibition/Smuggling → Prohibition and St. Pierre. UI groups only actual path labels by relation type, with book-pair SVG and full labels. Author names remain metadata strings, not verified human identities.

T. **Responsive/live UX:** all8 categories pass frontend and live API result-count checks. Desktop2-column cards, tablet/mobile1-column; no horizontal page overflow, long title wraps, pair graph present. Requested1440×900,1366×768,768×1024,375×812; actual CSS1440×900,1366×767,767×1024,375×812 because IAB0.8 scaling rounds by1 pixel. Raw initial screenshots reflect viewport/scaling behavior; final desktop proof is kg_productization_desktop_results.png. Temporary viewport reset. Seeded Graph Lab loaded10 recommendations and author-node inspection displayed actual connected books. Browser report: kg_productization_browser_checks.json. No production account/circulation mutation; disposable validation identity cleaned up.

U. **Tests:** backend385pass/1 unchanged failure; targeted frontend129pass; standard frontend31routing/read-now+81assistantpass (81assistant overlap the targeted run;160 distinct frontend cases). Covers identity/limits/freshness/availability/paths/empty/determinism/zero-Qwen, phrase routing, search depth, SHOW_MORE, read-now routing and private document cache/access. Collection hashes unchanged during live read-only validation. Logs named kg_productization_*_tests.log.

V. **Build/lint:** production TypeScript+Vite buildPASS; lint exit0 with19 existing warnings. No new dependency.

W. **Known failures/limits:** unchanged tests/test_rag_query_types.py::test_overview_rule_never_accepts_added_premises[What are the major themes of this book?]. Existing19 lint warnings. V2 usefulness gateFAIL; no fullV2/no promotion. Live port8005 assistant not started; live-Core orchestrator harness verified. Core+Vite are running; Search8003/recommender8004/RAG8005 are not started by this validation. Sparse/stale/excluded books may produce fewer than10; shared metadata does not guarantee useful similarity. Prior failed staging artifact retained and never selected. Screenshot capture with some resized viewport overrides was unreliable; DOM geometry is recorded and final proof captured after reset. No weak-relation implementation is fabricated from absent fields.

X. **Exact start commands** (separate terminals):

```powershell
# Separate terminals; Core + frontend are sufficient for More Like This.
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002 --workers 1

Set-Location D:\SDC\LibraryLLM\frontend
npm run dev -- --host 127.0.0.1 --port 5173

# Existing services, each in a separate terminal from the project root:
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe -m uvicorn search.api:app --host 127.0.0.1 --port 8003 --workers 1
.\.venv\Scripts\python.exe -m uvicorn recommendation.api:app --host 127.0.0.1 --port 8004 --workers 1
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
.\.venv\Scripts\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005 --workers 1
```

Open http://127.0.0.1:5173/book/OL19545719W and sign in normally. Stop at productization + ontology evaluation. No KG4, graph embeddings, user nodes, Search/KG blending or Qwen ontology generation.
