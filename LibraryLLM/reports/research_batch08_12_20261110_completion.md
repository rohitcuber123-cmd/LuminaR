# LuminaR Parts 08–12 consolidated engineering completion

## A. Final result

**PARTIAL.** Two reproduced ingestion/cache defects were repaired with five new positive/negative regression tests. The final executed regression results appear below. The four existing protected Search/KG defects reproduced on both targets and remain **APPROVAL_REQUIRED**. Current real-Qwen Private B and Assistant behavior remain unverified. No protected validator or generation source was edited.

## B. Current source baseline

Run namespace: `research_batch08_12_20261110`. Branch `codex/search-v11-finalization`, HEAD `606f0dfce3970bea8e6fc2b62d243433d1a66b8a`. Parts 04–07 completed before this task, and no research/pytest runner was active at preflight. Their uncommitted changes were retained. All 1,719 preflight source/configuration hashes matched their completed baseline; the immediately preceding actual-tree run had 3,191 backend passes, zero failures, 20 skips and 1,032 frontend passes. This comparison uses raw working-tree bytes and executed evidence, rather than HEAD alone.

The preflight contains dirty status, source/protection hashes, non-secret configured model/feature settings, environment-file hashes, resident observation references and fingerprints for 45 historical research files. Secrets and tokens were not copied into reports. The final preservation check permits exactly two application and two test-file changes.

## C. Historical evidence reconciliation

The available October 31 Parts 08–12 evidence comprises 45 files and 66 feature-ledger entries, including the complete Part 10 snapshot `20261031T065332Z_606f0df_10`. Technical evidence and open questions were reconciled with current routes, fixtures and the newly executed tests. Historical test counts and statements about missing announcements were not treated as current results.

[Reconciliation ledger](D:/SDC/LibraryLLM/reports/research_batch08_12_20261110_reconciliation.json) preserves historical rows and current qualifications. `MISSING_VALIDATION` in that ledger denotes an evidence gap, not an implementation defect. The historical `qa.py` raw-byte mismatch is absent from the current accepted reviewed bytes; no hash exception was added. Announcement and targeted inbox functionality already exists in Parts 2P/2P.1. Incremental KG, external author identity resolution, calibrated reading level, external delivery and learning-outcome evaluation remain separate design or research questions.

## D. Unified issue register

| ID | Classification | Current outcome |
|---|---|---|
| 08-DOCX | CONFIRMED_CURRENT_DEFECT | FIXED: deleted/moved-from and field-instruction text excluded; run separators retained |
| 08-RESTORE | CONFIRMED_CURRENT_DEFECT | FIXED: missing extraction coverage is disclosed on restored personal documents |
| 08-HASH | ALREADY_FIXED | Exact approved RAG bytes preserved |
| 08-PRIVATE-B | MISSING_VALIDATION | UNRESOLVED; current real validator wire/decision not obtained |
| 09-QUALITY | RESEARCH_ONLY | Structural/source tests passed; independent factuality and learning effectiveness unmeasured |
| 10-HOMONYM | EXPECTED_DESIGN_BOUND | Equal names collapse into one metadata feature; reproduced |
| 10-SYNONYM | EXPECTED_DESIGN_BOUND | Distinct labels/author aliases need external identity or ontology policy; reproduced |
| E-01–E-04 | PROTECTED_APPROVAL_REQUIRED | All four reproduced on Search and KG; no source repair applied |
| 10-INCREMENTAL | EXPECTED_DESIGN_BOUND | Whole-generation build retained; NOT_IMPLEMENTED |
| 11-QWEN | MISSING_VALIDATION | Patched Assistant real-Qwen run NOT_RUN |
| 11-LEVEL | UNSUPPORTED_POLICY | No invented reading-level guarantee |
| 12-ANNOUNCE | ALREADY_FIXED | Existing API delivery and recipient isolation verified in fixtures |
| 12-SMTP | UNSUPPORTED_POLICY | No external channel added or activated |
| PROD-MONGO | RESEARCH_ONLY | NOT_QUALIFIED; deployment unchanged |

## E. Part 08 ingestion

`library_asset_text.extract_text` was the common DOCX upload/preview/processing path. It joined `itertext()` for each paragraph. A generated DOCX containing a deleted capacity of 900, moved text stating 800, a field instruction and current capacity 25 supplied all four strings as source evidence. Separately, tabs and line breaks vanished, concatenating source values. The new iterative traversal retains Word run text, tabs, breaks and paragraph boundaries, and skips deleted/moved-from revisions and instruction text. Existing size, ZIP expansion, XML declaration and UTF-8 rejection remain unchanged. This is bounded text extraction, not a complete Word layout renderer.

