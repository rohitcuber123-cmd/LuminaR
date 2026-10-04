"""Assemble current validation reports while retaining the earlier KG31 evidence."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reports'


def read(name):
    return json.loads((R / name).read_text(encoding='utf-8'))


def write(name, value):
    (R / name).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def main():
    now = datetime.now(timezone.utc).isoformat()
    baseline = read('kg_productization_baseline.json')['files']
    changed = [p for p, h in baseline.items()
               if hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != h]
    expected = ['assistant/kg_routing.py', 'frontend/src/components/MoreLikeThisSection.tsx',
                'frontend/src/lib/knowledgeGraph.ts', 'knowledge_graph/core.py']
    assert sorted(changed) == sorted(expected), changed
    frozen = read('kg_productization_graph_baseline.json')['files']
    preserved = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h
                 for p, h in frozen.items() if p.startswith('reports/')}
    assert all(preserved.values())
    performance = read('kg_product_performance.json')
    assert performance['read_only_state_unchanged']
    assert performance['assistant_live_core_probe']['qwen_calls'] == 0
    author_case = next(c for c in performance['cases'] if c['category'] == 'same-author')
    assert any(p['kind'] == 'author' for c in author_case['recommendations'] for p in c['reason_paths'])
    browser = read('kg_productization_browser_checks.json')
    assert all(c['cards'] == c['expected'] for c in browser['realBookCases'])
    assert all(not c['overflow'] for c in browser['layouts'])
    evaluation = read('kg_productization_v1_vs_v2_current.json')
    gate = evaluation['full_build_gate_decision']
    assert gate['useful_reason_review'] == 'FAIL'
    initial = read('kg31_pilot_build.json')
    refined = read('kg31_pilot_v2_subject_vocab_build.json')
    write('kg_v2_build.json', {
        'reported_at': now, 'build_reused': True, 'new_build_this_turn': False,
        'active_graph': 'knowledge_graph/data/catalogue.sqlite (V1)',
        'v1_pilot': initial['v1'], 'initial_v2_pilot': initial['v2'],
        'refined_v2_pilot': refined, 'frozen_population': evaluation['population'],
        'published_pilot_quick_check': 'ok for V1, initial V2 and refined V2',
        'full_build_gate': gate, 'full_5m_v2_built': False,
        'full_projection': evaluation['full_build_estimate'],
        'disk_free_now_bytes': shutil.disk_usage(ROOT).free,
        'source_build_reports': ['kg31_pilot_build.json', 'kg31_pilot_v2_subject_vocab_build.json'],
        'note': 'Earlier failed staging artifact retained separately; it is not a published graph.'})
    integrity = {
        'reported_at': now, 'v1_artifact': read('kg_productization_v1_hash_check.json'),
        'changed_application_sources': changed,
        'protected_source_hashes_unchanged': {p: True for p in baseline if p not in changed},
        'frozen_kg3_and_build_reports': preserved,
        'same_40_seed_ids_rankings_and_scores_reproduced': True,
        'verified_pilot_reason_paths': evaluation['verified_paths'],
        'published_pilot_quick_check': 'ok', 'weak_only_recommendations': 0,
        'live_core_metadata_and_availability': all(c['metadata_availability_correct'] for c in performance['cases']),
        'live_reason_paths_source_verified': all(c['reason_paths_source_verified'] for c in performance['cases']),
        'same_author_case_has_author_reason': True,
        'live_read_only_collection_hashes_unchanged': performance['read_only_state_unchanged'],
        'disposable_identity': 'Created only for testing; removed after normal UI logout.',
        'qwen_calls': 0, 'existing_recommender_calls': 0,
        'recommendation_formula_search_paging_show_more_know_more_source_unchanged': True,
        'v2_promoted': False, 'kg4_started': False}
    write('kg_product_integrity.json', integrity)

    audit = read('kg_v2_metadata_audit.json')
    raw = R / 'kg_v2_metadata_audit_raw.json'
    if not raw.exists():
        raw.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding='utf-8')
    audit['relation_decisions'] = {
        'production_accepted': ['author names', 'subject labels (existing V1)'],
        'pilot_only': ['deterministic description topics; not promoted'],
        'structured_rejected': 'Series, publisher, language, publication era, genre, format, edition, ISBN and classification aliases: zero structured coverage.',
        'display_only': 'shelf_location is a physical display field, not semantic similarity.',
        'created_at': 'Import timestamp, never inferred as publication date.',
        'description_language': 'Unknown; no language inferred from missing metadata.',
        'normalization': 'NFKC, casefold, whitespace; preserve original source labels; author names are not resolved identities.',
        'weak_only_qualification': False}
    write('kg_v2_metadata_audit.json', audit)
    table = '\n'.join(f"| {name} | {v['non_null_count']:,} | {v['coverage_percent']:.5f}% | {v['unique_normalized_value_count']:,} | {v['degree']['median']} / {v['degree']['p90']} / {v['degree']['p99']} / {v['degree']['largest']} |"
                      for name, v in audit['fields'].items())
    (R / 'kg_v2_metadata_audit.md').write_text(f"""# KG V2 metadata audit

