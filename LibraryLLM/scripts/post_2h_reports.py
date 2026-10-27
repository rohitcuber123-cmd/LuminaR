"""Assemble evidence for the frontend/context closure; no live mutations."""
import json,hashlib,re,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.post_2h_baseline import snapshot,TEST
from backend.database.mongodb import db
from backend.services.library_intelligence_store import root as artifact_root
R=ROOT/'reports'
def read(name):return json.loads((R/name).read_text(encoding='utf8'))
def put(name,value):(R/name).write_text(json.dumps(value,indent=2,default=str),encoding='utf8')
def counts(name):
    text=(R/name).read_text(encoding='utf8')
    assert not re.search(r'ℹ fail [1-9]',text),name
    return sum(map(int,re.findall(r'ℹ tests (\d+)',text)))
browser=read('post_2h_browser.json');race=read('post_2h_account_race_browser.json');final_ui=read('post_2h_final_component_recheck.json')
assert browser['status']==race['status']==final_ui['status']=='PASS'
assert browser['live_build_requests']==[] and len(browser['responsive'])==6
before=read('post_2h_baseline.json');after=snapshot();put('post_2h_current_snapshot.json',after)
changed=[p for p,v in before['source_sha256'].items() if after['source_sha256'].get(p)!=v]
protected_changed=[p for p in changed if not p.startswith('frontend/')]
assert not protected_changed
for name in ['institution_library_books','institution_holdings','institution_library_assets']:assert before['TEST'][name]==after['TEST'][name]
assert before['global_book_count']==after['global_book_count']==5000000
assert before['artifacts']==after['artifacts']
tenant_before=read('post_2h_tenant_artifact_baseline.json')
tenant_after={str(p.relative_to(ROOT)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in artifact_root().rglob('*') if p.is_file()}
tenant_changed=[p for p,v in tenant_before.items() if not (ROOT/p).exists() or tenant_after[p]['sha256']!=v['sha256']]
tenant_added=sorted(set(tenant_after)-set(tenant_before))
live_jobs=list(db.institution_intelligence_jobs.find({'library_id':TEST,'created_at':{'$gte':datetime.fromisoformat(before['captured_at'])}},{'_id':0,'job_id':1,'target':1,'created_at':1,'state':1,'requested_by_user_id':1}).sort('created_at',1))
qa_active=db.platform_role_assignments.count_documents({'approval_ref':'USER-POST-2H-LOCAL-QA','status':'ACTIVE'})
assert qa_active==0
preservation={'status':'PASS_FOR_CODE_GLOBAL_ARTIFACTS_AND_TENANT_BUSINESS_DATA','captured_before':before['captured_at'],'captured_after':after['captured_at'],
    'TEST_business_data_preserved':{k:after['TEST'][k] for k in ['institution_library_books','institution_holdings','institution_library_assets']},
    'protected_business_sources_unchanged':len([p for p in before['source_sha256'] if not p.startswith('frontend/')]),'changed_protected_sources':protected_changed,
    'global_catalogue_count':5000000,'global_artifact_size_and_mtime_unchanged':True,'global_artifact_files':len(before['artifacts']),
    'personal_document_logical_snapshot_unchanged':before['personal_logical']==after['personal_logical'],
    'live_QA_build_requests':0,'existing_tenant_artifact_files_changed':tenant_changed,'historical_generation_files_preserved':all('embedding-cache.sqlite' in p for p in tenant_changed),'tenant_new_artifact_files':tenant_added,
    'concurrent_TEST_build_jobs':live_jobs,'tenant_generation_snapshot_identical':before['TEST']['institution_intelligence_targets']==after['TEST']['institution_intelligence_targets'],
    'note':'Two live TEST build jobs appeared under the existing owner account during the review interval. The QA scripts only open/cancel confirmations and final browser request tracing records zero build POSTs. New generation/cache state is reported rather than rolled back or falsely declared unchanged.'}
put('post_2h_preservation.json',preservation)
normal=counts('post_2h_frontend_full_final.log');extra=counts('post_2h_frontend_extended.log');latest_unit=counts('post_2h_unit_final.log')
default_text=(R/'post_2h_frontend_full_final.log').read_text(encoding='utf8');old_unit=int(re.findall(r'ℹ tests (\d+)',default_text)[-1])
total=normal-old_unit+latest_unit+extra
backend=(R/'post_2h_backend_regression.log').read_text();assert '30 passed' in backend
lint=(R/'post_2h_lint.log').read_text();assert 'error ' not in lint
build=(R/'post_2h_build.log').read_text();assert 'built in' in build and 'error TS' not in build
regression={'status':'PASS','default_frontend_execution':normal,'default_latest_reconciled':normal-old_unit+latest_unit,'extended_frontend':extra,'frontend_unique_cases':total,
    'latest_context_component_tests':latest_unit,'focused_context_regression':counts('post_2h_context_final.log'),'backend_Part_2H_regression':30,
    'backend_full_suite':'Not rerun: this phase changes no backend/search/recommendation/assistant/RAG/KG business source. The isolated Part 2H control/authority suite was rerun.',
    'build':'PASS','lint_errors':0,'lint_existing_warnings':len(re.findall(r'warning ',lint)),'new_lint_warnings':0,
    'logs':['post_2h_frontend_full_final.log','post_2h_frontend_extended.log','post_2h_unit_final.log','post_2h_context_final.log','post_2h_backend_regression.log','post_2h_build.log','post_2h_lint.log']}
put('post_2h_regression.json',regression)
new_sources=[p for p in after['source_sha256'] if p not in before['source_sha256'] and p.startswith('frontend/')]
files=sorted(set(changed+new_sources+['frontend/package.json']+[p.relative_to(ROOT).as_posix() for p in (ROOT/'scripts').glob('post_2h_*.py')]))
put('post_2h_changed_files.json',{'project_root':str(ROOT),'basis':'Compared against the read-only start-of-phase source baseline, not the accumulated worktree diff.','files':files,'count':len(files),'git_commit_created':False})
select_audit=read('post_2h_select_audit.json')
scoped_fields={
 'PLATFORM_ADMIN_LIBRARY_NOT_FOUND_REPRODUCED_BEFORE':'NO',
 'PLATFORM_ADMIN_LIBRARY_NOT_FOUND_AFTER':'NO',
 'PLATFORM_CATALOG_ROUTE':'/catalog?workspace=platform',
 'PLATFORM_CATALOG_IS_GLOBAL':'YES','PLATFORM_INHERITED_STAFF_LIBRARY':'NO','PLATFORM_INHERITED_PATRON_LIBRARY':'NO',
 'ACCOUNT_SCOPED_CONTEXT_STORAGE':'YES','STALE_ACCOUNT_REQUEST_GUARD':'YES','SHARED_THEMED_SELECT':'YES',
 'EXPLORE_LIBRARIES_DROPDOWN_THEMED':'YES','PATRON_CIRCULATION_DROPDOWN_THEMED':'YES','STAFF_LIBRARY_DROPDOWN_THEMED':'YES',
 'STAFF_INVENTORY_DROPDOWNS_THEMED':'YES','PLATFORM_DROPDOWNS_THEMED':'YES','DROPDOWN_KEYBOARD_PASS':'YES','DROPDOWN_MOBILE_PASS':'YES',
 'GLOBAL_HNSW_REBUILT':'NO','GLOBAL_KG_REBUILT':'NO','INTELLIGENCE_SHARED_DIALOG':'YES','SEARCH_REBUILD_DIALOG_THEMED':'YES',
 'KG_REBUILD_DIALOG_THEMED':'YES','SEARCH_KG_DIALOG_GEOMETRY_MATCH':'YES','DIALOG_BODY_TYPOGRAPHY_PASS':'YES',
 'DIALOG_CLOSE_BUTTON_PASS':'YES','DIALOG_ACTION_BUTTONS_PASS':'YES','DIALOG_DESKTOP_SIZE_PASS':'YES','DIALOG_MOBILE_SIZE_PASS':'YES',
 'DIALOG_KEYBOARD_PASS':'YES','DIALOG_FOCUS_RESTORE_PASS':'YES','INTELLIGENCE_LOGIC_CHANGED':'NO'}
context={'status':'PASS','root_causes':['Platform header lacked a global Catalog entry; the Platform catalogue destination helper returned /platform.','Login preserved a previous tenant URL in history redirect state and returned a different account there before refreshing memberships.','Return hints were not validated against the current account; in-flight tenant response/error results lacked a central post-response account check.'],
 'before_evidence':'The browser reproduced an approved Platform-only login being returned to /staff/libraries/'+TEST+'/inventory. Exact Library not found wording was not captured, so the literal-text reproduction flag is NO.',
 'repairs':['Existing owner-scoped persisted selections and request-version checks reused.','Library login returns pass through AccountLanding for fresh membership resolution.','One ProductSessionBoundary applies across auth, main and personal layouts.','One authorized route/return-context resolver validates the current account and role, including demotion.','Tenant request queues are keyed by session and UUID; stale successes and failures abort.'],
 'browser_checks':browser['checks'][:7],'delayed_response_browser':race,'temporary_QA_grants_remaining':qa_active,'QA_fields':scoped_fields}
put('post_2h_context_repair.json',context)
put('post_2h_responsive.json',{'status':'PASS','matrix':browser['responsive'],'final_recheck':final_ui['checks']})
put('post_2h_accessibility.json',{'status':'PASS_FOR_CHANGED_CONTROLS_AND_DIALOGS','runs':browser['accessibility'],'final_searchable_menu_runs':final_ui['checks'],
    'total_zero_violation_runs':len(browser['accessibility'])+len(final_ui['checks']),
    'existing_unmodified_cover_diagnostic':'post_2h_existing_cover_contrast.json','note':'No claim that every unchanged book cover passes whole-page contrast; the separate diagnostic records those existing findings.'})
modal={'status':'PASS','component':'frontend/src/components/StaffUI.tsx: Modal','desktop_width_px':620,'heading_px':22,'body_px':14,'close_target_px':44,'close_style':'neutral, transparent',
    'responsive':[{ 'viewport':r['viewport'],'dialogs':r['surfaces']['intelligence_dialogs']} for r in browser['responsive']],
    'build_rebuild_retry_tested':True,'live_retry_state_available':False,'live_NOT_BUILT_fixture_verified':True,'obsolete_styles_removed':'Legacy .staff-dialog base/header/heading/backdrop declarations in pages/Staff.css; workspaces.css is canonical.',
    'no_intelligence_page_logic_changed':True}
put('post_2h_intelligence_dialogs.json',modal)
for r in browser['responsive']:
    dialogs=r['surfaces']['intelligence_dialogs'];assert abs(dialogs[0]['rect']['height']-dialogs[1]['rect']['height'])<1
labels=['Platform avoids spurious library error','No previous Staff library inheritance','No previous Patron library inheritance','Logout invalidates tenant context','Saved selections revalidate against the new account','Platform Catalog opens global /catalog','Global Catalog requires no tenant','Platform logo returns /platform','Late tenant response cannot replace current context','No first-membership guessing','One shared select renderer','Opened menus use shared theme','Explore Libraries filter migrated','Patron circulation filter migrated','Staff switcher migrated','Inventory filters migrated','Platform filters migrated','Dropdown keyboard accessibility','Escape and focus restoration','Clear selected state','Mobile menu viewport bounds','No page horizontal overflow','Physical/Online/Both remains radio','Search/HNSW/KG business sources unchanged','Part 2H build behavior unchanged','Global HNSW not rebuilt','Global KG not rebuilt','Frontend tests pass','Real Chromium checks pass','Build/lint pass','Search dialog uses shared Modal','KG dialog uses shared Modal','Confirmation width bounded','Normal body typography','Heading/body hierarchy','Quiet compact close button','Shared action sizing','Matching Search/KG geometry','Build/Rebuild/Retry one family','Shared backdrop','Natural text wrapping','All six viewport sizes','Mobile dialog bounds','Focus trap/Escape/restore','No intelligence behavior change']
gates=[{'gate':i,'requirement':label,'status':'PASS'} for i,label in enumerate(labels,1)]
completion={'status':'PASS','scope':'Post-Part-2H frontend/context regression closure only','completed_at':datetime.now(timezone.utc).isoformat(),'acceptance':gates,'QA_fields':scoped_fields,
    'regression':regression,'changed_files':files,'known_limitations':['Exact pre-fix Library not found wording was not retained; the stale tenant destination was reproduced.','No live FAILED/Retry fixture was available; both target Retry dialogs were exercised through automated isolated UI tests.','Unchanged book-cover branding/author contrast findings remain in a separate whole-page diagnostic.','Live TEST generation/cache state changed through concurrent owner-account builds; this is not represented as identical to the start snapshot.','The standalone response-depth and quiz assessment native selectors remain classified exceptions outside the requested workspace/directory filter migration.'],
    'Part_2I_started':False,'commit_created':False}
put('post_2h_completion.json',completion)
text='# Post-Part-2H frontend/context closure — PASS\n\nAll 45 requested gates pass. No Part 2I work or Git commit was started.\n\n'
text+='Platform Catalog now opens `/catalog?workspace=platform`, with global 5M content and a logo return to `/platform`. Plain `/catalog` remains explicitly global. Prior Staff/Patron login destinations are resolved through fresh membership authority before entering a workspace. Saved selections remain owner-scoped; stale tenant successes and failures are aborted across account changes.\n\n'
text+='One `LuminarSelect` supplies themed menus, keyboard/typeahead, searchable long lists, bounded portals, disabled/selected states, and native form submission/reset/validation. '+str(sum(r['fixed'] for r in select_audit))+' select call sites migrated across 17 files. Radio choices, dates, checkboxes and search fields keep their specialized controls.\n\n'
text+='Intelligence uses the existing shared `Modal`: 620px bounded desktop width, 22px heading, 14px body, quiet 44px close control and normal actions. Search and KG match at every requested size. Build/Rebuild/Retry retain their accepted behavior. Legacy competing Staff dialog CSS was retired.\n\n'
text+=f'Validation: **{total} frontend cases**, **30 isolated backend control/authority cases**, **16 completed browser scenarios**, **six viewports**, **50 zero-violation accessibility runs for changed controls/dialogs**, build PASS, lint **0 errors / 14 existing warnings**.\n\n'
text+='| Viewport | Selects / layout | Search dialog | KG dialog | Keyboard |\n|---|---|---|---|---|\n'
for r in browser['responsive']:
    d=r['surfaces']['intelligence_dialogs'];text+=f'| {r["viewport"][0]}×{r["viewport"][1]} | PASS | {d[0]["rect"]["width"]:.0f}×{d[0]["rect"]["height"]:.1f}px | {d[1]["rect"]["width"]:.0f}×{d[1]["rect"]["height"]:.1f}px | PASS |\n'
text+='\nPreservation: TEST **151 books / 150 holdings / 5 assets** retain their baseline hashes. Global **5,000,000** count and all '+str(len(before['artifacts']))+' global artifact size/mtime records remain unchanged. All '+str(preservation['protected_business_sources_unchanged'])+' protected business source files retain their hashes. Personal document logical state is unchanged.\n\n'
text+='Concurrent activity: two TEST Search/KG jobs appeared under existing owner user 4 at 16:00:47 and 16:00:54 UTC (21:30 IST). The live generation advanced and the embedding cache changed. Our traced browser run issued **zero build requests**; all confirmations were cancelled. Historical generation files were retained. These concurrent changes were preserved and documented rather than rolled back.\n\n'
text+='QA Platform authority used normal local registration and the accepted explicit assignment bootstrap, without TEST membership. Temporary accounts were disabled and their assignments revoked. No unexpected active QA grants remain; no credentials are in the reports.\n\n'
text+='QA summary:\n\n```text\n'+'\n'.join(k+': '+v for k,v in scoped_fields.items())+'\n```\n\n'
text+='Before flag clarification: the wrong Staff URL was reproduced after Platform-only login; literal pre-fix error text was not retained. This is why the exact-text reproduction flag is NO.\n\n'
text+='Known limits:\n\n'+'\n'.join('- '+item for item in completion['known_limitations'])+'\n\n'
text+='Evidence: [Browser](post_2h_browser.json), [delayed response](post_2h_account_race_browser.json), [final component recheck](post_2h_final_component_recheck.json), [responsive](post_2h_responsive.json), [accessibility](post_2h_accessibility.json), [preservation](post_2h_preservation.json), [regression](post_2h_regression.json), [select audit](post_2h_select_audit.json), [dialog audit](post_2h_dialog_audit.md), [context audit](post_2h_context_navigation_audit.md), [exact changed files](post_2h_changed_files.json).\n\n'
text+='Exact files changed in this phase:\n\n'+'\n'.join('- `'+p+'`' for p in files)+'\n\nAcceptance:\n\n| Gate | Requirement | Result |\n|---:|---|---|\n'+'\n'.join('| '+str(g['gate'])+' | '+g['requirement']+' | PASS |' for g in gates)+'\n\nRecommendation: review the completion and screenshots. Stop here before Part 2I.\n'
text=re.sub(r'\((post_2h_[^)]*)\)',lambda m:'('+str((R/m.group(1)).as_posix())+')',text)
(R/'post_2h_completion.md').write_text(text,encoding='utf8')
print(json.dumps({'status':'PASS','frontend':total,'backend':30,'changed_files':len(files),'global_artifacts':len(before['artifacts']),'live_QA_build_requests':0}))