The personal prepared-document bundle does not retain the original failed/blank-page ledger. A two-page PDF with one unreadable page originally produced a warning; export/restore dropped it. Restore now warns when source pages have no retained chunks. In that uncertain case it does not synthesize an OCR success/failure ledger. Complete known OCR-page restores retain their prior metadata. The encrypted bundle format and integrity validation are unchanged. Blank unrepresented pages can also trigger the conservative coverage warning.

Controls covered valid PDF/TXT/DOCX, encrypted and corrupt PDF, empty/binary/oversized text, malformed DOCX, missing OCR, bounded OCR attempts, a 64-page native PDF and rejection above 64 MiB. A real local Tesseract run recovered the known text from one generated raster page. This is not multilingual, arbitrary-malformation or OCR accuracy qualification. Existing approved suite cases cover source checksum mismatch, reprocessing, job failure and interrupted asset recovery.

## F. Part 08 RAG security and grounding

The 88-check real-JWT integration run used fresh fixture signing keys, normal signature/session/account/membership dependencies and zero authentication overrides. It verified authorized document access and denied foreign tenant/user, forged chunk, retired-generation source and old artifact references. Membership suspension during deterministic generation withheld the response and cleared runtime state. Personal owner/session/deletion rules were exercised by the approved private-document/cache and Knowledge Tools suites.

The new integration engine is the existing approved deterministic Engine fixture, not Qwen. Its success verifies authorization and generation identity, not actual answer quality or validator entailment. Protected grounding regressions run in the complete suite. Current real-model false-positive/negative support rates and paired Private B cause remain unmeasured. No unsupported answer was made acceptable by changing a prompt.

## G. Part 09 Knowledge Tools

The production artifact/source routes generated and reopened flashcards, summary, mind map and quiz from an authorized synthetic institution PDF. The source endpoint retained generation-bound IDs. Reprocessing denied old source and artifact references. Foreign account and revoked-member access were denied. Document mind maps remain distinct from both catalogue graph systems.

The controlled corpus uses 12 newly named synthetic facts separate from the repository educational fixture. It exercised all seven nonempty quiz-format combinations, empty selection rejection, insufficient evidence, source bindings, duplicate options, answer keys and grading controls. Controlled generation without an encoder is explicitly labelled as such; production semantic preparation and educational quality are not inferred from it.

## H. Part 09 quiz and cloze correctness

Every retained candidate in the controlled candidate pool passed the existing authoritative MCQ verifier. A corrupted answer key was rejected. Format results preserve selected types, source chunk IDs, exactly one keyed option and matching bijections. Insufficient MCQ evidence produced no manufactured questions. Numeric/unit equivalence, incorrect magnitude, incorrect units, negation and sender/receiver reversal controls passed without using a semantic encoder. Full suites additionally exercise semantic distractor checks, source mutation and grading authorization.

This does not establish perfect natural-language entailment, expert distractor quality, general paraphrase accuracy or measured student benefit. Existing conservative rejection and reduced output counts were retained. No grading threshold, answer-key policy or quiz format was changed.

## I. Part 10 global graph

Read-only summary metadata was available at `knowledge_graph/data/catalogue.sqlite`. It reports version `kg1-2-metadata-cosine-v1`, 5,000,000 books, 29,406,707 edges, 2,454,492 author features and 975,785 subject features. The stored catalogue fingerprint is `50559012605f6fe3aba1fbc36f3f943c24563bb0a88fc60ac6a14df90fb3e904`, created at `2026-10-02T17:00:36.932421+00:00`. These are verified stored summary values, not fresh full-table counts, a new catalogue checksum, or proof of the graph loaded by a resident process. The file was opened read-only, with no catalogue scan or rebuild.

The configured base snapshot summary lists Author and Subject relations and no topic features. Optional topic enrichment remains a separate builder/output. It was not activated. The source uses bounded adjacent description phrases, description hashes and degree/TF-IDF filters; this is neither an ontology nor private-document extraction. Global graph read paths remain SQLite, not Neo4j, graph embeddings or causal reasoning.

## J. Part 10 tenant graph

