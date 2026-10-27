# End-to-End Source Provenance Evidence

> **Audit Context**: LuminaR Research Evidence Audit — Part 6  
> **Source Files Verified**:
> - `rag/services/document_knowledge.py` (Lines 405–550)
> - `rag/services/knowledge_algorithms.py` (Lines 25–30, 146–148)
> - `rag/services/knowledge_quiz.py` (Lines 120–130, 172–184)
> - `rag/services/knowledge_mcq.py` (Lines 35–48, 60–63)
> - `rag/services/knowledge_match.py` (Lines 57–75)
> - `rag/services/knowledge_cloze.py` (Lines 16–47)
> - `frontend/src/components/knowledge/SourceLink.tsx` (Lines 1–32)
> - `frontend/src/components/knowledge/KnowledgeTools.tsx` (Lines 104–118)

---

## 1. Provenance Architecture Overview

LuminaR implements **strict, end-to-end deterministic source grounding** across every generative and analytical interface. Every claim, concept, flashcard, quiz item, mind map node, and summary sentence is directly bound to its originating source text excerpt, chunk ID, page number, and document.

```
+-------------------------------------------------------------------------+
|                              ORIGINAL PDF                               |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                       PAGE (1-indexed, NATIVE/OCR)                      |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                  CHUNK (f"{doc_id}_{chunk_id:06d}")                     |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|              SOURCE UNIT (unit_id, exact verbatim slice)                |
+-------------------------------------------------------------------------+
                                     |
         +---------------------------+---------------------------+
         |                           |                           |
         v                           v                           v
+-------------------+       +-------------------+       +-------------------+
|  RAG Chat Answer  |       | Knowledge Artifact|       |   Quiz Evidence   |
|   (Chunk + Page)  |       |  (Card / MindMap) |       |  (Fact + Options) |
+-------------------+       +-------------------+       +-------------------+
```

---

## 2. Source Grounding Matrix by Feature

| Interaction Layer | Grounding Granularity | Metadata Fields Preserved | Active Code Verification |
| :--- | :--- | :--- | :--- |
| **RAG Answer $\to$ PDF** | Chunk & Page | `chunk_id`, `page`, `score`, `excerpt`, `filename` | `rag/services/interactive_pipeline.py:112`, `engine.py:285` |
| **Flashcard $\to$ Source** | Sentence & Chunk | `knowledgeItemId`, `sourceExcerpt`, `concept`, `sources: [{chunkId, page}]` | `rag/services/document_knowledge.py:482-495` |
| **Quiz $\to$ Source** | Fact & Choice Source | `sourceFactId`, `sourceExcerpt`, `pageStart`, `sources`, `optionSources` | `knowledge_mcq.py:35-47`, `knowledge_match.py:65-75` |
| **Mind Map $\to$ Source** | Node & Edge Source | `sourceChunkIds`, `sources: [{chunkId, page}]`, `pageStart` | `rag/services/document_knowledge.py:530-547` |
| **Summary $\to$ Source** | Sentence & Chunk | `knowledgeItemId`, `text`, `section`, `sources: [{chunkId, page}]` | `rag/services/document_knowledge.py:511-515` |

---

## 3. Deep Dive: Detailed Grounding Traces

### A. Answer $\to$ Chunk $\to$ Page $\to$ PDF
- When an interactive query is processed in `rag/services/interactive_pipeline.py`, retrieved chunks from FAISS are re-ranked.
- Each context chunk is passed with its metadata: `{chunk_id, document_id, filename, page, text}`.
- When Qwen generates an answer, the RAG API returns the exact citations:
  ```json
  "sources": [
    {
      "chunk_id": "doc_8f1a..._000014",
      "filename": "computer_networks.pdf",
      "page": 23,
      "score": 0.841,
      "text": "Sliding window protocol provides flow control by..."
    }
  ]
  ```
- Clicking any source in the UI opens the verbatim chunk viewer showing the exact page number and text slice.

