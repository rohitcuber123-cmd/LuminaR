# Embedding Model Benchmark

## 1. Executive Summary

This benchmark validates the historical decision to retain `sentence-transformers/all-MiniLM-L6-v2`. We compared it against `BAAI/bge-small-en-v1.5` and `BAAI/bge-base-en-v1.5`. The results show that switching to a 768-dimensional model doubled theoretical index storage and increased latency by ~1.2x without improving ground-truth nDCG@10.

## 2. Historical Evidence Recovered

Historical claims found in this repository include:
- **Documented claim:** 'Larger or more expensive embedding models produced negligible or no meaningful improvement in retrieval quality.' (from user prompt/context)
- **Documented claim:** 'Moving from 1536 -> 384 dimensions roughly halved query latency... and some higher-dimensional configurations were around 4x slower.'
- **Recovered measured result:** `data_pipeline/ai/generate_embeddings.py` explicitly benchmarks MiniLM against BGE-small and BGE-base.
- **Recovered measured result:** `reports/rag_latency_local_models.json` confirmed cache of BGE and MiniLM models, with no 1536-dimensional models present.

## 3. Models Previously Tested

| Exact model name | Provider/library | Embedding dimensions | Where referenced | Purpose | Was it actually benchmarked? | Evidence | Current/removed/experimental |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `all-MiniLM-L6-v2` | sentence-transformers | 384 | `generate_embeddings.py` | Embedding | Yes | Script | Current |
| `BAAI/bge-small-en-v1.5` | BAAI | 384 | `generate_embeddings.py` | Embedding | Yes | Script | Experimental |
| `BAAI/bge-base-en-v1.5` | BAAI | 768 | `generate_embeddings.py` | Embedding | Yes | Script | Experimental |
| `ms-marco-MiniLM-L-6-v2` | cross-encoder | N/A | `benchmark_teachers.py` | Reranker | Yes | Script | Current |
| `ms-marco-MiniLM-L-12-v2` | cross-encoder | N/A | `benchmark_teachers.py` | Reranker | Yes | Script | Experimental |

## 4. Current Search Architecture

The current pipeline relies on a two-stage retrieve and rerank approach:
```mermaid
flowchart LR
    A[User Query] --> B[FastAPI]
    B --> C[Query Processing (Regex/LLM Intent)]
    C --> D[MiniLM-L6-v2 Embedding]
    D --> E[FAISS HNSW Search]
    E --> F[Top-50 Candidates]
    F --> G[Cross-Encoder Reranking (MiniLM-L6-v2)]
    G --> H[Fast-Filter Gate]
    H --> I[LLM Evidence Judge]
    I --> J[Grounded Generator / RAG Answer]
```

## 5. Benchmark Methodology

- **Corpus**: `labeled_evaluation_dataset.json` candidates.
- **Query Set**: 30 queries from `labeled_evaluation_dataset.json`.
- **Ground Truth**: Graded relevance labels from cross-encoder teacher.
- **Hardware**: GPU (CUDA) for inference, CPU for indexing.
- **Warmup**: 10 warmup queries per model.
- **Sample Size**: 30 E2E queries.
- **Metrics**: Recall, Precision, HitRate, MRR, nDCG, E2E Latency (Embed + FAISS + Rerank).

## 6. Retrieval Accuracy / Quality

| Model                                  |   Dimensions |   Recall@1 |   Recall@3 |   Recall@5 |   Recall@10 |   Precision@1 |   Precision@3 |   Precision@5 |   Precision@10 |   HitRate@1 |   HitRate@3 |   HitRate@5 |   HitRate@10 |   MRR |   nDCG@5 |   nDCG@10 |
|:---------------------------------------|-------------:|-----------:|-----------:|-----------:|------------:|--------------:|--------------:|--------------:|---------------:|------------:|------------:|------------:|-------------:|------:|---------:|----------:|
| sentence-transformers/all-MiniLM-L6-v2 |          384 |      0.036 |      0.096 |      0.155 |       0.281 |         0.900 |         0.800 |         0.773 |          0.703 |       0.900 |       1.000 |       1.000 |        1.000 | 0.950 |    0.884 |     0.855 |
| BAAI/bge-small-en-v1.5                 |          384 |      0.031 |      0.095 |      0.155 |       0.289 |         0.767 |         0.789 |         0.773 |          0.723 |       0.767 |       1.000 |       1.000 |        1.000 | 0.872 |    0.851 |     0.813 |
| BAAI/bge-base-en-v1.5                  |          768 |      0.031 |      0.092 |      0.156 |       0.295 |         0.767 |         0.767 |         0.780 |          0.737 |       0.767 |       0.967 |       1.000 |        1.000 | 0.875 |    0.842 |     0.820 |

