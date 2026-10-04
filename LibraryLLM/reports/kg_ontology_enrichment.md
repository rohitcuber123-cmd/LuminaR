# KG3.1 ontology enrichment evaluation

**PARTIAL: ontology V2 evaluated in two separate pilots; neither is promoted. Product More Like This passes using V1.** Full build gate fails useful-reason review even after a general vocabulary refinement. Phase 32 explicitly permits stopping here. No KG4 or hybrid candidate union is introduced.

Audit: `kg_ontology_enrichment_audit.md/json`. Frozen prior KG3 measurements and full V1 SQLite artifact remain unchanged (complete-file SHA-256 verified in `kg31_integrity_preservation.json`). Full V1 still has **5,000,000 books, 2,454,492 author-name nodes, 975,785 subject-label nodes, 29,406,707 edges**, **5,871,624,192 bytes**, original **882.81 s** build. Runtime graph remains `catalogue.sqlite`, version `kg1-2-metadata-cosine-v1`.

## Pilot method and configuration

The same **100,040 works** (every 50th catalogue book_id plus all original 40 frozen KG3 seeds) form both V1 and V2 populations. Selection precedes outcomes. Description phrases use deterministic contiguous 2–3 Unicode word phrases, NFKC/case-fold/whitespace normalization, English and conservative generic stop words, corpus TF-IDF ranking, lexical ties, ≤5 non-nested topics per book, first ≤512 tokens and ≥20-token descriptions. Phrase degree ≥3 and ≤0.1% of pilot books; retained topic degrees/norms are recomputed. Each topic edge stores the original source phrase and normalized-description SHA-256. No Qwen, new neural model, training, generated topic or title-derived metadata.

Relation amplitudes are explicit: author **2**, subject **1**, topic **0.5**. Existing IDF formula `(1 + ln((N+1)/(degree+1)))` and weighted cosine are preserved; equal-degree topic squared contribution is one quarter of subject contribution. This conservative untuned choice does not establish relevance. Unavailable publisher/language/era are never configured as qualification edges; only source-auditable author/subject/pilot-topic features qualify. Operational/rating values never enter graph similarity.

The refinement requires exact phrase membership in the full frozen V1 subject vocabulary. It is a global data-derived filter, not a seed-specific allowlist. It reduces vocabulary noise but still admits incidental medical mentions and `qui est` from noisy subject labels. Further tuning against the same 40 seeds would risk overfitting; neither pilot passes the reason gate.

| Artifact | Books | Author / subject / topic nodes | Edges | Bytes | Build / enrichment time |
|---|---:|---|---:|---:|---|
| Pilot V1 | 100,040 | 105,107 / 93,867 / 0 | 587,074 | 126,763,008 | 10.14 s |
| Initial V2 | 100,040 | 105,107 / 93,867 / 16,623 | 656,478 | 145,911,808 | 50.09 s including compaction |
| Refined V2 | 100,040 | 105,107 / 93,867 / 4,789 | 620,810 | 138,604,544 | 61.28 s including compaction |

Initial V2 attaches topics to **22,046** books (+69,404 edges); refined V2 to **15,642** (+33,736 edges). The initial complete pilot workflow took **66.82 s**. Artifacts live under `knowledge_graph/data/kg31_pilot_*.sqlite`, with separate versions. Builders stream rows and disk-backed phrase DF, stage copies and compact before atomic publication. The initial pilot's embedded `scope` says full catalogue because it means all supplied input; authoritative driver/evaluation reports explicitly identify the 100,040-book pilot. It is not a full-5M graph.

## Same-population V1 versus refined V2

40 original frozen seeds; three warm local SQLite queries per seed/method; no API hydration time in these pilot timings. **1,224** paths checked against original fields/description hashes; every score equals its summed feature contributions. Same population and ranking conditions; this coverage must not be compared to the full V1 95% KG3 coverage as if populations were equal.

| Metric | Pilot V1 | Refined pilot V2 |
|---|---:|---:|
| Nonempty seed coverage | 0.875 | 0.9 |
| Full Top10 | 0.775 | 0.775 |
| Unique candidates | 313 | 321 |
| Subject diversity | 0.846482 | 0.852724 |
| Same-seed author concentration | 0.06 | 0.0583333 |
| Relationship type diversity | 1.01242 | 1.03333 |
| Reasons per result | 1.88509 | 1.8697 |
| Generic reason fraction (degree ≥1%) | 0.107084 | 0.100486 |
| Topic-only results | 0 | 8 |
| Query median ms | 5.18 | 5.23425 |
| Query p95 ms | 28.7753 | 31.6245 |
| Query maximum ms | 40.4119 | 38.4653 |

