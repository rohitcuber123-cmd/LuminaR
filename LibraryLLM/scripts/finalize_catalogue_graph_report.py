"""Derive the KG handoff from frozen measurement rows and integrity evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from knowledge_graph.core import terms


def main():
    report_dir = ROOT / 'reports'
    evaluation = json.loads((report_dir / 'kg3_evaluation.json').read_text())
    summary = evaluation['summary']
    manifest = json.loads((report_dir / 'document_rag_latency_baseline/manifest.json').read_text())
    changed, missing = [], []
    for name, record in manifest.items():
        path = ROOT / name
        if not path.exists():
            missing.append(name)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            changed.append(name)
    expected = {'backend/main.py', 'frontend/src/App.tsx', 'frontend/src/components/Header.tsx', 'rag/api.py'}
    assert set(changed) == expected and not missing
    old_rag = (report_dir / 'document_rag_latency_baseline/snapshot/rag/api.py').read_text().splitlines()
    current_rag = (ROOT / 'rag/api.py').read_text().splitlines()
    prior_installation = {'from rag.document_latency import install_document_latency', 'install_document_latency(engine)'}
    assert [line for line in current_rag if line not in prior_installation] == old_rag
    path_count = 0
    for row in evaluation['runs']:
        seed = next(book for book in evaluation['seeds'] if book['work_id'] == row['work_id'])
        books = {book['work_id']: book for book in row['kg']}
        for candidate_id, paths in row['reason_paths'].items():
            for path in paths:
                path_count += 1
                field = 'authors' if path['kind'] == 'author' else 'subjects'
                assert path['nodes'][0] == seed['work_id'] and path['nodes'][2] == candidate_id
                assert path['catalogue_degree'] > 0 and path['contribution'] > 0
                evidence = path['provenance']
                assert len(evidence) == 2 and all(item['field'] == field for item in evidence)
                assert evidence[0]['work_id'] == seed['work_id'] and evidence[1]['work_id'] == candidate_id
                assert set(terms([evidence[0]['value']])) <= set(terms(seed[field]))
                assert set(terms([evidence[1]['value']])) <= set(terms(books[candidate_id][field]))
                assert set(terms([evidence[0]['value']])) == set(terms([evidence[1]['value']]))
    integrity = {
        'baseline_files': len(manifest), 'unchanged': len(manifest) - len(changed),
        'changed_vs_previous_pre_document_latency_baseline': changed, 'missing': missing,
        'previous_document_latency_installation_only': True,
        'kg_existing_file_edits': sorted(expected - {'rag/api.py'}),
        'previous_reports_unchanged': all(name not in changed for name in manifest if name.startswith('reports/')),
        'recommendation_search_assistant_sources_unchanged': all(name not in changed for name in manifest if name.startswith(('recommendation/', 'search/', 'assistant/'))),
        'reason_paths_checked': path_count, 'reason_path_validity': 1.0,
        'account_circulation_feedback_writes_by_evaluation': False,
        'evaluation_state_digests_unchanged': evaluation['real_state_unchanged'],
    }
    browser_checks = {
        'route': 'http://127.0.0.1:5173/experimental/kg', 'authenticated_normal_reader': True,
        'real_seed': 'OL19545719W', 'recommendations': 10, 'connected_candidates': 74507,
        'comparison_visible': {'shared_books': 2, 'overlap_percent': 20, 'kg_only_books': 8, 'existing_subject_diversity_rounded': .76, 'kg_subject_diversity_rounded': .78},
        'checks': ['subject-node inspection', 'book-node inspection using Enter', 'subject filter hides/restores subject nodes', 'expanded paths show contributions and both source-field values', 'zoom controls', 'existing header/footer/assistant overlay present'],
        'console_errors': [],
        'responsive_checks': [
            {'requested_width': 390, 'observed_dom_client_width': 469, 'observed_dom_scroll_width': 469},
            {'requested_width': 1280, 'observed_dom_client_width': 1581, 'observed_dom_scroll_width': 1581},
            {'viewport_override_reset': True, 'observed_dom_client_width': 1192, 'observed_dom_scroll_width': 1192}],
        'viewport_note': 'Browser reporting differs from requested override sizes; tested rendered narrow and wide layouts, without claiming exact device emulation. The map intentionally scrolls within its own container.',
        'screenshot': 'reports/kg_graph_preview.png',
    }
    output = {'created_at': datetime.now(timezone.utc).isoformat(), 'status': 'KG1–KG3 complete; KG4 deferred',
              'snapshot': evaluation['snapshot'], 'database_bytes': (ROOT / 'knowledge_graph/data/catalogue.sqlite').stat().st_size,
              'summary': summary, 'integrity': integrity, 'browser_checks': browser_checks,
              'tests': {'backend_passed': 401, 'backend_existing_skipped': 10, 'kg_backend_included': 12,
                        'frontend_regression_passed': 111, 'kg_frontend_passed': 5, 'independent_frontend_passed': 5,
                        'production_build': 'PASS', 'lint': 'PASS with 18 existing warnings'},
              'kg4_decision': 'DEFERRED: paired diversity decline exceeds 0.05; independent relevance/reader-utility evidence is absent.'}
    def write_json(name, value):
        path = report_dir / name
        if path.exists():
            raise FileExistsError(f'Refusing to replace evidence: {path}')
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    write_json('kg_integrity.json', integrity)
    write_json('kg_browser_checks.json', browser_checks)
    write_json('knowledge_graph_final.json', output)
    lines = [
        '# LuminaR KG1–KG3: implementation and measured comparison', '',
        'KG1–KG3 are complete in the existing frontend at `/experimental/kg`. KG4 is **deferred**. Existing recommendation candidates and scoring remain unchanged.', '',
        '## Catalogue graph', '',
        'The full Mongo catalogue supplied **5,000,000 books**, **2,454,492 author-name nodes**, **975,785 subject-label nodes**, and **29,406,707 typed edges**. No rows were skipped. Missing author metadata: 60,151 books; missing subjects: 257,541; isolated books: 1,211.', '',
        f"Snapshot: {evaluation['snapshot']['created_at']}. Build: {evaluation['snapshot']['build_seconds']:.2f} seconds. SQLite: {output['database_bytes']:,} bytes (5.87 GB). Public-metadata stream digest: `{evaluation['snapshot']['catalogue_hash']}`.", '',
        'The builder streams projected public fields in batches and creates indexes before atomically publishing the local artifact. Runtime connections are read-only. This graph needs no Neo4j, embedding, LLM, document content or new dependency.', '',
        'Book → AUTHORED_BY → Author name and Book → HAS_SUBJECT → Subject label. Normalize NFKC, case folding and whitespace; split only pipes, preserving commas inside names. These are label matches, without verified author identity resolution or a multilingual subject ontology.', '',
        'For N books and feature degree d, weight = `(2 for author, else 1) * (1 + ln((N+1)/(d+1)))`. Similarity is weighted cosine over **all shared features** and all connected candidates. Each shared feature contributes weight² / sqrt(seed norm × candidate norm). All contributions sum to the score. Scores measure metadata similarity, not relevance probability.', '',
        f'Every returned path has two original catalogue field values and work IDs, a degree and a contribution. {path_count:,} paths from the real evaluation passed source-field membership and typed two-hop checks. Focused tests separately verify contribution sums. The interactive map displays the strongest three paths per recommendation; expanded evidence exposes every path.', '',
        '## KG3 protocol and results', '',
        '40 seeds were frozen before outcomes: 32 equally spaced positions across the full snapshot, two each with no authors/no subjects/no links, and two existing recommendation fixtures. Deduplication occurred before evaluation. This is a systematic and edge-case-enriched set, **not a random representative sample** of reader demand.', '',
        'Both methods used one real verified reader, the same work ID, k=10 and active loan/reservation exclusions. The baseline is the actual existing `/recommendations/from-book` service; no substitute scorer. All 40 paired requests succeeded, with no failures. The graph snapshot and seed list are retained in JSON.', '',
        '| Measurement | Existing | KG |', '|---|---:|---:|',
        '| Seeds with results | 100% (40/40) | 95% (38/40) |',
        '| Seeds returning all ten | 100% (40/40) | 87.5% (35/40) |',
        '| Distinct recommended work IDs | 400 | 356 |',
        '| Catalogue coverage across these seeds | 0.008% | 0.00712% |',
        '| Mean measured subject diversity | 0.7865 | 0.7196 |',
        '| Warm per-seed request median | 426.05 ms | 289.25 ms |',
        '| Largest measured request | 860.82 ms | 2596.64 ms |', '',
        '**Mean overlap: 14%. Mean Jaccard: 0.06367. 92.5% of seeds had at least one KG-only candidate.** Two intentionally isolated seeds had no KG candidates.', '',
        'Overlap is intersection size divided by the smaller nonempty returned list size; empty-list overlap is zero. Jaccard divides intersection by union. Both compare work IDs, so catalogue works with identical titles remain separate. Catalogue coverage divides distinct returned work IDs by all 5M books and applies only to these 40 seeds.', '',
        'Subject diversity is mean pairwise `1 − Jaccard(normalized subject sets)`. Pairs with missing subjects are omitted and their counts are retained in each JSON row. Undefined list diversity is omitted from the method means. The fair paired comparison has **36 seeds**, mean KG-minus-existing diversity **−0.05720**; the remaining four pairs cannot measure both diversities. Different method means therefore do not substitute for the paired delta.', '',
        'Latency is one sequential request per method per seed after a separate warm-up, on this local machine with existing loaded models. It is a median across seeds, not repeated-request or concurrent-load benchmarking. Some common-feature KG queries take longer because their full connected candidate pool is evaluated.', '',
        '## KG4 decision', '',
        'The candidate gate was specified before outcomes: nonempty seed coverage ≥0.90, KG-only candidate seed fraction ≥0.50, mean paired diversity decline ≤0.05, and reason-path validity 1.0. Coverage, novelty and path validity pass. Diversity **fails**: −0.05720 exceeds the permitted decline. The independent quality condition also fails because there are no relevance or reader-utility labels.', '',
        '**Do not run hybrid reranking yet.** Novelty, coverage and metadata diversity cannot establish useful recommendation improvements. No candidate union, reranker change, production replacement or KG4 experiment was added.', '',
        '## Existing frontend and live checks', '',
        'The protected experimental route and Graph Lab navigation link reuse the current frontend shell and chatbot overlay. It supports title-prefix/work-ID lookup, opt-in exploration, typed graph nodes, keyboard inspection, metadata filters, zoom, book details/reseeding, complete reason evidence and explicit side-by-side comparison. Aborted requests cannot replace a newly selected seed; unavailable baseline service returns an error without invented metrics.', '',
        'After the user signed in, live catalogue results for Fundamentals of Deep Learning showed ten KG recommendations from 74,507 connected candidates. Both lists were visible: two shared books (20%), eight KG-only books, rounded diversity 0.76 existing / 0.78 KG. These single-seed values are distinct from the aggregate experiment.', '',
        'Live checks confirmed subject inspection, Enter-key book selection, subject hiding/restoration, source-field disclosures and zoom. No console errors were captured. Narrow/wide rendered layouts had no document horizontal overflow; map overflow stays within its scroll container. Browser viewport override widths differed from reported DOM widths, so exact 390-pixel device emulation is not claimed. The override was reset. See `kg_browser_checks.json` and `kg_graph_preview.png`.', '',
        '## Validation, preservation and limits', '',
        '**401 backend tests passed; 10 existing skipped.** Includes 12 KG tests and prior assistant/document-RAG checks. Existing frontend suites: **111 passed**; KG frontend: **5 passed**; independent frontend contracts: **5 passed**. Production build passed. Lint passed with 18 existing warnings; no KG warnings. The existing backend warning concerns FastAPI/Starlette httpx deprecation.', '',
        'Against the prior 1208-file pre-document-latency baseline, 1204 files remain byte-identical and none are missing. Three KG edits register the backend route, frontend route and navigation item. The fourth difference is the already completed document-latency installation: verified as exactly its two prior installation lines. Recommendation/search/assistant sources and all previous report files in that baseline are unchanged. Full comparison is in `kg_integrity.json`.', '',
        'The evaluator hashes existing circulation/reading-list/feedback collections before and after; hashes match. It does not write accounts, issues, reservations, lists or feedback. Mongo catalogue is read-only. New local graph/evaluation artifacts are the intended outputs.', '',
        'Snapshots do not auto-refresh. Changed seed features return 409; missing/inactive/changed candidate features are filtered against live Mongo, which may shorten the list. Labels may be noisy or ambiguous and miss synonym relationships. Metadata similarity can favor narrowly similar works; no relevance labels support quality claims. No deployment or new model worker was started. Core/search/recommendation/Vite local services remain running for the user preview.', '',
        '## Reproduction and evidence', '',
        'See `knowledge_graph/README.md` for local commands. Builders refuse graph overwrite; evaluator refuses to replace its comparison report. Preserve the snapshot and reports before a deliberate rebuild/re-evaluation.', '',
        '- Build metadata: `kg1_kg2_build.json`, `kg_build.log`, `kg_build_progress.json`.',
        '- Frozen seeds and raw results: `kg3_seeds.json`, `kg3_evaluation.json`, `kg3_evaluation.log`.',
        '- Validation: `kg_backend_focused.log`, `kg_backend_regression.log`, `kg_frontend_focused.log`, `kg_frontend_regression.log`, `kg_independent_frontend.log`, `kg_frontend_build.log`, `kg_frontend_lint.log`.',
        '- Final structured handoff: `knowledge_graph_final.json`.', '',
        '## Per-seed outcomes', '',
        '| Work ID | Stratum | Existing / KG results | Overlap | Existing / KG diversity | Existing / KG ms |',
        '|---|---|---:|---:|---:|---:|',
    ]
    def value(number):
        return 'undefined' if number is None else f'{number:.4f}'
    for row in evaluation['runs']:
        metrics = row['metrics']
        lines.append(f"| {row['work_id']} | {row['stratum']} | {len(row['existing'])} / {len(row['kg'])} | {metrics['overlap_at_k']:.2f} | {value(metrics['existing_diversity']['subject_pairwise_distance'])} / {value(metrics['kg_diversity']['subject_pairwise_distance'])} | {row['existing_ms']:.2f} / {row['kg_ms']:.2f} |")
    path = report_dir / 'knowledge_graph_final.md'
    assert not path.exists()
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'paths_checked': path_count, 'integrity': integrity, 'report': str(path)}, indent=2))


if __name__ == '__main__':
    main()
