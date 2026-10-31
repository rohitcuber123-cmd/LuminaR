"""Fresh independent actual J/L CLI calls and restricted writer in owned O DB."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2n_operator.py').read_text().replace('v2n','v2o')
exec(compile(source,str(ROOT/'scripts/institution_v2n_operator.py'),'exec'),{'__file__':__file__,'__name__':'__main__'})
