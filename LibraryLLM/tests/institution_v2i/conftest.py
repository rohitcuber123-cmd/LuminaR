"""Reuse accepted 2H fixtures, changing only the disposable database namespace."""
from pathlib import Path

_path = Path(__file__).resolve().parents[1] / 'institution_v2h/conftest.py'
_source = _path.read_text(encoding='utf8').replace('luminar_institution_v2h_test_', 'luminar_institution_v2i_test_')
exec(compile(_source, str(_path), 'exec'))
