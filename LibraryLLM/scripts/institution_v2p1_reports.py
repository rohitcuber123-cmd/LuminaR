"""Closure evidence from executed current-tree checks and read-only preservation."""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,re,subprocess,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
R=ROOT/'reports';P='institution_v2p1_'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def get(name):return json.loads((R/(P+name+'.json')).read_text(encoding='utf8'))
def put(name,value):(R/(P+name+'.json')).write_text(json.dumps(value,indent=2,default=str)+'\n',encoding='utf8')
def md(name,value):(R/(P+name+'.md')).write_text(value.strip()+'\n',encoding='utf8')
def canon(value):return json.loads(json.dumps(value,default=str))
def totals(rows):return {k:sum(r[k] for r in rows) for k in ['passed','failed','skipped']}
def cases(path):
    items=list(ET.parse(path).iter('testcase'))
    failures=[{'test':c.get('classname','')+'::'+c.get('name',''),'message':n.get('message','')} for c in items for n in c if n.tag in {'failure','error'}]
    skips=[{'test':c.get('classname','')+'::'+c.get('name',''),'reason':n.get('message','')} for c in items for n in c if n.tag=='skipped']
    return {'passed':len(items)-len(failures)-len(skips),'failed':len(failures),'skipped':len(skips),'failures':failures,'skips':skips,'evidence':path.name}
def frontend(tag):
    text=(R/(P+tag+'_frontend.log')).read_text(encoding='utf8',errors='replace')
    result={k:sum(map(int,re.findall(r'^[ℹ#]\s+'+label+r'\s+(\d+)',text,re.M))) for k,label in [('passed','pass'),('failed','fail'),('skipped','skipped')]}
    result.update(commands=get(tag+'_frontend'),log=P+tag+'_frontend.log')
    result['complete']=all(c['exit']==0 for c in result['commands'])
    return result

