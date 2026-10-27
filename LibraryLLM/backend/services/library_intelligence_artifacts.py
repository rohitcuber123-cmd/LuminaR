"""Bounded immutable tenant HNSW/metadata graphs; no global paths or model loads."""
from collections import OrderedDict
from threading import RLock
from pathlib import Path
import hashlib,json,os,sqlite3,time
from fastapi import HTTPException
from knowledge_graph.core import canonical as term_key,feature_id,terms
from knowledge_graph.relations import RELATIONS
from search.catalogue import semantic_text
from backend.services import library_intelligence_store as store

PARAMETERS={'M':16,'efConstruction':80,'efSearch':64,'candidate_count':120,'reranking_count':60}
MAX_ARTIFACT_BYTES=256*1024*1024
def embedding_text(record):
    return semantic_text({**record,'first_publish_date':record.get('publication_year')})
def cache_key(record,model_version):
    return hashlib.sha256(store.encoded([model_version,store.SCHEMA,embedding_text(record)])).hexdigest()
class VectorCache:
    """Separate tenant-root content-addressed cache; never the global work cache."""
    def __init__(self,library_id,model_version):
        self.library_id=store.canonical(library_id);self.model_version=model_version
        path=store.root()/self.library_id;path.mkdir(parents=True,exist_ok=True)
        if path.resolve()!=path:raise HTTPException(404,'Artifact namespace is invalid.')
        self.path=path/'embedding-cache.sqlite'
        if self.path.resolve()!=self.path:raise HTTPException(404,'Artifact namespace is invalid.')
        with sqlite3.connect(self.path) as db:db.execute('CREATE TABLE IF NOT EXISTS vectors(key TEXT PRIMARY KEY,vector BLOB NOT NULL,checksum TEXT NOT NULL)')
    def get(self,record):
        import numpy as np
        key=cache_key(record,self.model_version)
        with sqlite3.connect(self.path) as db:row=db.execute('SELECT vector,checksum FROM vectors WHERE key=?',(key,)).fetchone()
        if not row:return None
        if hashlib.sha256(row[0]).hexdigest()!=row[1]:raise HTTPException(409,'EMBEDDING_CACHE_CORRUPT')
        vector=np.frombuffer(row[0],dtype=np.float32).copy()
        if vector.shape!=(384,) or not np.isfinite(vector).all() or abs(float(np.linalg.norm(vector))-1)>.001:raise HTTPException(409,'EMBEDDING_CACHE_CORRUPT')
        return vector
    def put(self,record,vector):
        content=vector.tobytes()
        with sqlite3.connect(self.path) as db:db.execute('INSERT OR IGNORE INTO vectors VALUES(?,?,?)',(cache_key(record,self.model_version),content,hashlib.sha256(content).hexdigest()))
def build_search(path,records,encoder,model_version,library_id,progress,fail):
    import numpy as np
    import faiss
    if not records:return {'empty':True,'vector_count':0,'model':store.MODEL,'model_version':model_version,'dimension':384,'parameters':PARAMETERS}
    vectors=np.zeros((len(records),384),dtype=np.float32)
    fail('EMBEDDING_CACHE');cache=VectorCache(library_id,model_version)
    for offset in range(0,len(records),32):
        progress('EMBEDDING',offset,len(records));missing=[]
        for i in range(offset,min(offset+32,len(records))):
            value=cache.get(records[i])
            if value is None:missing.append(i)
            else:vectors[i]=value
        if missing:
            fail('EMBEDDING_BATCH')
            result=np.asarray(encoder([embedding_text(records[i]) for i in missing]),dtype=np.float32)
            if result.shape!=(len(missing),384) or not np.isfinite(result).all():raise HTTPException(409,'EMBEDDING_INVALID')
            norms=np.linalg.norm(result,axis=1)
            if np.any(norms<1e-8):raise HTTPException(409,'EMBEDDING_INVALID')
            result/=norms[:,None]
            for i,value in zip(missing,result):cache.put(records[i],value);vectors[i]=value
    fail('FAISS_BUILD');index=faiss.IndexHNSWFlat(384,PARAMETERS['M'],faiss.METRIC_INNER_PRODUCT)
    index.hnsw.efConstruction=PARAMETERS['efConstruction'];index.hnsw.efSearch=PARAMETERS['efSearch'];index.add(vectors)
    fail('FAISS_SERIALIZATION');faiss.write_index(index,str(path/'index.faiss'));np.save(path/'vectors.npy',vectors,allow_pickle=False)
    return {'empty':False,'vector_count':len(records),'model':store.MODEL,'model_version':model_version,'dimension':384,'normalized':True,'parameters':PARAMETERS}
