"""Four fresh public RAG requests on the single-Qwen owned lab."""
from pathlib import Path
import httpx,json,time
ROOT=Path(__file__).resolve().parents[1]
def main():
 output=ROOT/'reports/institution_v2q1c_public_grounding.json';assert not output.exists()
 cases=[r for name in ['institution_v2q1_public_rag_results.json','institution_v2q1_public_rag_resumed.json'] for r in json.loads((ROOT/'reports'/name).read_text())['queries'] if r['id'] in {'RAG001','RAG013','RAG019','RAG027'}]
 result={'execution':'REAL_QWEN_REAL_PUBLIC_RETRIEVAL; current unprotected API boundary','cases':[]}
 with httpx.Client(timeout=240) as client:
  for case in cases:
   start=time.perf_counter();response=client.post('http://127.0.0.1:18005/rag/ask',json={'query':case['query']});body=response.json()
   row={'id':case['id'],'query':case['query'],'http':response.status_code,'elapsed_ms':round((time.perf_counter()-start)*1000,3),'response':body}
   result['cases'].append(row);output.write_text(json.dumps(result,indent=2));print(case['id'],response.status_code,body.get('verdict'),flush=True)
 result['complete']=True;output.write_text(json.dumps(result,indent=2))
if __name__=='__main__':main()
