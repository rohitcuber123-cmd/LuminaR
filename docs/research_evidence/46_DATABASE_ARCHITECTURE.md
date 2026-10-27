# 46_DATABASE_ARCHITECTURE.md: MongoDB Schema & Collection Architecture

> **Audit Report:** Part 8 Research Evidence Audit  
> **Repository:** LuminaR (`d:\SDC\LibraryLLM`)  
> **Database:** MongoDB 7.x / 8.x (`luminar_library` / `luminar_local`)  
> **Scope:** Complete Inventory of Active MongoDB Collections, Models, Schemas, Indexes, and Joins  
> **Status:** Ground-Truth Code Verification  

---

## 1. Database Architecture & Design Principles

LuminaR uses a **hybrid multi-tenant document architecture**:
1. **Shared-Database, Tenant-Partitioned Tenancy:** All tenants share a single MongoDB database (`luminar_library`), partitioned logically by a mandatory canonical UUID `library_id` on all tenant collections (`institution_*`).
2. **Explicit Foreign Keys:** Primary keys use UUID v4 strings (for institutional entities) or auto-incrementing integers (for global `user_id` and legacy catalogue entities). Cross-collection integrity is enforced in application service boundaries rather than database triggers.
3. **Write-Ahead Operation Journaling:** Multi-document circulation mutations use a dedicated journal collection (`institution_lending_operations`), maintaining state transitions (`PENDING` $\rightarrow$ `COMMITTED`) and two-phase effect rollback.
4. **Pessimistic Concurrency Leases:** Cross-worker serialization on standalone MongoDB instances uses `institution_locks`, with an immutable unique `_id` lease per `library_id`.
5. **Exact Integer Money Representation:** All monetary balances and fees are stored in integer minor units (`amount_minor`, e.g., 500 minor units = ₹5.00 INR) with append-only ledger entries in `institution_fee_ledger`, avoiding floating-point rounding errors.

---

## 2. Institutional Tenant Collections Inventory (`institution_*`)

### 2.1 `institution_libraries`
- **Purpose:** Core profile and tenant metadata for registered libraries and institutions.
- **Fields:**
  - `library_id`: `string` (UUID v4, PK)
  - `name`: `string` (Display name of library)
  - `slug`: `string` (URL-safe slug)
  - `slug_normalized`: `string` (Case-folded canonical slug, UK)
  - `library_type`: `string` (`"PUBLIC_LIBRARY"` | `"PRIVATE_INSTITUTION"`)
  - `access_mode`: `string` (`"PUBLIC"` | `"INVITATION_ONLY"` | `"CODE_PROTECTED"`)
  - `owner_user_id`: `integer` (FK to `users.user_id`)
  - `status`: `string` (`"ACTIVE"` | `"PROVISIONING"` | `"SUSPENDED"` | `"REMOVED"`)
  - `accession_prefix`: `string` (Prefix for generated accession IDs, e.g., `"LIB"`)
  - `description`: `string` (Optional description text)
  - `contact_email`: `string` (Official administrative email)
  - `created_at`: `datetime` (UTC timestamp)
  - `updated_at`: `datetime` (UTC timestamp)
- **Indexes:**
  - `{ "library_id": 1 }` (Unique)
  - `{ "slug_normalized": 1 }` (Unique)
  - `{ "status": 1, "library_type": 1, "name": 1, "library_id": 1 }`
- **Keys & References:** Primary Key: `library_id`. `owner_user_id` references `users.user_id`.
- **Embedded / Joins:** Looked up by `platform_library_service.py` with `$lookup` to `users` for owner resolution.

---

### 2.2 `institution_security`
- **Purpose:** Stores hashed access pass codes for code-protected private institutions.
- **Fields:**
  - `library_id`: `string` (UUID v4, PK, FK to `institution_libraries`)
  - `access_code_hash`: `string` (Bcrypt or Argon2 hash of institutional secret pass code)
  - `code_version`: `integer` (Monotonic version counter rotated upon secret change)
  - `updated_at`: `datetime` (UTC timestamp)
- **Indexes:**
  - `{ "library_id": 1 }` (Unique)
- **Keys & References:** Primary Key & Tenant FK: `library_id`. `userId`: None.
- **Embedded / Joins:** Direct 1-to-1 extension of `institution_libraries`. Never returned in API responses.

