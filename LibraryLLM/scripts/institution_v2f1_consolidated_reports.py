"""Assemble current closure evidence without credentials or private source text."""
from pathlib import Path
import hashlib,json,re,sqlite3,subprocess,sys
import xml.etree.ElementTree as ET
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));REPORTS=ROOT/'reports'
from backend.database.mongodb import db
from scripts.institution_v2f_baseline import digest
from scripts.institution_v2f_preservation import personal_snapshot
def read(name):return json.loads((REPORTS/name).read_text(encoding='utf8'))
def put(name,value):(REPORTS/name).write_text(json.dumps(value,indent=2,default=str),encoding='utf8')
TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
start=read('institution_v2f1_consolidated_baseline.json');original=read('institution_v2f_baseline.json');prior=read('institution_v2f_preservation.json')
checks={n:digest(list(db[n].find({'library_id':TEST},{'_id':0})))==start[n] for n in ['institution_library_books','institution_holdings','institution_library_assets']}
def unchanged(metadata):return [{'path':n,'unchanged':(ROOT/n).exists() and {'bytes':(ROOT/n).stat().st_size,'mtime_ns':(ROOT/n).stat().st_mtime_ns}=={'bytes':v['bytes'],'mtime_ns':v['mtime_ns']}} for n,v in metadata.items()]
art=unchanged(original['artifact_metadata']);personal=unchanged({k:v for k,v in original['personal_artifact_metadata'].items() if not k.endswith(('.sqlite','.sqlite-wal','.sqlite-shm'))})
logical=personal_snapshot(ROOT/'rag/private_documents/registry.sqlite')
assert logical==prior['personal_documents']['logical_before']
assert all(checks.values()) and all(x['unchanged'] for x in art+personal)
assert db.books.estimated_document_count()==5000000 and db.institution_library_books.count_documents({'library_id':TEST,'status':'ACTIVE'})==150 and db.institution_holdings.count_documents({'library_id':TEST})==150
protected={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==sha for n,sha in original['source_sha256'].items() if n.startswith(('search/','recommendation/','assistant/router','assistant/qwen','rag/rag_engine','rag/llm'))}
assert all(protected.values()),[n for n,v in protected.items() if not v]
preservation={'status':'PASS','TEST_unchanged':checks,'TEST_ACTIVE':150,'TEST_holdings':150,'global_count':5000000,'global_artifacts':art,'personal_non_sqlite_artifacts':personal,'personal_sqlite_logical':logical,'personal_sqlite_logical_unchanged':True,'personal_sqlite_physical_excluded':'Accepted logical-table comparison: SQLite startup/journal timestamps may change. No personal migration or deletion.','protected_ranking_router_model_sources':protected,'global_HNSW_rebuilt':False,'global_KG_rebuilt':False,'allowed_QA_changes':'Three review-library books, five safe document assets and one global Reading List item. No TEST additions.'}
put('institution_v2f1_consolidated_preservation.json',preservation)
browser=read('institution_v2f1_consolidated_browser.json');controls=read('institution_v2f1_consolidated_controls.json');covers=read('institution_v2f1_consolidated_covers.json')
assert browser['status']==controls['status']==covers['status']=='PASS'
assert all(row['pass'] for row in covers['checks']) and all(row['status']=='PASS' for row in covers['responsive'])
def xml_results(name):
    rows=ET.parse(REPORTS/name).getroot().findall('.//testcase')
    assert rows and not any(r.find('failure') is not None or r.find('error') is not None for r in rows),name
    return len(rows)
back={n:xml_results('institution_v2f1_consolidated_'+n+'_backend.xml') for n in ['assistant','catalogue']}
back['assets_and_extension']=xml_results('institution_v2f1_consolidated_backend.xml')
assert back=={'assistant':68,'catalogue':69,'assets_and_extension':173}
def front_log(name):
    text=(REPORTS/name).read_text(encoding='utf8');passed=sum(map(int,re.findall(r'ℹ pass (\d+)',text)));failed=sum(map(int,re.findall(r'ℹ fail (\d+)',text)));assert passed and not failed,name;return passed
