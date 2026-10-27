# 70. Publication Diagram Specifications

## 1. Overview and Graphical Standards

Academic systems papers require rigorous, clear, and informative architectural diagrams. Every diagram in the manuscript must depict the **actual software implementation** without vague abstraction or hand-waving.

This document provides detailed design specifications and executable Mermaid code for the **14 core publication figures** required for the LuminaR paper:
1. Overall LuminaR Multi-Tier Architecture
2. Multi-Library Intelligent Middleware & Tenant Isolation
3. Catalog & Dataset Ingestion Pipeline
4. Two-Stage Hybrid Semantic Search
5. HNSW Graph Structure & Vector Index Mapping
6. Query Understanding & Routing Pipeline
7. Retrieval-Augmented Generation (RAG) Architecture
8. Multi-Layered Hallucination Mitigation
9. Document PDF Processing & Chunk Segmentation
10. Availability-Gated 8-Factor Recommendation Engine
11. Multi-Relational Knowledge Graph Exploration
12. Deterministic Educational Knowledge Artifacts Pipeline
13. Library Circulation Transaction State Machine
14. End-to-End Experimental Architecture & Evaluation Testbed

---

## 2. Diagram Specifications

### Figure 1: Overall LuminaR Multi-Tier Architecture
- **Purpose**: System overview showing the interaction between the React frontend, Node.js API Gateway, Python FastAPI AI Microservice, and dual database storage.
- **Key Components**: Client Browser (SPA), Express Gateway (Auth/Circulation), FastAPI Microservice (PyTorch/FAISS), MongoDB, SQLite/FAISS file store.

```mermaid
flowchart TD
    subgraph ClientTier [Client Tier: Browser / Single-Page App]
        UI[React 18 SPA]
        Router[React Router v6]
        Cytoscape[Cytoscape / Vis.js Graph UI]
        UI --> Router
        UI --> Cytoscape
    end

    subgraph APIGateway [Application Gateway Tier: Node.js / Express]
        AuthMW[JWT & Tenant Auth Middleware]
        CirculationEngine[Circulation Business Logic]
        CatalogController[Catalog & Search Proxy]
        Proxy[AI Proxy Client]
        
        AuthMW --> CirculationEngine
        AuthMW --> CatalogController
        CatalogController --> Proxy
    end

    subgraph AIMicroservice [AI & Retrieval Tier: Python / FastAPI]
        RouterAI[FastAPI Endpoints]
        IntentClassifier[Query Intent Router]
        DenseEmbed[all-MiniLM-L6-v2 Encoder]
        FAISSEngine[FAISS HNSW Index Engine]
        Reranker[Cross-Encoder Reranker]
        LLMEngine[Qwen2.5-3B-Instruct NF4]
        Enforcer[lm-format-enforcer]
        DeterministicTools[Deterministic Study Tools Engine]
        
        RouterAI --> IntentClassifier
        RouterAI --> DenseEmbed
        RouterAI --> DeterministicTools
        DenseEmbed --> FAISSEngine
        FAISSEngine --> Reranker
        Reranker --> LLMEngine
        Enforcer -.-> LLMEngine
    end

    subgraph StorageTier [Storage Tier]
        Mongo[(MongoDB: Books, Users, Borrows, Reserves)]
        SQLite[(SQLite: Normalized Lexical Index)]
        FAISSDisk[(FAISS Binary Index: index.bin)]
    end

    UI -->|HTTPS / REST| AuthMW
    CirculationEngine --> Mongo
    CatalogController --> Mongo
    Proxy -->|Internal HTTP :8000| RouterAI
    FAISSEngine <--> FAISSDisk
    Reranker <--> SQLite
```

---

### Figure 2: Multi-Library Middleware & Tenant Isolation
- **Purpose**: Demonstrates how requests from multiple institutional tenants are authenticated, scoped, and prevented from cross-library leakage.