---

### 2.3 `institution_memberships`
- **Purpose:** Tracks user enrollment and granular administrative roles within tenant libraries.
- **Fields:**
  - `membership_id`: `string` (UUID v4, PK)
  - `library_id`: `string` (UUID v4, FK to `institution_libraries`)
  - `user_id`: `integer` (FK to `users.user_id`)
  - `role`: `string` (`"ADMIN"` | `"LIBRARIAN"` | `"GENERAL_USER"`)
  - `status`: `string` (`"ACTIVE"` | `"SUSPENDED"` | `"REMOVED"`)
  - `grant_invitation_id`: `string` (Optional UUID FK to `institution_invitations`)
  - `created_at`: `datetime`
  - `updated_at`: `datetime`
- **Indexes:**
  - `{ "membership_id": 1 }` (Unique)
  - `{ "library_id": 1, "user_id": 1 }` (Unique)
  - `{ "user_id": 1, "status": 1, "library_id": 1 }`
  - `{ "library_id": 1, "status": 1, "role": 1 }`
- **Keys & References:** `library_id` and `user_id` form a composite business key.
- **Embedded / Joins:** Hydrated in `institution_dependencies.py` to authenticate tenant requests.

---

### 2.4 `institution_invitations`
- **Purpose:** Pending staff and patron invitation records with cryptographically hashed tokens.
- **Fields:**
  - `invitation_id`: `string` (UUID v4, PK)
  - `library_id`: `string` (UUID v4, FK)
  - `email`: `string` (Invited recipient email)
  - `email_normalized`: `string` (Lowercase trimmed email)
  - `role`: `string` (`"STAFF"` | `"LIBRARIAN"` | `"ADMIN"`)
  - `token_hash`: `string` (SHA-256 hash of single-use invitation token)
  - `status`: `string` (`"PENDING"` | `"ACCEPTED"` | `"EXPIRED"` | `"REVOKED"`)
  - `expires_at`: `datetime`
  - `created_at`: `datetime`
  - `accepted_by_user_id`: `integer` (Optional FK to `users.user_id`)
- **Indexes:**
  - `{ "invitation_id": 1 }` (Unique)
  - `{ "token_hash": 1 }` (Unique partial: `{ token_hash: { $type: "string" } }`)
  - `{ "library_id": 1, "email_normalized": 1 }` (Unique partial: `{ status: "PENDING" }`)
  - `{ "library_id": 1, "status": 1, "created_at": -1 }`
  - `{ "email_normalized": 1, "status": 1 }`
  - `{ "expires_at": 1 }`

---

### 2.5 `institution_audit`
- **Purpose:** Append-only tenant operational ledger recording all administrative, cataloging, and circulation events.
- **Fields:**
  - `event_id`: `string` (UUID v4, PK)
  - `library_id`: `string` (UUID v4)
  - `event`: `string` (`"BOOK_CREATED"`, `"HOLDING_UPDATED"`, `"FEE_CREATED"`, etc.)
  - `actor_user_id`: `integer` (FK to `users.user_id`)
  - `target_user_id`: `integer` (Optional FK)
  - `target_email_normalized`: `string` (Optional)
  - `membership_id`: `string` (Optional FK)
  - `metadata`: `object` (Whitelisted operational metadata dictionary)
  - `created_at`: `datetime`
- **Indexes:**
  - `{ "event_id": 1 }` (Unique)
  - `{ "library_id": 1, "created_at": -1 }`
  - `{ "actor_user_id": 1, "created_at": -1 }`

---

### 2.6 `institution_locks`
- **Purpose:** Distributed write lock on standalone MongoDB, ensuring cross-worker serializability.
- **Fields:**
  - `_id`: `string` (`library_id` UUID v4, PK)
  - `holder`: `string` (UUID v4 of locking worker context)
  - `created_at`: `datetime`
- **Indexes:**
  - Primary key `_id` enforces mutual exclusion atomically.

---

