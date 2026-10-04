# Cleanup Report

## Summary

This is a source-and-asset cleanup review for the LuminaR Library project. No application source, tests, research scripts, project reports, or required local catalogue/index data were deleted by this run. A broad deletion command was rejected by the execution policy. At the final inventory, `backend.zip` and the dated restart files were absent; I cannot establish who or what removed them. `.gitignore` excludes their file types from a future Git add where the patterns apply.

The project directory has no `.git` metadata. Git-tracked state, staging state, remotes, and commit history could not be inspected. Treat push readiness as unverified until the project is checked in its actual Git checkout.

Added `pytest.ini` so the default pytest discovery uses the current `tests/` directory rather than archived test copies in `reports/` and `scratch/`.

## Deleted Files

**Deleted count: 0 files and 0 directories.** The removal operation was rejected with “blocked by policy”; no alternate deletion method was attempted.

The following reviewed candidates were still present at the final inventory:

| Path | Why it appears safe to remove |
|---|---|
| `knowledge_graph/data/kg31_pilot_v2_subject_vocab_failed.building.sqlite` | Incomplete build artifact; final V1/V2 graph files are present. |
| Python cache directories, `.pytest_cache/`, and `frontend/dist/` | Regenerable interpreter/test/build output. These are now ignored. |

`backend.zip`, `restart_id.txt`, `search_restart.err.log`, and `search_restart.out.log` were absent at the final inventory. They were not deleted by this run.

The root `.gitignore` also excludes `*.zip`, `*.log`, `*.db`, `*.sqlite*`, `*.duckdb`, `*.pdf`, and configured build/cache folders, so those files should not enter a fresh Git add when the ignore file is applied.

## Classification and Files Kept

| Area | Classification | Reason / action |
|---|---|---|
| `frontend/src/`, `backend/`, `assistant/`, `search/`, `recommendation/`, `rag/`, `knowledge_graph/` | KEEP — Production | Active app entry points, route wiring, services, search/RAG engines, and frontend routes. |
| `requirements.txt`, `frontend/package.json`, lockfile, Vite/TypeScript config, environment examples | KEEP — Configuration | Required to install and configure the app. Root `.env.example` was added. |
| `tests/`, `frontend/tests/` | KEEP — Test | Current automated tests. |
| `scripts/`, `data_pipeline/`, `datasets/training/` | KEEP — Research/Evaluation | Includes data ingestion, model training, reranking, retrieval evaluation, and reproducible reporting scripts. |
| `docs/`, `reports/`, `datasets/training/reports/`, root evaluation JSON | KEEP — Documentation / Research/Evaluation | Reports are cross referenced; historical snapshots are useful review evidence. |
| `scratch/`, `rag_e2e_test.py`, `check_db.py`, `cleanup_ids.json` | REVIEW MANUALLY | Manual/one-off tools and fixtures have no clear production references, but their evidence or operational purpose is uncertain. Preserved. |
| `RECOMMENDATION_SYSTEM_TECHNICAL_REVIEW.md`, `SEARCH_SYSTEM_TECHNICAL_REVIEW.md`, `STAFF_AUTH.md` | KEEP — Documentation | Technical and security review material; historical claims should be rechecked before presenting as current. |
| `frontend/README.md` | KEEP — Documentation | Replaced Vite starter text with a short pointer to the project README. |
| `pytest.ini` | KEEP — Configuration | Restricts pytest discovery to the current suite under `tests/`; archived source snapshots remain preserved. |
| `.venv/`, `frontend/node_modules/` | GITIGNORE | Left installed locally so the existing development environment remains usable. |
| `datasets/ai/`, source Parquet stores, local databases, training checkpoints/model cache, generated RAG assets | GITIGNORE / REVIEW MANUALLY | Large or generated assets; several are required at runtime and must be supplied separately or rebuilt. Preserved locally. |

## Gitignored Files

Updated [`.gitignore`](.gitignore) to cover `.env` and per-machine `.env.*` files while retaining `.env.example` files; Python/test caches; frontend dependencies/build output; logs and profiling output; local databases; PDFs; model weights, indexes, embeddings, and Parquet data; Hugging Face caches; training checkpoints/models; generated RAG indexes/chunks; temporary archives; IDE/OS files; and project validation traces.

The database ignore patterns already used by the project were retained. This means required local databases and indexes will not be included automatically in a clone. The README now calls out that the current app is not self-contained without those assets.

## Large Files

Sizes below are rounded from the files present during inspection. Indexes/catalogues are runtime data; Parquet and training assets are inputs or research outputs. None were deleted.

