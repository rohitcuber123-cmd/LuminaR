"""Repeat accepted read-only host audit into new evidence; no live mutations."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'scripts/institution_v2m_host_audit.py').read_text(encoding='utf8')
source = source.replace("reports/institution_v2m_host_audit.json", "reports/institution_v2n_host_audit.json")
exec(compile(source, str(ROOT / 'scripts/institution_v2m_host_audit.py'), 'exec'), {'__file__': __file__, '__name__': '__main__'})