```mermaid
flowchart LR
    subgraph Tenants [Institutional Tenants]
        T1[User @ Library A]
        T2[User @ Library B]
    end

    subgraph Middleware [LuminaR Middleware Proxy]
        Gate[JWT Verification & Tenant Extraction]
        ScopeCheck{library_id Verification}
        Conceal[HTTP 404 Concealment Filter]
    end

    subgraph PhysicalStores [Tenant Partitioned Indices]
        CatA[(Catalog A: Books & Chunks)]
        CatB[(Catalog B: Books & Chunks)]
        VecIndex[(Global FAISS HNSW Index)]
    end

    T1 -->|Bearer Token A| Gate
    T2 -->|Bearer Token B| Gate
    Gate --> ScopeCheck
    
    ScopeCheck -->|Authorized A| CatA
    ScopeCheck -->|Authorized B| CatB
    ScopeCheck -->|Cross-Tenant Access Attempt| Conceal
    Conceal -->|Hidden with 404 Not Found| T1
    
    CatA -.->|Post-Filter Mask: lib_id == A| VecIndex
    CatB -.->|Post-Filter Mask: lib_id == B| VecIndex
```

---

### Figure 3: Catalog & Dataset Ingestion Pipeline
- **Purpose**: Shows how raw catalog records (CSV/JSON) are normalized, embedded, and distributed into MongoDB, SQLite, and FAISS.

```mermaid
flowchart TD
    Raw[Raw Catalog Data: CSV / JSON / MARC] --> Validator[Catalog Schema Validator]
    Validator --> Normalizer[NFKC Text Normalizer]
    
    Normalizer --> DocRecord[Create Book Documents]
    DocRecord --> MongoInsert[(Insert MongoDB: books collection)]
    
    Normalizer --> LexicalExtract[Extract Title, Author, Subject Strings]
    LexicalExtract --> SQLiteInsert[(Insert SQLite: lexical_values B-Tree)]
    
    Normalizer --> TextConcat[Synthesize Representation String]
    TextConcat --> MiniLM[sentence-transformers/all-MiniLM-L6-v2]
    MiniLM --> DenseVectors[Generate 384-D Float32 Vectors]
    DenseVectors --> L2Norm[L2 Vector Normalization]
    L2Norm --> FAISSAdd[faiss.IndexHNSWFlat.add]
    FAISSAdd --> FAISSSerialize[(Serialize: index.bin & metadata.json)]
```

---

### Figure 4: Two-Stage Hybrid Semantic Search
- **Purpose**: Details the candidate generation, dynamic score normalization, candidate merging, and cross-encoder reranking steps.

```mermaid
flowchart TD
    Query[User Search Query q] --> NFKC[NFKC Normalization & Preprocessing]
    
    NFKC -->|Dense Path| Embed[all-MiniLM-L6-v2 Bi-Encoder]
    Embed --> HNSWQuery[FAISS HNSW Search: efSearch=128]
    HNSWQuery --> DensePool[Top-50 Dense Candidates with Dot Products]
    
    NFKC -->|Lexical Path| SQLiteQuery[SQLite Normalized B-Tree Query]
    SQLiteQuery --> FuzzyLev[Levenshtein Distance Filter: dist <= 2]
    FuzzyLev --> LexicalPool[Top-50 Lexical Candidates with Match Ratios]
    
    DensePool --> DenseNorm[Min-Max Normalization: S_dense_norm]
    LexicalPool --> LexicalNorm[Min-Max Normalization: S_lex_norm]
    
    DenseNorm & LexicalNorm --> Merge[Candidate Fusion: S_hybrid = alpha*S_dense + (1-alpha)*S_lex]
    Merge --> TenantFilter[Tenant Scope Filter: library_id == user.library_id]
    TenantFilter --> Top50Union[Top-50 Union Candidates]
    
    Top50Union --> CrossEncoder[cross-encoder/ms-marco-MiniLM-L-6-v2]
    Query -.-> CrossEncoder
    CrossEncoder --> Softmax[Relevance Logit Computation]
    Softmax --> TopK[Top-5 Final Ranked Results]
```

---

### Figure 5: HNSW Graph Structure & Vector Index Mapping
- **Purpose**: Illustrates the hierarchical multi-layer graph search process and mapping to MongoDB document metadata.

