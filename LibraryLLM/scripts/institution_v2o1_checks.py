"""Accepted full independent product groups through O plus review checks."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2n_checks.py').read_text().replace('institution_v2n','institution_v2o1').replace('institution-v2n','institution-v2o1')
source=source.replace("['v2j','v2k','v2l','v2m']", "['v2j','v2k','v2l','v2m','v2n','v2o']")
exec(compile(source,str(ROOT/'scripts/institution_v2n_checks.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