Real-JWT fixtures built fresh A/B graphs only in the disposable task store. The same normalized author/subject feature ID appeared in both, while each result retained only its own canonical book IDs. A/B members and an A/B shared member succeeded in their own scopes; foreign and outsider reads failed. A metadata edit made A STALE and the reader returned an empty graph, preserving existing policy.

The separate clean native run used the exact cached MiniLM revision recorded in its evidence, real FAISS and the native model-free KG worker. Both generated targets validated and served their own one-book fixture. This does not qualify large-scale publication reliability; E-01–E-04 remain unresolved.

## K. Part 10 relationship correctness

The global weighted cosine and summed reason-path contributions matched in controlled queries. Author 2.0 and Subject 1.0 weighting remained unchanged. Typed feature collisions did not create an author-to-subject relation. Exclusions, self-exclusion, inactive records and missing features were checked. Bounded size controls compared shared-feature candidate counts against direct typed metadata overlap. Tenant graph edges remain AUTHORED_BY, HAS_SUBJECT and HAS_CLASSIFICATION; they are not evidence of causal or confidence-labelled relationships.

## L. Part 10 author and feature ambiguity

Two synthetic, intentionally different identities named Alex Kim connected through one author-name feature. A. Kim remained separate, and DNS versus Domain Name System did not become synonyms. Unicode/case/whitespace variants deduplicated. These are measured consequences of string-feature policy, not defects repaired by guessing person identities. The fixture output records exact paths and scores. No identity linking, ontology or new graph model was introduced.

## M. Part 10 generation and freshness

READY and source-change STALE behavior were exercised through actual authenticated graph routes. Missing/unready/retired document generation references were also denied. Retaining previous files does not authorize stale graph serving. The dataset limits remain 50,000 records and 64 MiB; source and reader protections were unchanged. Native builds, publication and Mongo pointer updates remain separate filesystem/database operations, not one ACID transaction.

## N. Part 10 isolation

Tenant graph, document artifacts and source references used UUID namespaces and current membership. Equal feature hashes across A/B did not merge graphs. New tests used only synthetic data and task-owned records. The complete endpoint-by-role-by-race matrix and every possible foreign feature/generation permutation remain incomplete. Existing guard and integration suites add evidence but are not a proof of all concurrent executions.

## O. Part 10 product integration

Current source call paths remain separate: global More Like This and Assistant graph tool call CatalogueGraph; global seeded recommendations call the recommender/Search path; tenant For You intersects global work IDs and fills from usable local catalogue; tenant semantic Search loads SEARCH_INDEX; Library Graph loads KNOWLEDGE_GRAPH; Knowledge Tools mind maps use one document. No ordinary Search or For You path was relabelled as KG-ranked. Existing graph UI tests ran in the full frontend suite; live browser navigation was NOT_RUN.

## P. Part 11 recommendations

Global eight-component weights and feedback adjustment are unchanged. Tenant recommendations retain `GLOBAL_INTERSECTION_AND_LOCAL_DISCOVERY`, canonical hydration and local-only acquisition fill. Existing full regression groups cover provider failure, cache authorization, local ownership, concurrent recommendation reads, live eligibility and availability separation. No new relevance score, global filler, reading-level estimator or cache invalidation policy was added.

## Q. Part 11 similarity and context

Part 2Q current tests cover topic routing, singular selection, current-page references, comparison pairs, confirmation safety and local-only identity. They verify controlled parser/tool behavior and source preservation. They do not establish the real patched Qwen runtime now routes every database, SQL, networks, operating-systems, Python, Java or ML prompt correctly. There was no qualified current resident model run.

## R. Part 12 events

Authenticated fixtures exercised draft visibility, publish and repeat publish, member reading, foreign denial, patron mutation denial, cancel, archive, archived-edit rejection, invalid date range and +05:30-to-UTC normalization. Approved regression suites cover related work validation, lifecycle transitions and concurrent server-side revisions. Event edits compare the revision read by the server; this is not an invented client-supplied revision contract. No event scheduler or automatic inbox fanout was added.

## S. Part 12 announcements

Existing Parts 2P/2P.1 remain the implementation. The new fixture published both all-active-member and targeted announcements, repeated publication and delivery, and checked recipient visibility. Approved suites cover audience snapshot, later members, withdrawn publications, stale revisions and producer authority changes. Announcement management remains ADMIN-only; librarian event permissions do not grant announcement administration.

## T. Part 12 targeted notifications

