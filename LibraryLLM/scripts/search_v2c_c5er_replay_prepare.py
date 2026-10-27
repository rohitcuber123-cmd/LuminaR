"""Prepare C5C exposed replay for a source-frozen disabled revision."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,sys
R=Path('reports')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    version=sys.argv[1];P='search_v2c_c5er_v'+version+'_c5c_'
    assert version.isdigit()
    namespace='scratch.search_v2c_c5er.candidate_search_v'+version
    s=Path('scripts/search_v2c_c5e_v2_predict.py').read_text(encoding='utf8')
    s=s.replace('scratch.search_v2c_c5e.candidate_search_v2',namespace)
    s=s.replace("P = 'search_v2c_c5e_v2_development_' if len(sys.argv)>1 and sys.argv[1]=='development' else 'search_v2c_c5e_independent_'",'P = '+repr(P))
    predictor=Path('scripts/search_v2c_c5er_v'+version+'_predict_c5c.py')
    with predictor.open('x',encoding='utf8') as f:f.write(s)
    code={str(p):sha(p) for p in Path(namespace.replace('.','/')).glob('*.py')};code[str(predictor)]=sha(predictor)
    def write(n,v):
        with (R/(P+n)).open('x',encoding='utf8') as f:json.dump(v,f,indent=2)
    for n in ['parser_inputs.jsonl','eligibility.json']:
        with (R/(P+n)).open('xb') as f:f.write((R/('search_v2c_c5c_'+n)).read_bytes())
    write('preflight.json',json.loads((R/'search_v2c_c5er_preflight.json').read_text(encoding='utf8')))
    caps=R/'search_v2c_c5a_capability_matrix.json'
    write('candidate_freeze.json',{'files':code,'at_utc':datetime.now(timezone.utc).isoformat(),'exposed_development_only':True})
    write('parser_configuration.json',{'prediction_calls_planned':644,'input_sha256':sha(R/(P+'parser_inputs.jsonl')),'caps_path':str(caps),'caps_sha256':sha(caps),
        'parser_source_hashes':code,'frozen_before_prediction_scripts':code,'production_activation':False})
    score=Path('scripts/search_v2c_c5e_v2_development_score.py').read_text(encoding='utf8').replace('search_v2c_c5e_v2_development_',P)
    with Path('scripts/search_v2c_c5er_v'+version+'_score_c5c.py').open('x',encoding='utf8') as f:f.write(score)
if __name__=='__main__':main()
