# LuminaR Library

LuminaR is a library-management application with a React/TypeScript web client and Python APIs for circulation, catalogue search, recommendations, a knowledge graph, and book/document question answering.

## Main components

- `frontend/`: React 19, TypeScript, Vite, Tailwind CSS; development server on port 5173.
- `backend/`: FastAPI core API on port 8002; authentication, catalogue, borrowing, returns, reservations, renewals, fines, reading lists, and administration use MongoDB and local catalogue metadata.
- `search/`: semantic catalogue search API on port 8003, with SentenceTransformers, FAISS/HNSW, optional lexical ranking, and a CrossEncoder reranker.
- `recommendation/`: recommendation API on port 8004.
- `rag/`: RAG and private document API on port 8005, using MiniLM embeddings, FAISS, a CrossEncoder, and Qwen2.5-3B-Instruct. The assistant routes are installed in this service.
- `knowledge_graph/`: catalogue relationship/recommendation graph.
- `data_pipeline/`, `scripts/`, `datasets/training/`, and `tests/`: ingestion, index building, model training/evaluation, reporting, and automated tests.

## Requirements

- Python 3.11 or newer and the packages in `requirements.txt`.
- Node.js compatible with Vite 8 and npm.
- MongoDB for accounts, circulation, inventory, and activity data.
- Local catalogue databases, search indexes, RAG indexes, and model files. The current source expects these at repository-relative paths in most services and at fixed `D:\SDC\LibraryLLM\...` paths in `backend/database/` and some older pipeline scripts.
- Enough RAM/disk and a compatible accelerator for the Qwen RAG service; CPU use is possible but model startup and inference are resource intensive.

## Configure and install

From the repository root, copy `.env.example` to `.env` and set a private, random `JWT_SECRET_KEY`, your MongoDB connection, and optional Brevo/cache settings. Never commit `.env`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd frontend
npm ci
```

The `.env.example` lists supported core settings. `frontend/.env.example` documents the optional library selector and API proxy configuration. Do not put server secrets in frontend environment variables.

## Required data and model assets

The working development copy includes very large catalogues, databases, embedding matrices, vector indexes, training outputs, and local Hugging Face cache files. These are intentionally excluded by `.gitignore`; the current app cannot provide full catalogue search, the graph, or book-level RAG without the corresponding assets. Arrange a trusted download or reproducible build process for the specific files needed by each service before running it. Files above GitHub's regular file limit require Git LFS if they are within its per-file limit; multi-gigabyte files should use an external artifact/data store. Do not upload private documents or local databases containing user records.

The existing SQLite/DuckDB paths include absolute Windows paths. A fresh clone on another machine needs its data assets placed at the expected paths or those paths updated before core/metadata services can use them.

## Run locally

Start MongoDB and make sure the required catalogue, index, and model assets are available. In separate terminals, from the repository root:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
python -m uvicorn search.api:app --host 127.0.0.1 --port 8003
python -m uvicorn recommendation.api:app --host 127.0.0.1 --port 8004
python -m uvicorn rag.api:app --host 127.0.0.1 --port 8005
```

Then run the web client:

```powershell
cd frontend
npm run dev
```

Vite proxies `/api`, `/search-api`, `/recommendation-api`, and `/rag-api` to those local services. The RAG service loads model/index assets at startup, so it will fail to start when those assets are missing.

## Tests and useful documentation

Run frontend checks with `cd frontend; npm test` and `npm run build`. Run Python tests from the repository root with `python -m pytest`. Some integration and live-service checks require MongoDB, local model/index data, or email configuration. See `docs/`, `STAFF_AUTH.md`, and the reports under `reports/` and `datasets/training/reports/` for feature and evaluation details.