| Path | Approx. size | Purpose | Git recommendation |
|---|---:|---|---|
| `datasets/ai/faiss/hnsw/hnsw.index` | 8.4 GiB | Active semantic search HNSW index | External artifact storage; exceeds GitHub LFS per-file limit. |
| `knowledge_graph/data/catalogue.sqlite` | 5.5 GiB | Default active catalogue graph | External artifact storage; exceeds GitHub LFS per-file limit. |
| `datasets/ai/embeddings/vectors/embeddings.npy` | 7.2 GiB | Search embedding matrix | External artifact storage; exceeds GitHub LFS per-file limit. |
| `datasets/ai/faiss/faiss.index` | 7.2 GiB | Full FAISS index | External artifact storage; exceeds GitHub LFS per-file limit. |
| `datasets/ai/search/search_corpus.parquet` | 4.4 GiB | Search corpus input | Git LFS is technically possible by size; a data/artifact store is preferable. |
| `datasets/cleaned/editions.parquet` | 3.2 GiB | Cleaned catalogue data | Git LFS or external data storage. |
| `datasets/master/books_master.parquet` | 3.0 GiB | Master catalogue data | Git LFS or external data storage. |
| `datasets/cleaned/works.parquet` | 2.4 GiB | Cleaned work records | Git LFS or external data storage. |
| `datasets/ai/metadata/book_metadata.duckdb` | 2.4 GiB | Search metadata database | Git LFS or external artifact storage. |
| `datasets/library.db` | 2.1 GiB | Local core catalogue database | Do not publish if it contains user records; use sanitized seed data or external private storage. |
| `datasets/ai/lexical/published/*.sqlite` | 1.2 GiB | Active lexical-search sidecar | External artifact storage or regenerate from catalogue data. |
| `datasets/ai/embeddings/embedding_corpus.parquet` | 1.2 GiB | Embedding-generation corpus | Git LFS or external data storage. |
| `datasets/training/hf_cache/` | 1.1 GiB | Downloaded models/datasets cache | Re-download during setup; do not commit. |
| `datasets/training/models/`, `datasets/training/checkpoints/` | ~1.1 GiB combined | Fine-tuned model weights and optimizer checkpoints | Keep scripts/manifests/reports in Git; use LFS for selected small weights or external model hosting. |
| `reports/kg31_audit.sqlite`, `reports/kg_productization_metadata_degrees.sqlite` | ~293 MiB each | Generated audit databases | Rebuild from source inputs or publish as external research artifacts if needed. |

The `datasets/` directory totals about 56 GiB, and `knowledge_graph/data/` about 6.0 GiB. The `.gitignore` excludes generated/data binaries by path and extension. A future GitHub push still needs an explicit data distribution plan and an audit of already tracked files after Git metadata is restored.

There are 21 local PDF files totaling about 13 MiB. They were preserved on disk and are ignored by the requested `*.pdf` rule; review them before pushing in case any are intended project fixtures.

## Security

- `Secret detected in .env: API key`.
- `Secret detected in .env: authentication or encryption key`.
- `Secret detected in .env: database/service credential`.
- The root `.gitignore` excludes `.env`; `.env.example` contains safe placeholders only. Existing `.env.assistant.example`, `.env.know-more.example`, and `frontend/.env.example` were preserved.
- A filename-only source scan found no common private-key, credential-bearing MongoDB URI, bearer-token, or common provider-key formats in the scanned source directories.
- Because there is no `.git` history to inspect, it is unknown whether any `.env` values were previously committed or pushed. Rotate credentials if they were ever exposed in a public or shared Git history; deleting the local file alone would not remove history exposure.

## Verification

- `npm test` in `frontend/`: **passed**, 85 tests.
- `npm run build` in `frontend/`: **passed**. Vite reported that the main JavaScript chunk is just over 500 kB minified.
- `.venv\Scripts\python.exe -c "import backend.main"`: **passed**.
- `.venv\Scripts\python.exe -m pytest tests --collect-only -q`: **passed collection**, 1,199 tests collected.
- `.venv\Scripts\python.exe -m pytest tests -q`: **failed**, 47 failed, 1,142 passed, 10 skipped. Failures include notification/admin summary counts, staff authentication/authorization fixtures, real-model intent expectations, and one RAG overview classification assertion. These failures are pre-existing behavior/test issues as far as this cleanup can establish; no application source was changed.
- `.venv\Scripts\python.exe -m pytest -q` before adding `pytest.ini`: **failed collection**, 173 errors, because pytest also discovered archived duplicate test trees under `reports/` and `scratch/` in addition to the current `tests/` directory.
- `.venv\Scripts\python.exe -m pytest --collect-only -q` after adding `pytest.ini`: **passed collection**, 1,199 current tests collected with archived snapshots excluded.
- Full live-service startup was not attempted. MongoDB, large local databases/indexes, and locally cached LLM models are required; the RAG API loads its model and indexes at import/startup.

## Manual Review

- No Git checkout exists at this path. Restore/initialize the intended Git repository before trusting a push audit, and run `git status`, `git check-ignore`, and a secret/history scan there.
- Decide how to distribute required catalogue, graph, semantic/lexical indexes, RAG indexes, and selected training models. Several single files exceed GitHub LFS's per-file limit.
- Review whether `datasets/library.db` or other local databases contain personal/user data before sharing them.
- The code currently includes absolute `D:\SDC\LibraryLLM\...` paths in database configuration and older pipeline scripts; a clone elsewhere will need those assets/paths addressed.
- The root `.env` contains populated credentials. Confirm it has never been committed; rotate exposed credentials if it has.
- Preserved one-off candidates: `check_db.py`, `rag_e2e_test.py`, `cleanup_ids.json`, `scratch/`, and older technical review/report snapshots. Keep them if they are project-review evidence; otherwise remove them after confirming their purpose.
- The incomplete graph build artifact and generated cache/build directories were not removed because the execution policy blocked the removal operation.

## Important Directory Structure

```text
LibraryLLM/
├── assistant/               # assistant orchestration and API integration
├── backend/                 # FastAPI library service, routes, services, MongoDB
├── data_pipeline/           # catalogue/embedding/index ingestion and tooling
├── datasets/                # local catalogue, search, training, and experiment assets
├── docs/                    # operational and architecture notes
├── frontend/                # React/TypeScript application and tests
├── knowledge_graph/         # graph service and local graph data
├── rag/                     # book/document RAG, model and retrieval services
├── recommendation/          # recommendation service
├── reports/                 # evaluation reports and preserved baselines
├── scripts/                 # build, audit, benchmark, and validation scripts
├── search/                  # semantic and lexical search service
├── tests/                   # Python test suite
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```
