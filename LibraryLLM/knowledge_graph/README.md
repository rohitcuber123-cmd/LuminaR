# Experimental catalogue graph (KG1–KG3)

Open the existing LuminaR frontend at `/experimental/kg` after signing in. The
Graph Lab link uses the existing header, footer and assistant overlay. Search by
title prefix or an exact work ID, explore connections, select nodes, and explicitly
request a comparison with the existing recommender.

The graph is a local SQLite snapshot of public Mongo catalogue metadata. It stores
Book, Author-name and Subject-label nodes with AUTHORED_BY and HAS_SUBJECT edges.
Names and labels are normalized with NFKC, case folding and whitespace collapse;
only pipe delimiters split strings. Author names are not verified identities.
No account, circulation, document content, embedding or generated text is stored.

Similarity is weighted cosine over all shared typed features. With N books and
feature degree d, weight is `(2 for author, otherwise 1) * (1 + ln((N+1)/(d+1)))`.
Each shared feature supplies a two-hop reason path, the two original catalogue
field values, its degree, and its additive contribution to the score. This is
metadata similarity, not a relevance probability. The map shows the strongest
three paths per returned book; the expanded evidence shows every path.

## Run locally

From `D:\SDC\LibraryLLM` in PowerShell:

```powershell
.\scripts\kg_services.ps1 -Frontend
# On a fresh checkout, build the full snapshot once:
.\.venv\Scripts\python.exe scripts\build_catalogue_graph.py
# With the snapshot and core/search/recommendation services ready:
.\.venv\Scripts\python.exe scripts\evaluate_catalogue_graph.py
# Focused verification:
.\.venv\Scripts\python.exe -m pytest tests\test_knowledge_graph.py -q
cd frontend
npx tsx --tsconfig tsconfig.app.json --test tests/knowledge-graph.test.tsx
npm run build
npm run lint
```

The completed full-catalogue snapshot already exists locally at
`knowledge_graph/data/catalogue.sqlite` (5.87 GB). The builder refuses to overwrite
either a completed or unfinished graph. `--output` can build a separate snapshot
for inspection; the API uses the default path. Archive a previous snapshot and
its reports before deliberately replacing the default. `--max-books` is available
for a bounded development build; its metadata identifies the limited scope.
Builds stream Mongo rows, use file-backed indexing, and publish the SQLite file
only after completion. Runtime connections are read-only and close after use.
No extra package, graph server, model download or Qwen worker is required.

## API and freshness

Core API port 8002 exposes authenticated `/experimental/kg/meta`, `/books`,
`/more-like-this` and `/compare`. The frontend proxies through `/api`. Requests
reuse current identity checks; limit is 1–50 and extra request fields are rejected.
Active loans and reservations are excluded for the current caller. Mongo live
eligibility is checked before returning books. A changed seed's author/subject
metadata returns 409; deleted, inactive or changed candidates are removed.
Filtering can produce fewer than k results: it does not silently replace the
snapshot or its scores. Titles can refresh without changing feature scores.

Comparison calls the actual existing port-8004 `/recommendations/from-book` API
with the same JWT, seed and limit. Failure returns 503; no substitute baseline or
comparison metrics are invented. KG does not change its candidates or reranking.

## Evidence and decision

`reports/knowledge_graph_final.md` explains the full build, 40 frozen comparison
seeds, coverage/diversity definitions, missingness, checks and limitations.
`reports/kg3_evaluation.json` retains per-seed results and reason paths.
`reports/kg3_seeds.json` freezes the catalogue selections.

KG4 is deferred. The mean paired subject-diversity delta is -0.0572 across 36
measurable pairs, exceeding the predeclared permitted decline of 0.05. There are
also no independent relevance or reader-utility labels. Different candidates
alone do not justify a hybrid reranking experiment.