### 2.7 `institution_library_books`
- **Purpose:** Canonical book titles and bibliographic records owned by a tenant library.
- **Fields:**
  - `library_book_id`: `string` (UUID v4, PK)
  - `library_id`: `string` (UUID v4, FK)
  - `accession_number`: `string` (Formatted string, e.g. `"LIB-000042"`, UK per tenant)
  - `accession_sequence`: `integer` (Monotonic integer sequence per tenant)
  - `global_work_id`: `string` (Optional FK to OpenLibrary `books.work_id`, e.g. `"OL12345W"`)
  - `title`: `string`
  - `normalized_title`: `string` (Punctuation-stripped lowercase title for deduplication)
  - `authors`: `array[string]`
  - `subjects`: `array[string]`
  - `isbn_10`: `string` (Optional ISBN-10)
  - `isbn_13`: `string` (Optional ISBN-13)
  - `search_text`: `string` (Concatenated text for fast regex search)
  - `status`: `string` (`"ACTIVE"` | `"WITHDRAWN"`)
  - `needs_review`: `boolean` (Set true if title matches possible duplicate)
  - `source`: `string` (`"MANUAL"` | `"IMPORT"` | `"MIGRATION"`)
  - `source_key`: `string` (Optional unique deduplication key for imports)
  - `created_by_user_id`: `integer`
  - `updated_by_user_id`: `integer`
  - `created_at`: `datetime`
  - `updated_at`: `datetime`
- **Indexes:**
  - `{ "library_book_id": 1 }` (Unique)
  - `{ "library_id": 1, "accession_number": 1 }` (Unique)
  - `{ "library_id": 1, "accession_sequence": 1 }` (Unique)
  - `{ "library_id": 1, "global_work_id": 1 }` (Partial: `{ global_work_id: { $type: "string" } }`)
  - `{ "library_id": 1, "isbn_13": 1 }` (Partial)
  - `{ "library_id": 1, "isbn_10": 1 }` (Partial)
  - `{ "library_id": 1, "normalized_title": 1 }`
  - `{ "library_id": 1, "status": 1, "accession_sequence": 1 }`
  - `{ "library_id": 1, "source_key": 1 }` (Unique partial)

---

### 2.8 `institution_holdings`
- **Purpose:** Inventory stock and circulation parameters for a cataloged book item.
- **Fields:**
  - `holding_id`: `string` (UUID v4, PK)
  - `library_id`: `string` (UUID v4, FK)
  - `library_book_id`: `string` (UUID v4, FK to `institution_library_books`)
  - `total_copies`: `integer` (Total physical volume count)
  - `available_copies`: `integer` (Live calculated requestable snapshot)
  - `shelf_location`: `string` (Physical library location, e.g. `"Floor 2, Shelf B-14"`)
  - `call_number`: `string` (Local classification call number)
  - `local_tags`: `array[string]`
  - `acquisition_note`: `string`
  - `quantity_semantics`: `string` (`"CANONICAL_CIRCULATION"` | `"INVENTORY_SNAPSHOT_NOT_CIRCULATION"`)
  - `circulation_status`: `string` (`"CIRCULATING"` | `"REFERENCE_ONLY"` | `"TEMPORARILY_UNAVAILABLE"` | `"WITHDRAWN"`)
  - `allocation_mode`: `string` (`"AGGREGATE"` | `"COPY"`)
  - `unavailable_stock`: `integer` (Unresolved damaged or missing copies)
  - `created_at`: `datetime`
  - `updated_at`: `datetime`
- **Indexes:**
  - `{ "holding_id": 1 }` (Unique)
  - `{ "library_id": 1, "library_book_id": 1 }` (Unique)

---

### 2.9 `institution_copies`
- **Purpose:** Specific physical copy identities, barcodes, condition tracking, and active assignments.
- **Fields:**
  - `copy_id`: `string` (UUID v4, PK)
  - `library_id`: `string` (UUID v4, FK)
  - `library_book_id`: `string` (UUID v4, FK)
  - `holding_id`: `string` (UUID v4, FK)
  - `copy_number`: `integer` (1-indexed copy counter per holding)
  - `barcode`: `string` (Optional physical barcode scanner identifier, UK)
  - `status`: `string` (`"AVAILABLE"` | `"HELD_FOR_REQUEST"` | `"BORROWED"` | `"RESERVED"` | `"LOST"` | `"DAMAGED"` | `"WITHDRAWN"` | `"UNVERIFIED"`)
  - `lending_request_id`: `string` (Optional FK to `institution_lending_requests`)
  - `loan_id`: `string` (Optional FK to `institution_loans`)
  - `acquisition_date`: `datetime`
  - `created_at`: `datetime`
  - `updated_at`: `datetime`
