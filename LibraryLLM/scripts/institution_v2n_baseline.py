"""Read-only N checkpoint, preserving all prior phases and current client source."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];path=ROOT/'scripts/institution_v2l_baseline.py'
source=path.read_text(encoding='utf8').replace('institution_v2l','institution_v2n').replace('institution-v2l','institution-v2n')
source=source.replace("['institution_v2i_','institution_v2j_','institution_v2k_']","['institution_v2i_','institution_v2j_','institution_v2k_','institution_v2l_','institution_v2m_']")
source=source.replace("'scratch/institution_v2k_telemetry/observer.py']:","'scratch/institution_v2k_telemetry/observer.py','backend/database/mongodb.py','search/luminar_search.py','search/maintenance.py','backend/services/library_worker_telemetry.py','backend/services/library_worker_observer.py','backend/services/library_worker_diagnostics.py']:")
source=source.replace('Fresh baseline suites finish before editing native/K files. Native integration disabled by default.',
    'N source/client inventory and isolated authenticated rehearsal only; authenticated mode may be added without selecting it on the actual deployment. No live cutover/credential/ACL/service change or telemetry activation.')
exec(compile(source,str(path),'exec'),{'__file__':str(Path(__file__).resolve()),'__name__':'__main__'})
