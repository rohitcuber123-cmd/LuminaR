# Knowledge Tools V2.1 completion

A. **PASS** — the 36 completion gates are satisfied. Fixture clock adaptation and viewport rounding are disclosed below.

B. Preserved DocumentKnowledgeModel 3.2.1 selection/ranking/diversity. The real CN concept IDs, labels, explanations and scores, card text/types, quick-summary text and map labels/types match the previous baseline exactly. One existing bounded CPU semantic batch is reused for new quiz ambiguity metadata. Old cached models migrate only their additive quiz facet.

C. Nineteen validated real-CN facts starved because article-derived category pools were too small. Matching used page-local groups. Identity-conflict/leak checks were also applied too broadly. The audit records before/after candidates and every requested rejection category.

D. Real CN MCQ-only, requested 12: **0 → 9**, all nine manually reviewed against source evidence and alternatives. Seven GOOD, two ACCEPTABLE for awkward original wording; no incomplete or invented answer.

E. Real CN Match-only, requested 12: **0 → 2 sets**, each four pairs, both manually verified and GOOD. Families span source pages. Mixed requested 12: **2 MCQs + 2 matching sets + 4 fill questions**; partial counts are explicit and other successful types survive.

F. Bounded typed evidence/option pools, up to 100 frames, exact source associations, aliases, lexical overlap and cached semantic-peer checks. Four distinct alternatives remain required. Description options remove the old category starvation; every alternative keeps its own source IDs. Cross-format evidence/concept deduplication and source-section preference remain active.

G. Additive quiz-only structured colon, heading/bullet and short-definition relations preserve exact excerpts and evidence unit IDs. Identity, purpose, property, process, composition, component function and explicit application families remain distinct. Core concepts/cards/summary/map and RAG text are not rewritten. Dangling conjunctions, generic/deictic subjects, flattened ambiguous formulas and unsupported fragments are rejected.

H. Optional Qwen experiment **not triggered**: deterministic CN coverage exceeds six MCQs and one matching set. Production artifact Qwen calls stay **zero**, with no per-question inference. Assistant remains **existing_qwen**.

