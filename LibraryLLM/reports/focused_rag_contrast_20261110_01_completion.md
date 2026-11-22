# LuminaR focused RAG and catalogue repair — focused_rag_contrast_20261110_01

## A. OVERALL RESULT

**PARTIAL.** The three confirmed factual fast-accept bypasses and Private A/B validator asymmetry are repaired in tested explicit-fact scope. All four confirmed catalogue contrast failures are fixed. The final backend run retains 6 frozen-source contract failures; no assertion or manifest was changed to conceal them. A native equivalent-units question still receives an incorrect generated “No” despite a correct supported-evidence decision. This prevents an end-to-end PASS.

This phase changed five source/test files, used isolated synthetic fixtures, and stopped after these two repair areas. No deployment, commit, shared service restart, production auth/telemetry change, or existing index rebuild occurred.

## B. CURRENT SOURCE BASELINE

Branch `codex/search-v11-finalization`, HEAD `606f0dfce3970bea8e6fc2b62d243433d1a66b8a`. The dirty working tree, 1719 current source hashes, configurations, prior evidence and resident state were captured in [focused_rag_contrast_20261110_01_preflight.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_preflight.json); comparison uses that actual tree, not HEAD. Accepted E-01–E-04 repairs were included. Final backend source fingerprints stayed identical throughout the complete rerun: [focused_rag_contrast_20261110_01_final_run_sources.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_final_run_sources.json).

## C. CONFIRMED RAG ROOT CAUSES

`compute_alignment_signals` checked factual entity/event overlap but scoped polarity handling chiefly covered motivation queries. `fast_filter_decision` could accept on actor/event alignment without establishing the requested factual field/value. `validate_evidence` trusted the model’s supported flag, allowing an explicit contradiction to survive. Literal factual questions fell through to unconstrained model intent extraction, including unstable polarity/action surface forms. Validation runs before answer generation and receives no generated answer, so it cannot verify the final answer proposition.

The repair adds one bounded explicit-relationship helper shared by the fast filter and validator. It checks field/entity, exact identifiers, decimal quantities and time units, dates, explicit actor/action/target, scoped negation, contradictions, conditional/quantified text and ambiguous references. Clear positive facts retain fast acceptance. Unknown factual grammar loses unconditional overlap-based acceptance and retains semantic validation. It is not a general natural-language theorem prover.

## D. FAST_ACCEPT BEFORE/AFTER

| Case | Expected | Before filter / judge | After filter / validator |
|---|---|---|---|
| v2q2_exact_A_12m_ALPHA | SUPPORTED | NEEDS_LLM_VALIDATION / SUPPORTED | FAST_ACCEPT / SUPPORTED |
| v2q2_exact_B_47m_BRAVO | SUPPORTED | NEEDS_LLM_VALIDATION / NOT_SUPPORTED | FAST_ACCEPT / SUPPORTED |
| factor_12m_A_ALPHA | SUPPORTED | NEEDS_LLM_VALIDATION / SUPPORTED | FAST_ACCEPT / SUPPORTED |
| factor_12m_B_BRAVO | SUPPORTED | NEEDS_LLM_VALIDATION / NOT_SUPPORTED | FAST_ACCEPT / SUPPORTED |
| factor_B_47m_ALPHA | SUPPORTED | NEEDS_LLM_VALIDATION / NOT_SUPPORTED | FAST_ACCEPT / SUPPORTED |
| factor_B_12m_ALPHA | SUPPORTED | NEEDS_LLM_VALIDATION / SUPPORTED | FAST_ACCEPT / SUPPORTED |
| v2q2_analyze_intent_A | SUPPORTED | NEEDS_LLM_VALIDATION / SUPPORTED | FAST_ACCEPT / SUPPORTED |
| v2q2_analyze_intent_B | SUPPORTED | NEEDS_LLM_VALIDATION / NOT_SUPPORTED | FAST_ACCEPT / SUPPORTED |
| explicit_entity_B | SUPPORTED | FAST_ACCEPT / NOT_SUPPORTED | FAST_ACCEPT / SUPPORTED |
| neg_wrong_field | NOT_SUPPORTED | FAST_ACCEPT / NOT_SUPPORTED | FAST_REJECT / NOT_SUPPORTED |
| neg_negated_statement | NOT_SUPPORTED | FAST_ACCEPT / NOT_SUPPORTED | FAST_REJECT / NOT_SUPPORTED |
| neg_contradictory | NOT_SUPPORTED | FAST_ACCEPT / SUPPORTED | FAST_REJECT / NOT_SUPPORTED |

