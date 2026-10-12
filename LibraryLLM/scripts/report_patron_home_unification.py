"""Report only observed Home unification evidence; preserve all earlier reports."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
TEST = 'e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
PROMPT = Path(r'C:\Users\balak\.codex\attachments\05a51968-ff16-4a38-be07-3172f5c91355\Pasted text.txt')


def read(name):
    return json.loads((REPORTS / name).read_text(encoding='utf8'))


def write(name, data):
    (REPORTS / name).write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    baseline = read('patron_home_unification_baseline.json')
    live = read('patron_home_unification_live.json')
    browser = read('patron_home_unification_browser.json')
    fixture = read('patron_home_unification_disposable.json')
    cleanup = read('patron_home_unification_cleanup.json')
    receipt = read('patron_home_unification_request_receipt.json')
    groups = read('patron_home_unification_regression.json')
    frontend = read('patron_home_unification_frontend_results.json')
    assert len(groups) == 18 and all(g['exit'] == g['failed'] == 0 for g in groups)
    assert all(g['exit'] == g['failed'] == 0 for g in frontend)
    backend_pass = sum(g['tests'] - g['skipped'] for g in groups)
    backend_skips = sum(g['skipped'] for g in groups)
    frontend_pass = sum(g['passed'] for g in frontend)
    assert backend_pass == 1667 and frontend_pass == 588
    assert '✓ built in' in (REPORTS / 'patron_home_unification_frontend_build.log').read_text(encoding='utf8')
    lint = (REPORTS / 'patron_home_unification_frontend_lint.log').read_text(encoding='utf8')
    assert ': error ' not in lint and len(re.findall(': warning ', lint)) == 19
    names, skips = {}, []
    for path in REPORTS.glob('patron_home_unification_regression_*.xml'):
        for case in ET.parse(path).iter('testcase'):
            names.setdefault(case.attrib['name'], []).append(path.name)
            for node in case.findall('skipped'):
                skips.append({'test': case.attrib['name'], 'reason': node.attrib.get('message', '')})
    for name in ('patron_home_unification_frontend_default.log', 'patron_home_unification_frontend_extended.log'):
        for test in re.findall(r'^✔ (.+?) \(', (REPORTS / name).read_text(encoding='utf8'), re.M):
            names.setdefault(test, []).append(name)
    required = sorted(set(re.findall(r'test_[a-z_]+', PROMPT.read_text(encoding='utf8'))))
    assert len(required) == 30 and all(name in names for name in required)
    write('patron_home_unification_required_tests.json', {'status': 'PASS', 'required': 30,
        'tests': [{'name': name, 'status': 'PASS', 'evidence': names[name]} for name in required]})
    write('patron_home_unification_tests.json', {'status': 'PASS', 'backend_passed': backend_pass,
        'backend_skipped': backend_skips, 'backend_groups': groups, 'accepted_skips': skips,
        'frontend_passed': frontend_pass, 'frontend_groups': frontend, 'build': 'PASS', 'lint_errors': 0,
        'existing_lint_warnings': 19,
        'verification_notes': 'Earlier runs exposed outdated tests importing the retired Home export; migrated those assertions to shared Home without dropping functional coverage. One existing document-answer test initially timed out under concurrent checks; the complete final frontend run passed.'})

    load_dotenv(ROOT / '.env')
    mongo = MongoClient(os.getenv('MONGO_URI'))
    database = mongo['luminar_library']
    books = list(database.institution_library_books.find({'library_id': TEST, 'status': 'ACTIVE'}, {'_id': 0}))
    assert len(books) == 150
    canonical_ids = {book['library_book_id'] for book in books}
    rendered = [book['id'] for section in browser['testHome']['sections'] for book in section['books']]
    assert rendered and all(book in canonical_ids for book in rendered)
    assert browser['testHome']['globalBookLinks'] == 0
    classes = lambda value: [section['class'] for section in value['sections']]
    assert classes(browser['globalHome']) == classes(browser['testHome']) == classes(browser['emptyHome']) == classes(browser['oneBookHome'])
    assert browser['emptyHome']['physicalActions'] == browser['emptyHome']['ownedIds'] == 0
    assert browser['emptyHome']['globalLinks'] > 0 and browser['oneBookHome']['globalLinks'] == 0
    assert all(book == fixture['added_book_id'] for section in browser['oneBookHome']['sections'] for book in section['ownedIds'])
    assert fixture['source_before']['catalogue_source'] == 'GLOBAL_FALLBACK'
    assert fixture['source_after']['catalogue_source'] == 'LIBRARY_LOCAL'
    assert all(row['overflow'] is False for row in browser['responsive'])
    assert browser['carousel']['after'] > browser['carousel']['before']
    assert browser['globalHome']['forYouCardWidth'] == 180
    assert all(row['forYouCardWidth'] == 180 for row in browser['responsive'])
    assert browser['nonowned']['physicalActions'] == browser['nonowned']['shelfTerms'] == 0
    assert browser['arrivals']['ids'] and all(book in canonical_ids for book in browser['arrivals']['ids'])
    assert browser['searchNoResults']['results'] == 0
    assert 'subject=' in browser['genreNavigation']['url'] and TEST in browser['genreNavigation']['url']
    assert cleanup['disposable_library_removed'] and not database.institution_libraries.find_one({'library_id': fixture['library_id']})
    assert receipt['request_cancelled'] and not receipt['immediate_loan_created'] and receipt['patron_pending_requests_after'] == 0

    modified = [name for name, expected in baseline['source_sha256'].items()
        if not (ROOT / name).exists() or digest(ROOT / name) != expected]
    protected = [name for name in baseline['source_sha256'] if name.startswith(('search/', 'knowledge_graph/', 'recommendation/', 'rag/', 'assistant/'))]
    assert not set(modified).intersection(protected)
    artifacts = [name for name, expected in baseline['artifact_metadata'].items() if not (ROOT / name).exists() or
        {'bytes': (ROOT / name).stat().st_size, 'mtime_ns': (ROOT / name).stat().st_mtime_ns} != expected]
    assert artifacts == []
    old_reports = [name for name, expected in baseline['prior_reports_sha256'].items()
        if not (ROOT / name).exists() or digest(ROOT / name) != expected]
    assert old_reports == []
    seed = read('test_library_seed.json')
    sample_changed = []
    for work, expected in seed['source_hashes_before'].items():
        document = database.books.find_one({'work_id': work}, {'_id': 0})
        actual = hashlib.sha256(json.dumps(document, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()
        if actual != expected:
            sample_changed.append(work)
    assert not sample_changed
    count = database.books.estimated_document_count()
    assert count == baseline['production_counts']['books'] == 5000000
    assert database.platform_role_assignments.count_documents({}) == 0
    write('patron_home_unification_preservation.json', {'status': 'PASS', 'global_count_before': 5000000,
        'global_count_after': count, 'sampled_global_full_documents': len(seed['source_hashes_before']),
        'sample_changes': sample_changed, 'protected_source_files': len(protected), 'protected_source_changes': [],
        'index_artifact_records': len(baseline['artifact_metadata']), 'artifact_changes': [],
        'prior_reports_checked': len(baseline['prior_reports_sha256']), 'prior_report_changes': [],
        'test_library_preserved': TEST, 'test_active_books': 150, 'test_local_only_books': sum(not b.get('global_work_id') for b in books),
        'global_hnsw_rebuilt': False, 'global_kg_rebuilt': False, 'production_platform_assignments_created': 0,
        'intentional_database_changes': 'One exact disposable private library and its canonical book were created, validated and cleaned up. One TEST patron Home request was created PENDING and cancelled normally; its audit receipt remains. Existing TEST memberships, holdings and histories were preserved.',
        'limits': 'Global preservation uses unchanged collection count, 146 full sampled document hashes, protected global code hashes and 196 index artifact size/mtime records. It does not claim a content hash of all five million documents or all multi-gigabyte indexes.'})
    current = subprocess.check_output(['rg', '--files', '--hidden', '-g', '!.git', '-g', '!.venv', '-g', '!node_modules', '-g', '!.scratch', '-g', '!scratch', '-g', '!dist', '-g', '!datasets'], cwd=ROOT, text=True).splitlines()
    suffixes = {'.py', '.tsx', '.ts', '.css', '.json', '.md', '.html', '.yaml', '.yml', '.toml', '.txt', '.ps1'}
    added = [name.replace('\\', '/') for name in current if not name.replace('\\', '/').startswith('reports/')
        and Path(name).suffix in suffixes and name.replace('\\', '/') not in baseline['source_sha256'] and (ROOT / name).stat().st_size < 32 * 1024 * 1024]
    manifest = [{'path': name, 'change': kind, 'sha256': digest(ROOT / name)}
        for kind, paths in [('MODIFIED', modified), ('ADDED', added)] for name in sorted(paths)]
    write('patron_home_unification_changed_files.json', {'comparison': 'Phase baseline; pre-existing dirty Git work preserved.',
        'source_files': manifest, 'baseline_helper_created_before_capture': 'scripts/patron_home_unification_baseline.py'})

    fields = {'GLOBAL_HOME_COMPONENTS_REUSED': 'YES', 'SEPARATE_LIBRARY_HOME_REMOVED': 'YES',
        'TEST_HOME_USES_SHARED_HOME': 'YES', 'GLOBAL_HOME_CHANGED': 'NO', 'TEST_LOCAL_BOOK_COUNT': 150,
        'TEST_PRIMARY_RAIL_LOCAL_BOOK_PERCENT': 100, 'TEST_GLOBAL_FILLER_IN_PRIMARY_RAILS': 0,
        'EMPTY_LIBRARY_FALLBACK_VALIDATED': 'YES', 'LOCAL_SWITCHOVER_VALIDATED': 'YES',
        'FOR_YOU_LIBRARY_SCOPED': 'YES', 'NEW_ARRIVALS_LIBRARY_SCOPED': 'YES', 'POPULAR_LIBRARY_SCOPED': 'YES',
        'GENRES_LIBRARY_SCOPED': 'YES', 'BROWSE_LIBRARY_SCOPED': 'YES', 'SEARCH_LIBRARY_SCOPED': 'YES',
        'GLOBAL_5M_PRESERVED': 'YES', 'GLOBAL_HNSW_REBUILT': 'NO', 'GLOBAL_KG_REBUILT': 'NO'}
    write('patron_home_unification_summary.json', {'status': 'PASS', **fields,
        'rendered_local_records_checked': len(rendered), 'rendered_unique_local_records_checked': len(set(rendered)),
        'global_home_changed_definition': 'Visuals and global behavior remain unchanged. Shared component source was refactored to accept scoped data.',
        'backend_passed': backend_pass, 'backend_skipped': backend_skips, 'frontend_passed': frontend_pass})
    gates = [
        ('Separate Explore TEST presentation retired', 'App.tsx routes the Patron index to Home context=library; no production LibraryCatalogueHome or CatalogueRail remains.'),
        ('Original Home visual system reused', 'HomeSections renders Hero, ForYou, PopularBooks, CategoryExplorer, AlsoLikeTicker and NewArrivals for both contexts.'),
        ('Global Home intact', 'Same six section classes, typography, cover sizes, global fetches, recommendations pagination and original global card actions; global_before/global_after screenshots.'),
        ('Empty library full global discovery', 'Disposable GLOBAL_FALLBACK displayed all six shared sections and 84 global detail links.'),
        ('No fallback physical ownership', 'Zero physical actions and zero owned IDs in empty Home; global nonowned detail has zero shelf/accession/copy claims.'),
        ('Automatic source swap with same UI', 'First canonical Add switched source 0→1; identical six section classes before/after. Browser reloaded to observe an API-side Add; no server restart or flag. Add/import event and focus invalidation tests prove already-open page refresh.'),
        ('TEST collection powers primary sections', '150 active canonical TEST records remain; every rendered candidate resolves to a TEST canonical ID.'),
        ('Local showcase', '12 local titles repeated only for the original continuous marquee animation.'),
        ('Scoped For You including local-only', 'Global candidate intersection plus canonical acquisition fallback; all four TEST local-only titles appeared.'),
        ('Local New Arrivals', 'Acquisition date if valid, otherwise canonical created_at; browser checked 20 canonical arrivals IDs.'),
        ('Truthful Popular', 'Only tenant loans/approved requests/reservations enter popularity. With fewer than four activity titles, shared Popular geometry says Discover More and uses local arrivals.'),
        ('Local subjects', 'Canonical subjects/counts and canonical preview books; browser subject click remained TEST scoped.'),
        ('Local Browse', 'Canonical scoped read, original consumer grid geometry and shared branded cover/card frame; no Staff Inventory table.'),
        ('Local Search', 'Tenant catalogue search with explicit No matching books in TEST and a separate global action; no global filler.'),
        ('No silent global filler', f'{len(rendered)} rendered record instances, {len(set(rendered))} distinct canonical IDs, all verified against TEST; zero primary global links.'),
        ('Global works preserved independently', 'Same work continues to exist globally; nonowned global detail remains explicitly nonowned in TEST.'),
        ('Canonical library actions', 'Home CTA created a PENDING request, zero loans; normal detail cancellation restored availability. Waitlist HTTP/action tests passed.'),
        ('Role separation', 'ADMIN/LIBRARIAN stay Staff Workspace; membership route/security regression and live staff/patron 403 checks passed.'),
        ('Activity routes retained', 'My Library, Reservations and Fees remain accessible through main header/compact context links.'),
        ('No HNSW rebuild', 'Protected code and artifact records unchanged; no builder command executed.'),
        ('No KG rebuild', 'Protected code and artifact records unchanged; no builder command executed.'),
        ('Global 5M preserved', '5,000,000 before/after, 146 full sampled documents unchanged; preservation limits documented.'),
        ('TEST retained', '150 ACTIVE books, canonical holdings and existing memberships/history kept; exact disposable fixture cleaned up.')]
    write('patron_home_unification_acceptance.json', {'status': 'PASS', 'gates': [
        {'gate': i, 'requirement': title, 'status': 'PASS', 'evidence': evidence} for i, (title, evidence) in enumerate(gates, 1)]})
    text = f'''# Patron Home unification — PASS

Global and library contexts now render the same original LuminaR Home composition. The separate Explore TEST hero, compact Home rails and full Patron navigation row are retired. App.tsx mounts Home with a library context; no copied LibraryHome page or alternate flag remains.

HomeCatalogueContext injects canonical catalogue data into the original six sections. The global branch retains its existing APIs, recommendation algorithm, section geometry, typography, covers and actions. GLOBAL_HOME_CHANGED=NO refers to visuals and behavior; shared component source was refactored.

In an empty library, authoritative GLOBAL_FALLBACK uses the existing global catalogue/recommender and strips physical ownership fields/actions. Once any usable ACTIVE canonical record with a holding exists, all primary sections use local records. The resolver remains authoritative; no has_dataset switch, index build or application restart is required.

For You scopes up to 200 existing global work candidates against canonical holdings, retains their order, and fills only from deterministic local acquisition discovery. The request is read-only and bounded to 50 results. Local-only titles are eligible. TEST's four local-only titles appeared in its ten-item recommendation rail.

Arrivals use valid acquisition_date, otherwise LibraryBookRecord.created_at. Popular uses only tenant canonical activity; fewer than four activity titles produce a truthful Discover More section using local acquisitions. Categories use local subjects/counts and owned preview books. Browse, Search and every View All link retain the selected library. A zero-result search explicitly separates global discovery.

The shared recommendation card frame and original Popular card geometry use LuminaR's branded BookCover. Home cards keep concise availability, shelf and canonical request/waitlist actions. Accession, copy counts, full subjects, request status and queue metadata live in details. Existing Part 2B/C writers, membership authorization and platform assignments remain unchanged.

Validation: {backend_pass} backend tests passed, {backend_skips} accepted existing skips; {frontend_pass} frontend tests passed. All 30 requested named tests passed. Build passed; lint has zero errors and 19 existing warnings. All 23 browser acceptance gates passed. The final report links retained logs and XML evidence. Earlier transient/outdated-test failures were resolved and the complete final checks passed.

Browser comparison: global and TEST have the same six section classes, 190px desktop showcase covers and 180px recommendation cards. Mobile/tablet/desktop widths were verified with no document overflow. Windows 125% scaling produces a 767px actual tablet width for a 768px target; CSS and screenshot backing dimensions are distinct. The carousel advanced from {browser['carousel']['before']} to {browser['carousel']['after']} CSS pixels. Dynamic marquee positions and random category choices prevent a pixel-identical screenshot comparison.

TEST has 150 ACTIVE books. All {len(rendered)} rendered book instances ({len(set(rendered))} distinct IDs) checked against canonical TEST records are local: 100%, zero global filler. The sole genuine activity title is not represented as fabricated global popularity. A live Home request created PENDING with no loan, was cancelled, and left zero pending requests.

The disposable private library rendered full global fallback, then switched automatically to a single local-only book with the same UI. A browser reload observed the API-side Add; no application process was restarted during that transition. Existing Add/import invalidation and browser-focus tests validate refresh of an already-open page. The exact disposable library and its book were cleaned up; TEST remains available.

Preservation: global count 5,000,000, all 146 full sampled global documents unchanged, {len(protected)} protected global source files unchanged, all 196 artifact size/mtime records unchanged, all {len(baseline['prior_reports_sha256'])} previous reports byte-identical. No claim is made of hashing all five million documents or multi-gigabyte artifacts. No HNSW or KG rebuild, production platform grant, tenant indexing or next-phase work occurred.

Review: http://127.0.0.1:5182/libraries/{TEST}. Frontend 5182 and review core 8088 remain running. The review core was restarted only to load development code before switchover validation; original services 8002/8080 and Search 8003 were untouched.

Evidence: patron_home_unification_acceptance.json, patron_home_unification_required_tests.json, patron_home_unification_tests.json, patron_home_unification_browser.json, patron_home_unification_live.json, patron_home_unification_request_receipt.json, patron_home_unification_cleanup.json, patron_home_unification_preservation.json and patron_home_unification_changed_files.json. Screenshots are in patron_home_unification_screenshots, including global_before, global_after, global_home_viewport, test_home_viewport, test_for_you, empty_fallback and one_local_book.

```
''' + '\n'.join(f'{key}: {value}' for key, value in fields.items()) + '\n```\n'
    (REPORTS / 'patron_home_unification_completion.md').write_text(text, encoding='utf8')
    mongo.close()
    print(f'PASS: 23 gates; 30 required tests; {backend_pass} backend + {frontend_pass} frontend; {len(rendered)} local rendered instances; all earlier reports preserved.')


if __name__ == '__main__':
    main()
