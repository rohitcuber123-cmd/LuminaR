# 10_MULTI_LIBRARY_ARCHITECTURE.md: Architecture of Institutional Multi-Library Tenancy

## Executive Summary

LuminaR implements a dual-layer institutional tenancy architecture. Alongside its historical global OpenLibrary catalogue, LuminaR contains an **Institution Multi-Library Subsystem** (implemented across `backend/routes/institutions.py`, `backend/routes/library_*.py`, and `backend/services/institution_*.py`). 

This architecture supports physical libraries, private corporate collections, university libraries, and consortia. Each institution operates as an isolated tenant governed by UUID identifiers, role-based access control, cryptographic access codes, and scoped inventory collections in MongoDB.

---

## 1. Concrete Institutional Library Entity Representation

In the MongoDB database (`MONGO_DB_NAME`, defaulting to `luminar_library`), institutional data is isolated in dedicated collections prefixed with `institution_`:

### 1.1 The Library Entity (`institution_libraries`)
* **Collection:** `institution_libraries` ([backend/services/institution_service.py:21-23](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L21-L23))
* **Primary Key (`library_id`):** Canonical UUID v4 string (e.g., `"a4f932bc-9d0b-48ec-9257-ec79ebcb803a"`).
* **Core Attributes:**
  * `name`: Formal display name of the library (1–150 characters).
  * `slug` / `slug_normalized`: Unique URL slug (e.g., `"oxford-science-lib"`), constrained by a unique database index.
  * `description`: Institutional synopsis.
  * `library_type`: Categorical enumeration: `PHYSICAL`, `PRIVATE_COLLECTION`, `INSTITUTIONAL`, or `CONSORTIUM`.
  * `access_mode`: Admission control mode: `PUBLIC` (open join) or `PRIVATE_CODE` (requires shared passkey).
  * `owner_user_id`: Integer reference to the `users` account ID of the registered owner.
  * `status`: Operational state lifecycle:
    * `PROVISIONING`: Intermediate state during creation transaction; hidden from discovery.
    * `ACTIVE`: Fully operational.
    * `SUSPENDED`: Temporarily locked by administration.
    * `REMOVED`: Soft-deleted / retired.
  * `contact_email`, `phone`, `address` (`street`, `city`, `region`, `postal_code`, `country`).
  * `created_at`, `updated_at`: UTC timestamps.

### 1.2 Access & Security Secrets (`institution_security`)
* **Collection:** `institution_security`
* **Fields:** `library_id`, `access_code_hash` (Argon2id/PBKDF2 hash of the private access passkey), `access_code_changed_at`, `access_code_changed_by`.

### 1.3 Memberships & Staff (`institution_memberships`)
* **Collection:** `institution_memberships` ([backend/services/institution_service.py:23](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L23))
* **Fields:**
  * `membership_id`: UUID v4 string.
  * `library_id`: Target library foreign key.
  * `user_id`: Canonical numeric account ID.
  * `role`: Hierarchical role enumeration:
    * `ADMIN`: Library owner or delegated administrator (full catalog, policy, and staff control).
    * `LIBRARIAN`: Circulation and cataloging staff (inventory import, loan review, asset management).
    * `GENERAL_USER`: Standard library patron (borrowing, reservations, digital document AI).
  * `status`: `ACTIVE`, `SUSPENDED`, or `REMOVED`.
  * `joined_at`, `created_at`, `updated_at`.
  * `grant_invitation_id`: Foreign key proving invitation redemption if added via staff invite.

---

## 2. Institutional Subsystem Inventory

| Subsystem | Storage Collection | Key Tenant Fields | Scoped Responsibility |
| :--- | :--- | :--- | :--- |
| **Libraries** | `institution_libraries` | `library_id`, `owner_user_id`, `slug` | Institution registration, profile, access policy |
| **Memberships** | `institution_memberships` | `membership_id`, `library_id`, `user_id`, `role` | Patron and staff role management |
| **Invitations** | `institution_invitations` | `invitation_id`, `library_id`, `email_normalized` | Staff invitation lifecycle |
| **Catalogue Books** | `institution_library_books` | `library_book_id`, `library_id`, `accession_number` | Local title metadata, ISBNs, OpenLibrary links |
| **Holdings** | `institution_holdings` | `holding_id`, `library_id`, `library_book_id` | Aggregated copy quantities, shelf locations |
| **Copies** | `institution_copies` | `copy_id`, `library_id`, `holding_id`, `barcode` | Physical barcode item tracking, wear condition |
| **Circulation Loans**| `institution_loans` | `loan_id`, `library_id`, `library_book_id`, `user_id`| Active checkouts, due dates, return journals |
| **Lending Requests** | `institution_lending_requests`| `lending_request_id`, `library_id`, `user_id` | Patron borrow approval requests |
| **Reservations** | `institution_reservations` | `reservation_id`, `library_id`, `queue_sequence` | Waitlist queue management |
| **Digital Assets** | `institution_library_assets` | `asset_id`, `library_id`, `library_book_id` | Uploaded institutional PDFs, digital docs |
| **Events** | `institution_events` | `event_id`, `library_id`, `status` | Tenant workshops, lectures, announcements |
| **Analytics** | Computed on-demand | Scoped by `library_id` query | Circulation velocity, popularity, active patrons |

