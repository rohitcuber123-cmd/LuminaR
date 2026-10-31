"""Read-only cached embedding + existing local global snapshot probe.

Never initializes native engine/IndexManager (which can open writer queues).
No Mongo, private records, new weights, training, index writes or relevance oracle.
"""
import os,sys,json,time,hashlib,math
from pathlib import Path
os.environ.setdefault('USERNAME','v10-read-only-probe')

def main():
    json.loads(sys.stdin.readline())
    start=time.perf_counter()
    import torch,numpy as np,faiss
    from sentence_transformers import SentenceTransformer
    torch.set_num_threads(2);faiss.omp_set_num_threads(2)
    root=Path(__file__).resolve().parents[1]
    index_root=root/'local-data/search-index'
    pointer=json.loads((index_root/'active_index.json').read_text())
    version=pointer['version']
    if len(version)!=32 or any(c not in '0123456789abcdef' for c in version):raise ValueError('Invalid snapshot version')
    snapshot=index_root/'versions'/version
    manifest=json.loads((snapshot/'manifest.json').read_text())
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    for name,expected in manifest['checksums'].items():
        if Path(name).name!=name or sha(snapshot/name)!=expected:raise ValueError('Snapshot checksum mismatch')
    before={name:sha(snapshot/name) for name in manifest['checksums']}
    cache=Path.home()/'.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2'
    revision=(cache/'refs/main').read_text().strip();model_path=cache/'snapshots'/revision
    def read_only(event,args):
        if event in ('socket.connect','socket.bind','socket.getaddrinfo','subprocess.Popen'):raise RuntimeError('Probe forbids network/process IO')
        if event=='open':
            mode=args[1];flags=args[2]
            if isinstance(mode,str) and any(c in mode for c in 'wax+') or isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
                raise RuntimeError('Probe forbids filesystem writes')
    sys.addaudithook(read_only)
    load=time.perf_counter();model=SentenceTransformer(str(model_path),device='cpu',local_files_only=True);model.max_seq_length=256
    load_ms=(time.perf_counter()-load)*1000
    d=hashlib.sha256(b'all-MiniLM-L6-v2:normalize:256')
    for name,tensor in model.state_dict().items():
        d.update(name.encode());d.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    d.update(json.dumps(model.tokenizer.get_vocab(),sort_keys=True).encode())
    fingerprint='all-MiniLM-L6-v2:'+d.hexdigest()
    if fingerprint!=manifest['model_version']:raise ValueError('Embedding/index fingerprint mismatch')
    base=faiss.read_index(str(snapshot/'base.index'));delta=faiss.read_index(str(snapshot/'delta.index'))
    ids=np.load(snapshot/'base_ids.npy',allow_pickle=False)
    assert base.d==384 and base.ntotal==len(ids)
    latencies=[];observations=[]
    for query in ['books for learning Java','historical mysteries','distributed systems with practical examples','transformer architectures']*3:
        t=time.perf_counter();vector=model.encode([query],normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False)
        encoded=(time.perf_counter()-t)*1000
        assert vector.shape==(1,384) and np.isfinite(vector).all()
        t=time.perf_counter();scores,labels=base.search(np.asarray(vector,dtype=np.float32),min(5,base.ntotal));index_ms=(time.perf_counter()-t)*1000
        assert np.isfinite(scores).all() and all(0<=i<len(ids) for i in labels[0])
        latencies.append(encoded);observations.append(dict(query=query,embedding_ms=encoded,index_ms=index_ms,returned=len(labels[0])))
    assert all(sha(snapshot/name)==h for name,h in before.items())
    print(json.dumps(dict(event='embedding_probe',status='PASS_READ_ONLY_COMPONENT',model_revision=revision,
        model_fingerprint=fingerprint,index_version=version,index_vectors=base.ntotal,delta_vectors=delta.ntotal,
        model_load_ms=load_ms,wall_ms=(time.perf_counter()-start)*1000,observations=observations,
        real_embedding=True,real_local_snapshot=True,configured_service_verified=False,
        relevance='UNVERIFIED_NO_INDEPENDENT_BOOK_JUDGMENTS',full_catalog='UNVERIFIED_LOCAL_SNAPSHOT_HAS_12_VECTORS',
        source_hashes=before,mongo_calls=0,network_calls=0,index_writes=0,private_data_used=False)))

if __name__=='__main__':main()
