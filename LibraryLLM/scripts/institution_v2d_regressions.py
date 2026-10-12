"""Frozen suite runners, new evidence prefix, no Router research."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
frontend='--frontend' in sys.argv
original=ROOT/'scripts'/('test_full_product_frontend.py' if frontend else 'test_full_product_regressions.py')
source=original.read_text(encoding='utf8')
if frontend:
    source=source.replace('full_product_frontend_','institution_v2d_frontend_')
    if '--resume' in sys.argv:
        source=source.replace('results = []', "results = json.loads((REPORTS / 'institution_v2d_frontend_results.json').read_text(encoding='utf8')) if (REPORTS / 'institution_v2d_frontend_results.json').exists() else []\n    results = [row for row in results if row['exit'] == 0]\n    runs = [run for run in runs if run[0] not in {row['group'] for row in results}]")
else:
    source=source.replace('full_product_regression','institution_v2d_regression')
    source=source.replace('.scratch/full-product/events_regression.py','.scratch/institution-v2d/events_regression.py')
sys.argv=[str(original)]+[arg for arg in sys.argv[1:] if arg!='--frontend']
exec(compile(source,str(original),'exec'),{'__file__':str(original),'__name__':'__main__'})
