# 03 — DATABASE-LEVEL MULTI-TENANCY & DATASET ISOLATION

## 1. Multi-Tenancy Architecture Classification

A fundamental architectural question during a project defense is: **Does LuminaR use a Database-per-Tenant, Collection-per-Tenant, or Shared-Database Shared-Collection architecture?**

### Verified Finding: Hybrid Isolation (Architecture A/D)
LuminaR employs a **Hybrid Isolation Strategy**:
1. **Relational / Structured Metadata**: **Shared Database, Shared Prefixed Collections (Architecture A)** within MongoDB (`library_database`), where all institutional data resides in dedicated collections prefixed with `institution_*` and strictly partitioned by a UUID string field `library_id`.
2. **Unstructured Documents, Vector Indexes & Knowledge Graphs**: **Dedicated Filesystem & Dedicated Vector Index Isolation (Architecture D)**, where each library has isolated physical directories and dedicated FAISS index files under `local-data/library-intelligence/{library_id}/` and `local-data/library-assets/{library_id}/`.

---

## 2. Inventory of Database Collections & Scoping Policies

All multi-tenant data structures are registered and indexed on application startup in [backend/main.py:L37-48](file:///d:/SDC/LibraryLLM/backend/main.py#L37-L48). The underlying MongoDB helper `collection(name)` maps each logical name to `db['institution_' + name]` ([backend/services/institution_repository.py:L17-18](file:///d:/SDC/LibraryLLM/backend/services/institution_repository.py#L17-L18)).

| Collection Name | Primary Key | Library Identifier Field | Additional Owner / Actor Fields | Compound Indexes & Isolation Constraints | Enforcement Location |
|---|---|---|---|---|---|
| `institution_libraries` | `library_id` (UUID) | `library_id` | `owner_user_id` | `[('library_id', 1)]` (unique), `[('slug_normalized', 1)]` (unique) | `institution_service.py` |
| `institution_security` | `_id` (ObjectId) | `library_id` (UUID) | `access_code_changed_by` | `[('library_id', 1)]` (unique) | `institution_security.py` |
| `institution_memberships` | `membership_id` (UUID) | `library_id` (UUID) | `user_id`, `created_by_user_id` | `[('library_id', 1), ('user_id', 1)]` (unique), `[('library_id', 1), ('status', 1), ('role', 1)]` | `institution_dependencies.py` |
| `institution_invitations` | `invitation_id` (UUID) | `library_id` (UUID) | `invited_by_user_id`, `invited_user_id` | `[('token_hash', 1)]` (unique), `[('library_id', 1), ('email_normalized', 1)]` (unique on PENDING) | `institution_service.py` |
| `institution_library_books` | `library_book_id` (UUID) | `library_id` (UUID) | `created_by_user_id` | `[('library_id', 1), ('accession_number', 1)]` (unique), `[('library_id', 1), ('accession_sequence', 1)]` (unique), `[('library_id', 1), ('source_key', 1)]` (unique) | `TenantInventory` repository wrapper |
| `institution_holdings` | `holding_id` (UUID) | `library_id` (UUID) | N/A | `[('holding_id', 1)]` (unique), `[('library_id', 1), ('library_book_id', 1)]` (unique) | `TenantInventory` wrapper |
| `institution_copies` | `copy_id` (UUID) | `library_id` (UUID) | N/A | `[('copy_id', 1)]` (unique), `[('library_id', 1), ('barcode', 1)]` (unique), `[('library_id', 1), ('holding_id', 1), ('copy_number', 1)]` (unique) | `TenantInventory` wrapper |
| `institution_sequences` | `_id` (ObjectId) | `library_id` (UUID) | N/A | `[('library_id', 1), ('sequence_type', 1)]` (unique) | `TenantInventory.accession()` |
| `institution_locks` | `_id` (`library_id`) | `_id` (`library_id`) | `holder` (UUID) | Primary key is `library_id`. Single lock per library. | `institution_repository.py:library_mutation` |
| `institution_lending_requests` | `lending_request_id` (UUID) | `library_id` (UUID) | `user_id`, `reviewed_by_user_id` | `[('library_id', 1), ('user_id', 1), ('status', 1)]` | `library_lending_service.py` |
| `institution_loans` | `loan_id` (UUID) | `library_id` (UUID) | `user_id`, `copy_id`, `holding_id` | `[('library_id', 1), ('status', 1)]`, `[('library_id', 1), ('user_id', 1)]` | `library_lending_service.py` |
| `institution_reservations` | `reservation_id` (UUID) | `library_id` (UUID) | `user_id` | `[('library_id', 1), ('library_book_id', 1), ('queue_sequence', 1)]` | `library_reservation_service.py` |
| `institution_fees` | `fee_id` (UUID) | `library_id` (UUID) | `user_id`, `waived_by_user_id` | `[('library_id', 1), ('user_id', 1), ('status', 1)]` | `library_fee_service.py` |
| `institution_library_assets` | `asset_id` (UUID) | `library_id` (UUID) | `uploaded_by_user_id` | `[('library_id', 1), ('uploaded_by_user_id', 1), ('upload_id', 1)]` (unique), `[('library_id', 1), ('visibility', 1), ('status', 1)]` | `library_asset_service.py` |
| `institution_library_asset_jobs` | `job_id` (UUID) | `library_id` (UUID) | `actor_user_id` | `[('library_id', 1), ('asset_id', 1), ('created_at', -1)]` | `library_asset_service.py` |
| `institution_intelligence_targets` | `_id` (ObjectId) | `library_id` (UUID) | N/A | `[('library_id', 1), ('target', 1)]` (unique) | `library_intelligence_store.py` |
| `institution_intelligence_jobs` | `job_id` (UUID) | `library_id` (UUID) | `requested_by_user_id` | `[('library_id', 1), ('target', 1)]` (unique on active), `[('state', 1), ('created_at', 1)]` | `library_intelligence_store.py` |
| `institution_intelligence_generations` | `generation_id` (UUID) | `library_id` (UUID) | `created_by_user_id` | `[('library_id', 1), ('sequence', 1)]` (unique) | `library_intelligence_store.py` |
| `institution_audit` | `event_id` (UUID) | `library_id` (UUID) | `actor_user_id`, `target_user_id` | `[('library_id', 1), ('created_at', -1)]`, `[('actor_user_id', 1), ('created_at', -1)]` | `institution_repository.py:audit` |
| `institution_attempts` | `_id` (`key`) | Encoded in key | Encoded in key | `[('expires_at', 1)]` (`expireAfterSeconds: 0`) | `institution_service.py:consume_join_budget` |

---

## 3. The `TenantInventory` Scoping Boundary

Rather than relying on ad-hoc MongoDB queries throughout the codebase, inventory operations are encapsulated by the `TenantInventory` repository class:

### 3.1 Code Implementation

Code reference: [backend/services/library_catalogue_repository.py:L41-67](file:///d:/SDC/LibraryLLM/backend/services/library_catalogue_repository.py#L41-L67):
```python
class TenantInventory:
    def __init__(self, library_id):
        self.library_id = str(UUID(str(library_id)))

    def scope(self, query=None):
        query = dict(query or {})
        if 'library_id' in query and query['library_id'] != self.library_id:
            raise ValueError('Cross-library repository predicate rejected.')
        return {**query, 'library_id': self.library_id}

    def one(self, name, query=None, projection=None):
        return collection(name).find_one(self.scope(query), projection)

    def rows(self, name, query=None):
        return collection(name).find(self.scope(query), {'_id': 0})

    def count(self, name, query=None):
        return collection(name).count_documents(self.scope(query))

    def insert(self, name, document):
        collection(name).insert_one(self.scope(document))

    def update(self, name, query, values):
        if 'library_id' in values and values['library_id'] != self.library_id:
            raise ValueError('Cannot change tenant identity.')
        return collection(name).update_one(self.scope(query), {'$set': values})
```

### 3.2 Security Guarantees of `TenantInventory`

1. **UUID Normalization**: `self.library_id = str(UUID(str(library_id)))` guarantees that the tenant ID is a valid canonical UUID, rejecting path-traversal strings or MongoDB injection payloads.
2. **Predicate Tamper Detection**: If a caller accidentally or maliciously passes a query containing `{'library_id': 'other-id'}`, `self.scope()` detects the mismatch and immediately raises `ValueError('Cross-library repository predicate rejected.')`.
3. **Immutability of Tenant Identity**: In `self.update()`, any attempt to alter the `library_id` of an existing record raises `ValueError('Cannot change tenant identity.')`, preventing horizontal privilege escalation where an attacker attempts to reassign a resource to another library.
4. **Mandatory Scoping**: Every find, count, insert, and update automatically injects `{'library_id': self.library_id}` into the MongoDB filter.

---

## 4. Dataset Ingestion and Uniqueness Boundaries

### 4.1 Ingestion Pipeline (`library_inventory_import.py`)

Staff members can import book inventories via CSV or delimited files:
1. **Upload Size Cap**: Bounded by `InventoryUploadLimit` middleware (32 MiB max) and `MAX_BYTES` (16 MiB) in `importer.py`.
2. **Preview Mode**: `importer.preview()` parses headers, validates columns (`title`, `authors`, `isbn`, `copies`, `shelf_location`), and previews additions in memory without writing to permanent collections.
3. **Durable Apply Mode**: `importer.apply()` executes inside a `library_mutation(library_id)` lock.
4. **Sequential Accession Generation**: Each added book receives a sequential institutional accession number generated via `TenantInventory.accession()`:
   ```python
   sequence = collection('sequences').find_one_and_update(
       {'library_id': self.library_id, 'sequence_type': 'BOOK_ACCESSION'},
       {'$inc': {'value': 1}},
       upsert=True, return_document=ReturnDocument.AFTER
   )
   accession_number = f"{prefix}-{sequence['value']:06d}"
   ```

### 4.2 Handling Identical Titles and ISBNs Across Separate Libraries

A critical question for multi-tenant SaaS is: **What happens if Library A and Library B upload books with the exact same title, author, and ISBN?**

- **Verified Behavior: Zero Collision**:
  - In a naive database design, a unique index on `isbn_13` would prevent Library B from uploading a book already held by Library A.
  - LuminaR uses **Compound Indexes**:
    ```python
    ([('library_id', 1), ('isbn_13', 1)], {'partialFilterExpression': {'isbn_13': {'$type': 'string'}}})
    ([('library_id', 1), ('accession_number', 1)], {'unique': True})
    ```
  - Uniqueness is strictly enforced **within the tenant namespace**, never globally across all tenants.
  - Test evidence: [tests/institution_v2f/test_assets.py:L124-132](file:///d:/SDC/LibraryLLM/tests/institution_v2f/test_assets.py#L124-L132) explicitly tests uploading the identical document with identical SHA-256 checksum to two separate libraries (`library(owner=1)` and `library(owner=3)`). The test asserts that both receive independent IDs, independent filesystem paths, and zero collisions.

---

## 5. MongoDB Aggregation Pipeline Scoping Verification

When performing complex aggregation pipelines (such as catalogue searches or member lookups):
- Code reference: [backend/services/library_catalogue_experience.py:L45-65](file:///d:/SDC/LibraryLLM/backend/services/library_catalogue_experience.py#L45-L65):
  ```python
  def usable(library_id, *, search='', subject='', author='', circulation_status='', staff=False):
      pipeline = [{'$match': {'library_id': str(UUID(str(library_id))), 'status': 'ACTIVE'}}]
      # Additional filtering on normalized title, authors, subjects...
      return pipeline
  ```
- **Aggregation Boundary**: The first stage of every aggregation pipeline is an explicit `$match` filtering on `{'library_id': canonical_id, 'status': 'ACTIVE'}`.
- **Lookup Scoping**: When `$lookup` joins are performed (e.g., joining `holdings` to `library_books`), the foreign collection is also filtered by `library_id` to guarantee that records from another library cannot be joined.

---

## 6. Edge Case and Failure Analysis

1. **Orphaned Documents on Partial Deletion**:
   - Because MongoDB does not support cross-collection cascading foreign keys natively, deletions are managed via soft-deletion (`status = 'WITHDRAWN'` or `'DELETED'`) combined with atomic state updates under `library_mutation`.
2. **Bulk Update Bypass Prevention**:
   - There are no un-scoped `update_many` or `delete_many` queries in the production codebase. All write operations require an explicit `TenantInventory` scope or an explicit `library_id` parameter.
