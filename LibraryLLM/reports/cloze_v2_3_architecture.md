# Fill in the Blanks Natural Answer V2.3 — PASS

Implemented narrowly in the existing private Knowledge Tools Quiz. DocumentKnowledgeModel 3.2.1, study renderers, Flashcards reveal-only flow, MCQ V2.2 and Match generators remain intact. Frozen production files were hash-checked: 202 unchanged, including all 3 Recommendation files. Pre-existing dirty work was preserved.

## Authoritative grading and private lifecycle

`POST /rag/documents/{document_id}/artifacts/{artifact_id}/cloze/{item_id}/grade` accepts only `{"answer":"..."}` (strict string, 1–500 characters, unknown fields forbidden). Existing authentication resolves current Mongo identity and session. The service retrieves the owned, current artifact and active source revision, resolves the stored item, validates canonical/source/prompt identity and aliases, then grades. It rechecks active ownership and artifact existence after grading, so logout/delete cannot publish private results. Responses use `Cache-Control: no-store`. Missing/wrong-owner/wrong-session items retain private 404 behavior; unauthenticated/revoked tokens return 401. Client expected-answer injection returns 422.

Each stored item retains stable ID, source fact/subject/relation identities, relation type, canonical answer, answer type, accepted aliases, evidence units, chunk IDs, page bounds and a bounded source-term conflict list. Canonical text comes from the same excerpt used to construct the blank; reconstructing the excerpt from prompt + canonical must match. Repeated/leaked answers and suspicious OCR letter-digit corruption are rejected. New cloze metadata is generated from existing core facts/quiz relations; core ranking is untouched. Only quizzes containing fill blanks receive a cloze cache revision. MCQ-only/Match-only cache identities and outputs remain unchanged.

## Bounded decision flow

1. Unicode NFKC, case fold, whitespace collapse, safe letter-hyphen spacing and punctuation. Leading articles may be ignored for terms/phrases; entity names retain them. Numeric signs, decimal points and unit symbols are preserved.
2. NUMBER / NUMBER_WITH_UNIT use Decimal equality and explicit unit dimensions. Supported duration units include ms/s/min/h and printed spellings; percent formatting is supported. Unknown symbols match only themselves. Wrong values, missing units, unsupported unit changes and reversed signs cannot be rescued by semantics.
3. TERM / ENTITY use normalized identity, explicit same-source acronym/full-name aliases, then at most one edit in one sufficiently long word. Short words/acronyms/qualifiers stay strict; automatic plural/singular changes and other known source terms are rejected. No embeddings are used for term identity.
4. SHORT_PHRASE / DESCRIPTION require compatible source evidence as well as CPU MiniLM similarity and clause coverage. Numeric, negation, multiple/single, role/direction and other source-entity conflicts override similarity. A small compositional rate/speed rule retains sender/receiver and receiver-purpose identity; it is not a technical synonym dictionary. DESCRIPTION answers require a predicate for semantic full credit. Partial feedback is only for a supported but incomplete phrase; identity/numeric blanks remain binary.
5. Grading returns CORRECT / PARTIAL / INCORRECT, canonical answer, source pages/chunks, concise feedback, reason and measured server latency.

## CPU preparation, batching and Qwen decision

The existing cached local `all-MiniLM-L6-v2` singleton is prepared on FastAPI startup, on CPU. Preparation does not add a core-model encoding batch. Normal grade requests use zero Qwen calls, zero CUDA calls and no generation/GPU inference lock. Optional Qwen fallback was not added: the measured development cases passed without it.

A 512-entry, 300-second scalar similarity cache retains hashed keys and scores only. Identical requests share a Future. Distinct phrase requests collect for 5 ms and share source/context encoding through the same CPU encoder; no second model is loaded. The transient queue is bounded at 64 jobs; a 700 ms wait becomes a retryable 503 rather than an incorrect answer. Ownership is still checked per request and again after work completes. Cache hits never bypass authentication or source revision checks.

Initial distinct-phrase stress exposed serial encoder queuing (about 1113 ms at 20 users). CPU batching reduced the final 20-user maximum to 606.86 ms. Repeated/mixed 20-user p95 is 175.42 ms; maximum 186.14 ms. Single distinct-phrase HTTP request: 116.51 ms. All final 1/5/10/20 levels satisfy the 750 ms hard target. The distinct 10/20-user workload exceeds the preferred 200 ms target.

## Frontend behavior