Fresh full Mongo scan: {audit['books_scanned']:,} books in {audit['audit_seconds']:.2f}s. Raw source evidence: kg_v2_metadata_audit_raw.json. This is a full scan, not a sample. No structured relation is invented from title or description text.

| Field | Non-null | Coverage | Unique normalized values | Degree median / p90 / p99 / max |
|---|---:|---:|---:|---|
{table}

Absent fields have no meaningful degree distribution: null is not a measured zero-degree population. Existing graph authors and subjects remain the only production relations. Series could be strong, publisher moderate/weak and language/era weak if audited structured evidence existed; none exists here. Genre remains represented by source subjects, not a guessed new field. Shelf location remains display only. created_at is an import timestamp.

Descriptions: 1,732,337 present (34.64674%); 1,291,480 have at least 20 tokens (25.8296% of all books). Token lengths median49 / p90195 / p99386 / maximum58,401. There are 440,857 short descriptions, 6 exact boilerplate values, 27,826 markup-containing descriptions, 33,857 duplicate groups involving 106,106 books and 72,249 excess duplicates. Normalized description degree median1 / p901 / p992 / maximum4,573. Non-English rate is unknown; missing language fields do not justify a numerical estimate. Representative source excerpts and field value types are in the JSON.

The existing deterministic pilot strips markup, caps scanning at 512 tokens, accepts descriptions with at least20 tokens, and extracts adjacent Unicode2–3-word phrases with NFKC/casefold/whitespace normalization. English/generic stop words, corpus degree3–0.1%, TF-IDF ordering, lexical ties, no nested phrases, and at most5 topics per book bound noise and degree. Refined pilot also requires membership in the full V1 subject vocabulary. Original phrase and description hash remain provenance. This global policy does not select per-seed phrases or fit the frozen evaluation seeds.

Topics remain pilot only: incidental medical-doctor mentions and non-semantic French “qui est” survived even the subject-vocabulary filter. Weak fields cannot qualify a pair alone; no weak edges exist. No Qwen, embedding model, downloaded dataset, cloud service or new model was used. No full5M V2 promotion is justified.
""", encoding='utf-8')
    s1, s2 = evaluation['summary']['v1'], evaluation['summary']['v2']
    metrics = '\n'.join(f'| {key} | {s1[key]} | {s2[key]} |' for key in
        ['seed_coverage', 'top10_completeness', 'unique_candidates', 'mean_subject_diversity',
         'same_seed_author_concentration_mean', 'relationship_type_diversity_mean', 'reason_count_mean',
         'generic_reason_fraction_degree_at_least_1_percent', 'strong_or_moderate_reason_fraction',
         'topic_only_recommendations', 'latency_median_ms', 'latency_p90_ms', 'latency_p95_ms', 'latency_max_ms'])
    cases = '\n'.join(f"| {c['category']} | {c['work_id']} | {c['results']} | {c['first_observed_ms']:.1f} | {min(c['warm_ms']):.1f}–{max(c['warm_ms']):.1f} |" for c in performance['cases'])
    commands = r'''# Separate terminals; Core + frontend are sufficient for More Like This.
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002 --workers 1

Set-Location D:\SDC\LibraryLLM\frontend
npm run dev -- --host 127.0.0.1 --port 5173

# Existing services, each in a separate terminal from the project root:
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe -m uvicorn search.api:app --host 127.0.0.1 --port 8003 --workers 1
.\.venv\Scripts\python.exe -m uvicorn recommendation.api:app --host 127.0.0.1 --port 8004 --workers 1
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
.\.venv\Scripts\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005 --workers 1'''
    (R / 'kg_productization.md').write_text(f"""# LuminaR KG productization validation — {now}

A. **PARTIAL overall; product PASS.** Existing implementation verified and small gaps closed. Ontology evaluation complete; usefulness FAIL means stop at pilot. No full V2 build/promotion or KG4.

B. **Screen flow:** Book Detail → More Like This beside Reading List → loading state → up to10 inline cards → deterministic Why related → Show connection for the actual book pair → Explore full graph → existing seeded experimental Graph Lab. Live metadata, rating, availability and shelf come from Core. View and Select for AI remain available. No normal-UI similarity score or fabricated continuation. Empty: “No graph relationships are available for this title yet.” Recommend Similar fallback is an explicit separate action. Hide/refresh/retry/auth/stale behavior retained.

