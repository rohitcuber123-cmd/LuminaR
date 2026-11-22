"""Freeze the accepted uncommitted2P tree and current live metadata read-only."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2p_baseline.py').read_text(encoding='utf8').replace('institution_v2p_', 'institution_v2q_').replace('institution-v2p/', 'institution-v2q/')
exec(compile(source,str(ROOT/'scripts/institution_v2p_baseline.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
