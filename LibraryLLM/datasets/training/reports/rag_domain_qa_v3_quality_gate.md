# LuminaR domain QA v3 high-precision gate — 2026-09-27

**EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS**

**Decision B. PROPOSITION EXTRACTION STILL TOO UNRELIABLE — REVISE EXTRACTORS.** The 50-source pilot yielded **5 AUTO_VALIDATED candidates**, below the required **10** for a real human-review packet. All five were already seen in the 20-chunk mechanics probe, so the pilot did not independently confirm their quality. No candidate is REVIEWED. The training gate remains CLOSED.

## 1–5. Why v3 changed the architecture

V2's free-form Qwen extractor proposed 48 propositions/questions from 50 TRAIN chunks but produced 26 grounding failures, 21 semantic failures, 1 AUTO_CHECKED, and 0 AUTO_VALIDATED. V3 keeps the v2 validator unchanged. It segments source text, matches a closed family of source-clause patterns, assigns the relation/category/answer slot in code, builds a template question, and only then sends HIGH-confidence candidates through v2 validation. Qwen cannot define a v3 fact. The closed enum has `ACTION`, `ENTITY_RELATION`, `LOCATION_AT`, `LOCATION_FROM`, `LOCATION_TO`, `TEMPORAL_AT`, `TEMPORAL_BEFORE`, `TEMPORAL_AFTER`, `CAUSE`, `MOTIVATION`, `INSTRUCTION`, `STATEMENT`, `ATTRIBUTE`, `STATE_CHANGE`, and `SEQUENCE`. Unsupported relations return no proposition.

The active extractor registry runs **INSTRUCTION → ENTITY_RELATION → CAUSE → MOTIVATION → LOCATION → TEMPORAL → STATEMENT → ACTION → ATTRIBUTE**. Specific patterns therefore take priority over generic action. This pilot has no HIGH rule for STATE_CHANGE or SEQUENCE; their enum membership is not a claim of implementation. Likewise, BEFORE/AFTER temporal relations are represented but not emitted by a HIGH extractor yet.

## 6–10. Clause, participant, source span, and dedup rules

The deterministic segmenter retains character offsets, avoids splitting `Mr.`, `Mrs.`, `Dr.`, `St.`, and decimal points, and divides clauses on `;` and `:`. It keeps `because`, `after`, `before`, and conjunctions attached to the local clause so an extractor can see both sides of a relation. This is deliberately conservative segmentation, not a syntactic parser. No NLP model was downloaded; package inspection found no local spaCy or Stanza parser. Each candidate stores sentence and clause boundaries, exact evidence, and available subject/predicate/object/cause/effect/location/time/answer source spans.

Named participants are preferred. A name inside a preceding prepositional phrase, such as **“letter from Mr. Collins arrived,”** is disallowed as the event subject. This was a real error found in the first mechanics probe, corrected generically, and covered by a regression test. Same-sentence pronouns may resolve only to one unique earlier named antecedent, with `HIGH` method/confidence recorded; ambiguous and context-free pronouns fail. The current extraction path uses this narrow resolution for location subjects. It does not guess antecedents from book knowledge or broad prior discourse.

Proposition fingerprints hash work ID, authoritative evidence offsets, relation, asked slot, and normalized slot values. QA fingerprints add normalized question and answer. This collapses identical source propositions across overlapping 220-token chunks. Stored source text remains untouched; NFKC, casefold, whitespace, and quote normalization are comparison-only. The answer surface and normalized answer are both retained.

## 11–15. Category, answer, template, and optional Qwen behavior

An extractor owns its relation. It deterministically maps `INSTRUCTION` and `STATEMENT` to factual/event QA, kinship to `ENTITY_RELATION`, location directions to `LOCATION`, time to `TEMPORAL`, explicit because-clauses to `CAUSAL`, named intentions to `MOTIVATION`, and triggered actions to `EVENT`. The selected source slot determines PERSON, LOCATION, TIME, CAUSE, EVENT, or PHRASE answer type. Template questions ask only for that slot and preserve source relation direction. The v3 source-span precheck then verifies every stored slot against the authoritative source; the unchanged v2 validator checks semantic/WH/referent/dedup/decontamination constraints.

Qwen paraphrasing was **disabled** for both v3 runs: 0 attempted, 0 accepted. The optional paraphrase guard compares participants, answer, and FROM/TO or BEFORE/AFTER cues, then reruns validation; it keeps the template if a paraphrase drifts or lacks a dependable semantic judgment. An optional strict-JSON local judge now checks schema, booleans, and an exact supporting quote, permits at most one retry, and returns `UNCERTAIN` after invalid JSON. It was not invoked in the pilot. Structural failure always takes precedence over any judge result.

## 16–17. Twenty-chunk extractor probe and gate

