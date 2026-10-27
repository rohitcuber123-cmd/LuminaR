# LuminaR Frontend-Backend API Mapping & UI Integration Audit

## 1. Executive Summary

This document traces the complete integration between LuminaR’s React frontend and FastAPI backend for the Knowledge Tools module. It details every HTTP endpoint, Pydantic request model, TypeScript interface, UI component, state management hook, and abort controller lifecycle.

---

## 2. Complete API Endpoints Table

The system exposes two parallel sets of authenticated endpoints: one for **Personal Private Documents** and one for **Institutional Library Assets**:

| Method | Endpoint | Handler Function | Service Class & Method | Request Schema | Response Schema | Auth Guard | Scope |
|---|---|---|---|---|---|---|---|
| **GET** | `/rag/documents/{id}/artifacts` | `list_artifacts` | `KnowledgeArtifacts.list()` | None | `{"artifacts": Artifact[]}` | JWT (`get_current_user`) | Personal |
| **POST** | `/rag/documents/{id}/artifacts/quiz` | `generate_quiz` | `KnowledgeArtifacts.generate(slug='quiz')` | `QuizRequest` | `{"artifact": Artifact, "cached": bool}` | JWT (`get_current_user`) | Personal |
| **POST** | `/rag/documents/{id}/artifacts/{kind}` | `generate` | `KnowledgeArtifacts.generate()` | `ArtifactRequest` | `{"artifact": Artifact, "cached": bool}` | JWT (`get_current_user`) | Personal |
| **GET** | `/rag/documents/{id}/artifacts/{artifact_id}` | `get` | `KnowledgeArtifacts.get()` | None | `Artifact` | JWT (`get_current_user`) | Personal |
| **DELETE** | `/rag/documents/{id}/artifacts/{artifact_id}` | `delete` | `KnowledgeArtifacts.delete()` | None | `{"removed": true}` | JWT (`get_current_user`) | Personal |
| **GET** | `/rag/documents/{id}/sources/{chunk_id}` | `source` | `KnowledgeArtifacts.source()` | None | `Source` | JWT (`get_current_user`) | Personal |
| **POST** | `/rag/documents/{id}/artifacts/{aid}/cloze/{iid}/grade` | `grade_cloze` | `KnowledgeArtifacts.grade_cloze()` | `ClozeGradeRequest` | `ClozeGrade` | JWT (`get_current_user`) | Personal |
| **GET** | `/libraries/{lid}/assets/{aid}/artifacts` | `artifacts` | `LibraryAssetPipeline.list_artifacts()` | None | `{"artifacts": Artifact[]}` | JWT (`get_current_user`) | Institutional |
| **POST** | `/libraries/{lid}/assets/{aid}/artifacts/quiz` | `quiz` | `LibraryAssetPipeline.generate(slug='quiz')` | `QuizRequest` | `{"artifact": Artifact, "cached": bool}` | JWT (`get_current_user`) | Institutional |
| **POST** | `/libraries/{lid}/assets/{aid}/artifacts/{kind}` | `generate` | `LibraryAssetPipeline.generate()` | `ArtifactRequest` | `{"artifact": Artifact, "cached": bool}` | JWT (`get_current_user`) | Institutional |
| **GET** | `/libraries/{lid}/assets/{aid}/artifacts/{artifact_id}` | `artifact` | `LibraryAssetPipeline.get_artifact()` | None | `Artifact` | JWT (`get_current_user`) | Institutional |
| **DELETE** | `/libraries/{lid}/assets/{aid}/artifacts/{artifact_id}` | `delete` | `LibraryAssetPipeline.delete_artifact()` | None | `{"removed": true}` | Staff Role Required | Institutional |
| **GET** | `/libraries/{lid}/assets/{aid}/sources/{chunk_id}` | `source` | `LibraryAssetPipeline.source()` | None | `Source` | JWT (`get_current_user`) | Institutional |
| **POST** | `/libraries/{lid}/assets/{aid}/artifacts/{aid}/cloze/{iid}/grade` | `grade` | `LibraryAssetPipeline.grade()` | `ClozeGradeRequest` | `ClozeGrade` | JWT (`get_current_user`) | Institutional |

---

## 3. Backend Route Implementation & Schemas

