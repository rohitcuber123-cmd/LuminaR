"""Summarize captured browser observations; preserve errors and coverage gaps."""
from pathlib import Path
import json,re
R=Path(__file__).resolve().parents[1];D=R/'reports'
def get(name):return json.loads((D/name).read_text(encoding='utf8'))
def snap(name):return (D/f'institution_v2q2_browser_{name}.txt').read_text(encoding='utf8')

def main():
 obs=get('institution_v2q2_browser_observations.json')
 late=next(x for x in obs if x['case']=='late_A_response_after_B_switch' and x.get('held_http_status')==200)
 initial=get('institution_v2q2_browser_network_initial.json');last=get('institution_v2q2_browser_network_final.json');console=get('institution_v2q2_browser_console_final.json')
 lib=get('institution_v2q2_fixture_manifest.json')['libraries'][1]['library_id']
 paths=re.findall(r'/libraries/'+re.escape(lib)+r'/books/[0-9a-f-]+',snap('B_ForYou'))
 data={'status':'PARTIAL','browser':'One owned in-app browser session remained available; previous tab-loss cause not proven.',
       'cleanup_timing':'Browser closed after screenshots and final answers; owned services and fixtures removed afterward.',
       'executed':{
        'login_logout_relogin':True,
        'Global_ForYou':'Controlled provider omits metadata and produces Unknown Title cards.',
        'Private_A_ForYou':'Actual tenant service; member-home evidence in logout_relogin.txt and browser_A.png. Initial owner A_ForYou snapshot shows staff overview and is not used as patron rail proof.',
        'Private_B_ForYou':{'observed_book_links':len(paths),'unique_books':len(set(paths)),'all_in_B':len(paths)==84},
        'book_detail_navigation':True,
        'genuine_qwen_browser_subset':{scope:'available (2 available copies, 2 total).' in snap(scope+'_Qwen_final_availability') for scope in ['Global','A','B']},
        'outsider_private_document_denied':'Library resource not found.' in snap('outsider_document_denial'),
        'revoked_member_document_denied':'Library resource not found.' in snap('revoked_document_denial'),
        'authorized_member_resource_visible':'A fixture manual' in snap('authorized_A_resource'),
        'no_match_title_search':'No books match all selected filters.' in snap('A_no_match_final'),
        'late_old_response':late,'keyboard_focus':'Skip to content',
        'mobile':next(x for x in obs if x['case']=='mobile_B_detail')},
       'semantic_defects':[{'case':'B digital-copy follow-up','observed':'Repeats physical stock counts instead of answering digital availability.','evidence':'institution_v2q2_browser_B_Qwen_digital_followup.txt','expected_resource_metadata':'B detail shows Physical + Online and online copy available.'}],
       'console_entries_captured':len(console),
       'network_capture':{'initial_entries':len(initial),'final_entries':len(last['events']),'final_buffer_truncated':last['truncated'],'final_has_more':last['hasMore'],'limits':'Older CDP events were evicted; these captures do not establish exhaustive HTTP coverage.'},
       'known_api_errors':[
        {'http':404,'route':'/search-api/facets','cause':'Diagnostic lab does not install complete Global facets route.'},
        {'http':503,'route':'Private B catalogue recommendations','response':'Library update in progress. Please retry.','context':'Concurrent owned fixture activity; later ownership/UI checks succeed.'},
        {'http':502,'route':'/rag-api/assistant/chat','context':'Intentional service reload overlapped first late-response attempt. That attempt is not counted as a successful-response isolation test.'}],
       'automation_errors_retained':[
        {'error':'Uppercase login selector did not match DOM Title Case','resolution':'Inspected DOM; used actual labels.'},
        {'error':'Post-logout login wait expired before navigation settled','resolution':'Inspected eventual login page and completed relogin.'},
        {'error':'Playwright body.press(Tab) failed','resolution':'Native tab pressKey focused Skip to content.'},
        {'error':'View all matched two links','resolution':'Used observed visible catalogue href.'},
        {'error':'Mode-change navigation reset early no-match input','resolution':'Resubmitted after Title / Author mode settled; retained final empty-result state.'},
        {'error':'Invalid InterceptionId after navigation','resolution':'Exact held request was canceled; cleared interception and verified empty B conversation.'},
        {'error':'First report-generation attempt used Windows default cp1252 and raised UnicodeDecodeError','resolution':'Report reader now explicitly uses UTF-8; application and tests were unaffected.'}],
       'remaining_limits':['Global provider/facets are controlled and incomplete.','Exact390px viewport was not honored; actual487inner/469client recorded.','Only one successful response-stage cancellation, not a universal generation timing matrix.','Digital-copy follow-up remains wrong.','Older network events were evicted.'],
       'instrumentation_cleanup':{'fetch_patterns_cleared':True,'viewport_reset':True,'owned_tab_closed':True}}
 (D/'institution_v2q2_browser_qa.json').write_text(json.dumps(data,indent=2),encoding='utf8')
 warnings=lambda name:sorted(x for x in (D/name).read_text(encoding='utf8',errors='replace').splitlines() if ': warning ' in x)
 old=warnings('institution_v2q1d_lint.log');new=warnings('institution_v2q2_lint_final.log');assert old==new and len(new)==16
 p=D/'institution_v2q2_repairs.json';d=get(p.name);d.update(initial_lint_warnings=18,lint_warnings=16,lint_warning_multiset_unchanged=True,lint_cleanup='Removed disposable Vite config after stopping fixture frontend; final lint exits0 with original16warnings; no suppression.');p.write_text(json.dumps(d,indent=2))
 p=D/'institution_v2q2_frontend_tests.json';d=get(p.name)
 if not any(x['check']=='lint_after_fixture_cleanup' for x in d['checks']):d['checks'].append({'check':'lint_after_fixture_cleanup','exit':0,'log':'institution_v2q2_lint_final.log','warnings':16,'warning_multiset_matches_baseline':True})
 p.write_text(json.dumps(d,indent=2))
 print(json.dumps({'B_links':len(paths),'Qwen_subset':data['executed']['genuine_qwen_browser_subset'],'console_entries':len(console),'network_truncated':last['truncated'],'final_lint_warnings':len(new)}))

if __name__=='__main__':main()
