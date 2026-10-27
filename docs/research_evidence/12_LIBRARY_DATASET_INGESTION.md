# 12_LIBRARY_DATASET_INGESTION.md: Institutional Dataset Ingestion Pipeline

## Executive Summary

LuminaR provides an automated, two-phase dataset ingestion pipeline enabling librarians and administrators to upload, preview, validate, deduplicate, and commit physical and digital library inventories. The ingestion service is implemented in `LibraryLLM/backend/services/library_inventory_import.py` and exposed via endpoints in `LibraryLLM/backend/routes/library_inventory.py`.

---

## 1. End-to-End Ingestion Trace

```mermaid
flowchart TD
    Staff([Admin / Librarian]) -->|Upload File| UploadEP["POST /libraries/{id}/inventory/imports/preview"]
    UploadEP --> AuthCheck{"require_library_staff()"}
    AuthCheck -->|Forbidden| Err403["HTTP 403 / 404"]
    AuthCheck -->|Authorized| ParseFile["parse_file()<br>Format & Size Validation"]

    subgraph Phase 1: Parsing & Validation
        ParseFile --> FormatCheck{"CSV or XLSX?"}
        FormatCheck -->|No| Err422["HTTP 422: Format Unsupported"]
        FormatCheck -->|Yes| RowCheck{"Rows <= 2,000<br>Bytes <= 5 MiB<br>Cols <= 40"}
        RowCheck -->|Exceeded| Err413["HTTP 413: Payload Too Large"]
        RowCheck -->|Valid| HeaderNormalize["Normalize Headers against ALIASES"]
        HeaderNormalize --> ForbiddenCheck{"Contains Forbidden Cols?<br>(library_id, status, etc.)"}
        ForbiddenCheck -->|Yes| ErrForbidden["HTTP 422: Identity Columns Forbidden"]
        ForbiddenCheck -->|No| RowValidation["validated_row()<br>Pydantic BookCreate Validation"]
    end

    subgraph Phase 2: Deduplication & Global Linking
        RowValidation --> GlobalMatch["isbn_candidates()<br>Check Global OpenLibrary Match"]
        GlobalMatch --> LocalMatch["duplicate()<br>Check Tenant Existing Holdings"]
        LocalMatch --> Classify["Classify Rows:<br>• NEW_LOCAL<br>• GLOBAL_MATCH<br>• EXISTING_HOLDING<br>• POSSIBLE_DUPLICATE<br>• INVALID"]
        Classify --> StorePreview["Store Job in institution_inventory_previews<br>Expires in 1 Hour"]
    end

    StorePreview --> ReturnPreview["Return Preview JSON to Staff Client"]

    ReturnPreview --> StaffReview([Staff Reviews Preview & Selects Policy])
    StaffReview -->|Confirm Apply| ApplyEP["POST /libraries/{id}/inventory/imports/{import_id}/apply"]

    subgraph Phase 3: Transactional Persistence
        ApplyEP --> MutexLock["with library_mutation(library_id):<br>Acquire Process File Lock"]
        MutexLock --> PolicyEval{"existing_policy:<br>'skip' or 'increase_quantity'"}
        PolicyEval --> InsertBooks["insert_locked():<br>• Create UUID library_book_id<br>• Generate Accession Sequence<br>• Insert institution_library_books"]
        InsertBooks --> InsertHoldings["Create institution_holdings<br>(total_copies, shelf_location)"]
        InsertHoldings --> InsertCopies["Create institution_copies<br>(barcodes, condition)"]
        InsertCopies --> AuditLog["audit(INVENTORY_IMPORT_COMPLETED)"]
        AuditLog --> UpdateJob["Update institution_inventory_imports (COMPLETED)"]
    end

    UpdateJob --> ReadyCatalogue([Catalogue Ready in /libraries/{id}/catalogue/books])
```

---

## 2. Ingestion Format & Volume Specifications

* **Supported Formats:**
  * **CSV:** Standard comma-separated values. Decoded with UTF-8 or `utf-8-sig` (handling Excel Byte Order Marks). Strict parsing via Python `csv.reader`.
  * **XLSX:** Microsoft Excel OpenXML format. Loaded via `openpyxl.load_workbook(..., read_only=True, data_only=True)`. Enforces a zip-bomb decompression safety limit: uncompressed stream must not exceed 25 MiB.
  * **JSON / TSV / Parquet:** **NOT supported** in the inventory import endpoint. Submitting these formats returns HTTP 422 ("Only CSV and XLSX inventory files are supported").
* **Volume & Boundary Limits:**
  * Maximum file size: `MAX_BYTES = 5 * 1024 * 1024` (5.0 MiB).
  * Maximum rows: `MAX_ROWS = 2000` data rows per import batch.
  * Maximum header columns: `MAX_COLUMNS = 40` columns.
  * Preview validity window: Expires after 1 hour (`expires_at = now() + timedelta(hours=1)`).

