"""Assemble evidence without overwriting frozen KG1–KG3 measurements."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'


def read(name): return json.loads((REPORTS / name).read_text(encoding='utf-8'))
def write(name, value): (REPORTS / name).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
def md(name, value): (REPORTS / name).write_text(value, encoding='utf-8')
def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''): digest.update(chunk)
    return digest.hexdigest()


def review(example):
    topics = set(example['topics'])
    incidental = {'OL9778497W', 'OL23398717W', 'OL15671172W', 'OL32135005W'}
    if 'qui est' in topics:
        return 'FAIL: non-semantic French function phrase survives a noisy subject vocabulary; Mary Shelley evidence does not validate this extra phrase.'
    if example['candidate_work_id'] in incidental:
        return 'FAIL: medical doctor is an incidental mention, insufficient to relate this candidate to a Thai physician biography.'
    if topics & {'left corner', 'right corner', 'birthday anniversary', 'ouvrage montre', 'entre elles'}:
        return 'FAIL: layout, commemoration or non-semantic language fragment is not a useful shared theme.'
    if topics & {'machine learning', 'public health', 'bounty hunter'}:
        return 'PLAUSIBLE: specific shared subject/theme visible in both descriptions; no independent reader relevance label.'
    if topics == {'mary shelley'}:
        return 'PLAUSIBLE: shared named literary subject, not a verified author identity.'
    return 'REVIEW NEEDED: source phrase is real, but broad medicine/context or an incidental mention cannot establish useful similarity.'


def main():
    baseline = read('kg31_baseline.json')
    audit = read('kg_ontology_enrichment_audit.json')
    raw_audit = REPORTS / 'kg31_ontology_audit_raw.json'
    if not raw_audit.exists(): raw_audit.write_bytes((REPORTS / 'kg_ontology_enrichment_audit.json').read_bytes())
    for name, item in audit['fields'].items():
        if name == 'description':
            item.update(normalization_difficulty='Moderate: NFKC/case-fold/whitespace plus exact contiguous source phrases. Multilingual text, markup, duplicate descriptions and boilerplate remain concerns.',
                        semantic_usefulness='Potentially moderate; only bounded corpus-statistical topics were admitted to separate pilots.',
                        data_quality_problems=['Only 25.8296% have at least 20 tokens', 'Language unknown', 'Duplicated and markup text', 'Source validity does not ensure topic relevance'],
                        decision='PILOT ONLY; both topic policies fail qualitative usefulness gate. No production topic edges.',
                        degree_interpretation='Degree of identical normalized complete description, not derived topic degree.')
        elif name == 'created_at':
            item.update(normalization_difficulty='Low for stored values; this is ingestion metadata, not publication year.', semantic_usefulness='None for semantic similarity.',
                        data_quality_problems=['Only 0.20002% populated', 'One timestamp groups 10,000 books', 'Not a publication date'], decision='REJECT')
        elif name == 'shelf_location':
            item.update(normalization_difficulty='Library-specific operational location.', semantic_usefulness='Display metadata only.',
                        data_quality_problems=['Only one populated book', 'No stable semantic taxonomy'], decision='REJECT graph feature; retain authoritative display')
        else:
            item.update(normalization_difficulty='Not assessable: no non-null values or observed field instances in the full catalogue.',
                        semantic_usefulness='No usable source evidence; theoretical usefulness does not admit a category.',
                        data_quality_problems=['Absent in all 5,000,000 audited books'], decision='REJECT: structured source absent; do not infer from titles or descriptions')
    audit['operational_and_rating_decisions'] = {
        'available_copies/total_copies/borrow/reservation': 'REJECT similarity edges; Core operational availability only',
        'average_rating/rating_count/reading_log_count': 'REJECT graph identity; live display only',
        'book_id/work_id/title': 'Canonical work_id identity; title display; no inferred series/publisher/language/year'}
    audit['full_build_decision'] = 'STOP AT PILOT: source integrity, disk and latency pass; useful topic reasons do not.'
    write('kg_ontology_enrichment_audit.json', audit)
    table = '\n'.join(f"| {name} | {item['non_null_count']:,} | {item['coverage_percent']:.6g}% | {item['unique_normalized_value_count']:,} | {item['degree']['median']} / {item['degree']['p90']} / {item['degree']['p99']} / {item['degree']['largest']} | {item['decision']} |"
                      for name, item in audit['fields'].items())
    md('kg_ontology_enrichment_audit.md', f'''# KG3.1 full catalogue ontology audit

Read-only streaming scan of all **5,000,000** Mongo catalogue books, bounded batches and disk-backed degree aggregation. Duration **{audit['audit_seconds']:.2f} s**. Every candidate field and alias was checked; absent fields have no degree distribution (`None` means not applicable, not a measured zero). The JSON records per-field normalization difficulty, semantic usefulness and quality issues. Raw measurements are preserved in `kg31_ontology_audit_raw.json`.

| Field / alias | Non-null books | Coverage | Unique normalized values | Degree median / p90 / p99 / max | Decision |
|---|---:|---:|---:|---|---|
{table}

Series, publisher, language and publication era were evaluated first and rejected because their structured sources do not exist. Genre, format, edition, ISBN and classification aliases are likewise absent. No series is inferred from a title. Ingestion timestamps are not publication dates. Shelf, copies, circulation, ratings and popularity do not form semantic graph edges.

Description is populated for **1,732,337 books (34.64674%)**; **1,291,480 (25.8296%)** contain at least 20 tokens. Among populated descriptions, token lengths median/p90/p99 are **49 / 195 / 386**, maximum **58,401**. There are **440,857** short descriptions, **6** exact boilerplate descriptions, **27,826** with markup, **1,660,088** normalized unique descriptions, **33,857** duplicate groups involving **106,106** books (**72,249** duplicate excess). Complete-description degrees are **1 / 1 / 2 / 4,573**. Empty-whitespace count is zero among populated strings; remaining **3,267,663** books have no populated description. Language coverage is zero; the non-English rate is **unknown**, not estimated. Examples visibly include several languages.

Descriptions qualified for a bounded deterministic pilot, not automatic production acceptance. Both unrestricted phrases and the stricter existing-subject-vocabulary policy fail usefulness review. Stop at the pilot as allowed by Phase 32. Product queries continue using the original V1 graph.
''')

    initial = read('kg_v1_vs_v2.json')
    refined = read('kg31_v1_vs_v2_subject_vocab.json')
    initial_raw = REPORTS / 'kg31_v1_vs_v2_unrestricted_raw.json'
    if not initial_raw.exists(): initial_raw.write_bytes((REPORTS / 'kg_v1_vs_v2.json').read_bytes())
    for measurement in [initial, refined]:
        measurement.setdefault('pre_review_full_build_gate', measurement['full_build_gate'])
        measurement['full_build_gate'] = 'STOP AT PILOT: useful-reason review failed; no full V2 build or runtime switch.'
        measurement['manual_topic_review'] = [{**example, 'assessment': review(example)} for example in measurement['topic_examples']]
        measurement['metric_caveat'] = 'strong_or_moderate_reason_fraction is nominal relation-type eligibility, NOT human semantic-quality validation. No independent relevance or utility labels exist.'
        measurement['full_build_gate_decision'] = {'integrity': 'PASS', 'latency': 'PASS', 'disk_projection': 'PASS', 'diversity_decline': 'PASS',
                                                   'useful_reason_review': 'FAIL', 'decision': 'STOP AT PILOT; preserve production V1'}
    initial['refined_pilot_report'] = 'kg31_v1_vs_v2_subject_vocab.json'
    initial['refined_pilot_summary'] = refined['summary']
    initial['final_decision'] = 'Neither pilot promoted. No full V2 build and no KG4.'
    write('kg_v1_vs_v2.json', initial)
    write('kg31_v1_vs_v2_subject_vocab.json', refined)

    graph_path = Path(baseline['v1_artifact']['path'])
    artifact_check = {'path': str(graph_path), 'bytes': graph_path.stat().st_size, 'sha256': sha(graph_path)}
    artifact_check['unchanged'] = all(artifact_check[key] == baseline['v1_artifact'][key] for key in ['bytes', 'sha256'])
    assert artifact_check['unchanged']
    changed = [name for name, value in baseline['files'].items() if sha(ROOT / name) != value]
    protected = {name: name not in changed for name in baseline['files'] if name.startswith(('recommendation/', 'search/', 'rag/')) or name in ['assistant/routing.py', 'assistant/qwen.py', 'reports/kg3_evaluation.json', 'reports/kg3_seeds.json', 'reports/kg1_kg2_build.json', 'reports/knowledge_graph_final.md', 'reports/knowledge_graph_final.json']}
    assert all(protected.values()), [name for name, intact in protected.items() if not intact]
    performance = read('kg_product_performance.json')
    browser = read('kg31_browser_checks.json')
    performance['browser_evidence'] = {'report': 'kg31_browser_checks.json', 'technical_automation_wall_ms': 865,
                                      'refresh_automation_wall_ms': 809, 'caveat': 'Cua click-to-visible durations include automation overhead; six flows are observed samples, not a statistically established browser p95.'}
    for case in performance['cases']:
        case['reason_types'] = sorted({p['kind'] for b in case['recommendations'] for p in b['reason_paths']})
    write('kg_product_performance.json', performance)
    write('kg31_integrity_preservation.json', {'v1_artifact': artifact_check, 'protected_source_and_reports': protected, 'changed_baseline_files': changed})

    v1 = read('kg31_pilot_build.json')['v1']
    v2 = read('kg31_pilot_v2_subject_vocab_build.json')
    rows = '\n'.join(f"| {label} | {refined['summary']['v1'][key]:.6g} | {refined['summary']['v2'][key]:.6g} |" for label, key in [
        ('Nonempty seed coverage', 'seed_coverage'), ('Full Top10', 'top10_completeness'), ('Unique candidates', 'unique_candidates'),
        ('Subject diversity', 'mean_subject_diversity'), ('Same-seed author concentration', 'same_seed_author_concentration_mean'),
        ('Relationship type diversity', 'relationship_type_diversity_mean'), ('Reasons per result', 'reason_count_mean'),
        ('Generic reason fraction (degree ≥1%)', 'generic_reason_fraction_degree_at_least_1_percent'),
        ('Topic-only results', 'topic_only_recommendations'), ('Query median ms', 'latency_median_ms'),
        ('Query p95 ms', 'latency_p95_ms'), ('Query maximum ms', 'latency_max_ms')])
    reviews = '\n'.join(f"| {example['seed_title']} → {example['candidate_title']} | {', '.join(example['topics'])} | {review(example)} |" for example in refined['topic_examples'])
    md('kg_ontology_enrichment.md', f'''# KG3.1 ontology enrichment evaluation

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

40 original frozen seeds; three warm local SQLite queries per seed/method; no API hydration time in these pilot timings. **{refined['verified_paths']:,}** paths checked against original fields/description hashes; every score equals its summed feature contributions. Same population and ranking conditions; this coverage must not be compared to the full V1 95% KG3 coverage as if populations were equal.

| Metric | Pilot V1 | Refined pilot V2 |
|---|---:|---:|
{rows}

Mean top10 overlap **{refined['mean_top10_overlap']:.4f}**; paired subject-diversity delta **{refined['paired_diversity_delta_mean']:+.6f}**. Contribution fractions author/subject/topic: V1 **3.58% / 96.42% / 0%**, refined V2 **3.49% / 93.73% / 2.78%**. Coverage 35/40→36/40, full top10 stays 31/40. Unique candidates rise 313→321; this is metadata novelty, not a relevance gain. Initial unrestricted V2 had 328 unique candidates, 33/40 full lists, 15 topic-only recommendations and **−0.001945** paired diversity delta. Full per-seed evidence remains in `kg_v1_vs_v2.json`; refined evidence is in `kg31_v1_vs_v2_subject_vocab.json`.

The automatic `strong_or_moderate_reason_fraction = 1` is **only nominal relation-type eligibility**. It does not mean 100% useful reasons. Below is agent qualitative review of all 15 refined topic-bearing candidates; it is not independent human/reader relevance labeling. All 21 initial examples and all 15 refined examples also retain source excerpts in JSON.

| Seed → candidate | Description topics | Usefulness review |
|---|---|---|
{reviews}

## Full-build gate

Integrity PASS; contribution/path traceability PASS; pilot latency PASS; diversity-decline gate PASS; disk/time projection PASS; **useful-reason review FAIL**. The refined linear estimate is **6.93 GB** V2 output, **20.78 GB** conservative additional staging/compaction peak, **3,018 s (~50 min)** enrichment, with **53.03 GB** then free. Nonlinear full-corpus vocabulary/degree and indexing effects make these projections uncertain. No full V2 build was run and runtime V1 was never switched. Failed staging artifacts/logs are retained separately for audit; they are not active graphs.

Production series/publisher/language/era/genre/format/edition/ISBN/classification expansions are rejected because source fields are absent. Description topics remain an experimental pilot relation. Further promotion needs multilingual quality controls, reliable topic salience and independent held-out relevance evidence. KG4 stays deferred under the original KG3 failed diversity gate and missing reader utility evidence.
''')

    live_table = '\n'.join(f"| {c['category']} | {c['work_id']} | {c['results']} | {sum(c['warm_ms'])/len(c['warm_ms']):.1f} | {', '.join(c['reason_types']) or 'none'} | PASS |" for c in performance['cases'])
    md('kg_product_more_like_this.md', f'''# LuminaR KG3.1 product More Like This

**Product PASS. Overall PARTIAL because V2 remains at the permitted pilot stop.** Book Detail uses the unchanged full V1 graph. No KG4, production ontology promotion or model download.

Book Detail adds **More Like This** immediately beside Add to Reading List in the existing action row. Click stays on `/book/:work_id`, loads/focuses an inline section, shows Finding related books, native cover/title/author/rating/copy/shelf cards, View/Select and deterministic grouped Why related. Hide, refresh, retry and stale/not-found messages are supported. Empty books say no graph relationships and offer an explicit separate Try Recommend Similar action. No automatic recommender fallback or tray modification occurs. Raw scores remain API metrics and are not rendered in normal cards.

Small overflow links on catalogue, search, reading list, For You recommendation and assistant book cards open `/book/:work_id?related=1#more-like-this`. Existing assistant actions also include MORE_LIKE_THIS. Exact phrases more like this, show books connected to this and find related books with exactly one selected/page book enter the zero-Qwen route. Missing or multiple sources clarify without Qwen. Existing Recommend Similar, compact intent wire codes, recommendation engine and document RAG routes remain intact.

**API:** authenticated `GET /kg/books/{{work_id}}/more-like-this?limit=10`, Core port 8002 via the existing `/api` frontend proxy. It reuses the Graph Lab recommendation function and `CatalogueGraph.more_like_this`; no frontend query algorithm is duplicated. Canonical work_id only. Limits 1–50; active loans/reservations excluded. Results rehydrate through live Core catalogue and `get_availability_context`, including physical LIB001 inventory precedence. Author/subject freshness checked; future V2 hashes supported. Changed seeds return friendly 409; changed/deleted/ineligible candidates are removed. `has_more=false`: no fabricated paging. Filtering can return fewer than ten.

Graph Lab stays `/experimental/kg`; the explicit advanced link supplies `?seed=<work_id>`. Seed loading, new/unknown relationship colours/filtering and changing-seed result cleanup work. It is never opened automatically.

## Actual authenticated live checks

Loopback Core endpoint, one verified existing reader, no database writes. Each case has a first-observed request and three warm repeats; authoritative book metadata and availability are checked outside the timer. All returned reason paths source-verified. See `kg_product_performance.json` for complete cards, evidence and timings.

| Case | work_id | Results | Warm mean ms | Reason types | Metadata / availability |
|---|---|---:|---:|---|---|
{live_table}

Across 18 warm requests: median **{performance['warm_summary']['median_ms']:.1f} ms**, p95 **{performance['warm_summary']['p95_ms']:.1f} ms**, maximum **{performance['warm_summary']['max_ms']:.1f} ms**. First-observed is not a process-cold benchmark. The technical click-to-visible UI sample is **865 ms** and refresh **809 ms** including Cua overhead; four other UI cases are 308–540 ms. These are observed samples, not statistically established browser p95. All six cases also loaded in the real signed-in Book Detail UI. Isolated has zero results and separate normal recommendation offer. Selection stayed false; current page remained unchanged. Keyboard Enter expands exact Subjects such as Machine learning and Computer Neural Networks. Finance cards likewise preserve their actual shared author/subject labels.

A real assistant orchestrator and real HTTP adapter called live Core, with forbidden Qwen/RAG/recommender sentinels: MORE_LIKE_THIS returned {performance['assistant_live_core_probe']['books']} books with zero Qwen and seeded recommender calls. This is a live-Core transport harness, **not a running port-8005 end-to-end request**. The existing 8005 worker is not running; when normally started it requires the existing local RAG/model initialization. The normal page button needs only Core and Vite. Collection hashes before/after (users, issues, reservations, reading list, feedback, inventory, fines, activity) match.

## Verification

Backend **429 passed, 10 existing skips** including all 28 KG3.1 checks and 401 prior KG/assistant/document/access/auth/contracts. Focused UI **17**, Graph Lab **5**, independent frontend contracts **5**, original frontend **111**: **138 passed** in total. Production build passes. Lint exits zero with **19 existing warnings**, no new KG component warnings. Logs: `kg31_backend_regression_final.log`, `kg31_frontend_all_final.log`, `kg31_frontend_focus_final.log`, `kg31_frontend_contract_final.log`, `kg31_frontend_build_final.log`, `kg31_frontend_lint_final.log`. No tests were weakened; compact enum codes and protected routing were repaired additively.

Responsive DOM/layout plus action/result screenshots: requested **1440×900**, **1366×768**, **768×1024**, **375×812**. Actual CSS sizes **1440×900**, **1366×767**, **769×1024**, **375×812**, plus **767×1024** around the tablet breakpoint. No page horizontal overflow; mobile actions wrap and result cards stay within width. Browser DPR/zoom 0.8 plus integer viewport override prevents two exact dimensions; do not claim exact coverage there. Screenshot canvases may include padding from browser scaling. `kg31_browser_checks.json` retains actual geometry; `kg31_book_actions_*.jpg`, `kg31_more_like_this_*.jpg` and `kg31_product_preview.jpg` retain captures. Viewport reset before handoff.

## Exact local start commands

Use separate PowerShell terminals. Keep existing listeners; stop/restart only the intended service if code is already loaded in an old process. Do not rebuild V1 or promote either V2 pilot.

```powershell
# Terminal 1: product Core
Set-Location D:\\SDC\\LibraryLLM
.\\.venv\\Scripts\\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002 --workers 1
```

```powershell
# Terminal 2: existing frontend
Set-Location D:\\SDC\\LibraryLLM\\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173/book/OL19545719W`, sign in normally and click More Like This. Core/Vite remain running after verification. Search 8003 and recommendation 8004 remain running as before. For a fresh session, those existing services start separately from the project root:

```powershell
.\\.venv\\Scripts\\python.exe -m uvicorn search.api:app --host 127.0.0.1 --port 8003 --workers 1
.\\.venv\\Scripts\\python.exe -m uvicorn recommendation.api:app --host 127.0.0.1 --port 8004 --workers 1
# Optional existing assistant worker; reuses installed local models:
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
.\\.venv\\Scripts\\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005 --workers 1
```

Known limits: metadata similarity is not relevance probability; author names are unresolved strings; sparse/isolated works can return few/no books; stale candidates can reduce top10; current product graph contains only author and subject relations; topics are pilot-only and require further independent quality work. Full V2 and live-8005 overlay testing are deliberately unclaimed. Original KG3 paired diversity delta −0.0572 and 14% recommender overlap remain unchanged; no hybrid reranking is introduced.
''')
    write('kg31_final.json', {'status': 'PARTIAL', 'product': 'PASS', 'ontology': 'Evaluated; full-build gate rejected useful reasons, stop at pilot',
                             'active_graph': 'V1 catalogue.sqlite', 'v1_preserved': artifact_check['unchanged'], 'backend_passed': 429,
                             'backend_existing_skipped': 10, 'frontend_passed': 138, 'build': 'PASS', 'lint_existing_warnings': 19,
                             'v2_production_promoted': False, 'kg4_started': False, 'live_state_unchanged': performance['read_only_state_unchanged'],
                             'completed_at': datetime.now(timezone.utc).isoformat()})
    print(json.dumps({'status': 'PARTIAL', 'product': 'PASS', 'v1_unchanged': artifact_check['unchanged'], 'protected_files': len(protected), 'changed_files': changed}))


if __name__ == '__main__': main()
