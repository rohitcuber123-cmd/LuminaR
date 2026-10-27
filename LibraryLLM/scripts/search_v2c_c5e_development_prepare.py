"""Development replay A; explicitly not independent acceptance."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
R=Path('reports');P='search_v2c_c5e_development_'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(n,v):
    if (R/(P+n)).exists():
        assert json.loads((R/(P+n)).read_text(encoding='utf8'))==v
        return
    with (R/(P+n)).open('x',encoding='utf8') as f:json.dump(v,f,indent=2)
def main():
    pre=json.loads((R/'search_v2c_c5e_preflight.json').read_text(encoding='utf8'))
    assert all(sha(p)==h for p,h in pre['protected_files'].items())
    write('preflight.json',pre)
    for n in ['eligibility.json','parser_inputs.jsonl']:
        data=(R/('search_v2c_c5c_'+n)).read_bytes()
        if (R/(P+n)).exists():assert (R/(P+n)).read_bytes()==data
        else:
            with (R/(P+n)).open('xb') as f:f.write(data)
    files={str(p):sha(p) for p in Path('scratch/search_v2c_c5e/candidate_search').glob('*.py')}
    files.update({str(p):sha(p) for p in [Path('scripts/search_v2c_c5e_predict.py'),Path('scripts/search_v2c_c5e_development_score.py'),Path('scripts/search_v2c_c5c_score.py')]})
    write('candidate_freeze.json',{'files':files,'at_utc':datetime.now(timezone.utc).isoformat(),'cohort':'A original exposed C5C development only','disabled':True})
    cap=R/'search_v2c_c5a_capability_matrix.json'
    write('parser_configuration.json',{'prediction_calls_planned':644,'input_sha256':sha(R/(P+'parser_inputs.jsonl')),
          'caps_path':str(cap),'caps_sha256':sha(cap),'parser_source_hashes':files,'frozen_before_prediction_scripts':files,
          'independent_acceptance':False,'production_activation':False})
if __name__=='__main__':main()
