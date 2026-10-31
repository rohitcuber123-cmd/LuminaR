"""Unmodified product suite inventory through M plus new N tests, separate outputs."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];path=ROOT/'scripts/institution_v2i_checks.py'
source=path.read_text(encoding='utf8').replace('reports/institution_v2i_','reports/institution_v2n_').replace('.scratch/institution-v2i/','.scratch/institution-v2n/')
source=source.replace("f'institution_v2i_{a.tag}_generated_","f'institution_v2n_{a.tag}_generated_")
source=source.replace("if tag != 'baseline' and (ROOT / 'tests/institution_v2i').exists():","if (ROOT / 'tests/institution_v2i').exists():")
source=source.replace("groups['institution_v2i'] = ['tests/institution_v2i']","groups['institution_v2i'] = ['tests/institution_v2i']\n"+
    '\n'.join("    groups['institution_"+v+"'] = ['tests/institution_"+v+"']" for v in ['v2j','v2k','v2l','v2m'])+"\n    if (ROOT / 'tests/institution_v2n').exists():\n        groups['institution_v2n'] = ['tests/institution_v2n']")
exec(compile(source,str(path),'exec'),{'__file__':str(path),'__name__':'__main__'})