- **Indexes:**
  - `{ "copy_id": 1 }` (Unique)
  - `{ "library_id": 1, "library_book_id": 1 }`
  - `{ "library_id": 1, "barcode": 1 }` (Unique partial: `{ barcode: { $type: "string" } }`)
  - `{ "library_id": 1, "holding_id": 1, "copy_number": 1 }` (Unique)

---

### 2.10 `institution_sequences`
- **Purpose:** High-performance monotonic sequence generators for accession numbers.
- **Fields:**
  - `library_id`: `string` (UUID v4)
  - `sequence_type`: `string` (`"BOOK_ACCESSION"`)
  - `prefix`: `string` (e.g. `"LIB"`)
  - `value`: `integer` (Current highest generated integer)
  - `created_at`: `datetime`
- **Indexes:**
  - `{ "library_id": 1, "sequence_type": 1 }` (Unique)

---

### 2.11 `institution_lending_requests`
- **Purpose:** Two-phase circulation state machine for borrow requests and return requests.
- **Fields:**
  - `lending_request_id`: `string` (UUID v4, PK)
  - `library_id`: `string` (UUID v4, FK)
  - `library_book_id`: `string` (UUID v4, FK)
  - `holding_id`: `string` (UUID v4, FK)
  - `copy_id`: `string` (Optional UUID FK if allocated)
  - `allocation_mode`: `string` (`"AGGREGATE"` | `"COPY"`)
  - `user_id`: `integer` (FK to `users.user_id`)
  - `request_type`: `string` (`"BORROW"` | `"RETURN"`)
  - `status`: `string` (`"PENDING"` | `"APPROVED"` | `"REJECTED"` | `"CANCELLED"` | `"EXPIRED"` | `"COMPLETED"`)
  - `loan_id`: `string` (Optional FK to `institution_loans`)
  - `title`: `string` (Denormalized book title snapshot)
  - `accession_number`: `string` (Denormalized accession number)
  - `requested_at`: `datetime`
  - `expires_at`: `datetime` (Approval hold expiration, default +24h for BORROW)
  - `reviewed_at`: `datetime`
  - `reviewed_by_user_id`: `integer` (Staff user ID who approved/rejected)
  - `rejection_reason`: `string`
  - `staff_assisted`: `boolean`
  - `created_at`: `datetime`
  - `updated_at`: `datetime`
- **Indexes:**
  - `{ "lending_request_id": 1 }` (Unique)
  - `{ "library_id": 1, "library_book_id": 1, "status": 1 }`
  - `{ "library_id": 1, "user_id": 1, "request_type": 1, "status": 1 }`
  - `{ "library_id": 1, "expires_at": 1 }`

---

### 2.12 `institution_loans`
- **Purpose:** Authoritative active and completed physical circulation loans.
- **Fields:**
  - `loan_id`: `string` (UUID v4, PK)
  - `library_id`: `string` (UUID v4, FK)
  - `library_book_id`: `string` (UUID v4, FK)
  - `holding_id`: `string` (UUID v4, FK)
  - `copy_id`: `string` (Optional UUID FK)
  - `allocation_mode`: `string` (`"AGGREGATE"` | `"COPY"`)
  - `user_id`: `integer` (Borrower `users.user_id`)
  - `borrower_user_id`: `integer` (Duplicate alias for invariant safety)
  - `approved_by_user_id`: `integer` (Staff member ID)
  - `borrow_request_id`: `string` (UUID v4 FK to `institution_lending_requests`)
  - `borrowed_at`: `datetime`
  - `due_at`: `datetime` (Default +14 days)
  - `returned_at`: `datetime` (Timestamp of desk confirmation)
  - `status`: `string` (`"ACTIVE"` | `"RETURNED"`)
  - `global_work_id`: `string` (Optional OpenLibrary ID)
  - `title`: `string`
  - `accession_number`: `string`
  - `renewal_count`: `integer` (Max 2 renewals permitted)
  - `pending_return_request_id`: `string` (Optional UUID if return initiated)
  - `return_requested_at`: `datetime`
  - `physical_received_at`: `datetime`
  - `fee_policy_id`: `string` (FK to snapshot fee policy)
  - `fee_policy_snapshot`: `object` (Embedded policy version snapshot at loan creation)
