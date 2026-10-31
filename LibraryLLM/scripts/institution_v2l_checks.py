"""Frozen product groups through2K, distinct2L outputs, baseline before native edits."""
from pathlib import Path
path=Path(__file__).resolve().with_name('institution_v2i_checks.py')
source=path.read_text(encoding='utf8').replace('reports/institution_v2i_','reports/institution_v2l_').replace('.scratch/institution-v2i/','.scratch/institution-v2l/')
source=source.replace("f'institution_v2i_{a.tag}_generated_","f'institution_v2l_{a.tag}_generated_")
source=source.replace("if tag != 'baseline' and (ROOT / 'tests/institution_v2i').exists():","if (ROOT / 'tests/institution_v2i').exists():")
source=source.replace("groups['institution_v2i'] = ['tests/institution_v2i']","groups['institution_v2i'] = ['tests/institution_v2i']\n    groups['institution_v2j'] = ['tests/institution_v2j']\n    groups['institution_v2k'] = ['tests/institution_v2k']\n    if tag != 'baseline' and (ROOT / 'tests/institution_v2l').exists():\n        groups['institution_v2l'] = ['tests/institution_v2l']")
exec(compile(source,str(path),'exec'),{'__file__':str(path),'__name__':'__main__'})
