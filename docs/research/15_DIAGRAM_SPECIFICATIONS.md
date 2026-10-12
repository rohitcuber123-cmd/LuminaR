# Paper figure specifications

Figures below are source-supported topology or explicitly proposed architecture. Use consistent labels and captions; export final publication figures as SVG/PDF through a diagram tool. No latency/accuracy values should appear without measured sources.

## Figure 1 — Implemented LuminaR architecture

```mermaid
flowchart TB
 UI[React / Zustand / Vite] -->|/api| CORE[Core FastAPI 8002]
 UI -->|/search-api| SEARCH[Search FastAPI 8003]
 UI -->|/recommendation-api| REC[Recommendation 8004]
 UI -->|/rag-api| RAG[RAG + Assistant 8005]
 CORE --> MONGO[(MongoDB business data)]
 SEARCH --> MONGO
 REC --> MONGO
 REC --> SEARCH
 SEARCH --> H[(Global HNSW base + delta / mappings)]
 SEARCH --> L[(Optional SQLite lexical sidecar)]
 SEARCH --> MINI[Local MiniLM + CrossEncoder]
 RAG --> FLAT[(Book and private-PDF FlatIP indexes)]
 RAG --> QWEN[Local Qwen + evidence checks]
 RAG --> PRIVATE[(Session SQLite registry / files)]
 RAG -->|Assistant tools| CORE
 RAG -->|Assistant tools| SEARCH
 RAG -->|Assistant tools| REC
 CORE --> KG[(SQLite catalogue relationships)]
```

Caption: Four APIs share identity/business records while catalogue ANN and resource QA use different index structures. Optional lexical path must be dashed in final artwork. Evidence: frontend/vite.config.ts; backend/main.py; search/api.py; recommendation/api.py; rag/api.py; assistant/tools.py.

## Figure 2 — Implemented catalogue retrieval

```mermaid
flowchart LR
 Q[Authenticated query] --> E[Normalized MiniLM 384]
 E --> S[Capture immutable snapshot]
 S --> ANN[Base + delta HNSW]
 ANN --> MAP[Labels → work IDs / override suppression]
 MAP --> LIVE[Current Mongo validation / bounded overfetch]
 LIVE --> CE[CrossEncoder + optional lexical tiers]
 CE --> HYDRATE[Live facts / inventory]
 HYDRATE --> PAGE[Bounded 50-pool / 10-result pages]
```

Draw lexical title/author lookup as an optional side input before CE. Mark physical inventory filtering after global retrieval; do not label it isolated library ANN. Show versioned cache around ranking separately from live fact hydration.

## Figure 3 — Implemented private document QA

```mermaid
flowchart TB
 PDF[Authenticated PDF bytes] --> VALID[Size / name / signature checks]
 VALID --> EX[PyMuPDF text-layer extraction]
 EX --> CH[Page-local characters 3000 / overlap 400]
 CH --> EMB[Normalized MiniLM / batch 32]
 EMB --> IDX[(Per-document FlatIP / private registry)]
 Q[Question + document ID] --> AUTH[Owner + session + expiry check]
 AUTH --> IDX
 IDX --> RANK[CrossEncoder + evidence features]
 RANK --> SUPPORT[Support gate / optional Qwen validator]
 SUPPORT --> GEN[Grounded answer or limitation prompt]
 GEN --> OUT[Answer + page/chunk sources]
```

Caption must say text extraction, not OCR. Overlay inference lock/session binding; optional ciphertext export/restore is a separate lifecycle inset.

## Figure 4 — Implemented circulation workflow

```mermaid
stateDiagram-v2
 [*] --> Available
 Available --> ISSUED: authorized borrow / guarded decrement
 ISSUED --> ISSUED: eligible idempotent renewal
 ISSUED --> RETURNED: owner return / state CAS
 RETURNED --> Available: restore original stock source
 RETURNED --> UNPAID: overdue calendar days × 5
 UNPAID --> PAID: settlement status endpoint
 NoAvailableCopies --> ACTIVE: reservation
 ACTIVE --> READY_FOR_PICKUP: FIFO after return
 READY_FOR_PICKUP --> FULFILLED: borrower issues book
 ACTIVE --> CANCELLED: owner cancels
 READY_FOR_PICKUP --> CANCELLED: owner cancels
```

This diagram summarizes multiple collections rather than one transactional state machine. Caption the stock/issue/fine side-effect failure windows and absence of financial processing.

## Figure 5 — PROPOSED private libraries

```mermaid
flowchart TB
 U[User + memberships] --> CTX[Authorized LibraryContext]
 CTX --> A[Library A / L_A]
 CTX --> B[Library B / L_B]
 A --> DA[Versioned dataset A]
 B --> DB[Versioned dataset B]
 DA --> BA[Scoped holdings A]
 DB --> BB[Scoped holdings B]
 BA --> HA[IndexRegistry → H_A / mappings A]
 BB --> HB[IndexRegistry → H_B / mappings B]
 HA --> RA[Only authorized A results / sources]
 HB --> RB[Only authorized B results / sources]
```

Caption: Proposed institution ownership and retrieval isolation, not current deployed capability. Global bibliographic Work records may be referenced by both holding branches; private text/metadata is scoped. Separate user-personal PDF ownership from library-shared corpus boxes.

## Figure 6 — PROPOSED dataset publication and recovery

```mermaid
flowchart LR
 UP[Owner upload + checksum] --> V[Validate / normalize]
 V --> ST[Stage scoped version]
 ST --> J[Durable embedding jobs]
 J --> BUILD[Build scoped vectors/index/mapping]
 BUILD --> CHECK[Checksum / ownership / generation validation]
 CHECK --> SWAP[Atomic published generation]
 SWAP --> READY[READY catalogue visible]
 J --> FAIL[FAILED / retry, old generation serves]
 BUILD --> FAIL
 CHECK --> FAIL
```

Add a dotted edge from failure to resumable job; add previous generation/rollback inset. Never suggest Mongo transaction includes filesystem graph construction. Supplementary figure candidates: snapshot base/delta tombstones, book entitlement matrix, cache restore/key-version flow, library switching/new-chat context, and measured latency/recall Pareto plot after experiments.
