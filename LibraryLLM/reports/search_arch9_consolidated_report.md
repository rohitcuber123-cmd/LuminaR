# LuminaR Smart Search Engineering — Combined V9 Consolidated Report
## Architectural Recovery & Practical Learned Extractor Comparison
**Candidate ID**: `search-smarteng-disabled-proof-9`  
**Execution Timestamp**: `2026-10-29T14:10:00Z`  
**Status**: `CANDIDATE_DISABLED = true` | `STAGING_READINESS = BLOCKED` | `PRODUCTION_READINESS = BLOCKED`  
**Architecture Decision**: `PATH_C` (Neither architecture is currently adequate for unconstrained production qualification)

---

## 1. Executive Summary

This engineering milestone executes LuminaR Combined V9 under strict historical preservation and isolation controls. Rather than repeating the pattern of achieving artificial 100% scores on exposed phrases while failing unfamiliar natural language, V9 addresses the underlying architectural causes:

1. **Deconstructed Pipeline**: Refactored monolithic parsing into three distinct, non-circular contracts:
   - **Contract A (Interpretation)**: Proposes candidate semantic units and domains without assuming execution authority.
   - **Contract B (Validation)**: Validates proposals against an authoritative Capability Registry and independent source-obligation scanner.
   - **Contract C (Planning)**: Emits native `QueryPlan` only for fully validated operations.
2. **Eliminated Unsafe Execution**: Completely eliminated all 12 unsafe false execution recommendations from the exposed V8 baseline (achieving **0/138 false execution** on the 205 exposed V8 cases and **0/360 false execution** across all 4 historical cohorts).
3. **Regression Recovery**: Resolved 265 seeded compositional failures caused by domain-obligation wiping, reaching **1,757 passed / 2 failed / 6 deselected** on broad regressions. The 2 remaining failures reflect explicit, documented native capability boundaries (title-only substring exclusion and missing operand `pages`).
4. **Constrained Decoding & Compact Adapter**: Analyzed the root causes of Qwen2.5-3B-Instruct extraction failures (38.8s latency, character offset arithmetic failure, domain/enum hallucinations) and implemented a compact proposal schema with deterministic span resolution and `lmformatenforcer` JSON schema enforcement.
5. **Rigorous Architecture Decision (Path C)**: Based on measured empirical evidence (50.0% typed accuracy and 10.4% false execution on the newly reviewed 72-query development cohort; 2.60 GB available host RAM breaching the 7.25-7.78 GB guarded model loading threshold; 11.8s-38.8s model latency disqualifying hot-path deployment), V9 explicitly reports **Path C** with concrete development prerequisites rather than prematurely declaring production readiness.

---

## 2. Integrity and Preservation Verification

