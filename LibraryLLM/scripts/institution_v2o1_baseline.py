"""Immutable O.1 source/data/reports checkpoint, no runtime imports or writes."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'scripts/institution_v2l_baseline.py'
source=path.read_text().replace('institution_v2l','institution_v2o1').replace('institution-v2l','institution-v2o1')
source=source.replace("['institution_v2i_','institution_v2j_','institution_v2k_']", "['institution_v2i_','institution_v2j_','institution_v2k_','institution_v2l_','institution_v2m_','institution_v2n_','institution_v2o_']")
source=source.replace("'scratch/institution_v2k_telemetry/observer.py']:", "'scratch/institution_v2k_telemetry/observer.py','frontend/src/pages/LibraryIntelligence.tsx','frontend/src/lib/libraryIntelligence.ts','tests/institution_v2j/test_diagnostics.py','tests/test_assistant_backend.py','reports/assistant_backend_baseline/hashes.json','rag/qa.py']:")
source=source.replace('Fresh baseline suites finish before editing native/K files. Native integration disabled by default.', 'O.1 investigation and proposed contract patches only. No protected contract/source/test/hash edit or product feature, cutover, telemetry or rebuild authorized.')
exec(compile(source,str(path),'exec'),{'__file__':__file__,'__name__':'__main__'})