def build_graph(path,records,progress,fail):
    nodes={};edges=[]
    for i,book in enumerate(records):
        fail('KG_NODES');bid=book['library_book_id'];book_node='book:'+bid
        nodes[book_node]={'id':book_node,'type':'Book','label':book['title'],'library_book_id':bid,'global_work_id':book.get('global_work_id')}
        for kind,field in [('author','authors'),('subject','subjects'),('classification','classification')]:
            source=book.get(field);source=[source] if kind=='classification' and source else source
            for key,label in terms(source).items():
                node_id=feature_id(kind,key)
                nodes.setdefault(node_id,{'id':node_id,'type':kind.title(),'label':label})
                fail('KG_EDGES');edges.append({'source':book_node,'target':node_id,'relation':RELATIONS[kind][0] if kind in RELATIONS else 'HAS_CLASSIFICATION'})
        if i%100==0:progress('KG_METADATA',i,len(records))
    graph={'nodes':sorted(nodes.values(),key=lambda n:n['id']),'edges':sorted(edges,key=lambda e:(e['source'],e['target'],e['relation']))}
    fail('KG_SERIALIZATION');store.durable_json(path/'graph.json',graph)
    return {'node_count':len(nodes),'edge_count':len(edges),'book_count':len(records),'deterministic':True}
def expected_files(target,manifest):
    return {'metadata.json'}|({'index.faiss','vectors.npy'} if target=='SEARCH_INDEX' and not manifest.get('empty') else {'graph.json'} if target=='KNOWLEDGE_GRAPH' else set())
def validate(library_id,target,generation_id,dataset=None,path=None):
    path=path or store.directory(library_id,'search' if target=='SEARCH_INDEX' else 'kg',generation_id)
    if path.resolve()!=path:raise HTTPException(409,'ARTIFACT_CORRUPT')
    try:
        manifest=json.loads((path/'manifest.json').read_text(encoding='utf8'))
        if manifest['library_id']!=store.canonical(library_id) or manifest['generation_id']!=store.canonical(generation_id) or manifest['target']!=target or manifest['schema_version']!=store.SCHEMA:raise ValueError()
        if set(manifest['files'])!=expected_files(target,manifest):raise ValueError()
        for name,expected in manifest['files'].items():
            file=path/name
            if file.resolve()!=file or not file.is_file() or file.stat().st_size>MAX_ARTIFACT_BYTES or store.checksum(file)!=expected:raise ValueError()
        records=json.loads((path/'metadata.json').read_text(encoding='utf8'))
        if len(records)!=manifest['book_count'] or len({r['library_book_id'] for r in records})!=len(records) or any(r['library_id']!=library_id or r['status']!='ACTIVE' or set(r)!=set(store.SOURCE_FIELDS) for r in records):raise ValueError()
        if store.fingerprint(records)!=manifest['source_fingerprint']:raise ValueError()
        source=store.collection('intelligence_generations').find_one({'library_id':library_id,'generation_id':manifest['source_generation_id'],'status':'READY'})
        if not source or source['source_fingerprint']!=manifest['source_fingerprint']:raise ValueError()
        dataset_path=store.directory(library_id,'datasets',source['generation_id'])
        if store.checksum(dataset_path/'manifest.json')!=source['manifest_checksum'] or store.checksum(dataset_path/'records.json')!=source['records_checksum']:raise ValueError()
        if dataset is not None and records!=dataset:raise ValueError()
        ids={r['library_book_id'] for r in records}
        owned={r['library_book_id'] for r in store.collection('library_books').find({'library_id':library_id,'library_book_id':{'$in':list(ids)}},{'library_book_id':1})}
        if ids!=owned:raise ValueError()
        if target=='SEARCH_INDEX':
            import numpy as np
            import faiss
            if manifest['model']!=store.MODEL or manifest['dimension']!=384 or manifest['vector_count']!=len(records) or manifest.get('parameters')!=PARAMETERS or not isinstance(manifest.get('model_version'),str) or not manifest['model_version']:raise ValueError()
            if manifest.get('empty'):
                if records:raise ValueError()
                return manifest,records,None
            index=faiss.read_index(str(path/'index.faiss'));vectors=np.load(path/'vectors.npy',allow_pickle=False)
            if not isinstance(index,faiss.IndexHNSWFlat) or index.metric_type!=faiss.METRIC_INNER_PRODUCT or index.d!=384 or index.ntotal!=len(records) or vectors.shape!=(len(records),384) or vectors.dtype!=np.float32 or not np.isfinite(vectors).all():raise ValueError()
            if not np.allclose(np.linalg.norm(vectors,axis=1),1,atol=.001):raise ValueError()
            if not np.allclose(index.reconstruct_n(0,len(records)),vectors,atol=.00001):raise ValueError()
            if index.hnsw.efConstruction!=PARAMETERS['efConstruction'] or index.hnsw.efSearch!=PARAMETERS['efSearch'] or index.hnsw.nb_neighbors(1)!=PARAMETERS['M']:raise ValueError()
            return manifest,records,index
        graph=json.loads((path/'graph.json').read_text(encoding='utf8'));nodes={n['id']:n for n in graph['nodes']}
        if len(nodes)!=len(graph['nodes']) or len(nodes)!=manifest['node_count'] or len(graph['edges'])!=manifest['edge_count']:raise ValueError()
        if {n['library_book_id'] for n in nodes.values() if n['type']=='Book'}!=ids:raise ValueError()
        if any(n['type'] not in {'Book','Author','Subject','Classification'} for n in nodes.values()):raise ValueError()
        if len({(e['source'],e['target'],e['relation']) for e in graph['edges']})!=len(graph['edges']) or any(e['source'] not in nodes or e['target'] not in nodes or nodes[e['source']]['type']!='Book' for e in graph['edges']):raise ValueError()
        expected_nodes={};expected_edges=set()
        for book in records:
            bid='book:'+book['library_book_id']
            expected_nodes[bid]={'id':bid,'type':'Book','label':book['title'],'library_book_id':book['library_book_id'],'global_work_id':book.get('global_work_id')}
            for kind,field in [('author','authors'),('subject','subjects'),('classification','classification')]:
                values=book.get(field);values=[values] if kind=='classification' and values else values
                for key,label in terms(values).items():
                    fid=feature_id(kind,key);expected_nodes.setdefault(fid,{'id':fid,'type':kind.title(),'label':label})
                    expected_edges.add((bid,fid,RELATIONS[kind][0] if kind in RELATIONS else 'HAS_CLASSIFICATION'))
        if nodes!=expected_nodes or {(e['source'],e['target'],e['relation']) for e in graph['edges']}!=expected_edges:raise ValueError()
        return manifest,records,graph
    except HTTPException:raise
    except Exception as error:raise HTTPException(409,'ARTIFACT_CORRUPT') from error