```mermaid
flowchart TD
    subgraph HNSWGraph [Hierarchical Navigable Small World Graph]
        L2[Layer 2: Sparse Long-Range Highway Edges]
        L1[Layer 1: Intermediate Clustering Edges]
        L0[Layer 0: Dense Bottom Layer with All Vectors]
        
        EntryPoint((Entry Point)) --> L2
        L2 -->|Greedy Search to Local Minimum| Down1[Step Down]
        Down1 --> L1
        L1 -->|Greedy Search to Local Minimum| Down0[Step Down]
        Down0 --> L0
        L0 -->|efSearch=128 Priority Queue| NN[k Nearest Neighbor Node IDs]
    end

    subgraph MetadataMapping [ID to Catalog Resolution]
        NN --> IDMap[metadata.json: Integer ID -> MongoDB ObjectId]
        IDMap --> MongoFetch[(MongoDB: Fetch Book & Chunk Records)]
    end
```

---

### Figure 6: Query Understanding & Routing Pipeline
- **Purpose**: Explains how incoming user prompts are categorized into Catalog Search, Factual QA, or Administrative commands.

```mermaid
flowchart TD
    Input[Incoming User String] --> Clean[Normalize & Strip Characters]
    Clean --> IntentClassifier{Intent Classification Router}
    
    IntentClassifier -->|Catalog / Book Intent| SearchPath[Route to Hybrid Catalog Search Pipeline]
    IntentClassifier -->|Document QA Intent| RAGPath[Route to PDF Chunk Retrieval & RAG]
    IntentClassifier -->|Circulation / Admin Intent| OpsPath[Route to Express CRUD / Borrow Router]
    IntentClassifier -->|Off-Topic / Chit-Chat| FastChat[Direct Conversational Agent / Polite Boundary Refusal]
```

---

### Figure 7: Retrieval-Augmented Generation (RAG) Architecture
- **Purpose**: Depicts the end-to-end RAG pipeline from chunk retrieval to constrained autoregressive generation.

```mermaid
flowchart TD
    UserQuery[User Question] --> ChunkRetriever[Retrieve Top-5 Relevant Chunks via Hybrid Search]
    ChunkRetriever --> ContextPacker[Format Context Window: Document, Page, Chunk Text]
    
    ContextPacker --> PromptBuilder[Inject System Prompt, Context, and Query into Qwen Prompt Template]
    
    PromptBuilder --> ModelInference[Qwen2.5-3B-Instruct in 4-bit NF4]
    
    subgraph DecodingConstraint [Constrained Generation Control]
        Enforcer[lm-format-enforcer Prefix Trie Masking]
        Grammar[Pydantic JSON / Regex Schema]
        Grammar --> Enforcer
        Enforcer -.->|Logit Masking| ModelInference
    end
    
    ModelInference --> StructuredOutput[Valid JSON Object / Grounded Answer]
```

---

### Figure 8: Multi-Layered Hallucination Mitigation
- **Purpose**: Shows the three defensive barriers that prevent hallucinations and enforce abstention.

```mermaid
flowchart TD
    Q[User Query] --> C[Retrieved Context Chunks]
    
    subgraph Barrier1 [Barrier 1: Retrieval Relevance & Filtering]
        RerankFilter{Cross-Encoder Score >= Threshold?}
        RerankFilter -- No --> EmptyContext[Empty Context Window]
        RerankFilter -- Yes --> FillContext[Populate Context Window]
    end
    
    subgraph Barrier2 [Barrier 2: Negative Refusal System Prompting]
        Prompt["System: Answer ONLY from context. If facts are missing, emit 'NOT_SUPPORTED'."]
    end
    
    subgraph Barrier3 [Barrier 3: Constrained Decoding & Schema Enforcement]
        Mask[Mask Logits Violating Pydantic Schema / Refusal Token Tokens]
    end
    
    C --> Barrier1
    Barrier1 --> Barrier2
    Barrier2 --> Barrier3
    Barrier3 --> OutputAnswer{Output Evaluation}
    OutputAnswer -->|Answer Present| GroundedResp[Grounded Factual Response with Citations]
    OutputAnswer -->|Answer Absent| SafeRefusal[Safe Abstention: 'NOT_SUPPORTED']
```

