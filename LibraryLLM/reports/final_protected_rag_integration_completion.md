# LuminaR protected RAG integration closure — 11 November 2026

## A. Overall result

**PASS for the approved bounded explicit-fact integration and exact reviewed-source contract.** The observed incorrect Qwen answer to the 61-minute question is no longer returned with a supporting citation. This is a bounded factual safeguard, not a general natural-language entailment guarantee. No deployment or commit was made.

## B–C. Source checkpoint and authorized scope

Branch `codex/search-v11-finalization`; HEAD `606f0dfce3970bea8e6fc2b62d243433d1a66b8a`. The exact accepted hashes and old-to-new source review are in `final_protected_rag_integration_source_contract.json`. The user authorized the production answer verifier, the minimum `rag/qa.py` response-boundary change, and exact reviewed source acceptance. Existing fast-filter, authorization, Search, KG, and application repairs were retained. The large preexisting dirty tree was neither reset nor committed.

## D–G. Root cause, verifier, applicability, and QA boundary

`LuminaRAG.ask` previously validated selected evidence before Qwen generation, then attached sources to the generated answer without checking its material claim. `rag/citation_boundary.py` maps authorized pages; it does not establish factual consistency. The new pure `rag/generated_answer_verification.py` shares one implementation with the isolated pilot via the `evaluation/` re-export. It checks bounded explicit facts using the original question, selected authorized chunks, answer, selected source ID, and chunk IDs. It parses identifiers, dates, numeric values, explicit field and entity relationships, negation, and exact hour/minute/second conversions. It makes no network, database, or model calls.

In `rag/qa.py`, a `SUPPORTED` answer within `bounded_factual_scope` is checked immediately after generation and before source construction. `VERIFIED` preserves the answer and citations. `CONTRADICTED` and `UNKNOWN` become `NOT_SUPPORTED`, use a conservative unable-to-verify answer, and have no sources. `ABSTAINED` preserves the conservative text but has no sources. Definitions, summaries, and broader explanations remain on the existing response path. There is no regeneration loop.

## H. Citation and source authorization

The verifier consumes only the existing authorized selection; it cannot fetch another passage or accept a model supplied citation. An unselected chunk ID or mismatched selected source fails verification. Existing library membership, personal session, READY/current-generation, revocation, and page-mapping checks remain in their established upstream and HTTP boundaries. The integration and independent contracts cover foreign library/session, expired or unselected source, wrong citation, and selected-document cases. The native personal and institution examples below use injected task-owned authorized chunks, not a live entitlement service.

## I–L. Original case, private cases, negative and positive grounding

In 14 native Qwen requests, the equivalent-units question with evidence `Device UMJWWTJ duration is 61 minutes` again generated `No` for 3660 seconds. Evidence was `SUPPORTED`; the post-generation check was `CONTRADICTED`; final response was conservative with **zero citations**. A separate literal `Does 61 minutes equal 3660 seconds?` request generated a correct Yes and retained its citation. Controlled generation injection of `No` through the actual QA boundary also rejects the claim.

Private A returned `ALPHA-SEVEN` and Private B returned `BRAVO-NINE`, each verified with one selected citation. Native wrong-field, negation, contradiction, and wrong-unit questions produced `NOT_SUPPORTED` with no citations. Unseen positive, personal, institution, and explicit negative facts retained correct selected citations. Definitions and explanations retained existing answers and citations. No tested case turned into blanket abstention.

## M–O. Isolated, corpus, and held-out results

The original 39 labelled verifier cases remain passing; one additional mixed/limitation case makes the current pilot and held-out suite **40/40** (25 pilot, 15 held-out). Production QA integration is **16/16**. The independent factual evidence corpus, run with an adversarial controlled judge rather than Qwen, accepted **80/80** positive facts and rejected **128/128** negatives, including 40/40 held-out positives and 64/64 held-out negatives. The final focused RAG and safety matrix passed **592/592**. See the focused JUnit XML and deterministic evaluation JSON.

## P–Q. Real Qwen and answer correctness

The native trace used existing local `Qwen/Qwen2.5-3B-Instruct` revision `aa8e72537993ba99e69dfaafa59ed015b17504d1` on `cuda:0`; no weights were replaced. Its 14 task-owned injected-chunk requests record raw generated answers, evidence verdicts, post-generation decisions, final QA responses, source IDs, timing, and exact source fingerprints in `final_protected_rag_integration_native.json`. Eight answers entered the bounded verifier: seven `VERIFIED`, one `CONTRADICTED`, zero final false cited answers. Six other requests followed existing evidence/definition paths. The captured QA results were run through the actual `rag/api.py` adapter code as a **14-case HTTP-shape replay**; no live network HTTP request or second inference is claimed.

## R–U. Protection review, pins, approval, and mutation guards

The previous closure had four backend source-acceptance identities failing. The original assistant and latency manifests expected historical `llm.py`/`fast_filter.py` bytes, and the two proposed-guard cases invoked those old baselines. Two earlier independent document-definition failures were a genuine semantic handoff regression, already repaired before this integration. The historical manifests and frozen QA projection remain intact. `tests/contracts/rag_grounding_v2q.py` now accepts only the exact reviewed current `qa.py`, `llm.py`, `fast_filter.py`, factual, document-grounding, verifier, and citation-boundary bytes. It rejects the old runtime QA because that version can cite the demonstrated contradiction. Tests for one-byte and substantive mutations, including import, return, selected-source, and verifier changes, pass. The two historical projection tests now load their frozen reviewed QA fixture rather than the new live QA path; no frozen assertion was disabled.