---

## 3. Dataset Column Mapping & Header Aliases

The parser matches case-insensitive raw column names against a predefined dictionary of aliases ([backend/services/library_inventory_import.py:26-36](file:///d:/SDC/LibraryLLM/backend/services/library_inventory_import.py#L26-L36)):

### 3.1 Mandatory Columns (Minimum Required Set)
1. **Title:** Must match `title`, `book_title`, or `name`. (Must be non-empty string).
2. **Subjects / Genre:** Must match `subjects`, `subject`, `genre`, or `category`. (Must be non-empty string).

### 3.2 Optional Supported Metadata Columns

| Standard Target Field | Accepted Column Aliases in CSV / XLSX | Expected Type / Validation |
| :--- | :--- | :--- |
| `title` | `title`, `book_title`, `name` | String (max 250 chars) |
| `subjects` | `subjects`, `subject`, `genre`, `category` | Comma-separated or string list |
| `authors` | `author`, `authors` | Comma-separated or string list |
| `isbn` | `isbn` | Digits (validated length 10 or 13) |
| `isbn_10` | `isbn10`, `isbn_10` | 10-character ISBN |
| `isbn_13` | `isbn13`, `isbn_13` | 13-character ISBN |
| `global_work_id` | `work_id`, `global_work_id` | OpenLibrary work ID (e.g., `OL12345W`) |
| `publisher` | `publisher` | String |
| `publication_year`| `year`, `publication_year` | Integer (e.g. `2021`) |
| `edition` | `edition` | String |
| `language` | `language` | ISO language code / string |
| `description` | `description` | String (up to 4,000 chars per cell) |
| `copies` | `copies`, `quantity`, `total_copies` | Whole integer $\ge 0$ |
| `available_copies`| `available_copies` | Whole integer $\le \text{copies}$ |
| `shelf_location` | `shelf`, `shelf_location` | String (e.g., `"STACKS-4B"`) |
| `local_call_number`| `call_number`, `local_call_number` | Dewey / LOC string |
| `local_tags` | `tags`, `local_tags` | Comma-separated tags |
| `acquisition_note`| `acquisition_note` | String |
| `barcode` | `barcode` | Alphanumeric barcode string |

### 3.3 Explicitly Forbidden Columns
To prevent tenant spoofing, role escalation, or ID collisions, the following columns are banned in upload files:
```python
FORBIDDEN = {
    'library_id', 'canonical_library_id', 'library_book_id', 'holding_id', 
    'copy_id', 'accession_number', 'accession_sequence', 'created_by', 
    'created_by_user_id', 'updated_by_user_id', 'role', 'status'
}
```
Attempting to upload a CSV containing any of these columns returns **HTTP 422** ("Identity, tenant, role and accession columns are not allowed in normal inventory imports").

---

## 4. Deduplication Logic & Classification Rules

During the preview phase, each row is evaluated by `duplicate(repo, data)` ([backend/services/library_inventory_import.py:151-163](file:///d:/SDC/LibraryLLM/backend/services/library_inventory_import.py#L151-L163)):

1. **`EXISTING_HOLDING`:**
   * Trigger: The book matches an existing record in `institution_library_books` for this library by identical `global_work_id` or matching `isbn_10`/`isbn_13`.
   * Action: Depending on `existing_policy`:
     * If `'skip'`: Row is ignored during apply.
     * If `'increase_quantity'`: Existing holding's `total_copies` and `available_copies` are incremented.
2. **`GLOBAL_MATCH`:**
   * Trigger: Book has an ISBN or Work ID matching OpenLibrary's 5-million master catalog, but this library does not yet hold a copy.
   * Action: Imports record, linking `global_work_id` to inherit global ratings, cover art, and descriptions.
3. **`POSSIBLE_DUPLICATE`:**
   * Trigger: A title matches an existing holding when case-normalized, but lacks a definitive ISBN or Work ID link.
   * Action: Flags to librarian for review; creates a distinct local record unless linked.
4. **`NEW_LOCAL`:**
   * Trigger: A unique title with no local or global duplicate matches.
   * Action: Inserts a purely local book record.
5. **`INVALID`:**
   * Trigger: Missing required title/subject, non-integer copies, or corrupted encoding.

---

## 5. Vector Indexing & Catalogue Availability

* **Immediate Availability:** Immediately upon transaction commit, records are live in the local catalogue (`GET /libraries/{library_id}/catalogue/books`).
* **HNSW Vector Index Interaction:**
  * Books matching an OpenLibrary `global_work_id` are already present in the global 5-million vector HNSW index (`hnsw.index`).
  * Purely custom local books (`NEW_LOCAL` with no `global_work_id`) are indexed in MongoDB lexical search; they are **not dynamically embedded or added to the global FAISS HNSW graph**, because the static 9.04 GB HNSW index does not support real-time per-tenant vector partitioning.
