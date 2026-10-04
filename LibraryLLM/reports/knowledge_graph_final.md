# LuminaR KG1–KG3: implementation and measured comparison

KG1–KG3 are complete in the existing frontend at `/experimental/kg`. KG4 is **deferred**. Existing recommendation candidates and scoring remain unchanged.

## Catalogue graph

The full Mongo catalogue supplied **5,000,000 books**, **2,454,492 author-name nodes**, **975,785 subject-label nodes**, and **29,406,707 typed edges**. No rows were skipped. Missing author metadata: 60,151 books; missing subjects: 257,541; isolated books: 1,211.

Snapshot: 2026-10-02T17:00:36.932421+00:00. Build: 882.81 seconds. SQLite: 5,871,624,192 bytes (5.87 GB). Public-metadata stream digest: `50559012605f6fe3aba1fbc36f3f943c24563bb0a88fc60ac6a14df90fb3e904`.

The builder streams projected public fields in batches and creates indexes before atomically publishing the local artifact. Runtime connections are read-only. This graph needs no Neo4j, embedding, LLM, document content or new dependency.

Book → AUTHORED_BY → Author name and Book → HAS_SUBJECT → Subject label. Normalize NFKC, case folding and whitespace; split only pipes, preserving commas inside names. These are label matches, without verified author identity resolution or a multilingual subject ontology.

For N books and feature degree d, weight = `(2 for author, else 1) * (1 + ln((N+1)/(d+1)))`. Similarity is weighted cosine over **all shared features** and all connected candidates. Each shared feature contributes weight² / sqrt(seed norm × candidate norm). All contributions sum to the score. Scores measure metadata similarity, not relevance probability.

Every returned path has two original catalogue field values and work IDs, a degree and a contribution. 758 paths from the real evaluation passed source-field membership and typed two-hop checks. Focused tests separately verify contribution sums. The interactive map displays the strongest three paths per recommendation; expanded evidence exposes every path.

## KG3 protocol and results

40 seeds were frozen before outcomes: 32 equally spaced positions across the full snapshot, two each with no authors/no subjects/no links, and two existing recommendation fixtures. Deduplication occurred before evaluation. This is a systematic and edge-case-enriched set, **not a random representative sample** of reader demand.

Both methods used one real verified reader, the same work ID, k=10 and active loan/reservation exclusions. The baseline is the actual existing `/recommendations/from-book` service; no substitute scorer. All 40 paired requests succeeded, with no failures. The graph snapshot and seed list are retained in JSON.

| Measurement | Existing | KG |
|---|---:|---:|
| Seeds with results | 100% (40/40) | 95% (38/40) |
| Seeds returning all ten | 100% (40/40) | 87.5% (35/40) |
| Distinct recommended work IDs | 400 | 356 |
| Catalogue coverage across these seeds | 0.008% | 0.00712% |
| Mean measured subject diversity | 0.7865 | 0.7196 |
| Warm per-seed request median | 426.05 ms | 289.25 ms |
| Largest measured request | 860.82 ms | 2596.64 ms |

**Mean overlap: 14%. Mean Jaccard: 0.06367. 92.5% of seeds had at least one KG-only candidate.** Two intentionally isolated seeds had no KG candidates.

Overlap is intersection size divided by the smaller nonempty returned list size; empty-list overlap is zero. Jaccard divides intersection by union. Both compare work IDs, so catalogue works with identical titles remain separate. Catalogue coverage divides distinct returned work IDs by all 5M books and applies only to these 40 seeds.

Subject diversity is mean pairwise `1 − Jaccard(normalized subject sets)`. Pairs with missing subjects are omitted and their counts are retained in each JSON row. Undefined list diversity is omitted from the method means. The fair paired comparison has **36 seeds**, mean KG-minus-existing diversity **−0.05720**; the remaining four pairs cannot measure both diversities. Different method means therefore do not substitute for the paired delta.

Latency is one sequential request per method per seed after a separate warm-up, on this local machine with existing loaded models. It is a median across seeds, not repeated-request or concurrent-load benchmarking. Some common-feature KG queries take longer because their full connected candidate pool is evaluated.

## KG4 decision

The candidate gate was specified before outcomes: nonempty seed coverage ≥0.90, KG-only candidate seed fraction ≥0.50, mean paired diversity decline ≤0.05, and reason-path validity 1.0. Coverage, novelty and path validity pass. Diversity **fails**: −0.05720 exceeds the permitted decline. The independent quality condition also fails because there are no relevance or reader-utility labels.

**Do not run hybrid reranking yet.** Novelty, coverage and metadata diversity cannot establish useful recommendation improvements. No candidate union, reranker change, production replacement or KG4 experiment was added.

## Existing frontend and live checks