---

### Figure 9: Document PDF Processing & Chunk Segmentation
- **Purpose**: Illustrates PDF document parsing, page extraction, sliding-window chunking, and metadata indexing.

```mermaid
flowchart TD
    PDF[Uploaded PDF Document] --> PyPDF[PyPDF2 Text Extraction Engine]
    PyPDF --> PageExtract[Extract Text by Page with Page Number Metadata]
    PageExtract --> CleanText[Remove Non-printable Characters & Normalize Whitespace]
    
    CleanText --> SlidingWindow[Sliding Character Window Chunker]
    
    subgraph ChunkSpecs [Chunking Parameters]
        CSize[Window Size: 3,000 Characters (~650 Tokens)]
        COverlap[Window Overlap: 400 Characters (~90 Tokens)]
    end
    
    SlidingWindow --> ChunkList[Array of Text Chunks with {doc_id, page_num, chunk_index}]
    ChunkList --> Embedder[Sentence-Transformers Bi-Encoder]
    Embedder --> VectorStore[(Register in SQLite & FAISS Chunk Index)]
```

---

### Figure 10: Availability-Gated 8-Factor Recommendation Engine
- **Purpose**: Details the 8 mathematical components and availability gating of the recommendation scoring function.

```mermaid
flowchart TD
    User[User Profile u] & Book[Candidate Book i] --> Factors[Compute 8 Composite Factors]
    
    Factors --> f1[f1: Genre / Subject Match w1=0.25]
    Factors --> f2[f2: Author Affinity w2=0.20]
    Factors --> f3[f3: Semantic Embedding Cosine w3=0.20]
    Factors --> f4[f4: Global Borrow Popularity w4=0.10]
    Factors --> f5[f5: Catalog Review Rating w5=0.10]
    Factors --> f6[f6: Temporal Recency Decay: exp(-lambda*dt) w6=0.05]
    Factors --> f7[f7: Collaborative Co-Borrowing w7=0.05]
    Factors --> f8[f8: Intra-List Diversity Penalty w8=-0.05]
    
    f1 & f2 & f3 & f4 & f5 & f6 & f7 & f8 --> Sum[Weighted Sum: S_raw(u, i)]
    
    Book --> InvCheck{copiesAvailable > 0?}
    InvCheck -- No (0 Copies) --> GateZero[Multiply by 0: Final Score = 0]
    InvCheck -- Yes (> 0 Copies) --> GateOne[Multiply by 1: Final Score = S_raw]
    
    GateOne --> RankList[Rank Candidates in Descending Order]
    GateZero --> Exclude[Filter from Top-k Recommendations]
```

---

### Figure 11: Multi-Relational Knowledge Graph Exploration
- **Purpose**: Depicts the bipartite schema linking books, authors, and subjects, along with dynamic neighborhood expansion.

```mermaid
graph TD
    subgraph GraphSchema [Heterogeneous Graph Schema]
        B1((Book: Clean Code))
        B2((Book: Clean Architecture))
        B3((Book: Refactoring))
        
        A1[Author: Robert C. Martin]
        A2[Author: Martin Fowler]
        
        G1{Subject: Software Engineering}
        G2{Subject: Agile Development}
        
        B1 -->|WRITTEN_BY| A1
        B2 -->|WRITTEN_BY| A1
        B3 -->|WRITTEN_BY| A2
        
        B1 -->|BELONGS_TO| G1
        B2 -->|BELONGS_TO| G1
        B3 -->|BELONGS_TO| G1
        B1 -->|BELONGS_TO| G2
        B3 -->|BELONGS_TO| G2
    end
```

---

### Figure 12: Deterministic Educational Knowledge Artifacts Pipeline
- **Purpose**: Contrasts the deterministic CPU NLP study tools pipeline with unconstrained generative models.

