# Canonical new-library defaults and safe promotion

PASS. Root cause: registration previously created institution identity/security/owner membership only; missing lending/v2c config defaulted to LEGACY when later screens read it. An empty modern library therefore looked like a historical migration candidate.

Registration now remains PROVISIONING under the existing durable tenant gate while the canonical journal writes lending_config, v2c_config (reservation and fee modes), and immutable version-1 fee policy. The policy retains existing INR 5/day, UTC-day and physical-receipt semantics. Only verified initialization reaches ACTIVE. Failure retains a gate and hidden PROVISIONING state instead of exposing a partial active library.

The operator recovery CLI requires stopped writers, a retained gate and proven initialization journal origins. It replays absolute effects, verifies all canonical documents and owner/security authority, then activates and releases the gate. It does not expire locks online or infer unknown history. Failures without a valid durable plan require explicit operator review rather than guessed recovery.

Existing historical libraries are never changed by a GET or by a zero usable-record count. ADMIN-only preflight checks explicit legacy associations, migration provenance, mapped legacy inventory, loan/reservation/fee history, canonical metadata/holdings/copies/history/policy, conflicting states and incomplete operations/imports. Truly empty unassociated LEGACY installations can be explicitly promoted with a durable idempotent command. GENERAL_USER and platform-only accounts cannot promote. Historical cutover/recovery APIs remain the path for genuine legacy data.

The existing TEST library passed this preflight before seeding. Its normal owner, with scoped ADMIN membership and global GENERAL_USER role, performed the explicit promotion. It is now canonical and populated. Fixtures for historical v2a/v2b/v2c tests remove fresh defaults only in their isolated databases so the original migration scenarios remain meaningful.

Evidence: canonical_empty_library_promotion.json; product_consistency_regression_product_consistency.xml (27 checks); product_consistency_fresh_overview.png; product_consistency_live.json. Recovery: scripts/recover_library_initialization.py.
