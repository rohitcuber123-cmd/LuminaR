"""Accepted K authenticated actual-model fault workflows, through native integration."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2k_native_faults.py').read_text(encoding='utf8').replace('V2K','V2L').replace('v2k','v2l')
exec(compile(source,str(ROOT/'scripts/institution_v2k_native_faults.py'),'exec'),{'__file__':str(Path(__file__).resolve()),'__name__':'__main__'})