The intended recipient received one inbox item after repeated materialization. Another member and a foreign-library notification URL were denied. Repeated read marking was idempotent. Suspension removed recipient access to the targeted notice and announcement. Existing recipient search and delivery tests cover tenant lookup boundaries. No SMTP, push or external service was activated.

## U. Inbox/outbox reliability

Stable dedupe keys and retry/materialization guards remain intact. The approved suites cover committed producer receipts, suppression, retries, pending delivery and account-owned inbox operations. The new fixture directly checks duplicate stored targeted entries after repeated delivery. This is not exactly-once external delivery, an arbitrary Mongo/OS-crash guarantee or a tenant circulation reminder redesign. Parts 04–07 business policy remained out of scope.

## V. Private B validator status

**UNRESOLVED.** No current real-Qwen wire input/structured validator decision was captured for original/code-swap/label-swap paired A/B cases. The older ALPHA-SEVEN versus BRAVO-NINE observations remain historical. No causal conclusion or post-repair claim is made, and neither rejected protected prompt candidate was applied.

## W. Live patched-Qwen status

**NOT_RUN.** No resident RAG/Qwen listener was available during observation. Measured available physical memory was about 2.1 million KiB before further testing; no safe model headroom was established. No Qwen process or shared-service restart was attempted. The native embedding and OCR exercises are separately labelled and do not count as Qwen verification. Live UI and actual conversational quality remain unavailable evidence.

## X. E-01 through E-04

Eight new controlled reproductions used the existing approved failpoint harness adapted only to the new task-owned Mongo/filesystem roots and run names. Worker termination checked a task/run/PID marker. No resident lock, pointer or generation was changed. All eight reproduce a failed invariant; those failures are retained separately from passing regression totals.

| Issue | Exact boundary and durable result | Root cause and affected function | Proposal and required safety checks |
|---|---|---|---|
| E-03, priority | Alter owned manifest library_id at SERIALIZATION_ACK after validation; Search and KG both become SUCCEEDED with the new active pointer, while reader status is RECOVERY_REQUIRED | `TenantIntelligence.run_one` validates the pending generation, then renames and accepts a fresh manifest digest before pointer CAS | Bind the pointer to the already validated digest; validate final identity/file set before CAS. Test library/generation/source/file corruption at rename, successful unchanged output, expired fences, changed authority/source and concurrent predecessor/successor. Preserve previous serving pointer on failure. |
| E-01 | Terminate after SUCCEEDED update before tagged lock release; success is durable and lock remains; explicit recovery after controlled expiry returns 409 on both targets | `run_one` has a success-to-release gap; `library_intelligence_service.recover` terminal/inactive tagged-job handling cannot reconcile it | Admit only exact tagged ownership plus validated terminal pointer/audit outcome; idempotent cleanup. Test active lease denial, unrelated token/holder denial, terminal published and unpublished cases, repeated/concurrent cleanup. |
| E-02 | Terminate after recovery changes target fence but before job fence; job remains PUBLISHING, mismatched fences and lock remain; retry returns 409 on both targets | `recover` performs two fence writes without a persisted resumable recovery intent | Persist exact old/next fence intent under tagged-lock CAS, replay both writes, verify completion before release. Test every interruption, concurrent recovery and former-worker late resume. |
| E-04 | Terminate inside generic barrier after insertion but before intelligence tag; QUEUED job and untagged lock remain; explicit recovery returns 503 on both targets | `library_intelligence_store.intelligence_barrier` tags after `institution_repository.library_mutation` inserts the durable lock | Include exact intelligence job ownership at insertion through a narrowly scoped reviewed API. Test before/after insertion, queued work and unrelated generic tenant mutations. Existing unknown/untagged locks must still block unsafe takeover. |

These are proposals, not applied patches. Required changes touch frozen worker/service/store and native-protocol contracts. Separate explicit approval is required for the exact reviewed patch and any narrowly necessary guard update. There is no blanket lock deletion, fence bypass or manifest rebaseline. Recovery must preserve exact authority and last-good evidence, quarantine uncertain candidates and leave unknown ownership blocked. E-03 demonstrates invalid-pointer publication followed by read-side refusal; it does not demonstrate cross-tenant content serving.

## Y. Cross-module scenarios

