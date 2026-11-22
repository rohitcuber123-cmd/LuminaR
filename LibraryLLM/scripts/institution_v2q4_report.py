"""Assemble actual Part2Q.4 evidence; never rebaseline protected application files."""
from pathlib import Path
import difflib, hashlib, json, re, subprocess

R=Path(__file__).resolve().parents[1]
P=R/'reports'
def read(n):return json.loads((P/f'institution_v2q4_{n}.json').read_text(encoding='utf8'))
def write(n,d):(P/f'institution_v2q4_{n}.json').write_text(json.dumps(d,indent=2),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 rows=json.loads((P/'institution_v2q_2q4_backend.json').read_text())
 counts={k:sum(x.get(k,0) for x in rows) for k in ['passed','failed','skipped']}
 assert len(rows)==38 and not counts['failed'] and all(x['exit']==0 for x in rows)
 frozen=read('final_source')['source_sha256'];assert all(sha(R/n)==h for n,h in frozen.items())
 write('backend_tests',{'counts':counts,'groups':rows,'source_drift_after_checks':[],'baseline':[3124,0,20]})
 text=(P/'institution_v2q4_final_frontend.log').read_text(encoding='utf8')
 front={k:sum(map(int,re.findall('ℹ '+label+r' (\d+)',text))) for k,label in [('passed','pass'),('failed','fail'),('skipped','skipped')]}
 checks=read('final_frontend_checks');assert not front['failed'] and all(x['exit']==0 for x in checks)
 warnings=(P/'institution_v2q4_final_lint.log').read_text(encoding='utf8').count(': warning ')
 write('frontend_tests',{'counts':front,'checks':checks,'lint_warnings':warnings,'baseline':[1030,0,0]})
 paths=['assistant/orchestrator.py','backend/services/library_catalogue_experience.py','frontend/src/components/ForYou.tsx','frontend/tests/recommendation-runtime.test.tsx','tests/institution_v2q_ai/test_v2q1_parallel_core.py','tests/institution_v2q_ai/test_borrowing_information_q4.py','tests/institution_v2q_ai/test_recommendation_concurrency_q4.py']
 changes=[];patch=[]
 for n in paths:
  before=R/'.scratch/institution-v2q/q4-before'/n;current=R/n
  changes.append({'path':n,'absolute_path':str(current),'before_sha256':sha(before) if before.exists() else None,'after_sha256':sha(current)})
  prior=before.read_bytes().decode('utf8').splitlines(keepends=True) if before.exists() else []
  diff=difflib.unified_diff(prior,current.read_bytes().decode('utf8').splitlines(keepends=True),fromfile='a/'+n if before.exists() else '/dev/null',tofile='b/'+n)
  for line in diff:
   patch.append(line if line.endswith('\n') else line+'\n\\ No newline at end of file\n')
 target=P/'institution_v2q4_changes.patch';target.write_bytes(''.join(patch).encode('utf8'))
 reverse=subprocess.run(['git','apply','--reverse','--check',str(target)],cwd=R,capture_output=True,text=True)
 assert reverse.returncode==0,reverse.stderr
 write('changed_files',{'application_and_tests':changes,'patch_sha256':sha(target),'reverse_check_exit':0,'scope':'Three application files; four test files. Existing dirty changes preserved.'})
 prior=json.loads((P/'institution_v2q3_artifact_manifest.json').read_text())
 old_errors=[x['path'] for x in prior['files'] if x['path'].startswith(('reports/','scripts/')) and (not (R/x['path']).exists() or sha(R/x['path'])!=x['sha256'])]
 preservation=read('preservation');preservation['prior_q3_artifact_changes']=old_errors;preservation['prior_q3_artifacts_preserved']=not old_errors
 preservation['live_reference_limit']='Live state compared to Part2Q.3 observation, not an independently captured Q4 start. Do not infer attribution or roll back concurrent data.'
 preservation['overall_result']='PARTIAL' if old_errors else preservation['result'];write('preservation',preservation)
 security=read('security');security_cases=security['cases']
 initial=read('live_final');repeat=read('live_B_recheck')
 live=initial['cases']+repeat['cases'];denied=[x for x in live if x['http']!=200]
 write('real_qwen_validation',{'chat_attempts':len(live),'successful_chat_workflows':sum(x['http']==200 for x in live),'initial_B_missing_membership_denials':len(denied),'authorized_B_rechecks':repeat['cases'],'private_rag':initial['private_rag']+repeat['private_rag'],'model':'Qwen2.5-3B NF4 CUDA unchanged; single owned runtime','browser_additional_workflows':3,'limits':'Counts describe requests, not general model accuracy. Browser explicit follow-up clarified exact local record. No repeated intent generation via application retry.'})
 switch=read('browser_switch');diagnostics=read('browser_diagnostics')
 write('browser_qa',{'result':'PARTIAL','observations':read('browser_observations'),'controlled_503_responses':read('browser_controlled_failures'),'scope_switch':switch,'diagnostics':diagnostics,'limits':['Exact390px unavailable: observed487px.','Keyboard coverage limited to native Tab/Skip control.','No empty-catalogue browser case; existing API fallback tests retained.','Explicit borrowing follow-up asked for exact record; fresh-request API confirms correctly.'],'cleanup':read('fixture_cleanup')})
 protected={n:{'before':read('checkpoint')['source_sha256'][n],'after':sha(R/n)} for n in ['rag/qa.py','rag/llm.py']};assert all(x['before']==x['after'] for x in protected.values())
 write('regression',{'backend':counts,'frontend':front,'new_automated_failures':0,'protected':protected,'security_cases':len(security_cases),'security_passed':sum(bool(x['pass']) for x in security_cases),'retained_errors':['Initial lock reproduction503','Obsolete historical bug-reproduction assertion failed before expectation updated to success','Initial frontend recovery assertion timeout/multiple-match; corrected test selectors','Initial B fixture had no membership;404denials retained','HistoricalQ3frontend.log overwritten by accidental runner invocation'],'no_loan_mutation':read('no_loan_mutation')})
 qa={'PART_2Q4_RESULT':'PARTIAL','RECOMMENDATION_503_ROOT_CAUSE':'CONFIRMED','RECOMMENDATION_CONCURRENCY':'PASS','RECOMMENDATION_FALLBACK':'SAFE','TENANT_RECOMMENDATION_OWNERSHIP':'PASS','BORROWING_INFORMATION_INTENT':'PASS','UNREQUESTED_LOAN_MUTATION':'NO','CIRCULATION_AUTHORIZATION':'PASS','DIGITAL_AVAILABILITY':'PASS','PRIVATE_B_RAG':'UNRESOLVED','PROTECTED_RAG_CHANGED':'NO','REAL_QWEN_TESTS':'16 authorized chat workflows plus2 authorized private RAG workflows;3 additional browser workflows.5 initial fixture authorization denials retained. Browser explicit follow-up partial; PrivateB abstains.','BROWSER_QA':'PARTIAL','BACKEND_TESTS':counts,'FRONTEND_TESTS':front,'BUILD':'PASS','LINT':'PASS','NEW_REGRESSIONS':0,'GLOBAL_HNSW_REBUILT':'NO','GLOBAL_KG_REBUILT':'NO','PRODUCTION_AUTH_CHANGED':'NO','PRODUCTION_TELEMETRY_ENABLED':'NO','DEPLOYED':'NO','COMMITTED':'NO'}
 write('qa',qa)
 entries=[
 ('A. Final result','PARTIAL. Narrow reliability and information-intent repairs verified; remaining limits below.'),
 ('B. Checkpoint','3124/0/20 backend;1030/0/0 frontend. Existing dirty work retained; checkpoint and before snapshots recorded.'),
 ('C. Recommendation503 cause','Confirmed source defect: canonical read_context called the unlocked membership guard before its30-second library_mutation wait. A competing ordinary read holds the same gate, so require_readable immediately returned503. Reproduced with a real disposable Mongo lock and actual endpoint. Historical A/B responses lack bodies: cannot attribute every historical503 solely to this cause. Reload502 was separately ECONNREFUSED.'),
 ('D. Exact recommendation repair','For canonical reads, acquire the existing bounded durable authority gate before checking membership. Perform the original guard before canonical maintenance, then repeat original access_locked and final guard. Legacy reads retain original guards. No lock takeover, timeout increase, ranking, candidate mapping, eligibility or recovery-policy change.'),
 ('E. Concurrency/retry','Short lock wait succeeds; revocation during wait404;8 overlapping A/B requests all succeed with own books. Old parallel-client scenario now succeeds too. Existing frontend idempotent-read retry budget retained; controlled browser503 exhausted3 attempts, then one explicit manual retry recovered. No Qwen retry added.'),
 ('F. Tenant ownership','Canonical intersection and recent-local supplementation unchanged. Browser B84/84local book links; stale A HTTP200 canceled on switch. No foreign Global filler.'),
 ('G. Informational borrowing cause','Qwen BORROW_BOOK/RESERVE_BOOK classification could reach propose without a separate user-request modality check.'),
 ('H. Borrowing repair','Narrow interrogative/negative borrowing boundary converts model action labels to physical availability while preserving canonical reference resolution. Eligibility/loan-period questions conservatively clarify rather than invent policy. Explicit requests/actions and confirmation path remain. Digital questions still use Q3 authoritative digital lookup.'),
 ('I. Circulation authority','Actual authority, roles, restrictions and confirmation code unchanged. Owned fixture has0loans and0lending_requests after live checks. No confirmation clicked.'),
 ('J. Digital preservation','All existing digital tests included; real A/B authorized PDF and Global/I UNKNOWN correct. Browser B PDF question after borrowing remains authorized with canonical local link and no physical badge.'),
 ('K. PrivateB RAG','Actual A and B intents have actorunknown/actionrecord/targetcalibration code. Authorized extraction/retrieval/selection preserve each synthetic fact. A supports; B validator returns NOT_SUPPORTED. No source-supported unprotected adapter defect established. Remains unresolved; no tuning loop or source patch.'),
 ('L. Protected source','rag/llm.py and rag/qa.py hashes unchanged; both rejected validator candidates remain unapplied. Frozen guards/manifests untouched.'),
 ('M. Security','Live security cases and complete security/tenant/native/protected suites retained. Revocation while lock waits rechecks authority and denies404; browser revoked A and foreign B resources concealed.'),
 ('N. Real Qwen',qa['REAL_QWEN_TESTS']+' Controlled parser fixtures, deterministic API contention and browser transport injection are separate evidence.'),
 ('O. Browser','Global/A/B ForYou, controlled failure/manual recovery, A->B cancellation, local detail, information question, explicit request, digital question, revoked/foreign denials recorded. Exact mobile viewport unavailable;487px observed. Native Tab reaches Skip control. Explicit follow-up clarified instead of proposing; browser remains partial.'),
 ('P. Backend',str(counts)+' across38groups.9new tests; no newly introduced automated failures. Initial obsolete test failure retained; both original paths and unchanged-data snapshots now require successful responses.'),
 ('Q. Frontend',str(front)+';1new recovery test. Preliminary failed runs retained; final run passes.'),
 ('R. Build/lint',f'Both exit0;{warnings}warnings, same16baseline.'),
 ('S. Preservation','Live/global/index/source comparison result: '+preservation['result']+'. Overall evidence preservation PARTIAL: accidental Q3runner invocation overwrote Q3frontend.log; original bytes unavailable. Historical JSON counts and original hash manifest retained; damage explicitly recorded. No production auth/telemetry, existing index rebuild, deployment, commit or rollback. Only owned lab removed.'),
 ('T. Exact files','changed_files.json lists7source/test files with before/after hashes. Patch SHA256 '+sha(target)+'. Supporting files enumerated in artifact_manifest.json.'),
 ('U. Remaining product defects','PrivateB false negative; explicit borrowing conversational reference clarification; policy eligibility remains conservative unknown. No claim every historical503was explained or every possible borrowing wording classified.'),
 ('V. Research limits','Synthetic task-owned data, controlled Global candidates; no5M relevance benchmark, independent reviewer labels or new subjective evaluation. No new validator prompt experiment.'),
 ('W. Next scope','Separately diagnose explicit local-record follow-up resolution and actual validator entity/evidence interaction under protected approval policy. Stop at Part2Q.4; noPart2R begun.')]
 body='# LuminaR Part 2Q.4 completion\n\n'+ '\n\n'.join('**'+k+'**\n\n'+v for k,v in entries)+'\n\nFinal QA: institution_v2q4_qa.json. Errors, initial failures and limited coverage remain in raw evidence.\n'
 (P/'institution_v2q4_completion.md').write_text(body,encoding='utf8')
 files=sorted(set(list(R.glob('scripts/institution_v2q4*'))+list(P.glob('institution_v2q4*'))+list(P.glob('institution_v2q_2q4_*'))+[R/n for n in paths]+[p for p in (R/'.scratch/institution-v2q/q4-before').rglob('*') if p.is_file()]))
 write('artifact_manifest',{'files':[{'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in files if p.is_file() and p.name!='institution_v2q4_artifact_manifest.json'],'self_hash':None})
 print(json.dumps({'qa':qa,'prior_artifact_changes':old_errors,'patch_sha256':sha(target)}))

if __name__=='__main__':main()
