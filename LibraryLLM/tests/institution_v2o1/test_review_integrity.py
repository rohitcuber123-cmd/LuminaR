"""Review evidence must reconstruct the protected bytes, not redefine them."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def test_recovered_original_rag_bytes_match_unchanged_frozen_hash():
    rows=json.loads((ROOT/'reports/assistant_backend_baseline/hashes.json').read_text(encoding='utf-8-sig'))
    expected=next(row['Hash'] for row in rows if Path(row['Path']).name=='qa.py')
    assert hashlib.sha256((ROOT/'reports/institution_v2o1_recovered_frozen_qa.txt').read_bytes()).hexdigest().upper()==expected


def test_frozen_review_before_copies_match_recorded_baseline():
    baseline=json.loads((ROOT/'reports/institution_v2o1_baseline.json').read_text())
    # Preserve review evidence without creating another permanent whole-page or
    # guard freeze that would reject a later explicitly approved contract patch.
    for name in ['rag/qa.py','tests/test_assistant_backend.py','tests/institution_v2j/test_diagnostics.py',
                 'frontend/src/pages/LibraryIntelligence.tsx','frontend/src/lib/libraryIntelligence.ts',
                 'search/library_intelligence.py','search/library_intelligence_api.py']:
        before=ROOT/'.scratch/institution-v2o1/before'/name
        assert hashlib.sha256(before.read_bytes()).hexdigest()==baseline['source_sha256'][name]