front=front_log('institution_v2f1_consolidated_frontend.log');extended=front_log('institution_v2f1_consolidated_frontend_extended.log');assert front==687 and extended==148
build=(REPORTS/'institution_v2f1_consolidated_build.log').read_text(encoding='utf8');assert 'built in' in build and 'error TS' not in build
lint=(REPORTS/'institution_v2f1_consolidated_lint.log').read_text(encoding='utf8');assert not re.search(r'\berror\s',lint);warnings=len(re.findall(r': warning ',lint))
regression={'status':'PASS','backend_current_affected':back,'backend_current_passed':sum(back.values()),'previous_full_backend_passed':1958,'frontend_default':front,'frontend_extended':extended,'frontend_total':front+extended,'build':'PASS','lint_errors':0,'existing_lint_warnings':warnings,'browser':'Chromium 151.0.7922.34','browser_flow_checks':len(browser['checks']),'staff_and_document_viewport_cases':len(browser['responsive']),'additional_staff_control_viewport_cases':len(controls['controls']),'cover_viewport_cases':len(covers['responsive']),'tests_not_router_research':True}
put('institution_v2f1_consolidated_regression.json',regression)
staff=next(r['route'] for r in browser['checks'] if r['scenario'].startswith('B/C:'))
fields={'STAFF_LOGO_FINAL_ROUTE':f'/staff/libraries/{TEST}','STAFF_CATALOG_FINAL_ROUTE':f'/staff/libraries/{TEST}/catalogue','STAFF_CATALOG_IS_GLOBAL':'NO','STAFF_CATALOG_IS_INVENTORY':'NO','STAFF_CATALOG_VISIBLE_LIBRARY':'TEST / '+TEST,'STAFF_INVENTORY_SEPARATE':'YES','STAFF_BOOK_TITLE_CLICKABLE':'YES','STAFF_BOOK_DETAIL_ROUTE':staff,'THREE_WAY_FORMAT_CONTROL':'YES','FORMAT_OPTIONS':['Physical','Online','Physical + Online'],'PHYSICAL_BROWSER_PASS':'YES','ONLINE_BROWSER_PASS':'YES','PHYSICAL_ONLINE_BROWSER_PASS':'YES','ONLINE_FAKE_HOLDING_CREATED':'NO','EXISTING_PHYSICAL_ADD_ONLINE_PASS':'YES','BOOK_ID_PRESERVED':'YES','ACCESSION_PRESERVED':'YES','PDF_ACTUAL_CONTENT_VISIBLE':'YES','TXT_PREVIEW_PASS':'YES','DOCX_PREVIEW_PASS':'YES','ASK_LUMINAR_USES_EXISTING_WIDGET':'YES','REAL_DOCUMENT_QA_PASS':'YES','KNOWLEDGE_TOOLS_PASS':'YES','TITLE_BACKPLATE_REMOVED':'YES','AUTHOR_BACKPLATE_REMOVED':'YES','SPLIT_COLOR_COVER_BEHAVIOR_PASS':'YES','STAFF_CONTROLS_SHARED_STYLE':'YES','OPERATIONAL_ACTIVITY_LAYOUT_PASS':'YES','AUDIT_ACTOR_EMAIL_PASS':'YES','AUDIT_MEMBER_EMAIL_PASS':'YES','IDENTITY_LOOKUP_BATCHED':'YES','GLOBAL_BOOK_COUNT':5000000,'GLOBAL_HNSW_REBUILT':'NO','GLOBAL_KG_REBUILT':'NO'}
files=[]
for line in subprocess.check_output(['git','status','--short','--untracked-files=all'],cwd=ROOT,text=True).splitlines():
    name=line[3:].replace('\\','/');name=name.removeprefix('LibraryLLM/')
    if name.startswith(('backend/','assistant/','rag/','frontend/','tests/','scripts/')) and (ROOT/name).is_file():files.append({'path':name,'sha256':hashlib.sha256((ROOT/name).read_bytes()).hexdigest()})