The protected experimental route and Graph Lab navigation link reuse the current frontend shell and chatbot overlay. It supports title-prefix/work-ID lookup, opt-in exploration, typed graph nodes, keyboard inspection, metadata filters, zoom, book details/reseeding, complete reason evidence and explicit side-by-side comparison. Aborted requests cannot replace a newly selected seed; unavailable baseline service returns an error without invented metrics.

After the user signed in, live catalogue results for Fundamentals of Deep Learning showed ten KG recommendations from 74,507 connected candidates. Both lists were visible: two shared books (20%), eight KG-only books, rounded diversity 0.76 existing / 0.78 KG. These single-seed values are distinct from the aggregate experiment.

Live checks confirmed subject inspection, Enter-key book selection, subject hiding/restoration, source-field disclosures and zoom. No console errors were captured. Narrow/wide rendered layouts had no document horizontal overflow; map overflow stays within its scroll container. Browser viewport override widths differed from reported DOM widths, so exact 390-pixel device emulation is not claimed. The override was reset. See `kg_browser_checks.json` and `kg_graph_preview.png`.

## Validation, preservation and limits

**401 backend tests passed; 10 existing skipped.** Includes 12 KG tests and prior assistant/document-RAG checks. Existing frontend suites: **111 passed**; KG frontend: **5 passed**; independent frontend contracts: **5 passed**. Production build passed. Lint passed with 18 existing warnings; no KG warnings. The existing backend warning concerns FastAPI/Starlette httpx deprecation.

Against the prior 1208-file pre-document-latency baseline, 1204 files remain byte-identical and none are missing. Three KG edits register the backend route, frontend route and navigation item. The fourth difference is the already completed document-latency installation: verified as exactly its two prior installation lines. Recommendation/search/assistant sources and all previous report files in that baseline are unchanged. Full comparison is in `kg_integrity.json`.

The evaluator hashes existing circulation/reading-list/feedback collections before and after; hashes match. It does not write accounts, issues, reservations, lists or feedback. Mongo catalogue is read-only. New local graph/evaluation artifacts are the intended outputs.

Snapshots do not auto-refresh. Changed seed features return 409; missing/inactive/changed candidate features are filtered against live Mongo, which may shorten the list. Labels may be noisy or ambiguous and miss synonym relationships. Metadata similarity can favor narrowly similar works; no relevance labels support quality claims. No deployment or new model worker was started. Core/search/recommendation/Vite local services remain running for the user preview.

## Reproduction and evidence

See `knowledge_graph/README.md` for local commands. Builders refuse graph overwrite; evaluator refuses to replace its comparison report. Preserve the snapshot and reports before a deliberate rebuild/re-evaluation.

- Build metadata: `kg1_kg2_build.json`, `kg_build.log`, `kg_build_progress.json`.
- Frozen seeds and raw results: `kg3_seeds.json`, `kg3_evaluation.json`, `kg3_evaluation.log`.
- Validation: `kg_backend_focused.log`, `kg_backend_regression.log`, `kg_frontend_focused.log`, `kg_frontend_regression.log`, `kg_independent_frontend.log`, `kg_frontend_build.log`, `kg_frontend_lint.log`.
- Final structured handoff: `knowledge_graph_final.json`.

## Per-seed outcomes