All three original negatives changed from FAST_ACCEPT to FAST_REJECT. The nine paired positives now all accept; the before native judge accepted only four of nine positives. Details and raw native traces remain in the original and current run files.

## E. NEGATION HANDLING

Negation is interpreted within the explicit assignment or actor/action/target. A negative elsewhere in the passage does not by itself veto a positive fact. Opposed assertions or ambiguous pronoun continuations conservatively return internal UNCERTAIN, mapped to the existing NOT_SUPPORTED decision with a reason. Positive and explicit-negative controls pass; no new public verdict enum was introduced.

## F. WRONG-FIELD HANDLING

Requested relationships must bind the field/entity or full actor/action/target. Calibration evidence cannot establish a service code merely by sharing the sensor name. Wrong actor, action, target, code, value, unit and date controls reject. Source entitlement is still established by application authorization before semantic validation; the helper cannot grant document access.

## G. CONTRADICTION HANDLING

Distinct positive values or opposed assertions for the same explicitly bound relationship produce UNCERTAIN and cannot be overridden by a confident model supported=true. Original contradiction: before FAST_ACCEPT and direct native SUPPORTED; after FAST_REJECT and NOT_SUPPORTED, with a generated evidence limitation and zero citations.

## H. FACTUAL INTENT CLASSIFICATION

All ten requested question forms produce the expected positive/negative polarity in the final controlled classifier test. Literal grammar is general to factual questions, not calibration-specific, and does not retain arbitrary private queries in the shared LRU. Causal/narrative questions and existing informational book classifications retain their established paths. The deliberately wrong classifier stub measures the fallback boundary; it is not evidence that native Qwen scored 3/10. The historical negative-polarity native result remains historical evidence.

## I. PRIVATE A/B VALIDATION

The current-source before pilot reproduced A SUPPORTED versus B NOT_SUPPORTED with the original 12/47-minute code fixtures. Final native QA returns ALPHA-SEVEN for A and BRAVO-NINE for B, each with the correct injected document/page source. Code, document-label and duration swaps no longer change the explicit validation relationship. Real authorization is tested separately; the native pilot injects only owned synthetic chunks.

## J. HELD-OUT POSITIVE/NEGATIVE RESULTS

The corpus was frozen at 208 cases before source integration, with independently template-assigned labels and SHA-256 `037c92584420b266ae4c6cf94ee083c1c9d305828bbeb2204f35d42ad3afe89a`. Development: 20 positive/32 negative; regression: 20/32; held-out: 40/64. Every primary case passes, including all 104 held-out cases. A separate 14-case review challenge exposed mixed-case identifier and proposed-value weaknesses in the initial candidate; final corrections pass 14/14. That challenge is development evidence, not an untouched final hold-out. No gold labels were changed. The held-out corpus varies values/entities within shared template families, so this is not production generalization evidence.

## K. REAL QWEN EXPERIMENTS

Model `Qwen/Qwen2.5-3B-Instruct`, revision `aa8e72537993ba99e69dfaafa59ed015b17504d1`, CUDA device `cuda:0`, NF4 4-bit with double quantization and float16 compute. One task-owned model instance ran at a time; cached weights loaded offline. Final source fingerprints, exact prompts, decoding settings, generated answers and citations are preserved in [focused_rag_contrast_20261110_01_final_native.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_final_native.json), with actual decoding settings in [focused_rag_contrast_20261110_01_final_native.log](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_final_native.log).

There are 46 direct validation cases, all matching independent labels: 24 positives and 22 negatives. Six model-fallback trials (three positive, three negative) actually invoke the native parser/judge. Explicit deterministic cases do not invoke Qwen merely to rejudge a proven fact. Fourteen full semantic QA responses execute native answer generation using injected owned retrieval fixtures: all evidence verdicts are correct; 5/6 supported generated answers are correct and all eight negative responses express limitations with no citations. The equivalent-units positive produces “No” and remains unresolved. This is not a model-verified complete grounding fix.

## L. FALSE-SUPPORT METRICS

Controlled explicit-fact corpus plus review challenge: 0/136 unsupported cases labelled supported, rejection 136/136. Primary held-out false support: 0/64; 16 held-out cases are deliberately ambiguous. Primary corpus has 32 ambiguous cases overall; internal UNCERTAIN remains distinguishable in detailed validator results. Native direct pilot: 0/22 unsupported cases accepted. These semantic label counts do not conceal the one wrong generated answer under a SUPPORTED label.

