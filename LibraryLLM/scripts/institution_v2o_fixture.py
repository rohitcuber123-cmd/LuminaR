"""Owned O server/identities reuse accepted isolated N fixture, never live Mongo."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2n_fixture.py').read_text(encoding='utf8').replace('v2n','v2o')
# Role discovery uses the frozen N repository inventory as source input only.
source=source.replace('institution_v2o_client_inventory_baseline.json','institution_v2n_client_inventory_baseline.json')
exec(compile(source,str(ROOT/'scripts/institution_v2n_fixture.py'),'exec'))
