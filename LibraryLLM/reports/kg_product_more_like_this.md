# LuminaR KG3.1 product More Like This

**Product PASS. Overall PARTIAL because V2 remains at the permitted pilot stop.** Book Detail uses the unchanged full V1 graph. No KG4, production ontology promotion or model download.

Book Detail adds **More Like This** immediately beside Add to Reading List in the existing action row. Click stays on `/book/:work_id`, loads/focuses an inline section, shows Finding related books, native cover/title/author/rating/copy/shelf cards, View/Select and deterministic grouped Why related. Hide, refresh, retry and stale/not-found messages are supported. Empty books say no graph relationships and offer an explicit separate Try Recommend Similar action. No automatic recommender fallback or tray modification occurs. Raw scores remain API metrics and are not rendered in normal cards.

Small overflow links on catalogue, search, reading list, For You recommendation and assistant book cards open `/book/:work_id?related=1#more-like-this`. Existing assistant actions also include MORE_LIKE_THIS. Exact phrases more like this, show books connected to this and find related books with exactly one selected/page book enter the zero-Qwen route. Missing or multiple sources clarify without Qwen. Existing Recommend Similar, compact intent wire codes, recommendation engine and document RAG routes remain intact.

**API:** authenticated `GET /kg/books/{work_id}/more-like-this?limit=10`, Core port 8002 via the existing `/api` frontend proxy. It reuses the Graph Lab recommendation function and `CatalogueGraph.more_like_this`; no frontend query algorithm is duplicated. Canonical work_id only. Limits 1–50; active loans/reservations excluded. Results rehydrate through live Core catalogue and `get_availability_context`, including physical LIB001 inventory precedence. Author/subject freshness checked; future V2 hashes supported. Changed seeds return friendly 409; changed/deleted/ineligible candidates are removed. `has_more=false`: no fabricated paging. Filtering can return fewer than ten.

Graph Lab stays `/experimental/kg`; the explicit advanced link supplies `?seed=<work_id>`. Seed loading, new/unknown relationship colours/filtering and changing-seed result cleanup work. It is never opened automatically.

## Actual authenticated live checks

Loopback Core endpoint, one verified existing reader, no database writes. Each case has a first-observed request and three warm repeats; authoritative book metadata and availability are checked outside the timer. All returned reason paths source-verified. See `kg_product_performance.json` for complete cards, evidence and timings.

| Case | work_id | Results | Warm mean ms | Reason types | Metadata / availability |
|---|---|---:|---:|---|---|
| finance | OL2010879W | 10 | 254.6 | author, subject | PASS |
| fiction/literature | OL11359361W | 10 | 340.6 | author, subject | PASS |
| technical | OL19545719W | 10 | 392.5 | subject | PASS |
| no authors | OL24712944W | 10 | 34.9 | subject | PASS |
| no subjects | OL25339037W | 4 | 15.5 | author | PASS |
| isolated | OL23058018W | 0 | 10.3 | none | PASS |

Across 18 warm requests: median **140.2 ms**, p95 **393.7 ms**, maximum **396.6 ms**. First-observed is not a process-cold benchmark. The technical click-to-visible UI sample is **865 ms** and refresh **809 ms** including Cua overhead; four other UI cases are 308–540 ms. These are observed samples, not statistically established browser p95. All six cases also loaded in the real signed-in Book Detail UI. Isolated has zero results and separate normal recommendation offer. Selection stayed false; current page remained unchanged. Keyboard Enter expands exact Subjects such as Machine learning and Computer Neural Networks. Finance cards likewise preserve their actual shared author/subject labels.

A real assistant orchestrator and real HTTP adapter called live Core, with forbidden Qwen/RAG/recommender sentinels: MORE_LIKE_THIS returned 10 books with zero Qwen and seeded recommender calls. This is a live-Core transport harness, **not a running port-8005 end-to-end request**. The existing 8005 worker is not running; when normally started it requires the existing local RAG/model initialization. The normal page button needs only Core and Vite. Collection hashes before/after (users, issues, reservations, reading list, feedback, inventory, fines, activity) match.

## Verification

Backend **429 passed, 10 existing skips** including all 28 KG3.1 checks and 401 prior KG/assistant/document/access/auth/contracts. Focused UI **17**, Graph Lab **5**, independent frontend contracts **5**, original frontend **111**: **138 passed** in total. Production build passes. Lint exits zero with **19 existing warnings**, no new KG component warnings. Logs: `kg31_backend_regression_final.log`, `kg31_frontend_all_final.log`, `kg31_frontend_focus_final.log`, `kg31_frontend_contract_final.log`, `kg31_frontend_build_final.log`, `kg31_frontend_lint_final.log`. No tests were weakened; compact enum codes and protected routing were repaired additively.

Responsive DOM/layout plus action/result screenshots: requested **1440×900**, **1366×768**, **768×1024**, **375×812**. Actual CSS sizes **1440×900**, **1366×767**, **769×1024**, **375×812**, plus **767×1024** around the tablet breakpoint. No page horizontal overflow; mobile actions wrap and result cards stay within width. Browser DPR/zoom 0.8 plus integer viewport override prevents two exact dimensions; do not claim exact coverage there. Screenshot canvases may include padding from browser scaling. `kg31_browser_checks.json` retains actual geometry; `kg31_book_actions_*.jpg`, `kg31_more_like_this_*.jpg` and `kg31_product_preview.jpg` retain captures. Viewport reset before handoff.

## Exact local start commands

Use separate PowerShell terminals. Keep existing listeners; stop/restart only the intended service if code is already loaded in an old process. Do not rebuild V1 or promote either V2 pilot.

```powershell
# Terminal 1: product Core
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002 --workers 1
```

```powershell
# Terminal 2: existing frontend
Set-Location D:\SDC\LibraryLLM\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173/book/OL19545719W`, sign in normally and click More Like This. Core/Vite remain running after verification. Search 8003 and recommendation 8004 remain running as before. For a fresh session, those existing services start separately from the project root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn search.api:app --host 127.0.0.1 --port 8003 --workers 1
.\.venv\Scripts\python.exe -m uvicorn recommendation.api:app --host 127.0.0.1 --port 8004 --workers 1
# Optional existing assistant worker; reuses installed local models:
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
.\.venv\Scripts\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005 --workers 1
```

Known limits: metadata similarity is not relevance probability; author names are unresolved strings; sparse/isolated works can return few/no books; stale candidates can reduce top10; current product graph contains only author and subject relations; topics are pilot-only and require further independent quality work. Full V2 and live-8005 overlay testing are deliberately unclaimed. Original KG3 paired diversity delta −0.0572 and 14% recommender overlap remain unchanged; no hybrid reranking is introduced.
