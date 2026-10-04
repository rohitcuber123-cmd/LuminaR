"""Live read-only benchmark through normal auth and existing assistant/tools."""
import argparse
import json
from pathlib import Path
import statistics
from time import perf_counter, sleep
import httpx

ROOT = Path(__file__).resolve().parents[1]
IDS = ['OL21640039W', 'OL44077582W']
CASES = [
    ('compare', 'what are the differences in these books', IDS),
    ('compare_typo', 'what are the differnces in these books', IDS),
    ('compare_short', 'compare these', IDS),
    ('availability', 'are these books available?', IDS),
    ('recommend', 'recommend based on these', IDS),
    ('fees', 'what do I owe?', []),
    ('loans', 'show my loans', []),
    ('reservations', 'my reservations', []),
    ('more_like_this', 'more like this', IDS[:1]),
    ('simple_search', 'find books about machine learning', []),
    ('complex_search', 'I want something about money but not a textbook and preferably useful for someone starting a business', []),
    ('general_help', 'What is Gothic fiction?', []),
    ('ambiguous', 'Which of these would fit someone who already understands calculus but is new to machine learning?', IDS),
]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['before','after'],required=True)
    parser.add_argument('--repetitions',type=int,default=3)
    args=parser.parse_args()
    identity=json.loads((ROOT/'.selected_context_validation.json').read_text())
    rows=[]
    def save():
        grouped={}
        for name,_,_ in CASES:
            measured=[r for r in rows if r['case']==name and r['warm']]
            if measured:
                times=[r['latency_ms'] for r in measured]
                grouped[name]={'median_ms':statistics.median(times),'min_ms':min(times),'max_ms':max(times),
                    'qwen_calls':[r['qwen_call_count'] for r in measured],
                    'intent':[r['response'].get('intent') for r in measured]}
        (ROOT/f'reports/assistant_selected_{args.phase}_benchmark.json').write_text(json.dumps({'phase':args.phase,'repetitions':args.repetitions,'warm_summary':grouped,'runs':rows},indent=2))
    with httpx.Client(timeout=180) as client:
        login=client.post('http://127.0.0.1:8002/auth/login',json={'email':identity['email'],'password':identity['password']})
        login.raise_for_status()
        headers={'Authorization':'Bearer '+login.json()['access_token']}
        for name,message,selected in CASES:
            for repetition in range(args.repetitions+1):
                payload={'message':message,'selected_work_ids':selected,'recent_work_ids':['OL19545719W'],
                         'page_context':{'work_id':'OL17930368W'},'conversation_id':None,'action':None,'pending_action_id':None}
                start=perf_counter()
                response=client.post('http://127.0.0.1:8005/assistant/chat',json=payload,headers=headers)
                elapsed=(perf_counter()-start)*1000
                response.raise_for_status()
                trace=response.headers.get('x-assistant-trace')
                profiles=ROOT/f'reports/assistant_selected_{args.phase}_profiles.jsonl'
                profile={}
                for _ in range(100):
                    # ASGI sends the response before finally writing its profile.
                    observations=profiles.read_text().splitlines() if profiles.exists() else []
                    profile=next((p for p in reversed([json.loads(line) for line in observations]) if p['trace_id']==trace),{})
                    if profile: break
                    sleep(.01)
                if not profile: raise RuntimeError('Completed request profile was not written.')
                rows.append({'case':name,'warm':repetition>0,'request':payload,'latency_ms':elapsed,'trace_id':trace,
                             'qwen_call_count':profile.get('qwen_call_count'),'profile':profile,'response':response.json()})
                save()
                print(f"{args.phase} {name} repetition={repetition} {elapsed:.1f}ms intent={response.json().get('intent')} qwen={profile.get('qwen_call_count')}",flush=True)

if __name__=='__main__':main()
