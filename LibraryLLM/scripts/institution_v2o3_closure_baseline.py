"""Immutable pre-application checkpoint for the explicitly approved closure."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2o3_baseline.py').read_text().replace('institution_v2o3','institution_v2o3_closure').replace('institution-v2o3','institution-v2o3-closure')
source=source.replace("'institution_v2o2_']", "'institution_v2o2_','institution_v2o3_']")
exec(compile(source,str(ROOT/'scripts/institution_v2o3_baseline.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
