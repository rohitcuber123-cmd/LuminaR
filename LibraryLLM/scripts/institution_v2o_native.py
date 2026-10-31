"""Fresh accepted actual native authentication/crash workflows, O namespace."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2n_native.py').read_text(encoding='utf8').replace('v2n','v2o').replace('V2N','V2O')
exec(compile(source,str(ROOT/'scripts/institution_v2n_native.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
