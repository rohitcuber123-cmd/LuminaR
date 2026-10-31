"""Fresh actual server negatives, reusing frozen N assertions in owned O scope."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
source=(ROOT/'tests/institution_v2n/test_mongo_authentication.py').read_text(encoding='utf8').replace('v2n','v2o')
exec(compile(source,str(ROOT/'tests/institution_v2n/test_mongo_authentication.py'),'exec'))
