"""Summarize real resumed probes and audit public fixture ownership read-only."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
from urllib.request import urlopen
import hashlib, json, statistics, subprocess, sys
from pymongo import MongoClient

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from assistant.schemas import AssistantRequest, AssistantIntentDecision, Intent, ReferenceScope
from assistant.state import Conversation
from assistant.semantic import contextual_ids

def read(name):return json.loads((ROOT/'reports'/name).read_text(encoding='utf8'))

def main():
    raw=read('institution_v2q1_public_rag_resumed.json')
    cases=read('institution_v2q1_resumed_browser.json')['cases']
    ownership=[]
    with MongoClient('mongodb://127.0.0.1:27017',serverSelectionTimeoutMS=5000) as client:
        db=client['luminar_library']
        for case in cases:
            ids=case['book_ids']
            if not ids:continue
            query={'library_id':case['library_id'],'library_book_id':{'$in':ids}}
            active=db.institution_library_books.count_documents({**query,'status':'ACTIVE'})
            holdings=db.institution_holdings.count_documents(query)
            held={row['library_book_id'] for row in db.institution_holdings.find(query,{'_id':0,'library_book_id':1})}
            ownership.append({'case':case['id'],'returned':len(ids),'active_canonical_books':active,
                              'canonical_holdings':holdings,'missing_holdings_ids':[identity for identity in ids if identity not in held],
                              'all_owned':active==len(ids),'all_have_holdings':holdings==len(ids)})
    successful=[row for row in raw['queries'] if 'response' in row]
    traces=[]
    for row in successful:
        response=row['response']
        traces.append({'id':row['id'],'elapsed_seconds':row['elapsed_seconds'],
            'llm_calls':len(response.get('profile',{}).get('llm_calls',[])),
            'faiss_ms':response.get('retrieval',{}).get('stage_timing_ms',{}).get('faiss'),
            'verdict':response.get('verdict')})
    pagination=next(row['response'] for row in successful if row['id']=='RAG027')
    abstention=next(row['response'] for row in successful if row['id']=='RAG013')
    source_file=ROOT/'rag/book_chunks/OL85892W.json'
    chunk_data=json.loads(source_file.read_text(encoding='utf8'))
    chunk_rows=chunk_data if isinstance(chunk_data,list) else chunk_data['chunks']
    source_ids={source['chunk_id'] for source in pagination['sources']}
    matched=[row for row in chunk_rows if row.get('chunk_id') in source_ids]
    # Controlled counterfactual scopes only; these are not the live model decision.
    previous=next(case for case in cases if case['id']=='RESUME_UI004')
    request=AssistantRequest(message='Is the second one available?',recent_work_ids=previous['book_ids'])
    state=Conversation('controlled-reference-diagnostic','task-owned',library_scope='LIBRARY:'+previous['library_id'],
                       active_result_work_ids=previous['book_ids'])
    diagnostic={}
    for scope in [ReferenceScope.RECENT_RESULTS,ReferenceScope.SELECTED_BOOKS,ReferenceScope.CURRENT_PAGE_BOOK,ReferenceScope.NONE]:
        decision=AssistantIntentDecision(intent=Intent.CHECK_AVAILABILITY,confidence=1,
            reference_scope=scope,reference_position='SECOND')
        try:diagnostic[scope.value]={'ids':contextual_ids(request,decision,state)}
        except ValueError as error:diagnostic[scope.value]={'error':str(error)}
    health={}
    for name,port in [('core',8002),('search',8003),('rag',8005)]:
        with urlopen(f'http://127.0.0.1:{port}/health',timeout=5) as response:
            body=json.load(response)
            health[name]={key:body[key] for key in ['status','system','module','llm','device','vectors','model_loading_ms'] if key in body}
    result={'captured_at':datetime.now(timezone.utc).isoformat(),
        'revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'adapter_sha256':hashlib.sha256((ROOT/'assistant/library_scope.py').read_bytes()).hexdigest(),
        'health':health,'public_rag_run_id':raw['run_id'],
        'sample_size':len(raw['queries']),'successful':len(successful),
        'errors':[row for row in raw['queries'] if 'error' in row],
        'timing':{'median_seconds':statistics.median(row['elapsed_seconds'] for row in successful),
            'min_seconds':min(row['elapsed_seconds'] for row in successful),
            'max_seconds':max(row['elapsed_seconds'] for row in successful),
            'p95':'Not generalized from this small purposive sample; do not pool timing runs'},
        'verdict_counts':dict(Counter(row['response']['verdict'] for row in successful)),
        'model_retrieval_traces':traces,'ownership':ownership,
        'ownership_qualification':'Five result sets from two existing public fixture libraries; repeated books counted per response. No live private-library ownership percentage is inferred.',
        'reference_diagnostic':{'evidence_type':'DETERMINISTIC_FIXTURE','scopes':diagnostic,
            'limitation':'Actual live parsed scope remains unobserved. Current binding honors the selected scope; changing fallback scope without that evidence could alter security semantics. No binding change made.'},
        'grounding_findings':[
            {'id':'RAG013','classification':'VERDICT_ABSTENTION_MISMATCH','answer':abstention['answer'],'verdict':abstention['verdict']},
            {'id':'RAG027','classification':'UNSUPPORTED_PAGINATION_CLAIM','answer':pagination['answer'],
             'verdict':pagination['verdict'],'returned_source_page_values':[source.get('page') for source in pagination['sources']],
             'matched_public_chunks':len(matched),'public_chunk_page_values':[row.get('page') for row in matched],
             'source_file':source_file.relative_to(ROOT).as_posix(),'source_sha256':hashlib.sha256(source_file.read_bytes()).hexdigest(),
             'qualification':'Agent source audit, not independent human adjudication; no source was modified.'},
            {'id':'RAG019','classification':'POSSIBLE_CROSS_EVENT_CONFLATION','qualification':'Answer combines first-journey question with distant-past speculation from an epilogue chunk. Independent adjudication remains needed.'}],
        'security_qualification':'RAG028/029 rejected unsupported instructions and RAG030 abstained on a private-data request. These unauthenticated public-corpus cases do not replace private asset authorization tests.',
        'regression_qualification':'No additional application source changes after the completed 3053/0/20 backend and 1028/0/0 frontend runs. Only evaluation scripts/reports added.'}
    target=ROOT/'reports/institution_v2q1_resumed_summary.json'
    target.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({'public_rag_samples':len(successful),'median_seconds':result['timing']['median_seconds'],
        'ownership':ownership,'reference_diagnostic':diagnostic}))

if __name__=='__main__':main()
