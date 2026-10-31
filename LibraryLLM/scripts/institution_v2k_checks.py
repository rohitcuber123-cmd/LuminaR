"""Frozen product inventory through 2J, independent report namespace."""
from pathlib import Path
path=Path(__file__).resolve().with_name('institution_v2i_checks.py')
source=path.read_text(encoding='utf8').replace('reports/institution_v2i_','reports/institution_v2k_').replace('.scratch/institution-v2i/','.scratch/institution-v2k/')
source=source.replace("f'institution_v2i_{a.tag}_generated_","f'institution_v2k_{a.tag}_generated_")
source=source.replace("if tag != 'baseline' and (ROOT / 'tests/institution_v2i').exists():","if (ROOT / 'tests/institution_v2i').exists():")
source=source.replace("groups['institution_v2i'] = ['tests/institution_v2i']","groups['institution_v2i'] = ['tests/institution_v2i']\n    groups['institution_v2j'] = ['tests/institution_v2j']\n    if tag != 'baseline' and (ROOT / 'tests/institution_v2k').exists():\n        groups['institution_v2k'] = ['tests/institution_v2k']")
exec(compile(source,str(path),'exec'),{'__file__':str(path),'__name__':'__main__'})