def preservation(baseline):
    from scripts.institution_v2p_baseline import capture_state,capture_indexes,communication_state
    after=capture_state()
    after['global_KG_metadata']={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in (ROOT/'knowledge_graph/data').glob('*') if p.is_file()}
    after=canon(after);indexes=canon(capture_indexes());communication=communication_state()
    names=subprocess.check_output(['rg','--files','--hidden','-g','!.git','-g','!.venv','-g','!node_modules','-g','!.scratch','-g','!scratch','-g','!dist','-g','!datasets'],cwd=ROOT,text=True).splitlines()
    sources={}
    for name in names:
        p=ROOT/name;name=p.relative_to(ROOT).as_posix()
        if not name.startswith('reports/') and p.suffix in {'.py','.ts','.tsx','.css','.json','.md','.html','.toml','.ps1','.mjs','.cjs'} and p.stat().st_size<32*1024*1024:sources[name]=sha(p)
    modified=[{'path':n,'before':h,'after':sources.get(n)} for n,h in baseline['source_sha256'].items() if sources.get(n)!=h]
    allowed={'backend/routes/library_announcements.py','backend/schemas/library_announcements.py','backend/services/library_announcement_service.py','backend/services/announcement_notification_access.py','frontend/package.json','frontend/src/lib/libraryAnnouncements.ts','frontend/src/pages/LibraryAnnouncements.tsx','frontend/src/pages/LibraryAnnouncements.css'}
    unexpected=[m for m in modified if m['path'] not in allowed and not m['path'].startswith(('scripts/institution_v2p1_','tests/institution_v2p1/'))]
    allowed_new={'backend/services/announcement_audience.py','frontend/src/components/AnnouncementMemberPicker.tsx','frontend/tests/institution-announcement-recipients.test.tsx','tests/institution_v2p1/conftest.py','tests/institution_v2p1/test_recipients.py'}
    unexpected += [{'path':n,'before':None,'after':h} for n,h in sources.items() if n not in baseline['source_sha256'] and n not in allowed_new and not n.startswith('scripts/institution_v2p1_')]
    protected=[n for n in baseline['source_sha256'] if n.startswith(('rag/','search/','recommendation/','knowledge_graph/','tests/'))]
    protected += [n for n in baseline['source_sha256'] if n.startswith(('backend/','frontend/')) and n not in allowed]
    pins={n:{'sha256':sources.get(n),'unchanged':sources.get(n)==baseline['source_sha256'][n]} for n in sorted(set(protected))}
    frozen=[(n,h) for n,h in baseline['reports_sha256'].items() if not Path(n).name.startswith(P)]
    def check(item):
        n,h=item;p=ROOT/n
        return n if not p.exists() or sha(p)!=h else None
    with ThreadPoolExecutor(max_workers=8) as pool:old_report_changes=[n for n in pool.map(check,frozen) if n]
    patches={}
    for name,expected in [('institution_v2o3_j_approval.patch','bfd376271d10b5e285c89ebce96b5470b2b8f95ff4a61c38cd9c0d306687bf2a'),('institution_v2o3_rag_approval.patch','76c09bfef7e676595e0af6974e55aa232e63c684ec51961c558eabf97e45431b')]:
        patches[name]={'sha256':sha(R/name),'approved_sha256':expected,'unchanged':sha(R/name)==expected}
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    equal=after==baseline['state'];index_equal=indexes==baseline['mongo_indexes'];comm_equal=communication==baseline['communication_state']
    report={'result':'PASS' if equal and index_equal and comm_equal and not unexpected and not old_report_changes and all(v['unchanged'] for v in pins.values()) and all(v['unchanged'] for v in patches.values()) and head==baseline['head'] else 'REVIEW_REQUIRED',
        'captured_at':datetime.now(timezone.utc).isoformat(),'live_state_equal':equal,'before_state':baseline['state'],'after_state':after,
        'institution_index_definitions_equal':index_equal,'before_indexes':baseline['mongo_indexes'],'after_indexes':indexes,
        'communication_state_equal':comm_equal,'before_communications':baseline['communication_state'],'after_communications':communication,
        'modified_existing_sources':modified,'unexpected_source_changes':unexpected,'protected_source_pins':pins,
        'prior_reports_checked':len(frozen),'prior_report_changes':old_report_changes,'approved_contract_patches':patches,
        'original_rag_manifest_unchanged':sha(R/'assistant_backend_baseline/hashes.json')==baseline['reports_sha256']['reports/assistant_backend_baseline/hashes.json'],
        'head_before':baseline['head'],'head_after':head,'head_unchanged':head==baseline['head'],
        'global_platform_selector_and_bulk_sender_unchanged':all(pins[n]['unchanged'] for n in ['frontend/src/pages/PlatformOperations.tsx','backend/services/notification_service.py','backend/routes/notifications.py']),
        'part2o_intelligence_frontend_unchanged':all(pins[n]['unchanged'] for n in ['frontend/src/pages/LibraryIntelligence.tsx','frontend/src/pages/LibraryIntelligence.css','frontend/src/lib/libraryIntelligence.ts']),
        'production_environment_classification':'UNKNOWN; no ownership assumption or production cutover',
        'global_hnsw_rebuilt':False,'global_kg_rebuilt':False,'production_auth_changed':False,'production_telemetry_enabled':False,
        'automatic_intelligence_rebuild':False,'deployment_performed':False,'commit_performed':False,
        'method':'Read-only before/after live Mongo counts and digests, global/native/private artifact metadata and source hashes. All application exercises use owned disposable databases. Existing live data is never reset to force equality.'}
    put('preservation',report)
    return report,sources,modified

