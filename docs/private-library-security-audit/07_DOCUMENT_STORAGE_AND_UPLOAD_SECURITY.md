# 07 — PRIVATE DOCUMENT STORAGE & UPLOAD SECURITY

## 1. Document Storage Architecture & Hierarchy

LuminaR segregates uploaded files into two independent storage tiers to prevent operational cross-contamination:

```
                            STORAGE SUB-TREE ARCHITECTURE
                            
   d:\SDC\LibraryLLM\
   ├── local-data/
   │   ├── library-assets/                         <-- INSTITUTIONAL DIGITAL ASSETS
   │   │   └── {library_id}/                       <-- Canonical UUID
   │   │       └── {asset_id}/                     <-- Canonical UUID
   │   │           ├── source.pdf (or .txt, .docx) <-- Validated source document
   │   │           └── generation/
   │   │               └── {generation_id}/        <-- Processed RAG & Tool Artifacts
   │   │                   ├── manifest.json       <-- Checksums & metadata
   │   │                   ├── extracted.json      <-- Extracted text per page
   │   │                   ├── chunks.json         <-- Chunked text & IDs
   │   │                   ├── vectors.npy         <-- NumPy raw embeddings
   │   │                   ├── runtime.faiss       <-- Serialized FAISS index
   │   │                   └── knowledge/          <-- Cached Knowledge Tools JSON
   │   │
   │   └── library-intelligence/                   <-- TENANT SEARCH & KG ARTIFACTS
   │       └── {library_id}/
   │           ├── datasets/{generation_id}/records.json
   │           ├── search/{generation_id}/index.faiss
   │           └── kg/{generation_id}/graph.json
   │
   └── rag/
       └── private_documents/                      <-- PERSONAL SESSION UPLOADS
           ├── registry.sqlite                     <-- Local SQLite session ledger
           └── {doc_id}/                           <-- Session document directory
```

---

## 2. Path Traversal & Filesystem Sanitization

A common vulnerability in web platforms is **Path Traversal (CWE-22)**, where malicious filenames (e.g., `../../../../etc/passwd`) or manipulated IDs escape the upload sandbox.

### 2.1 Multi-Layered Traversal Defenses

