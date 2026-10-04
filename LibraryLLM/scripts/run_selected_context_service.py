"""Local selected-context audit runner; one resident model, unchanged settings."""
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
baseline = '--baseline' in sys.argv
phase = 'before' if baseline else 'after'
os.environ['ASSISTANT_PROFILE_PATH'] = str(ROOT / f'reports/assistant_selected_{phase}_profiles.jsonl')
if baseline:
    for name in ('routing', 'kg_routing', 'orchestrator'):
        spec = importlib.util.spec_from_file_location('assistant.' + name,
            ROOT / 'reports/assistant_selected_source_baseline/assistant' / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        sys.modules['assistant.' + name] = module
        spec.loader.exec_module(module)

import assistant.api
from assistant.profiling import current

Original = assistant.api.AssistantOrchestrator
class AuditOrchestrator(Original):
    async def resolve(self, request, parsed, state, tools, optional=False):
        # Explicit local audit only. No auth headers, private account records or
        # document content. Normal application logs stay unchanged.
        row = {'trace_id': (current.get() or {}).get('trace_id'),
               'message': request.message, 'selected_work_ids': request.selected_work_ids,
               'parsed': parsed.model_dump(mode='json'), 'title_resolution': [], 'search': []}
        original_resolve, original_search = tools.catalogue.resolve, tools.search.search
        async def resolve(title, author):
            row['title_resolution'].append({'title': title, 'author': author})
            return await original_resolve(title, author)
        async def search(query, count):
            row['search'].append({'query': query, 'count': count})
            return await original_search(query, count)
        tools.catalogue.resolve, tools.search.search = resolve, search
        try:
            return await super().resolve(request, parsed, state, tools, optional)
        finally:
            tools.catalogue.resolve, tools.search.search = original_resolve, original_search
            with (ROOT / f'reports/assistant_selected_{phase}_resolver.jsonl').open('a',encoding='utf8') as handle:
                handle.write(json.dumps(row) + '\n')
assistant.api.AssistantOrchestrator = AuditOrchestrator

import uvicorn
uvicorn.run('rag.api:app', host='127.0.0.1', port=8005, workers=1)
