# LuminaR Part 2Q.3 completion

| Item | Executed result |
|---|---|
| A. Result | PARTIAL. Primary digital availability defect fixed; model-reference, validator and browser limitations remain. |
| B. Baseline | Backend 3102/0/20; frontend 1028/0/0. Legitimate dirty work retained. |
| C. Root cause | Digital questions entered physical CHECK_AVAILABILITY; the Book projection and renderer retained stock counts but had no fresh digital authorization signal. |
| D. Exact fix | Narrow request-modality detection, original finite book resolver, fresh authenticated Core digital lookup, strict typed evidence, deterministic response and digital-specific rendering. No new AI intent or persistence. |
| E. Contract | Catalogue presence, physical totals/available counts, canonical resource link, asset presence, access authorization and full-text accessibility are separate. UNKNOWN carries no hidden asset hints. See digital_contract.md. |
| F. Local-only books | Exact library UUID + local book UUID; no Global identity substitute. Tests include authorized digital-only book with no physical holdings. |
| G. Private authorization | Existing membership/code proof, asset visibility, READY state, source/artifact checks and authority barrier; repeat check on open. Foreign/revoked/forged access denied. |
| H. Follow-ups | Real Qwen seven-turn sequence in Global/A/B/I plus 10 linked A/B wording probes. Digital/physical evidence separate. Broader plural comparison and physical-borrow semantics remain partial. |
| I. Global chatbot | Final-runtime and browser Qwen PDF question gives UNKNOWN, no tenant assets or stock-only answer. Global retrieval/provider controlled in lab; production ranking/source unchanged. |
| J. Private chatbot | A/B authorized PDF answers and actual B PDF viewer pass. Final-runtime A/B/I checks retained. Private RAG A supported 2/2; B abstains 2/2 with unchanged protected validator. |
| K. Validator investigation | Isolated alternative failed safety review. No protected patch proposed/applied. Direct authored-intent positives do not establish a fix for actual B pipeline intent. |
| L. Negative evidence | All 25 Part 2Q.2 base cases unchanged. 31 runs/variant: original 6/25 negative acceptances; candidate 10/25. Six positive runs per variant, zero missed positives. Repeat strata/oracle ambiguity prevent universal or cross-phase accuracy claims. |
| M. Approval status | Old 53a4... patch rejected and unapplied; new prompt REVIEW_ONLY, unsafe. No RAG source/manifest/guard changes. |
| N. Browser | All 21 requested areas exercised to bounded extent; overall PARTIAL. A/B/Global genuine Qwen, authorized PDF open, physical follow-up, stale cancellation, unauthorized/revoked denials, no-match and relogin evidence retained. Actual viewport 487 inner/469 client, exact 390 unavailable; keyboard limited to Skip navigation plus existing component checks. |
| O. Backend | 3124/0/20, 38 groups, exit 0, final source stable. New focused tests 22/22. Frozen/security/native/RAG/tenant/physical/Assistant suites included. |
| P. Frontend | 1030/0/0, exit 0; two added rendering tests. |
| Q. Build/lint | Both exit 0. 16 existing lint warnings, no increase. |
| R. Preservation | PASS. Read-only comparison and source hashes retained. Large global artifacts checked by size/mtime, not full multi-GB content rehash. No existing tenant/global rebuild, production auth/telemetry change, deployment or commit. Owned disposable DB/files/listeners removed; ordinary services stayed in initial off-state. |
| S. Exact files | See changed_files.json for 11 source/test paths with before/after hashes and all supporting report/script paths. Patch SHA256 06ea5947de0f6072b73cce756ecfad90b5585153ad72dc18fbcf2ce1ecd66b2a; reverse check exit 0. |
| T. Product defects | B evidence validator still abstains on sufficient synthetic evidence; plural semantic references partial; informational physical-borrow question can yield an unexecuted confirmation proposal. Intermittent recommendation 503 during read/switch concurrency needs separate diagnosis. External full-text entitlements lack canonical signal, safely UNKNOWN. |
| U. Research limits | 70 review rows preserved, zero human labels; no Precision@K/MRR/nDCG. Synthetic controlled Global candidates are not 5M ranking evaluation. Greedy bounded model repeats are not calibrated safety metrics. Historical live metadata drift remains unattributed; no snapshot rollback. |
| V. Next action | Separately diagnose existing recommendation 503 and actual B intent/evidence interaction while preserving authorization; obtain independent relevance judgments. Do not apply either unsafe validator prompt. No Part 2R started. |

The preliminary full backend run is retained separately because application source changed during it. Only the final frozen run above is used for closure. Initial fixture 422/default-holding failures were corrected in fixtures and their logs retained. API 503 responses, lifecycle 502 responses and model abstentions remain visible in the raw evidence; zero automated regressions does not mean zero live errors.

The initial API A PDF 503 and A For You 503 were followed by sequential 200 checks after fixture writes completed. A later B recommendations 503 during ordinary switch/read concurrency was followed by 200. No authorization relaxation was made, and the latter cause is not fully attributed. Unauthorized/revoked browser 404s are expected denials. Two 502 poll errors correspond to the owned lab reload and ECONNREFUSED in Vite stderr. Network-buffer truncation in five batches prevents an exhaustive console/network claim.

Three initial native Search fixture generations were explicitly built for the owned A/B/I test libraries and removed with the disposable lab. No existing tenant or Global generation was rebuilt.

Protected source SHA256:

- rag/llm.py: d369e26fcbe458964bf642a057ca79212a63f48a6acf2b1c0a12590003f5cc1b
- rag/qa.py: 4a1141649a4ce9b4bce6413627c27557f5817bb8718a4e842a4d12021bd89de3

![Authorized PDF answer in Private B](D:/SDC/LibraryLLM/reports/institution_v2q3_browser_B_digital.png)

Final QA is recorded in institution_v2q3_qa.json. Tests, browser, model, preservation, fixture cleanup and exact file hashes are separate evidence artifacts. This work stops at Part 2Q.3.