| Requested scenario | Evidence and limit |
|---|---|
| A: institution PDF → answer → study artifacts → sources | Executed in 88-check fixture with deterministic Engine; real-Qwen grounded answer remains unverified |
| B: personal PDF → artifacts → different session denial | Executed approved personal/cache/artifact regressions; no live browser session |
| C: tenant book → graph → recommendation → availability | Scoped pieces executed in native/JWT/full suites; no single live UI trace |
| D: global KG → reasons → eligibility → detail | Native synthetic SQLite plus graph route regressions; resident catalogue records not probed |
| E: source edit → stale graph → current canonical source | Executed authenticated A fixture; graph empty while stale |
| F: A/B stale result references | Cross-tenant graph/asset/source denials executed; browser switching races NOT_RUN |
| G: announcement → snapshot → inbox → read → revocation | Executed and approved 2P/2P.1 suites |
| H: real Qwen recommendation → follow-up → no loan | Real Qwen NOT_RUN; controlled Assistant regression only |
| I: false-premise question → actual validator rejection | Protected deterministic grounding regressions; current real-Qwen paired evaluation NOT_RUN |
| J: optional provider failure → scoped local fallback | Full recommendation/Search/Assistant fixture regressions; no live provider fault injection |

## Z. Confirmed defects

The new repaired defects are DOCX source text corruption and restored-document warning loss. E-01–E-04 are existing, newly reproduced protected defects. Homonyms, synonyms, lack of incremental KG and missing experimental benchmarks were not reclassified as bugs to justify speculative architecture changes.

## AA. Actual source repairs

| Exact changed file | Before SHA-256 | After SHA-256 |
|---|---|---|
| [backend/services/library_asset_text.py](D:/SDC/LibraryLLM/backend/services/library_asset_text.py) | 52ad051a4f60175cf98c1aeaa0b69360e359dbd08ae52ac40f407306c5c035c8 | bd2a7d47374d70c3d2658fe1b19b81430e272d61e3a87610adb9690bc1b40b04 |
| [rag/services/private_documents.py](D:/SDC/LibraryLLM/rag/services/private_documents.py) | f325d19018907000656e0403c9a33ed4b85ff9950af72b53d85a9c8ae0fb31f6 | 45b5edcda8eecab9b15a1cdb074f31d64d396991d0cc9aa6e2eb453076410ee5 |
| [tests/institution_v2f/test_text_assets.py](D:/SDC/LibraryLLM/tests/institution_v2f/test_text_assets.py) | 8b2ab0008c1dbd9f08a31a17eb64e381dc138e61256efdb8823ded93f7f458c0 | e40163c4d7460a9b01a2ab8fa37fe6ded94aea55009819d850821b15d527bc10 |
| [tests/test_private_document_cache.py](D:/SDC/LibraryLLM/tests/test_private_document_cache.py) | 6170cc1b2954700ca538b53d03920eca98c94eb68e020a623414a93b0b0541f6 | f6660a407396f13a2b7b9bee0deb392dd8aca7974c601c068c380b785df26427 |

Only the two application files and two test files above changed from preflight. Added scripts, logs, JUnit files and reports are listed with hashes in the task manifest. Previously legitimate dirty changes were retained. Existing DOCX generations were not automatically rebuilt; staff must explicitly reprocess an existing document to adopt the new extractor. Reverting these four task diffs is the source rollback scope; historical data was not rewritten.

## AB. Before/after measurements

| Reproduction | Before | After |
|---|---|---|
| DOCX run boundaries, excluded revision/instruction text, deleted-only input and field-result preservation | Four new assertions failed against preflight application source | Four pass; nine selected DOCX/input checks pass |
| Partial personal PDF restore | New assertion fails because warnings field is absent | Warning exposed, no invented OCR ledger; both selected restore controls pass |
| Adjacent module regression | Historical current-tree baseline retained | 251 asset/private-cache/global-graph tests pass |
| E-01–E-04 | Prior Prompt E raw failures | Eight current failures reproduced, no repair applied |

These are test observations, not controlled speedup claims. JUnit files preserve durations and original errors. Application source before/after SHA-256 values are in the source table and preservation JSON. Exact raw evidence and corpus hashes are retained.

## AC. Security regressions

New source changes add no authentication exception. The approved authentication/session dependencies, tenant membership checks, source/generation IDs, encrypted cache owner scope and original protection manifests remain unchanged. Real-JWT integration used generated synthetic accounts in isolated Mongo. Existing regression harnesses also contain identity-injected tests; those are not represented as real-JWT or native-model observations.

