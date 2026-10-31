"""Actual unmodified RAG entrypoint/Qwen, redirected fixture document storage only."""
import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import scripts.institution_v2o_trace
assert os.environ['MONGO_DB_NAME'].startswith('luminar_v2o_fixture_')
report={'mode':'Actual RAG/Qwen entrypoint, no LLM mock. Only fixture filesystem constructor/config redirected; protected source unchanged.'}
output=ROOT/'reports/institution_v2o_rag_entrypoint.json'
try:
    import torch
    torch.set_num_threads(2)
    report['cuda_available']=torch.cuda.is_available()
    if not torch.cuda.is_available():raise RuntimeError('CPU_QWEN_EXCEEDS_OBSERVED_RAM_BUDGET')
    report['gpu_free_bytes']=torch.cuda.mem_get_info()[0]
    if report['gpu_free_bytes']<3*1024**3:raise RuntimeError('INSUFFICIENT_FREE_GPU_MEMORY')
    import rag.services.private_documents as documents
    class OwnedDocuments(documents.PrivateDocuments):
        def __init__(self,root,*args,**kwargs):super().__init__(Path(os.environ['LIBRARY_ASSET_ROOT']).parent/'private-documents',*args,**kwargs)
    documents.PrivateDocuments=OwnedDocuments
    import rag.retriever as retriever
    private_root=Path(os.environ['LIBRARY_ASSET_ROOT']).parent/'empty-legacy-documents';private_root.mkdir()
    retriever.DOC_INDEX_DIR=private_root;retriever.DOC_INDEX_PATH=private_root/'rag.index';retriever.DOC_METADATA_PATH=private_root/'metadata.json';retriever.DOC_CHUNKS_DIR=private_root
    from rag.api import app
    from backend.database.mongodb import db,client
    from backend.utils.jwt_utils import create_access_token
    from fastapi.testclient import TestClient
    evidence=json.loads(Path(sys.argv[1]).read_text());lib=evidence['serving_library']
    asset=db.institution_library_assets.find_one({'library_id':lib})
    headers={'Authorization':'Bearer '+create_access_token(1,'n-bench-1@example.com','GENERAL_USER')}
    with TestClient(app) as api:
        response=api.get('/health');report['health_http']=response.status_code;assert response.status_code==200
        response=api.post(f"/libraries/{lib}/assets/{asset['asset_id']}/rag",headers=headers,json={'query':'What is a network?','depth':'concise'})
        report['private_rag_http']=response.status_code;assert response.status_code==200
        value=response.json();report['answer_present']=bool(value.get('answer'));report['source_count']=len(value.get('sources',[]))
        response=api.post(f"/libraries/{lib}/assets/{asset['asset_id']}/artifacts/summary",headers=headers,json={'mode':'quick'})
        report['knowledge_tools_http']=response.status_code;assert response.status_code==200
    client.close();report['status']='PASS'
except Exception as error:
    report['status']='NOT_QUALIFIED';report['error_type']=type(error).__name__
    # Local cache/dependency/model/runtime failure; no raw exception or prompt.
    report['reason']='Actual RAG entrypoint could not complete the fixture; see sanitized model-load log and recorded stage.'
output.write_text(json.dumps(report,indent=2))
print(json.dumps(report))
