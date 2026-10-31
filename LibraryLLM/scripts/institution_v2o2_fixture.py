"""Task-owned O.2 authenticated Mongo fixture, never production cutover."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2o1_fixture.py').read_text().replace('v2o1','v2o2')
exec(compile(source,str(ROOT/'scripts/institution_v2o1_fixture.py'),'exec'))
