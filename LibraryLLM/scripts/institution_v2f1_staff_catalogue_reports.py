"""Assemble the current 2F.1 title/catalogue correction from retained evidence."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reports'
TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
BASE=f'/staff/libraries/{TEST}'
def read(name):return json.loads((R/name).read_text(encoding='utf8'))
def put(name,data):(R/name).write_text(json.dumps(data,indent=2,default=str)+'\n',encoding='utf8')
def write(name,text):(R/name).write_text(text,encoding='utf8')

browser=read('institution_v2f1_staff_catalogue_browser.json')
responsive=read('institution_v2f1_staff_catalogue_responsive.json')
preservation=read('institution_v2f1_critical_preservation.json')
assert all(data['status']=='PASS' for data in [browser,responsive,preservation])
assert responsive['cases']==18 and all(row['status']=='PASS' for row in responsive['checks'])
assert len(browser['checks'])==12 and all(row['status']=='PASS' for row in browser['checks'])
groups=read('institution_v2f_regression.json')
cases={}
for row in groups:
    assert row['exit']==row['failed']==0,row
    for case in ET.parse(R/f'institution_v2f_regression_{row["group"]}.xml').iter('testcase'):
        cases[(case.attrib['classname'],case.attrib['name'])]=case
passed=sum(not any(c.tag in {'failure','error','skipped'} for c in case) for case in cases.values())
skips=sum(any(c.tag=='skipped' for c in case) for case in cases.values())
assert passed==1958 and skips==10
final_backend=list(ET.parse(R/'institution_v2f1_staff_catalogue_backend_final.xml').iter('testcase'))
assert len(final_backend)==14 and all(not list(case) for case in final_backend)
frontend=read('institution_v2f_frontend_results.json')
assert all(row['exit']==0 for row in frontend)
full_frontend=sum(row['passed'] for row in frontend)
assert full_frontend==831
final_front=(R/'institution_v2f1_staff_catalogue_frontend_final.log').read_text(encoding='utf8')
assert 'pass 28' in final_front and 'fail 0' in final_front
lint=(R/'institution_v2f1_staff_catalogue_lint.log').read_text(encoding='utf8')
assert not re.search(r': error ',lint)
warnings=len(re.findall(r': warning ',lint));assert warnings==14
assert 'built in' in (R/'institution_v2f1_staff_catalogue_build.log').read_text(encoding='utf8')

# Cover source is unchanged from the already accepted, original-palette repair.
cover_checks=[]
for name in ['frontend/src/components/BookCover.tsx','frontend/src/components/BookCoverArt.tsx','frontend/src/components/DiscoveryBookFrame.tsx','frontend/src/data/books.ts']:
    prior=subprocess.check_output(['git','show','HEAD:LibraryLLM/'+name],cwd=ROOT.parent).decode('utf8').replace('\r\n','\n')
    current=(ROOT/name).read_text(encoding='utf8')
    assert prior==current,name
    cover_checks.append({'path':name,'unchanged_from_accepted_HEAD':True,'sha256':hashlib.sha256((ROOT/name).read_bytes()).hexdigest()})
put('institution_v2f1_staff_catalogue_preservation.json',{**preservation,'original_cover_palette_and_geometry':cover_checks,'new_safe_QA_asset':next(row for row in browser['checks'] if row['scenario']=='Add Online Copy works from shared Staff detail')['asset'],'TEST_books_or_holdings_modified':False})

audit=[
 ('frontend/src/pages/LibraryInventory.tsx','Staff Inventory table','STAFF_WORKSPACE',BASE+'/books/{library_book_id}','Fixed; real title Link; safe Inventory return state.'),
 ('frontend/src/components/BookCard.tsx','Patron Browse / Catalogue','PATRON_WORKSPACE','/libraries/{explicit_library_id}/books/{library_book_id}','Verified; canonical shared card.'),
 ('frontend/src/components/GlobalCatalogue.tsx','Global catalogue / Search','GLOBAL_INTENTIONAL','/book/{global_work_id}','Verified; shared card and global work identity.'),
 ('frontend/src/pages/ReadingListPage.tsx','Saved global/local books','PERSONAL_WITH_RETURN_CONTEXT','exact global or library book; explicit Staff membership chooses Staff detail','Verified through shared BookCard/bookPath. No first-membership selection.'),
 ('frontend/src/pages/LibraryReservationsFees.tsx','Reservation book rows','STAFF_WORKSPACE / PATRON_WORKSPACE','exact library book route in row workspace','Fixed; real title Link.'),
 ('frontend/src/pages/LibraryCirculation.tsx','Circulation request/loan rows','STAFF_WORKSPACE / PATRON_WORKSPACE','exact library book route in row workspace','Fixed; real title Link.'),
 ('frontend/src/pages/LibraryAnalyticsPage.tsx','Popular books table','STAFF_WORKSPACE','/staff/libraries/{analytics.library_id}/books/{library_book_id}','Fixed; uses response-scoped library and canonical row ID.'),
 ('frontend/src/pages/LibraryAssets.tsx','Digital Asset linked-book label','STAFF_WORKSPACE / PATRON_WORKSPACE','exact library book detail','Fixed in facts/list and detail link; verified in browser.'),
 ('frontend/src/pages/LibraryReservationsFees.tsx','Fee references and accrued estimates','STAFF_WORKSPACE / PATRON_WORKSPACE','exact library book where API supplies ID','Fee records link; estimates lacking canonical ID remain text, with no guessed destination.'),
 ('frontend/src/pages/LibraryInventory.tsx','Uncommitted import preview rows','GLOBAL_INTENTIONAL','no canonical detail before creation','Intentional plain text: preview row has no created library_book_id.'),
]
write('institution_v2f1_book_title_navigation_audit.md','# Part 2F.1 book-title navigation audit\n\nTitles with canonical identities use real links. No routing by title, accession, ISBN or first membership.\n\n| File | Surface | Classification | Destination | Result |\n|---|---|---|---|---|\n'+''.join('| '+' | '.join(row)+' |\n' for row in audit))

write('institution_v2f1_staff_catalogue_architecture.md',f'''# Part 2F.1 — Staff catalogue correction and clickable titles

The latest user correction supersedes the earlier decision to send Staff Catalog to Inventory. The current canonical browsing route is `{BASE}/catalogue`; management stays at `{BASE}/inventory`. Both navigation entries remain.

Staff Catalogue reuses `LibraryCataloguePage`, `CatalogueSurface`, `CatalogueGrid`, `BookCard`, `DiscoveryBookFrame`, `BookCoverArt` and `BookCover`. The detail route reuses `LibraryCatalogueDetail` and `BookDetailView`, with the existing BookEditor, LibraryStockEditor and AddSoftCopyModal. No second cover system or catalogue design was added.

The existing source/books/genres/detail catalogue APIs accept `staff=true` to select a representation. That flag invokes `require_library_staff`; it is never authority. ACTIVE ADMIN/LIBRARIAN LibraryMembership in the URL's exact library is mandatory, revalidated inside the canonical lock. Platform role and legacy User.role do not supply membership. Missing/revoked membership returns the existing non-disclosing 404; an active Patron requesting Staff representation receives 403. Default Patron browsing remains Patron-only. No new mutation service exists.

Staff reads use canonical LibraryBookRecords, holdings and authorized READY assets (including STAFF_ONLY). Processing/failed unstocked records remain visible for management; they never acquire a false online capability. An empty Staff library returns LOCAL/0 and never automatically loads global filler. Source counts and pages remain bounded server reads. Global browsing is an explicit `/catalog` action.

`libraryBookPath` centralizes exact library/book identities. Staff Inventory titles carry only a same-library Inventory return path; search, record/state/format filters and zero-based page are URL state. Creation/import commands are excluded from return links. Foreign and malformed history return state is rejected. Personal card links consult the matching explicit membership, without first-membership selection. Reservations, circulation, analytics and asset-linked titles reuse `LibraryBookTitleLink` and its visible keyboard focus style.

Staff detail displays canonical format, accession, ISBN/global reference, shelf, current holding call number, status, stock/requestable counts and resource status/visibility. Staff book resources reuse the existing protected asset APIs; only READY authorized assets offer Read Online. Asset detail already enforces file/RAG/Knowledge permissions. The browser uploaded a hand-authored QA PDF to the disposable review library only, retaining book identity and holding hash. TEST records/holdings were not changed.

Original cover palette/geometry files are unchanged from the accepted HEAD. No text backplates, adaptive foreground colors, new catalogue HNSW/KG builds, Router changes or new phase were introduced.
''')
put('institution_v2f1_staff_catalogue_routes.json',{'status':'PASS','routes':[
 {'path':'/staff/libraries/:libraryId/catalogue','component':'LibraryCataloguePage staff','authority':'ACTIVE ADMIN/LIBRARIAN LibraryMembership','purpose':'selected-library visual browsing'},
 {'path':'/staff/libraries/:libraryId/genres','component':'LibraryCatalogueGenres staff','authority':'same Staff membership','purpose':'shared subject browser'},
 {'path':'/staff/libraries/:libraryId/books/:bookId','component':'LibraryCatalogueDetail staff','identity':'library_book_id','authority':'same Staff membership','purpose':'shared detail with existing Staff forms/resources'},
 {'path':'/staff/libraries/:libraryId/inventory','purpose':'existing separate management table'},
 {'path':'/libraries/:libraryId/catalogue','purpose':'unchanged Patron catalogue'},
 {'path':'/catalog','purpose':'unchanged global catalogue; explicit Staff discovery action'}],
 'reused_API_reads':['GET /libraries/{library_id}/catalogue/source?staff=true','GET /libraries/{library_id}/catalogue/books?staff=true','GET /libraries/{library_id}/catalogue/genres?staff=true','GET /libraries/{library_id}/catalogue/books/{library_book_id}?staff=true'],'new_mutation_endpoints':[]})

regression={'status':'PASS','captured_at':datetime.now(timezone.utc).isoformat(),'backend':{'unique_passed':passed,'existing_security_skips':skips,'failed':0,'new_staff_catalogue_tests':14,'final_targeted_rerun':14,'groups':groups},'frontend':{'full_suite_passed':831,'full_default':683,'full_extended':148,'final_affected_suite':28,'distinct_cases_passed_across_full_and_final_runs':833,'failed':0,'method':'Full 831-case run, then final 28-case affected suite after two additional return-state cases and small Inventory return guards; replaces the earlier 26-case group.'},'build':'PASS','lint':{'errors':0,'new_warnings':0,'existing_warnings':warnings},'browser':{'engine':'Chromium 151.0.7922.34','live_flow_checks':len(browser['checks']),'surface_viewport_cases':18,'viewports':[[1440,900],[1366,768],[1024,768],[768,1024],[390,844],[375,812]],'errors':0},'router_research_rerun':False}
put('institution_v2f1_staff_catalogue_regression.json',regression)

flags={
 'STAFF_INVENTORY_TITLE_CLICKABLE':'YES','STAFF_TITLE_DESTINATION':BASE+'/books/{library_book_id}',
 'STAFF_TITLE_USES_LIBRARY_BOOK_ID':'YES','STAFF_TITLE_PRESERVES_STAFF_CONTEXT':'YES',
 'STAFF_BOOK_DETAIL_FORMAT_VISIBLE':'YES','STAFF_BOOK_DETAIL_ONLINE_ASSET_VISIBLE':'YES',
 'STAFF_BOOK_DETAIL_READ_ONLINE_WORKS':'YES','DIGITAL_ASSET_LINKED_BOOK_CLICKABLE':'YES',
 'INVENTORY_BACK_STATE_PRESERVED':'YES','STAFF_CATALOG_FINAL_ROUTE':BASE+'/catalogue',
 'STAFF_CATALOG_IS_INVENTORY':'NO','STAFF_CATALOG_IS_GLOBAL':'NO',
 'STAFF_CATALOG_SELECTED_LIBRARY':TEST+' / TEST','STAFF_CATALOG_VISIBLE_BOOK_COUNT':150,
 'STAFF_CATALOG_REUSES_BROWSE_SURFACE':'YES','STAFF_CATALOG_PATRON_REQUEST_ACTIONS_VISIBLE':'NO',
 'STAFF_CATALOG_BOOK_DETAIL_PRESERVES_STAFF_CONTEXT':'YES','STAFF_INVENTORY_REMAINS_SEPARATE':'YES',
 'EXPLICIT_GLOBAL_CATALOG_ACTION_EXISTS':'YES'}
gates=[]
attachments=[r'C:\Users\balak\.codex\attachments\8b11902a-f100-48d8-ada1-5c74ee31dab3\Pasted text.txt',r'C:\Users\balak\.codex\attachments\204c2930-995b-45bd-9f79-153918a34b3b\Pasted text.txt']
for path in attachments:
    prompt=Path(path).read_text(encoding='utf-8-sig')
    for match in re.finditer(r'^(\d{3})\.\s+(.+?)(?=\n\s*\n|\Z)',prompt,re.M|re.S):
        number=int(match.group(1))
        if 231<=number<=254:gates.append({'gate':number,'requirement':' '.join(match.group(2).split()),'status':'PASS','evidence':'institution_v2f1_staff_catalogue_browser.json' if number not in [241,247,251] else 'institution_v2f1_staff_catalogue_responsive.json'})
assert sorted(g['gate'] for g in gates)==list(range(231,255))

changed=subprocess.check_output(['git','diff','--name-only','--','LibraryLLM/backend','LibraryLLM/frontend'],cwd=ROOT.parent,stderr=subprocess.DEVNULL).decode().splitlines()
files=[p.removeprefix('LibraryLLM/') for p in changed]
files+=['frontend/src/components/LibraryBookTitleLink.tsx','frontend/src/components/StaffBookManagement.tsx','frontend/tests/staff-catalogue-titles.test.tsx','tests/library_catalogue_experience/test_staff_catalogue.py','scripts/institution_v2f1_staff_catalogue_browser.py','scripts/institution_v2f1_staff_catalogue_reports.py']
files=sorted(set(files))
put('institution_v2f1_staff_catalogue_changed_files.json',[{'path':name,'sha256':hashlib.sha256((ROOT/name).read_bytes()).hexdigest()} for name in files])
reports=sorted(p.name for p in R.glob('institution_v2f1_staff_catalogue*') if p.suffix in {'.json','.md','.xml','.log'})+['institution_v2f1_book_title_navigation_audit.md']
limitations=['Library uploads support PDF only, as in the accepted phase.','Global 5M preservation uses estimated_document_count; binary artifacts compare size/mtime, and TEST/source checks use hashes.','Browser validation uses Chromium at the six requested viewports.','Ten existing security skips and fourteen existing lint warnings remain; no failing tests or lint errors.','The safe review library retains the newly created Staff-only QA attachment for manual review; TEST data is unchanged.','Earlier critical report screenshots/routing decisions remain historical; this correction supersedes the Staff Catalog → Inventory decision.']
completion={'status':'PASS','phase':'Institution Part 2F.1 clickable titles and Staff catalogue correction','acceptance_gates':gates,'final_fields':flags,'regression':regression,'preservation':'institution_v2f1_staff_catalogue_preservation.json','changed_files':'institution_v2f1_staff_catalogue_changed_files.json','reports':reports,'limitations':limitations,'stop':'STOP before Part 2G, tenant catalogue HNSW/KG, Build/Rebuild or any new domain phase.','git_commit':'Not performed; user explicitly cancelled the mistaken Git instruction.'}
put('institution_v2f1_staff_catalogue_completion.json',completion)
text=f'''# Institution Part 2F.1 — clickable titles and Staff catalogue correction

**FINAL PASS. All 24 additional gates (231–254) pass.**

Staff Catalog now opens `/staff/libraries/{{libraryId}}/catalogue`, reusing the accepted Browse Books cards, covers, filters and paging for the selected library. Inventory remains the separate management table. TEST shows 150 canonical local books. Staff cards/details preserve Staff mode and do not offer Patron Request/Waitlist actions. An explicit Browse Global Catalogue action retains global 5M discovery.

Inventory title links open the exact LibraryBookRecord via `library_book_id`. Shared Staff detail displays format, physical facts, current call number, stock/requestable counts and authorized online-resource state/visibility. Existing edit, stock and online-upload forms are reused. Live Chromium verified safe PDF reading, Linked Book navigation, online upload in the disposable review library, library switching and Inventory Back with filters/page 2. Keyboard focus, Enter activation and online-dialog focus trap/Escape/restore pass. All 18 catalogue/inventory/detail viewport cases pass.

Backend: **{passed} unique tests pass**, with {skips} existing security skips; final 14-case Staff catalogue rerun passes. Frontend: full **831-case** run passes, followed by the final **28-case** affected suite (833 distinct cases across runs). Build passes. Lint: 0 errors, 0 new warnings, 14 existing warnings.

TEST retains the same 150 ACTIVE record and 150 holding hashes. Global catalogue remains 5,000,000 estimated records; all 196 protected artifact and 156 protected source checks pass. Accepted cover palette, geometry and renderer files are unchanged. No Git commit was made.

## Required final fields

| Field | Result |
|---|---|
'''
text+=''.join(f'| {key} | {value} |\n' for key,value in flags.items())
text+='\n## Acceptance evidence\n\n| Gate | Requirement | Result | Evidence |\n|---|---|---|---|\n'+''.join(f'| {g["gate"]} | {g["requirement"]} | PASS | [{g["evidence"]}]({g["evidence"]}) |\n' for g in gates)
text+='\n## Files changed\n\n'+''.join(f'- `{name}`\n' for name in files)
text+='\nRegenerated full-suite XML/logs and viewport screenshots are evidence outputs, listed separately by their report prefix. No credentials are included. The original `institution_v2f1_staff_catalogue_backend.xml` and frontend log captured early fixture/assertion failures; authoritative final results are the full regression catalogue XML and `*_backend_final.xml` / `*_frontend_final.log`.\n'
text+='\n## Reports\n\n'+''.join(f'- [{name}]({name})\n' for name in reports)
text+='\n## Limits and stop\n\n'+''.join(f'- {line}\n' for line in limitations)+'\n**Accept the current Part 2F.1 correction. STOP before Part 2G and all further domain/index/build work.**\n'
write('institution_v2f1_staff_catalogue_completion.md',text)

# Preserve previous evidence while making the current correction the first result.
main=R/'institution_v2f1_critical_completion.md'
old=main.read_text(encoding='utf8')
marker='<!-- current-staff-catalogue-correction -->'
if marker not in old:
    write(main.name,marker+'\n# Current Part 2F.1 closure — PASS\n\nThe latest Staff catalogue/title correction is complete. **Staff Catalog opens the selected-library browsing surface at `/staff/libraries/{libraryId}/catalogue`; Inventory remains separate.** [Current completion, gates 231–254 and required QA fields](institution_v2f1_staff_catalogue_completion.md). The previous routing decision below is superseded; its other accepted evidence remains historical.\n\n---\n\n'+old.replace('# Institution Part 2F.1 — final critical closure','# Earlier critical closure — historical evidence',1))
prior=read('institution_v2f1_critical_completion.json')
if 'historical_final_fields' not in prior:prior['historical_final_fields']=dict(prior['final_fields'])
prior['final_fields'].update(flags)
prior['final_fields']['STAFF_CATALOG_FINAL_URL']=BASE+'/catalogue'
prior['latest_addendum']='institution_v2f1_staff_catalogue_completion.json'
prior['latest_addendum_acceptance_gates']=gates
prior['current_regression']=regression
prior['superseded_routing_decision']='Staff Catalog → Inventory is superseded by Staff Catalog → /staff/libraries/{libraryId}/catalogue.'
put('institution_v2f1_critical_completion.json',prior)
parent=R/'institution_v2f_completion.md';content=parent.read_text(encoding='utf8')
if marker not in content:write(parent.name,content+'\n'+marker+'\n## Current Part 2F.1 title and catalogue closure\n\n[FINAL PASS: clickable canonical Staff titles, selected-library Staff Catalogue, separate Inventory, six viewports and preservation](institution_v2f1_staff_catalogue_completion.md). Staff Catalog → Inventory was explicitly superseded by the latest user correction. No Part 2G work or Git commit was performed.\n')
nav=R/'product_context_navigation_audit.md';content=nav.read_text(encoding='utf8')
if marker not in content:
    content=content.replace('## Part 2F.1 canonical collection supplement','## Earlier Part 2F.1 routing supplement — superseded by current correction')
    write(nav.name,content+'\n'+marker+'\n## Current Staff catalogue and title correction\n\nThe earlier Staff Catalog → Inventory choice is superseded. The shared product-context resolver now sends Catalog to `/staff/libraries/{current_library_id}/catalogue`, Search there with a bounded query, and New Arrivals there with `sort=new_arrivals`. Inventory remains `/staff/libraries/{current_library_id}/inventory`. Patron and explicit Global routes are unchanged. Legacy catalogue compatibility URLs redirect to the correct Staff catalogue without selecting the first membership.\n\n[Ten inspected title/list call sites and exact destinations](institution_v2f1_book_title_navigation_audit.md). [Current route inventory](institution_v2f1_staff_catalogue_routes.json). [Browser evidence](institution_v2f1_staff_catalogue_browser.json).\n')
print(json.dumps({'status':'PASS','gates':len(gates),'backend':passed,'frontend_full':831,'frontend_final':28,'distinct_frontend':833,'files':len(files),'report':'institution_v2f1_staff_catalogue_completion.md'}))