class ArtifactCache:
    def __init__(self,max_entries=3,max_bytes=256*1024*1024):self.entries=OrderedDict();self.lock=RLock();self.max_entries=max_entries;self.max_bytes=max_bytes;self.loads=0;self.evictions=0
    def clear(self):
        with self.lock:self.entries.clear()
    def load(self,library_id,target,generation_id,manifest_checksum):
        key=(library_id,generation_id,target)
        with self.lock:
            path=store.directory(library_id,'search' if target=='SEARCH_INDEX' else 'kg',generation_id)
            if store.checksum(path/'manifest.json')!=manifest_checksum:raise HTTPException(409,'ARTIFACT_CORRUPT')
            if key in self.entries:
                value,size=self.entries[key]
                for name,digest in value[0]['files'].items():
                    file=path/name
                    if file.resolve()!=file or store.checksum(file)!=digest:
                        self.entries.pop(key);raise HTTPException(409,'ARTIFACT_CORRUPT')
                self.entries.move_to_end(key);return value
            value=validate(library_id,target,generation_id)
            # Bound retained Python metadata/graph objects as well as native
            # HNSW storage. Serialized JSON alone underestimates resident RAM.
            import sys
            seen=set()
            def retained_size(item):
                identity=id(item)
                if identity in seen:return 0
                seen.add(identity);size=sys.getsizeof(item)
                if isinstance(item,dict):size+=sum(retained_size(k)+retained_size(v) for k,v in item.items())
                elif isinstance(item,(list,tuple)):size+=sum(retained_size(v) for v in item)
                return size
            size=retained_size(value[:2])+((path/'index.faiss').stat().st_size if target=='SEARCH_INDEX' and value[2] is not None else retained_size(value[2]))
            if size>self.max_bytes:raise HTTPException(503,'TENANT_CACHE_LIMIT')
            while self.entries and (len(self.entries)>=self.max_entries or sum(v[1] for v in self.entries.values())+size>self.max_bytes):self.entries.popitem(last=False);self.evictions+=1
            self.entries[key]=(value,size);self.loads+=1;return value
    def metrics(self):
        with self.lock:return {'entries':len(self.entries),'retained_bytes_estimate':sum(v[1] for v in self.entries.values()),'limit_bytes':self.max_bytes,'limit_entries':self.max_entries,'loads':self.loads,'evictions':self.evictions,'keys':[list(k) for k in self.entries]}