- **Indexes:**
  - `{ "loan_id": 1 }` (Unique)
  - `{ "library_id": 1, "user_id": 1, "status": 1 }`
  - `{ "library_id": 1, "library_book_id": 1, "status": 1 }`
  - `{ "library_id": 1, "due_at": 1, "status": 1 }`

---

### 2.13 `institution_reservations`
- **Purpose:** FIFO waiting queue for books whose available inventory copies are exhausted.
- **Fields:**
  - `reservation_id`: `string` (UUID v4, PK)
  - `library_id`: `string` (UUID v4, FK)
  - `library_book_id`: `string` (UUID v4, FK)
  - `user_id`: `integer` (FK to `users.user_id`)
  - `global_work_id`: `string`
  - `title`: `string`
  - `accession_number`: `string`
  - `queue_sequence`: `integer` (Monotonic queue sequence per book)
  - `status`: `string` (`"WAITING"` | `"CONVERTED"` | `"FULFILLED"` | `"CANCELLED"` | `"EXPIRED"`)
  - `requested_at`: `datetime`
  - `expires_at`: `datetime`
  - `lending_request_id`: `string` (Optional FK when converted to borrow request)
  - `loan_id`: `string` (Optional FK when fulfilled)
  - `created_at`: `datetime`
  - `updated_at`: `datetime`
- **Indexes:**
  - `{ "reservation_id": 1 }` (Unique)
  - `{ "library_id": 1, "user_id": 1, "status": 1 }`
  - `{ "library_id": 1, "library_book_id": 1, "queue_sequence": 1 }` (Unique)
  - `{ "library_id": 1, "library_book_id": 1, "status": 1, "queue_sequence": 1 }`
  - `{ "library_id": 1, "library_book_id": 1, "user_id": 1 }` (Unique partial: `{ status: "WAITING" }`)

---

### 2.14 `institution_reservation_counters`
- **Purpose:** Monotonic sequence tracker for book waiting queues.
- **Fields:**
  - `library_id`: `string` (UUID v4)
  - `library_book_id`: `string` (UUID v4)
  - `last_sequence`: `integer` (Current highest queue sequence assigned)
- **Indexes:**
  - `{ "library_id": 1, "library_book_id": 1 }` (Unique)

---

### 2.15 `institution_fees`
- **Purpose:** Financial fee accounts associated with overdue loans, lost books, and damages.
- **Fields:**
  - `fee_id`: `string` (UUID v5, PK)
  - `library_id`: `string` (UUID v4, FK)
  - `loan_id`: `string` (UUID v4, FK to `institution_loans`)
  - `library_book_id`: `string` (UUID v4, FK)
  - `user_id`: `integer` (FK to `users.user_id`)
  - `borrower_user_id`: `integer`
  - `title`: `string`
  - `accession_number`: `string`
  - `fee_type`: `string` (`"OVERDUE"` | `"DAMAGE"` | `"LOST"` | `"MANUAL_ADJUSTMENT"`)
  - `status`: `string` (`"OPEN"` | `"PARTIALLY_PAID"` | `"PAID"` | `"WAIVED"` | `"CANCELLED"`)
  - `currency`: `string` (`"INR"`)
  - `original_amount_minor`: `integer` (Base assessment in minor units, e.g. 500 = ₹5.00)
  - `current_amount_minor`: `integer` (Post-adjustment amount)
  - `paid_amount_minor`: `integer` (Cumulative recorded cash payments)
  - `balance_minor`: `integer` (Outstanding balance: `current - paid`)
  - `policy_id`: `string` (FK to `institution_fee_policies`)
  - `policy_snapshot`: `object`
  - `calculation`: `object` (Detailed calculation provenance: days, grace, rate, stop date)
  - `source_event`: `string` (`"PHYSICAL_RETURN_CONFIRMED"`)
  - `created_at`: `datetime`
  - `updated_at`: `datetime`
