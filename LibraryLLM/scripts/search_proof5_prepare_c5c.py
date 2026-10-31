"""Versioned exposed C5C capture setup using unchanged prediction/scoring logic."""
from pathlib import Path
import json,hashlib,sys
R=Path('reports')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    tag=sys.argv[1];assert tag.isalnum()
    P='search_proof5_c5c_'+tag+'_';predictor=Path('scripts/search_proof5_c5c_'+tag+'_predict.py')
    text=Path('scripts/search_comp3_final2_predict_c5c.py').read_text(encoding='utf8').replace('search_comp3_final2_c5c_',P).replace('scratch.search_compositional_recovery_v3.parser','scratch.search_proof_recovery_v5.parser')
    with predictor.open('x',encoding='utf8') as f:f.write(text)
    config=json.loads((R/'search_comp3_final2_c5c_parser_configuration.json').read_text(encoding='utf8'))
    paths=list(Path('scratch/search_proof_recovery_v5').glob('*.py'))+list(Path('scratch/search_v2c_c5er/candidate_search_v4').glob('*.py'))+[predictor]
    config['parser_source_hashes']={str(p):sha(p) for p in paths};config['frozen_before_prediction_scripts']=config['parser_source_hashes'];config['candidate_id']='search-smarteng-disabled-proof-5'
    for n in ['parser_inputs.jsonl','eligibility.json']:
        with (R/(P+n)).open('xb') as f:f.write((R/('search_comp3_final2_c5c_'+n)).read_bytes())
    with (R/(P+'preflight.json')).open('xb') as f:f.write((R/'search_proof5_preflight.json').read_bytes())
    for n,v in [('parser_configuration.json',config),('candidate_freeze.json',{'files':config['parser_source_hashes']})]:
        with (R/(P+n)).open('x') as f:json.dump(v,f,indent=2)
    out=Path('scratch/search_proof5_history')/('c5c_'+tag);out.mkdir(parents=True)
    for p in Path('scratch/search_proof_recovery_v5').glob('*.py'):(out/(p.name+'.txt')).write_bytes(p.read_bytes())
    text=Path('scripts/search_comp3_final2_score_c5c.py').read_text(encoding='utf8').replace('search_comp3_final2_c5c_',P)
    with Path('scripts/search_proof5_c5c_'+tag+'_score.py').open('x',encoding='utf8') as f:f.write(text)
    print(json.dumps({'tag':tag,'prefix':P,'source_files':len(paths)}))
if __name__=='__main__':main()
