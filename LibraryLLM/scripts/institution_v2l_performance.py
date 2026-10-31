"""Reuse exact accepted K paired diagnostic fixture workloads with integrated primitives."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2k_performance.py').read_text(encoding='utf8')
source=source.replace('scripts.institution_v2k_fixture','scripts.institution_v2l_fixture').replace('reports/institution_v2k_','reports/institution_v2l_')
source=source.replace('from scratch.institution_v2k_telemetry.telemetry import Actor,COLLECTION,SLOT',
    'from backend.services.library_worker_telemetry import COLLECTION,SLOT\nfrom backend.services.library_worker_observer import RestrictedWriter,Configuration\ndef Actor(uri,database,owner):return RestrictedWriter(Configuration(database,uri),owner)')
source=source.replace('from scratch.institution_v2k_telemetry.observer import inspect_telemetry','from backend.services.library_worker_diagnostics import inspect_telemetry')
exec(compile(source,str(ROOT/'scripts/institution_v2k_performance.py'),'exec'),{'__file__':str(Path(__file__).resolve()),'__name__':'__main__'})