C. **Frontend changed this turn:** frontend/src/components/MoreLikeThisSection.tsx (empty/link wording), frontend/src/lib/knowledgeGraph.ts (optional additive trace fields), frontend/tests/kg-product.test.tsx (wording assertions). Existing BookDetailPage, RelatedBookCard/WhyRelated/BookConnectionGraph, useMoreLikeThis, BookDiscoveryMenu and card-menu placements were already implemented; no new page or duplicated query logic. Full architecture audit: kg_productization_audit.md.

D. **Backend/KG changed this turn:** assistant/kg_routing.py (two requested graph phrases), knowledge_graph/core.py (trace fields derived from published feature weights; scoring SQL unchanged), tests/test_assistant_kg.py, tests/test_kg_product.py. Added scripts/revalidate_kg_metadata.py, scripts/revalidate_kg_product.py and scripts/write_kg_productization_reports.py; .gitignore excludes the disposable test credential file. backend/routes/knowledge_graph.py is the preserved product implementation. No schema/query/ranking/model change.

E. **Endpoint:** authenticated GET /kg/books/{{work_id}}/more-like-this?limit=10 on Core8002; frontend /api/kg/books/{{work_id}}/more-like-this through the existing proxy. Canonical work_id, max50, current10. has_more=false; candidate_count is diagnostic. Excludes seed, active loans/reservations, stale/deleted/inactive candidates; seed metadata changes produce friendly409. API rehydrates live Mongo metadata and physical LIB001 inventory precedence. Topic description hashes are supported for future vetted artifacts.

F. **Qwen calls:0.** Product route tests forbid Qwen and the existing recommender. Real assistant orchestrator/HTTP adapter calls live Core with forbidden Qwen/RAG/recommender sentinels and returns10 books with0 model/recommender calls. This is not a live port8005 end-to-end request. Exact phrases “more like this”, “show related books”, “what books are connected to this?” and structured MORE_LIKE_THIS are preserved/covered.

G. **V1 preserved and active:** 5,000,000 books; 2,454,492 author-name nodes; 975,785 subject nodes; 29,406,707 edges; 5,871,624,192bytes; original build882.81s. SHA2560d5c6603f8cb5cf720b46eaac5d1cf6f1ef9952b3d668a69395cf1afb57921fc reproduced. Read-only SQLite queries. Frozen KG3 seed/evaluation/build report hashes match. Search, recommendation formula/weights/paging, assistant SHOW_MORE and Know More lifecycle/cache sources match pre-edit hashes.

H. **Metadata audit:** fresh full5M scan265.15s; all structured series/publisher/language/year/genre/format/edition/ISBN/classification aliases absent. Description34.64674% present,25.8296% usable≥20 tokens; language unknown. Full coverage/type/normalization/duplicate/degree/source-excerpt evidence: kg_v2_metadata_audit.md/json.

I. **Accepted:** existing author-name and subject-label relations in production; verified deterministic description topics only in pilot.

J. **Rejected:** absent structured relations; shelf location as semantics; created_at as publication era; title-parsed series; weak-only matches; noisy/incidental topics as production evidence.

K. **Description topics:** global bounded deterministic2–3-word TF-IDF phrase policy; refined vocabulary from full V1 subjects; original phrase/hash provenance. No LLM/new model. Refined15,642 topic-bearing books,33,736 topic edges,4,789 topic nodes. Eight topic-only recommendations survived nominal eligibility, but source-reason review fails semantic usefulness. “machine learning” is plausible; incidental “medical doctor” and French “qui est” are failures. No independent reader utility labels exist.

L. **V2 counts:** same100,040-book pilot as V1, with all40 frozen KG3 seeds. V1pilot105,107authors +93,867subjects /587,074edges. InitialV2 adds16,623topics /656,478edges. RefinedV2 adds4,789topics /620,810edges. These are pilot counts, not full5M V2 counts.

M. **Size:** V1pilot126,763,008bytes; initialV2145,911,808bytes; refinedV2138,604,544bytes. Linear refined full estimate6.93GB plus staging reserve20.78GB; degree/vocabulary/index growth can be nonlinear. Actual free disk recorded in kg_v2_build.json. Production V1 retained.

N. **Original measured build times, reused:** V1pilot10.14s; initialV2 enrichment+compaction50.09s; refined61.28s. No rebuild this turn. Full linear enrichment estimate3018.33s is a projection, not a measured build. Published pilot SQLite quick_check returnsok.

