# Corrected approval package — NOT APPLIED TO ACTUAL TREE

J patch: `reports/institution_v2o2_j_approval.patch`

SHA256: `b65e11352b78cb72d0a67686ae939635e5eaab9c3f544c36e214cfb20f94e0a0`

RAG patch: `reports/institution_v2o2_rag_approval.patch`

SHA256: `76c09bfef7e676595e0af6974e55aa232e63c684ec51961c558eabf97e45431b`

Both exact patches pass git apply --check --ignore-space-change from D:\SDC. Actual application occurred only under the independently initialized Git root .scratch/institution-v2o2/candidate, verified before application. No actual frozen test, protected source, original manifest or old O.1 proposal was edited. New patch files use LF bytes; no broad production source newline normalization exists.

Changed assertions: J: remove only the frontend page from the original four-file byte loop; preserve three backend hashes; add pins for three test-only boundary files, then execute full transport/executable authority checks; keep the L protocol comment/guard unchanged. RAG: pin unchanged original manifest, resolve its immutable paths within the tested checkout, pin one test helper before import, allow only qa.py's exact two-version projection, retain every other original protected-file assertion and existing api.py exclusion.

Files affected after approval: tests/institution_v2j/test_diagnostics.py; tests/contracts/staff_boundary_v2o2.py, .cjs, .json; tests/test_assistant_backend.py; tests/contracts/rag_grounding_v2o2.py. No product file change. Complete before/after coverage is in j_guard_review.md, j_transport_contract.md, j_ast_security.md and rag_source_review.md.

Before: whole page bytes and three backend files fixed at J; RAG exact original hashes (api.py already excepted). Proposed after: three backend hashes/protocol unchanged; complete reviewed transport chain plus all executable page logic pinned while passive presentation evolves; RAG only original/reviewed exact bytes plus original projection and manifest pin. Positive product/authority/protocol suites and explicit negative mutants are separately recorded.

Candidate bounded backend: 380 passed / 0 failed / 0 skipped. Contract/grounding checks: 67 passed / 0 failed. Actual-tree backend: 2689 passed / 2 failed / 20 skipped. The latter still includes both original contract failures. Unapplied candidate successes are not main-tree successes.

Unresolved approvals: user Part G explicitly says “Any frozen-test patch requires the user's separate approval before application.” Approval must name the exact J and/or RAG patch hashes above. RAG approval must accept the reviewed historical grounding-source exception, not arbitrary current bytes. This request's favorable direction is not that separate approval.

Expected bounded next action only after approval: apply approved patches, rerun exact frozen failures, all affected product/security/mutation suites and accepted full regression. Expected two historical contract failures then resolve; any other failure remains independently investigated, never suppressed. Do not infer universal security or a guaranteed full green result from finite candidate checks. No deployment/cutover/telemetry/global rebuild authorized.