## M. VALID-ANSWER SUPPORT METRICS

Explicit evidence acceptance: 86/86 positives, 0 false negatives. Primary held-out: 40/40 supported, recall 100% in this template scope. Native paired evidence positives improved from 4/9 to 9/9. Native direct pilot positives: 24/24. End-to-end generated positive correctness is **5/6**, not 6/6: source-supported validation alone does not guarantee a correct generated answer.

## N. RAG AUTHORIZATION PRESERVATION

No membership, document ownership, session ownership, generation readiness, visibility, source citation entitlement or revocation implementation changed. Existing isolated private Knowledge Tools/OCR, institution membership/isolation, personal document/session, Assistant and tenant authority suites execute as part of the complete inventory. They use existing test authentication with owned synthetic records. No live foreign institution, user credential or private record was probed. Frozen-source failures are enumerated separately; they are not authorization bypasses.

## O. RAG PERFORMANCE IMPACT

Controlled fast-filter median: before 0.017 ms, final 0.083 ms across 208 cases. Controlled validator median: 0.048 ms; these timings use a stub and are not GPU latency. The primary explicit corpus retains 80 useful fast accepts and 128 rejects, with zero judge calls. In the original twelve native cases, the old filter would invoke the model validator on 8/12; final requires none for those explicit facts.

Native fallback parser/judge generation median: 7039.57 ms across 12 wire calls. Final native QA total median: 2901.02 ms across 14 responses, after-only. No paired before total-QA timing was captured; no end-to-end speedup is claimed. Inspection is limited to selected top-one/top-three evidence and 24,000 characters; no document scan or model/index replacement was introduced.

## P. GLOBAL CATALOGUE ORIGINAL AXE RESULTS

Before Chromium reproduced four serious failing text nodes under one color-contrast rule: brand and author text on the magenta cover, repeated in carousel and grid. Effective brand foreground #ebb6c3 on #c81d4f was 3.2:1; author #eec1cb was 3.5:1. Both small normal-text nodes require 4.5:1. Exact selectors, computed ancestors, opacity, typography and axe data are in the selector evidence.

## Q. FIXED SELECTORS AND COLOR TOKENS

Only `BookCover.tsx` changed: `.book-cover-brand` loses `opacity-70`; `.book-cover-author` loses `opacity-75`. The palette, layout, typography, navigation, spacing, controls, variants, cover renderer and theme tokens remain intact. No text was hidden, made decorative, enlarged to evade the threshold, or covered by an opaque panel. The source diff and exact selectors are linked below.

## R. NEW CONTRAST RATIOS

Chromium computes opacity 1 and foreground #faf8f4 against the same #c81d4f effective base background. All four previously failing nodes now have calculated contrast 5.2872:1, above 4.5:1. Browser axe reports no failures for these nodes. Decorative overlay combinations can still produce axe incomplete checks; this measured result is not a claim about every possible cover datum/variant.

## S. CHROMIUM AXE AFTER-RESULTS

Zero axe violations in all 70 catalogue state checks. Each width/preferences combination renders loaded, search, empty, paused-loading and controlled 503 error states; actual DOM state counts confirm they were reached. Zero uncaught page errors. The matrix records 28 expected 503 console messages from intentionally controlled error-state fetches; these are retained, not suppressed. The separate cross-page run has no console errors. Axe incomplete color-contrast observations are preserved and require further manual review; no automated audit is described as full WCAG certification.

## T. LIGHT/DARK THEME RESULTS

Light and dark OS preferences were both emulated in Chromium. Catalogue actual backgrounds remain rgb(250,248,244) under both: no alternate catalogue dark theme/provider exists. Light appearance and dark preference checks pass; a genuine separate dark appearance is NOT_RUN/unsupported. No dark theme was added.

## U. RESPONSIVE VIEWPORT RESULTS

Widths 320, 360, 390, 430, 768, 1024 and 1440, two OS preferences and five states produce 70 measurements, with zero horizontal overflow. Original route/viewport sweep also reports zero overflow. Four 390px screenshots were captured; the loaded screenshot was visually inspected. Fourteen keyboard input/Tab/Enter submissions pass, with associated labels, in-view input bounds and a 2px visible focus outline. This does not certify every control/data-dependent clipping condition.

## V. CROSS-PAGE ACCESSIBILITY

