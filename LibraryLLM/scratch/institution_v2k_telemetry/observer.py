"""Part2K fixture-only read facade over the single canonical implementation."""
from backend.services.library_worker_diagnostics import classify
from backend.services.library_worker_diagnostics import inspect_telemetry as _inspect


def inspect_telemetry(reader,library_id,*,stale_seconds=30):
    return _inspect(reader,library_id,stale_seconds=stale_seconds,fixture_only=True)