The first two direct DOCX pytest probes used the existing approved institution_v2f fixture's randomly named dedicated database on localhost:27017, with fixture cleanup; they were not separate mongod-process runs. The accepted adjacent suite, complete backend run and new integration/recovery experiments used separate task-owned Mongo processes on ephemeral loopback ports. No real institutional record was used in authorization tests. Earlier integration attempts (invalid classification input and an incorrect expected unready-member status) remain in logs; current code correctly rejects them. A preservation-script import-path setup error was corrected without application changes.

## AD. Research experiment results

42 controlled cases passed; 88 real-JWT HTTP checks passed; eight size/OCR cases passed. The clean real MiniLM/native Search/KG scenario passed. Eight protected fault invariants failed and remain open.

| Books | Global build ms | Global bytes | Tenant writer ms | Tenant graph bytes | Tenant components |
|---|---|---|---|---|---|
| 0 | 11.418 | 53248 | 1.597 | 23 | 0 |
| 1 | 7.981 | 53248 | 1.739 | 496 | 1 |
| 16 | 9.213 | 53248 | 2.722 | 15205 | 7 |
| 128 | 12.684 | 106496 | 5.949 | 90298 | 1 |
| 512 | 29.043 | 270336 | 21.706 | 343129 | 1 |

Real local OCR recovered the synthetic LIMA-TWENTY text in 1379.492 ms on one page. Full timings, native phases, input/output data and cache qualifications are in the linked raw records.

Evidence labels are SOURCE_VERIFIED, CONTROLLED_TEST and NATIVE_EXECUTED as appropriate. Real MiniLM version and phase times appear in native evidence; OCR engine, DPI, raster budget and latency are in size/OCR evidence. No new Qwen run, independent relevance labels, NDCG, learning outcomes, deployment latency or peak-memory benchmark is claimed. Disk/model caches were not flushed, and concurrent regression processes mean cost observations are not isolated performance benchmarks.

## AE. Backend tests

3,197 passed / 0 failed / 20 skipped. Change from the completed current-tree baseline: {"passed": 6, "failed": 0, "skipped": 0}.

| Group | Passed | Failed | Skipped |
|---|---|---|---|
| unit | 37 | 0 | 0 |
| assistant | 452 | 0 | 0 |
| security | 117 | 0 | 10 |
| staff | 76 | 0 | 0 |
| notifications | 51 | 0 | 0 |
| circulation | 13 | 0 | 0 |
| search | 172 | 0 | 0 |
| private_knowledge_ocr | 279 | 0 | 0 |
| kg | 30 | 0 | 0 |
| institution_v1 | 60 | 0 | 0 |
| institution_v2a | 95 | 0 | 0 |
| institution_v2b | 57 | 0 | 0 |
| institution_v2c | 59 | 0 | 0 |
| institution_v2d | 45 | 0 | 0 |
| institution_v2e | 108 | 0 | 0 |
| institution_v2f | 187 | 0 | 0 |
| institution_v2h | 30 | 0 | 0 |
| institution_v2g | 152 | 0 | 0 |
| workspace_authorization | 13 | 0 | 0 |
| dashboard_authority | 86 | 0 | 0 |
| catalogue_experience | 88 | 0 | 0 |
| product_consistency | 27 | 0 | 0 |
| current_product_extensions | 0 | 0 | 10 |
| institution_v2i | 60 | 0 | 0 |
| institution_v2j | 54 | 0 | 0 |
| institution_v2k | 56 | 0 | 0 |
| institution_v2l | 67 | 0 | 0 |
| institution_v2m | 50 | 0 | 0 |
| institution_v2n | 35 | 0 | 0 |
| institution_v2o | 32 | 0 | 0 |
| institution_v2o1 | 19 | 0 | 0 |
| institution_v2o2 | 67 | 0 | 0 |
| institution_v2o3 | 67 | 0 | 0 |
| institution_v2o3_closure | 75 | 0 | 0 |
| institution_v2p | 84 | 0 | 0 |
| institution_v2p1 | 80 | 0 | 0 |
| institution_v2q_ai | 141 | 0 | 0 |
| events | 76 | 0 | 0 |

The accepted full product inventory retained all 38 groups and the original test bodies, adding five tests. Recovery fault invariants are listed separately: **eight failures, unchanged protected code**. The suite did not suppress them; they are explicit diagnostic reproductions outside its existing regression inventory.

Totals follow the accepted grouped runner's test executions, which include overlapping files. The increase of six passes comprises four new DOCX tests plus the one new restore test executed in both the security and private_knowledge_ocr groups. There are five distinct new regression tests.

## AF. Frontend tests

1,032 passed / 0 failed / 0 skipped. All executed checks exited zero.