Previously passing Analytics (43 passes), Staff Intelligence (38), Private Catalogue (34) remain at zero violations. Added real Chromium checks cover Home recommendations, global/private book details and Search under both OS preferences, plus Notification Center and expanded catalogue filters: ten checks, zero violations, no console or page errors. Shared theme tokens were not edited. Large-text/decorative-overlay and all non-text contrast combinations were not exhaustively manually certified, so their broad QA status is PARTIAL.

## W. SOURCE CHANGES

| Path | Before SHA-256 | After SHA-256 |
|---|---|---|
| [rag/llm.py](D:/SDC/LibraryLLM/rag/llm.py) | `d369e26fcbe458964bf642a057ca79212a63f48a6acf2b1c0a12590003f5cc1b` | `6f35a4034ae0acff78596b8cc81ed9c355a055f6560cf8dd703d907c02aab2da` |
| [rag/fast_filter.py](D:/SDC/LibraryLLM/rag/fast_filter.py) | `1da09b70cd1ed73a45b5d3362149e7e19118dc1d7ffadd76853ca813e1578c5f` | `f500e3d32286e2d560512db2293615f0ea0a035c12b410fa03e71e3541d8d6fe` |
| [frontend/src/components/BookCover.tsx](D:/SDC/LibraryLLM/frontend/src/components/BookCover.tsx) | `61068e80b7fd0fbce54db671a2e2ead0f7bf20c6d96b8501df2b5415ea85f820` | `37a6a7394b890562e96b0925870f99b1ee4a2a75f5c2a417b45260a0135cb062` |
| [rag/factual_evidence.py](D:/SDC/LibraryLLM/rag/factual_evidence.py) | `NEW` | `aec553cd0799bb2e5cfcfb8ab2f1136c51e9b5bc06d2f09800b7c96b9c898d0a` |
| [tests/test_factual_evidence_validation.py](D:/SDC/LibraryLLM/tests/test_factual_evidence_validation.py) | `NEW` | `c857067ff12574a0ff17c0e010c93943db7584d97539f702ffad7dae8286cb37` |

Final focused patch SHA-256: `1b7f6644700ef7fa89138f978b58833d89837663c7d91ad09d5c647329a551e6`. [focused_rag_contrast_20261110_01_final.patch](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_final.patch) and [focused_rag_contrast_20261110_01_changed_files.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_changed_files.json) capture only this phase’s delta, preserving pre-existing uncommitted changes. Scratch harnesses and run-specific reports are additional evidence files, not application changes.

## X. PROTECTED CONTRACT RESULTS

Independent closure contracts: **73 passed / 2 failed / 0 skipped**. The two accepted-version fixtures reject the intentionally modified llm/fast-filter bytes. The assistant original hash assertion and document latency source manifest also reject the new bytes; all six distinct backend failures are enumerated in regression JSON with original assertion messages. Separate `institution_v2o3` contracts pass; the original historical qa.py projection remains intact.

No frozen test or protection manifest was edited or disabled. Passing negative mutations alone cannot prove a revised guard valid while its accepted baseline is rejected. Scoped user authorization names llm.py/fast_filter.py, but automatic pin changes are forbidden. The exact final patch and proposed transitive source pins are prepared separately for formal review, including the new helper. There is no new source-hash exception or broad rebaseline.

## Y. SEARCH/KG RECOVERY REGRESSION

Dedicated E-01–E-04 recovery tests: 41 passed / 0 failed / 0 skipped, including the combined 20-scenario interaction test. Every accepted recovery implementation/test/contract source hash remains unchanged in the preservation audit. Last-good generation, publication barriers, native job protocols and tenant-authority implementation were not modified.

## Z. BACKEND REGRESSION

Complete final-source accepted product inventory: 38 groups, **3199 passed / 6 failed / 20 skipped**. Added recovery + focused tests: 68 passed / 0 failed / 0 skipped. Combined raw executions excluding the duplicate independent contract rerun: 3267 passed / 6 failed / 20 skipped. **Unique combined tests: 3185 passed / 6 failed / 10 skipped.** Independent protected rerun is reported separately above. New focused tests: 27 passed / 0 failed / 0 skipped. All retained failures concern frozen source acceptance, and their raw logs/XML remain available. The earlier intermediate-source run is preserved separately and is not substituted for final results. No tests were suppressed.

## AA. FRONTEND REGRESSION

Full final frontend script: **1033 passed / 0 failed / 0 skipped**. This includes catalogue/search/filter/runtime, role/route isolation, Staff Intelligence/progress and existing accessibility regressions. Real-rendering Chromium evidence supplies contrast checks beyond JSDOM. No catalogue API, entitlement or recommendation ownership code changed.