```mermaid
flowchart TD
    DocText[Ingested Textbook Section] --> Preproc[Sentence Boundary Tokenization]
    
    subgraph DeterministicEngine [Deterministic CPU NLP Engine (Zero-LLM)]
        Preproc --> CopularRegex[Copular Pattern Matcher: 'X is defined as Y']
        CopularRegex --> Flashcards[Concept Flashcards: 100% Faithful]
        
        Preproc --> TFIDFMask[Noun-Phrase & Keyword Salience Filter]
        TFIDFMask --> ClozeBlanks[Generate Cloze Fill-in-the-Blank Tests]
        
        Preproc --> NounCooccur[Noun-Phrase Co-occurrence Graph Builder]
        NounCooccur --> CyclePrune[Cycle Detection & Hierarchical DAG Pruning]
        CyclePrune --> MindMap[Renderable Hierarchical Mind Map]
    end
    
    subgraph GradingEngine [Deterministic Grading Engine]
        StudentInput[Student Answer] --> PhoneticMatch[Soundex & Metaphone Phonetic Distance]
        StudentInput --> EditDist[Levenshtein Distance: dist <= 2]
        PhoneticMatch & EditDist --> FinalGrade[Binary / Partial Credit Grade in <50ms]
    end
    
    ClozeBlanks --> StudentInput
```

---

### Figure 13: Library Circulation Transaction State Machine
- **Purpose**: Illustrates the state machine transitions and invariants governing book copies, borrows, and reservations.

```mermaid
stateDiagram-v2
    [*] --> Available: Book Registered in Catalog
    
    Available --> CheckedOut: checkout() [copiesAvailable > 0, Fines <= $10]
    Available --> Reserved: reserve() [Waitlist queue formed]
    
    CheckedOut --> Renewed: renew() [renewalsCount < maxRenewals]
    Renewed --> CheckedOut: Due Date Extended
    
    CheckedOut --> Returned: returnBook() [Within due date]
    CheckedOut --> Overdue: Due Date Passed [Accruing daily fines]
    Overdue --> Returned: returnBook() [Fines recorded on user account]
    
    Returned --> Available: No Pending Reservations
    Returned --> Reserved: Pending Reservation Next in Queue
    
    Reserved --> CheckedOut: Claimed within 48 Hours
    Reserved --> Available: Hold Expired / Canceled
```

---

### Figure 14: End-to-End Experimental Architecture & Evaluation Testbed
- **Purpose**: Depicts the master evaluation framework executing Experiments A through K with frozen seeds and metrics logging.

```mermaid
flowchart TD
    subgraph GroundTruth [Ground Truth Curation]
        Queries[100 Stratified Queries across 10 Categories]
        RAGQuestions[90 Questions across Tri-Partite Partitions]
        Annotators[Double-Blind Human Annotators with Cohen's Kappa]
        Queries & RAGQuestions --> Annotators
        Annotators --> GoldLabels[(Immutable Gold Truth Benchmark JSON)]
    end

    subgraph BenchmarkHarness [Automated Evaluation Harness]
        GoldLabels --> Runner[Test Harness Runner: Fixed Seeds 42]
        
        Runner --> ExpA[Exp A: Search Precision/Recall/nDCG]
        Runner --> ExpB[Exp B: HNSW Scaling 1k-100k]
        Runner --> ExpD[Exp D: RAG vs LLM-Only]
        Runner --> ExpE[Exp E: Hallucination & Abstention]
        Runner --> ExpI[Exp I: 3,000 Multi-Tenant Security Calls]
        Runner --> ExpJ[Exp J: Recommender nDCG & Availability]
        Runner --> ExpK[Exp K: Artifact Faithfulness & Latency]
    end

    subgraph MetricsOutput [Standardized Reporting]
        ExpA & ExpB & ExpD & ExpE & ExpI & ExpJ & ExpK --> Logger[Metrics Collector]
        Logger --> Tables[(Populate Result Tables 1-13 in 62_RESULT_TABLE_TEMPLATES.md)]
    end
```
