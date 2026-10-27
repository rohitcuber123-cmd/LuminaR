"""Query-only review packet, labels/strata withheld from independent reviewer."""
from pathlib import Path
import json,hashlib
R=Path('reports');P='search_v2c_c5e_'
def main():
    old=json.loads((R/(P+'blind_reviewer_input.json')).read_text(encoding='utf8'))
    path=R/(P+'independent_authored_v3.jsonl')
    rows=[json.loads(s) for s in path.read_text(encoding='utf8').splitlines()]
    # Retain only normative specification and scope contracts from old packet.
    result={k:v for k,v in old.items() if k not in ['cases','source_author_artifact_sha256','output','source_query_artifact_sha256']}
    for key in list(result):
        if 'sha' in key or 'output' in key or 'source' in key:result.pop(key)
    result['cases']=[{k:x[k] for k in ['case_id','query_text','scope_type','workspace_type','search_mode']} for x in rows]
    result['source_query_artifact_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    result['output']='reports/search_v2c_c5e_independent_review_v3.json'
    result['task']='Fresh output-blind normative review of structurally isolated revised queries; no labels, target strata, source or candidate predictions supplied.'
    with (R/(P+'blind_reviewer_input_v3.json')).open('x',encoding='utf8') as f:json.dump(result,f,indent=2,ensure_ascii=False)
    print(json.dumps({'query_contexts':len(rows),'labels_or_strata_in_cases':False,'packet_keys':list(result)}))
if __name__=='__main__':main()
