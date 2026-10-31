"""Apply the byte-frozen C5C scorer to candidate capture; namespace only."""
import json
from pathlib import Path
import scripts.search_v2c_c5c_score as scorer
from scripts.search_v2c_c5d_repair_prepare import R,sha,load
P="search_v2c_smarteng_c5c_"

def write(name,value):
    with (R/(P+name)).open('x',encoding='utf8') as f:f.write(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False)+'\n')
def jsonl(name,values):
    with (R/(P+name)).open('x',encoding='utf8') as f:
        for value in values:f.write(json.dumps(value,sort_keys=True,ensure_ascii=False)+'\n')
if __name__=='__main__':
    frozen=load(R/(P+'candidate_freeze.json'))
    assert all(sha(p)==h for p,h in frozen['files'].items())
    scorer.P=P;scorer.write=write;scorer.jsonl=jsonl
    scorer.main()