---

## 3. End-to-End Institutional Lifecycle Trace

```mermaid
sequenceDiagram
    autonumber
    participant Admin as Institution Owner
    participant API as Institutions API (/libraries)
    participant DB as MongoDB (institution_*)
    participant Importer as Inventory Importer
    participant Search as Global Search / HNSW
    participant Patron as Library Patron

    Note over Admin, API: Stage 1: Library Registration
    Admin->>API: POST /libraries/register (name, slug, access_mode, access_code)
    API->>DB: INSERT institution_libraries (status='PROVISIONING')
    API->>DB: INSERT institution_security (access_code_hash)
    API->>DB: INSERT institution_memberships (user=Owner, role='ADMIN')
    API->>DB: UPDATE institution_libraries SET status='ACTIVE'
    API-->>Admin: 201 Created (library_id: UUID)

    Note over Admin, Importer: Stage 2: Staff Invitation
    Admin->>API: POST /libraries/{id}/invitations (email, role='LIBRARIAN')
    API->>DB: INSERT institution_invitations
    API-->>Admin: 201 Invitation Created

    Note over Admin, Importer: Stage 3: Dataset Ingestion
    Admin->>API: POST /libraries/{id}/inventory/imports/preview (file: CSV/XLSX)
    API->>Importer: parse_file() + validated_row()
    Importer->>DB: INSERT institution_inventory_previews
    Importer-->>Admin: Preview Rows + Duplicate Analysis
    Admin->>API: POST /libraries/{id}/inventory/imports/{import_id}/apply
    API->>Importer: apply() under library_mutation lock
    Importer->>DB: INSERT institution_library_books (with library_id)
    Importer->>DB: INSERT institution_holdings & institution_copies
    Importer-->>Admin: Import Summary (Created / Skipped / Invalid)

    Note over Search: Stage 4: Indexing & Search Sync
    Importer->>Search: Local books remain in Mongo; global sync outbox notified if linked to global_work_id

    Note over Patron, API: Stage 5: Patron Discovery & Interaction
    Patron->>API: GET /libraries (Discover public & private libraries)
    Patron->>API: POST /libraries/{id}/join (access_code if private)
    API->>DB: INSERT institution_memberships (user=Patron, role='GENERAL_USER')
    Patron->>API: GET /libraries/{id}/catalogue/home
    API->>DB: Read library_books, featured rails, new arrivals
    API-->>Patron: Hydrated Scoped Catalogue
```

---

## 4. Patron Membership & Multi-Library Capabilities

An audit of `LibraryLLM/backend/services/institution_service.py` reveals the following architectural capabilities regarding membership:

1. **Multiple Library Memberships:**
   * **Allowed.** Users are not locked into a single library.
   * `my_libraries(current_user)` queries:
     ```python
     collection('memberships').find({'user_id': user_id, 'status': 'ACTIVE'})
     ```
   * A single user account can simultaneously hold `ADMIN` at Library A, `LIBRARIAN` at Library B, and `GENERAL_USER` at Library C.

2. **Active Library Switching:**
   * Handled statelessly via API routing.
   * There is no persistent "active_library" column on the `users` table. The client specifies the target tenant context explicitly via URL path: `/libraries/{library_id}/...`.
   * The backend resolves tenancy and verifies active membership on each request via dependency injection (`require_library_membership(library_id, current_user)`).

3. **Browsing Unjoined Libraries:**
   * **Public Libraries (`access_mode: 'PUBLIC'`):** Unjoined users can view institutional profiles (`GET /libraries/{library_id}`) and browse the discovery directory (`GET /libraries`). To view catalogue holdings, the patron must join (`POST /libraries/{id}/join`), which completes instantly without credentials.
   * **Private Libraries (`access_mode: 'PRIVATE_CODE'`):** Unjoined users see only high-level directory metadata. Accessing catalogue endpoints (`/catalogue/home`, `/catalogue/books`, `/lending/*`) without an active membership triggers `require_library_membership()`, which immediately raises **HTTP 404** ("Library resource not found"), intentionally concealing tenant data from outsiders.
