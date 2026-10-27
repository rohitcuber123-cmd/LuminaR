"""Source-backed residual wrapper repair, before independent acceptance.

Preserve candidate-1, every prior run and all old namespace files verbatim.
"""
from pathlib import Path
import json,hashlib
ROOT=Path('scratch/search_v2c_c5e')
def main():
    target=ROOT/'candidate_search_v2';target.mkdir()
    for p in (ROOT/'candidate_search').glob('*.py'):
        text=p.read_text(encoding='utf8').replace('scratch.search_v2c_c5e.candidate_search','scratch.search_v2c_c5e.candidate_search_v2').replace('search-v2c-c5e-disabled-candidate-1','search-v2c-c5e-disabled-candidate-2')
        (target/p.name).write_text(text,encoding='utf8')
    tests=ROOT/'regression_v2';tests.mkdir()
    sources=list((ROOT/'regression').glob('*.py'))+list(ROOT.glob('test*.py'))
    for p in sources:
        text=p.read_text(encoding='utf8').replace('scratch.search_v2c_c5e.candidate_search','scratch.search_v2c_c5e.candidate_search_v2')
        (tests/p.name).write_text(text,encoding='utf8')
    native=ROOT/'native_v2';native.mkdir()
    for p in (ROOT/'native').glob('*.py'):
        text=p.read_text(encoding='utf8').replace('scratch.search_v2c_c5e.candidate_search','scratch.search_v2c_c5e.candidate_search_v2').replace('search-v2c-c5e-disabled-candidate-1','search-v2c-c5e-disabled-candidate-2').replace('scratch/search_v2c_c5e/native/login_sessions.sqlite','scratch/search_v2c_c5e/native_v2/login_sessions.sqlite')
        (native/p.name).write_text(text,encoding='utf8')
    for name in ['predict','development_prepare','development_score','performance']:
        source=Path('scripts/search_v2c_c5e_'+name+'.py')
        text=source.read_text(encoding='utf8').replace('scratch.search_v2c_c5e.candidate_search','scratch.search_v2c_c5e.candidate_search_v2').replace('scratch/search_v2c_c5e/candidate_search','scratch/search_v2c_c5e/candidate_search_v2')
        text=text.replace('search_v2c_c5e_development_','search_v2c_c5e_v2_development_').replace('search_v2c_c5e_predict.py','search_v2c_c5e_v2_predict.py').replace('search_v2c_c5e_development_score.py','search_v2c_c5e_v2_development_score.py')
        if name=='performance':text=text.replace("P='search_v2c_c5e_'","P='search_v2c_c5e_v2_'")
        Path('scripts/search_v2c_c5e_v2_'+name+'.py').write_text(text,encoding='utf8')
    print('Created disabled C5E candidate-2; candidate-1 and all measurements preserved.')
if __name__=='__main__':main()
