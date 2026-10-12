"""Reuse frozen suite runners, with new closure log names and no old-report overwrite."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
frontend='--frontend' in sys.argv
original=ROOT/'scripts'/('test_full_product_frontend.py' if frontend else 'test_full_product_regressions.py')
source=original.read_text(encoding='utf8')
if frontend:
    source=source.replace('full_product_frontend_', 'platform_completion_frontend_')
else:
    source=source.replace('full_product_regression', 'platform_completion_backend')
    source=source.replace('.scratch/full-product/events_regression.py','.scratch/platform-completion/events_regression.py')
sys.argv=[str(original)]
exec(compile(source,str(original),'exec'),{'__file__':str(original),'__name__':'__main__'})
