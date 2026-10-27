# LuminaR native contract v2 — C3 development review

AI_REVIEWED; HUMAN_REVIEWED=0. Reviewer is separate from the parser-hardening agent, but saw preserved C2 native outputs. This is a source-grounded contract audit, not output-blind gold correction. No fresh parser/API/database/evaluator calls, calibration or held-out access occurred.

All 352 unique DEVELOPMENT native IDs are covered by `search_v2c_c3_native_contract_v2.json`. The 233 historical discrepancies and original statuses remain individually visible in `search_v2c_c3_native_status_audit.json`; C2 inputs are immutable.

## Existing authorization and ownership

Public library status changes discovery/join policy; current tenant Search still requires active exact-library membership. GENERAL_USER owns PATRON operations; ADMIN/LIBRARIAN owns STAFF operations. Platform administration supplies no membership override. Guards check current verified identity and current membership before facets, projections, cache/index reads, pending state, retrieval or hydration.

A resource belongs to `(user_id, login_session/JWT sid, GLOBAL-or-LIBRARY scope, exact library_id, workspace)`. Matching only account, UUID or library is insufficient. Search plans, pending choices and profiles never cross this tuple. Tenant Search never falls back to the global candidate universe.

Active membership with the wrong workspace role returns403. No active membership, including removed membership and platform admins without tenant membership, returns generic concealed404. Foreign search UUID or pending choice ownership and a valid-shaped unoffered choice UUID also return404. None of the 233 cases involves invalid authentication.

Invalid/expired decoded authentication or inactive identity returns401; interactions additionally require a login sid. No missing-bearer transport status is prescribed by this audit. Malformed UUID/schema, forbidden plan patches and invalid operands return422. A used/stale/mismatched-version choice or concurrent claim returns409. Existing pending choices that are still stored but expired return410; Mongo TTL may already have removed a choice, yielding404. Ordinary accepted-context expiry starts a fresh plan; no blanket410 is imposed. Busy/recovery503 does not prove authorization loss.

## Mutation and privacy invariants

A denied endpoint operation alone cannot erase accepted or pending state. Fresh current-scope eligibility loss, checked under the existing membership mutation lock, permits deleting only inaccessible exact tuples for the current account/login/library and their profile entries. Preserve other libraries, GLOBAL, other login sids and still-authorized workspaces. A STAFF role denial must preserve an authorized PATRON context.

Choice resolution validates the server-issued choice before claiming it, binds original query/mode/session/parser/base-version/expiry, and commits through accepted-context CAS with a receipt. An invalid choice must preserve every document and the genuine choice. The genuine original owner may subsequently commit exactly once; replay409 must preserve that commit. A successful explicit context clear deletes that exact accepted UUID and its pending records, leaving profiles unchanged.

The privacy oracle requires generic errors with no private catalogue/vocabulary, result, accepted plan, candidate choices or personalization disclosures. C2 observation JSONL did not serialize bodies: details in the audit are source-inferred, not fabricated observed responses. C2 asserts exact generic bodies only on private suggestions/corrections/resolve. A fresh evaluator must capture bodies and phase snapshots to strengthen privacy evidence.

## Exact request status contracts

| Action/family | Cases | Canonical primary status |
|---|---:|---:|
| clear_current_authorized_search_context | 4 | 200 |
| d24_refinement_turns | 10 | 200 |
| d25_instead_turns | 10 | 200 |
| request_private_clarification_choices | 12 | 404 |
| request_private_corrections | 12 | 404 |
| request_private_session_metadata | 11 | 404 |
| request_private_suggestions | 12 | 404 |
| resolve_sid_1_clarification_under_sid_2 | 47 | 404 |
| revoke_current_membership_then_search | 48 | 404 |
| search_denied_other_library_then_revoke_other_membership | 47 | 403 |
| search_tenant_as_platform_admin_without_membership | 47 | 404 |
| search_unauthorized_workspace | 48 | 403 |
| submit_forged_choice_then_submit_genuine_choice | 44 | 404 |

The 47 cross-library sequences additionally require404 after B membership removal. The 91 invalid-choice/cross-login sequences additionally require genuine200 then replay409. Twenty legacy delta rows return typed plans with status200 even when their decision blocks execution; status must not substitute for semantic delta or accepted-plan checks.

Classification: 189 C VALID EQUIVALENT DENIAL STATUS, 44 B STALE TEST EXPECTATION. The forged-choice list omitted the existing unavailable-choice404 convention and included statuses with other meanings. No evidence supports changing authorization/product behavior for these233 status disagreements. Source-grounded v2 expectations happen to agree with all352 preserved C2 primary statuses; this is a retrospective evidence check, not a fresh C3 result.

## Four legacy delta rows

The separate delta audit selects exactly the four nonempty authored-field mismatch dictionaries, not all rating changes. Original delta labels remain untouched. Three prefix `instead X` queries should replace the topic with canonical X while retaining synthetic rating>=2; suffix-only recognition instead reset the accepted plan. Bare `above 4` has no field/unit and the original row has no prior state. The reviewed supplemental sequence requires safe clarification and no accepted mutation, rather than turning an injected prior control into independent blind gold.

`search_v2c_c3_delta_plan_contract_v2.json` freezes these four output-visible normative supplemental contracts. The original raw delta comparison must remain separate. Full prior plans in the audit come from C2 final `previous_plan` or unchanged seed; the C2 before snapshot predates synthetic seeding. No end-to-end candidate counts are inferred.

## Executable artifact and preservation

Machine-readable case records include historical expectation, exact v2 expected status, symbolic request and role, transport distinction, phase/state/privacy oracles and review provenance. Each JSON artifact records SHA256 for its immutable inputs and the contract source used. Native records preserve all IDs; no broad 4xx adapter, silent status normalization or weakened state oracle is introduced.
