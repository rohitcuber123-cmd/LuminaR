"""Accepted N native code laboratory with O fixture scope; no native patches."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2n_native_child.py').read_text(encoding='utf8').replace('v2n','v2o').replace('V2N','V2O')
exec(compile(source,str(ROOT/'scripts/institution_v2n_native_child.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
