# AI context audit

The production Assistant selected context resolves global WorkID metadata; personal PDF selection uses session-owned document IDs. Its string syntax admits opaque IDs, but a library asset UUID or filename does not authorize a global book record and cannot acquire tenant authority through selected_work_ids. The schema has no typed library asset target or library ownership field.

Reuse existing resident Qwen and document retrieval via an explicit library asset page/API. Global Assistant does not enumerate libraries or search assets. Authorization must precede file/chunk/index/cache access and be rechecked before returning generated output. Dedicated source context retains canonical library/asset identity.

Typed library assets in the global Select for AI list are deferred under the request's Phase 20 allowance because its current router/schema supports global book selections and personal session document IDs. Explicit per-asset document Q&A and shared Knowledge Tools provide the permitted library document interaction without changing the frozen router.
