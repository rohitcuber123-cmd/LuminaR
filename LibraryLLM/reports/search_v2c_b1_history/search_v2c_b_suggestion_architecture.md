# Authorized bounded autocomplete — observed implementation

GET /query/suggestions and POST /query/suggestions/select authenticate and authorize
before any vocabulary/cache/entity lookup. Maximum8, prefix2 for subjects,3 for
authors/titles, bounded150 characters. Exact/quoted/numeric forms abstain.

Global uses the existing SQLite TITLE/AUTHOR prefix range indexes (32 relationships
per source per base/delta) and indexed canonical work_id hydration. It never scans
the 5M catalogue, invokes HNSW/KG/CrossEncoder, or uses Global filler for tenants.
Tenant titles use the existing library_id,normalized_title index; authors use one
small auxiliary Mongo library_id,status,authors index with en strength2 collation.
At most32 candidates/source are fetched before the unchanged usable()/format
pipeline verifies canonical visibility. Subjects use a bounded2048 tenant/4096
Global projection; a max16 LRU expires30s and is keyed by user,sid,library,workspace
and latest indexed audit generation. Cached subject candidates receive fresh
bounded indexed discoverability proofs, including after removal. No response
cache can bypass authorization. Typo matching uses at most64 subject candidates
from a prebuilt prefix bucket and conservative threshold/margin; proper names are
not silently rewritten. Broad author typo/infix completion is intentionally absent.

Suggestion IDs are random opaque tokens in a max2048 process cache, expire120s,
and bind exact query/mode/owner/workspace/generation. Selecting requires fresh
authorization and canonical revalidation. Viewing/typing does not commit Search.
The frontend debounces200ms, cancels with AbortController, gates by full scope/token/
query/mode key, checks async selection keys, handles IME and keyboard listbox input.
403/404 reuse the existing context revalidation path to remove revoked private UI.
