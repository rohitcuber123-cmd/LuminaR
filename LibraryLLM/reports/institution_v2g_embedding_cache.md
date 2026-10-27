# Tenant embedding input and reuse

Reuse the existing global `semantic_text` helper for bounded descriptive book metadata. Classification remains in metadata/KG; no document text, fees, loans or account fields enter embeddings. Public linked work enrichment supplies missing descriptive fields only.

Each canonical UUID library root contains a separate SQLite content-addressed cache. Key: model revision/version + normalization/schema + exact semantic input SHA-256. Cached bytes have a checksum and must decode as finite normalized float32[384]. A mismatch fails the build, retaining the last good published generation. Global work identity alone is insufficient, because two libraries can have different local metadata for one work.

Global caches and embedding indexes are untouched. Reuse across unchanged tenant builds avoids re-encoding unchanged input without mutating a published generation.