| Work ID | Stratum | Existing / KG results | Overlap | Existing / KG diversity | Existing / KG ms |
|---|---|---:|---:|---:|---:|
| OL19545719W | systematic full-catalogue interval | 10 / 10 | 0.20 | 0.7601 / 0.7803 | 260.35 / 1195.76 |
| OL21548576W | systematic full-catalogue interval | 10 / 10 | 0.00 | 0.8417 / 0.9607 | 434.11 / 1947.84 |
| OL19764415W | systematic full-catalogue interval | 10 / 10 | 0.10 | 0.8125 / 0.7090 | 837.57 / 2449.84 |
| OL32628060W | systematic full-catalogue interval | 10 / 10 | 0.00 | 0.8976 / 0.4978 | 533.59 / 1776.39 |
| OL1186544W | systematic full-catalogue interval | 10 / 10 | 0.20 | 0.6419 / 0.6505 | 412.51 / 109.79 |
| OL1262274W | systematic full-catalogue interval | 10 / 10 | 0.00 | 0.8080 / 0.8295 | 421.82 / 401.24 |
| OL39102753W | systematic full-catalogue interval | 10 / 10 | 0.00 | 0.7491 / 0.8139 | 674.53 / 668.58 |
| OL91307W | systematic full-catalogue interval | 10 / 10 | 0.00 | 0.5449 / 0.6733 | 390.34 / 522.49 |
| OL5260192W | systematic full-catalogue interval | 10 / 10 | 0.10 | 0.7826 / 0.8780 | 453.12 / 537.67 |
| OL34083034W | systematic full-catalogue interval | 10 / 10 | 0.00 | 0.8474 / 0.0000 | 409.55 / 310.17 |
| OL6605264W | systematic full-catalogue interval | 10 / 10 | 0.10 | 0.6167 / 0.2274 | 310.17 / 45.06 |
| OL80139W | systematic full-catalogue interval | 10 / 10 | 0.20 | 0.8227 / 0.8116 | 860.82 / 1288.97 |
| OL21371602W | systematic full-catalogue interval | 10 / 10 | 0.20 | 0.8374 / 0.8429 | 327.47 / 36.81 |
| OL11356114W | systematic full-catalogue interval | 10 / 10 | 0.30 | 0.7165 / 0.6612 | 358.29 / 435.00 |
| OL1278747W | systematic full-catalogue interval | 10 / 10 | 0.10 | 0.7498 / 0.9231 | 352.28 / 44.65 |
| OL23669751W | systematic full-catalogue interval | 10 / 1 | 1.00 | 0.7775 / undefined | 327.03 / 16.24 |
| OL43370123W | systematic full-catalogue interval | 10 / 10 | 0.20 | 1.0000 / 0.3556 | 332.44 / 34.75 |
| OL7079061W | systematic full-catalogue interval | 10 / 10 | 0.00 | 0.4944 / 0.5296 | 342.01 / 66.75 |
| OL3486219W | systematic full-catalogue interval | 10 / 10 | 0.00 | 0.7372 / 0.9058 | 344.43 / 735.10 |
| OL17869247W | systematic full-catalogue interval | 10 / 10 | 0.10 | 0.6839 / 0.9367 | 496.93 / 1092.77 |
| OL2245597W | systematic full-catalogue interval | 10 / 10 | 0.00 | 0.9647 / 0.9077 | 500.69 / 415.74 |
| OL3351681W | systematic full-catalogue interval | 10 / 10 | 0.10 | 0.8055 / 0.8558 | 401.89 / 395.16 |
| OL26771281W | systematic full-catalogue interval | 10 / 10 | 0.40 | 0.8772 / 0.9074 | 421.83 / 2596.64 |
| OL19513321W | systematic full-catalogue interval | 10 / 10 | 0.20 | 0.6274 / 0.8208 | 431.80 / 1888.00 |
| OL33869300W | systematic full-catalogue interval | 10 / 10 | 0.20 | 0.7798 / 0.8974 | 331.59 / 92.93 |
| OL18278917W | systematic full-catalogue interval | 10 / 10 | 0.20 | 0.8030 / 0.6604 | 324.84 / 1247.10 |
| OL18074787W | systematic full-catalogue interval | 10 / 10 | 0.10 | 0.7607 / 0.5446 | 430.27 / 67.92 |
| OL11471353W | systematic full-catalogue interval | 10 / 10 | 0.10 | 0.9132 / 0.9778 | 477.95 / 56.94 |
| OL13576021W | systematic full-catalogue interval | 10 / 10 | 0.20 | 0.6189 / 0.2733 | 398.56 / 62.34 |
| OL7467872W | systematic full-catalogue interval | 10 / 10 | 0.20 | 0.7011 / 0.3511 | 493.20 / 45.52 |
| OL22319288W | systematic full-catalogue interval | 10 / 10 | 0.00 | 0.5606 / 0.9683 | 768.03 / 965.40 |
| OL25127599W | systematic full-catalogue interval | 10 / 10 | 0.10 | 0.8737 / 0.5861 | 453.95 / 54.39 |
| OL24712944W | no authors | 10 / 10 | 0.10 | 0.7532 / 0.8446 | 500.09 / 57.11 |
| OL20927213W | no authors | 10 / 10 | 0.10 | 0.9608 / 0.5622 | 627.19 / 37.49 |
| OL25339037W | no subjects | 10 / 4 | 0.50 | 1.0000 / 0.9667 | 313.19 / 22.33 |
| OL24406311W | no subjects | 10 / 1 | 0.00 | 0.9167 / undefined | 389.66 / 29.56 |
| OL23058018W | isolated | 10 / 0 | 0.00 | 0.8524 / undefined | 533.44 / 14.10 |
| OL23355322W | isolated | 10 / 0 | 0.00 | 0.9485 / undefined | 538.56 / 15.69 |
| OL3411044W | existing seeded recommendation fixture | 10 / 10 | 0.20 | 0.7780 / 0.8899 | 487.45 / 2436.21 |
| OL2000134W | existing seeded recommendation fixture | 10 / 10 | 0.10 | 0.8416 / 0.9036 | 707.07 / 268.33 |
