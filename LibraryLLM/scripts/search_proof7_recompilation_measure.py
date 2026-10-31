"""Pure reparse/verification timing; no backend or commit."""
import time,json,statistics,math
from pathlib import Path
from scratch.search_proof_recovery_v7.parser import parse_query,_decode,PARSER_VERSION
from scratch.search_proof_recovery_v7.contract import State,digest
from scratch.search_proof_recovery_v7.completion import BoundContext
from scratch.search_proof_recovery_v7.recompilation import issue_completion,recompile
from scripts.search_proof7_performance import stats

def main():
    samples=[];errors=[]
    for field,value in [('by','Oak Vale'),('titled','Field Manual'),('language','English'),('rating at least','4'),('published after','2020'),('sort by','TITLE')]:
        p=parse_query('category Fiction; '+field+' [not supplied]',['Fiction'])
        r=next(r for r in _decode(p.decision['query_ir_contract']).requirements if r.state==State.PLACEHOLDER)
        c=BoundContext('owner','login','library','STAFF',PARSER_VERSION,'SMART',digest(p.raw_query),7,1000)
        for _ in range(10):
            st=time.perf_counter()
            e=issue_completion(p,r.requirement_id,value,7)
            d=recompile(e,p,c,c,now=10,facets=['Fiction'],capabilities={},authorized=True)
            samples.append((time.perf_counter()-st)*1000)
            assert not d['commit_performed']
    report={'population':'60 pure drafts; six fields x10, exposed development fixtures','timing':stats(samples),'successful':len(samples),'errors':errors,'fresh_authorization':'externally asserted mock only','Mongo_calls':0,'commit_calls':0,'actual_CAS_durability':'N/A','operational_SLO':'UNAGREED'}
    with Path('reports/search_proof7_recompilation_timing.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
if __name__=='__main__':main()