- **Indexes:**
  - `{ "fee_id": 1 }` (Unique)
  - `{ "library_id": 1, "user_id": 1, "status": 1 }`
  - `{ "library_id": 1, "loan_id": 1, "fee_type": 1 }` (Unique)
  - `{ "library_id": 1, "status": 1, "created_at": -1 }`

---

### 2.16 `institution_fee_ledger`
- **Purpose:** Append-only immutable financial transaction log for desk audits.
- **Fields:**
  - `entry_id`: `string` (UUID v5, PK)
  - `fee_id`: `string` (UUID v5, FK to `institution_fees`)
  - `library_id`: `string` (UUID v4, FK)
  - `entry_type`: `string` (`"CHARGE"` | `"CREDIT"` | `"WAIVER"` | `"PAYMENT_RECORD"`)
  - `amount_minor`: `integer` (Integer minor unit transaction delta)
  - `actor_user_id`: `integer` (Staff or system user ID who initiated transaction)
  - `reason`: `string` (Audit reason text)
  - `created_at`: `datetime`
- **Indexes:**
  - `{ "entry_id": 1 }` (Unique)
  - `{ "library_id": 1, "fee_id": 1, "created_at": 1 }`

---

### 2.17 `institution_fee_policies`
- **Purpose:** Versioned immutable fee schedules and calculation parameters.
- **Fields:**
  - `policy_id`: `string` (UUID, PK)
  - `library_id`: `string` (UUID v4, FK)
  - `version`: `integer` (Monotonic version counter)
  - `effective_from`: `datetime`
  - `overdue_enabled`: `boolean`
  - `rate_minor_per_day`: `integer` (e.g. 500 = ₹5.00/day)
  - `currency`: `string` (`"INR"`)
  - `minor_units_per_major`: `integer` (100)
  - `grace_days`: `integer` (e.g. 0)
  - `charge_stop_policy`: `string` (`"PHYSICAL_RECEIPT"` | `"FIRST_VALID_RETURN_REQUEST"`)
  - `day_boundary`: `string` (`"UTC_CALENDAR_DAY"`)
  - `created_by_user_id`: `integer`
  - `created_at`: `datetime`
  - `provenance`: `string`
- **Indexes:**
  - `{ "policy_id": 1 }` (Unique)
  - `{ "library_id": 1, "version": 1 }` (Unique)

---

### 2.18 `institution_lending_operations`
- **Purpose:** Write-ahead operation journal for durable two-phase commit transactions.
- **Fields:**
  - `operation_id`: `string` (UUID v4, PK)
  - `library_id`: `string` (UUID v4, FK)
  - `idempotency_key`: `string` (UUID v4 supplied by client)
  - `kind`: `string` (`"BORROW_REQUEST_CREATED"`, `"RETURN_CONFIRMED"`, etc.)
  - `payload`: `object` (Original request payload)
  - `effects`: `array[object]` (Target collection, selector, and update values)
  - `state`: `string` (`"PENDING"` | `"COMMITTED"` | `"RECOVERY_REQUIRED"`)
  - `result`: `object` (Committed response value)
  - `created_at`: `datetime`
  - `committed_at`: `datetime`
- **Indexes:**
  - `{ "operation_id": 1 }` (Unique)
  - `{ "library_id": 1, "idempotency_key": 1 }` (Unique)

---

### 2.19 `institution_library_assets`
- **Purpose:** Cataloged institutional digital documents (PDFs) uploaded by staff.
- **Fields:**
  - `asset_id`: `string` (UUID v4, PK)
  - `library_id`: `string` (UUID v4, FK)
  - `library_book_id`: `string` (Optional UUID FK linking asset to a library book)
  - `title`: `string`
  - `original_filename`: `string`
  - `file_bytes`: `integer`
  - `sha256`: `string` (Cryptographic file digest)
  - `visibility`: `string` (`"STAFF_ONLY"` | `"PATRON_AND_STAFF"`)
  - `status`: `string` (`"PROCESSING"` | `"READY"` | `"FAILED"`)
  - `error_message`: `string` (Optional failure detail)
  - `pages`: `integer` (Extracted page count)
  - `chunk_count`: `integer` (Extracted text chunk count)
  - `created_by_user_id`: `integer`
  - `created_at`: `datetime`
  - `updated_at`: `datetime`
