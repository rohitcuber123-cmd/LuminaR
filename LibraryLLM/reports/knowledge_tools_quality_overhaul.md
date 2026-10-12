# Knowledge Tools quality overhaul

2026-10-07 · DocumentKnowledgeModel 3.2.1 · Existing LuminaR frontend `/llm`.

Implemented and validated the shared architecture. The reviewed concept/card samples exceed the requested 90% usefulness threshold. Quiz coverage on the real CN PDF remains partial; this report does not claim universal quality or a blanket PASS for every document.

## AA. Architecture before

The five tools independently interpreted raw document chunks. Frequency-driven noun phrases and short lecture headings could reach output without complete explanatory evidence. Lexical-only deduplication preserved doubled headings and did not distinguish generic repeated language from useful technical terms. Quiz builders had narrower independent evidence rules.

## AB. Architecture after

Existing extraction → normalized structural source units → supported concepts/facts/relations → inspectable ranking → bounded CPU semantic deduplication and diversity → one session DocumentKnowledgeModel → all five artifact renderers. The upload/OCR and interactive Document RAG paths remain unchanged.

## AC. Document knowledge model

`rag/services/document_knowledge.py` provides source_units, concepts, definitions, facts, relations, examples, processes and section_structure. Evidence preserves source chunk, page, known section, exact source excerpt and normalized display text. Confidence is a heuristic, not a calibrated probability. Limits include 2,200 source units, 192 embedding candidates and 30 concepts; adaptive output targets are 12/20/30. Large inputs expose sampling status.

## AD. Extraction root cause

Repeated frequency was promoted without sufficient structural or factual support. Line-wrapped subjects could become separate terms; low-value sections, doubled headings and rhetorical fragments lacked shared rejection gates. Fixes apply to source units and evidence quality rather than individual unwanted words.

## AE. Ranking strategy

Scores expose heading support, explicit definition, capped frequency, page spread, specificity, source relations and multiword support, minus genericity/fragment penalties. Generic vocabulary is a penalty signal, not an exclusion list. Complete explicit fact families are retained conservatively so diversity selection does not remove all valid distractors. Explanations use the strongest complete supported sentence.

## AF. Live before / after

The legacy run on the supplied 29-page CN PDF ranked acknowledgment, stations, Transmission and idea near the top and retained doubled Sliding Window/Noiseless Channel headings. The final run yields 30 explained concepts, led by send window, Flow control, Vulnerable time and Error control. Sliding Window and Noiseless Channel appear once. Page buttons replace numbered source links; desktop uses two columns, narrower screens one column and content-sized cards.

## AG. Boilerplate / duplicate filtering

Repeated headers/footers, page numbers, preface/acknowledgment/reference sections, adjacent equivalent phrases, unsupported/incomplete paragraphs and rhetorical questions are filtered or deprioritized only for Knowledge Tools. Existing RAG keeps its source text. Wrapped subjects are normalized conservatively. Formula layout and perfect PDF structure recovery are outside these heuristics.

## AH. Semantic deduplication

One pruned MiniLM CPU batch supports similarity suppression and MMR diversity. Distinct related definitions survive; lexical normalization also collapses equivalent forms. The encoder is separate from Search embeddings, indexes and GPU Qwen state. The first generation calls it once; later artifact views reuse the model.

## AI. Shared artifact pipeline

All production renderers consume accepted shared-model evidence. They do not independently re-extract chunks. Cards reference accepted fact IDs, summaries select section-distinct facts, maps use known organization plus explicit relations, and quizzes validate accepted evidence for contradictions, ambiguity, compatibility and answer leaks.

## AJ. Summary quality result

CN quick summary: ACCEPTABLE. Five distinct, source-ordered sections provide faithful excerpts with page links. Detailed mode supports up to 12 section selections. Quick mode is still a short extractive overview and currently favors early sections; it is not a comprehensive generated synopsis.

## AK. Flashcard quality result

CN produced 40 cards. Manual first-20 review: 19/20 useful (GOOD or ACCEPTABLE). Cards use complete definitions or supported concept explanations; additional cards require distinct supported facts. Filters expose only types actually present. The ambiguous mathematical-expression card is BAD and remains an acknowledged extraction limitation.

## AL. Mind Map quality result

CN map: ACCEPTABLE. Organization edges are labeled as document topics/source organization, separately from explicit DEFINED_AS, DESCRIBED_AS, USED_FOR, CONTAINS and HAS_STEP relations. Whole-to-component composition points in the correct direction. Rhetorical questions cannot become process steps. Selecting a node shows its explanation/relation and source pages. Maps are bounded to 60 nodes; long labels and large maps still require pan/scroll.

## AM. Quiz quality result