### B. Flashcard $\to$ Source Chunk
In `rag/services/document_knowledge.py:465-498`:
```python
cards.append({
    'id': legacy.identifier('card', fact['id']),
    'type': card_type,
    'front': front,
    'back': back,
    'sourceExcerpt': fact['text'],
    'concept': concept['label'],
    'knowledgeItemId': fact['id'],
    **legacy.provenance_from_row(fact),
    'sources': fact['sources'],  # [{'chunkId': cid, 'page': p}, ...]
})
```
- A flashcard front/back cannot be generated without an underlying accepted fact row.
- The `sourceExcerpt` holds the unedited source sentence from the document.
- The `sources` array contains the exact `chunkId` and `page`.

### C. Quiz $\to$ Source Chunk (MCQ, Cloze, Matching)
LuminaR goes beyond basic quiz grounding by requiring **option-level provenance**:

1. **MCQ Grounding** (`knowledge_mcq.py:35-48`):
   - The stem and correct answer are bound to `sourceFactId` and `sourceExcerpt`.
   - **Crucial Feature**: Every single distractor option carries its own source grounding in `optionSources`:
     ```python
     'optionSources': {
         x['subjectText'] if identify else x['targetText']: r.source(x)
         for x in chosen
     }
     ```
     Users and graders can verify why every incorrect option is an actual concept mentioned elsewhere in the same document!

2. **Matching Grounding** (`knowledge_match.py:57-75`):
   - Every left item (`Column A`) carries `relationId`, `sourceFactId`, and `sourceExcerpt`.
   - The overall matching question block carries:
     ```python
     'sourceExcerpt': '\n'.join(x['sourceExcerpt'] for x in selected),
     'sourceChunkIds': sorted({c for x in selected for c in x['sourceChunkIds']}),
     'sources': [{'chunkId': c, 'page': x.get('pageStart')} for x in selected for c in x['sourceChunkIds']]
     ```

3. **Fill in the Blanks Grounding** (`knowledge_cloze.py:27-47`):
   - Deletions are mapped strictly to underlying `evidenceUnitIds` and `sourceChunkIds`.
   - If a source unit was extracted via OCR and exhibits corrupted characters (e.g. digit-letter merges), the cloze question is strictly rejected (`knowledge_cloze.py:33`).

### D. Mind Map $\to$ Source Chunk
In `rag/services/document_knowledge.py:516-547`:
- Structural nodes (`chapter`, `section`) inherit `provenance_from_row(concept)` and `sources: concept['sources']`.
- Concept nodes (`type: 'concept'`) carry the concept's `sources` (up to 12 chunk IDs and pages).
- Evidence nodes (`type: 'evidence'`) carry `relation['sources']` and `provenance_from_row(relation)`.
- In the frontend SVG visualizer (`KnowledgeMap.tsx:104-118`), clicking any node selects it, rendering a side drawer that fetches and displays the verbatim source text and page number.

### E. Summary $\to$ Source Sentence
In `rag/services/document_knowledge.py:499-515`:
- Extractive summaries do NOT generate abstractive text.
- Every summary sentence is an exact, unedited sentence chosen directly from the source facts (`normalized(fact['text'])`).
- Every sentence object retains:
  ```python
  'sentences': [{
      'text': normalized(fact['text']),
      'knowledgeItemId': fact['id'],
      'pageStart': fact.get('pageStart'),
      'pageEnd': fact.get('pageEnd'),
      'sourceChunkIds': fact.get('sourceChunkIds'),
      'sources': fact['sources']
  }]
  ```

---

## 4. UI Source Link Integration

The frontend component `frontend/src/components/knowledge/SourceLink.tsx` provides a universal source inspector across all artifacts:
1. Renders a compact button: `"Page {page} · View source"`.
2. Triggers `onSource(chunkId)`.
3. Calls API endpoint: `GET /rag-api/rag/documents/{doc_id}/sources/{chunk_id}` or `GET /rag-api/libraries/{lib_id}/assets/{asset_id}/sources/{chunk_id}`.
4. Renders a secure modal/panel displaying:
   - Filename
   - Page number
   - Full verbatim chunk text in a blockquote.