The deterministic, source-first [probe](rag_domain_qa_v3_extractor_probe.json) covered **20 TRAIN chunks**, **164 sentences**, **202 clauses**, and **17 relation matches**. After authoritative-offset deduplication it retained **5 HIGH**, **10 MEDIUM**, and 2 removed duplicates. All 5 HIGH passed v2 validation; MEDIUM stayed diagnostic. The assistant inspected the five HIGH source clauses in the probe packet: Miss Temple instructing Helen Burns, Bill wanting to kill Turner, Georgiana going to Ramsgate, Camilla as Mr. Pocket's sister, and Van Helsing asking Mrs. Harker. No obvious participant reversal, unsupported relation, location/temporal direction error, or invented cause remained after the generic “from Mr. Collins” fix. The automated structural and assistant spot gates therefore passed **for running a 50-chunk pilot only**; this was not human REVIEWED approval. [Probe Markdown](rag_domain_qa_v3_extractor_probe.md) shows each source clause, proposition, template, answer, and validation result.

## 18–20. Fifty-source pilot, per-relation yield, and failures

The bounded seed-42 pilot used **50 distinct TRAIN chunks**, balanced over the 12 TRAIN books. It examined **451 sentences**, **547 clauses**, and **24 pattern matches**. Four overlapping-source propositions were removed. It retained **5 HIGH**, **15 MEDIUM**, and no LOW; built and validated five HIGH template questions; attempted no paraphrases; and produced **5 AUTO_VALIDATED**. No HIGH candidate failed the validator. All five overlap the probe's five HIGH propositions, a limitation explicitly recorded in the [generation audit](rag_domain_qa_generation_audit_v3.json) and [Markdown audit](rag_domain_qa_generation_audit_v3.md).

| Relation family | Matches | HIGH validated | MEDIUM | Duplicates |
|---|---:|---:|---:|---:|
| ACTION | 0 | 0 | 0 | 0 |
| ENTITY_RELATION | 1 | 1 | 0 | 0 |
| LOCATION (TO; FROM/AT 0) | 1 | 1 | 0 | 0 |
| TEMPORAL_AT | 1 | 0 | 1 | 0 |
| CAUSE | 0 | 0 | 0 | 0 |
| MOTIVATION | 4 | 1 | 2 | 1 |
| INSTRUCTION | 2 | 2 | 0 | 0 |
| STATEMENT | 0 | 0 | 0 | 0 |
| ATTRIBUTE | 15 | 0 | 12 | 3 |

The underlying classifier found can-match cues in 29 entity-relation clauses, 22 temporal, 18 attribute, 12 location, 10 causal, 8 instruction, 7 action, 5 motivation, and 2 statement clauses; most lacked the stricter explicit pattern. The v2 validator's spelled-out clock-time rule held one temporal extraction at MEDIUM rather than changing v2. The dominant failure is **low HIGH-confidence extraction coverage**, not validator rejection of the emitted HIGH examples. No HIGH rejection codes were recorded. This does not establish that unextracted facts are absent from the books.

## 21–29. Safety counts and review gate

Among emitted HIGH candidates: unresolved referent **0**, wrong-role answer **0**, relation-direction error **0**, unsupported causal answer **0**, answer-type mismatch **0**, evaluation-query leakage **0**, and TEST leakage **0**. These are small-sample observed counts, not estimated false-negative rates. **Four** duplicate propositions were removed before question validation. All five HIGH candidates passed independent read-only [v3 revalidation](rag_domain_qa_validation_v3.json). The source-first [engineering diagnostic](rag_domain_qa_v3_diagnostic.md) displays the five candidates with template/final question, proposition, evidence, and validation. It is **not** a human-review packet. Because 5 < 10, no `rag_domain_qa_review_v3.md` or CSV was rendered; review packet row count is **0** and human review is **NOT YET COMPLETE**.

## 30–33. Tests, files, production safety, and decision

Added `scripts/rag_domain_qa_v3.py`, `rag_domain_qa_v3_judge.py`, `probe_rag_domain_qa_v3.py`, `build_rag_domain_qa_candidates_v3.py`, and `audit_rag_domain_qa_v3.py`; extended `validate_rag_domain_qa_candidates.py` with a v3 read-only path; and added `tests/test_rag_domain_qa_v3_extractor.py`. All outputs are versioned under `datasets/training/`; v1/v2 artifacts remain intact. **69 focused tests passed, 0 failed**, including all 41 prior v2 validator/domain tests and new closed-enum, extraction, role, direction, cause, source-span, overlap-dedup, template, paraphrase-drift, and judge-fail-closed tests. New scripts compile.

Frozen corpus, mapping, manifest, source map, and evaluation-label hashes match their control. TRAIN/VALIDATION/TEST book partitions remain disjoint; the pilot used TRAIN only and excluded chunks overlapping accepted DRAFT evaluation spans. The 64-file production snapshot reports **zero changes**. No production RAG/index/model/retriever/reranker/LLM, catalogue indexes, Mongo catalogue, evaluation question/span, or TEST work was changed. No final hard negatives were mined. No C or D training occurred. The existing training gate remains CLOSED with 0 REVIEWED TRAIN, 0 REVIEWED VALIDATION, and no reviewed negatives or training Parquet.

**Next:** broaden high-precision source-clause extractors without weakening v2, then use a fresh versioned mechanics probe and an independent bounded pilot. The current five template questions are useful diagnostics but do not satisfy the ≥10 review threshold or the later supervised-training requirements.
