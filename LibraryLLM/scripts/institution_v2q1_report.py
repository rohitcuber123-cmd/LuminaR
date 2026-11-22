"""Assemble an honest, partial Part 2Q.1 report from recorded observations."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, re

ROOT=Path(__file__).resolve().parents[1];REPORTS=ROOT/'reports'
def read(name):return json.loads((REPORTS/name).read_text(encoding='utf8'))
def write(name,value):(REPORTS/name).write_text(json.dumps(value,indent=2,default=str),encoding='utf8')

def main():
    baseline=read('institution_v2q1_baseline.json')
    cases=read('institution_v2q1_live_browser_observations.json')
    rag=read('institution_v2q1_public_rag_results.json')
    perf=read('institution_v2q1_performance.json')
    comparison=read('institution_v2q1_before_after.json')
    capacity=read('institution_v2q1_capacity.json')
    resumed=read('institution_v2q1_resumed_summary.json')
    resumed_cases=read('institution_v2q1_resumed_browser.json')['cases']
    resources=read('institution_v2q1_resumed_resources.json')
    preservation=read('institution_v2q1_preservation.json')
    groups=read('institution_v2q_2q1_closure_backend.json')
    backend={k:sum(g.get(k,0) for g in groups) for k in ['passed','failed','skipped']}
    backend_complete=len(groups)==38 and groups[-1]['group']=='events'
    frontend_checks=read('institution_v2q_2q1_final_frontend.json')
    log=(REPORTS/'institution_v2q_2q1_final_frontend.log').read_text(encoding='utf8')
    frontend={key:sum(map(int,re.findall(r'\u2139 '+label+r' (\d+)',log))) for key,label in [('passed','pass'),('failed','fail'),('skipped','skipped')]}
    lint_warnings=[line for line in (REPORTS/'institution_v2q_2q1_final_lint.log').read_text(encoding='utf8').splitlines() if ': warning ' in line]
    prior_warnings=[line for line in (REPORTS/'institution_v2q_ai_release_lint.log').read_text(encoding='utf8').splitlines() if ': warning ' in line]
    same_warnings=sorted(lint_warnings)==sorted(prior_warnings)
    qa={'PART_2Q1_RESULT':'PARTIAL','REAL_QWEN_EXECUTED':'YES','REAL_MINILM_EXECUTED':'YES, public RAG',
        'REAL_FAISS_SEARCH':'YES, public 3,959-vector RAG index; global HNSW execution not verified',
        'GLOBAL_RETRIEVAL_QUALITY':'PARTIAL','TENANT_RETRIEVAL_QUALITY':'PARTIAL',
        'INTENT_QUALITY':'PARTIAL','RELEVANCE_JUDGMENTS':'PROVISIONAL',
        'GLOBAL_CHATBOT_PRESERVED':'NO: observed follow-up failure','PRIVATE_CHATBOT_PRESERVED':'NO: private-library live coverage incomplete',
        'PRIVATE_SELECT_FOR_YOU':'PARTIAL','SMALL_LIBRARY_RECOMMENDATIONS':'PARTIAL',
        'LOCAL_ONLY_BOOKS':'PASS in isolated tests and one live public local-only seed case; no generalized relevance claim',
        'SIMILAR_BOOK_QUALITY':'PARTIAL','FOLLOW_UP_CONTEXT':'FAIL in Global and resumed public isolation-library cases',
        'HALLUCINATION_EVALUATION':'PARTIAL','TENANT_OWNERSHIP_CORRECTNESS':'100% of 50 resumed returned book instances matched active records in the selected public library; 49/50 had holdings. Prior direct Search sample separately matched 20/20 holdings.',
        'UNAUTHORIZED_PRIVATE_DATA_LEAKS':'0 observed in one cross-scope UI case; not a complete security audit',
        'QWEN_LATENCY':'Separate public RAG samples: initial n=4 median 20.827s; extended n=5 range 15.837–20.860s; restarted n=21 median 17.338s, range 11.861–24.003s. Do not pool runs or infer a production SLO.',
        'SEARCH_LATENCY':'Global Search: one query, three duplicate UI requests 1569.508–1626.913 ms. Tenant Search: one query 854.362 ms, TENANT_SEMANTIC/READY. RAG FAISS stage 0.63–1.23 ms, n=4. No p95 estimate.',
        'QUALITY_FIXES_IMPLEMENTED':1,'QUALITY_IMPROVEMENT_SUPPORTED':'YES for the narrow hydration defect: same-fixture controlled comparison plus successful live recommendations/Search after the user restarted services. Other quality defects remain.',
        'BACKEND_TESTS':{**backend,'complete':backend_complete},'FRONTEND_TESTS':frontend,
        'REAL_BROWSER_QA':'PARTIAL: actual browser; functional failures observed',
        'PRODUCTION_BUILD':'PASS' if next(x for x in frontend_checks if x['check']=='build')['exit']==0 else 'FAIL',
        'LINT':'PASS' if next(x for x in frontend_checks if x['check']=='lint')['exit']==0 else 'FAIL',
        'LINT_WARNINGS':len(lint_warnings),'LINT_WARNINGS_MATCH_PRIOR':same_warnings,
        'NEW_BACKEND_REGRESSIONS':backend['failed'],'NEW_FRONTEND_REGRESSIONS':frontend['failed'],
        'GLOBAL_HNSW_REBUILT':'NO','GLOBAL_KG_REBUILT':'NO','TENANT_AUTO_REBUILD':'NO',
        'PROTECTED_RAG_CHANGED':'NO' if preservation['checks']['rag_qa'] else 'YES',
        'PRODUCTION_AUTH_CHANGED':'NO','PRODUCTION_TELEMETRY_ENABLED':'NO','DEPLOYED':'NO','COMMITTED':'NO',
        'NEXT_RECOMMENDED_SCOPE':'Complete Part 2Q.1: diagnose tenant 503 and parsed reference scope with authorized, non-sensitive diagnostics; repeat real-model quality and security evaluation.'}
    write('institution_v2q1_regression.json',{'backend_groups':groups,'backend_totals':backend,'backend_complete':backend_complete,
        'before_fix_backend_groups':read('institution_v2q_2q1_live_backend.json'),
        'interrupted_postfix_attempt':read('institution_v2q_2q1_postfix_backend.json'),
        'interrupted_attempt_qualification':'Incomplete process-interrupted attempt, including launch errors; preserved and superseded by the separately named closure run, never counted as a successful full run.',
        'frontend_checks':frontend_checks,'frontend_totals':frontend,'historical_baseline':baseline['historical_2q_tests']})
    notes=[
      ('A. Final result','PARTIAL. Real services were exercised and real functional failures were observed; the requested comprehensive quality and security evaluation remains incomplete.'),
      ('B. Executive summary','Four public RAG requests executed real Qwen, MiniLM and FAISS. Actual signed-in browser probes exercised Global and authorized public tenant contexts. One narrow tenant-read concurrency fix was implemented and validated on controlled Core fixtures.'),
      ('C. Current baseline','The Part 2Q source freeze matched at the Part 2Q.1 checkpoint. Historical Part 2Q tests were 3050/0/20 backend and 1028/0/0 frontend; they are not substituted for current results.'),
      ('D. Qwen configuration','Qwen/Qwen2.5-3B-Instruct, resident service reports cuda:0. Source uses local-only loading, 4-bit NF4 and double quantization on CUDA; model configuration in local cache has 32768 maximum positions. Cached revision is recorded in baseline; active loaded revision was not independently proven. Generation is deterministic; temperature/top-p arguments are unused with sampling disabled.'),
      ('E. MiniLM and FAISS','The RAG retriever uses all-MiniLM-L6-v2 and real FAISS; RAG health reports 3959 vectors. The separate Global Search health reports 5000000 active vectors, STALE and baseline_verified false. Source specifies 384 dimensions, HNSW efSearch 128 and rerank depth 50. No Global HNSW execution trace was captured.'),
      ('F. Evaluation dataset','A reproducible inventory of 160 queries exists, covering the requested broad categories. It was built after exploratory probes and is not held out; only recorded live probes were executed.'),
      ('G. Relevance judgments','All labels are provisional or unjudged; no independent human review and no exhaustive Global relevance set. Precision, recall, MRR and nDCG are not validly estimated from this sample.'),
      ('H. Global Search quality','One operating-systems query returned ten titles appearing topically related; one author query returned ten records whose displayed author matched Bram Stoker. These are provisional observations, not validated retrieval metrics. Native Global FAISS use was not traced.'),
      ('I. Tenant Search quality','A networking query returned HTTP 503 in two public test libraries. Tenant Search relevance and native-index versus fallback quality were not measured.'),
      ('J. Private-library Search','Not measured with a disposable private library in this run. Previous Part 2Q deterministic evidence remains historical.'),
      ('K. Global versus tenant','Not a controlled comparable benchmark: Global returned results for selected queries; scoped requests produced service errors. Data, judgments and executed query coverage differ.'),
      ('L. Intent interpretation','Beginner Python query requested a reference clarification; exact tenant workbook title was routed to a document-access prompt. Database recommendation was routed to personalized recommendations. Parsed model decisions were not exposed, so exact attribution remains open.'),
      ('M. Live Qwen responses','Four public RAG requests ran the resident Qwen service. Browser natural-language probes ran through the existing assistant; their per-request model calls were not independently traced. Raw public RAG output and sanitized UI observations are in separate JSON artifacts.'),
      ('N. Follow-ups','In two fresh Global conversations, “Is the second one available?” after ten search results returned an out-of-range clarification. The browser sent the conversation ID and ten recent IDs. After switching to TEST, an equivalent follow-up returned clarification and no books; this is one isolation observation, not a complete audit.'),
      ('O. Select For You','The TEST library page displayed tenant recommendations and canonical links. An isolation-library assistant quick-action recommendation returned HTTP 503. Live private/small-library recommendation quality remains unmeasured.'),
      ('P. Similar books','Not measured with sufficient evidence. No claim of recommendation similarity quality is made.'),
      ('Q. Local-only and acquisitions','Task-owned Part 2Q.1 scope tests and the full backend inventory cover local-only paths deterministically. The same-fixture concurrency comparison uses 12 local books. Live quality for these cases remains incomplete.'),
      ('R. Availability','The Global result cards displayed copy counts, but independent holdings verification was not performed. The requested Global follow-up failed to bind the second result. Tenant availability was not measured in the 503 cases.'),
      ('S. Grounding and hallucinations','Four public RAG probes: the unrelated machine-learning question abstained but returned SUPPORTED; the smartphone question abstained with NOT_SUPPORTED. Two book questions returned answers and sources, without independent citation verification. This is not a hallucination-rate estimate.'),
      ('T. Knowledge Graph','Live KG relevance was not evaluated. TEST metadata reports a READY published target. Existing protocol and security test groups are included in regression evidence; no graph was built.'),
      ('U. Private RAG authorization','No new live private-document retrieval or foreign-asset trial was completed. Existing regression groups and historical Part 2Q isolated tests provide limited boundary evidence; no new private content was exported.'),
      ('V. Performance and resources',f"Public RAG endpoint samples (n={perf['sample_size']}) have median {perf['median_ms']/1000:.3f}s and range {perf['min_ms']/1000:.3f}–{perf['max_ms']/1000:.3f}s. Each used two or three model calls. A separate 50-candidate controlled Core fixture completed in {capacity['elapsed_ms']:.2f} ms; no Qwen was used. Stage-level embedding and FAISS times are in performance JSON. p95 and production SLOs are not inferred. A shared GPU/system snapshot is in resource_sample JSON."),
      ('W. Identified defects','Global ordinal follow-up failed twice despite ten recent IDs being sent. Scoped topic and structured recommendation calls returned 503 across two libraries. A canonical-library controlled fixture reproduced the 503 with concurrent book reads. A topical recommendation returned ten results with no literal “database” in title/subjects. Public RAG returned SUPPORTED alongside an abstaining answer. Exact parsed model fields and the live 503 upstream status remain unobserved.'),
      ('X. Controlled fixes','Serialized book hydration within each scoped assistant request, retaining per-book Core authorization and the overall timeout. This avoids self-contention on canonical-library locks and prevents a set of sibling lookups from continuing after the first failed lookup. The existing running service retains previously loaded code; no restart or deployment was performed. Other simultaneous clients can still contend and fail closed.'),
      ('Y. Before/after',f"A single disposable canonical library, same 12 book IDs and matching book, holdings and copy collection hashes, same structured action and deterministic fixture providers: prior parallel hydration returned HTTP {comparison['before_http_status']} in {comparison['before_ms']:.2f} ms with concurrent Core 503s; serialized hydration returned HTTP {comparison['after_http_status']} and ten tenant-owned books in {comparison['after_ms']:.2f} ms, with all twelve Core reads successful. A failing request and a successful request are not comparable success-latency measurements. See same_fixture_final.log and the comparison JSON. This is controlled Core evidence, not a live Qwen or production before/after measurement. The recommendation query omission and reference-scope issues remain unresolved."),
      ('Z. Security negatives','One actual Global-to-TEST switch cleared the old transcript and returned no book for an ordinal follow-up. This is not sufficient to establish tenant ownership or zero leakage generally. Isolated scope and prior accepted security tests supply additional bounded evidence.'),
      ('AA. Browser QA','PARTIAL. Real signed-in in-app browser exercised Global and public TEST/isolation-library flows, and failures were observed. It did not cover the full requested mobile, private asset, revocation or tenant matrix in this phase.'),
      ('AB. Backend regression',f"Current run: {backend['passed']} passed / {backend['failed']} failed / {backend['skipped']} skipped; complete={backend_complete}, {len(groups)} groups."),
      ('AC. Frontend regression',f"Current run: {frontend['passed']} passed / {frontend['failed']} failed / {frontend['skipped']} skipped. See frontend log for all raw results."),
      ('AD. Build and lint',f"Production build: {qa['PRODUCTION_BUILD']}; lint: {qa['LINT']}, {len(lint_warnings)} warnings, prior-warning multiset match={same_warnings}. Raw output, including the build chunk-size warning, is retained."),
      ('AE. Preservation',f"Post-observation comparison: {preservation['result']}. See preservation JSON for each check and any concurrent-state drift. No action intentionally rebuilt an index, activated auth/telemetry, committed or deployed."),
      ('AF. Changed files','One scoped assistant adapter was changed, one integration test was added, and task-scoped evaluation scripts and reports were created. Exact file hashes and source-freeze comparison are in changed_files JSON. Existing uncommitted application work is preserved.'),
      ('AG. Limitations','Small non-independent sample; public RAG and Global Search indexes are distinct; no trace proves Global FAISS execution. No complete tenant relevance labels, private-document quality evaluation or full browser/security scenario matrix. Live services and regression overlap may distort timings; available system RAM was low.'),
      ('AH. Acceptance','PARTIAL. Actual model and RAG retrieval ran, but quality defects remain and multiple required metrics and scenarios are not measured. No PASS is asserted from fixture tests.'),
      ('AI. Next scope','Continue Part 2Q.1 only: inspect sanitized upstream errors and parsed reference decisions without changing security; reproduce on controlled disposable data; validate any narrow repair before and after; complete remaining real-model, tenant and security measurements.')]
    revised={
        'B':'Thirty evaluated public RAG requests executed the resident Qwen, MiniLM and FAISS across three separately recorded runs. Signed-in browser probes exercised Global and authorized public tenant contexts. One scoped hydration concurrency defect was repaired, tested on identical controlled Core data, and revalidated live after the user restarted services. Grounding and reference failures remain.',
        'F':'A reproducible inventory of 160 unjudged queries exists; it does not imply 160 executions. Initial exploratory probes preceded that inventory. The new 21-query public RAG sample was declared before execution, and remains separate from the earlier four- and five-query runs. This is not a comprehensive held-out assistant evaluation.',
        'H':'Selected Global assistant queries returned apparently topical results, with provisional author matching for Bram Stoker. A history-free, non-personalized direct Global Search query returned ten machine-learning titles from 50 ranked candidates. Three duplicate UI requests took 1569.508–1626.913 ms. No independent relevance judgments or native Global execution trace were obtained.',
        'I':'Direct TEST Search succeeded with TENANT_SEMANTIC, READY and LIBRARY_LOCAL/CANONICAL: 20 results in 854.362 ms, all independently matched canonical holdings. After the user restart, the previously failing networking requests returned HTTP 200, no assistant errors and ten results in both TEST and public isolation A. Five resumed result sets contained 50/50 active books in their selected library; 49/50 had holdings. The CN recommendation had no holdings and displayed Availability unknown. Relevance remains provisional.',
        'K':'Direct Search and resumed assistant discovery succeeded in both public tenant scopes. Global and tenant corpora, queries and judgments differ; no comparable relevance benchmark or private-library quality percentage is claimed.',
        'M':'Thirty public RAG cases have raw responses and model/retrieval profiles: initial n=4, extended n=5 and restarted n=21. All 21 restarted cases recorded two or three model calls and positive FAISS stage timing. Natural-language browser assistant requests ran against resident services, but their upstream parsed model fields/calls were not independently traced. Structured actions are explicitly marked as using no Qwen.',
        'N':'The Global ordinal failure was observed twice before restart. The resumed public isolation A conversation reproduced it: after ten Search results, Is the second one available? returned That position is not in the current book list. The follow-up carried all ten recent IDs and matched the previous response conversation ID. A pure-function diagnostic binds SECOND correctly for RECENT_RESULTS/NONE, while empty SELECTED_BOOKS/CURRENT_PAGE_BOOK scopes reproduce the error. The actual parsed scope remains unknown, so no scope fallback or authorization rule was changed.',
        'O':'The public TEST Recommend action returned HTTP 200, no errors and ten scoped books after restart. The earlier isolation-library 503 is preserved as historical live evidence. Private Select For You and independently judged small-library recommendation quality remain incomplete.',
        'P':'One live local-only workbook seed, independently confirmed to have no global work ID, returned ten scoped recommendations with the seed excluded. Computing, business-network and mathematics topics were mixed. This validates the local-only path, not similarity precision or ranking quality; no independent relevance labels are available.',
        'Q':'The completed regression covers local-only paths and the new concurrency repair on disposable data. Live RECOMMEND_SIMILAR also succeeded for the public TEST workbook with global_work_id null. No global mapping was invented and no acquisitions or catalogue mutations were performed.',
        'R':'The resumed AVAILABLE_NOW action returned ten books with positive available-copy counts; all ten had canonical holdings. It is a collection-level discovery action, not a selected-book availability question. The local workbook detail displayed one total and one requestable copy. Independent quantity reconciliation was not completed, and ordinal availability still failed. The CN recommendation correctly displayed unknown availability when no holdings existed.',
        'S':'All 30 public RAG outputs remain provisional. RAG001 and resumed RAG013 produced abstaining answers with SUPPORTED verdicts. RAG027 returned Page 15 with SUPPORTED although every returned source page and all four matched public chunk page values were null; this is an unsupported pagination claim in the source audit. RAG019 may conflate first-journey events with epilogue speculation and needs independent adjudication. No hallucination-rate or citation-accuracy percentage is inferred.',
        'U':'No live private-document retrieval, revocation or foreign-asset matrix was completed. Public RAG030 abstained on a request for another member’s private documents, but this unauthenticated public-corpus probe is not a private asset authorization test. Existing regression groups retain bounded security evidence; no private document content was exported.',
        'V':f"Separate public RAG timing runs: initial n=4 median 20.827s, extended n=5 range 15.837–20.860s, restarted n=21 median {resumed['timing']['median_seconds']:.3f}s and range {resumed['timing']['min_seconds']:.3f}–{resumed['timing']['max_seconds']:.3f}s. Restarted FAISS stages ranged 0.42–36.67 ms. Do not pool runs or infer a production p95/SLO. Resumed assistant networking took 5.377s in isolation A and 11.883s in TEST; structured actions took 10.087–13.366s. Early structured probes overlapped public RAG work. The 50-candidate controlled Core fixture took {capacity['elapsed_ms']:.2f} ms without Qwen.",
        'W':'The tenant 503 was reproduced on controlled canonical Core reads and no longer occurred in the resumed public probes. Remaining observed defects include ordinal binding in Global and isolation A, topical recommendation mismatch, verdict/abstention mismatch and unsupported pagination. Exact parsed decisions remain unavailable; no speculative change to model scope semantics or protected RAG was made.',
        'X':'Serialized per-request scoped book hydration, retaining each Core authorization check, input order and the existing overall timeout. Controlled evidence confirms avoidance of self-contention on canonical-library locks and absence of later sibling requests after failure. The user restarted the services; the agent did not restart, deploy or change the model. Subsequent real scoped requests succeeded. Independent clients can still contend and must continue to fail closed.',
        'Y':f"Same disposable canonical library, same 12 book IDs and unchanged collection hashes: original parallel hydration returned {comparison['before_http_status']}; serialized hydration returned {comparison['after_http_status']}, ten scoped books and twelve successful Core reads. The prior error and successful request are not comparable success-latency measurements. After the user restart, the same networking input that previously returned 503 succeeded in both existing public libraries, and structured TEST recommendations also succeeded. The final preservation check confirms unchanged tenant data. This supports the narrow repair; it does not establish generalized model or relevance improvement.",
        'Z':'Live tenant switches cleared selected-book and transcript state before new scoped requests. Fifty resumed returned book instances matched active records in their selected public library; there were zero observed cross-tenant book instances in those results. Public instruction probes RAG028/029 abstained and RAG030 returned no private content. These bounded cases do not establish private-library or foreign-asset security generally; deterministic authorization/mutation suites supply separate evidence.',
        'AA':'PARTIAL. The real signed-in browser exercised earlier Global/public tenant flows plus six resumed cases. Recommendations, available-only discovery, local-only similarity and networking succeeded; ordinal context failed. Full mobile, private asset, revocation and tenant security matrices remain incomplete. Sanitized browser observations are retained without credentials or account identifiers.',
        'AB':f"Current application tree: {backend['passed']} passed / {backend['failed']} failed / {backend['skipped']} skipped across {len(groups)} completed groups. The interrupted earlier attempt and its launch errors remain preserved. No additional application source changed during resumed evaluation, so the executed closure run still covers the current source tree.",
        'AE':f"Final resumed preservation comparison: {preservation['result']}. All 553 frozen source files match except the intended scoped adapter change, and all 594 prior reports match. Tenant records, private logical state, Mongo indexes, communications, global/tenant artifacts and HEAD match the saved checkpoint. Large global artifact checks use size/mtime, as recorded in preservation limits. No rebuild, auth/telemetry activation, commit or deployment was performed.",
        'AG':'Thirty public RAG queries are not representative Global/tenant assistant quality coverage. The 160-row query inventory remains unjudged and mostly unexecuted. Global native HNSW execution, live private-library quality, independent relevance judgments and the complete browser/security matrix remain unverified. Raw response metadata cannot establish factual accuracy. Two structured browser timestamps were not retained across navigation; their elapsed times were captured before navigation. Three timing runs must not be pooled. Services were initially unavailable, then the user restarted them and signed in; the old checkpoint/report is preserved separately.',
        'AH':'PARTIAL. Complete backend/frontend checks, build, lint and preservation pass, and the narrow tenant repair has both controlled and live support. Observed grounding/reference failures, unjudged relevance and incomplete private-library coverage prevent overall PASS.',
        'AI':'Continue Part 2Q.1 only: inspect actual parsed reference decisions using authorized non-production diagnostics; complete independent relevance and live private-library/asset evaluation; propose a separately reviewed protected-RAG repair for observed grounding defects. Do not alter the protected implementation or weaken scope binding automatically.'}
    notes=[(title,revised.get(title.split('.')[0],body)) for title,body in notes]
    notes=[(title,body+(f" Post-probe resource snapshot: {resources['available_ram_mib']} MiB RAM available of {resources['total_ram_mib']} MiB; GPU CSV (name,total MiB,used MiB,utilization percent): {resources['gpu']}. This is not a peak or per-request measurement." if title.startswith('V.') else '')+(' See institution_v2q1_grounding_followup_proposal.md; it applies no source changes.' if title.startswith('AI.') else '')) for title,body in notes]
    qa['REAL_MINILM_EXECUTED']='YES, public RAG; tenant semantic path observed'
    qa['LIVE_PUBLIC_RAG_QUERIES']=len(rag['queries'])+len(read('institution_v2q1_public_rag_extended.json')['queries'])+resumed['successful']
    qa['SERVICE_AVAILABILITY_BEFORE_USER_RESTART']=read('institution_v2q1_resume_services.json')
    qa['SERVICE_HEALTH_AFTER_USER_RESTART']=resumed['health']
    qa['RESUMED_BROWSER_CASES']=resumed_cases
    qa['RESUMED_OWNERSHIP_CHECKS']=resumed['ownership']
    qa['GROUNDING_FINDINGS']=resumed['grounding_findings']
    qa['LIVE_SEARCH_EVIDENCE']={'global':read('institution_v2q1_global_search_probe.json'),'tenant':read('institution_v2q1_tenant_search_probe.json')}
    qa['NEXT_RECOMMENDED_SCOPE']=revised['AI']
    normalized={'REAL_MINILM_EXECUTED':'YES','REAL_FAISS_SEARCH':'YES',
        'GLOBAL_CHATBOT_PRESERVED':'NO','PRIVATE_CHATBOT_PRESERVED':'NO',
        'LOCAL_ONLY_BOOKS':'PASS','QUALITY_IMPROVEMENT_SUPPORTED':'YES',
        'FOLLOW_UP_CONTEXT':'FAIL','REAL_BROWSER_QA':'PARTIAL',
        'TENANT_OWNERSHIP_CORRECTNESS':100.0,'UNAUTHORIZED_PRIVATE_DATA_LEAKS':0}
    qa['EVIDENCE_QUALIFICATIONS']={key:qa[key] for key in normalized}
    qa.update(normalized)
    write('institution_v2q1_final_qa.json',qa)
    (REPORTS/'institution_v2q1_completion.md').write_text('# LuminaR Part 2Q.1 — observed results\n\n'+'\n\n'.join('## '+title+'\n\n'+body for title,body in notes)+'\n',encoding='utf8')
    paths=[p for p in (ROOT/'scripts').glob('institution_v2q1_*.py')]+[ROOT/'tests/institution_v2q_ai/test_v2q1_parallel_core.py']+[p for p in REPORTS.glob('institution_v2q1_*') if p.is_file() and p.name!='institution_v2q1_changed_files.json']
    paths += [p for p in REPORTS.glob('institution_v2q_2q1_*') if p.is_file()]
    freeze=read('institution_v2q_ai_final_source_freeze.json');adapter=ROOT/'assistant/library_scope.py'
    write('institution_v2q1_changed_files.json',{'project_root':str(ROOT),'application_source_changes':{'assistant/library_scope.py':{'before_sha256':freeze['assistant/library_scope.py'],'after_sha256':hashlib.sha256(adapter.read_bytes()).hexdigest()}},
        'source_freeze_drift_at_baseline':baseline['drift_from_2q_source_freeze'],
        'task_artifacts':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}})
    print(json.dumps(qa,indent=2))

if __name__=='__main__':main()