Before and after implementation, all repository assets were verified against preflight checksums:
- **Protected Entries Checked**: 5,584 / 5,584 (0 missing, 0 mismatched).
- **Production Files Modified**: 0 (Production parser, C4 policy, frontend, and routing unchanged).
- **Database Writes**: 0 (Zero MongoDB writes across all databases).
- **Index Rebuilds**: 0 (Zero HNSW or KG rebuilds).
- **External Network / Model Downloads**: 0 (Zero weight downloads or remote inference calls).
- **Historical Evidence Preserved**: All historical reports (`search_combined8_*`, `search_arch9_initial_*`, `search_arch9_repair1_*`) remain intact in exclusive read-only status.
- **Preservation Report**: [search_arch9_preservation.json](file:///D:/SDC/LibraryLLM/reports/search_arch9_preservation.json).

---

## 3. Major Step 1: Query Interpretation Architecture Recovery

### 3.1 All-205-Case V8 Generalization Failure Matrix
We diagnosed all 205 exposed V8 primary cases across 42 linguistic families to identify the first incorrect pipeline stage:
- **First Incorrect Stage Breakdown**:
  - `4. Required/advisory modality`: 56 cases (advisory framing overblocking valid search).
  - `10. Capability checking`: 24 cases (unsupported pages/price/publisher escaping validation).
  - `5. Operator ownership`: 20 cases (exact title paraphrases becoming broad `title_text`, sort arguments converted into author tokens).
  - `9. Missing/unknown classification`: 11 cases (missing `by:` operands, disjunctions `either/or`).
  - `7. Operand extraction`: 7 cases (trailing clause absorption dropping named authors).
  - `3. Source-role interpretation`: 6 cases (metalinguistic negation treated as data exclusions).
  - `6. Field/domain identification`: 6 cases (misbinding operands to incorrect fields).
- **Fault Layer**: Validation (24 cases), Interpretation (97 cases), Planning (9 cases).
- **Deliverables**: [search_arch9_root_cause_matrix.json](file:///D:/SDC/LibraryLLM/reports/search_arch9_root_cause_matrix.json) and [search_arch9_root_cause_matrix.md](file:///D:/SDC/LibraryLLM/reports/search_arch9_root_cause_matrix.md).

### 3.2 Authoritative Versioned Native Capability Registry
Formalized LuminaR native backend capabilities and scope masks in `reports/search_arch9_capability_registry.json` (`V9-capability-registry-v1`):
- **Scope Capability Masks**:
  - `GLOBAL`: Rating (✓), Year (✗), Language (✗), Formats (`ONLINE` only), Availability (✗), Sort (✓).
  - Institutional Scopes (`PUBLIC_TENANT_*`, `PRIVATE_TENANT_*`): Rating (✓), Year (✓), Language (✓), Formats (`PHYSICAL`, `ONLINE`, `BOTH`), Availability (✓), Sort (✓).
- **Contract Boundary Conflict Resolutions**:
  - *Title-Only Substring Search*: Inherited legacy test `test_quoted_filter_words_owned_by_literal_title` expected title-only substring matching. Native `QueryPlan` maps titles to `title_text` which cross-matches authors. V9 formally refuses to advertise or execute this operation, maintaining `UNSUPPORTED` safety.
  - *Page Count & Price*: LuminaR is an institutional library lending catalog without page count or commercial price indexing. All mandatory page/price constraints safely return `UNSUPPORTED`.
- **Deliverable**: [search_arch9_capability_registry.md](file:///D:/SDC/LibraryLLM/reports/search_arch9_capability_registry.md).

### 3.3 Metamorphic Properties & Compositional Tests
Expanded `test_compositional_properties.py` to 42 property tests (100% pass rate):
- Proved ordinary topical vocabulary (`books about uncertainty in climate forecasting`, `books discussing book prices`, `historical accounts of library editions`) remains `EXECUTABLE`.
- Proved mandatory unsupported attributes (`books with price under $20`, `require page count under 300 pages`) safely reject as `UNSUPPORTED`.
- Proved author entity replacement invariance across diverse authors.
- Proved explicit placeholder author (`books by [...]`) yields `INCOMPLETE` targeted clarification.

---

## 4. Major Step 2: Practical Learned Extractor Comparison & Resource Safety

### 4.1 Root Cause Analysis of Prior Qwen2.5-3B Captures
Analysis of `reports/search_proof8a3_model_capture.json` revealed:
- **Excessive Latency**: 11,810 ms to 38,844 ms per query (200x–800x above interactive search budget).
- **Arithmetic & Offset Failures**: The model failed integer character arithmetic (e.g. `start: 14, end: 28` for a 39-character string).
- **Hallucinated Domains & Enums**: Generated `USER_REQUESTED_OPERATION` as a domain and `MandatorySearchCondition` / `EQUAL` as invalid enums.
- **Zero Valid Outputs**: 0 / 2 raw captures satisfied schema validation.

### 4.2 Compact Proposal Interface & Constrained Decoding
To eliminate model character-arithmetic and enum hallucinations, we engineered:
1. `CompactConstraintProposal`: Model outputs only intent, constraint type, exact source substring, modality, and state.
2. Deterministic Resolver: Unambiguously maps literal substrings to unique `(start, end)` spans, strictly rejecting fabricated or ambiguous repeated occurrences.
3. `lmformatenforcer` Integration: Built and verified a schema parser enforcing valid JSON generation.
- **Deliverables**: [extraction_compact.py](file:///D:/SDC/LibraryLLM/scratch/search_architecture_v9/extraction_compact.py) and [test_extraction_compact.py](file:///D:/SDC/LibraryLLM/scratch/search_architecture_v9/test_extraction_compact.py) (5/5 passed).

### 4.3 Hardware Resource Headroom Gate
Direct measurement on the RTX 5060 host:
- **Host System RAM**: 15.31 GB Total, **2.60 GB Available (83.0% used)**.
- **GPU VRAM**: 8,150.6 MB Total, **7,043.0 MB Free**.
- **Resource Gate Decision**: Prior guarded BF16 execution required a minimum available RAM threshold of 7.25–7.78 GB (worker memory cap + platform reserve + safety margin). Launching a 3B model under current headroom (2.60 GB) would violate resource safety invariants and risk OS/IDE thrashing. Per Section 12/14 instructions, no doomed model load was launched.

---

## 5. Quantitative Evaluation Summary

### 5.1 Historical Exposed Cohorts (V9 Candidate `repair2`)
| Cohort | Contexts | Typed Accuracy | Execution Accuracy | False Execution | Missed Execution | Critical Operands |
|---|---:|---:|---:|---:|---:|---:|
| `c5e90` | 90 | 90 / 90 (100.0%) | 90 / 90 (100.0%) | **0 / 60 (0.0%)** | 0 / 30 (0.0%) | 0 |
| `c5er150` | 150 | 150 / 150 (100.0%) | 150 / 150 (100.0%) | **0 / 100 (0.0%)** | 0 / 50 (0.0%) | 0 |
| `smarteng150` | 150 | 145 / 150 (96.7%) | 145 / 150 (96.7%) | **0 / 100 (0.0%)** | 5 / 50 (10.0%) | 0 |
| `comp3_150` | 150 | 111 / 150 (74.0%) | 137 / 150 (91.3%) | **0 / 100 (0.0%)** | 13 / 50 (26.0%) | 0 |
| **Total** | **540** | **496 / 540 (91.9%)** | **522 / 540 (96.7%)** | **0 / 360 (0.0%)** | **18 / 180 (10.0%)** | **0** |

### 5.2 Exposed V8 Primary Cases (205 Contexts)
| Candidate | Typed Accuracy | Execution Accuracy | False Execution Rate | Critical Operands |
|---|---:|---:|---:|---:|
| V8 Baseline (`search-smarteng-disabled-proof-8`) | 86 / 205 (42.0%) | 146 / 205 (71.2%) | 12 / 138 (8.7%) | 31 / 32 |
| **V9 Candidate (`search-smarteng-disabled-proof-9`)** | **94 / 205 (45.9%)** | **158 / 205 (77.1%)** | **0 / 138 (0.0%)** | **5 / 32** |

### 5.3 Separately Reviewed Development Cohort (72 Contexts)
| Query Length Stratum | Total | Typed Correct | Execution Correct | False Execution | Missed Execution |
|---|---:|---:|---:|---:|---:|
| Short (≤ 60 chars) | 24 | 14 / 24 (58.3%) | 19 / 24 (79.2%) | 1 / 16 | 4 / 8 |
| Medium (61–150 chars) | 24 | 14 / 24 (58.3%) | 20 / 24 (83.3%) | 1 / 16 | 3 / 8 |
| Long (151–300 chars) | 16 | 6 / 16 (37.5%) | 12 / 16 (75.0%) | 2 / 11 | 2 / 5 |
| Very Long (301–500 chars) | 8 | 2 / 8 (25.0%) | 5 / 8 (62.5%) | 1 / 5 | 2 / 3 |
| **Total Dev72** | **72** | **36 / 72 (50.0%)** | **56 / 72 (77.8%)** | **5 / 48 (10.4%)** | **11 / 24 (45.8%)** |

---

## 6. Architecture Decision: PATH C

We officially report **PATH C** (Neither architecture is currently adequate for unconstrained production qualification).

### Rationale:
1. **Deterministic Parser Limitations**: While V9 successfully eradicated unsafe false executions across historical cohorts (0/360) and the 205 exposed V8 cases (0/138), its performance on the newly reviewed 72-query cohort drops to 50.0% typed accuracy and 10.4% false execution, especially on very long queries (25.0% typed accuracy).
2. **Learned Model Infeasibility**: The cached Qwen2.5-3B model cannot be safely loaded under current memory headroom (2.60 GB available vs 7.78 GB required), exhibited unacceptable latency (11.8s–38.8s per query), and failed schema validation in prior trials.
3. **Prerequisites for Future Acceptance**:
   - Establish a restricted supported-search grammar contract for interactive search.
   - Fine-tune task-specific compact extraction heads (500M parameter distilled models with int4 quantization).
   - Require minimum 16 GB host RAM headroom before scheduling local hybrid execution.
   - Maintain `search-smarteng-disabled-proof-9` in disabled status.