### 3.1 Pydantic Request Models
Defined in [rag/services/knowledge_routes.py:L11-L28](file:///d:/SDC/LibraryLLM/rag/services/knowledge_routes.py#L11-L28):

```python
class ArtifactRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scope: Literal['document'] = 'document'
    mode: Literal['quick', 'detailed'] = 'quick'

class QuizRequest(ArtifactRequest):
    questionTypes: list[Literal['mcq', 'fill_blank', 'matching']] = Field(
        default_factory=lambda: ['mcq', 'fill_blank'], min_length=1, max_length=3
    )
    questionCount: int = Field(default=12, ge=1, le=30, strict=True)

class ClozeGradeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    answer: str = Field(min_length=1, max_length=500, strict=True)
```

### 3.2 HTTP Status Code Matrix & Error Handling
The backend implements strict HTTP error mapping:

| Status Code | Exception Reason | Client Error Message in UI |
|---|---|---|
| `401 Unauthorized` | Missing token or expired session (`exp <= time.time()`) | `"Sign in again to use Knowledge Tools."` |
| `403 Forbidden` | User does not own document or lacks library access | `"You do not have access to this document."` |
| `404 Not Found` | Document or artifact does not exist | `"This document or artifact is no longer available."` |
| `409 Conflict` | Document text unavailable or OCR corrupted | `"Document text is unavailable. Restore or upload the PDF again."` |
| `413 Payload Too Large` | Document `chunks.json` exceeds 64 MB | `"This document is too large for Knowledge Tools."` |
| `422 Unprocessable` | Empty questionTypes list or count outside 1..30 | Handled by Pydantic validation |
| `429 Too Many Requests` | Concurrency limit reached (`Semaphore(3)` full) | `"Knowledge Tools is busy. Please retry shortly."` |
| `503 Service Unavailable` | Cloze grading model busy | `"Answer checking is temporarily unavailable."` |

---

## 4. Frontend Component Hierarchy & State Architecture

### 4.1 Component Tree

```
[LLMPage.tsx] (Personal) OR [LibraryAssets.tsx] (Institutional)
       |
       +--> <KnowledgeTools documentId={...} title={...} libraryAsset={...} />
                 |
                 +--> <KnowledgeToolsSession key={`${token}:${libraryId}:${documentId}`} />
                           |
                           +--> Tab Navigation (Key Concepts | Summary | Flashcards | Mind Map | Quiz)
                           |
                           +--> Tab Panels:
                           |      |
                           |      +--> [Key Concepts]: Responsive Concept Grid + <SourceLink />
                           |      +--> [Summary]: Section Sentences List + <SourceLink />
                           |      +--> [Flashcards]: <Flashcards /> (Flip Card, Filters, Keyboard)
                           |      +--> [Mind Map]: <KnowledgeMap /> (SVG Canvas, Pan, Zoom, Fullscreen)
                           |      +--> [Quiz]: <Quiz /> (MCQ Radios, Cloze Inputs, Matching Selects)
                           |
                           +--> <aside aria-label="Source excerpt">: Source Inspection Drawer
```

### 4.2 State Isolation via React Keying Pattern
In [KnowledgeTools.tsx:L53-L56](file:///d:/SDC/LibraryLLM/frontend/src/components/knowledge/KnowledgeTools.tsx#L53-L56), the parent component implements a vital privacy and state-clearing mechanism:

```tsx
export function KnowledgeTools({ documentId, title, libraryAsset }: { documentId: string; title: string; libraryAsset?: LibraryAssetTarget }) {
  const token = useAuthStore(state => state.token)
  return <KnowledgeToolsSession
    key={`${token}:${libraryAsset?.libraryId || 'personal'}:${documentId}`}
    documentId={documentId}
    title={title}
    libraryAsset={libraryAsset}
  />
}
```
**Why this matters for review:**
By encoding `token`, `libraryId`, and `documentId` into the React component `key`:
- Switching between documents **unmounts and destroys** the entire session state.
- Signing out or switching user accounts **instantly purges** any displayed cards, quiz questions, or source excerpts from React memory.
- It prevents memory leaks and cross-document data leakage between tenant assets.

### 4.3 AbortController Lifecycle
Every network request in `KnowledgeToolsSession` is tracked via React refs holding `AbortController` instances ([KnowledgeTools.tsx:L64-L65](file:///d:/SDC/LibraryLLM/frontend/src/components/knowledge/KnowledgeTools.tsx#L64-L65)):
- `controller = useRef<AbortController | null>(null)`: Controls artifact list and generation calls.
- `sourceController = useRef<AbortController | null>(null)`: Controls source chunk fetches.
- When a user switches tabs or navigates away, `controller.current?.abort()` immediately cancels pending HTTP requests, preventing race conditions and stale state updates.

---

## 5. End-to-End Traces

### 5.1 Trace 1: Flashcard Flip & Source Inspection
```
User clicks 'Reveal answer' (Space bar)
  -> Flashcards.setFlipped(true)
  -> UI re-renders displaying card.back

User clicks 'View source' on Card 3
  -> SourceLink.onClick(card.sourceChunkIds[0])
  -> KnowledgeToolsSession.viewSource(chunkId)
  -> Calls getSource(documentId, chunkId, signal)
  -> Backend GET /rag/documents/{id}/sources/{chunk_id}
  -> KnowledgeArtifacts.source() retrieves chunk text & page numbers
  -> Frontend setSource(result)
  -> sourcePreview.scrollIntoView({ behavior: 'smooth' })
  -> <aside aria-label="Source excerpt"> displays original PDF text
```

### 5.2 Trace 2: Live Cloze Answer Submission & Semantic Grading
```
User types "sliding-window protocol" into Blank #2 and hits Enter
  -> Quiz.onKeyDown (Enter key intercepted, preventDefault)
  -> Quiz.submitCloze(question.id)
  -> Quiz.setBusy({ [q.id]: true })
  -> onGrade(question.id, "sliding-window protocol", abortSignal)
  -> Calls gradeCloze(documentId, artifactId, itemId, answer)
  -> Backend POST /rag/documents/{id}/artifacts/{aid}/cloze/{iid}/grade
  -> KnowledgeArtifacts.grade_cloze()
  -> cloze_grading.grade(item, answer, encoder)
       -> Normalizes NFKC & checks safe typo / identity
       -> Debounces MiniLM embeddings via SemanticCache (5ms window)
       -> Returns { verdict: 'CORRECT', canonical_answer: 'Sliding Window Protocol', feedback: '...' }
  -> Frontend receives ClozeGrade payload
  -> Quiz.setGrades({ [q.id]: grade })
  -> Quiz.setChecked({ [q.id]: true })
  -> UI displays "✓ Correct. Your answer matches the source meaning."
```
