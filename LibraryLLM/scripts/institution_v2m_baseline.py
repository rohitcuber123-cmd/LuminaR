"""Read-only2M freeze, reusing the accepted source/data/index capture."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'scripts/institution_v2l_baseline.py'
source=path.read_text(encoding='utf8').replace('institution_v2l','institution_v2m').replace('institution-v2l','institution-v2m')
source=source.replace("['institution_v2i_','institution_v2j_','institution_v2k_']","['institution_v2i_','institution_v2j_','institution_v2k_','institution_v2l_']")
source=source.replace("'scratch/institution_v2k_telemetry/observer.py']:",
    "'scratch/institution_v2k_telemetry/observer.py','backend/services/library_worker_telemetry.py','backend/services/library_worker_observer.py','backend/services/library_worker_diagnostics.py','backend/services/library_operator_access.py','backend/services/library_intelligence_diagnostics.py','scripts/diagnose_worker_telemetry.py','scripts/diagnose_library_intelligence.py']:")
source=source.replace('Fresh baseline suites finish before editing native/K files. Native integration disabled by default.',
    'Runtime and all previous tests/reports remain unchanged in2M. Prior2L test results form the source-verified checkpoint; fresh full2M regression is executed after new fixture tests. Production telemetry remains disabled.')
exec(compile(source,str(path),'exec'),{'__file__':str(Path(__file__).resolve()),'__name__':'__main__'})
