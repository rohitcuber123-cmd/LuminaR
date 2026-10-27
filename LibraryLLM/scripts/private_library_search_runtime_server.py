"""Explicit loopback audit launch; wraps real FAISS, never substitutes ranking."""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['SEARCH_GLOBAL_READ_ONLY']='1'
os.environ['LUMINAR_SEARCH_QA_OUTPUT']='.scratch/private-library/search-events.jsonl'
from scripts import search_runtime_audit_server as qa
qa.ALLOWED.clear()
qa.ALLOWED.update({'Aster Vale Restricted Archive Orchid 731','Community archive preservation','getting around when walking is difficult'})
if __name__=='__main__':
    import uvicorn
    uvicorn.run(qa.api.app,host='127.0.0.1',port=8003)
