# V6 source-first coverage-gap analysis of the frozen V5 probe

**DIAGNOSTIC ONLY — NO QA GENERATED. Training gate CLOSED.**

V5 was **not rerun**. This audit read its saved 40-chunk probe, audit, manifest, and empty high/medium/rejected JSONL diagnostics. Their SHA-256 hashes are recorded in [the cue inventory JSON](rag_domain_qa_v6_v5_cue_inventory.json). The frozen V5 source, source offsets, and hashes verified without error. All **158/158** can-match events were inspected; **0** were missing or unparseable. The [cue inventory](rag_domain_qa_v6_v5_cue_inventory.md) shows every clause, enclosing sentence, exact offsets, trigger, tentative surface slots, detector/extractor path, and no-match code. This is an audit of cues, not 158 valid QA opportunities.

The 158 cues yielded no candidates because the broad detector tests did not coincide with the much narrower concrete extractor patterns in these 40 chunks. A read-only detector replay found all 158 cue conditions again, while **zero** of the corresponding V4 concrete extractor regexes matched their clause surfaces. There is no evidence of a silent candidate-emission, enum, or offset bug causing the zero yield. The V5 quote diagnostic counter increments only after a quote candidate is emitted, so failed V5 quote scans are absent from the 158 total. That is a **metric/interface limitation**, not a demonstrated cause of zero output.

## Per-relation coverage

| Relation family | Cues | Matches | Most common gap | Plausible safe structures |
|---|---:|---:|---|---:|
| ATTRIBUTE | 95 | 0 | Generic/deictic copula, pronoun subject, unsupported complement | 1 |
| ENTITY_RELATION | 26 | 0 | Relation word without two grounded endpoints | 0 |
| LOCATION_AT/FROM/TO | 22 undirected motion cues | 0 | No named destination, idiom, or unresolved actor | 0 |
| ACTION | 12 | 0 | Pronoun actor or unsupported direct-object form | 2 |
| CAUSE | 2 | 0 | Because-clauses with unresolved event/cause referents | 0 |
| MOTIVATION | 1 | 0 | Unresolved actor | 0 |
| TEMPORAL_AT/BEFORE/AFTER | 0 | 0 | No detector cue in this sample | 0 |
| INSTRUCTION, STATEMENT, STATE_CHANGE, SEQUENCE | 0 counted | 0 | No counted detector cue; failed V5 quote scans are uncounted | 0 |

The detailed [machine-readable analysis](rag_domain_qa_v6_gap_analysis.json) gives each family’s reason distribution, extractor attempts, false-positive counts, and representative cue IDs. Because the LOCATION detector merely sees a motion verb, its 22 cues cannot honestly be assigned to AT/FROM/TO without a matched direction phrase.

| Detector family | Primary no-match reasons |
|---|---|
| ATTRIBUTE | false-positive cue 40; unsafe complement 27; unresolved pronoun 25; parser required 2; preceding-sentence subject 1 |
| ENTITY_RELATION | missing endpoint 25; parser required 1 |
| LOCATION (undirected) | destination missing 14; false-positive motion 6; ambiguous boundary 1; unresolved subject 1 |
| ACTION | unresolved subject 10; context/object ambiguity 2 |
| CAUSE | unresolved cause/effect subject 2 |
| MOTIVATION | unresolved actor 1 |

## Why the detectors fired without extraction

Across all 158 cues, the primary no-match codes are FALSE_POSITIVE_CUE **46**, SUBJECT_PRONOUN_UNRESOLVED **36**, ATTRIBUTE_COMPLEMENT_UNSAFE **27**, RELATION_ENDPOINT_MISSING **25**, LOCATION_DESTINATION_MISSING **14**, PARSER_REQUIRED **3**, ACTION_CONTEXT_AMBIGUOUS **2**, CAUSE_EFFECT_SUBJECT_UNRESOLVED **2**, OBJECT_BOUNDARY_AMBIGUOUS **1**, MOTIVATION_VERB_FOUND_BUT_ACTOR_UNRESOLVED **1**, and SUBJECT_ONLY_IN_PREVIOUS_SENTENCE **1**. One primary code is assigned per cue; the full source context remains available for finer future review.

The consistency classification is **81 DETECTOR_TOO_BROAD**, **29 EXPECTED_PRECISION_REJECTION**, **45 REQUIRES_DISCOURSE_REASONING**, **3 EXTRACTOR_TOO_NARROW_BUT_FIXABLE**, and **0 per-cue BUG_OR_INTERFACE_MISMATCH**. The source-opportunity classification is **83 FALSE_POSITIVE_CUE**, **72 AMBIGUOUS**, and **3 TRUE_STRUCTURAL_OPPORTUNITY**. The categories describe these exact cue events and should not be extrapolated to the whole corpus.