- **Indexes:**
  - `{ "asset_id": 1 }` (Unique)
  - `{ "library_id": 1, "visibility": 1, "status": 1 }`
  - `{ "library_id": 1, "library_book_id": 1 }`

---

### 2.20 `institution_asset_chunks`
- **Purpose:** Text chunks and token counts extracted from institutional digital assets for RAG retrieval.
- **Fields:**
  - `chunk_id`: `string` (Deterministic hash ID, PK)
  - `asset_id`: `string` (UUID v4, FK)
  - `library_id`: `string` (UUID v4, FK)
  - `page`: `integer` (1-indexed page number)
  - `chunk_index`: `integer` (0-indexed sequence)
  - `text`: `string` (Raw chunk text)
  - `token_count`: `integer`
  - `created_at`: `datetime`
- **Indexes:**
  - `{ "chunk_id": 1 }` (Unique)
  - `{ "library_id": 1, "asset_id": 1, "chunk_index": 1 }`

---

### 2.21 `institution_asset_artifacts`
- **Purpose:** Study intelligence tools synthesized from institutional digital assets.
- **Fields:**
  - `artifact_id`: `string` (UUID v4, PK)
  - `asset_id`: `string` (UUID v4, FK)
  - `library_id`: `string` (UUID v4, FK)
  - `artifact_type`: `string` (`"key-concepts"` | `"summary"` | `"flashcards"` | `"mindmap"` | `"quiz"`)
  - `payload`: `object` (Structured JSON representation of synthesized artifact)
  - `created_at`: `datetime`
- **Indexes:**
  - `{ "artifact_id": 1 }` (Unique)
  - `{ "library_id": 1, "asset_id": 1, "artifact_type": 1 }`

---

### 2.22 `institution_events`
- **Purpose:** Tenant library event schedule, workshops, book clubs, and announcements.
- **Fields:**
  - `event_id`: `string` (UUID v4, PK)
  - `library_id`: `string` (UUID v4, FK)
  - `title`: `string`
  - `description`: `string`
  - `event_type`: `string`
  - `start_time`: `datetime`
  - `end_time`: `datetime`
  - `location`: `string`
  - `status`: `string` (`"DRAFT"` | `"PUBLISHED"` | `"CANCELLED"` | `"ARCHIVED"`)
  - `created_by_user_id`: `integer`
  - `created_at`: `datetime`
  - `updated_at`: `datetime`
- **Indexes:**
  - `{ "event_id": 1 }` (Unique)
  - `{ "library_id": 1, "status": 1, "start_time": 1 }`

---

### 2.23 `institution_inventory_imports` & `institution_inventory_previews`
- **Purpose:** Asynchronous bulk CSV/XLSX catalogue import batch tracking and ephemeral preview staging.
- **Fields (`imports`):** `import_id` (UUID), `library_id` (UUID), `actor_user_id` (int), `filename`, `status`, `rows_total`, `rows_created`, `rows_updated`, `created_at`, `completed_at`.
- **Fields (`previews`):** `import_id` (UUID), `rows` (array), `expires_at` (TTL).
- **Indexes:**
  - `imports`: `{ "import_id": 1 }` (Unique), `{ "library_id": 1, "actor_user_id": 1, "created_at": -1 }`
  - `previews`: `{ "import_id": 1 }` (Unique), `{ "expires_at": 1 }` (TTL expireAfterSeconds: 0)

---

## 3. Platform & Global Collections Inventory

### 3.1 `users`
- **Purpose:** Core platform user identities, bcrypt credentials, email verification flags.
- **Fields:** `user_id` (int, PK), `name` (str), `email` (str, UK), `password_hash` (str bcrypt), `role` (`"PLATFORM_USER"` | `"READER_ROLE"` | `"GENERAL_USER"`), `is_email_verified` (bool), `is_active` (bool), `password_setup_required` (bool), `created_at` (datetime).
- **Indexes:** `{ "user_id": 1 }` (Unique), `{ "email": 1 }` (Unique).

### 3.2 `email_verifications`
- **Purpose:** Stores 6-digit OTP codes for email verification with rate-limiting attempt counters and 10-minute TTL.
- **Fields:** `user_id` (int), `otp_hash` (str bcrypt), `expires_at` (datetime), `attempts` (int), `created_at` (datetime).
- **Indexes:** `{ "user_id": 1 }`, `{ "expires_at": 1 }`.

