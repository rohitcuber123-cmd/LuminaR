"""Frozen product inventory through2L, new2M tests and independent output namespace."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];path=ROOT/'scripts/institution_v2i_checks.py'
source=path.read_text(encoding='utf8').replace('reports/institution_v2i_','reports/institution_v2m_').replace('.scratch/institution-v2i/','.scratch/institution-v2m/')
source=source.replace("f'institution_v2i_{a.tag}_generated_","f'institution_v2m_{a.tag}_generated_")
source=source.replace("if tag != 'baseline' and (ROOT / 'tests/institution_v2i').exists():","if (ROOT / 'tests/institution_v2i').exists():")
source=source.replace("groups['institution_v2i'] = ['tests/institution_v2i']","groups['institution_v2i'] = ['tests/institution_v2i']\n    groups['institution_v2j'] = ['tests/institution_v2j']\n    groups['institution_v2k'] = ['tests/institution_v2k']\n    groups['institution_v2l'] = ['tests/institution_v2l']\n    if (ROOT / 'tests/institution_v2m').exists():\n        groups['institution_v2m'] = ['tests/institution_v2m']")
exec(compile(source,str(path),'exec'),{'__file__':str(path),'__name__':'__main__'})
