# Chunking Strategy & Metadata Preservation Evidence

> **Audit Context**: LuminaR Research Evidence Audit — Part 6  
> **Source Files Verified**:
> - `rag/services/document_service.py` (Lines 43–125, 340–393)
> - `rag/services/local_document_cache.py` (Lines 23–45, 117–190)
> - `rag/services/library_asset_pipeline.py` (Lines 121–135)
> - `rag/services/private_documents.py` (Lines 139–145)

---

## 1. Exact Implementation & Parameters

Chunking in LuminaR is implemented in `rag/services/document_service.py`:

```python
# rag/services/document_service.py:43-44
CHUNK_SIZE = 3000
CHUNK_OVERLAP = 400

# rag/services/document_service.py:85-124
def chunk_text(text: str, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    if not text:
        return []
    chunks = []
    start = 0
    text_length = len(text)
    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_length:
            break
        start = end - overlap
    return chunks
```

### Parameter Specification
| Parameter | Exact Value | Verification Reference | Notes |
| :--- | :--- | :--- | :--- |
| **Function Name** | `chunk_text()` | `rag/services/document_service.py:85` | Pure sliding-window character slicer |
| **Caller Method** | `create_chunks()` | `rag/services/document_service.py:343` | Iterates over extracted pages |
| **Chunk Size** | `3000` | `document_service.py:43` | 3,000 raw unicode characters |
| **Unit** | **Characters** | `len(text)` in `document_service.py:99` | **Not words, not tokens** |
| **Overlap** | `400` | `document_service.py:44` | 400 characters sliding window |
| **Official Chunker ID** | `'page-character-3000-overlap400-v1'` | `local_document_cache.py:125, 174` | Manifest version identifier |
| **Max Chunks per Doc** | `20,000` | `MAX_CHUNKS = 20000` in `local_document_cache.py:23` | Hard upper bound per document |

---

## 2. Structural & Boundary Handling

### A. Page Boundary Isolation
Chunking in LuminaR is strictly **page-scoped**:
```python
# rag/services/document_service.py:354-368
for page in pages:
    page_text = page["text"]
    if not page_text:
        continue
    page_chunks = chunk_text(page_text)
```
- **Chunks NEVER cross page boundaries**: Each page's text is chunked independently. If a sentence spans across page 3 and page 4, page 3's final chunk terminates at the end of page 3, and page 4's first chunk starts at the top of page 4.
- **Short Pages**: A page with only 250 characters produces a single 250-character chunk. It is not merged with adjacent pages.

### B. Section and Heading Handling
- In `create_chunks()`, raw chunks do not independently detect headings; they inherit the page number.
- In `rag/services/document_knowledge.py:118-195` (`source_units()`), structural headings are identified via regex (`heading()`, lines 60–67) and bullet lists (`BULLET`, line 21). When knowledge units are generated, chunks are contextualized with their `heading`, `section`, and `chapter` metadata.
- In `rag/services/library_asset_pipeline.py:125-135`, character offsets within the source page are rigorously computed:
```python
offsets = {}
for chunk in chunks:
    page = pages[chunk['page'] - 1]
    start = page['text'].find(chunk['text'], offsets.get(chunk['page'], 0))
    if start < 0:
        raise HTTPException(409, 'CHUNK_PROVENANCE_INVALID')
    offsets[chunk['page']] = max(start + len(chunk['text']) - 400, start + 1)
    chunk.update(
        library_id=job['library_id'],
        asset_id=job['asset_id'],
        generation_id=job['generation_id'],
        source_start=start,
        source_end=start + len(chunk['text']),
        extraction_method=page['extraction_method'],
    )
```

---

## 3. Metadata Preservation Matrix

| Metadata Field | Preserved in Chunks | Exact Representation / Source |
| :--- | :---: | :--- |
| **Chunk ID** | **Yes** | `f"{document_id}_{chunk_id:06d}"` (e.g., `doc_a1b2c3..._000001`) |
| **Document ID** | **Yes** | `document_id` (e.g., `doc_3f4e...` or `library:...:asset:...:generation:...`) |
| **Page Number** | **Yes** | `chunk['page']` (1-indexed integer) |
| **Filename** | **Yes** | `chunk['filename']` |
| **Text Content** | **Yes** | `chunk['text']` (3,000-char slice, stripped) |
| **Extraction Method**| **Yes** | `'NATIVE'` or `'OCR'` (propagated from page OCR result) |
| **Library ID** | **Yes** (Tenant) | `chunk['library_id']` (institutional pipeline only) |
| **Asset ID** | **Yes** (Tenant) | `chunk['asset_id']` (institutional pipeline only) |
| **Generation ID** | **Yes** (Tenant) | `chunk['generation_id']` (institutional pipeline only) |
| **Character Offsets**| **Yes** (Tenant) | `chunk['source_start']`, `chunk['source_end']` |
| **User ID** | **No** (by design) | Stripped from chunk files. User ownership is enforced in the outer SQLite/MongoDB table, preserving data privacy during cache export. |
| **Vector ID** | **Implicit** | Corresponds 1:1 with row index in `vectors.npy` and FAISS index ID (`0 ... N-1`). |

---

## 4. The Embedding Truncation Gap (Critical Bottleneck)

A critical architectural asymmetry exists between chunk length and embedding context length:

```
[ Chunk Text: 3,000 characters (~600 to 750 tokens) ]
|---------------------------------- 3000 chars ----------------------------------|
[ MiniLM Context Window: 256 tokens (~1,000 characters) ]
|------------ 256 tokens ------------| [ Truncated / Ignored by MiniLM: ~500 tokens ]
```

1. **Chunk Size**: 3,000 characters roughly corresponds to 550–750 English tokens.
2. **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` has a hard model limit of `max_seq_length = 256` tokens.
3. **Execution**: When `DocumentService.embed_chunks(chunks)` calls `self.model.encode(texts)`, the Hugging Face tokenizer truncates every chunk to 256 tokens.
4. **Consequence**: Only the first ~30–40% of each chunk is represented in the dense vector embeddings. If key information or terminology appears in the latter 1,800 characters of a 3,000-character chunk, it will not be retrievable via dense semantic vector search (though it remains intact in the full chunk text for verbatim context injection).
