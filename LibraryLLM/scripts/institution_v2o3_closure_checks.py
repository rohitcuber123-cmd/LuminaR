"""Complete accepted actual-tree product inventory through O.3 and closure."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2o2_checks.py').read_text().replace('institution_v2o2','institution_v2o3_closure').replace('institution-v2o2','institution-v2o3-closure')
source=source.replace("'v2o','v2o1']", "'v2o','v2o1','v2o2','v2o3']")
exec(compile(source,str(ROOT/'scripts/institution_v2o2_checks.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
