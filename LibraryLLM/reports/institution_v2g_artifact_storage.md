# Storage and publication boundary

Root: `local-data/library-intelligence/<canonical library UUID>/`. Immutable dataset/search/kg generation UUID subdirectories hold metadata, manifest and target artifacts. Search: index.faiss + vectors.npy + metadata.json. KG: graph.json + metadata.json. Tenant-root SQLite embedding cache is separate from private RAG/global caches.

User strings never become path components. UUID parsing, containment and resolved-path equality reject traversal, child symlinks/junctions and protected global roots. No HTTP raw-artifact download route exists. Safe status routes do not expose paths, fence/lease tokens or traceback text.

Worker writes a private `.building` directory, validates all checksums/identity/schema/dimensions/normalization/graph invariants, then atomically renames it. A durable canonical Mongo target pointer is the sole publication authority. The pointer requires exact library/target/job/fence ownership plus current membership/lifecycle and source fingerprint. No competing filesystem pointer or hard deletion of canonical tenant data exists.

One durable effective-active job per library+target is enforced by a partial unique index. Search and KG are independent targets. Lease heartbeat, per-job and per-target fencing and explicit unknown-outcome recovery prevent old workers publishing after recovery. Reconciliation is read-only by default: temporary/orphan/final corruption, missing pointer, source mismatch, expired/unknown jobs and duplicate-active records are reported, never automatically deleted or blindly published.
