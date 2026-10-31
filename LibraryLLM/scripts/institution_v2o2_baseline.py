"""Read-only immutable O.2 checkpoint before proposal hardening."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2o1_baseline.py').read_text().replace('institution_v2o1','institution_v2o2').replace('institution-v2o1','institution-v2o2')
source=source.replace("'institution_v2o_']", "'institution_v2o_','institution_v2o1_']")
exec(compile(source,str(ROOT/'scripts/institution_v2o1_baseline.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
