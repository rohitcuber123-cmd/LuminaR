"""Isolated O.1 Mongo scope, no current deployment change."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2o_fixture.py').read_text().replace('v2o','v2o1')
exec(compile(source,str(ROOT/'scripts/institution_v2o_fixture.py'),'exec'))
