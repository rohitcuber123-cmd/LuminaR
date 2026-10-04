"""Mock-free accuracy reports, recorded-output replay for prompt/contract parity.

This checks production prompts and decoding schemas, not model accuracy. No
Qwen model is loaded, and captured outputs are never stored in production code.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
from threading import RLock
from unittest.mock import AsyncMock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import evaluate_assistant_semantics as fixtures
from assistant import schemas, tools as tool_module
from assistant.qwen import QwenGateway
from assistant.orchestrator import AssistantOrchestrator
from assistant.state import ConversationStore
from assistant.semantic import router_context


async def main():
    matrix=json.loads((ROOT/'reports/assistant_router_v2_experiments.json').read_text())
    results={}
    for label,meta in matrix['variants'].items():
        report=json.loads((ROOT/'reports'/meta['case_report']).read_text())
        assert report['complete']
        os.environ['ASSISTANT_ROUTER_V2_VARIANT']=meta['architecture']
        os.environ['ASSISTANT_ROUTER_V2_RETRY']='1' if meta['retry'] else '0'
        verified=0;failures=[]
        for row in report['cases']:
            gateway=QwenGateway(None,RLock());observed=[]
            async def generate(prompt,schema,stage):
                observed.append({'prompt':hashlib.sha256(prompt.encode()).hexdigest(),
                    'schema':hashlib.sha256(json.dumps(schema.model_json_schema(),sort_keys=True).encode()).hexdigest()})
                return row['raw_output'][len(observed)-1]
            gateway.generate=generate
            orch=AssistantOrchestrator(gateway,ConversationStore())
            tool=fixtures.FixtureTools(schemas,tool_module)
            request=fixtures.establish(orch,row,schemas)
            state=orch.store.entries[request.conversation_id]
            ctx=await router_context(request,state,tool)
            try:
                result=await gateway.parse(row['message'],ctx)
                # D/E report hashes track the last (potentially retry) call;
                # legacy reports track the first call.
                target=observed[-1 if meta['architecture'] in {'D','E','E2'} else 0]
                okay=target['prompt']==row['prompt_sha256'] and target['schema']==row['schema_sha256']
                okay=okay and result.model_dump(mode='json')==row['semantic_decision'] and len(observed)==len(row['raw_output'])
                if okay:verified+=1
                else:failures.append(row['index'])
            finally:gateway.close()
        results[label]={'verified':verified,'total':len(report['cases']),'failures':failures}
    path=ROOT/'reports/assistant_router_v2_prompt_parity.json'
    path.write_text(json.dumps({'method':'Recorded-output replay of exact production gateway; a contract check, not an accuracy evaluation',
        'variants':results,'pass':all(not r['failures'] for r in results.values())},indent=2),encoding='utf8')
    print(json.dumps(results,indent=2))


if __name__=='__main__':asyncio.run(main())
