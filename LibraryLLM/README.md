# LuminaR

## Intelligent Library Search, RAG, and Recommendations

LuminaR is a library management and discovery platform. It combines library workflows with semantic search, retrieval-augmented generation (RAG), recommendations, and a catalogue knowledge graph.

## Features

- Search a catalogue using natural-language queries and semantic retrieval.
- Ask questions about indexed books and uploaded documents using RAG.
- Discover related books through recommendations and catalogue relationships.
- Support library-scoped inventory and availability using a library ID. The default ID is `LIB001`.
- Manage accounts, borrowing, returns, reservations, renewals, fines, reading lists, and staff operations.
- Provide staff tools for inventory import and administrative activity.

The code supports library IDs in inventory and search flows. Configure and verify authorization across all services before using the platform for multiple independent institutions.

## Technology

| Area | Technologies |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| APIs | Python, FastAPI, Pydantic |
| Application data | MongoDB; local SQLite and DuckDB assets are also used by some modules and tools |
| Semantic search | SentenceTransformers, FAISS HNSW, CrossEncoder reranking |
| RAG | FAISS retrieval, MiniLM embeddings, CrossEncoder reranking, Qwen2.5-3B-Instruct |
| Testing | pytest, Node.js test runner, Testing Library |

## Project Structure

```text
.
├── assistant/       # Assistant orchestration and service integration
├── backend/         # Core library API, routes, services, and database access
├── data_pipeline/   # Catalogue, embedding, and index preparation
├── datasets/        # Local catalogue, search, and training data assets
├── docs/            # Operational and technical documentation
├── frontend/        # React and TypeScript client
├── knowledge_graph/ # Catalogue relationship graph
├── rag/             # Book and document retrieval and generation
├── recommendation/  # Recommendation API
├── reports/         # Evaluation reports and preserved results
├── scripts/         # Build, audit, benchmark, and validation tools
├── search/          # Semantic and lexical search API
├── tests/           # Python tests
├── .env.example
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.11 or later
- Node.js and npm compatible with Vite 8
- MongoDB
- Local search, catalogue, and RAG data assets
- Local model files for services configured to load models offline

The search and RAG services need substantial memory and disk space. GPU acceleration is supported where available; CPU inference may be slow.

## Setup

From the repository root, create and activate a Python environment, then install the backend dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create a local environment file from the example and set the required values:

```powershell
Copy-Item .env.example .env
```

Set a private random `JWT_SECRET_KEY` and a valid `MONGO_URI`. Brevo email settings and the private document cache key are optional. Do not commit `.env` or put server secrets in frontend environment variables.

Install frontend dependencies:

```powershell
cd frontend
npm ci
```

## Data and Model Assets

Large databases, catalogues, vector indexes, embedding files, model checkpoints, and local caches are excluded from Git. The current working environment contains these assets, but a fresh clone does not include them. Obtain or build the assets required by each service before starting it.

Several services load models in offline mode and expect indexes at specific paths. Some older database and pipeline files also contain absolute Windows paths. A clone in a different location may need local path configuration before those parts can run. Large files should be distributed through an artifact or data store; files larger than Git LFS's per-file limit cannot be stored there.

## Run Locally

Start MongoDB and make sure the required data and model assets are available. Run each API in a separate terminal from the repository root:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
python -m uvicorn search.api:app --host 127.0.0.1 --port 8003
python -m uvicorn recommendation.api:app --host 127.0.0.1 --port 8004
python -m uvicorn rag.api:app --host 127.0.0.1 --port 8005
```

In another terminal, start the frontend:

```powershell
cd frontend
npm run dev
```

The Vite development server runs on port `5173` and proxies requests to the local APIs. The RAG service loads its models and indexes during startup, so it will not start if required assets are missing.

## Tests

From the repository root, run the Python suite:

```powershell
python -m pytest
```

For frontend tests and a production build:

```powershell
cd frontend
npm test
npm run build
```

Some integration tests require MongoDB, local model/index assets, or external service configuration.

## Documentation

See `docs/`, `STAFF_AUTH.md`, and the reports under `reports/` and `datasets/training/reports/` for implementation details and evaluation results.
