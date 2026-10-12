# Recommended next scope

Stop after Institution Part 2D acceptance. Await explicit approval.

A focused tenant analytics authorization/data-isolation audit is the recommended
next phase because Events and domain notifications now have canonical tenancy.
Define safe aggregates, retention and role boundaries before implementation. A
private-document RAG tenancy audit is a separate alternative, with its own source
ownership, retrieval and artifact boundaries. Do not combine either with automatic
HNSW/KG building, router research or Build/Rebuild controls.

No work on either recommendation has begun. Legacy event/notification production
migration remains a separately approved operator activity, not a continuation job.

Read-only dependency review found the remaining global platform summary in
`backend/routes/notifications.py`, while tenant stock/lending summaries use the
canonical library-scoped services. No new analytics product or endpoints were
added. The one Events count convergence fix uses the existing scope query.

Private-document upload and access remain account-owned in
`rag/services/private_document_routes.py` through `service.owned(document_id,
user)`. Global linked-work retrieval remains in `rag/api.py` and the existing book
access service. Those modules were inspected without edits. A future tenant RAG
phase must specify library ownership and membership checks before changing the
accepted personal-document behavior or introducing any tenant retrieval artifacts.