## AB. BUILD AND LINT

Production frontend build: PASS. Lint: PASS, 16 existing warnings retained. Build warnings and full logs are preserved; no warning was hidden or converted into an invented clean result.

## AC. PRESERVATION AUDIT

Actual-tree source changes are limited to frontend/src/components/BookCover.tsx, rag/fast_filter.py, rag/llm.py, plus the new helper and focused tests. Unapproved changes: []. E-01–E-04 accepted-source checks: True. Resident-state differences: []. Mongo index definitions unchanged: True; communications unchanged: True; existing configuration files preserved: True. `rag/qa.py`, source authority, transport modules, ranking, Knowledge Tools, circulation, production security/telemetry configuration and recorded prior evidence remain unchanged.

Global HNSW/KG and existing tenant indexes were not rebuilt. Resident global catalogue count, tenant logical fingerprints, generation/job/lock state, assets and index metadata are compared read-only. Large global artifact checks are size/mtime comparisons, not complete byte hashes; global books use estimated count, not a 5M-row content scan. Qwen loaded cached weights offline, with no before/after complete weights digest. No deployment/commit/shared restart occurred. All seven isolated Mongo receipts confirm stopped servers and removed owned roots. Browser cleanup additionally found nine orphaned Vite/npm/cmd processes from the task harness; exact task environment/ancestry was verified before stopping all nine. No shared process was targeted.

## AD. REMAINING LIMITATIONS

1. Six retained exact-source assertions fail pending formal review of the new llm/fast-filter/helper fingerprints. Overall backend/guard PASS is not claimed.
2. Correct evidence validation does not validate generated answer propositions. The native 61-minute/3660-second positive produces “No”; generated positive correctness is 5/6. qa.py remains unchanged as required. A separately reviewed answer-verification interface is needed before claiming complete end-to-end grounding.
3. The new checker covers bounded explicit assignments/events. Unrecognized grammar still uses existing Qwen semantics; pronouns, indirect statements, temporal interpretation and prose entailment are conservative/limited. Template hold-outs are not independent natural-language or production accuracy certification.
4. Native retrieval is controlled synthetic chunk injection; existing service tests establish entitlement. No live private-data security probing occurred.
5. Axe incomplete/decorative-background observations remain for manual assessment. A real separate catalogue dark theme and exhaustive non-text/manual assistive-technology certification are not available in this phase.
6. Expected controlled 503 console messages, all skipped tests, warnings, failed assertions and the first failed native launch (missing PYTHONPATH, then corrected) remain in evidence.

## AE. NEXT ENGINEERING ACTION

Stop this phase. Review the exact focused RAG patch and transitive helper pin proposal before formally changing frozen contracts. Separately authorize/design generated-answer proposition validation for the measured unit-conversion error without weakening source authority or modifying qa.py implicitly. No next phase, deployment, model replacement or index rebuild was started.

## Evidence and machine-readable QA

- [focused_rag_contrast_20261110_01_preflight.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_preflight.json)
- [focused_rag_contrast_20261110_01_authorization.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_authorization.json)
- [focused_rag_contrast_20261110_01_authorization_final.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_authorization_final.json)
- [focused_rag_contrast_20261110_01_rag_results.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_rag_results.json)
- [focused_rag_contrast_20261110_01_native_oracle.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_native_oracle.json)
- [focused_rag_contrast_20261110_01_final_native.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_final_native.json)
- [focused_rag_contrast_20261110_01_contrast_results.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_contrast_results.json)
- [focused_rag_contrast_20261110_01_after_browser.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_after_browser.json)
- [focused_rag_contrast_20261110_01_cross_browser.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_cross_browser.json)
- [focused_rag_contrast_20261110_01_regression.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_regression.json)
- [focused_rag_contrast_20261110_01_formal_guard_proposal.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_formal_guard_proposal.json)
- [focused_rag_contrast_20261110_01_preservation.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_preservation.json)
- [focused_rag_contrast_20261110_01_browser_cleanup.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_browser_cleanup.json)
- [focused_rag_contrast_20261110_01_artifacts.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_artifacts.json)
- [focused_rag_contrast_20261110_01_changed_files.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_changed_files.json)
- [focused_rag_contrast_20261110_01_patch_verification.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_patch_verification.json)
- [focused_rag_contrast_20261110_01_final_native.log](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_final_native.log)
- [focused_rag_contrast_20261110_01_qa.json](D:/SDC/LibraryLLM/reports/focused_rag_contrast_20261110_01_qa.json)