The user expressly approved this exact revision. No independent signer or repository contract-owner mechanism was found; the source-contract JSON records that limit. The final independent protected contract group passed **85/85**. Exact source fingerprints still match the native trace and guard. No wildcard acceptance or automatic manifest rebaseline was introduced.

## V–Z. Regression, performance, frontend, build, and lint

The stable-source full backend runner completed **38 isolated groups: 3,215 raw passes, 0 failures, 20 raw skips**. De-duplicating JUnit test identities yields **3,133 unique passes, 0 failures, 10 unique skips**; several groups intentionally repeat tests. The focused 592-case run adds 113 test identities outside that grouped inventory. The owned test Mongo instance and fallback database were removed. The earlier intermediate grouped run with historical tests pointed at live QA is superseded by this stable-source run.

Across 14 native requests, 8 entered the verifier; median verifier latency was **0.183 ms**, maximum **2.054 ms**, and median total QA latency **2,301.035 ms**. The trace recorded 18 model calls across all requests and **zero additional calls from verification**. There was no paired deployed before/after latency test, so no end-to-end speed improvement is claimed. Frontend full test log totals **1,033 passes, 0 failures, 0 skips**. Production build exited 0; lint exited 0 with warnings. Frontend source was not changed in this closure.

## AA–AB. Search/KG and production preservation

Search/KG recovery regressions passed **288/288**; E-01–E-04 and catalogue contrast repairs remain. A read-only production snapshot before and after the work is byte-equivalent as serialized JSON for its tracked state and 33 index collections. It includes estimated global catalogue count **5,000,000**, global HNSW/KG pointers and metadata, tenant Search/KG generations, and tenant collections. The comparison does not scan all five million records. No index rebuild, production Mongo configuration change, telemetry enablement, document deletion, deployment, or commit was performed.

## AC. Exact closure files and fingerprints

| File | SHA-256 |
| --- | --- |
| `rag/qa.py` | `ab7f3d2baa5e828a5c2eb5fe6e6e9ac8bdb6e596cb3fe70348edb7bde88f9830` |
| `rag/generated_answer_verification.py` | `c1e81fa77e7dd3139cc03ed13c095f12e1d6f576cac57349fa788260b9edbed9` |
| `evaluation/generated_answer_verification.py` | `16044f6182aef41a6173919233aba2b41982487a789e31bb48845921e41d1ecc` |
| `tests/contracts/rag_grounding_v2q.py` | `5935d7210a62506973b3014f28609c30cbc30c2984d8ad2bbb55b7cc346e979d` |
| `tests/test_generated_answer_qa_integration.py` | `51dec227a929df0c7d2631da299baed37c8f9b463d7d6c6e6eb6cfb68ba45632` |
| `tests/test_assistant_backend.py` | `5f472aae1806abc41467f19bb921cb135af51a37c150bdded1527e7b2e57f21b` |
| `tests/test_document_rag_latency.py` | `7882148255d9b529c9032e8d488cd9fbb06d7132c5bdfc579b37f48fffac835b` |
| `tests/institution_v2o1/test_proposed_contracts.py` | `1265eebcc6994a11c26892bd6fa5a5be2790eecd2ef3363bc563b86c1721cf50` |
| `tests/institution_v2o3_closure/test_actual_contracts.py` | `746b4a31e80a422843ba095216610dd68854284d995d09278d6408433e67b7c7` |

`rag/llm.py`, `rag/fast_filter.py`, `rag/factual_evidence.py`, `rag/document_grounding.py`, and `rag/citation_boundary.py` retain their previously reviewed hashes, recorded in the source-contract JSON. The two historical accepted-source manifests are unchanged. The scoped tracked diff passes `git diff --check` (Git reports only line-ending conversion notices); unrelated preexisting files elsewhere in the dirty tree have whitespace findings and were not changed for this closure.

## AD–AE. Limits and next action

The verifier handles bounded explicit factual propositions and deterministic time conversions. It does not prove correctness for unrestricted prose, ambiguous relations, arbitrary units, or every generated summary. Native tests use injected authorized chunks and the HTTP result is an adapter replay, so neither demonstrates a live production entitlement request. The full backend and frontend gates are green for this source snapshot. The next engineering action is the user's normal review of this uncommitted change set; this closure stops here without deployment or new modules.

## Evidence files

- `final_protected_rag_integration_source_contract.json`: reviewed exact pins and approval status.
- `final_protected_rag_integration_native.json`: native Qwen questions, raw answers, final responses, citations, and timing.
- `final_protected_rag_integration_http_replay.json`: API adapter replay over captured native QA responses.
- `final_protected_rag_integration_performance.json`: measured verifier and QA timing.
- `final_protected_rag_integration_focused_final.xml` and `final_protected_rag_integration_protected_final.xml`: focused and protected test cases.
- `institution_v2q_final_protected_rag_integration_stable_backend.json` and matching group XMLs: full backend.
- `final_protected_rag_integration_frontend.log`: full frontend test log.
- `final_protected_rag_integration_preservation_before.json` and `_after.json`: read-only production comparison.
- `final_protected_rag_integration_stable_backend_isolation.json`: owned Mongo cleanup.
- `final_protected_rag_integration_qa.json`: machine-readable final status.
