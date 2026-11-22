"""Fresh preserved O progress/security behavior using its existing owned fixture."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2o3_closure_browser.py').read_text(encoding='utf8').replace("replace('v2o1','v2o3_closure')", "replace('v2o1','v2p_intelligence')")
exec(compile(source,str(ROOT/'scripts/institution_v2o3_closure_browser.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
