"""Frozen independent suite inventory through N plus O, with separate evidence."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2n_checks.py').read_text(encoding='utf8').replace('institution_v2n','institution_v2o').replace('institution-v2n','institution-v2o')
source=source.replace("['v2j','v2k','v2l','v2m']", "['v2j','v2k','v2l','v2m','v2n']")
exec(compile(source,str(ROOT/'scripts/institution_v2n_checks.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