```json
{
  "OVERALL_RESULT": "PARTIAL",
  "RAG_FAST_FILTER": "FIXED",
  "WRONG_FIELD_FALSE_ACCEPT": "FIXED",
  "NEGATION_FALSE_ACCEPT": "FIXED",
  "CONTRADICTION_FALSE_ACCEPT": "FIXED",
  "FACTUAL_INTENT_POLARITY": "FIXED",
  "PRIVATE_B_VALIDATOR": "FIXED",
  "POSITIVE_GROUNDING": "PARTIAL",
  "NEGATIVE_GROUNDING": "PASS",
  "HELD_OUT_EVALUATION": "PASS",
  "REAL_QWEN_VALIDATION": "PARTIAL",
  "RAG_SOURCE_AUTHORIZATION": "PASS",
  "UNSUPPORTED_POSITIVE_COUNT": 0,
  "VALID_POSITIVE_ACCEPT_COUNT": 86,
  "FALSE_NEGATIVE_COUNT": 0,
  "COUNT_SCOPE": "222 controlled explicit-fact validation cases; excludes generated-answer correctness",
  "GENERATED_SUPPORTED_ANSWER_ERRORS": 1,
  "GENERATED_POSITIVE_ANSWER_CORRECT": "5/6 in the 14-response native QA pilot",
  "FAST_FILTER_LATENCY": {
    "n": 208,
    "median_ms": 0.0830499998301093,
    "min_ms": 0.032500000088475645,
    "max_ms": 3.4217000002172426
  },
  "LLM_VALIDATION_LATENCY": {
    "full_qa_validator": {
      "n": 2,
      "median_ms": 2370.675,
      "min_ms": 1833.1,
      "max_ms": 2908.25
    },
    "judge_generation": {
      "n": 6,
      "median_ms": 2649.985,
      "min_ms": 1949.17,
      "max_ms": 3198.29
    },
    "scope": "2 complete native QA validator timings and 6 direct judge generation timings"
  },
  "GLOBAL_CATALOGUE_CONTRAST": "PASS",
  "AXE_VIOLATIONS_BEFORE": "4 serious nodes in one color-contrast rule",
  "AXE_VIOLATIONS_AFTER": 0,
  "NORMAL_TEXT_CONTRAST": "PASS",
  "LARGE_TEXT_CONTRAST": "PARTIAL",
  "NON_TEXT_CONTRAST": "PARTIAL",
  "LIGHT_THEME": "PASS",
  "DARK_THEME": "NOT_RUN",
  "DARK_PREFERENCE": "PASS; catalogue has no alternate dark theme",
  "MOBILE_390PX": "PASS",
  "GLOBAL_CATALOGUE_KEYBOARD": "PASS",
  "ANALYTICS_AXE_PRESERVED": "YES",
  "STAFF_AXE_PRESERVED": "YES",
  "PRIVATE_CATALOGUE_AXE_PRESERVED": "YES",
  "E01_E04_RECOVERY_PRESERVED": "YES",
  "BACKEND": {
    "passed": 3185,
    "failed": 6,
    "skipped": 10
  },
  "BACKEND_GROUPED": {
    "passed": 3199,
    "failed": 6,
    "skipped": 20
  },
  "FRONTEND": {
    "passed": 1033,
    "failed": 0,
    "skipped": 0
  },
  "PROTECTED_CONTRACTS": {
    "passed": 73,
    "failed": 2,
    "skipped": 0
  },
  "BUILD": "PASS",
  "LINT": "PASS",
  "NEW_REGRESSIONS": 6,
  "NEW_REGRESSION_SCOPE": "Distinct failed backend testcase identities; all retained frozen-source assertions, not suppressed",
  "GLOBAL_HNSW_REBUILT": "NO",
  "GLOBAL_KG_REBUILT": "NO",
  "EXISTING_TENANT_INDEX_REBUILT": "NO",
  "RAG_QA_SOURCE_CHANGED": "NO",
  "RAG_FAST_FILTER_SOURCE_CHANGED": "YES",
  "RAG_LLM_SOURCE_CHANGED": "YES",
  "PROTECTED_CHANGE_AUTHORIZED": "YES",
  "FORMAL_PROTECTION_MANIFEST_REVISION": "NOT_APPLIED; separate review required",
  "PRODUCTION_MONGO_AUTH_CHANGED": "NO",
  "PRODUCTION_TELEMETRY_ENABLED": "NO",
  "DEPLOYED": "NO",
  "COMMITTED": "NO"
}
```
