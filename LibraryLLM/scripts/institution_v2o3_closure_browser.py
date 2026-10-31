"""Actual Chromium, actual APIs/JWT/owned Mongo and manually built fixture indexes."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2o1_browser.py').read_text().replace('v2o1','v2o3_closure')
exec(compile(source,str(ROOT/'scripts/institution_v2o1_browser.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