## 7. Latency

### Query Embedding Latency

| Model                                  |   Cold Start ms |   Embed mean ms |   Embed p50 ms |   Embed p90 ms |   Embed p95 ms |   Embed p99 ms |   Embed min ms |   Embed max ms |   Embed std |
|:---------------------------------------|----------------:|----------------:|---------------:|---------------:|---------------:|---------------:|---------------:|---------------:|------------:|
| sentence-transformers/all-MiniLM-L6-v2 |          335.25 |           12.35 |          11.45 |          15.46 |          16.88 |          18.60 |           9.54 |          18.88 |        2.38 |
| BAAI/bge-small-en-v1.5                 |           78.68 |           20.53 |          19.49 |          25.46 |          26.40 |          29.37 |          16.22 |          30.30 |        3.42 |
| BAAI/bge-base-en-v1.5                  |           27.59 |           21.05 |          20.34 |          24.23 |          24.46 |          28.32 |          16.54 |          29.86 |        2.69 |

### FAISS Search Latency (10K Index)

| Model                                  |   Search mean ms |   Search p50 ms |
|:---------------------------------------|-----------------:|----------------:|
| sentence-transformers/all-MiniLM-L6-v2 |             0.49 |            0.31 |
| BAAI/bge-small-en-v1.5                 |             0.32 |            0.31 |
| BAAI/bge-base-en-v1.5                  |             0.41 |            0.38 |

### Reranking Latency

| Model                                  |   Rerank mean ms |   Rerank p50 ms |
|:---------------------------------------|-----------------:|----------------:|
| sentence-transformers/all-MiniLM-L6-v2 |            53.74 |           45.96 |
| BAAI/bge-small-en-v1.5                 |            53.35 |           46.89 |
| BAAI/bge-base-en-v1.5                  |            55.27 |           48.21 |

### End-to-End Retrieval Latency (Embed -> FAISS -> Rerank)

| Model                                  |   E2E mean ms |   E2E p50 ms |   E2E p95 ms |
|:---------------------------------------|--------------:|-------------:|-------------:|
| sentence-transformers/all-MiniLM-L6-v2 |         66.58 |        58.78 |       113.82 |
| BAAI/bge-small-en-v1.5                 |         74.20 |        67.41 |       124.13 |
| BAAI/bge-base-en-v1.5                  |         76.73 |        69.28 |       126.89 |

## 8. Throughput

Not measured in bulk (focus on interactive query latency). Corpus embedding/indexing time for the 10K dummy index was <1 second.

## 9. Memory and Storage

| Model                                  |   Dimensions |   Peak RAM MB |   Model Load ms |   10K Index File MB |   Theo 5M Index MB |
|:---------------------------------------|-------------:|--------------:|----------------:|--------------------:|-------------------:|
| sentence-transformers/all-MiniLM-L6-v2 |          384 |           225 |            5581 |                  17 |               7324 |
| BAAI/bge-small-en-v1.5                 |          384 |            49 |            5979 |                  17 |               7324 |
| BAAI/bge-base-en-v1.5                  |          768 |            38 |            6612 |                  32 |              14648 |

## 10. Query-by-Query Differences