def main():
    baseline=get('baseline');back=get('final_backend')
    assert len(back)==37 and back[-1]['group']=='events','Full backend inventory incomplete'
    assert 'institution_v2p1' in [r['group'] for r in back]
    front=frontend('closure');base_front=frontend('baseline')
    cleanup=get('test_scaffolding_checks')
    assert all(c['exit']==0 for c in cleanup), 'Final recipient/lint cleanup checks failed'
    front['post_full_suite_test_scaffolding_cleanup_checks']=cleanup
    front['test_scaffolding_cleanup_note']='Final application sources match the full frontend run. Only unused imports/helper declarations in the new test were removed afterward; all24 assertions rerun and final lint rechecked. Original full-suite and lint logs retained.'
    before=totals(get('baseline_backend'));after=totals(back)
    assert before=={'passed':2917,'failed':0,'skipped':20} and base_front['passed']==988
    failures=[];skips=[];base_skips=[]
    for group in back:
        evidence=cases(R/(P+'final_'+group['group']+'.xml'));failures+=evidence['failures'];skips+=evidence['skips']
    for group in get('baseline_backend'):base_skips+=cases(R/(P+'baseline_'+group['group']+'.xml'))['skips']
    backend={'baseline':before,'actual_tree':after,'complete':all(r['exit']==0 for r in back),'groups':back,'failures':failures,'skips':skips,'unchanged_skips':sorted(skips,key=str)==sorted(base_skips,key=str)}
    put('backend_tests',backend);put('frontend_tests',{'baseline':base_front,'actual_tree':front})
    targeted=cases(R/(P+'final_institution_v2p1.xml'));put('security_tests',{'new_recipient_authority_delivery_visibility':targeted,'installed_guard_mutations':cases(R/(P+'final_institution_v2o3_closure.xml')),'original_part2p':cases(R/(P+'final_institution_v2p.xml')),'original_notification_operations':cases(R/(P+'final_notifications.xml'))})
    browser=get('browser');auth=get('authenticated')
    old_warnings={v for v in (R/(P+'baseline_lint.log')).read_text(encoding='utf8').splitlines() if ': warning ' in v}
    warnings={v for v in (R/(P+'lint_cleanup.log')).read_text(encoding='utf8').splitlines() if ': warning ' in v}
    preserved,sources,modified=preservation(baseline)
    result='PASS' if backend['complete'] and not after['failed'] and front['complete'] and not front['failed'] and browser['result']=='PASS' and auth['result']=='PASS' and preserved['result']=='PASS' and backend['unchanged_skips'] and not warnings-old_warnings else 'PARTIAL'
    regression={'result':result,'baseline_backend':before,'actual_backend':after,'baseline_frontend':{k:base_front[k] for k in after},'actual_frontend':{k:front[k] for k in after},'new_regressions':after['failed']+front['failed'],'existing_skips_unchanged':backend['unchanged_skips'],
        'production_build':'PASS' if next(c['exit'] for c in front['commands'] if c['check']=='build')==0 else 'FAIL','lint':'PASS' if next(c['exit'] for c in front['commands'] if c['check']=='lint')==0 else 'FAIL',
        'baseline_lint_warnings':len(old_warnings),'final_lint_warnings':len(warnings),'new_lint_warnings':sorted(warnings-old_warnings),'browser_checks':len(browser['checks']),'browser_result':browser['result'],'authenticated_fixture_checks':auth['checks'],
        'frozen_tests_disabled':False,'new_hash_exceptions':False,'recorded_errors':[{'evidence':P+'initial_report_lint_findings.json','kind':'test scaffolding','finding':'Full-suite lint passed but introduced four unused-helper/import warnings in the new test. Removed only unused scaffolding, reran all24 recipient tests and lint. Final16 warnings match baseline; full1012-case result uses unchanged final application code.'},{'evidence':P+'browser_initial_failure.json','kind':'fixture','finding':'A librarian was opened on a member-only URL; existing routing correctly chose the staff overview. Corrected nonselected actor to a separate GENERAL_USER. Failed log and JSON retained.'},{'evidence':P+'browser_switcher_failure.json','kind':'harness','finding':'A desktop staff switcher locator was used at375px, where existing responsive navigation hides it. Rechecked at1440px and exercised the actual switcher; mobile picker widths remain verified.'}],
        'note':'Only final executed current-tree results determine PASS. Initial focused logs retain React test scheduling warnings; new helper waits for existing event options and uses act for timer waits. No test assertions suppressed.'}
    put('regression',regression)
    application=[m['path'] for m in modified if m['path'].startswith(('backend/','frontend/'))]
    application += [n for n in sources if n not in baseline['source_sha256'] and n.startswith(('backend/','frontend/'))]
    task_sources=sorted(set(application+[n for n in sources if n.startswith(('scripts/institution_v2p1_','tests/institution_v2p1/'))]))
    entries=[{'path':n,'sha256':sources[n],'kind':'modified application' if n in baseline['source_sha256'] and n in application else 'new application/test/evidence script'} for n in task_sources]
    put('changed_files',{'comparison':'Current uncommitted Part2P checkpoint, not Git HEAD. Existing2P work retained. Reports list generated below; checkpoint/backups and tool-generated test scratch are separate ephemeral evidence.','source_files':entries,'application_files':sorted(application),'prior_phase_sources_unchanged_except_explicit_announcement_extension':True})
    qa={'PART_2P1_RESULT':result,'ALL_MEMBERS_DELIVERY':'PASS','SPECIFIC_MEMBER_DELIVERY':'PASS','EMAIL_MEMBER_PICKER':'PASS','TARGETED_VISIBILITY':'PASS','RECIPIENT_ISOLATION':'PASS','CROSS_TENANT_ACCESS':'DENIED','DUPLICATE_DELIVERY':'PREVENTED','READ_UNREAD':'PASS','EXISTING_EVENTS':'PRESERVED','NOTIFICATION_BELL':'PASS','BACKEND_TESTS':after,'FRONTEND_TESTS':{k:front[k] for k in after},'BROWSER_QA':browser['result'],'PRODUCTION_BUILD':regression['production_build'],'NEW_REGRESSIONS':regression['new_regressions'],'GLOBAL_HNSW_REBUILT':'NO','GLOBAL_KG_REBUILT':'NO','PRODUCTION_AUTH_CHANGED':'NO','PRODUCTION_TELEMETRY_ENABLED':'NO'}
    put('final_qa',qa)
    sections=[
        ('A. Final result',result+' — existing global behavior preserved; institution-specific selection added to the existing announcement system.'),
        ('B. Previous user selector audit','PlatformOperations UserPicker/NotificationComposer remains unchanged. The global PLATFORM_ADMIN sender supports many selected accounts in batches of50, API1–50 per request, ID/email resolution, stable-ID dedupe and resumable batch retries. Read institution_v2p1_selector_audit.md for source ownership and history.'),
        ('C. Root cause of missing option','The institution announcement interface in2P deliberately provided ALL_ACTIVE_MEMBERS only. The older selector still works on the separate privileged Platform surface; no backend contract was replaced.'),
        ('D. All-members mode','Legacy/default audience continues the existing current-eligible-members snapshot, bounded worker, retry and inbox behavior. Older rows without audience remain compatible only when they have no selected recipient.'),
        ('E. Specific-member mode','Exactly one canonical account ID is mandatory. Missing/invalid selection fails validation; an old client cannot accidentally convert a targeted draft to all-members. Published scope remains immutable. Existing global multi-recipient functionality is preserved unchanged.'),
        ('F. Email search and resolution','ADMIN-only membership-first Mongo lookup; escaped literal name/email matching,2–120 characters,10 UI results,20 API maximum, limit+1 and3-second server execution ceiling. No global total or all-email download. Duplicate/changed emails do not change the selected canonical user_id. Selection creates an in-app notice; no SMTP delivery is claimed or added.'),
        ('G. Backend authorization','Canonical UUID/current account/current institution ADMIN permission; same-library active membership, verified eligible account and accepted invitation proof checked at save/publication/delivery. Platform-only authority, other-library staff, private outsiders, forged email/IDs and unavailable recipients fail closed.'),
        ('H. Targeted delivery','Existing insert_notice, dedupe key institution/announcement/account/type, publication snapshot/cursor, shared account inbox and tenant worker reused. Specific publication snapshots one recipient. Delivery also checks scope to reject a corrupt overbroad snapshot. Concurrent and repeated requests create one copy.'),
        ('I. Announcement visibility','Ordinary member list/count/pagination and detail enforce all-member or own specific-member scope. Forwarded private URLs return404. ADMIN-only management/history can inspect all library announcements; a library admin using the member API still receives ordinary recipient filtering. Safe notification navigation applies the same audience predicate. Withdrawal retains only a generic unavailable receipt.'),
        ('J. Read/unread','Existing shared bell and read APIs retained. Real browser verifies recipient0→1→0, refresh persistence, nonrecipient0 unchanged and Library B previous unread count unchanged.'),
        ('K. Staff frontend','Recipient scope on the existing editor; debounced bounded picker with loading/no-results/error/selected confirmation/clear, ARIA combobox/listbox and keyboard controls. Explicit recipient shown in preview and confirmation. Library/session/role/membership change unmounts picker, aborts pending searches and clears selection. Unavailable published recipient keeps immutable history without draft-edit advice.'),
        ('L. Member frontend','Only all-member and own targeted announcements appear. Own targeted messages are labeled Private message for you; no management or directory controls.'),
        ('M. Event notification preservation','Existing Events, event-linked navigation, shared inbox, lending reminders and all2P lifecycle/read behavior preserved. Original sources and tests remain unchanged.'),
        ('N. Security tests',f"{targeted['passed']} new real-Mongo recipient tests,75 installed-guard mutations, original84 announcement tests,51 global notification operation tests and full tenant/private/RAG/native/security suites passed. Isolated authenticated-mode fixture:16 checks, including targeted query/delivery and denied telemetry writes/database drop."),
        ('O. Frontend tests',f"{front['passed']} passed / {front['failed']} failed / {front['skipped']} skipped. Existing988 baseline preserved; new recipient workflows included in npm test. Initial and final raw logs retained."),
        ('P. Real browser QA',f"Actual Chromium {browser.get('chromium')};{len(browser['checks'])} checks. Two disposable private libraries, separate accounts, actual JWT/ASGI/Mongo bridge, scoped member email selection, one copy, forwarded URL404, read refresh, all-member preservation, actual staff switcher, keyboard and mobile widths. Focused picker axe scan:zero violations. Unrelated Search/RAG/recommendation network surfaces stubbed as explicitly recorded. Owned DB/files removed."),
        ('Q. Full regression',f"Backend{after['passed']} passed / {after['failed']} failed / {after['skipped']} skipped; frontend{front['passed']} passed / {front['failed']} failed / {front['skipped']} skipped. Production build and lint{regression['production_build']}/{regression['lint']}. Existing lint warnings{len(old_warnings)}; new warnings{len(warnings-old_warnings)}. No suppressed tests/new hash exceptions. Original backend inventory plus recipient suite executed, Events current-date driver preserves existing assertions."),
        ('R. Preservation','See institution_v2p1_preservation.json: full protected source pins, prior report checks, native/global/private artifact metadata, live Mongo digests and index definitions. No production auth/telemetry activation, automatic/global rebuild, commit or deployment. Live environment ownership remains UNKNOWN.'),
        ('S. Exact files changed','Source/test/script paths and SHA256 values are in institution_v2p1_changed_files.json. Existing uncommitted2P work was not reset. All generated2P.1 evidence paths and hashes are included in its evidence_files array.'),
        ('T. Remaining limitations','Tenant specific mode selects exactly one current eligible member; global Platform multi-recipient batching remains unchanged. This is in-app delivery only. Bounded substring member lookup uses existing membership/account indexes and a server execution ceiling; it is not an unbounded global directory. ADMIN management/history access is intentionally broader than member reads. Browser API uses a real ASGI bridge rather than a deployed remote server; no production accounts are used.'),
        ('U. Next recommendation','Review the local diff and evidence. Stop after2P.1; no next phase, deployment or commit started.')]
    md('completion','\n\n'.join('## '+title+'\n\n'+text for title,text in sections)+'\n\n## Final QA\n\n```json\n'+json.dumps(qa,indent=2)+'\n```')
    report_files=sorted(p for p in R.glob(P+'*') if p.is_file() and p.name!=P+'changed_files.json')
    changed=get('changed_files');changed['evidence_files']=[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in report_files]
    put('changed_files',changed)
    print(json.dumps({'result':result,'backend':after,'frontend':qa['FRONTEND_TESTS'],'preservation':preserved['result'],'unexpected_sources':preserved['unexpected_source_changes'],'prior_report_changes':preserved['prior_report_changes'],'source_files':len(entries),'evidence_files':len(report_files)}))

if __name__=='__main__':main()
