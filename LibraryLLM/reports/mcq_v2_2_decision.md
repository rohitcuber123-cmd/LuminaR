# Quiz correctness V2.2

A. **PARTIAL under the requested strict acceptance rule.** Implementation and reproduced checks pass. MCQ acceptance gate 1 requires identifying a wrong-key root cause; no wrong key was reproduced in the supplied CN baseline. The reported defect remains unconfirmed. Independent matching gates pass against the reviewed records and tested invariants; dependent matching gate 16 remains PARTIAL because it requires full MCQ acceptance. This is not a universal semantic guarantee.

B. Confirmed causes: first compatible distractors repeated across the quiz, no global duplicate option-set gate, and permissive candidate associations. Legacy matching consumed evidence directly (not MCQ objects), but lacked a dedicated authoritative relation facet, opaque IDs and pair-level global allocation.

C. No backend key mismatch reproduced. Strict subject/relation/target round-trip and assembled-option verification now reject tampered or detached bindings.

D. No frontend option identity defect reproduced. The existing MCQ contract checks exact unique option text; no correct_index or browser reshuffling exists. Matching uses stable opaque left/right IDs.

E. Fix the correct target before distractor construction. Preserve source fact, subject, relation, evidence units, pages and source explanation together; verify again after option assembly.

F. Alternatives come from compatible relation families and retain their own source evidence. Reject equivalent values (including simple time-unit conversions), cached semantic peers and alternatives also supported for the current subject.

G. Bounded candidate generation and global selection penalize reuse after the first placement, cap distractor reuse at two, reject duplicate/near-duplicate sets and prefer varied correct targets.

H. Maximum two questions per primary concept, relation/form diversity where supported. CN accepted evidence supports definitions only; unsupported categories are not fabricated. Educational and OCR fixtures exercise definition/identification, with explicit purpose and numeric tests.

I. Contention-window baseline: page 26 explicitly establishes option C. D belongs to another subject's definition. No confirmed answer-binding defect. The browser source panel displays the same page for MCQ and matching feedback.

J. CN requested 12 MCQs: nine baseline questions become five stricter final questions. Across five stable seeded count requests, 24 final displayed items were manually reviewed against local source evidence: all GOOD/ACCEPTABLE. Match-only: two sets, three and six pairs, nine distinct supported learning items. Mixed: four MCQs + four clozes + one four-pair set; primary fact/concept/relation reuse across formats is zero. All nine final CN pairs were reviewed.

K. Known wrong keys in the reviewed final CN sample: **0**.

L. Multiple-correct and unsupported-correct answers in that sample: **0 / 0**.

M. CN distractor maximum reuse **8 → 2**, mean **6.75 → 1.667**, duplicate option sets **3 → 0**. Unique options stay nine as placements decrease **36 → 20**; the source vocabulary is limited. A/B/C/D all occur across the larger reviewed sample.

N. Live browser Q1→Q5→Q1 preserved MCQ order, selected answer and feedback. Matching Next/Previous preserved opaque-ID order, selections and 2/3 score. Row-level correction and page source were checked; six viewport checks have no page overflow or launcher overlap. All-correct matching also shows a numerical score.

O. Cached-model generation in the final audit is below one second (maximum 806ms on that run); live artifact cache hits and cold creation are separately recorded. No new encoder, no extra semantic batch, zero artifact Qwen calls. Assistant stays existing_qwen.

P. Knowledge/backend suite **279 passed**, final hardening **43 passed**. Frozen-system regressions include Assistant 439, Search 157, KG 32, Events 76, staff 76, notifications 51, circulation 40, unit 37 and security 116 passed / 10 skipped. Isolated suites overlap. Events uses a test-only fixture-clock alignment without production edits.

Q. Full frontend run **289 passed**; after the final all-correct score change, focused Knowledge tests **43 passed**. One unrelated flashcard keyboard timing failure passed on rerun; disclosed rather than hidden.

R. Production build **PASS**, lint **zero errors**. Existing lint and Vite large-chunk warnings remain.

S. Exact changed/new files in this phase:

Production:

- `rag/services/document_knowledge.py`
- `rag/services/knowledge_artifacts.py`
- `rag/services/knowledge_quiz.py`
- `rag/services/knowledge_quiz_relations.py`
- `rag/services/knowledge_mcq.py`
- `rag/services/knowledge_match.py`
- `frontend/src/components/knowledge/KnowledgeTools.tsx`
- `frontend/src/components/knowledge/Quiz.tsx`
- `frontend/src/lib/knowledgeArtifacts.ts`

Tests:

- `tests/test_quiz_v2_2.py`
- `tests/test_knowledge_quiz.py`
- `tests/test_knowledge_artifacts.py`
- `frontend/tests/knowledge-artifacts.test.tsx`

Support:

- `scripts/check_quiz_v2_2.py`
- `scripts/test_quiz_v2_2_regressions.py`
- `scripts/report_quiz_v2_2.py`

T. Required reports:

- `reports/mcq_v2_2_root_cause.json`
- `reports/mcq_v2_2_answer_integrity.json`
- `reports/mcq_v2_2_option_diversity.json`
- `reports/mcq_v2_2_cn_live.json`
- `reports/mcq_v2_2_frontend.json`
- `reports/mcq_v2_2_regression.json`
- `reports/mcq_v2_2_decision.md`
- `reports/match_v2_2_root_cause.json`
- `reports/match_v2_2_relation_quality.json`
- `reports/match_v2_2_cross_format_diversity.json`
- `reports/match_v2_2_cn_live.json`
- `reports/match_v2_2_frontend.json`

Additional source hashes, final API evidence, OCR fixture statistics, cleanup evidence, XML/logs and screenshots are retained. Private question/model text is kept out of permanent JSON reports.

U. The reported wrong-key case could not be reproduced, so strict overall acceptance remains PARTIAL. Candidate validation is deterministic and conservative; limited or ambiguous notes yield partial counts. Existing persisted semantic-peer metadata is reused; relationships outside that metadata depend on lexical/source-binding checks. Numeric equivalence covers basic durations, not arbitrary dimensional analysis. Stable requested-count seeds are reproducible; refresh does not imply a new quiz. No frozen subsystem or core 3.2.1 ranking/view changed. This phase stops here.
