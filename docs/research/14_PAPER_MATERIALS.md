# IEEE paper preparation materials

This is a drafting kit, not a completed paper. Measurements remain placeholders except explicitly qualified historical artifacts. Current scope is global catalogue plus resource-specific QA; private-library retrieval remains **FUTURE WORK**.

## Research questions and hypotheses

| Question | Testable hypothesis (unproven) | Experiment |
|---|---|---|
| RQ1: Does dense retrieval help conceptual library queries while preserving exact lookup? | H1: Dense+rerank improves conceptual nDCG over lexical; lexical fusion preserves exact-name performance | E1 |
| RQ2: What ANN quality/cost tradeoff suits this catalogue? | H2: HNSW reduces query cost at a measured acceptable exact-neighbor recall for large N | E2 |
| RQ3: Do evidence features improve book QA/refusal behavior? | H3: Evidence composite reduces unsupported answers without excessive false refusals versus cross-encoder RAG | E3 + gate/feature ablations |
| RQ4: How does chunk representation affect grounding? | H4: Token-aware chunks improve source-span coverage and answer grounding compared with oversized character chunks | E4/E5 |
| RQ5: Can selected-resource access stay consistent across UI/API/source switching? | H5: Explicit source binding and backend checks produce no measured wrong-source output in the tested access matrix | E6/E7 |
| RQ6: What does maintainable indexing cost under catalogue churn? | H6: Base/delta publication lowers normal update cost relative to full rebuild while preserving validated mappings | E10 |
| RQ-F1: How can independently owned catalogues preserve strict retrieval isolation? | H-F1: Authorized partition indexes and final scoped hydration prevent measured cross-library results under the test workload | FUTURE E8 |
| RQ-F2: What index strategy handles many small/skewed libraries? | H-F2: On-demand registry with small-library exact search offers a better measured memory/cold-latency tradeoff than permanently resident HNSW for every library | FUTURE E9 |

## Ten current title options

1. LuminaR: Semantic Catalogue Retrieval and Resource-Specific Question Answering for Digital Libraries
2. An Evidence-Aware Conversational Retrieval System for Library Resources
3. Integrating Dense Book Discovery with Grounded Full-Text Question Answering
4. LuminaR: Design and Evaluation of an Intelligent Library Retrieval Platform
5. Resource-Bound Retrieval-Augmented Question Answering in a Digital Library
6. Evaluating Semantic Search and Evidence Selection for Library Discovery
7. A Local Retrieval and Generation Architecture for Books and Private Documents
8. Contextual Library Assistance through Semantic Retrieval and Verified Service Tools
9. Maintaining Dynamic Semantic Catalogues with Versioned Approximate Search Indexes
10. A Systems Study of Semantic Discovery and Conversational Access in Libraries

Future-only variant after implementation/evaluation: “Institution-Scoped Semantic Retrieval with Dynamically Maintained Library Indexes.” Do not use a multi-tenant title for current results.

## Abstract building blocks

Problem: conventional catalogue interfaces often require users to express information needs through bibliographic terms, while full-text answers require separate resource inspection. Motivation: natural-language discovery and grounded responses can complement established library operations.

System: LuminaR integrates local MiniLM catalogue embeddings, FAISS HNSW candidate retrieval, cross-encoder reranking, resource-specific flat-index retrieval, evidence-aware QA with local Qwen, personal PDF processing, and borrowing-based selected-book entitlement.

Evaluation placeholder: “We evaluate [frozen number] independently judged catalogue queries and [number] source-annotated QA questions against [baselines], measuring [metrics] on [hardware].” Results placeholder: “[Insert actual paired results and confidence intervals; NOT YET MEASURED].” Contributions: evaluated system integration, retrieval/grounding tradeoffs, and reproducible maintenance experiments if completed.

Future sentence: “The architecture is being extended toward institution-scoped catalogues with independently owned datasets and retrieval indexes.” This does not claim the extension works today.

## Introduction material

Begin with the practical gap between a user's conceptual reading need and available title/author/subject metadata. Dense representations can broaden candidate discovery; lexical matching still matters for exact names. Approximate retrieval makes large vector search tractable but must be measured for loss of nearest neighbors. Full-text QA adds a distinct evidence problem: relevant excerpts, correct resource selection, unsupported premises, and answers whose provenance is visible.

Introduce LuminaR as an implemented system connecting these mechanisms to circulation and selected-book access. Explain catalogue metadata retrieval versus full-text chunk retrieval and personal PDF processing. State a narrow evaluated contribution and limitations: established models/index algorithms, oversized source chunks, teacher-proxy historical labels, single-process assistant state, partial cross-store consistency. Finish the contribution paragraph with planned institution scoping as extensibility: physical libraries own different collections and should control their uploaded data and retrieval space.

## Related work categories and primary anchors

