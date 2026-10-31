"""Read-only O checkpoint before UX/auth/runtime edits; includes frozen N evidence."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'scripts/institution_v2l_baseline.py'
source=path.read_text(encoding='utf8').replace('institution_v2l','institution_v2o').replace('institution-v2l','institution-v2o')
source=source.replace("['institution_v2i_','institution_v2j_','institution_v2k_']", "['institution_v2i_','institution_v2j_','institution_v2k_','institution_v2l_','institution_v2m_','institution_v2n_']")
source=source.replace("'scratch/institution_v2k_telemetry/observer.py']:", "'scratch/institution_v2k_telemetry/observer.py','backend/database/mongo_configuration.py','backend/database/mongodb.py','search/luminar_search.py','search/maintenance.py','search/api.py','frontend/src/pages/LibraryIntelligence.tsx','frontend/src/pages/LibraryIntelligence.css','frontend/src/lib/libraryIntelligence.ts']:")
source=source.replace('Fresh baseline suites finish before editing native/K files. Native integration disabled by default.', 'O readiness/UX and regression investigation. No live cutover/credential/ACL/firewall/telemetry/global rebuild; owned synthetic fixtures only.')
exec(compile(source,str(path),'exec'),{'__file__':__file__,'__name__':'__main__'})
