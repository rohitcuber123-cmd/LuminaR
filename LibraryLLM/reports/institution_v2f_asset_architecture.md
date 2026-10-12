# Library Digital Assets, Part 2F

This phase adds canonical library ownership around the accepted per-document PDF/OCR/chunk/FAISS pipeline. Core owns authorization, metadata, source upload, lifecycle and the durable processing queue. The existing RAG process consumes that queue with its resident embedding model and existing document AI engine. It creates no tenant catalogue HNSW, knowledge graph, private global vector index or additional Qwen instance.

## Ownership and visibility

`institution_library_assets` stores immutable UUID `asset_id` and canonical UUID `library_id`. Neither filename, title, account membership, global work reference nor file placement establishes ownership. Persisted fields include uploader's numeric user ID, PDF type, title, original filename, parser-established media type, size, SHA-256 checksum, internal storage key, status, visibility, optional same-library book/global reference, extraction/RAG status and timestamps. Processing summaries expose pages, chunks, bounded warnings and safe error codes. Public DTOs exclude storage paths, internal upload IDs, lease identities and generation pointers. Scoped uploader name and linked-book title provide useful summaries.

`STAFF_ONLY` permits active ADMIN/LIBRARIAN members. `MEMBERS` additionally permits active GENERAL_USER members of the exact library after READY. Every protected access reads current account eligibility, ACTIVE library and current exact membership through the accepted centralized guards. Platform assignment and historical account role confer no tenant asset permission. Outsiders, cross-library asset UUIDs and patron requests for STAFF_ONLY assets receive concealed 404 responses. Patrons cannot upload, edit, delete or reprocess library-owned documents.

## Canonical API

The only Core resource family is `/libraries/{library_uuid}/assets`: bounded GET list, POST multipart upload, GET/PATCH/DELETE `/{asset_uuid}`, POST `/{asset_uuid}/reprocess` and authorized GET `/{asset_uuid}/file`. List filters include escaped title/filename/linked-book search, visibility, status, same-library book ID, offset and limit; maximum page size is 100. The list takes a short centralized library lock so concurrent visibility/membership changes cannot expose a mixed snapshot. Mutations take the accepted durable library lock and repeat authority checks inside it. Protected responses use `Cache-Control: private, no-store` and `nosniff`.

The file endpoint uses Starlette FileResponse, supports byte ranges and streams the checked source path. It never advertises a filesystem path; the original display filename is Content-Disposition metadata only. PDF responses use a restrictive sandbox policy. Every request repeats state and visibility checks before file access.

## Storage and validation

The shared Core/RAG default root is `local-data/library-assets`, configurable with `LIBRARY_ASSET_ROOT`. Each source is `<library_uuid>/<asset_uuid>/source.pdf`; each fenced derived generation is `<library_uuid>/<asset_uuid>/generation/<generation_uuid>/`. Fixed derived files are `extracted.json`, `chunks.json`, `vectors.npy`, `runtime.faiss` and `manifest.json`. Asset, library and generation identifiers must parse as UUIDs; resolved directory/file paths must equal their constructed canonical paths. Junction/symlink escapes are rejected before private reads. Original filenames never name storage directories or source files.

Only PDF is exposed because it is the accepted private-document pipeline's actual format. A multipart-body middleware bounds disk spooling and upload reads reuse its 64 MiB per-file budget. Empty files, excessive size, path-bearing/control/encoded-control filenames, incorrect signatures, parser-detected corruption, encrypted PDFs and missing usable pages are rejected. The client MIME does not authorize a format. The accepted page/chunk/OCR limits remain in the reused processing pipeline.

SHA-256 establishes source integrity. Same-library identical uploads produce an explicit duplicate warning and keep distinct IDs. Identical bytes in two libraries retain distinct metadata, source directories, extraction, chunks, index and caches. No physical deduplication or cross-library alias is introduced.

## Durable processing and acknowledgement loss

Upload starts UPLOADING, writes and flushes a canonical `source.part`, inserts metadata, moves the source, persists `institution_library_asset_jobs` and commits PROCESSING. A normal HTTP 202 acknowledges durable submission rather than RAG readiness. The required client `X-Luminar-Upload` UUID is unique with library and uploader; repeating identical input returns the original asset/job, while reuse with different content or metadata returns 409. Uncertain persistence retains nonpublic FAILED metadata/source for reconciliation instead of assigning orphan content elsewhere.

Jobs persist UUID job ID, canonical owner IDs, submitting actor, QUEUED/PROCESSING/READY/FAILED state, attempt number, bounded safe error, timestamps and a renewable claim lease. The RAG app processes one job at a time and renews the lease. Reclaiming an expired lease obtains both a new lease UUID and a new generation UUID, so a stale worker cannot overwrite its successor's artifacts. Completion compares exact job, claim, generation, current asset state and current submitting actor's account/membership/library authority before publishing READY. Manifest identity, checksum and expected files must match. A stale/deleted/revoked job cannot resurrect an asset. Repeated reprocess clicks reuse an outstanding job.

The source, extraction/OCR, chunking, embeddings and isolated FAISS artifact are separate states; FAILED is visible with a safe code and an authorized reprocess action. Extraction and chunk records carry library UUID, asset UUID and document/generation identity, with source offsets in chunks. RAG authorization precedes private artifact access and output; the RAG adapter supplies further manifest/file/provenance checks and existing Knowledge Tool adapters.

This is a bounded Mongo queue with restart-recoverable claims, not a new general worker platform. It inherits the accepted standalone-Mongo durable library lock policy: unknown commit outcomes retain a fail-closed lock and require operator reconciliation rather than automatically admitting a competing writer.

## Deletion and recovery

Delete commits DELETING before any artifact cleanup, immediately denying file/RAG/patron discovery. It terminates outstanding jobs, removes derived generation subtrees and moves the original to the asset's `retired/source.pdf`. DELETED preserves canonical metadata and audit evidence; retained originals have no normal API retrieval route. A filesystem cleanup failure keeps DELETING with `DELETE_INCOMPLETE`; an authorized repeated delete completes cleanup. Workers remove only their own fenced unpublished generation and preserve a generation already published if its completion acknowledgement was lost.

Library suspend/remove follows the existing centralized denial without deleting documents. Restored libraries can regain access to intact READY assets. Membership revocation and MEMBERS-to-STAFF_ONLY changes require no index rebuild; the next access rechecks authority.

The shared institution audit records upload, processing start, READY, failure, visibility/link changes, delete and reprocess with actor, library, asset, time and bounded metadata. It never stores document text, prompts, raw paths or credentials.

`scripts/reconcile_library_assets_v2f.py` defaults to dry run: source/namespace/checksum, extraction and chunk provenance, manifest/file checksums, missing READY files, interrupted moves/uploads/deletes and orphan source/generation namespaces. It never guesses ownership or deletes orphan files. Explicit `--repair-metadata` revokes inconsistent READY metadata or resumes a completely persisted interrupted submission. Explicit `--repair-source` completes only a canonical source.part whose size/checksum match unchanged canonical metadata. Sources failing integrity remain untouched. Subsequent authorized reprocessing restores artifacts.

Indexes are justified by bounded tenant lists/visibility/status/book/checksum queries, unique upload identity, unique immutable asset/job IDs and the worker's state/lease query. The architecture does not load all libraries/documents in a browser, implicitly search a member's entire library corpus, migrate personal documents or publish world-readable assets.
