"""Summarize measured public RAG samples without extrapolating a production SLO."""
from pathlib import Path
import json, statistics

ROOT=Path(__file__).resolve().parents[1]

def main():
    raw=json.loads((ROOT/'reports/institution_v2q1_public_rag_results.json').read_text(encoding='utf8'))
    rows=[]
    for query in raw['queries']:
        if 'response' not in query:continue
        response=query['response'];profile=response.get('profile',{});retrieval=response.get('retrieval',{})
        rows.append({'id':query['id'],'elapsed_ms':query['elapsed_seconds']*1000,
            'stage_timing_ms':response.get('timing_ms'),'retrieval_timing_ms':retrieval.get('stage_timing_ms'),
            'model_calls':profile.get('llm_calls',[]),'verdict':response.get('verdict')})
    values=[r['elapsed_ms'] for r in rows]
    summary={'run_id':raw['run_id'],'evidence':'REAL_MODEL_REAL_RETRIEVAL',
        'scope':'Public 3,959-vector RAG index, not global five-million-book Search.',
        'sample_size':len(rows),'median_ms':statistics.median(values) if values else None,
        'min_ms':min(values) if values else None,'max_ms':max(values) if values else None,
        'p95':'NOT_REPORTED: four samples are inadequate','samples':rows,
        'limits':'Warm process, local single-host calls; no production SLO or global Search latency claim.'}
    (ROOT/'reports/institution_v2q1_performance.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(json.dumps({'sample_size':len(rows),'median_ms':summary['median_ms']}))

if __name__=='__main__':main()
