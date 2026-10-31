# Conditional integration / rollback proposal — NOT IMPLEMENTED
Deployment is NOT authorized and this candidate failed acceptance. Retain the proven active C4 route. Do not begin C5F. The following plan applies only after separately authorized repairs and new qualification.

Exact integration surfaces to review:
- `search/query_plan.py`: a server-owned parser selector defaulting to C4, unchanged QueryPlan/public schema, mode handling and max-length policy. Package the reviewed experimental implementation under an application module before staging; no production scratch imports.
- `search/query_confidence.py`: one compatible typed/capability decision composition and native edit revalidation, preserving unresolved mandatory semantics.
- `search/query_session.py`, `search/session_store.py`, `search/query_interaction.py`: consistent parser version, parse/validate/canonical resolver imports, current identity/login/library/workspace binding, source-span edits, correction availability, expiry/version and one-use reservations. Do not change authorization behavior or use global monkeypatching.
- `search/interaction_api.py`: review existing150-character query/100-character completion contracts and placeholder completion semantics. Any schema or UX change is a separate reviewed decision, not silently extended here.
- `search/query_execution.py`, `search/api.py` and institutional route callers: retain native fresh access guards, scoped facet/capability selection, local-only candidate universes, filtering/hydration, pagination, error behavior and C4 assessment. Scope comes from trusted server context.

Staging prerequisites: zero observed unsafe/critical-operand errors under pre-registered fresh validation; required typed/execution/notice/EXACT gates; authorized disposable Mongo/API/current-membership/expiry/CAS/replay/borrowing tests; real providers and unavailable-service checks; benchmarked relevance; accepted parser/retrieval/concurrency latency; health/index-generation verification and packaging hashes. Current no-write constraint must be separately lifted for those staging fixtures.

Rollout proposal: independently reviewed server feature flag (does not exist in this phase), defaultC4, small authorized staging cohort and rollback rehearsal. Monitor decision types/reason codes, field coverage, parser/provider latency/errors, blocked/unsafe audits by mode/scope; never log private raw queries broadly. No unconditional model fallback.

Rollback: switch proposed selector back to C4; reject/migrate only incompatible search parser-version contexts through existing actor/scope-bound facilities. Do not delete general login/library data. Restore paired artifacts/config generation only if an authorized deployment changed them; this phase changed no database or indexes and needs no data rollback. Deployment/flag/source edits are not performed by this report.
