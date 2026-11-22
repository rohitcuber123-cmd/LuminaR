"""Extend the existing evaluation: exact failures, source review, judge-ready rows."""
from pathlib import Path
from datetime import datetime,timezone
from statistics import median
import hashlib,json
from pymongo import MongoClient
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'reports'
def read(name):return json.loads((OUT/name).read_text(encoding='utf8'))
def save(name,payload):(OUT/name).write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding='utf8')

def main():
    old=read('institution_v2q1_resumed_browser.json')['cases']
    matrix=[]
    def row(identifier,input,scope,output,invariant,evidence,suspected,proven,repair,security,safe,execution='NOT_INDEPENDENTLY_TRACED'):
        matrix.append({'id':identifier,'input':input,'effective_library':scope,'conversation_scope':scope,
            'actual_model_tool_execution':execution,'actual_output':output,'expected_invariant':invariant,
            'evidence':evidence,'suspected_cause':suspected,'proven_cause':proven,'possible_repair':repair,
            'security_impact':security,'safe_unprotected_repair':safe})
    row('F01','Is the second one available?','public isolation A; historical Global also failed',old[4]['message'],
        'Bind the second item in the actual intended valid context, then read current holdings.',
        ['institution_v2q1_resumed_browser.json:RESUME_UI004/005'],'Empty selected/page scope or lost server context',
        'Same conversation and ten recent IDs were supplied; actual parsed scope still unknown.',
        'Trace raw enum fields and validated decision in the isolated one-Qwen lab before changing anything.',
        'No arbitrary cross-scope fallback is safe.','CONDITIONAL_ON_TRACE')
    row('F02','Ordinal/selected/page references','Global and scoped conversations','Scope choice not captured in prior runs',
        'Selected, page, recent, literal IDs, explicit titles and document scopes remain distinct.',
        ['institution_v2q1_resumed_summary.json:reference_diagnostic'],'Selected-pair prompt example may bias an empty-scope choice',
        'Controlled RECENT_RESULTS/NONE binds SECOND; empty SELECTED_BOOKS/PAGE gives the observed error. This is not the actual model decision.',
        'A prompt/context repair may be appropriate after real decision tracing; retain scope validation.',
        'Blindly replacing an explicit valid scope can disclose unrelated records.','UNKNOWN',execution='DETERMINISTIC_FIXTURE only for counterfactual binding')
    row('F03','Give the exact page number of the first mention of Jonathan Harker.','public RAG corpus','Page 15; SUPPORTED; four null source pages',
        'Do not present exact page attribution without trustworthy page evidence.',
        ['institution_v2q1_public_rag_resumed.json:RAG027','institution_v2q1c_citation_before.log','institution_v2q1c_citation_final.log'],
        'Question intent lost pagination focus; evidence validator accepted character relevance.',
        'All four matched public chunks have null pages; context headers include page only when metadata exists; the number appears in generation, not citation formatting.',
        'Applied numeric-page validation at unprotected API and authorized library-asset response boundaries.',
        'Only downgrades unsupported output; leaves ownership, source selection and protected generation intact.','APPLIED_AND_TARGETED_TESTED',execution='REAL_MODEL_REAL_RETRIEVAL; adapter replay is DETERMINISTIC_FIXTURE')
    row('F04','Machine-learning evidence / Dracula mirrors','public RAG corpus','Abstaining answers with SUPPORTED evidence verdicts',
        'Define whether a label grades retrieved evidence or final generated claims before declaring contradiction.',
        ['institution_v2q1_public_rag_results.json:RAG001','institution_v2q1_public_rag_resumed.json:RAG013'],
        'Evidence validator false positives or final generation declining despite relevant evidence',
        'verdict is assigned before answer generation. Both cases used LLM evidence validation, not FAST_ACCEPT.',
        'Review evidence/validator decisions separately; do not flip all abstention verdicts by text matching.',
        'A broad rewrite can destroy legitimate evidence semantics and valid grounded responses.','NO_GENERIC_REWRITE_JUSTIFIED',execution='REAL_MODEL_REAL_RETRIEVAL')
    row('F05','Recommend similar books to the local-only network workbook','public TEST','Computing/business networks/mathematics mix',
        'Scoped ownership is mandatory; relevance requires judged evidence.',
        ['institution_v2q1_resumed_browser.json:RESUME_UI003'],'Broad subject tags, semantic candidates, reranking or fallback',
        'Seed has no global ID; code routes this branch to subject-based local Search. The actual native/fallback provider was not recorded.',
        'Collect scored metadata and independent judgments before considering ranking changes.',
        'Never fill a private recommendation with unowned global books.','NOT_BEFORE_JUDGMENT',execution='CONTROLLED_MODEL_REAL_RETRIEVAL; no Qwen on structured action')
    row('F06','Private-library discovery and Select For You','private A/B','Not executed live in earlier work',
        'Use real JWT, current membership, local IDs and holdings on task-owned private libraries.',
        ['institution_v2q1_completion.md:J/O/U'],'Missing controlled runtime environment','Missing evidence, not a proven implementation defect.',
        'Prepared isolated three-library/six-user fixture and actual authenticated Core smoke.',
        'Never probe real member records or infer private authorization from public abstention.','EVALUATION_REQUIRED',execution='Historical deterministic tests; new no-model authenticated smoke')
    row('F07','Stratified relevance sample','Global/public TEST','160 inventory rows unjudged, not 160 executions',
        'Do not invent ground truth or precision/recall/MRR/nDCG.',
        ['institution_v2q1_query_inventory.json','institution_v2q1_global_search_probe.json'],'No independent reviewer labels',
        'No independent labels exist in the recorded artifacts.',
        'Prepare query/rank/ID/metadata/rationale review rows; leave human grades unassigned.',
        'Use only public metadata and disposable fixtures; no private history export.','REPORTING_ONLY',execution='Actual result sets, unjudged')
    row('F08','Foreign/revoked private-asset requests','disposable private A/B','Live private-asset matrix previously missing',
        'Authorization precedes private retrieval/model context and is rechecked.',
        ['institution_v2q1_completion.md:U/Z'],'Missing controlled live matrix','Public RAG030 abstention is not private authorization evidence.',
        'Use task-owned PDFs, outsiders, second-library member and revoked member in isolated DB.',
        'No real private content or credentials in diagnostics.','EVALUATION_REQUIRED')
    row('F09','Fresh uncached Global MACHINE Search','Global catalogue','HTTP 200; HNSW 613.67ms; 101 candidates; generation 30',
        'Observe native execution without rebuilding or forcing health flags.',
        ['institution_v2q1c_global_native_probe.json'],'Earlier response lacked a native trace',
        'Existing machine endpoint returns a cache miss, native-stage timing, candidate/rerank counts and generation.',
        'No source repair required. Keep prior HUMAN-path inference distinct.',
        'History/personalization disabled; no global writes/rebuild requested.','NO_REPAIR_NEEDED',execution='CONTROLLED_MODEL_REAL_RETRIEVAL; actual native HNSW verified')
    row('F10','Global/tenant/private browser sequence matrix','multiple scopes','Public subset executed; private/revocation/mobile coverage incomplete',
        'Library indicator, selected books, conversation and returned facts stay in the same active scope.',
        ['institution_v2q1_live_browser_observations.json','institution_v2q1_resumed_browser.json'],'Incomplete executed coverage',
        'Earlier browser evidence explicitly marked PARTIAL.',
        'Use existing frontend against the isolated task proxy, with actual authenticated flows.',
        'No unexpected JS/API errors, stale private responses or foreign document context.','EVALUATION_REQUIRED')
    save('institution_v2q1c_failure_matrix.json',matrix)
    lines=['# Part 2Q.1 continuation failure matrix','','Evidence and cause are separated in the accompanying JSON.','',
           '| Case | Recorded behavior | Proven cause / missing evidence | Repair status |','|---|---|---|---|']
    for record in matrix:lines.append('| '+' | '.join(str(record[key]).replace('|','/').replace('\n',' ') for key in ['id','actual_output','proven_cause','safe_unprotected_repair'])+' |')
    (OUT/'institution_v2q1c_failure_matrix.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    grounding=[];performance=[]
    for filename in ['institution_v2q1_public_rag_results.json','institution_v2q1_public_rag_extended.json','institution_v2q1_public_rag_resumed.json']:
        raw=read(filename);samples=[]
        for case in raw['queries']:
            result=case.get('response',{});calls=result.get('profile',{}).get('llm_calls',[])
            generation=sum(call.get('generation_ms',0) for call in calls)
            samples.append({'id':case['id'],'endpoint_ms':case['elapsed_seconds']*1000,
                'model_generation_ms':generation,'model_calls':len(calls),
                'input_tokens':[call.get('input_tokens') for call in calls],
                'generated_tokens':[call.get('generated_tokens') for call in calls],
                'retrieval_ms':result.get('retrieval',{}).get('stage_timing_ms',{})})
            if case['id'] in {'RAG001','RAG013','RAG019','RAG027'}:
                grounding.append({'id':case['id'],'query':case['query'],'answer':result['answer'],
                    'evidence_verdict':result['verdict'],'fast_filter':result['fast_filter_decision'],
                    'intent_data':result['intent_data'],'source_pages':[s.get('page') for s in result['sources']],
                    'source_chunk_ids':[s.get('chunk_id') for s in result['sources']],
                    'origin': 'MODEL_GENERATION_WITHOUT_METADATA_SUPPORT' if case['id']=='RAG027' else
                        'POSSIBLE_CROSS_EVENT_CONFLATION' if case['id']=='RAG019' else 'EVIDENCE_VERDICT_PRECEDES_ABSTAINING_GENERATION',
                    'adjudication':'Agent source review; no independent human judgment',
                    'actual_protected_source_changed':False})
        performance.append({'path':filename,'run_id':raw['run_id'],'n':len(samples),'samples':samples,
            'median_endpoint_ms':median(s['endpoint_ms'] for s in samples),
            'median_model_generation_ms':median(s['model_generation_ms'] for s in samples),
            'largest_measured_contributor':'Qwen generation across multiple calls',
            'first_token_latency':'NOT_MEASURED: non-streaming endpoint',
            'qualification':'Historical actual runtime observations; runs kept separate, not a before/after performance claim.'})
    save('institution_v2q1c_grounding_review.json',{'verdict_semantics':'Evidence sufficiency is classified before final answer generation; it is not a final-answer faithfulness grade.',
        'cases':grounding,'page_containment':'Unprotected response boundary; protected qa.py remains exact reviewed bytes.',
        'limits':'Numeric page citations and explicit page-location questions are checked. This does not validate chronology, all factual claims, Roman page labels or every possible citation convention.'})
    save('institution_v2q1c_latency_breakdown.json',performance)
    root=ROOT/'datasets/ai/faiss/hnsw';pointer=json.loads((root/'active_index.json').read_text())
    path=root/'versions'/pointer['version']/'manifest.json';manifest=json.loads(path.read_text())
    save('institution_v2q1c_global_search_review.json',{'checkpoint_health':read('institution_v2q1c_checkpoint.json')['services']['search'],
        'active_pointer':pointer,'manifest':manifest,'manifest_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'pointer_sha256':hashlib.sha256((root/'active_index.json').read_bytes()).hexdigest(),
        'stale_reason':'status() forces STALE when baseline_verified is false, even with pending=false. Legacy bootstrap starts unverified; delta publications retain that flag unless a full verified rebuild is performed.',
        'meaning':'A structural native index can serve queries without a completed full-source baseline verification. False is not proof of corruption or proof of full catalogue consistency.',
        'native_trace':read('institution_v2q1c_global_native_probe.json'),
        'prior_human_path':'Recorded interpretation identifies the HUMAN wrapper; per-request semantic/native execution was not retained and cannot be retroactively claimed.',
        'actions':'Read-only health/pointer/manifest inspection and one public machine request. No validation scan, rebuild, manifest rewrite, pointer reset or flag change.'})
    judge_rows=[]
    sources=[('GLOBAL_MACHINE_LEARNING',read('institution_v2q1_global_search_probe.json'),'Global','introductory machine learning for beginners','Global machine learning; beginner difficulty is a preference','institution_v2q1_global_search_probe.json'),
        ('GLOBAL_DISTRIBUTED',read('institution_v2q1c_global_native_probe.json'),'Global','introductory distributed computing with network protocols for beginners','Distributed computing and protocols; beginner preference','institution_v2q1c_global_native_probe.json'),
        ('TENANT_NETWORKING',read('institution_v2q1_tenant_search_probe.json'),'TEST','networking','Ambiguous: social/business versus computer networking','institution_v2q1_tenant_search_probe.json')]
    public_test='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
    similarity=next(case for case in old if case['id']=='RESUME_UI003')
    sources.append(('LOCAL_SIMILAR',{'results':[{'library_book_id':i} for i in similarity['book_ids']]},'TEST',
        'Recommend similar books to TEST Campus Network Practice Workbook','Seed subjects: Computer networks; Technical education. Seed is local-only.','institution_v2q1_resumed_browser.json:RESUME_UI003'))
    with MongoClient('mongodb://127.0.0.1:27017',serverSelectionTimeoutMS=5000) as client:
        db=client['luminar_library']
        for stratum,source,scope,query,topic,path in sources:
            for rank,record in enumerate(source['results'],1):
                identity=record.get('work_id') or record.get('library_book_id')
                metadata=(db.books.find_one({'work_id':identity}) if scope=='Global' else
                    db.institution_library_books.find_one({'library_id':public_test,'library_book_id':identity})) or {}
                clean={key:metadata.get(key) for key in ['title','authors','subjects','description','language','average_rating']}
                clean['description']=str(clean['description'] or '')[:2000]
                judge_rows.append({'row_id':stratum+f'-{rank:02d}','stratum':stratum,'scope':scope,'query':query,
                    'expected_topic':topic,'requested_filters':'Selected library only; exclude seed' if stratum=='LOCAL_SIMILAR' else 'No hard metadata filters',
                    'book_id':identity,'rank':rank,'metadata':clean,'retrieval_evidence':path,
                    'relevance_grade':None,'judge_identity':None,'judge_type':'UNASSIGNED',
                    'judgment_rationale':None,'label_status':'UNJUDGED'})
    save('institution_v2q1c_relevance_review.json',{'instructions':'Independent reviewer: grade 0 irrelevant, 1 marginal, 2 relevant, 3 strongly relevant from supplied metadata; use UNKNOWN if metadata is insufficient. Record identity/type and rationale. Do not infer contents or calculate recall from these top results.',
        'human_reviewed_rows':0,'metrics':'NOT_MEASURED; no independent labels or exhaustive relevance set',
        'rows':judge_rows})
    lines=['# Relevance review sheet','','All rows are actual executed results. Human grades are unassigned. Full metadata and query/filter context are in institution_v2q1c_relevance_review.json.','',
        'Grade: 0 irrelevant, 1 marginal, 2 relevant, 3 strongly relevant, UNKNOWN when evidence is insufficient. Fill judge identity/type and rationale.','',
        '| Row | Rank | Title | Subjects | Grade | Judge / rationale |','|---|---:|---|---|---|---|']
    for row in judge_rows:
        text=lambda value:str(value or '').replace('|','/').replace('\n',' ')
        lines.append(f"| {row['row_id']} | {row['rank']} | {text(row['metadata']['title'])} | {text(row['metadata']['subjects'])} |  |  |")
    (OUT/'institution_v2q1c_relevance_review.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps({'failure_cases':len(matrix),'grounding_cases':len(grounding),'separate_latency_runs':len(performance),'judgment_ready_rows':len(judge_rows),'independent_labels':0}))

if __name__=='__main__':main()
