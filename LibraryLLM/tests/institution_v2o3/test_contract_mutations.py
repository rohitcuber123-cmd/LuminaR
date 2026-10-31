"""Retain all O.2 security mutants against the new isolated J candidate."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
source=(ROOT/'tests/institution_v2o2/test_contract_mutations.py').read_text().replace('v2o2','v2o3')
source=source.replace('rag_grounding_v2o3','rag_grounding_v2o2')
exec(compile(source,str(ROOT/'tests/institution_v2o2/test_contract_mutations.py'),'exec'))