Traditional IR/BM25 and dense neural retrieval establish exact-versus-conceptual baselines. Sentence embedding techniques: [Reimers and Gurevych, Sentence-BERT](https://arxiv.org/abs/1908.10084). ANN: [Malkov and Yashunin, HNSW](https://arxiv.org/abs/1603.09320). Retrieval and generation: [Lewis et al., RAG](https://arxiv.org/abs/2005.11401). These are background methods, not LuminaR inventions. Model configuration: [MiniLM model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2), [Qwen model card](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct). Verify exact bibliographic venue/pages/DOI from publisher records before final IEEE references.

Further literature categories requiring a targeted survey: digital libraries/conversational search, document QA/source attribution, cross-encoder reranking, vector database maintenance, tenant-isolated information systems, filtered ANN, partition/federated retrieval and recommendation explanations. No claim of being first is justified by this preliminary set. A cross-library partition design is not federation unless independent services actually participate in a distributed query.

## Current methodology and pseudocode

Algorithm 1 — Implemented semantic book retrieval:

```text
authorize bearer; validate query/limit
snapshot ← current immutable global catalogue snapshot
vq ← normalize(MiniLM(query))
C ← merge(snapshot.base.search(vq), snapshot.delta.search(vq))
suppress overwritten/tombstoned labels; resolve work IDs
hydrate live searchable Mongo records; overfetch within budget
if lexical flag: add validated bounded title/author candidates
S ← CrossEncoder(query, title+author+subjects) for candidates
rank by S with configured exact/author evidence
hydrate current facts and inventory; optionally filter availability
cache bounded ranked identities by generation; return display page
```

Algorithm 2 — Implemented private PDF ingestion:

```text
authenticate owner/session; validate PDF bytes/name/size
create INGESTING UUID registry row and private directory
extract text layer page by page with PyMuPDF
clean; create 3000-character chunks with 400 overlap within each page
vectors ← normalized MiniLM(chunks), batch 32
write chunks/vectors; build per-document FlatIP(384)
publish ACTIVE registry state; on error disable/purge partial artifacts
return session-owned document ID
```

Algorithm 3 — Implemented resource-specific RAG:

```text
validate selected source and entitlement/session ownership
under inference lock bind only that private PDF or selected book
intent ← literal document fast path where applicable, otherwise intent analysis
retrieve FlatIP source candidates; expand eligible book queries
score candidates: 0.30 CE + 0.55 evidence + 0.15 dense (normalized)
select diverse context under character/depth budget
support ← fast gate or structured Qwen validator
if partially supported: optional second retrieval/validation
prompt ← grounded answer instructions or unsupported-evidence refusal
answer ← local Qwen with deterministic decoding
return answer, predicted verdict, structured source metadata and timings
clear private runtime binding
```

Algorithm 4 — **PROPOSED** library dataset ingestion:

```text
INPUT D,L,actor
verify actor may manage L; validate D and idempotency/checksum
create versioned staged dataset; parse normalized holdings/private records
persist scoped records with PENDING index state and durable jobs
build text/model-compatible vectors in batches
build staged H_L and generation-scoped label mappings
validate every mapping belongs to L and expected version
persist graph/mapping/manifests; atomically publish library generation
mark visible dataset READY; retain old generation for rollback
```

Algorithm 5 — **PROPOSED** library semantic retrieval:

```text
INPUT q,user,requested L
context ← verify active membership/access to L
(H_L,manifest) ← registry.acquire_published(L)
vq ← E_manifest(q)
labels ← ANN(H_L,vq,k or candidate budget)
holdings ← resolve(L,generation,partition,labels)
hydrate Mongo with library=L AND published version AND active
assert all resources/sources belong to L; rank scoped candidates
return page bound to L+generation; release handle
```

Formal future requirement: for dataset D_l, derive books/holdings B_l, vectors V_l through embedding function E and published index H_l. `v_q=E(q)`; `R_k(q,l)=ANN(H_l,v_q,k)` followed by scoped live mapping. Require `∀r∈R_k(q,l), library(r)=l` plus authorized membership. This invariant is proposed; approximate retrieval alone cannot prove it.

## Stack and paper structure

Verified languages/frameworks: Python/FastAPI/Pydantic/PyMongo, React/TypeScript/Vite/Zustand/Tailwind, SentenceTransformers/PyTorch/Transformers/FAISS, PyMuPDF, bcrypt/python-jose, local SQLite, offline DuckDB/Parquet/NumPy, optional cryptography and Brevo. Exact host versions are not established by dependency ranges. Future scope adds Library/Membership/Dataset services, index registry/jobs and library-aware clients, without requiring a new embedding provider.

Suggested sections: Introduction; Related Work; System Architecture; Catalogue Retrieval; Resource QA/Evidence; Experimental Setup; Results/Ablations; Limitations; Future Institution Architecture; Conclusion. Keep CRUD implementation compact and put reviewer source map in supplementary material. Figures/tables: 15–16.

## Screenshot and demo plan

Capture real semantic query/results, exact-name query, eligible selected-book Know More with sources, uploaded PDF QA/page provenance, borrow/return/history, staff counts/import preview, event publish/reader unseen badge, and metadata relationship explanations. Existing screenshots in reports may depict older builds; recapture only after verifying current source/service version. No screenshots were captured by this audit.

Proposed query categories: exact “Pride and Prejudice”; author “Jane Austen”; synonym “stories about social class and marriage”; conceptual “books explaining why societies become unequal”; beginner “learn programming from scratch”; descriptive “a story about a scientist creating life”; cross-domain “computing ideas used in biology”. These are candidate evaluation/demo prompts, not successful outcomes.

Future demo: Library A holds beginner Python; B holds advanced architecture. Same beginner query should return each active library's authorized relevant resources or a transparent no-match, never unauthorized resources. Show library switch, different results, upload build/READY indicator and scope-bound sources **after** implementation and testing.