The frontend source and transport fingerprints are unchanged. Existing tests include Knowledge Tools, graphs, Assistant context, Search/KG progress, event editor, announcements and inbox state. No real-browser test was run in this task.

## AG. Build and lint

Production build PASS. Lint PASS with 16 existing warnings. Logs preserve warnings and errors. A default whitespace check flagged native CRLF added lines; the original CRLF bytes were retained and the CRLF-aware check passed.

## AH. Protected contracts

75 passed / 0 failed / 0 skipped.

The original manifests and guards were not regenerated. Protected `rag/qa.py`, `rag/llm.py` and worker/service/store/artifact bytes match preflight. Passing frozen contracts do not mean the four protected runtime defects are fixed.

## AI. Preservation and cleanup

All 1,719 preflight hashes were checked: exactly four expected files changed, and the other 1,715 remained identical. Protected hashes, frontend source, HEAD and all recorded resident state/index/artifact observations matched. All 16 separate Mongo fixture processes stopped and removed their owned temporary roots, including the two unsuccessful integration setup runs.

The resident comparison is read-only and includes pointer/job/generation census, logical catalogue/communications digests, indexes, Search pointer files and global/tenant artifact metadata. Large global artifacts use size/mtime and existing pointer hashes; they were not rehashed in full. The read-only local KG summary is separate from proof of deployed loaded-source identity. No production Mongo authentication or telemetry activation, existing tenant/global index rebuild, deployment, commit, reset or unrelated rollback occurred.

## AJ. Approval-required changes

E-03 should receive first protected review, followed by the combined E-01/E-02 recovery protocol and the E-04 insertion-time ownership tag. Review exact source/protection changes and positive/negative failure tests before applying. This task neither seeks nor assumes that approval. Protected RAG changes would likewise require separate reviewed evidence; the Private B cause has not been established.

## AK. Remaining engineering limitations

Protected publication/recovery failures remain. Current real-Qwen paired validation and patched Assistant verification are unavailable. The complete authorization/async race matrix and live UI navigation remain incomplete. Restored old bundles cannot recover a lost original failure/blank-page ledger; the fix reports uncertainty. Existing prepared DOCX artifacts require explicit reprocessing to adopt extraction changes. Full Word rendering, arbitrary parser faults, full-scale native graph costs and deployed network security remain unqualified.

## AL. Remaining research limitations

Graph relevance is UNJUDGED. Synthetic known string collisions are not a population identity error rate. Small bounded graph costs, one OCR raster and one native embedding build are not production performance, OCR accuracy or educational benchmarks. There are no independent relevance/learning labels, blind factuality ratings, multilingual corpus, time-split recommendation study or reader-benefit result. Production Mongo remains NOT_QUALIFIED.

## AM. Next recommended work

Review the E-03 protected patch proposal against the exact current failure record. Then qualify the replayable recovery design before any protected edit. Arrange a single owned Qwen runtime with sufficient measured headroom for paired validator inputs and patched conversational cases. Plan independent, licensed relevance/OCR/quiz evaluation separately from engineering regression. This task stops after Parts 08–12; Part 13 was not started.

## Evidence index

- [Preflight](D:/SDC/LibraryLLM/reports/research_batch08_12_20261110_preflight.json)
- [Controlled inputs and outputs](D:/SDC/LibraryLLM/reports/research_batch08_12_20261110_controlled.json)
- [Graph sizes and OCR](D:/SDC/LibraryLLM/reports/research_batch08_12_20261110_sizes_ocr.json)
- [Global KG read-only metadata](D:/SDC/LibraryLLM/reports/research_batch08_12_20261110_global_kg_metadata.json)
- [Real-JWT integration summary](D:/SDC/LibraryLLM/reports/research_batch08_12_20261110_integration_03_integration_summary.json)
- [Native Search/KG](D:/SDC/LibraryLLM/reports/research_batch08_12_20261110_native_scenarios.jsonl)
- [Recovery reproduction index](D:/SDC/LibraryLLM/reports/research_batch08_12_20261110_recovery_summary.json)
- [Complete backend groups](D:/SDC/LibraryLLM/reports/institution_v2q_research_batch08_12_20261110_backend.json)
- [Frontend/build/lint](D:/SDC/LibraryLLM/reports/institution_v2q_research_batch08_12_20261110_front_frontend.json)
- [Preservation](D:/SDC/LibraryLLM/reports/research_batch08_12_20261110_preservation.json)
- [Exact changed/evidence files and hashes](D:/SDC/LibraryLLM/reports/research_batch08_12_20261110_changed_files.json)

