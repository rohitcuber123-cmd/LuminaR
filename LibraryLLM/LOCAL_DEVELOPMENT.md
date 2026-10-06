# Independent local development

The original machine's MongoDB records, FAISS indexes and model cache are not in a Git checkout. This profile creates a separate `luminar_local` database on loopback MongoDB. It runs the real APIs, actual MiniLM embeddings, cross-encoder search and Qwen document answers. Knowledge Tools remain deterministic and make no Qwen calls.

Install Python 3.13, Node.js and MongoDB Server. From the `LibraryLLM` directory, use PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-local.txt
.\.venv\Scripts\python.exe scripts/local_init.py
# Start MongoDB first, or use your existing local MongoDB service.
# Choose a writable data directory; do not point at the original database files.
New-Item -ItemType Directory -Force .local/mongodb
& 'C:/Program Files/MongoDB/Server/8.3/bin/mongod.exe' --dbpath "$PWD/.local/mongodb" --bind_ip 127.0.0.1 --port 27017
```

Leave MongoDB running. In a second terminal at the same directory:

```powershell
.\.venv\Scripts\python.exe scripts/local_models.py
.\.venv\Scripts\python.exe scripts/local_seed.py --assets
Push-Location frontend
npm ci
Pop-Location
.\.venv\Scripts\python.exe scripts/start_local.py
```

Open http://127.0.0.1:5173/. Leave the launcher running; Ctrl+C stops its children. All APIs bind to loopback. Logs are in `.local/logs`. Downloads need several GB of disk; CPU Qwen currently loads float32 weights and needs substantial RAM (roughly 12 GB for weights plus runtime). CPU answers are slower than the original GPU system. The launcher uses real Qwen, never mock answers.

Seeded development accounts:

| Role | Email | Password |
|---|---|---|
| Reader | reader@luminar.example.com | LuminaR-Local-123! |
| Admin | admin@luminar.example.com | LuminaR-Admin-123! |

These accounts are verified only by the explicit local seed script. Normal login still verifies bcrypt hashes. Re-running the seed preserves existing accounts, passwords, loans and inventory quantities. It refuses non-local MongoDB or a database other than `luminar_local`. Existing book RAG assets and catalogue graphs are retained. The twelve original study samples use fixture work IDs and are clearly marked Local Sample. They are not claimed to be Open Library records or the original system's books.

To create your own local reader without putting a password in source files:

```powershell
$env:LUMINAR_LOCAL_PASSWORD = Read-Host 'Local password'
.\.venv\Scripts\python.exe scripts/local_seed.py --email 'your-address@example.com'
Remove-Item Env:LUMINAR_LOCAL_PASSWORD
```

Borrow a sample from the catalogue, then open My Books to read it or use Know More. For Knowledge Tools, open Know More, upload `local-data/sample-study-guide.pdf`, select it, then choose Knowledge Tools. Generate key concepts, summaries, flashcards, mind maps and quizzes. Private documents are scoped to the login session and removed on logout; upload again after a new login.

Normal signup, password recovery and email notifications require the original Brevo email configuration. They are not silently bypassed. Use the seeded accounts for local development until you configure email delivery. Physical shipping, real library inventory and production accounts require the original data.

## Using the original system's data later

Obtain an authorized `mongodump` export from the original machine. Restore it to a **new local database**, keeping `luminar_local` as your sample sandbox. Do not point your development APIs at the original live database unless that is deliberately intended. Set `MONGO_DB_NAME` to the restored database, configure a separate `LUMINAR_SEARCH_INDEX_DIR` and `LUMINAR_LEXICAL_PATH`, and use the repository's ordinary index builders against that database. The local seed and local supervisor deliberately reject that profile.

Copy the original authorized full texts and matching `rag/book_index`, `rag/book_chunks`, `rag/processed` and graph assets if available, or rebuild them with the repository ingestion scripts. Catalogue records alone cannot reconstruct full book text. Keep JWT and Brevo keys in `.env`, outside Git and shared archives. This local setup never modifies the original machine.
