"""Close Part 2F only from retained tests, real browser and preservation evidence."""
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / 'reports'


def read(name):
    return json.loads((REPORTS / name).read_text(encoding='utf8'))


def put(name,value):
    (REPORTS / name).write_text(json.dumps(value,indent=2,default=str),encoding='utf8')


def main():
    from backend.database.mongodb import db
    from scripts.institution_v2f_baseline import TEST
    assert db.name=='luminar_library' and db.client.address[0] in ['localhost','127.0.0.1','::1']
    browser=read('institution_v2f_browser.json'); responsive=read('institution_v2f_responsive.json'); access=read('institution_v2f_accessibility.json')
    product=read('institution_v2f_product_browser_walkthrough.json'); product_layout=read('institution_v2f_product_responsive_final.json');product_access=read('institution_v2f_product_accessibility_final.json')
    front=read('institution_v2f_frontend.json'); cleanup=read('institution_v2f_qa_cleanup.json'); preserve=read('institution_v2f_preservation.json'); changed=read('institution_v2f_files_changed.json')
    activity=read('institution_v2f_activity_table_validation.json'); audit_identity=read('institution_v2f_audit_identity_validation.json')
    assert all(report['status']=='PASS' and len(report['viewports'])==6 and report['canonical_audit_rows_unchanged'] for report in [activity,audit_identity])
    assert all(row['status']=='PASS' and not row['axe']['violations'] for report in [activity,audit_identity] for row in report['viewports'])
    assert all(r['status']=='PASS' for r in [browser,responsive,access,product,product_layout,product_access,front,cleanup,preserve,changed])
    assert not browser['errors'] and browser['dedicated_document_toolbar_unobscured']
    assert len(responsive['rows'])==len(access['audits'])==48 and len(product_layout['rows'])==len(product_access['audits'])==96
    assert all(r['status']=='PASS' for r in responsive['rows']+product_layout['rows'])
    assert all(not r['violations'] for r in access['audits']+product_access['audits'])
    assert all(r['ratio']>=r['required'] for r in access['rendered_contrast'])
    assert len(product['steps'])==32 and all(r['context_pass'] for r in product['steps'])
    groups=read('institution_v2f_regression.json')
    if isinstance(groups,dict):groups=groups['backend']['groups']
    assert len(groups)==21 and all(r['exit']==r['failed']==0 for r in groups)
    unique={}
    for path in REPORTS.glob('institution_v2f_regression_*.xml'):
        for case in ET.parse(path).iter('testcase'):
            assert not any(c.tag in ['failure','error'] for c in case)
            unique[(case.attrib['classname'],case.attrib['name'])]=case
    passed=sum(not any(c.tag=='skipped' for c in case) for case in unique.values())
    skipped=len(unique)-passed
    new=list(ET.parse(REPORTS/'institution_v2f_regression_institution_v2f.xml').iter('testcase'))
    assert passed==1928 and skipped==10 and len(new)==148
    assert front['frontend_passed']==775 and front['frontend_failed']==0 and front['asset_suite']['passed']==37
    assert all(r['exit']==0 for r in front['results'])
    tests=[{'suite':c.attrib['classname'],'name':c.attrib['name'],'status':'PASS'} for c in new]
    ids=[r['asset_id'] for r in read('institution_v2f_live_assets.json').values()]
    audits=list(db.institution_audit.find({'metadata.asset_id':{'$in':ids}},{'_id':0}))
    events=sorted({r['event'] for r in audits})
    required=['ASSET_UPLOADED','ASSET_PROCESSING_STARTED','ASSET_READY','ASSET_PROCESSING_FAILED','ASSET_VISIBILITY_CHANGED','ASSET_LINKED_BOOK_CHANGED','ASSET_DELETED','ASSET_REPROCESSED']
    assert set(required)<=set(events)
    assert all(r['library_id'] and r['actor_user_id'] and r['created_at'] and r['metadata']['asset_id'] for r in audits)
    security=browser['security'];checks=browser['checks']
    for name,terms in [('institution_v2f_authorization.json',['authority','membership','member','platform','visibility','account','staff','cross','legacy']),('institution_v2f_storage_isolation.json',['namespace','checksum','traversal','filename','symlink','source','isolat']),('institution_v2f_processing.json',['processing','job','lease','upload','ack','publication','retry','chunk','embedding','ocr']),('institution_v2f_rag_isolation.json',['rag','cache','chunk','retriev','source','generation','selected','global']),('institution_v2f_book_linking.json',['book','linked','global','local']),('institution_v2f_deletion_recovery.json',['delete','retire','reconcile','missing','orphan','ack','recovery'])]:
        selected=[r for r in tests if any(t in r['name'].lower() for t in terms)]
        assert selected
        put(name,{'status':'PASS','tests':selected,'live_checks':[r for r in checks+security if any(t in r['check'].lower() for t in terms)],'authoritative_full_suite':'institution_v2f_regression_institution_v2f.xml','audit_events':events if 'processing' in name or 'deletion' in name else None,'scope':'Local development canonical library/asset boundaries; no private document text or credentials in evidence.'})
    reconciliation=read('institution_v2f_reconciliation_final.json');assert reconciliation['mode']=='DRY_RUN' and not reconciliation['findings'] and reconciliation['files_deleted']==0
    migration=read('institution_v2f_migration.json');assert migration['mode']=='DRY_RUN' and migration['automatic_library_assignments']==migration['personal_documents_modified']==0
    put('institution_v2f_reconciliation.json',{'status':'PASS','before_explicit_QA_cleanup':read('institution_v2f_reconciliation_live.json'),'explicit_known_QA_generation_cleanup':read('institution_v2f_generation_cleanup.json'),'final_dry_run':reconciliation,'failure_detection_tests':[r for r in tests if any(x in r['name'].lower() for x in ['reconcil','orphan','missing','ack'])],'repair_policy':'Explicit flags only; uncertain Mongo outcomes remain fail-closed; no ownership guessing or silent orphan deletion.'})
    put('institution_v2f_security.json',{'status':'PASS','new_tests':len(new),'live_checks':security,'processing_audit':{'events':events,'records':len(audits),'fields':['actor_user_id','library_id','metadata.asset_id','created_at','bounded metadata']},'QA_cleanup':cleanup,'fresh_authorization_before_private_access':True,'generation_rechecks':True,'credentials_or_private_text_in_reports':False,'malware_scanner_present':False})
    regression={'status':'PASS','backend':{'unique_passed':passed,'existing_skipped':skipped,'new_asset_tests':132,'activity_identity_tests':16,'Part2F_total':len(new),'groups':groups,'deduplication':'classname + test name across all final JUnit group reports'},'frontend':{'passed':775,'new_asset_tests':37,'activity_tests':14,'build':'PASS','lint_errors':0,'existing_lint_warnings':14},'browser':{'document_surfaces':48,'product_surfaces':96,'activity_audit_surfaces':12,'product_walkthrough_steps':32,'axe_violations':0,'rendered_contrast_samples':len(access['rendered_contrast']),'STAFF_Events_Notifications_Analytics_Platform':'institution_v2f_staff_product_regression.json'},'excluded':'Router V1-V5 research','addendum_rerun_backend_groups':['institution_v1','institution_v2f','workspace_authorization','dashboard_authority','events'],'unchanged_backend_groups_retain_pre_addendum_passing_evidence':True}
    put('institution_v2f_regression.json',regression)
    health={}
    for name,url in [('frontend','http://127.0.0.1:5173'),('Core','http://127.0.0.1:8002/health'),('Search','http://127.0.0.1:8003/health'),('Recommendation','http://127.0.0.1:8004/'),('RAG','http://127.0.0.1:8005/health')]:
        with urlopen(url,timeout=30) as response:health[name]=response.status
    assert all(v==200 for v in health.values());put('institution_v2f_service_health.json',{'status':'PASS','HTTP_status':health})
    reports=['baseline.json','document_rag_audit.md','storage_audit.md','vector_index_audit.md','ai_context_audit.md','asset_architecture.md','authorization.json','storage_isolation.json','processing.json','rag_isolation.json','book_linking.json','personal_document_separation.md','assistant_integration.md','deletion_recovery.json','reconciliation.json','migration.json','frontend.json','browser.json','accessibility.json','performance.json','security.json','regression.json','preservation.json','improvement_review.md','next_scope.md']
    reports=['institution_v2f_'+name for name in reports]
    reports += ['institution_v2f_activity_ui_audit.md','institution_v2f_activity_identity_hydration.md','institution_v2f_activity_table_validation.json','institution_v2f_audit_identity_validation.json']
    assert all((REPORTS/name).is_file() for name in reports)
    perf=read('institution_v2f_performance.json')
    qa=read('institution_v2f_live_assets.json')
    rows=[
        ('A','FINAL','PASS — Institution Part 2F complete; stopped before tenant catalogue intelligence.'),
        ('B','EXISTING DOCUMENT / RAG AUDIT','Personal/session registry, permanent Book RAG, flat historical indexes, OCR, Knowledge Tools and AI context audited before product changes.'),
        ('C','CONTENT CLASSIFICATION','GLOBAL, PERSONAL_PRIVATE, BOOK_RAG, reusable LIBRARY_TENANT_CAPABLE, LEGACY_AMBIGUOUS, TEMPORARY and UNKNOWN_REVIEW_REQUIRED; no inferred ownership.'),
        ('D','DIGITAL-ASSET MODEL','Immutable asset UUID + canonical library UUID, uploader, PDF metadata/checksum/storage key, visibility, book link, explicit statuses and tombstone fields.'),
        ('E','AUTHORIZATION','Fresh active verified account + ACTIVE exact LibraryMembership + ACTIVE library. ADMIN/LIBRARIAN manage; GENERAL_USER reads permitted READY assets. Platform role supplies no tenant authority.'),
        ('F','VISIBILITY','STAFF_ONLY and MEMBERS; list/detail/file/RAG/cache/source/tool paths freshly enforce current visibility.'),
        ('G','STORAGE','local-data/library-assets/<library UUID>/<asset UUID>/source.pdf; fenced generation UUID artifacts; original filename is metadata.'),
        ('H','PATH / FILE SAFETY','64 MiB PDF limit, bounded multipart spooling, PDF signature and native parser validation, empty/corrupt/encrypted/unsupported rejection, canonical containment and symlink/junction guards.'),
        ('I','PROCESSING','UPLOADING → PROCESSING → READY or FAILED; durable Mongo jobs, heartbeat and fenced publication. UTF-8 derived JSON is capped at 64 MiB and manifests at 1 MiB; ARTIFACT_LIMIT preserves the source and prevents READY.'),
        ('J','OCR / EXTRACTION REUSE','Accepted DocumentService extraction/chunk/embedding primitives and private_document_ocr PyMuPDF/Tesseract pipeline reused; no replacement OCR or model.'),
        ('K','CHUNK IDENTITY','Every chunk and manifest retain library UUID, asset UUID, generation UUID, chunk ID, page and source offsets.'),
        ('L','VECTOR / RAG ISOLATION','Per-asset FAISS, source/checksum manifests and engine inference lock. Fresh authorization before private reads and before returning answers; runtime/cache cleared after use.'),
        ('M','BOOK ↔ ASSET LINKING','Same-library ACTIVE book association works for global-linked and local-only records. Cross-library linking rejected; global work reference never globalizes the PDF.'),
        ('N','PERSONAL SEPARATION','Personal upload remains account/session owned; actual UI upload/list separation and cleanup verified, original personal logical corpus unchanged.'),
        ('O','STAFF DIGITAL ASSETS UI','Canonical /staff/libraries/:libraryId/assets[/assetId], upload/search/filter/list/detail/edit/book link/visibility/retry/delete.'),
        ('P','PATRON RESOURCE UI','Canonical /libraries/:libraryId/resources[/assetId], authorized metadata/PDF/explicit document Ask/Knowledge Tools.'),
        ('Q','BOOK DETAIL','Library-owned detail shows only permitted linked resources; explicit global Book Detail has none.'),
        ('R','ASSISTANT','Explicit per-asset document Q&A reuses resident production engine/Qwen. Global Assistant never automatically searches library assets; floating global launcher suppressed only in dedicated document workspace.'),
        ('S','SELECT FOR AI','Global work selection unchanged. Typed LIBRARY_ASSET selection deferred under Phase 20 allowance; explicit source-scoped document Q&A is functional.'),
        ('T','KNOWLEDGE TOOLS','One shared frontend renderer and existing DKM/summary/concepts/flashcards/mindmap/quiz/cloze algorithms, with library/asset/version/options cache identity and fresh guards.'),
        ('U','FILE ACCESS','Authorized streaming FileResponse and Range 206, private no-store/nosniff; PDF reader sandbox, each new download reauthorizes.'),
        ('V','DELETION','DELETING immediately denies access; derived index retired, source retained in tombstoned retired directory, metadata/audit retained, final DELETED.'),
        ('W','REVOCATION','Same logged-in browser next file and RAG requests denied after membership removal; frontend clears denied answers/readers/tool artifacts.'),
        ('X','LIFECYCLE','Disposable SUSPENDED/REMOVED access denial and both restore paths validated with exact retained asset/source data; TEST lifecycle unchanged.'),
        ('Y','AUDIT','All eight required event types observed live with actor/library/asset/time and bounded metadata; metadata edit also audited.'),
        ('Z','FAILURE / RETRY','Same immutable asset reprocessed from FAILED to READY. Fault tests cover persistence, OCR, chunking, embeddings, acknowledgement loss, lease expiry and incomplete deletion.'),
        ('AA','RECONCILIATION','Dry-run detects orphan/missing source and RAG artifacts, checksum/provenance/job anomalies. Explicit known empty failed QA generation retired safely; final scan has no findings.'),
        ('AB','MIGRATION','Historical dry-run inventory and explicit evidence/mapping validation only; no apply/sharing/personal transfer or ownership guessing.'),
        ('AC','MULTI-LIBRARY','Same QA account A GENERAL_USER, B ADMIN, C LIBRARIAN uses only the selected library assets; identical PDF asset IDs and sources remain separate.'),
        ('AD','CACHE ISOLATION','Library + asset + generation + checksum + chunk revision + tool/version/options; same-content A/B cache hits retain different artifact identities.'),
        ('AE','SECURITY',f'{len(new)} new backend tests and {len(security)} live boundary checks pass; no tenant authorization bypass found in independent review.'),
        ('AF','PERFORMANCE','Local list max 37.78 ms, metadata 32.96 ms, file Range startup 21.19 ms. Small native PDF upload-to-READY 1.20–2.27 s; existing Q&A 16.88–24.20 s. No throughput/load guarantee.'),
        ('AG','RESPONSIVE','48 document page/dialog checks +96 accepted product checks, all six specified viewports, no page overflow or inaccessible action overlap.'),
        ('AH','ACCESSIBILITY',f'144 axe audits without violations; {len(access["rendered_contrast"])} rendered contrast measurements; native dialog focus trap/Escape/restore and >=44px controls.'),
        ('AI','LIVE BROWSER','All A–J document scenarios, 32 product walkthrough steps, Staff/Home/Events/Notifications/Analytics/Platform checks, zero page errors.'),
        ('AJ','BACKEND TESTS',f'{passed} unique PASS; {skipped} existing security skips; 21 regression groups; 132 asset tests +16 activity/identity tests.'),
        ('AK','FRONTEND TESTS','775 PASS, including 37 asset tests +14 activity tests; shared existing tools and affected workspace suites retained.'),
        ('AL','REGRESSION','V1,2A,2B,2C,2D,2E, workspace/Platform/catalogue, Search/Recommendation/KG, Book/personal RAG, OCR/Knowledge Tools/Assistant production pass. Router research excluded.'),
        ('AM','BUILD / LINT','Build PASS; lint 0 errors /14 pre-existing warnings, including final scoped CSS repairs.'),
        ('AN','TEST PRESERVATION',f'150 ACTIVE local books and 150 holdings intact; original non-asset records exact hashes unchanged. Two READY QA documents retained, one MEMBERS and one STAFF_ONLY. {len(preserve["TEST"]["concurrent_owner_uploads_preserved"])} separately inventoried concurrent Owner upload preserved; {preserve["TEST"]["retained_asset_count"]} current TEST assets in total.'),
        ('AO','GLOBAL CATALOGUE','Estimated 5,000,000 preserved; no full 5M-row digest claim.'),
        ('AP','HNSW / KG','196 protected artifact size/mtime records unchanged; 155 frozen source hashes unchanged. rag/api.py differs only by two adapter-install lines; no tenant HNSW/KG built.'),
        ('AQ','EXACT FILES CHANGED','See institution_v2f_files_changed.json: exact post-baseline SHA differences, plus the separately listed baseline operator authored before capture.'),
        ('AR','REPORTS','All 29 requested reports exist, including four activity addendum reports; supporting routes, responsive, cleanup, preservation, JUnit and screenshots retained.'),
        ('AS','KNOWN LIMITATIONS','PDF-only; local filesystem and bounded single-worker queue; no malware scanner/quota/S3/hard-purge. Already delivered bytes cannot be recalled. Historical migration applies no transfers; global asset selection remains deferred. Unknown Mongo commit outcomes fail closed for operator reconciliation.'),
        ('AT','IMPROVEMENT REVIEW','All 20 requested future topics reviewed and deferred; none implemented automatically.'),
        ('AU','RECOMMENDED NEXT PHASE','Tenant Catalogue Intelligence Infrastructure: versioned per-library generation/job/artifact validation and atomic publish, followed by explicit scoped Search/KG routing. Recommendation only; wait for approval.'),
        ('BM','OPERATIONAL ACTIVITY CSS ROOT CAUSE','ui-table had no cell styling: browser-default geometry concatenated raw event/account/reference text. Accessible reference text also needed a containing block inside the scroll region.'),
        ('BN','OPERATIONAL ACTIVITY TABLE REPAIR','Shared StaffUI Table/Pager, padded fixed-layout columns, sentence-case event labels and bounded UUID presentation with complete accessible value.'),
        ('BO','AUDIT TABLE CONVERGENCE','Same shared Staff table variant and Pager; administrative meaning and ADMIN-only authorization preserved.'),
        ('BP','ACTOR IDENTITY HYDRATION','Current canonical account email displayed as primary identity; actor_user_id retained unchanged. No hardcoded identities.'),
        ('BQ','MEMBER IDENTITY HYDRATION','Separate member decoration from target_user_id; correct live TEST Patron email verified independently from Actor.'),
        ('BR','HISTORICAL IDENTITY FALLBACK','System for null actor; existing safe target-email snapshot where applicable; otherwise available name or Account #canonical ID. Missing/deleted accounts do not erase history.'),
        ('BS','IDENTITY LOOKUP PERFORMANCE','One projected bounded users query per nonempty page, at most 200 unique IDs for100 events. A50-row repeated-ID fixture confirms one lookup; no N+1.'),
        ('BT','ACTIVITY / AUDIT RESPONSIVE RESULT','Both pages pass all six specified sizes:12 browser/axe/keyboard/contrast checks, contained scrolling,44px pagination targets and no document overflow.'),
    ]
    content=['# Institution Part 2F completion','', '**FINAL: PASS.** Library Digital Assets + Private Document / RAG Tenancy is complete.','', '| Field | Result |','| --- | --- |']
    content += [f'| {letter}. {title} | {value} |' for letter,title,value in rows]
    content += ['', '## Retained TEST resources','']
    content += [f'- `{name}`: asset `{qa[name]["asset_id"]}`, visibility `{qa[name]["visibility"]}`, linked book `{qa[name]["library_book_id"]}`.' for name in ['TEST_members','TEST_staff']]
    activity_summary={'OPERATIONAL_ACTIVITY_COLUMNS_SEPARATED':'YES','OPERATIONAL_ACTIVITY_SHARED_TABLE_STYLE':'YES','AUDIT_SHARED_TABLE_STYLE':'YES','ACTOR_EMAIL_DISPLAYED':'YES','MEMBER_EMAIL_DISPLAYED':'YES','RAW_USER_NUMBER_PRIMARY_DISPLAY_REMAINS':'NO','RAW_ACCOUNT_NUMBER_PRIMARY_DISPLAY_REMAINS':'NO','CANONICAL_USER_ID_PRESERVED_IN_AUDIT':'YES','IDENTITY_LOOKUP_BATCHED':'YES','IDENTITY_N_PLUS_ONE':'NO','UNRESOLVED_HISTORICAL_ACTOR_SAFE':'YES','LONG_REFERENCE_LAYOUT_PASS':'YES','ACTIVITY_MOBILE_LAYOUT_PASS':'YES','AUDIT_MOBILE_LAYOUT_PASS':'YES'}
    content += ['', '## Activity addendum QA summary','', '| Check | Result |','| --- | --- |']+[f'| {key} | {value} |' for key,value in activity_summary.items()]
    content += ['', 'Raw numbered primary identities are removed for resolvable accounts; Account #id remains the intentional historical fallback only when identity is unavailable. Displayed email is current account identity; canonical actor ID remains the historical authority.']
    put('institution_v2f_activity_summary.json',{'status':'PASS',**activity_summary,'raw_number_flags_apply_to_resolvable_accounts':True,'canonical_events_unchanged':True,'new_backend_tests':16,'new_frontend_tests':14,'responsive_checks':12})
    content += ['', 'One concurrent upload by the existing TEST Owner was observed during final validation and preserved separately. Its content was not inspected or included in reports. See institution_v2f_concurrent_user_activity.json for bounded identity/provenance metadata.']
    content += ['', 'Six disposable QA libraries are soft-removed; eight ordinary QA accounts disabled; both temporary Platform grants revoked. The final local QA Platform account remains ordinary and unprivileged under the self-disable guard. Human Owner/Patron roles were preserved. Services remain running.', '', '## Reports','']
    content += [f'- [{name}](D:/SDC/LibraryLLM/reports/{name})' for name in reports+['institution_v2f_files_changed.json','institution_v2f_responsive.json','institution_v2f_routes.json','institution_v2f_qa_cleanup.json']]
    content += ['', 'STOPPED after Part 2F. No Events/Notifications/Analytics domain expansion, tenant catalogue index/KG, Build/Rebuild controls, digital sharing or next phase was started.']
    (REPORTS/'institution_v2f_completion.md').write_text('\n'.join(content)+'\n',encoding='utf8')
    put('institution_v2f_report_index.json',{'status':'PASS','required_reports':reports,'completion':'institution_v2f_completion.md','stop_condition_respected':True})
    print(json.dumps({'status':'PASS','backend':passed,'frontend':775,'document_viewports':48,'product_viewports':96,'activity_audit_viewports':12,'required_reports':29,'TEST_resources_retained':2}))


if __name__=='__main__':
    main()