The cloze card has a typed field, Check answer and Enter submission. Before submission it does not render canonical answers or aliases. Feedback uses text and symbols: ✓ Correct, ~ Partially correct, × Needs review, with Your answer, Accepted/Expected answer, explanatory text and source links. State is keyed by stable item ID and survives Previous/Next. Try again clears only the current cloze response/result without regenerating the question. Failure keeps input and offers retry. Duplicate submission is blocked; pending checks abort on unmount/document/account change. MCQ/Match scoring is unchanged. Flashcards still show Front → Reveal answer → Show front, with Previous/Next and zero typed fields.

Browser checks covered all three verdicts, Enter, drafts/results through navigation, per-cloze retry, source page 1, a real mixed quiz (4 MCQ, 4 cloze, 1 set/4 pairs), matching 4/4 and preserved MCQ/Match results after cloze retry. Six CSS viewport sizes from 375×811 to 1920×1079 have no horizontal overflow and reserve at least 16 px between the study scroll area and Ask LuminaR. See desktop/mobile PNGs and browser geometry JSON.

## Evidence and limits

Development calibration: 432 cases, 19 categories, 50 generated source items from the actual CN PDF, educational fixtures and real image-only OCR, plus independently labelled narrow source fixtures. Correct precision 100%; verdict accuracy 100%; numeric conflict accuracy 100% (10 cases); zero term false accepts. This is development calibration, not held-out or unrestricted essay accuracy. Only six manually labelled correct paraphrases and two partial-answer cases supplement formatting/identity coverage.

Live API: CN 12 clozes / 57 variants; OCR 12 clozes / 53 variants. Source excerpts/pages were verified through private source routes. The OCR fixture is a genuine 3-page image-only PDF, processed by the existing OCR pipeline; native text pages = 0. Both mixed quizzes retain 4 MCQ, 4 cloze and one 4-pair match set. Numeric 2T examples are supplemental source fixtures; the conservative CN selection does not generate that numeric blank.

Validation: broad Knowledge/Quiz/OCR/private/DocRAG suite 338 passed, then final focused grading/artifact suite 105 passed. Frozen regression groups pass, with 10 pre-existing security skips. All 298 frontend tests pass (52 Knowledge tests). Build passes; zero lint errors, existing warnings only. Events fixtures receive a test-only clock alignment; real JWT expiry is enforced. Router V1–V5 research was not rerun. Disposable readers/server copies/private scratch were removed; the user's original PDF was only read.

Known limits:

- Development calibration: 50 generated source-bound items with repeated formatting variants plus manually labelled source fixtures; not held-out/general essay accuracy.
- Paraphrases remain conservative; unknown aliases/acronyms, unrestricted synonyms and unsupported conversions are rejected.
- The live CN selection has term/short-phrase blanks, not a numeric 2T blank. Numeric/quantity conflicts are tested against explicit supplemental source fixtures, not fabricated CN questions.
- CPU model load occurs at service startup (roughly 14–20 seconds in isolated calibration runs). Single uncached phrase requests remain interactive.
- 20 distinct longer phrase answers take about 607 ms, above the preferred 200 ms but below the 750 ms hard target. Queue bounded at 64 with retryable failures.
- Only the existing CPU MiniLM and deterministic checks are used; no optional Qwen ambiguity experiment was justified by this development corpus.

## Exact phase files

- `rag/services/cloze_grading.py`
- `rag/services/knowledge_cloze.py`
- `rag/services/knowledge_encoder.py`
- `rag/services/knowledge_artifacts.py`
- `rag/services/knowledge_routes.py`
- `rag/services/knowledge_quiz.py`
- `frontend/src/lib/knowledgeArtifacts.ts`
- `frontend/src/components/knowledge/KnowledgeTools.tsx`
- `frontend/src/components/knowledge/Quiz.tsx`
- `tests/test_cloze_v2_3.py`
- `tests/test_knowledge_quiz.py`
- `frontend/tests/knowledge-artifacts.test.tsx`
- `scripts/check_cloze_v2_3.py`
- `scripts/check_cloze_v2_3_live.py`
- `scripts/test_cloze_v2_3_regressions.py`
- `scripts/test_cloze_v2_3_events.py`
- `scripts/report_cloze_v2_3.py`

## Required reports

- `reports/cloze_v2_3_architecture.md`
- `reports/cloze_v2_3_calibration.json`
- `reports/cloze_v2_3_quality.json`
- `reports/cloze_v2_3_performance.json`
- `reports/cloze_v2_3_live.json`
- `reports/cloze_v2_3_regression.json`
