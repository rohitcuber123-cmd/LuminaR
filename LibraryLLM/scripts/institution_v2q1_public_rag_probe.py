"""Small public RAG probe against the existing resident service, without auth or writes."""
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
import json, subprocess, urllib.request, uuid

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/institution_v2q1_public_rag_results.json'
queries = [
    ('RAG001', 'What evidence is available about machine learning?', 'abstain if evidence is insufficient'),
    ('RAG002', 'Who is Dracula and what evidence supports the answer?', 'ground claims in public sources'),
    ('RAG003', 'What does The Time Machine say about time travel?', 'ground claims in public sources'),
    ('RAG004', 'What does the text say about modern smartphones?', 'abstain if evidence is insufficient'),
]

def request(path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request('http://127.0.0.1:8005'+path, data=body,
        headers={'Content-Type':'application/json'} if body else {})
    with urllib.request.urlopen(req, timeout=180) as response:
        return json.load(response)

def main():
    run_id=uuid.uuid4().hex
    result={'run_id':run_id,'started_at':datetime.now(timezone.utc).isoformat(),
        'revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'health':request('/health'),'scope':'public RAG corpus; not assistant chat or global catalogue Search',
        'judgments':'provisional; no independent review','queries':[]}
    for qid,query,expected in queries:
        started=perf_counter()
        row={'id':qid,'query':query,'expected':expected,'evidence_type':'REAL_MODEL_REAL_RETRIEVAL',
             'timestamp':datetime.now(timezone.utc).isoformat()}
        try:row['response']=request('/rag/ask',{'query':query,'depth':'concise'})
        except Exception as error:row.update(evidence_type='NOT_EXECUTED',error=f'{type(error).__name__}: {error}')
        row['elapsed_seconds']=round(perf_counter()-started,3)
        result['queries'].append(row)
        OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False,default=str),encoding='utf8')
        print(qid,row.get('error','completed'),row['elapsed_seconds'],flush=True)

if __name__=='__main__':main()
