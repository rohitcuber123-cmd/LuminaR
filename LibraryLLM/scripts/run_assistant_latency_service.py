"""Benchmark-only runner for the frozen pre-optimization orchestrator.

Uses the exact saved Part 2 source and current numeric observation adapters.
This is not a production configuration or a second model loader.
"""
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if '--baseline' in sys.argv:
    import assistant.api
    from assistant.profiling import measured
    source = ROOT / 'reports/assistant_latency_source_baseline/assistant/orchestrator.py'
    spec = importlib.util.spec_from_file_location('frozen_assistant_orchestrator', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cls = module.AssistantOrchestrator
    cls.resolve = measured('entity_resolution')(cls.resolve)
    cls.route = measured('tool_execution')(cls.route)
    assistant.api.AssistantOrchestrator = cls

import uvicorn
uvicorn.run('rag.api:app', host='127.0.0.1', port=8005, workers=1)