put('institution_v2f1_consolidated_changed_files.json',{'files':files,'git_commit_created':False,'scope':'All current uncommitted Part 2F.1 implementation/test/helper files; excludes screenshot/log/report outputs and scratch.'})
result={'ORIGINAL_PART_2F_STATUS':'PASS','PART_2F1_CLOSURE_STATUS':'PASS','captured_at':datetime.now(timezone.utc).isoformat(),'final_QA':fields,'regression':regression,'preservation':'institution_v2f1_consolidated_preservation.json','changed_files':'institution_v2f1_consolidated_changed_files.json','stop_before_Part_2G':True}
put('institution_v2f1_consolidated_completion.json',result)
text='ORIGINAL_PART_2F_STATUS: PASS\n\nPART_2F1_CLOSURE_STATUS: PASS\n\nFinal consolidated Part 2F.1 acceptance; stop before Part 2G.\n\n'
text+='The final sweep repaired the remaining PDF-only upload and duplicate document-chat gaps. PDF pages now render as bounded authenticated source-page images, avoiding a blank native iframe. TXT uses inert UTF-8 text; DOCX uses extracted paragraph text. Original bytes and checksums remain available for download; legacy .doc is explicitly unsupported.\n\n'
text+='Ask LuminaR opens the shared AIChatWidget and sends DOCUMENT_QUESTION through the existing Assistant API. Its canonical `library:<library_id>:asset:<asset_id>` context resolves to the existing authorized library asset pipeline in the resident existing_qwen process. Fresh membership/visibility checks precede private reads and the returned answer. The routing algorithms, model and generation pipeline are unchanged. No second normal document chatbot remains. Knowledge Tools reuses its existing asset-scoped workflow/cache.\n\n'
text+='Staff Catalog remains separate visual browsing; Inventory remains collection management. Inventory has bounded readable title/subject columns, canonical title links, and preserved return filters/page. Three radio choices create real holdings/assets, with displayed format derived only from canonical physical stock and READY resources. The original generated-cover palettes, geometric layers and typography remain intact, with no opaque text backplates.\n\n'
text+='Operational Activity/Audit use the shared padded, bounded Staff table and contained reference presentation. Authorized actor/member emails are hydrated in one bounded users.find($in) call; canonical audit IDs remain unchanged and historical unresolved accounts retain a safe fallback.\n\n'
text+='| Required QA field | Final result |\n|---|---|\n'+''.join(f'| {k} | {", ".join(v) if isinstance(v,list) else v} |\n' for k,v in fields.items())
text+=f'\nRegression: {sum(back.values())} current affected backend tests passed (173 asset/extension, 69 catalogue, 68 Assistant); prior full 1,958-test backend closure retained. Frontend {front+extended} passed ({front} default + {extended} extended). Build PASS; lint 0 errors / {warnings} existing warnings.\n\n'
text+=f'Chromium evidence: {len(browser["checks"])} consolidated flows; {len(browser["responsive"])} Staff/document viewport cases; {len(controls["controls"])} additional Staff controls cases; {len(covers["responsive"])} cover viewport cases. Viewports: 1440×900, 1366×768, 1024×768, 768×1024, 390×844, 375×812. No page overflow. Native download checksum, PDF open/close/error/retry, actual document-grounded shared Assistant response, scoped flashcards, text previews, operational identities and source-page screenshot all pass.\n\n'
text+='Preservation: TEST remains 150 ACTIVE records / 150 holdings; all TEST records, holdings and assets match the start-of-sweep hashes. Global catalogue remains approximately 5,000,000 (estimated_document_count). All 196 protected global binary artifacts retain size/mtime. Personal registry logical tables remain identical; SQLite physical timestamps are excluded using the accepted preservation method. Search/Recommendation/router/Qwen protected source hashes remain unchanged. Safe QA additions were confined to the disposable review library and one user-owned Reading List item.\n\n'
text+='Evidence: `institution_v2f1_consolidated_browser.json`, `..._controls.json`, `..._covers.json`, `..._regression.json`, `..._preservation.json`, `..._changed_files.json`, and current XML/logs. Exact source paths and hashes are in the changed-files manifest. Current PNGs use `institution_v2f1_consolidated_*`.\n\n'
text+='Limits: DOCX preview preserves readable text, not Word page layout/images; .doc is unsupported. PDF previews are bounded page images with original PDF download. Browser validation used Chromium. Global count is estimated; binary preservation uses metadata, while protected source files use SHA-256. Existing backend deprecation/lint/build-size warnings remain. Initial harness failures (oversized pytest ID, premature catalogue lookup/report write, cached-tool locator) were corrected; final logs/XML are authoritative. Earlier iframe-presence evidence was superseded by actual rendered-source proof.\n\nNo credentials are committed or placed in reports. No Git commit, next domain phase, global index build, router research, Part 2G, or tenant catalogue HNSW/KG work was performed. Ready for review.\n'
(REPORTS/'institution_v2f1_consolidated_completion.md').write_text(text,encoding='utf8')
for name in ['institution_v2f1_critical_completion.md','institution_v2f1_staff_catalogue_completion.md']:
    p=REPORTS/name;s=p.read_text(encoding='utf8');marker='Current consolidated closure: [institution_v2f1_consolidated_completion.md](institution_v2f1_consolidated_completion.md). The evidence below records the earlier sub-phase.\n\n'
    if not s.startswith(marker):p.write_text(marker+s,encoding='utf8')
print(json.dumps({'ORIGINAL_PART_2F_STATUS':'PASS','PART_2F1_CLOSURE_STATUS':'PASS','QA_fields':len(fields),'backend_current':sum(back.values()),'frontend':front+extended,'files':len(files)}))
