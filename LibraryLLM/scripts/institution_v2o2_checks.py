"""Full accepted current-tree inventory through O.1 plus O.2 candidate tests."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2o1_checks.py').read_text().replace('institution_v2o1','institution_v2o2').replace('institution-v2o1','institution-v2o2')
source=source.replace("'v2m','v2n','v2o']", "'v2m','v2n','v2o','v2o1']")
exec(compile(source,str(ROOT/'scripts/institution_v2o1_checks.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
