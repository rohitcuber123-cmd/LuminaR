"""Run exact proposed assertions only in O.3 owned source fixtures."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2o2_guard_probe.py').read_text().replace('v2o2','v2o3')
exec(compile(source,str(ROOT/'scripts/institution_v2o2_guard_probe.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
