# Paper tables and empty result templates

Values marked **NYM** mean **NOT YET MEASURED**. Planned dataset sizes are design parameters, not completed benchmarks. Historical artifacts must be labeled separately from new results.

## Table I — Verified implementation stack

| Layer | Technology / model | Source | Caveat |
|---|---|---|---|
| Browser | React/TypeScript/Vite/Zustand/Tailwind | frontend/package.json | Version ranges/lockfile; actual deployed build unverified |
| APIs | FastAPI/Pydantic/Python | backend/main.py and service API modules | Four localhost processes |
| Business persistence | MongoDB/PyMongo | backend/database/mongodb.py | Live schema/index audit not performed |
| Catalogue embedding | MiniLM-L6-v2 / 384 / 256 tokens | search/luminar_search.py | Local cached model |
| Catalogue ANN | FAISS HNSW M32/efC200/efS128 | search/index_manager.py | Base/delta logical deletion |
| Rerank | MS MARCO MiniLM L6 CrossEncoder | search/luminar_search.py, rag/reranker.py | Standard pretrained model |
| QA index | FAISS FlatIP | rag/embed.py, private_documents.py | Separate book/PDF scope |
| Generation | Qwen2.5-3B-Instruct | rag/llm.py | NF4 CUDA / float32 CPU |
| Extraction | PyMuPDF | document_service.py | Text layer, no OCR |
| Identity | bcrypt + HS256 JWT | auth_service/jwt_utils | Current identity/revocation checks |
| Derived artifacts | SQLite/DuckDB/NumPy/JSON/Parquet | search/rag/data_pipeline | Different consistency domains |

## Table II — Major modules

| Module | Inputs | Outputs | Storage / service boundary |
|---|---|---|---|
| Core catalogue/circulation | Authorized resource operations | Book/loan/reservation/fine/history | MongoDB |
| Catalogue search | Query/filter/page | Ranked book IDs/facts | FAISS + Mongo + optional lexical |
| Recommendation | User/seed/feedback | Ranked discovery candidates | Mongo + search HTTP |
| Resource QA | Question/selected source/depth | Answer/verdict/sources | FlatIP + Qwen |
| Assistant | Message/selection/page/action | Structured response/proposal/tool output | Owner/session memory + service calls |
| Private library | PROPOSED scope/dataset | PROPOSED scoped results | PROPOSED registry/jobs/holdings |

## Table III — Search evaluation

| System | Queries/corpus/checksum | nDCG@10 | MRR@10 | P@5 | Pooled R@10 | p50/p95 ms | Failure % |
|---|---|---|---|---|---|---|---|
| Exact/lexical | NYM | NYM | NYM | NYM | NYM | NYM | NYM |
| BM25 proposed | NYM | NYM | NYM | NYM | NYM | NYM | NYM |
| Exact dense | NYM | NYM | NYM | NYM | NYM | NYM | NYM |
| HNSW dense | NYM | NYM | NYM | NYM | NYM | NYM | NYM |
| HNSW + CE | NYM | NYM | NYM | NYM | NYM | NYM | NYM |
| Optional lexical merge + CE | NYM | NYM | NYM | NYM | NYM | NYM | NYM |

Repeat query strata and paired confidence intervals; teacher-proxy historical metrics belong in a separate exploratory table.

## Table IV — ANN efficiency/fidelity

| N / d / hardware | Index / M / efC / efS | Exact-neighbor R@5/R@10 | Warm p50/p95 | Cold load | Build sec | Peak RSS | Disk bytes |
|---|---|---|---|---|---|---|---|
| NYM | FlatIP | NYM | NYM | NYM | NYM | NYM | NYM |
| NYM | HNSW 32/200/128 | NYM | NYM | NYM | NYM | NYM | NYM |

## Table V — QA evaluation

| Variant | Supported/unanswerable n | Correctness | Groundedness | Completeness | False refusal | Unsupported claims | p50/p95 | Prompt tokens |
|---|---|---|---|---|---|---|---|---|
| Qwen only | NYM | NYM | NYM | NYM | NYM | NYM | NYM | NYM |
| Dense top1/topk | NYM | NYM | NYM | NYM | NYM | NYM | NYM | NYM |
| CE RAG | NYM | NYM | NYM | NYM | NYM | NYM | NYM | NYM |
| Evidence composite/gates | NYM | NYM | NYM | NYM | NYM | NYM | NYM | NYM |

## Table VI — Ablation

| Removed/changed factor | Fixed controls | Δ primary metric + CI | Δ latency + CI | Failure/error stratum |
|---|---|---|---|---|
| Lexical / rerank / expansion / evidence / validator | NYM | NYM | NYM | NYM |
| Chunk tokens / overlap / context k | NYM | NYM | NYM | NYM |
| Embedding snapshot/model | NYM | NYM | NYM | NYM |

## Table VII — PROPOSED multi-library architecture comparison

| Architecture | Isolation mechanism | Memory cost (theory) | Search behavior | Scale tradeoff | Complexity |
|---|---|---|---|---|---|
| Shared HNSW + postfilter | Backend scoped mapping/output check; graph pool still global | One resident graph | Global topN→filter; scoped recall may collapse | Small tenants/high skew need large N | Simple files; difficult recall/privacy maintenance |
| Per-library graph | Authorized handle + scoped graph/mapping + DB recheck | Sum resident library graph sizes | ANN on selected library; no other tenants in pool | Many tiny graphs/load overhead | Independent lifecycle; needs lazy loading |
| Registry hybrid | Library partition + small FlatIP + large HNSW; optional future shards | Bounded resident cache + manifest/queue cost | Selected partition only | Better controlled working set; cold miss costs | More orchestration; measure before sharding |

The table states design reasoning, not measured memory/latency superiority. Fill numeric scope leakage, R@k, cold/p95/build/RSS and architecture costs only after future E8/E9.

## Supplementary consistency and evidence tables

| Mutation/failure | Publication generation | Time-to-searchable | Stale/wrong ID count | Recovery outcome | Dataset/model checksum |
|---|---|---|---|---|---|
| Add/update/delete/replacement/corruption | NYM | NYM | NYM | NYM | NYM |

| Claim ID | Source/version | Experiment/artifact | Scope | Confidence interval | Paper wording approved |
|---|---|---|---|---|---|
| See claims ledger | NYM | NYM | NYM | NYM | NYM |
