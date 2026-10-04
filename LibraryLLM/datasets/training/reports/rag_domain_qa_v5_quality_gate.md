# LuminaR Domain-QA V5 precision gate — 2026-09-28

**EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS. Training gate CLOSED.**

**Decision B. V5 PRECISION OR YIELD GATE STILL FAILS — REVISE AGAIN.** V5 fixed the known V4 precision failures in regression replay, but its fresh, balanced 40-chunk probe produced **zero relation matches**. The required eight AUTO_VALIDATED candidates were not present. The independent pilot, review packet, hard-negative mining, and model training were not run.

## Frozen V4 evidence and failure inventory (items 1–3)

V4 was **not rerun**, and no V4 artifact was rewritten. V5 read the saved `rag_domain_qa_v4_quality_gate.md`, `rag_domain_qa_v4_probe.json`, `rag_domain_qa_v4_probe_audit.json`, and `rag_domain_qa_v4_probe_ranges.json`. Their SHA-256 values are recorded in the [V5 failure inventory](rag_domain_qa_v5_v4_failure_inventory.json) and verified unchanged after V5. The 27 old HIGH propositions were classified as 14 STATEMENT_FRAGMENT, 4 STATEMENT_TOPIC, 1 ACTION_CONTEXT, 1 DISCOURSE_DEPENDENCY, and 7 CLEAN_REFERENCE.

## V5 precision rules (items 4–16)

The [V5 extractor](../../../scripts/rag_domain_qa_v5.py) reuses V4/V3 relations and source offsets. It stores extraction confidence, validator status, and source-audit status separately. New direct-speech HIGH candidates require an explicit named speaker, a source-grounded speech verb, an exact complete utterance, and exact speaker/verb/statement spans. V5 no longer invents a required statement topic from capitalized words. Vocatives remain inside statement content and cannot become the speaker or topic. Quotes ending in a dangling comma, lacking a predicate, starting an unresolved subordinate clause, or depending on a discourse antecedent are not HIGH. A conservative answer-slot sufficiency check runs before downstream validation. V4 ACTION candidates with a second coordinated predicate swallowed by context or object are downgraded; V5 does not turn that second action into a context anchor. The existing precedence and other relation families remain unchanged. V5 uses deterministic templates; Qwen paraphrasing is disabled. New reason codes cover statement fragments, unsupported topics, discourse dependence, coordinated action drift, and insufficient answer slots. The unchanged v2/v3 validator still decides AUTO_VALIDATED.

## Frozen V4 → V5 replay (items 17–23)

The [replay](rag_domain_qa_v5_v4_replay.md) read saved V4 source inputs; it did not regenerate V4. Of 27 old HIGH: **7 STILL_HIGH, 20 DOWNGRADED_MEDIUM, 0 REJECTED, 0 CHANGED_PROPOSITION** by exact proposition fingerprint. All 7 clean references remained HIGH and auto-validated. All 20 previously rejected cases were blocked upstream: 14/14 fragmentary statements, 4/4 unsupported topics, 1/1 action-context drift, and 1/1 discourse-dependent quote. **Zero known V4 failures still auto-validated.** This is regression evidence, not fresh quality evidence. The replay retains complete per-candidate transitions and reasons in [JSON](rag_domain_qa_v5_v4_replay.json).

## Focused tests and fresh V5 probe (items 24–43)

The focused v2/v3/v4/v5 suite passed **80 tests, 0 failures**. New tests cover explicit quote attribution, optional topic, vocative/speaker distinction, capitalized pseudo-entities, fragments, unresolved discourse, coordinated-action drift, frozen replay, and source-range overlap.

The fresh [V5 probe manifest](../manifests/rag_domain_qa_v5_probe_ranges.json) selected **40 TRAIN chunks with seed 101**, balanced across the 12 TRAIN books without relation quotas. All selected authoritative source ranges were checked against the frozen V4 probe: **0 overlapping ranges**, including overlapping chunks with distinct IDs. There was no V3 range manifest to apply. The canonical source-range digest is `9cda457265e143fa9714cb400b25f852b613239b0f58aae974b632edacd0b056`; the manifest file SHA-256 is `e35bb1bbd503d6e15b4fbc1b05a52591edda38a752ff960de1d9d29bbd29ddae`.

The [fresh probe](rag_domain_qa_v5_probe.md) covered **373 sentences, 444 clauses, and 158 can-match cues**, but yielded **0 relation matches, 0 extracted HIGH, 0 MEDIUM, 0 LOW, 0 duplicates, and 0 answer-slot sufficiency rejects**. Validator-passing HIGH, validator-failing HIGH, and AUTO_VALIDATED were all **0**. The extracted-HIGH validator pass rate is defined as **0.0 for an empty denominator** for gate evaluation; it is not an empirical precision estimate. The [source-audit record](rag_domain_qa_v5_probe_audit.md) has 0 CLEAN and 0 REJECTED because there were no candidates to inspect. Thus the fresh probe observed 0 statement/action/fragment/role/direction/discourse failures, but cannot establish precision. TEST leakage and accepted evaluation-span leakage were **0** under the frozen TRAIN pool controls. The required ≥8 AUTO_VALIDATED and ≥80% HIGH validation gates failed. **V5 probe gate: FAIL.**

## Gated work, safety, and next decision (items 44–50)

No 120-chunk independent pilot or pilot manifest was created; pilot per-relation yield and source-range independence are not applicable. Review-packet row count is **0**; human review status is **NOT REVIEWED**. The saved 64-file production SHA-256 snapshot has **0 changed files**. Production RAG chunks/indexes, embedding model, retriever, reranker, answer LLM, catalogue indexes/Mongo/CRUD, evaluation questions and accepted spans, and TEST works were not changed. No hard negatives or Model C/D training occurred.

New files are `scripts/inventory_rag_domain_qa_v5.py`, `scripts/rag_domain_qa_v5.py`, `scripts/replay_rag_domain_qa_v4_with_v5.py`, `scripts/probe_rag_domain_qa_v5.py`, `scripts/audit_rag_domain_qa_v5.py`, `tests/test_rag_domain_qa_v5_extractor.py`, and versioned V5 reports/manifest/JSONL diagnostics under `datasets/training/`. V1–V4 artifacts remain frozen. The fresh zero-yield sample does not prove deterministic extraction has reached its limit; it does show that the repaired rules did not produce an independently testable V5 set. Further work should examine unmatched explicit structures in this new sample before any new probe or pilot.

## Reproduction commands

```powershell
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe -m pytest tests\test_rag_domain_qa_validator.py tests\test_rag_domain_qa_v3_extractor.py tests\test_rag_domain_qa_v4_extractor.py tests\test_rag_domain_qa_v5_extractor.py -q
.\.venv\Scripts\python.exe scripts\replay_rag_domain_qa_v4_with_v5.py
.\.venv\Scripts\python.exe scripts\probe_rag_domain_qa_v5.py --chunks 40 --seed 101 --exclude-prior-probe-ranges --precision high
.\.venv\Scripts\python.exe scripts\audit_rag_domain_qa_v5.py --probe
```

The replay reads frozen V4 files; it does not run the V4 generator. The V5 probe command regenerates V5 artifacts and is provided only for reproducibility, not as authorization to bypass the failed gate. The independent pilot remains blocked.
