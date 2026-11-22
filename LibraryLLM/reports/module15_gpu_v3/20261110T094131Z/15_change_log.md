# LuminaR Module 15 GPU V3 — Minimal Change Log and Preservation Audit

- **Verification Track**: Module 15 GPU V3 (`reports/module15_gpu_v3/20261110T094131Z/`)
- **Base Git HEAD**: `606f0dfce3970bea8e6fc2b62d243433d1a66b8a`
- **Git Branch**: `codex/search-v11-finalization`
- **Pre-change Hash Baseline**: `15_source_hashes.json` (211 source/test/config files hashed at `2026-11-10T09:41:47.741470+00:00`)
- **Post-change Hash Verification**: `15_source_hashes_post_change.json` (`2026-11-10T12:36:20.640854+00:00`)

## 1. Architectural Preservation Scope

Across all 211 hashed repository files in `15_source_hashes.json`:
- **209 files** remained byte-for-byte **unchanged** (`missing: []`), including:
  - `assistant/ROUTER_FREEZE.md` (SHA-256 `530e847aa8dd2a5ab68c14aad30ebcdc650fb21b6b6d869f4c98c464d0bce78d`), preserving `ASSISTANT_ROUTER_MODE=existing_qwen` as the active default.
  - `rag/qa.py` (SHA-256 `4a1141649a4ce9b4bce6413627c27557f5817bb8718a4e842a4d12021bd89de3`) and `rag/llm.py` (SHA-256 `d369e26fcbe458964bf642a057ca79212a63f48a6acf2b1c0a12590003f5cc1b`).
  - `assistant/schemas.py`, `assistant/api.py`, `assistant/routing.py`, `assistant/state.py`, `assistant/tools.py`, `rag/retriever.py`, `rag/reranker.py`, `rag/document_grounding.py`, `rag/services/*`, `backend/*`, `search/*`, and `frontend/*`.
- Historical baseline directories `reports/module15_gpu_verification/` and `reports/module15_gpu_v2/` were preserved untouched (UTC timestamps `05-11-2026 04:xx`).

## 2. Modified Runtime Files (2 of 211)

| File | Pre-change SHA-256 (bytes) | Post-change SHA-256 (bytes) | Scope of Minimal Fix |
| :--- | :--- | :--- | :--- |
| `LibraryLLM/assistant/qwen.py` | `15b153cd6616ca95ef3c62b8416ab37f04be60a224205b1aadfcc30d9155b30d` (28,982 B) | `ea7e2952eed6f0d9cd65b39472dd6d45daf1273a871a6cde89b7d76dca3d4eb2` (30,267 B, +1,285 B) | `QwenGateway.parse` prompt disambiguation and compact `"i"`-first examples (lines 256–325). |
| `LibraryLLM/assistant/orchestrator.py` | `c0be3c0fae83301496097043af4429ddd6a1c73c40839172241af461207b1730` (75,141 B) | `7b299d20ec86fe980ec9a37fe70bc749369237b6ef65d5a3054a384b852a023a` (75,164 B, +23 B) | Added `READING_LIST_PENDING` to literal-title precedence check (line 227). |

## 3. Summary of Behavioral Changes Implemented

1. **Compact Prompt Definitions & Disambiguation Rules (`assistant/qwen.py:256-325`)**:
   - Explicitly distinguished account retrieval vs. reading-list operations within the compact `existing_qwen` system prompt: `loans` vs. `reservations` vs. `history` vs. `fees` vs. `list` vs. `add_list` vs. `remove_list` vs. `clear_list` vs. `unknown`.
   - Added generalizable `"i"`-first few-shot examples covering account tools (`loans`, `history`, `fees`), reading-list reads/mutations (`list`, `add_list`, `remove_list`), and `document_id` targeting prior to `'Examples (with a selected pair unless stated otherwise): '`.
   - Added explicit structural rule: `'Topic search (s=none,i=search) and s=account never emit e or d.'` and changed ambiguous phrasing `"list the volumes..."` to `"show the volumes..."`.
   - Preserved `_reference_examples`, output schemas, model/lock lifecycle, and `close()`.
2. **Literal-Title Precedence on Reading List Mutations (`assistant/orchestrator.py:227`)**:
   - Updated line 227 from `ENTITY` only to `ENTITY | READING_LIST_PENDING | {Intent.GENERAL_LIBRARY_HELP}` so requests that explicitly name a target book title (e.g., `"Remove Synthetic Astronomy from my reading list"`) are not wrongly stalled in a clarification state when a valid literal title overrides ambient context.

## 4. Verification Workspace Artifacts (Non-runtime)

- Test runners & harnesses created under `LibraryLLM/.scratch/module15_gpu_v3/` (isolated disposable `mongod` via `isolation.py`, never touching database `luminar_library` on port `27017`).
- V3 evidence outputs and screenshots saved exclusively under `LibraryLLM/reports/module15_gpu_v3/20261110T094131Z/`.