O. **Weights:** explicit knowledge_graph/relations.py author2,subject1,topic0.5; importance=1+ln((N+1)/(degree+1)); stored feature_weight=relation_weight×importance; cosine contribution=feature_weight²/(seed_norm×candidate_norm). Additive reasons expose each value, typed node IDs, predicates, original labels and source provenance; sum(contribution)=score. Runtime relation multipliers are derived from the artifact, never retroactively substituted. Ranking/ties remain score DESC / internal book_id ASC.

P. **Weak qualification:** weak-only matches cannot qualify. No publisher/language/era weak edges were built; weak-only result count0. Topics are nominally moderate in the experimental policy, so topic-only pilot pairs exist and require semantic review before promotion.

Q. **Comparable V1/V2:** identical systematic100,040-book population including all40 frozen KG3 seeds; not full5M V1 versus a small V2. IDs/order/scores exactly reproduce the earlier refined evaluation;1,224 paths verified. Mean top10 overlap0.8575; paired subject-diversity delta+0.001910 over paired seeds. Original full KG3 evidence is unchanged.

| Metric | Same-population V1 | Refined V2 |
|---|---:|---:|
{metrics}

Nominal strong/moderate fraction1.0 means relation eligibility, not validated semantic quality. Mean contribution shares V1 author3.58%/subject96.42%; V2 author3.49%/subject93.73%/topic2.78%. kg_v1_vs_v2.json retains the original initial-pilot report; kg31_v1_vs_v2_subject_vocab.json retains refined evidence; kg_productization_v1_vs_v2_current.json holds the fresh reproduction.

R. **Live product latency:** first observed+3 warm authenticated Core requests per seed; metadata verification outside timing. No process-cold claim. Warm24-request median254.50ms/p902239.65ms/p952280.33ms/max2297.87ms. Broad History degree571,286 yields572,162 candidates; first finance request2675ms. High-degree expansion remains a known cost, with IDF downweighting preserved. The pilot SQLite timing table above excludes HTTP/Mongo hydration and must not be equated to product timings.

| Case | Work ID | Cards | First observed ms | Warm range ms |
|---|---|---:|---:|---:|
{cases}

S. **Why related examples:** Rich Dad, Poor Dad → Sharon L. Lechter/Robert T. Kiyosaki + Personal Finance/Investments → El juego del dinero; Over the side → Jean-Pierre Andrieux/Prohibition/Smuggling → Prohibition and St. Pierre. UI groups only actual path labels by relation type, with book-pair SVG and full labels. Author names remain metadata strings, not verified human identities.

T. **Responsive/live UX:** all8 categories pass frontend and live API result-count checks. Desktop2-column cards, tablet/mobile1-column; no horizontal page overflow, long title wraps, pair graph present. Requested1440×900,1366×768,768×1024,375×812; actual CSS1440×900,1366×767,767×1024,375×812 because IAB0.8 scaling rounds by1 pixel. Raw initial screenshots reflect viewport/scaling behavior; final desktop proof is kg_productization_desktop_results.png. Temporary viewport reset. Seeded Graph Lab loaded10 recommendations and author-node inspection displayed actual connected books. Browser report: kg_productization_browser_checks.json. No production account/circulation mutation; disposable validation identity cleaned up.

U. **Tests:** backend385pass/1 unchanged failure; targeted frontend129pass; standard frontend31routing/read-now+81assistantpass (81assistant overlap the targeted run;160 distinct frontend cases). Covers identity/limits/freshness/availability/paths/empty/determinism/zero-Qwen, phrase routing, search depth, SHOW_MORE, read-now routing and private document cache/access. Collection hashes unchanged during live read-only validation. Logs named kg_productization_*_tests.log.

V. **Build/lint:** production TypeScript+Vite buildPASS; lint exit0 with19 existing warnings. No new dependency.

W. **Known failures/limits:** unchanged tests/test_rag_query_types.py::test_overview_rule_never_accepts_added_premises[What are the major themes of this book?]. Existing19 lint warnings. V2 usefulness gateFAIL; no fullV2/no promotion. Live port8005 assistant not started; live-Core orchestrator harness verified. Core+Vite are running; Search8003/recommender8004/RAG8005 are not started by this validation. Sparse/stale/excluded books may produce fewer than10; shared metadata does not guarantee useful similarity. Prior failed staging artifact retained and never selected. Screenshot capture with some resized viewport overrides was unreliable; DOM geometry is recorded and final proof captured after reset. No weak-relation implementation is fabricated from absent fields.

X. **Exact start commands** (separate terminals):

```powershell
{commands}
```

Open http://127.0.0.1:5173/book/OL19545719W and sign in normally. Stop at productization + ontology evaluation. No KG4, graph embeddings, user nodes, Search/KG blending or Qwen ontology generation.
""", encoding='utf-8')
    print('Wrote productization, metadata, build and integrity reports; preserved original KG31/KG3 evidence.')


if __name__ == '__main__':
    main()