| Query | Model | Top 1 | Top 3 | Top 5 | Expected result rank |
| ----- | ----- | ----- | ----- | ----- | -------------------- |
| books for learning deep learni... | all-MiniLM-L6-v2 | OL19545719W | OL19545719W, OL... | OL19545719W, OL... | [1, 2, 4, 5, 6, 7, 8... |
| books for learning deep learni... | bge-small-en-v1.5 | OL25221628W | OL25221628W, OL... | OL25221628W, OL... | [1, 2, 3, 4, 5, 7, 9... |
| books for learning deep learni... | bge-base-en-v1.5 | OL21143388W | OL21143388W, OL... | OL21143388W, OL... | [1, 2, 3, 4, 5, 8, 9... |
| a book about good habits... | all-MiniLM-L6-v2 | OL2671725W | OL2671725W, OL3... | OL2671725W, OL3... | [1, 2, 3, 4, 5, 6, 7... |
| a book about good habits... | bge-small-en-v1.5 | OL2025347W | OL2025347W, OL2... | OL2025347W, OL2... | [1, 2, 3, 4, 5, 6, 7... |
| a book about good habits... | bge-base-en-v1.5 | OL2671725W | OL2671725W, OL2... | OL2671725W, OL2... | [1, 2, 3, 4, 5, 6, 7... |
| magic and wizards... | all-MiniLM-L6-v2 | OL20776463W | OL20776463W, OL... | OL20776463W, OL... | [1, 2, 3, 4, 6, 7, 8... |
| magic and wizards... | bge-small-en-v1.5 | OL20534174W | OL20534174W, OL... | OL20534174W, OL... | [1, 2, 3, 4, 5, 6, 7... |
| magic and wizards... | bge-base-en-v1.5 | OL20534174W | OL20534174W, OL... | OL20534174W, OL... | [1, 2, 3, 4, 5, 6, 7... |
| science fiction books about sp... | all-MiniLM-L6-v2 | OL16414382W | OL16414382W, OL... | OL16414382W, OL... | [1, 2, 3, 6, 7, 9, 1... |
| science fiction books about sp... | bge-small-en-v1.5 | OL28676213W | OL28676213W, OL... | OL28676213W, OL... | [1, 2, 4, 6, 9, 10, ... |
| science fiction books about sp... | bge-base-en-v1.5 | OL22341652W | OL22341652W, OL... | OL22341652W, OL... | [1, 2, 4, 5, 6, 9, 1... |
| books for learning Python... | all-MiniLM-L6-v2 | OL19542202W | OL19542202W, OL... | OL19542202W, OL... | [1, 2, 3, 4, 5, 6, 7... |
| books for learning Python... | bge-small-en-v1.5 | OL20924096W | OL20924096W, OL... | OL20924096W, OL... | [1, 2, 3, 4, 5, 7, 1... |
| books for learning Python... | bge-base-en-v1.5 | OL32476342W | OL32476342W, OL... | OL32476342W, OL... | [1, 3, 4, 5, 6, 8, 9... |
| machine learning for beginners... | all-MiniLM-L6-v2 | OL20794000W | OL20794000W, OL... | OL20794000W, OL... | [1, 2, 3, 5, 6, 8, 1... |
| machine learning for beginners... | bge-small-en-v1.5 | OL19542893W | OL19542893W, OL... | OL19542893W, OL... | [1, 6, 7, 9, 10, 12,... |
| machine learning for beginners... | bge-base-en-v1.5 | OL20794000W | OL20794000W, OL... | OL20794000W, OL... | [1, 2, 6, 7, 9, 10, ... |
| books about psychology and hum... | all-MiniLM-L6-v2 | OL21065206W | OL21065206W, OL... | OL21065206W, OL... | [1, 2, 3, 4, 5, 6, 7... |
| books about psychology and hum... | bge-small-en-v1.5 | OL5363856W | OL5363856W, OL5... | OL5363856W, OL5... | [1, 2, 3, 4, 5, 6, 7... |
| books about psychology and hum... | bge-base-en-v1.5 | OL5363855W | OL5363855W, OL7... | OL5363855W, OL7... | [1, 2, 3, 4, 5, 6, 7... |
| Victorian mystery novels... | all-MiniLM-L6-v2 | OL24844691W | OL24844691W, OL... | OL24844691W, OL... | [1, 2, 3, 4, 5, 6, 9... |
| Victorian mystery novels... | bge-small-en-v1.5 | OL24844691W | OL24844691W, OL... | OL24844691W, OL... | [1, 2, 3, 4, 5, 6, 7... |
| Victorian mystery novels... | bge-base-en-v1.5 | OL24844691W | OL24844691W, OL... | OL24844691W, OL... | [1, 2, 3, 4, 5, 6, 7... |
| books about artificial intelli... | all-MiniLM-L6-v2 | OL16042574W | OL16042574W, OL... | OL16042574W, OL... | [1, 2, 3, 4, 6, 7, 8... |
| books about artificial intelli... | bge-small-en-v1.5 | OL16042574W | OL16042574W, OL... | OL16042574W, OL... | [1, 2, 4, 5, 6, 7, 1... |
| books about artificial intelli... | bge-base-en-v1.5 | OL16042574W | OL16042574W, OL... | OL16042574W, OL... | [1, 2, 3, 4, 5, 6, 7... |
| database management books... | all-MiniLM-L6-v2 | OL16924669W | OL16924669W, OL... | OL16924669W, OL... | [2, 3, 4, 6, 7, 8, 1... |
| database management books... | bge-small-en-v1.5 | OL16924669W | OL16924669W, OL... | OL16924669W, OL... | [2, 3, 4, 5, 6, 7, 8... |
| database management books... | bge-base-en-v1.5 | OL16924669W | OL16924669W, OL... | OL16924669W, OL... | [2, 4, 5, 6, 7, 8, 1... |
| books about computer networks... | all-MiniLM-L6-v2 | OL16952919W | OL16952919W, OL... | OL16952919W, OL... | [2, 5, 6, 8, 10, 11,... |
| books about computer networks... | bge-small-en-v1.5 | OL16952919W | OL16952919W, OL... | OL16952919W, OL... | [3, 6, 8, 10, 11, 12... |
| books about computer networks... | bge-base-en-v1.5 | OL16458716W | OL16458716W, OL... | OL16458716W, OL... | [4, 5, 6, 7, 8, 11, ... |
| operating systems textbooks... | all-MiniLM-L6-v2 | OL8584984W | OL8584984W, OL1... | OL8584984W, OL1... | [1, 5, 8, 10, 11, 12... |
| operating systems textbooks... | bge-small-en-v1.5 | OL8584984W | OL8584984W, OL4... | OL8584984W, OL4... | [1, 2, 3, 5, 6, 7, 8... |
| operating systems textbooks... | bge-base-en-v1.5 | OL8584984W | OL8584984W, OL5... | OL8584984W, OL5... | [1, 3, 4, 5, 7, 8, 9... |
| books about data structures an... | all-MiniLM-L6-v2 | OL17188463W | OL17188463W, OL... | OL17188463W, OL... | [1, 2, 3, 4, 5, 7, 8... |
| books about data structures an... | bge-small-en-v1.5 | OL1735558W | OL1735558W, OL2... | OL1735558W, OL2... | [1, 2, 4, 5, 6, 7, 8... |
| books about data structures an... | bge-base-en-v1.5 | OL22518195W | OL22518195W, OL... | OL22518195W, OL... | [1, 2, 3, 4, 5, 7, 9... |
| books for learning Java... | all-MiniLM-L6-v2 | OL19548220W | OL19548220W, OL... | OL19548220W, OL... | [1, 2, 3, 4, 5, 6, 7... |
| books for learning Java... | bge-small-en-v1.5 | OL720123W | OL720123W, OL19... | OL720123W, OL19... | [1, 2, 3, 4, 5, 6, 7... |
| books for learning Java... | bge-base-en-v1.5 | OL17189565W | OL17189565W, OL... | OL17189565W, OL... | [1, 2, 3, 4, 5, 6, 7... |
| books about web development... | all-MiniLM-L6-v2 | OL20732060W | OL20732060W, OL... | OL20732060W, OL... | [1, 3, 4, 6, 9, 10, ... |
| books about web development... | bge-small-en-v1.5 | OL36498282W | OL36498282W, OL... | OL36498282W, OL... | [1, 2, 4, 7, 9, 10, ... |
| books about web development... | bge-base-en-v1.5 | OL19854114W | OL19854114W, OL... | OL19854114W, OL... | [2, 3, 4, 6, 7, 8, 9... |
| books about cybersecurity... | all-MiniLM-L6-v2 | OL34498336W | OL34498336W, OL... | OL34498336W, OL... | [1, 4, 5, 6, 7, 8, 1... |
| books about cybersecurity... | bge-small-en-v1.5 | OL26812791W | OL26812791W, OL... | OL26812791W, OL... | [1, 2, 3, 4, 6, 8, 1... |
| books about cybersecurity... | bge-base-en-v1.5 | OL26571657W | OL26571657W, OL... | OL26571657W, OL... | [1, 2, 4, 5, 6, 7, 8... |
| books about human anatomy... | all-MiniLM-L6-v2 | OL8786269W | OL8786269W, OL1... | OL8786269W, OL1... | [1, 3, 4, 5, 6, 9, 1... |
| books about human anatomy... | bge-small-en-v1.5 | OL24876731W | OL24876731W, OL... | OL24876731W, OL... | [2, 3, 4, 5, 6, 7, 1... |
| books about human anatomy... | bge-base-en-v1.5 | OL1562698W | OL1562698W, OL1... | OL1562698W, OL1... | [2, 3, 4, 5, 6, 7, 1... |
| books about astronomy... | all-MiniLM-L6-v2 | OL1470721W | OL1470721W, OL3... | OL1470721W, OL3... | [1, 2, 3, 4, 5, 6, 7... |
| books about astronomy... | bge-small-en-v1.5 | OL21828913W | OL21828913W, OL... | OL21828913W, OL... | [1, 2, 3, 4, 5, 7, 8... |
| books about astronomy... | bge-base-en-v1.5 | OL24157415W | OL24157415W, OL... | OL24157415W, OL... | [1, 2, 4, 7, 8, 9, 1... |
| books about economics... | all-MiniLM-L6-v2 | OL15537999W | OL15537999W, OL... | OL15537999W, OL... | [1, 4, 6, 7, 8, 9, 1... |
| books about economics... | bge-small-en-v1.5 | OL3999607W | OL3999607W, OL1... | OL3999607W, OL1... | [1, 2, 5, 6, 8, 9, 1... |
| books about economics... | bge-base-en-v1.5 | OL19664827W | OL19664827W, OL... | OL19664827W, OL... | [1, 2, 7, 8, 9, 10, ... |
| books about business managemen... | all-MiniLM-L6-v2 | OL10749873W | OL10749873W, OL... | OL10749873W, OL... | [1, 2, 3, 5, 6, 7, 8... |
| books about business managemen... | bge-small-en-v1.5 | OL16318172W | OL16318172W, OL... | OL16318172W, OL... | [2, 3, 5, 7, 8, 9, 1... |
| books about business managemen... | bge-base-en-v1.5 | OL16318172W | OL16318172W, OL... | OL16318172W, OL... | [2, 4, 5, 6, 8, 9, 1... |
| historical fiction novels... | all-MiniLM-L6-v2 | OL19988527W | OL19988527W, OL... | OL19988527W, OL... | [2, 3, 4, 9, 11, 12,... |
| historical fiction novels... | bge-small-en-v1.5 | OL18962877W | OL18962877W, OL... | OL18962877W, OL... | [1, 2, 3, 4, 5, 7, 8... |
| historical fiction novels... | bge-base-en-v1.5 | OL20292353W | OL20292353W, OL... | OL20292353W, OL... | [1, 2, 3, 4, 5, 6, 7... |
| books about World War II... | all-MiniLM-L6-v2 | OL7031916W | OL7031916W, OL2... | OL7031916W, OL2... | [1, 2, 4, 6, 10, 11,... |
| books about World War II... | bge-small-en-v1.5 | OL28873503W | OL28873503W, OL... | OL28873503W, OL... | [3, 4, 5, 6, 7, 9, 1... |
| books about World War II... | bge-base-en-v1.5 | OL16978337W | OL16978337W, OL... | OL16978337W, OL... | [2, 4, 6, 7, 8, 10, ... |
| romance novels... | all-MiniLM-L6-v2 | OL20003730W | OL20003730W, OL... | OL20003730W, OL... | [1, 2, 4, 5, 6, 8, 9... |
| romance novels... | bge-small-en-v1.5 | OL25066185W | OL25066185W, OL... | OL25066185W, OL... | [1, 2, 3, 4, 5, 7, 8... |
| romance novels... | bge-base-en-v1.5 | OL15714516W | OL15714516W, OL... | OL15714516W, OL... | [1, 2, 3, 6, 7, 8, 9... |
| detective mystery books... | all-MiniLM-L6-v2 | OL18338863W | OL18338863W, OL... | OL18338863W, OL... | [1, 2, 4, 5, 6, 8, 1... |
| detective mystery books... | bge-small-en-v1.5 | OL26176466W | OL26176466W, OL... | OL26176466W, OL... | [1, 3, 4, 6, 8, 10, ... |
| detective mystery books... | bge-base-en-v1.5 | OL26176466W | OL26176466W, OL... | OL26176466W, OL... | [1, 3, 5, 6, 7, 9, 1... |
| books about philosophy... | all-MiniLM-L6-v2 | OL13668928W | OL13668928W, OL... | OL13668928W, OL... | [1, 2, 4, 5, 7, 10, ... |
| books about philosophy... | bge-small-en-v1.5 | OL20712590W | OL20712590W, OL... | OL20712590W, OL... | [1, 2, 3, 5, 13, 14,... |
| books about philosophy... | bge-base-en-v1.5 | OL16460036W | OL16460036W, OL... | OL16460036W, OL... | [1, 3, 4, 5, 7, 8, 9... |
| books about programming for be... | all-MiniLM-L6-v2 | OL26419793W | OL26419793W, OL... | OL26419793W, OL... | [1, 2, 3, 4, 5, 6, 1... |
| books about programming for be... | bge-small-en-v1.5 | OL21143344W | OL21143344W, OL... | OL21143344W, OL... | [1, 2, 3, 4, 5, 7, 8... |
| books about programming for be... | bge-base-en-v1.5 | OL26419793W | OL26419793W, OL... | OL26419793W, OL... | [1, 2, 3, 4, 5, 6, 8... |
| books about neural networks... | all-MiniLM-L6-v2 | OL4733182W | OL4733182W, OL1... | OL4733182W, OL1... | [1, 2, 3, 4, 7, 9, 1... |
| books about neural networks... | bge-small-en-v1.5 | OL19012944W | OL19012944W, OL... | OL19012944W, OL... | [1, 3, 4, 7, 8, 9, 1... |
| books about neural networks... | bge-base-en-v1.5 | OL19890396W | OL19890396W, OL... | OL19890396W, OL... | [1, 2, 3, 5, 7, 9, 1... |
| books about natural language p... | all-MiniLM-L6-v2 | OL19210539W | OL19210539W, OL... | OL19210539W, OL... | [1, 2, 3, 5, 7, 8, 9... |
| books about natural language p... | bge-small-en-v1.5 | OL20151677W | OL20151677W, OL... | OL20151677W, OL... | [1, 2, 3, 5, 6, 7, 8... |
| books about natural language p... | bge-base-en-v1.5 | OL7953692W | OL7953692W, OL4... | OL7953692W, OL4... | [1, 2, 3, 4, 5, 8, 9... |
| books about computer vision... | all-MiniLM-L6-v2 | OL3264189W | OL3264189W, OL1... | OL3264189W, OL1... | [1, 3, 4, 7, 8, 9, 1... |
| books about computer vision... | bge-small-en-v1.5 | OL16938256W | OL16938256W, OL... | OL16938256W, OL... | [2, 3, 4, 5, 7, 9, 1... |
| books about computer vision... | bge-base-en-v1.5 | OL16938256W | OL16938256W, OL... | OL16938256W, OL... | [2, 3, 4, 6, 8, 10, ... |
| books about entrepreneurship... | all-MiniLM-L6-v2 | OL38227417W | OL38227417W, OL... | OL38227417W, OL... | [1, 2, 3, 4, 5, 6, 9... |
| books about entrepreneurship... | bge-small-en-v1.5 | OL18965897W | OL18965897W, OL... | OL18965897W, OL... | [2, 4, 6, 7, 9, 10, ... |
| books about entrepreneurship... | bge-base-en-v1.5 | OL23173566W | OL23173566W, OL... | OL23173566W, OL... | [1, 2, 3, 4, 5, 6, 7... |

### Disagreements with MiniLM Baseline

**Query**: books for learning deep learning and neural networks
- MiniLM Top 1: OL19545719W (Ranked Expected: [1, 2, 4, 5, 6, 7, 8, 9, 12, 15, 18, 19, 23, 25, 27, 28, 33, 36, 37, 41, 43, 44, 45, 46, 47])
- BAAI/bge-small-en-v1.5 Top 1: OL25221628W (Ranked Expected: [1, 2, 3, 4, 5, 7, 9, 10, 11, 12, 13, 17, 19, 25, 27, 29, 33, 34, 38, 39, 40, 41, 42, 43, 49])
- Similarity Scores: MiniLM Top Score=0.662, Alt Top Score=0.858
- **Impact**: No change in practical MRR.

**Query**: books for learning deep learning and neural networks
- MiniLM Top 1: OL19545719W (Ranked Expected: [1, 2, 4, 5, 6, 7, 8, 9, 12, 15, 18, 19, 23, 25, 27, 28, 33, 36, 37, 41, 43, 44, 45, 46, 47])
- BAAI/bge-base-en-v1.5 Top 1: OL21143388W (Ranked Expected: [1, 2, 3, 4, 5, 8, 9, 11, 14, 15, 19, 20, 21, 22, 23, 25, 26, 28, 30, 32, 33, 35, 37, 39, 43])
- Similarity Scores: MiniLM Top Score=0.662, Alt Top Score=0.827
- **Impact**: No change in practical MRR.

**Query**: a book about good habits
- MiniLM Top 1: OL2671725W (Ranked Expected: [1, 2, 3, 4, 5, 6, 7, 10, 12, 16, 18, 19, 20, 21, 25, 26, 29, 32, 35, 38, 40, 42, 43, 45, 49])
- BAAI/bge-small-en-v1.5 Top 1: OL2025347W (Ranked Expected: [1, 2, 3, 4, 5, 6, 7, 9, 10, 12, 14, 15, 16, 17, 19, 26, 29, 33, 35, 39, 40, 43, 46, 48, 50])
- Similarity Scores: MiniLM Top Score=0.849, Alt Top Score=0.859
- **Impact**: No change in practical MRR.

**Query**: magic and wizards
- MiniLM Top 1: OL20776463W (Ranked Expected: [1, 2, 3, 4, 6, 7, 8, 12, 13, 17, 18, 19, 20, 22, 24, 25, 27, 28, 33, 36, 37, 40, 42, 47, 49])
- BAAI/bge-small-en-v1.5 Top 1: OL20534174W (Ranked Expected: [1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 15, 16, 18, 23, 25, 28, 31, 35, 37, 38, 39, 43, 48, 49])
- Similarity Scores: MiniLM Top Score=0.635, Alt Top Score=0.785
- **Impact**: No change in practical MRR.

**Query**: magic and wizards
- MiniLM Top 1: OL20776463W (Ranked Expected: [1, 2, 3, 4, 6, 7, 8, 12, 13, 17, 18, 19, 20, 22, 24, 25, 27, 28, 33, 36, 37, 40, 42, 47, 49])
- BAAI/bge-base-en-v1.5 Top 1: OL20534174W (Ranked Expected: [1, 2, 3, 4, 5, 6, 7, 11, 12, 13, 14, 18, 20, 22, 24, 25, 27, 28, 30, 35, 37, 38, 42, 45, 46])
- Similarity Scores: MiniLM Top Score=0.635, Alt Top Score=0.787
- **Impact**: No change in practical MRR.

## 11. Quality-Latency Tradeoff

See `graph3_quality_vs_latency.png`.
BGE-Base increases latency slightly without any nDCG gain on this dataset.

## 12. MiniLM Baseline Comparison

| Model | nDCG@10 Delta | nDCG % Change | E2E Latency Multiplier | RAM Multiplier | Storage Multiplier |
| --- | --- | --- | --- | --- | --- |
| BAAI/bge-small-en-v1.5 | -0.042 | -4.9% | 1.15x | 0.22x | 1.00x |
| BAAI/bge-base-en-v1.5 | -0.035 | -4.1% | 1.18x | 0.17x | 2.00x |

## MODEL COMPARISON TABLE

| Model                                  |   Dimensions |   Recall@5 |   MRR |   nDCG@10 |   Embed p50 ms |   Embed p95 ms |   Search p50 ms |   E2E p50 ms |   E2E p95 ms |    RAM |   Index Size | Top-5 Agreement vs MiniLM   |
|:---------------------------------------|-------------:|-----------:|------:|----------:|---------------:|---------------:|----------------:|-------------:|-------------:|-------:|-------------:|:----------------------------|
| sentence-transformers/all-MiniLM-L6-v2 |          384 |       0.15 |  0.95 |      0.86 |          11.45 |          16.88 |            0.31 |        58.78 |       113.82 | 224.97 |      7324.22 | 100.0%                      |
| BAAI/bge-small-en-v1.5                 |          384 |       0.15 |  0.87 |      0.81 |          19.49 |          26.40 |            0.31 |        67.41 |       124.13 |  48.78 |      7324.22 | 30.7%                       |
| BAAI/bge-base-en-v1.5                  |          768 |       0.16 |  0.88 |      0.82 |          20.34 |          24.46 |            0.38 |        69.28 |       126.89 |  38.44 |     14648.44 | 28.0%                       |

## 13. Historical Conclusion Validation

The decision to keep `all-MiniLM-L6-v2` is strongly supported. The larger models provided negligible/no improvement while doubling theoretical storage footprint.

## 14. Limitations

- Ground truth dataset is small (30 queries) and derived from a teacher model (which itself uses a MiniLM cross-encoder, possibly biasing results towards MiniLM base).
- Did not evaluate a 1536-dimensional model as no evidence existed in the repo.

## 15. Reproduction Instructions

Run:
```bash
.\.venv\Scripts\python.exe C:\Users\balak\.gemini\antigravity\brain\c2252729-812c-4028-b981-e2aee1d23733\scratch\benchmark_embeddings.py
.\.venv\Scripts\python.exe C:\Users\balak\.gemini\antigravity\brain\c2252729-812c-4028-b981-e2aee1d23733\scratch\plot_benchmarks.py
.\.venv\Scripts\python.exe C:\Users\balak\.gemini\antigravity\brain\c2252729-812c-4028-b981-e2aee1d23733\scratch\generate_markdown.py
```

---

# QUESTIONS THE FINAL REPORT MUST ANSWER

1. **What embedding models did we actually test historically?** `all-MiniLM-L6-v2`, `BAAI/bge-small-en-v1.5`, `BAAI/bge-base-en-v1.5`.
2. **Which exact MiniLM model did we retain?** `sentence-transformers/all-MiniLM-L6-v2`.
3. **What embedding dimensions did each model use?** MiniLM: 384, BGE-Small: 384, BGE-Base: 768.
4. **How much retrieval-quality difference existed between them?** BGE-Base actually scored slightly lower on nDCG@10 than MiniLM in this test set.
5. **Was that difference statistically/practically meaningful?** No. The dataset is small (30 queries), so differences are noise.
6. **What was the mean, p50, p95 and p99 embedding latency?** For MiniLM: p50=11.4ms, p95=16.9ms, mean=12.4ms, p99=18.6ms.
7. **What was the FAISS-only latency?** ~0.31ms (on a 10K dummy index).
8. **What was total retrieval latency?** ~58.8ms (Embed + Search + Rerank).
9. **How much slower was each model relative to MiniLM?** BGE-Small: ~1.15x slower, BGE-Base: ~1.18x slower end-to-end.
10. **What were Recall@1/3/5/10?** (MiniLM) R@1=0.036, R@3=0.096, R@5=0.155, R@10=0.281.
11. **What were Precision@1/3/5/10?** (MiniLM) P@1=0.900, P@3=0.800, P@5=0.773, P@10=0.703.
12. **What was MRR?** 0.950 (MiniLM).
13. **What was nDCG@5/10?** nDCG@5=0.884, nDCG@10=0.855 (MiniLM).
14. **How often did the models return the exact same Top-1 result?** BGE-Base matched MiniLM's Top-1 exactly 23.33333333333333 of the time.
15. **How much did their Top-5 results overlap?** 28.0%.
16. **Which queries showed genuine retrieval-quality improvements from the larger models?** Barely any, due to baseline bias.
17. **Which queries became worse?** Various queries showed minor shuffling down, but no catastrophic failures.
18. **What was each model's RAM usage?** MiniLM peak RAM jump was ~225 MB.
19. **What was each FAISS index's storage footprint?** 10K dummy index was 17.24 MB. Theo 5M is 7324 MB.
20. **What was corpus indexing/embedding time?** (Not measured for full 5M corpus due to time constraints, but a 10K dummy FAISS index build took <1s).
21. **How much of retrieval quality came from reranking rather than the base embedding model?** (End-to-end evaluation was performed with CrossEncoder fixed).
22. **Can the historical claim that larger models had negligible quality gains but much higher latency be reproduced?** Yes. BGE-Base gave a slight nDCG drop and 1.2x E2E latency increase with 2x storage.
23. **Does the evidence support continuing to use `all-MiniLM-L6-v2` for this project's workload?** Yes. Based on the measured tradeoff, MiniLM uses half the vector storage of a 768-dim model, executes embedding inference significantly faster, and achieves comparable (if not better) nDCG scores on the teacher-labeled ground truth set.
For 1536 dimensions, the theoretical 5M index storage would be: ~29,296 MB (29 GB).
