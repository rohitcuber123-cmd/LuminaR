# Persistence architecture and schema overview

## Actual storage responsibilities

MongoDB through PyMongo is authoritative for account/catalogue/circulation/business data (`backend/database/mongodb.py`). Collections are accessed directly by services, not through a universal ORM repository. References primarily use application numeric IDs and Open Library-style work IDs; Mongo `_id` exists but is not the principal API identity. SQLite supports semantic queues/cache, graph sidecars, revoked sessions, and private document registry; DuckDB and Parquet support offline metadata/ISBN/corpus work. FAISS graphs and NumPy/JSON mappings are local retrieval artifacts. Browser sessionStorage holds account/assistant state; OPFS/IndexedDB can hold encrypted prepared documents.

| Entity / collection | Actual important fields/identity | Relationships and current scope | Proposed library impact |
|---|---|---|---|
| users | user_id, name, email, password_hash, role, verification/active/setup flags, created_at | Global numeric identity; unique email/user ID required | Keep global; separate LibraryMembership + preference active library |
| email_verifications | user/email, hashed OTP, expiry/consumption/setup state | Account workflow | Usually global identity; invitation can include authorized library |
| counters | `_id`, seq | Atomic IDs for several services | Keep IDs globally unique or explicitly namespace counters |
| books | book_id, work_id, title, authors, subjects, description, ratings/logs, shelf, total/available_copies, created_at | Global work record | Separate library holding/private catalogue record; avoid one library_id on shared work |
| library_inventory | library_id, work_id, ISBN, total/available_copies, shelf_location, source, timestamps | Current scoped physical holding | Add holding_id/dataset/version, compound unique scope, canonical inventory authority |
| inventory_previews | preview_id, library_id, filename, rows/status/summary, times | Embedded row status payload | Uploader membership, limits/expiry, retain separate from versioned catalogue Dataset |
| issues | issue_id, user_id, book_id/work_id/title, inventory_source, library_id, issued/due/returned timestamps, status, fine_amount, renewal metadata | Numeric references + denormalized title; current default LIB001 | Immutable holding/library history, policy version, idempotent side effects |
| borrow_locks | `_id=user:work`, token, expires_at | Mongo unique-ID lease | Include library/holding; lease ownership/fencing and cleanup |
| reservations | reservation_id,user_id,book_id,work_id,title,times,status | Global work queue; no library field in create | Library+holding+user active key, scoped FIFO |
| fines | fine_id,user_id,issue_id,work_id,title,overdue_days,amount,status,times | Persisted return-derived fee | Copy immutable library/holding/policy for history and restricted settlement |
| activity | activity_id,user_id,type,description,resource refs,actor/title,timestamp,event_key | Denormalized audit feed and numeric references | Immutable library and actor membership; platform actions explicit |
| reading_list | user_id,work_id,title/authors/copy fields,timestamp | Unique user/work; denormalized catalogue copy | Decide work-level personal saves vs library-specific holding saves |
| search_history | search_id,user_id,query,top_k,result snapshots,timestamp | User-owned; bounded retrieval | Add library/index/model generation to reproducibility and profiles |
| recommendation_feedbacks | feedback_id,user_id,work_id,type,timestamp | User/work behavior | Library/holding context and separate cross-library consent policy |
| book_categories | category,count,preview work data | Offline cached data | Per-library counts or scoped query; invalidate on catalogue versions |
| events | UUID event_id, validated content/category/dates, related works, status, revision, creator/updater/times | Global; embedded related-work list | library_id, scope kind; ownership checks and scoped related holdings |
| event_user_state | user_id, seen IDs, revision,times | Per-account embedded bounded IDs | unique user+library, library-bound receipts |
| notifications | notice UUID/type/user/title/message/source/ref/event_key, read state/times | Per-user, deduplicated delivery | library provenance; authorized recipient membership |
| Private PDF registry (SQLite) | id,owner,sid,expires,state,cache_id,metadata | user/session owned, not institution | Preserve personal scope; separate library-shared documents/ACL |
| PDF chunks/vectors | chunk_id,document_id,filename,page,text; vectors.npy/runtime.faiss | Local per-document files | Source owner type and library generation for shared corpora |
| Book chunks/index metadata | work/document/chunk IDs,title/author/chapter/offset/text | Global + separate book FlatIP | Holding/library visibility binding and private full-text ownership |
| Semantic snapshot manifests | version,model fingerprint,dimension,base version,generation,counts,checksums | Global graph root | library/namespace/published dataset identity, permissions version |
| Semantic labels | base work_ids array,delta_ids list,overrides | Snapshot-relative positional mapping | composite scope/generation/partition/label mapping |
| Semantic cache/queue (SQLite) | hashes/model-version vectors; seq/kind/IDs/state/retry | One global namespace/root | Scope/dataset generation; per-library queue or scoped shared durable jobs |
| Catalogue graph (SQLite) | books/features/edges/norms | Work→author/subject/topic relations | Private graph partition or scoped candidate generation/validation |
| Libraries / memberships / catalogue datasets | No active entities traced | **PROPOSED** | Add explicit Library, Membership, Dataset, Job, IndexManifest |

Fields are code-derived summaries, not a dump of deployed database schema. Live document counts, index presence, validation rules and migration completion are **CANNOT VERIFY FROM CURRENT IMPLEMENTATION** without inspecting a running database.

## Join and denormalization patterns

`book_service`, `book_capability_service` and `availability_service` join books to issues/inventory in application code by work/user IDs. Event hydration batches related work/user IDs and builds dictionaries. Admin operations gather resource IDs then hydrate source records; reading lists copy title/author/copy data. Transactions store title snapshots for durable history. Mongo summary/events use aggregation (`$match/$group`, event `$addFields/$sort`), but no active `$lookup` join was found in the inspected core paths. Relationships are not predominantly ObjectId document references. Embedded preview rows, seen event IDs, renewal receipts and result snapshots reduce joins but can grow or age.

## Consistency limitations

There is no single transaction across Mongo, FAISS/files and browser state. Catalogue mutation intent journaling and immutable index publication recover work eventually; live Mongo revalidation removes missing books but cannot regenerate stale vectors instantly. Circulation stock/issue/fine/activity writes have partial-failure windows. Private PDFs publish registry ACTIVE after preparing files and disable access before deletion, but rely on shared local storage and process locking. Book index publication replaces global index and metadata separately in `embed.index_registered_book`, unlike catalogue snapshot publication; a crash between replacements can mix generations. Snapshot validation helps detect, not prevent, all recovery gaps.

## Future schema decisions

Use global account identity plus `LibraryMembership(user_id,library_id,role,status)` with compound uniqueness. An active-library preference is not authorization. Preserve global Work metadata and scoped Holding (`holding_id,library_id,work_id/private_record_id,dataset_id,version,copies,shelf,status,index_status`). A same ISBN/title in two libraries is valid. Private descriptions/full text may belong to scoped catalogue records rather than modifying public shared works.

Redundant library_id on loans/reservations/fines/activity is useful: history remains scoped after books are edited/deleted or users switch institutions. Server assigns and verifies it; never accept inconsistent redundant ownership from a client. Add scoped compound indexes for holding identity, statuses/time, memberships, dataset checksum/version, jobs/idempotency and source mappings. Database is the source of truth; index manifests and mappings are versioned derived state. Full proposed schemas and migration strategy: [21](21_PRIVATE_LIBRARY_ARCHITECTURE.md).