Educational fixture: MCQ-only generated 12 questions; matching-only generated three sets. Mixed request generated three MCQs, two matching sets and four cloze questions, reflecting available distinct compatible facts. Manual review of ten MCQs and two matching sets: all GOOD, with unambiguous supported answers, compatible source-derived alternatives and correct stable-ID matching.

Real CN PDF: four cloze questions in the mixed 12-question request, zero MCQs and zero matching sets. Insufficient compatible evidence is explained in the UI. This is a remaining coverage gap; unrelated distractors or fabricated matches are not used to fill the requested count. The reviewed MCQs/matches are from the educational fixture, not the CN PDF.

## AN. Optional Qwen quality-pass decision

Keep deterministic production generation. An isolated authenticated loopback experiment used the existing resident Qwen, at most one 192-token selection call per request, and validated returned IDs. On the earlier shared-model CN candidate set it kept only five of 30 concepts (3,911.97 ms); on the educational set it kept all 20 unchanged (10,820.12 ms). The small comparison demonstrated coverage loss or added time without a demonstrated quality gain. Production makes zero Qwen artifact calls. The experimental route is absent from the restored normal service. These exploratory results predate the final deterministic refinements.

## AO. Knowledge-model cache

Version/revision/owner-keyed session SQLite cache uses the existing document registry and cascade cleanup. Subsequent tabs avoid JSON source parsing and embeddings. Old model/artifact versions cannot satisfy new requests. Authorization is checked before work and publication; logout/deletion during generation cannot republish a removed document. No permanent Knowledge Graph or private plaintext RAM cache is added. Runtime metrics contain numeric counts/timings, not document text.

Per-user admission allows one active distinct job, joins identical requests, bounds total CPU leaders to three and returns retriable 429 responses for excess work. Different users can progress independently; there is no artifact GPU queue. The UI disables duplicate work immediately and shows real loading/error/retry states.

## AP. Artifact generation latency

Final authenticated HTTP wall times on this development machine, excluding already-completed upload:

| Document | First shared-model build + concepts | Subsequent new artifact views |
| --- | ---: | ---: |
| CN, 29 pages | 1548.95 ms | 23.70–36.91 ms |
| Educational fixture | 331.25 ms | 21.91–32.79 ms |

Earlier exact-artifact replay returned the same ID in roughly 19 ms. Fresh standalone Python/model startup took approximately 13–14 seconds in unloaded runs; one run under concurrent frontend CPU load took 20.7 seconds. These are local observations, not a universal latency guarantee. Interactive Document RAG source/encoder/retrieval behavior was not changed.

## AQ. Manual quality review and validation

Real CN PDF: first 15 ranked concepts 14/15 useful (93.3%); first 20 cards 19/20 useful (95%). One mathematical-layout item in each sample is BAD. The ten fixture MCQs and two matching sets were GOOD. Summary and map were ACCEPTABLE. Per-item ratings, pages and reasons are in `knowledge_quality_review.json`; these small samples do not establish accuracy rates.

Backend isolated regression groups: 1121 passed, 10 skipped, zero failures, including 206 Knowledge/Document privacy/latency checks. Frontend: 279 passed. Build and lint passed with existing warnings. Added structural/ranking/dedup/evidence/quiz tests exceed ten, and new shared/cache/privacy/admission tests exceed six. Isolated groups avoid pre-existing cross-suite fake-database fixture interference seen in a combined invocation.

Source-hash audit: 238 existing source files checked; only eight intended Knowledge Tools source files changed, with no unexpected changes to Search/HNSW, Assistant/research, recommendations/KG, Events, Book RAG or interactive Document RAG. New production files are only the shared Knowledge model and its CPU encoder. Browser checks covered all five views, real loading, page-source navigation, desktop two-column and mobile one-column layout with the workspace sidebar collapsed. Temporary viewport overrides were reset.

## AR. Remaining quality limitations

CN MCQ/matching coverage remains incomplete. Plain text extraction can flatten superscripts/formulas and retain awkward original prose. Strict complete-sentence gates may omit useful punctuation-poor/OCR fragments. Quick summary coverage is limited; maps can be large; confidence is uncalibrated. The first-ranked review samples do not certify every generated item or arbitrary documents. Cached private knowledge shares the existing session document privacy lifetime and is removed with it; session persistence is not permanent publication.

Temporary account/uploads and private review scratch files are removed after review; completion counters are recorded in `knowledge_quality_cleanup.json`. Screenshots preserve only the requested UI proof. The user's original local PDF is unchanged.

Evidence: `knowledge_quality_final_live.json`, `knowledge_quality_live.json` (bounded exploratory Qwen comparison), `knowledge_quality_review.json`, `knowledge_quality_regressions.json`, `knowledge_quality_source_audit.json`, backend JUnit XML and frontend/build/lint logs.
