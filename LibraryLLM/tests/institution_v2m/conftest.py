"""Reuse accepted isolated test plumbing in a new2M owned database."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
path=ROOT/'tests/institution_v2l/conftest.py'
source=path.read_text(encoding='utf8').replace('scripts.institution_v2l_fixture','scripts.institution_v2m_fixture')
exec(compile(source,str(path),'exec'),globals())
