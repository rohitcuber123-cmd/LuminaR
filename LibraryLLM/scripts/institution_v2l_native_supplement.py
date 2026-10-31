"""Reuse accepted K explicit recovery/A-B-C workflows against the native observer seam."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2k_native_supplement.py').read_text(encoding='utf8')
source=source.replace('from scratch.institution_v2k_telemetry.telemetry import COLLECTION,SLOT,digest','from backend.services.library_worker_telemetry import COLLECTION,SLOT,digest')
source=source.replace('from scratch.institution_v2k_telemetry.observer import classify,inspect_telemetry','from backend.services.library_worker_diagnostics import classify,inspect_telemetry')
source=source.replace('V2K','V2L').replace('v2k','v2l')
exec(compile(source,str(ROOT/'scripts/institution_v2k_native_supplement.py'),'exec'),{'__file__':str(Path(__file__).resolve()),'__name__':'__main__'})
