"""Owned authenticated fixture for preserved O.3 progress behavior only."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2o1_fixture.py').read_text(encoding='utf8').replace('v2o1','v2p_intelligence')
exec(compile(source,str(ROOT/'scripts/institution_v2o1_fixture.py'),'exec'))
