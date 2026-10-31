"""Immutable O.3 review checkpoint; no protected-change approval inferred."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2o2_baseline.py').read_text().replace('institution_v2o2','institution_v2o3').replace('institution-v2o2','institution-v2o3')
source=source.replace("'institution_v2o1_']", "'institution_v2o1_','institution_v2o2_']")
exec(compile(source,str(ROOT/'scripts/institution_v2o2_baseline.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
