# J JSX exception audit and final candidate

Status: AWAITING_APPROVAL; actual J guard remains unchanged and failing. Final candidate SHA `bfd376271d10b5e285c89ebce96b5470b2b8f95ff4a61c38cd9c0d306687bf2a`.

The O.2 analyzer skipped literal className/title/aria-label/aria-describedby/htmlFor/id attributes without first requiring a native passive element. That wrongly exempted custom React component props. The O.3 analyzer ignores those literals only when tag is in the reviewed native passive allowlist. PageHeading, StatePanel, Modal, TargetCard and any other custom component retain every prop in their complete executable fingerprint.

Native details/summary/label/progress/button are separated from passive layout elements. They retain tag identity and all attributes, including literal presentation attributes. This catches button-to-span, progress-to-div, summary-to-paragraph and click-to-hover changes. Passive section/article layout and container-class edits still pass. All executable expressions, events, bindings, imports, compiler/comment checks remain protected. No whole-page byte identity check is reintroduced.

Full raw fingerprints remain exactly unchanged for libraryIntelligence.ts, institutions.ts and api.ts. Original three backend authority hashes and the native protocol guard remain in the proposed assertion. The actual working page, helpers, CSS, backend and native worker are unchanged.

Candidate checks: 67 passed, including inherited 54 source/security/exact-RAG cases and 13 new JSX cases. Existing complete Staff frontend groups: 78 passed. Original existing behavior assertions also ran in owned page fixtures: original and allowed passive layout passed; native button/progress/interaction mutants caused their intended role/dialog/progress failures. Those expected mutant failures and early harness setup failures are retained separately from real-product results.

The helper/manifest are proposed audited revisions, not approved contracts. Static fingerprints and finite behavior tests do not prove every future accessibility/vendor/runtime condition. Full post-application regression remains pending explicit approval under Step 1.
