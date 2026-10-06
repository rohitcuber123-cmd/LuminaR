"""Finalize repair evidence only after production/live/UI checks pass."""
import json
from pathlib import Path
from statistics import median
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from events_evidence import digest, sources

REPORTS = ROOT / 'reports'


def load(name):
    return json.loads((REPORTS / name).read_text(encoding='utf8'))


def main():
    live = load('assistant_selected_context_live.json')
    rows = {r['name']: r for r in live['cases']}
    ids = [b['work_id'] for b in live['books']]
    pair = ids[:2]
    fallback = ['reported', 'connects', 'sounds', 'titles', 'related',
                'three', 'ordinal_relation', 'publication_cause', 'one_famous']
    for name in fallback:
        row = rows[name]
        expected = ids[:3] if name == 'three' else ids if name == 'four' else ids[:1] if name == 'one_famous' else pair
        assert [b['work_id'] for b in row['response']['books']] == expected, name
        assert row['profile']['route'] == 'SELECTED_BOOK_CONTEXT_QUESTION', name
        assert not row['response']['clarification'] and not row['response']['errors'], name
        assert row['profile']['fuzzy_title_calls'] == row['profile']['search_calls'] == 0, name
        assert row['profile']['qwen_call_count'] == 2, name
    structured = {'rating': 'COMPARE_BOOKS',
                  'availability': 'CHECK_AVAILABILITY', 'loans': 'USER_LOANS',
                  'account_borrowed': 'USER_LOANS', 'search': 'SEARCH_BOOKS',
                  'search_databases': 'SEARCH_BOOKS', 'details_second': 'BOOK_DETAILS',
                  'recommend': 'RECOMMEND_FROM_SELECTION',
                  'graph_second': 'MORE_LIKE_THIS', 'borrow': 'BORROW_BOOK',
                  'reading_list': 'ADD_TO_READING_LIST', 'rag': 'BOOK_CONTENT_QUESTION'}
    for name, intent in structured.items():
        assert rows[name]['response']['intent'] == intent, (name, rows[name]['response']['intent'])
        assert rows[name]['profile']['qwen_call_count'] == 1, name
        assert not rows[name]['response']['clarification'], name
        if name != 'rag': assert not rows[name]['response']['errors'], name
    for name, expected in [('difference', pair), ('share', pair), ('criterion', pair), ('four', ids), ('single_stands', ids[:1]), ('single_read', ids[:1]), ('single_about', ids[:1])]:
        body = rows[name]['response']
        books = body['books'] or (body.get('comparison') or {}).get('books', [])
        assert [b['work_id'] for b in books] == expected, name
        assert not body['clarification'] and not body['errors'], name
        assert rows[name]['profile']['fuzzy_title_calls'] == rows[name]['profile']['search_calls'] == 0
    assert [b['work_id'] for b in rows['availability']['response']['books']] == ids[1:2]
    assert [b['work_id'] for b in rows['details_second']['response']['books']] == ids[1:2]
    assert rows['borrow']['response']['pending_action'] and rows['reading_list']['response']['pending_action']
    assert rows['rag']['response']['errors'] and rows['rag']['profile']['stages_ms']['qwen_rag_generation'] == 0
    assert rows['override']['response']['clarification']['type'] == 'TITLE_AMBIGUITY'
    assert all(b['work_id'] not in pair for b in rows['override']['response']['clarification']['choices'])
    assert rows['missing_third']['response']['clarification']
    for name in ['clear', 'chain_cleared']:
        assert not rows[name]['selected_work_ids'] and not rows[name]['profile']['selected_context_bound']
        assert not rows[name]['response']['errors']
    for name, expected in [('replace', ids[2:]), ('chain_pair', pair),
                           ('chain_replaced', ids[2:]), ('chain_removed', ids[2:3])]:
        assert [b['work_id'] for b in rows[name]['response']['books']] == expected, name
        assert not rows[name]['response']['errors'] and not rows[name]['response']['clarification'], name
    for name in ['ui_compare', 'ui_availability']:
        assert rows[name]['profile']['qwen_call_count'] == 0
        assert not rows[name]['response']['errors'] and not rows[name]['response']['clarification']
    ui = load('assistant_selected_context_ui.json')
    assert ui['reported_pair_pass'] and ui['new_chat_preserved_selection'] and ui['remove_pass']
    assert (REPORTS / 'assistant_selected_context_ui.png').exists()

    suites = {}
    for group in ['unit', 'assistant', 'security', 'staff', 'notifications', 'circulation', 'search', 'events', 'new_backend']:
        name = f'assistant_selected_context_regression_{group}.xml' if group not in ['events', 'new_backend'] else f'assistant_selected_context_{group}.xml'
        root = ET.parse(REPORTS / name).getroot()
        tests = root.findall('testsuite') if root.tag == 'testsuites' else [root]
        counts = {key: sum(int(s.get(key, 0)) for s in tests) for key in ['tests', 'failures', 'errors', 'skipped']}
        counts['passed'] = counts['tests'] - counts['failures'] - counts['errors'] - counts['skipped']
        assert counts['failures'] == counts['errors'] == 0, group
        suites[group] = {**counts, 'report': name}
    front = (REPORTS / 'assistant_selected_context_frontend_regression_serial.log').read_text(encoding='utf8')
    assert 'pass 246' in front and 'fail 0' in front
    assert 'built in' in (REPORTS / 'assistant_selected_context_build.log').read_text(encoding='utf8')
    lint = (REPORTS / 'assistant_selected_context_lint.log').read_text(encoding='utf8')
    assert ': error ' not in lint and lint.count(': warning ') == 19
    baseline = load('assistant_selected_context_repair_baseline.json')['files']
    current = {p.relative_to(ROOT).as_posix(): digest(p) for p in sources()}
    for p in REPORTS.glob('events*'):
        if p.is_file() and p.suffix in {'.md', '.json'}: current[p.relative_to(ROOT).as_posix()] = digest(p)
    changed = sorted(p for p, h in baseline.items() if current.get(p) != h)
    allowed = sorted(['assistant/orchestrator.py', 'assistant/qwen.py', 'assistant/schemas.py',
                      'assistant/semantic.py', 'assistant/tools.py', 'frontend/tests/assistant.test.tsx'])
    assert changed == allowed, changed
    new = sorted(set(current) - set(baseline))
    runtime = load('assistant_selected_context_profiles.jsonl.runtime.json')
    assert runtime['router_mode'] == 'existing_qwen' and not runtime['experimental_router_modules']
    assert not runtime['child_processes']
    perf_names = ['reported', 'rating', 'availability', 'search', 'loans', 'ui_compare', 'ui_availability']
    performance = {name: {key: rows[name]['profile'].get(key) for key in
                         ['total_ms', 'qwen_call_count', 'fuzzy_title_calls', 'search_calls', 'tool_calls', 'selected_count', 'selected_context_bound', 'route']}
                   for name in perf_names}
    regression = {'status': 'PASS', 'backend_suites': suites,
                  'backend_passed': sum(s['passed'] for s in suites.values()),
                  'backend_skipped': sum(s['skipped'] for s in suites.values()),
                  'frontend_passed': 246, 'frontend_new_tests': 6, 'build': 'PASS', 'lint_errors': 0,
                  'lint_existing_warnings': 19, 'changed_files': changed, 'new_files': new,
                  'baseline_files': len(baseline), 'preserved_baseline_files': len(baseline) - len(changed),
                  'preservation': {'events': True, 'search': True, 'recommendation': True, 'kg': True,
                                   'rag': True, 'router_research_v1_v5': True},
                  'router_mode': runtime['router_mode'], 'experimental_router_modules': [],
                  'live_cases': len(rows), 'performance': performance,
                  'fallback_median_ms': round(median(rows[n]['profile']['total_ms'] for n in fallback), 2),
                  'ui': ui, 'cleanup': load('assistant_selected_context_cleanup.json')}
    assert regression['cleanup']['disposable_reader_removed'] and regression['cleanup']['temporary_frontend_stopped']
    (REPORTS / 'assistant_selected_context_regression.json').write_text(json.dumps(regression, indent=2), encoding='utf8')
    live['status'] = 'PASS'
    live['acceptance'] = {'original_pair': True, 'paraphrases': True, 'sizes_1_to_4': True,
                          'same_conversation_selection_change': True, 'structured_routes': True,
                          'fuzzy_and_unrelated_search_zero': True, 'metadata_only': True,
                          'ui_payload_contract': True}
    (REPORTS / 'assistant_selected_context_live.json').write_text(json.dumps(live, indent=2), encoding='utf8')
    files = '\n'.join(f'- `{p}`' for p in changed + new)
    perf_table = '\n'.join(f'| {name} | {p["total_ms"]:.0f} | {p["qwen_call_count"]} | {p["fuzzy_title_calls"]} | {p["search_calls"]} |' for name, p in performance.items())
    text = f'''# Assistant selected-context repair: PASS

Production remains `existing_qwen`; Router V1-V5 research stays frozen. No new model, classifier, retry generation, Search ranking, recommendation algorithm, KG or RAG changes.

## Root cause and repair

The visible tray already sent the correct IDs. The semantic contract did not consistently treat the current selection as explicit context, and general help had no authoritative selected-metadata binding before clarification. The repair supplies selected count/status and ordered catalogue titles to the existing router, preserves literal-title precedence, and binds current canonical IDs before conversational answering. Requested positions are validated; free-form explanations receive the entire selected set, so cross-ordinal questions retain both records. Structured tools retain their own positional targets.

Typed messages snapshot the visible tray. New chat intentionally clears conversation/history while preserving selection. Six frontend tests verify payload, count, removal, replacement, Clear and New chat; no frontend production change was necessary.

Metadata is limited to four records: title 200 characters, authors four by 80 (or string 320), subjects eight by 80 (or string 640), description 1200. Qwen chooses one to three verified observations with an enum-constrained answer plan; application rendering supplies canonical titles and source-derived facts. This prevents invented descriptions or publication claims. Answers remain verified observations; missing cause/reputation/publication evidence cannot support an invented claim. Source-gap notes are available in the answer plan. No full catalogue/private data or automatic RAG chunks are supplied. Prompt-only free prose failed source grounding during development and was replaced before acceptance.

## Live results

Actual pair: `OL17930368W` (Atomic Habits) and `OL37490159W` (Atomic Habits, I Will Teach You To Be Rich, Mindset, The One Thing 4 Books Collection Set). The collection is one catalogue record and has no description. The original question now mentions both titles and their recorded shared words/authorship. There is no missing-book clarification, fuzzy title resolution or unrelated Search.

Seven original paraphrases pass; the main-difference request uses verified metadata contrasts while objective rating comparison remains structured. First/second relationship reasoning, source-limited inspiration, single-book reputation, three and four selections also pass. A same-conversation chain replaces the pair, removes one and clears selection while deliberately supplying stale page/recent IDs; current selection wins. Invalid third position clarifies. Explicit Frankenstein overrides selection through normal catalogue title ambiguity (several real works); the user must choose the intended edition/work.

Higher rating uses authoritative comparison, second availability uses Core, ordinal details use catalogue, recommendations use both seeds, related alternatives use KG, and borrow/reading-list actions retain pending confirmation. Account requests remain account; unseeded topics remain Search. A real chapter request uses Book RAG and is denied for the disposable reader without an active borrow; no metadata answer bypasses that boundary.

## Performance and generation counts

Each selected answer plan uses one generation. Typed free-form fallback uses the existing router plus that plan: two total. Typed structured operations use one routing generation. Explicit UI comparison/availability use zero. Removing the routing pass would require a broader change and cannot safely identify account, Search, mutations or content questions from selection alone.

| Check | Total ms | Qwen | Fuzzy | Search |
|---|---:|---:|---:|---:|
{perf_table}

Fallback median: {regression['fallback_median_ms']:.0f} ms on the current local GPU. These are observed serial development timings, not a benchmark or latency guarantee. Numeric/categorical profiles contain counts, route and timings; no raw user question, email or metadata is recorded in profiling.

## Validation and preservation

Backend: {regression['backend_passed']} passed, {regression['backend_skipped']} existing optional security/integration skips, zero failures/errors, including {suites['new_backend']['passed']} new repair tests. Frontend: 246 passed (six new payload tests). Build passes; lint has zero errors and 19 existing warnings. Existing bundle-size warning remains.

Initial concurrent frontend testing exhausted memory and MongoDB stopped. The user restored MongoDB; final frontend tests ran serially and all database-dependent groups passed after recovery. On resumption, missing normal services were restored and the disposable access token refreshed. Intermediate failures are retained in development logs; final XML and live evidence determine acceptance.

Hash audit: {len(baseline)} baseline files, exactly six existing files changed. All Events reports/source, Search, Recommendations, KG, RAG and Router V1-V5 research/models remain unchanged. Runtime has no experimental router imports or child worker processes. Disposable account and temporary frontend are cleaned up; normal local stack remains running.

## Exact files changed or added

{files}

## Evidence and limits

- `assistant_selected_context_live.json`: raw public-book live answers, canonical IDs, profiles and acceptance.
- `assistant_selected_context_regression.json`: tests, preservation, exact files, performance and cleanup.
- `assistant_selected_context_ui.png` / `assistant_selected_context_ui.json`: real frontend pair/tray/answer and New chat/removal proof.
- XML/logs under `assistant_selected_context_*`: suite results and development diagnostics.

Answers are bounded catalogue observations, not unrestricted literary analysis. The collection lacks a description. Publication influence/reputation cannot be established from absent metadata. Explicit-title ambiguity still needs user choice. True Book RAG requires its existing borrow authorization. Two total generations remain for typed fallback. No Router V6 was started. Repair work stops here.
'''
    (REPORTS / 'assistant_selected_context_repair.md').write_text(text, encoding='utf8')
    print(json.dumps({'status': 'PASS', 'backend': regression['backend_passed'], 'skipped': regression['backend_skipped'],
                      'live_cases': len(rows), 'performance': performance, 'changed': changed, 'new': new}, indent=2))


if __name__ == '__main__':
    main()
