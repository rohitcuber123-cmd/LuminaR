"""Capture this phase before edits and preserve reports it explicitly updates."""
from pathlib import Path
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'scripts/library_catalogue_experience_baseline.py').read_text(encoding='utf8')
source = source.replace("reports/library_catalogue_experience_baseline.json", "reports/product_consistency_baseline.json")
scope = {'__file__': __file__, '__name__': '__main__'}
exec(compile(source, __file__, 'exec'), scope)
archive = ROOT / '.scratch/product_consistency_prior_reports'
archive.mkdir(parents=True, exist_ok=True)
for path in (ROOT / 'reports').glob('library_catalogue_*'):
    if path.is_file():
        shutil.copy2(path, archive / path.name)
print('Prior catalogue reports archived before the requested report updates.')