Code references: [backend/services/library_asset_service.py:L48-88](file:///d:/SDC/LibraryLLM/backend/services/library_asset_service.py#L48-L88) and [rag/services/library_asset_pipeline.py:L68-74](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L68-L74):

1. **Strict Canonical UUID Enforcement (`canonical_id`)**:
   ```python
   def canonical_id(value):
       try:
           return str(UUID(str(value)))
       except (ValueError, TypeError, AttributeError):
           raise HTTPException(404, 'Library resource not found.')
   ```
   Every path component (`library_id`, `asset_id`, `generation_id`) must parse successfully as a RFC 4122 UUID. Any path attempting string manipulation (`..`, `/`, `\`) fails immediately with HTTP 404.

2. **Filesystem Boundary Validation (`asset_directory`)**:
   ```python
   def asset_directory(library_id, asset_id):
       root = storage_root()
       path = root / canonical_id(library_id) / canonical_id(asset_id)
       resolved = path.resolve()
       if resolved != path or root not in resolved.parents:
           raise HTTPException(404, 'Library resource not found.')
       return path
   ```
   Using Python's `pathlib.Path.resolve()`, the system resolves symlinks and junctions. If the resolved path does not contain `root` in its parent hierarchy, access is denied.

3. **`safe_child` Directory Fencing**:
   ```python
   def safe_child(directory, *parts):
       directory = Path(directory)
       target = directory.joinpath(*parts)
       if target.resolve() != target or directory not in target.parents:
           raise HTTPException(404, 'Document not found.')
       return target
   ```
   No file read or write operation is permitted to traverse outside its specific generation directory.

---

## 3. Upload Validation & Malware / Denial-of-Service Defenses

The upload pipeline validates every submitted file against stringent technical standards before saving to disk.

### 3.1 Upload Security Checklist

| Check | Implemented Standard | Code Location | Security Purpose |
|---|---|---|---|
| **Max Payload Size** | 64 MiB (`MAX_FILE_BYTES = 67,108,864`) | [library_asset_upload_limit.py](file:///d:/SDC/LibraryLLM/backend/services/library_asset_upload_limit.py) | Prevents storage exhaustion and memory exhaustion during OCR. Enforced in ASGI middleware before reading file body. |
| **Filename Sanitization** | NFC normalization, URL-decoding, length $\le 255$, prohibited characters (`/ \ : \x00`), prohibited leading dots | [library_asset_service.py:L178-186](file:///d:/SDC/LibraryLLM/backend/services/library_asset_service.py#L178-L186) | Prevents directory traversal, hidden dotfiles, and null-byte injection. |
| **File Extension Whitelist** | Exactly `.pdf`, `.txt`, `.docx` | [library_asset_service.py:L183](file:///d:/SDC/LibraryLLM/backend/services/library_asset_service.py#L183) | Executable files (`.exe`, `.sh`, `.bat`, `.py`) and legacy insecure formats (`.doc`) are rejected. |
| **PDF Magic Byte Check** | File stream must start with `b'%PDF-'` | [library_asset_service.py:L194](file:///d:/SDC/LibraryLLM/backend/services/library_asset_service.py#L194) | Prevents polyglot file uploads (e.g., HTML/JS disguised as PDF). |
| **Encryption Check** | Document must not be password-protected | [library_asset_service.py:L198](file:///d:/SDC/LibraryLLM/backend/services/library_asset_service.py#L198) | Blocks encrypted PDFs that cannot be verified or indexed. |
| **Page Count Limit** | Exactly $1 \le \text{page\_count} \le 10,000$ | [library_asset_service.py:L198](file:///d:/SDC/LibraryLLM/backend/services/library_asset_service.py#L198) | Prevents decompression bombs / PDF page bombs designed to crash PyMuPDF. |
| **Idempotent Retries** | Requires `X-Luminar-Upload: <UUID>` header | [library_asset_service.py:L38](file:///d:/SDC/LibraryLLM/backend/services/library_asset_service.py#L38) | Duplicate HTTP POST requests replay previous receipt; compound unique index on `(library_id, uploaded_by_user_id, upload_id)`. |

---

## 4. Download and Preview Security

A common failure in multi-tenant document systems is exposing uploads via an unauthenticated static file server (e.g., Nginx `/uploads/` directory).

### 4.1 No Static Directory Exposure
- **Verified Fact**: `local-data/library-assets/` is **NEVER** mounted as a static directory in FastAPI or web server configs.
- Every single file download or preview passes through an authenticated FastAPI route:
  - `GET /libraries/{library_id}/assets/{asset_id}/file` ([backend/routes/library_assets.py:L66-73](file:///d:/SDC/LibraryLLM/backend/routes/library_assets.py#L66-L73)).
  - `GET /libraries/{library_id}/assets/{asset_id}/preview/pages/{page_number}` ([backend/routes/library_assets.py:L92-100](file:///d:/SDC/LibraryLLM/backend/routes/library_assets.py#L92-L100)).

### 4.2 Security Headers on File Responses
When a document is served, the backend attaches restrictive HTTP security headers:
```python
FileResponse(
    service.source_path(row),
    media_type=row.get('media_type', 'application/pdf'),
    filename=row['original_filename'],
    content_disposition_type='attachment' if download else 'inline',
    headers={
        'Cache-Control': 'private, no-store',
        'X-Content-Type-Options': 'nosniff',
        'Content-Security-Policy': "sandbox; default-src 'none'"
    }
)
```
1. `Cache-Control: private, no-store`: Forbids browser caching and intermediate proxy caching of sensitive institutional files.
2. `X-Content-Type-Options: nosniff`: Prevents MIME-confusion attacks in web browsers.
3. `Content-Security-Policy: sandbox; default-src 'none'`: If a malicious PDF contains embedded JavaScript or XFA forms, browser sandbox execution prevents the PDF from accessing cookies, local storage, or the surrounding web page.

### 4.3 Rate-Limited PDF Rasterization (`_preview_slots`)
To protect against CPU exhaustion attacks where an attacker requests 100 simultaneous high-DPI page renders:
- Code reference: [backend/routes/library_assets.py:L14, L100](file:///d:/SDC/LibraryLLM/backend/routes/library_assets.py#L14#L100):
  ```python
  _preview_slots = BoundedSemaphore(2)

  @router.get('/{asset_id}/preview/pages/{page_number}')
  def pdf_page(...):
      if not _preview_slots.acquire(blocking=False):
          raise HTTPException(429, 'Document preview is busy. Please retry shortly.')
  ```
- Non-blocking semaphore limits concurrent PDF rendering to **2 operations across the process**, shedding excess load with HTTP 429 rather than degrading API performance.

---

## 5. Document Deletion & Lifecycle Management

### 5.1 Deletion Protocol
When staff deletes an asset (`DELETE /libraries/{library_id}/assets/{asset_id}`):
1. **Soft-Delete in Database**: Updates MongoDB record status to `'DELETING'`, then `'DELETED'` with `deleted_at` and `deleted_by_user_id` ([library_asset_service.py:L260-275](file:///d:/SDC/LibraryLLM/backend/services/library_asset_service.py#L260-L275)).
2. **Immediate Visibility Invalidation**: Any subsequent API request querying the document immediately encounters `if row['status'] in {'DELETING', 'DELETED'}: raise HTTPException(404)`.
3. **Physical File Removal**: The physical asset directory `local-data/library-assets/{library_id}/{asset_id}/` is unlinked and removed from disk using `shutil.rmtree()`.
4. **Audit Trail Preservation**: An immutable record of the deletion is appended to `institution_audit` with `event: 'ASSET_DELETED'`, recording who deleted the file and when.