### 3.3 `platform_role_assignments`
- **Purpose:** Explicit administrative assignments required for global platform control.
- **Fields:** `user_id` (int), `role` (`"PLATFORM_ADMIN"`), `status` (`"ACTIVE"`), `approval_ref` (str), `approved_by` (str), `approved_at` (datetime), `expires_at` (datetime).
- **Indexes:** `{ "user_id": 1, "role": 1 }` (Unique).

### 3.4 `platform_audit`
- **Purpose:** Global administrative lifecycle audit records (e.g., library suspension, restoration).
- **Indexes:** `{ "event_id": 1 }` (Unique), `{ "library_id": 1, "actor_user_id": 1, "idempotency_key": 1 }` (Unique), `{ "library_id": 1, "created_at": -1, "event_id": 1 }`.

### 3.5 `books` (Global 5M Catalogue)
- **Purpose:** Authoritative global OpenLibrary catalogue of 5,000,000 books referenced by FAISS vector index and semantic search.
- **Fields:** `book_id` (int), `work_id` (str, e.g. `"OL12345W"`, PK), `title` (str), `authors` (str), `subjects` (str), `description` (str), `average_rating` (float), `rating_count` (int), `reading_log_count` (int), `shelf_location` (str), `total_copies` (int), `available_copies` (int), `created_at` (datetime).
- **Indexes:** `{ "work_id": 1 }` (Unique), `{ "book_id": 1 }` (Unique), `{ "title": 1 }`.

### 3.6 Auxiliary Collections
- `book_categories`: Cached precomputed categories and counts for fast catalog discovery.
- `activity`: Append-only user activity log (`user_id`, `work_id`, `event_type`, `created_at`). Indexes: `{ "user_id": 1, "created_at": -1 }`, `{ "work_id": 1, "created_at": -1 }`.
- `notifications`: User notifications inbox. Indexes: `{ "user_id": 1, "created_at": -1 }`, `{ "status": 1 }`.
- `reading_list`: User bookmarks and personal reading lists. Indexes: `{ "user_id": 1, "work_id": 1 }` (Unique).
- `search_history`: User natural-language search query history. Indexes: `{ "user_id": 1, "created_at": -1 }`.
- `counters`: Integer autoincrement sequence counters for numeric IDs (`user_id`, `book_id`).
- `borrow_locks`: Ephemeral leases used during legacy borrow duplicate checking.
- `recommendation_feedbacks`: Implicit and explicit feedback logging for recommendation reranking.
- `events` & `event_user_state`: Global library events and user RSVP/attendance state.
- `issues`, `reservations`, `fines`: Legacy global circulation records retained for backward compatibility.

---

## 4. Denormalization & Join Patterns

| Join Type | Implementation Pattern | Target Collections | Rationale |
| :--- | :--- | :--- | :--- |
| **Directory Lookup** | MongoDB `$lookup` aggregation | `institution_libraries` $\rightarrow$ `users` | Single-query resolution of library owner details (`name`, `email`) in `platform_library_service.py:38-42`. |
| **Catalogue Hydration** | MongoDB `$lookup` aggregation | `institution_library_books` $\rightarrow$ `institution_holdings`, `institution_library_assets` | Hydrates physical stock, shelf location, and online digital assets in `library_catalogue_experience.py:250-257`. |
| **Candidate In-Memory Join** | Multi-key batch `find({ $in: ids })` | HNSW Candidate IDs $\rightarrow$ `books` | Search engine fetches 50 top vector candidate IDs from FAISS, then queries `books` via a single indexed `$in` batch query (`search/catalogue.py:49-58`). |
| **Availability Aggregation** | Live count queries under lock | `institution_holdings`, `institution_copies`, `institution_lending_requests`, `institution_loans` | Calculates live availability without stale denormalized counters that risk race conditions under high concurrency. |
| **Audit Metadata** | Embedded JSON snapshot | `institution_loans`, `institution_fees` | Fee policy snapshot and book title/accession number are denormalized into loan and fee documents to ensure historical integrity even if book titles or policies are modified later. |