I. Local **PyMuPDF embedded Tesseract**, English fast language data, no external OCR API, no GPU OCR model and no pytesseract dependency. The 4,113,088-byte pack is pinned and checksummed in the preflight report. RGB raster input is required by the tested build. [PyMuPDF OCR documentation](https://pymupdf.readthedocs.io/en/latest/faq/index.html#OCR), [official Tesseract language data](https://github.com/tesseract-ocr/tessdata_fast).

J. Native quality uses letter/word counts, alphabetic and printable ratios, and replacement/control character ratios. Defaults: 220 DPI, maximum 12 million raster pixels, one concurrent OCR page, two preparations, 20-second page timeout, 80 attempts. Oversized pages are rejected before allocation. Failures remain page-local with an authenticated UI warning.

K. Three-page image-only fixture: all three pages OCR, 12 concepts, 12 cards, 12 MCQs and 3 matching sets in single-type live runs. Ask Document returned a sourced answer with three sources. OCR View Source was verified through the browser and API.

L. Mixed text/scan/text fixture: methods **NATIVE/OCR/NATIVE**, original pages 1/2/3, only one OCR attempt. Blank and unusable-content fixtures remain empty rather than generating fabricated facts.

M. Images stay in memory/pipes; private extraction/chunks/model/artifacts use the existing authenticated session lifecycle. Encrypted restore retains OCR page markers and vectors with no PDF/raster and no OCR or embedding rerun. Live status is account/session/UUID scoped and disappears on completion. Owned test accounts/documents and private scratch files were removed; original CN PDF stays untouched. The nonprivate English language dependency remains cached.

N. The launcher was fixed over the content, and padding inside the scrolling content did not protect controls at intermediate scroll positions. The desktop sidebar also squeezed mobile content.

O. Shared launcher dimensions and a **rail outside the scroll viewport** guarantee clearance. Flashcards have Previous / Card N of M / Next, clamp/filter reset, and Left/Right/Space/Enter shortcuts that ignore interactive fields and dialogs. Desktop sidebar collapses to an optional mobile drawer.

P. Quiz pager renders one question, preserves per-question answers/checks, shows correct-answer or matching-pair feedback/source links, and exposes Previous/Next/Try again above the launcher rail. Exact generated/requested/per-type counts and shortfalls are visible.

Q. All **36 checks** across flashcards, MCQ feedback, matching feedback, concepts, summary and map at **1440×900, 1366×768, 1024×768, 768×1024, 390×844, 375×812** passed: zero visible overlaps or horizontal page overflow, 16px clearance. Actual clicks, matching answers, source links and card shortcuts were tested. Mobile launcher is a 52px accessible Ask LuminaR circle. Existing browser zoom was accounted for; measured CSS dimensions have at most one-pixel rounding.

R. Live native preparation: CN 29 pages **625ms**, three-page native **100ms**, zero OCR attempts. First CN model/concept view **1.49s**; other study views use the persisted model.

S. Live full-scan preparation **4.10s** (3.32s OCR), mixed **1.32s** (1.03s OCR). Final OCR worker peak RSS **97MB**, RGB raster **14MB**. Encrypted restore **42ms** with all three OCR markers. These are single local measurements, not throughput claims.

T. CN live mixed/MCQ/Match generation **59/53/55ms**, cache hits **17–19ms**. Cold legacy-facet migration includes one CPU encoder load (~12s); newly prepared models reuse their existing semantic batch and cached views do not repeat it.

U. Backend suites pass: Knowledge **233**, final private/cache/status **53**, final hardening **29**, KG **32**, Events **76**, plus unit/Assistant/security/staff/notifications/circulation/Search groups. Ten existing skips; isolated suites overlap. The unmodified Events fixtures pin 6 Oct 2026 and their receipts expire after that day. A test-only runner aligns NOW to current UTC, retaining expiry checks; all 76 pass without Events source edits.

V. Frontend **285 passed**, including Know More, Assistant, Events, paging and source/privacy controls.

W. Production build PASS; lint has **zero errors**, existing warnings retained. Existing Vite chunk-size warning remains.

X. Exact V2.1 changed/new files (prior V2 files left unchanged are excluded):

Production:

- `rag/services/document_knowledge.py`
- `rag/services/knowledge_artifacts.py`
- `rag/services/knowledge_quiz.py`
- `rag/services/knowledge_quiz_evidence.py`
- `rag/services/knowledge_quiz_formats.py`
- `rag/services/private_document_ocr.py`
- `rag/services/private_ocr_worker.py`
- `rag/services/private_documents.py`
- `rag/services/private_document_routes.py`
- `rag/services/local_document_cache.py`
- `frontend/src/components/AIChatWidget.tsx`
- `frontend/src/components/knowledge/KnowledgeTools.tsx`
- `frontend/src/components/knowledge/Quiz.tsx`
- `frontend/src/index.css`
- `frontend/src/lib/api.ts`
- `frontend/src/pages/LLMPage.tsx`

Tests:

- `tests/test_knowledge_quiz.py`
- `tests/test_knowledge_artifacts.py`
- `tests/test_knowledge_algorithms.py`
- `tests/test_private_document_cache.py`
- `tests/test_knowledge_tools_v2_1.py`
- `tests/test_private_preparation_status.py`
- `frontend/tests/assistant.test.tsx`
- `frontend/tests/knowledge-artifacts.test.tsx`
- `frontend/tests/part3-contract.test.tsx`

Support/docs:

- `scripts/check_knowledge_tools_v2_1.py`
- `scripts/test_knowledge_tools_v2_1_regressions.py`
- `scripts/test_knowledge_tools_v2_1_events.py`
- `scripts/report_knowledge_tools_v2_1.py`
- `docs/private_document_ocr.md`

Y. Required reports:

- `reports/knowledge_tools_v2_1_quiz_coverage_audit.json`
- `reports/knowledge_tools_v2_1_cn_quiz.json`
- `reports/knowledge_tools_v2_1_ocr.json`
- `reports/knowledge_tools_v2_1_frontend.json`
- `reports/knowledge_tools_v2_1_performance.json`
- `reports/knowledge_tools_v2_1_live.json`
- `reports/knowledge_tools_v2_1_regression.json`
- `reports/knowledge_tools_v2_1_decision.md`

Additional preflight, preservation, source audit, cleanup, final live, XML test evidence and screenshots accompany these reports.

Z. English printed-text OCR is optional and depends on local language data. Handwriting, poor scans, complex math and other languages may fail; failures are reported, with usable pages retained. Coverage is intentionally partial when supported facts or unique pairs are scarce. Matching counts are sets, not individual pairs. Viewport dimensions can round by one CSS pixel at the existing 80% browser zoom. Events regression requires its fixture clock alignment; no production Events change was made. No frozen Search/Recommendation/KG/Events/Admin/Notifications/Book RAG/router source changed (228 baseline files unchanged). No router experiment or new phase was started.
