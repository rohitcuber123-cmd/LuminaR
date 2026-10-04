"""Local synthetic generation diagnostic; loads only the existing RAG engine."""
import asyncio
import os
from pathlib import Path
import sys
import socket
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['LUMINAR_MOCK_LLM'] = '0'
with socket.socket() as probe:
    probe.settimeout(.2)
    if probe.connect_ex(('127.0.0.1', 8005)) == 0:
        raise RuntimeError('Qwen service 8005 is running; diagnostic will not load another copy.')
from rag.api import app


async def main():
    try:
        result = await app.state.assistant.qwen.parse('Find books about neural networks', {})
        print('PARSED', result.model_dump_json(), flush=True)
    except Exception:
        traceback.print_exc()
    finally:
        app.state.assistant.qwen.close()


asyncio.run(main())