## Final QA

~~~json
{
  "BATCH08_12": "PARTIAL",
  "DOCUMENT_INGESTION": "PARTIAL",
  "RAG_GROUNDING": "PARTIAL",
  "RAG_SOURCE_AUTH": "PASS",
  "PRIVATE_B_VALIDATOR": "UNRESOLVED",
  "KNOWLEDGE_TOOLS": "PARTIAL",
  "MCQ_CORRECTNESS": "PARTIAL",
  "MATCHING": "PARTIAL",
  "CLOZE_GRADING": "PARTIAL",
  "GLOBAL_KG": "PARTIAL",
  "GLOBAL_KG_EXPLANATIONS": "PASS",
  "GLOBAL_KG_METADATA": "VERIFIED",
  "TENANT_KG": "PARTIAL",
  "TENANT_KG_ISOLATION": "PASS",
  "TENANT_KG_FRESHNESS": "PASS",
  "TENANT_KG_NATIVE_BUILD": "PASS",
  "KG_RELEVANCE": "UNJUDGED",
  "KG_INCREMENTAL_UPDATES": "NOT_IMPLEMENTED",
  "RECOMMENDATIONS": "PARTIAL",
  "TENANT_RECOMMENDATIONS": "PASS",
  "BOOK_SIMILARITY": "PARTIAL",
  "LIVE_PATCHED_QWEN": "NOT_RUN",
  "ANNOUNCEMENTS": "PASS",
  "TARGETED_NOTIFICATIONS": "PASS",
  "OUTBOX_DEDUPLICATION": "PASS",
  "INBOX_UI": "PARTIAL",
  "E01_RETAINED_LOCK": "APPROVAL_REQUIRED",
  "E02_RECOVERY_FENCING": "APPROVAL_REQUIRED",
  "E03_CORRUPT_POINTER": "APPROVAL_REQUIRED",
  "E04_PRETAG_LOCK": "APPROVAL_REQUIRED",
  "CROSS_TENANT_SECURITY": "PARTIAL",
  "PRIVATE_E2E": "PARTIAL",
  "REAL_MODEL_TESTS": 1,
  "REAL_QWEN_TESTS": 0,
  "REAL_OCR_PAGES": 1,
  "BROWSER_TESTS": "NOT_RUN",
  "BACKEND": {
    "passed": 3197,
    "failed": 0,
    "skipped": 20
  },
  "FRONTEND": {
    "passed": 1032,
    "failed": 0,
    "skipped": 0
  },
  "PROTECTED_CONTRACTS": {
    "passed": 75,
    "failed": 0,
    "skipped": 0
  },
  "BUILD": "PASS",
  "LINT": "PASS",
  "LINT_WARNINGS": 16,
  "NEW_REGRESSIONS": 0,
  "GLOBAL_HNSW_REBUILT": "NO",
  "GLOBAL_KG_REBUILT": "NO",
  "EXISTING_TENANT_INDEX_REBUILT": "NO",
  "PROTECTED_RAG_CHANGED": "NO",
  "PROTECTED_GENERATION_SOURCE_CHANGED": "NO",
  "PRODUCTION_MONGO_AUTH_CHANGED": "NO",
  "PRODUCTION_MONGO_QUALIFIED": "NO",
  "PRODUCTION_TELEMETRY_ENABLED": "NO",
  "DEPLOYED": "NO",
  "COMMITTED": "NO",
  "source_repairs": 2,
  "new_regression_tests": 5,
  "real_jwt_http_checks": 88,
  "controlled_cases": 42,
  "bounded_size_ocr_cases": 8,
  "diagnostic_recovery_failures": 8,
  "owned_mongo_cleanup_receipts": 16,
  "regression_delta": {
    "passed": 6,
    "failed": 0,
    "skipped": 0
  },
  "qualifications": {
    "PASS": "Only the executed fixture scope; not universal race or production qualification.",
    "REAL_MODEL_TESTS": "One real CPU MiniLM native Search/KG scenario; zero Qwen runs. One real OCR page separately counted.",
    "GLOBAL_KG_METADATA": "Stored read-only local default summary, not fresh scanned counts or loaded resident process identity.",
    "BACKEND": "Accepted grouped test executions include overlaps; five distinct new tests add six passes because the restore test runs in two groups."
  }
}
~~~
