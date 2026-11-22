import asyncio, json, os, time, threading, traceback
from pathlib import Path
os.environ.update(LUMINAR_MOCK_LLM='0', LUMINAR_DEBUG_PROMPT='0', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
import torch
from rag.llm import LuminaRLLM
from assistant.qwen import QwenGateway
out={}
try:
 t=time.perf_counter(); llm=LuminaRLLM(); out['load_seconds_including_warmup']=time.perf_counter()-t
 out['model_commit']=getattr(llm.model.config,'_commit_hash',None); out['tokenizer_commit']=llm.tokenizer.init_kwargs.get('_commit_hash'); out['model_path']=llm.tokenizer.name_or_path
 out['quantization']=str(getattr(llm.model.config,'quantization_config',None)); out['is_loaded_in_4bit']=getattr(llm.model,'is_loaded_in_4bit',None); out['parameter_device']=str(next(llm.model.parameters()).device); out['parameter_dtype']=str(next(llm.model.parameters()).dtype)
 async def run():
  g=QwenGateway(llm,threading.RLock(),timeout=90,allow_experimental=False)
  for key,query in [('intent','Find books about astronomy'),('clarification','Is it available?')]:
   try:
    t=time.perf_counter(); d=await g.parse(query,{}); out[key]={'status':'PASS','seconds':time.perf_counter()-t,'decision':d.model_dump(mode='json')}
   except Exception as e: out[key]={'status':'FAIL','error':type(e).__name__}
  g.close()
 asyncio.run(run()); out['peak_gpu_allocated_bytes']=torch.cuda.max_memory_allocated()
except Exception as e:
 out['error']=type(e).__name__; out['traceback']=traceback.format_exc()
Path('reports/module15_gpu_verification/native_probe.json').write_text(json.dumps(out,indent=2,default=str),encoding='utf-8')