Mean top10 overlap **0.8575**; paired subject-diversity delta **+0.001910**. Contribution fractions author/subject/topic: V1 **3.58% / 96.42% / 0%**, refined V2 **3.49% / 93.73% / 2.78%**. Coverage 35/40→36/40, full top10 stays 31/40. Unique candidates rise 313→321; this is metadata novelty, not a relevance gain. Initial unrestricted V2 had 328 unique candidates, 33/40 full lists, 15 topic-only recommendations and **−0.001945** paired diversity delta. Full per-seed evidence remains in `kg_v1_vs_v2.json`; refined evidence is in `kg31_v1_vs_v2_subject_vocab.json`.

The automatic `strong_or_moderate_reason_fraction = 1` is **only nominal relation-type eligibility**. It does not mean 100% useful reasons. Below is agent qualitative review of all 15 refined topic-bearing candidates; it is not independent human/reader relevance labeling. All 21 initial examples and all 15 refined examples also retain source excerpts in JSON.

| Seed → candidate | Description topics | Usefulness review |
|---|---|---|
| Fundamentals of Deep Learning → Computational trust models and machine learning | machine learning | PLAUSIBLE: specific shared subject/theme visible in both descriptions; no independent reader relevance label. |
| Dernier cahier → Biografía del Dr. Fernando Bolet, 1818-1888 | public health | PLAUSIBLE: specific shared subject/theme visible in both descriptions; no independent reader relevance label. |
| You can run, but you can't hide → Jonah Hex | bounty hunter | PLAUSIBLE: specific shared subject/theme visible in both descriptions; no independent reader relevance label. |
| You can run, but you can't hide → Nine Lives | bounty hunter | PLAUSIBLE: specific shared subject/theme visible in both descriptions; no independent reader relevance label. |
| You can run, but you can't hide → Fugitive Ambush | bounty hunter | PLAUSIBLE: specific shared subject/theme visible in both descriptions; no independent reader relevance label. |
| Looking for opportunities → Black Clone's Wife | medical doctor | FAIL: medical doctor is an incidental mention, insufficient to relate this candidate to a Thai physician biography. |
| Looking for opportunities → An English translation of the Sushruta samhita, based on original Sanskrit text | medical science | REVIEW NEEDED: source phrase is real, but broad medicine/context or an incidental mention cannot establish useful similarity. |
| Looking for opportunities → My Killaloe | medical doctor | FAIL: medical doctor is an incidental mention, insufficient to relate this candidate to a Thai physician biography. |
| Looking for opportunities → Christ or Therapy? | medical doctor | FAIL: medical doctor is an incidental mention, insufficient to relate this candidate to a Thai physician biography. |
| Looking for opportunities → Roald Dahl's Marvellous Medicine | medical science | REVIEW NEEDED: source phrase is real, but broad medicine/context or an incidental mention cannot establish useful similarity. |
| Looking for opportunities → Euthanasia and the Ethics of a Doctor's Decisions | medical doctor | REVIEW NEEDED: source phrase is real, but broad medicine/context or an incidental mention cannot establish useful similarity. |
| Looking for opportunities → House, M.D. | medical science | REVIEW NEEDED: source phrase is real, but broad medicine/context or an incidental mention cannot establish useful similarity. |
| Looking for opportunities → Sensing art, training the body | medical doctor | FAIL: medical doctor is an incidental mention, insufficient to relate this candidate to a Thai physician biography. |
| Frankenstein → Frankenstein | mary shelley, qui est | FAIL: non-semantic French function phrase survives a noisy subject vocabulary; Mary Shelley evidence does not validate this extra phrase. |
| Frankenstein → The monster factory | mary shelley | PLAUSIBLE: shared named literary subject, not a verified author identity. |

## Full-build gate

Integrity PASS; contribution/path traceability PASS; pilot latency PASS; diversity-decline gate PASS; disk/time projection PASS; **useful-reason review FAIL**. The refined linear estimate is **6.93 GB** V2 output, **20.78 GB** conservative additional staging/compaction peak, **3,018 s (~50 min)** enrichment, with **53.03 GB** then free. Nonlinear full-corpus vocabulary/degree and indexing effects make these projections uncertain. No full V2 build was run and runtime V1 was never switched. Failed staging artifacts/logs are retained separately for audit; they are not active graphs.

Production series/publisher/language/era/genre/format/edition/ISBN/classification expansions are rejected because source fields are absent. Description topics remain an experimental pilot relation. Further promotion needs multilingual quality controls, reliable topic salience and independent held-out relevance evidence. KG4 stays deferred under the original KG3 failed diversity gate and missing reader utility evidence.