The [22-pattern frequency table](rag_domain_qa_v6_pattern_frequency.md) is sorted by count. Its largest structures are generic/deictic copulas **40**, pronoun copulas **25**, other noncanonical copulas **21**, kinship mentions without two endpoints **17**, motion without a named destination **14**, and pronoun actions **10**. Together these explain **127/158** cues. They are mostly detector breadth or unresolved roles, not a small hidden reservoir of safe QA facts. The two safely isolatable structures are named direct-object actions **2** and a named-person complex attribute **1**; neither warrants assuming that every surface match would pass v2.

No confirmed sentence/clause **boundary error** or source-offset drift caused a lost match. Three clauses need syntactic attachment beyond the current regex surfaces: a relative-clause antecedent, an inverted copula, and nested relative clauses. Quote punctuation and archaic dialogue appear in the probe, but the counted V4 cues did not show a recoverable statement blocked by a specific sentence split. The 45 discourse/coreference-classified cues include same-sentence antecedent candidates such as V6C-053 and V6C-150 and a preceding-sentence role at V6C-067; none yields a safe proposition for the relation that actually fired. Thus **0** same-sentence and **0** previous-sentence cues are counted as safely recoverable. The remaining participant-dependent cases need ambiguous prior, dialogue-turn, or broader discourse interpretation; their exact depth cannot be established from the local cue alone. No character gender, plot, or world knowledge was used.

Only **three** source structures merit a future high-precision rule investigation, across **two** patterns. The conservative lower-bound estimate is **one** likely recoverable proposition: Lady Catherine explicitly opened doors into named rooms (V6C-001). Alice’s direct-object action (V6C-147) is structurally clear but lacks an obviously specific v2-compatible template without invented context. Elizabeth’s “was determined to …” state (V6C-003) is explicit but its complete answer boundary and relation/category must be proven. See the [V6 implementation plan](rag_domain_qa_v6_implementation_plan.md) for required contracts, known unsafe variants, and tests. Neither pattern should absorb a coordinated second action, infer a quote topic, or depend on earlier discourse.

**Decision B. RULE-BASED EXTRACTION IS NEAR DIMINISHING RETURNS.** The frozen 40-chunk sample contains only 3 plausible safe structures, with a conservative recoverable lower bound of 1, far below the suggested ≥10 from ≤5 patterns for targeted expansion. There is no evidence that zero yield was primarily an implementation bug. This audit changes no extractor or validator and authorizes no new QA generation. A future task should decide whether a broader, separately reviewed source-annotation strategy offers better returns than further local regex expansion.

## Integrity, tests, and files

Frozen V5 SHA-256 values were: quality-gate report `3629cd17a98eade165e2f7b8d5c66b3b2121a18be77bf99b0fc7b66b0ead2833`; probe JSON `e20fa4a2efbc77cb7a8f8c05f43ab449fde198c436e81c6de50015c8016f8a31`; probe Markdown `6cbadb4eaed2c15a5c6e7cd4f2a261655d20cd564dcc809abf1b6d80d0a07fff`; probe audit Markdown `2b27c646274daa0261956625ca378777d79eae05c4985fe6ac16ce63feceaadc`; range manifest `e35bb1bbd503d6e15b4fbc1b05a52591edda38a752ff960de1d9d29bbd29ddae`. Each of the three empty high/medium/rejected JSONL files has SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. The [inventory JSON](rag_domain_qa_v6_v5_cue_inventory.json) records paths and hashes. A read-only check found all frozen V4/V5 artifacts unchanged, and the 64-file production snapshot had **0 changed files**.

Diagnostic-only tests: **3 passed, 0 failed**. Added `scripts/analyze_rag_domain_qa_v5_gaps.py`, `scripts/audit_rag_domain_qa_v6_gaps.py`, `scripts/summarize_rag_domain_qa_v6_patterns.py`, `tests/test_rag_domain_qa_v6_gap_analysis.py`, and the versioned V6 cue inventory, cue audit, gap analysis, pattern-frequency, and implementation-plan reports. No V1–V5 extractor, validator, candidate, source, evaluation, production index, or model was changed. **Training gate: CLOSED.**

Reproduce the read-only analysis from the saved probe with:

```powershell
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe scripts\analyze_rag_domain_qa_v5_gaps.py --probe-existing --version v6
.\.venv\Scripts\python.exe scripts\audit_rag_domain_qa_v6_gaps.py --all-cues
.\.venv\Scripts\python.exe scripts\summarize_rag_domain_qa_v6_patterns.py
.\.venv\Scripts\python.exe -m pytest tests\test_rag_domain_qa_v6_gap_analysis.py -q
```
