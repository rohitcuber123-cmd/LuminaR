"""Frozen independent-process product suites; no Router research."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
original=ROOT/'scripts/test_full_product_regressions.py'
source=original.read_text(encoding='utf8').replace('full_product_regression','institution_v2h_regression').replace('.scratch/full-product/events_regression.py','.scratch/institution-v2h/events_regression.py')
source=source.replace("groups['workspace_authorization']", "groups.update({f'institution_{v}':[f'tests/institution_{v}'] for v in ['v2d','v2e','v2f','v2g','v2h']})\ngroups['workspace_authorization']",1)
exec(compile(source,str(original),'exec'),{'__file__':str(original),'__name__':'__main__'})
