# Search Intelligence V2C-B: precondition blocker

FINAL: FAIL at the mandatory precondition gate. V2C-B implementation was not started.

V2C_A_PRECONDITION_PASS: NO.

The supplied V2C-B prompt explicitly requires stopping when Search Intelligence V2C-A is missing, failing or partial. The actual repository has the accepted V2A/V2B parser and evidence, but no accepted Search Intelligence V2C-A implementation or reports. Existing `institution_v2c_*` files concern a different circulation/reservation/fee feature batch and do not satisfy this gate.

## Missing required acceptance evidence

All five files are absent under `D:\SDC\LibraryLLM\reports`:

- `search_v2c_a_final_qa.json`
- `search_v2c_a_confidence.json`
- `search_v2c_a_leftover_analysis.json`
- `search_v2c_a_browser.json`
- `search_v2c_a_preservation.json`

## Actual interfaces inspected

- `search/query_plan.py`: `PARSER_VERSION = 'search-v2a-deterministic-1'`; `QueryPlan`; `parse_query(query, facets=(), mode='SMART', filters=None, omit=())`; `QueryPlan.public()`.
- `search/query_session.py`: V2B refinement delegates independent queries to that parser.
- `search/session_store.py`: accepted V2B scoped context lifecycle; no V2C-A decision/repair contract.
- Search/parser tests and report paths were searched for Search V2C-A, reusable recognizers, leftover analysis, query repair, ambiguity/conflict decisions and slot confidence. No Search V2C-A implementation or acceptance suite was found.

The existing `interpretation_confidence` float is real and was not ignored: it defaults to 1.0 and is adjusted for canonical facet matching. It does not provide per-slot acceptance, ambiguous numeric decisions, incomplete-constraint decisions, conflict metadata, or leftover-token validation. The public interpretation exposes chips/corrections and a subject notice, without those missing typed decisions.

## Executed parser evidence

Eight direct, read-only probes executed the real parser using the existing canonical Global facet snapshot `reports/search_v2a_facet_vocabulary.json`, which includes Fiction. They did not commit V2B context, invoke retrieval models, mutate the database, or manufacture a new vocabulary. Full plans and public interpretations are retained in `search_v2c_b_precondition.json`.

| Query | Actual result | Required V2C-A contract |
|---|---|---|
| `fiction books above rating of 3` | Subject Fiction; no rating bound; Topic `above of 3`; confidence 1.0 | Fiction + rating > 3; no garbage topic |
| `fiction about wizards above rating of 3` | Subject Fiction; no rating bound; Topic `wizards above of 3` | Preserve Wizards as topic; consume the complete rating expression |
| `fiction 4` | Ordinary semantic text `fiction 4`; no ambiguity decision; confidence 1.0 | Explicit ambiguous-number decision; do not infer a hard field |
| `books rated above 4 and below 3` | Rating > 4; Topic `below 3`; no conflict decision | Recognize both bounds and detect the conflict |
| `books rated above 4 and rated below 3` | Rating > 4 AND < 3 accepted; no conflict decision | Explicit contradiction detection |
| `after 2020 before 2000` | Year > 2020 AND < 2000 accepted; no conflict decision | Explicit contradiction detection |
| `online only and physical only` | ONLINE + PHYSICAL; Topic `only only`; no conflict decision | Detect exclusive-format conflict; consume constraint tokens |
| `fiction rating above` | Topic `fiction above`; no incomplete-constraint decision | Preserve incomplete rating intent as a typed decision |

In the numeric ambiguity probe, the parser does avoid inventing a rating. It still fails the gate because it does not mark the query ambiguous.

## Required V2C-A fixes before V2C-B can proceed

1. Implement and independently accept reusable, order-independent constraint recognizers and deterministic repair. Consume the full supported phrase, including `above rating of 3`, while preserving unrelated topic words.
2. Add leftover-token validation that distinguishes genuine semantic text from unconsumed operators, connectors and numbers. Preserve source-span evidence and avoid claiming confidence 1.0 for an unrecognized constraint.
3. Provide typed slot/plan decisions (or an equivalent explicit contract) for accepted, ambiguous, incomplete, unsupported and contradictory input. A facet-match confidence scalar alone is insufficient.
4. Detect contradictory rating/year ranges, exclusivity conflicts and relevant include/exclude conflicts before treating a plan as executable. Do not silently select one bound or discard the other into semantic text.
5. Add V2C-A regression coverage for the exact required phrases, reordered phrasing, topic preservation, ambiguous numeric input, incomplete input and contradictions.
6. Validate the parser in Global, TEST public and an authorized private tenant, with canonical scope vocabulary and accepted authorization boundaries. No V2C-A scoped validation is currently available; legacy V2A/V2B results cannot substitute for it.
7. Rerun V2B session, personalization/isolation, Recommendation and More Like This regressions against V2C-A. Prior passing V2B evidence is retained in `search_v2b_final_qa.json`, `search_v2b_regression.json` and the associated XML reports; it is historical evidence, not a new V2C-A pass.
8. Complete real Chromium V2C-A acceptance and preservation checks, then produce the five missing reports with observed results. Existing V2A/V2B browser closure is not V2C-A acceptance.
9. Once V2C-A passes, freeze that accepted baseline and rerun this V2C-B gate before implementing clarification, autocomplete or correction controls.

## Work performed and preservation

Only these two diagnostic reports were created for this request:

- `reports/search_v2c_b_precondition.json`
- `reports/search_v2c_b_precondition_blocker.md`

The JSON records source hashes before and after the read-only probes; all inspected parser, session, personalization and retrieval sources are unchanged. No application implementation was changed, no service was restarted, no HNSW/KG index was rebuilt, and no Qwen/model setting was changed.

V2C-B feature tests, new browser QA and performance benchmarks were not run because the mandatory precondition failed. No downstream PASS, security-leak absence or benchmark number is asserted. V2C-C and Part 2I were not started.

The next authorized step is to supply or separately implement and accept Search Intelligence V2C-A. This V2C-B request explicitly prohibits silently doing that work as part of this batch.
