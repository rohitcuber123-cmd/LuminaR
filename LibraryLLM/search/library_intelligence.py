"""Tenant build worker and semantic reader injected into the resident Search API."""
from threading import Event,Thread,Lock
from uuid import uuid4
import json,os,time
from fastapi import HTTPException
from backend.services import library_intelligence_store as store
from backend.services import library_intelligence_artifacts as artifacts
from backend.services import library_catalogue_experience as catalogue

class TenantIntelligence:
    def __init__(self,encoder,reranker=None,model_version=store.MODEL,cache=None,fail=None):
        self.encoder=encoder;self.reranker=reranker;self.model_version=model_version
        self.cache=cache or artifacts.ArtifactCache();self.fail=fail or (lambda stage:None)
        self.stop=Event();self.thread=None;self.model_lock=Lock();self.worker_id='tenant-'+str(uuid4())
    def start(self):
        store.initialize()
        if self.thread and self.thread.is_alive():return
        self.thread=Thread(target=self.loop,name='tenant-intelligence-worker',daemon=True);self.thread.start()
    def close(self):self.stop.set();self.cache.clear()
    def loop(self):
        while not self.stop.is_set():
            try:
                if self.run_one():continue
            except Exception:pass  # Durable state/reconciliation owns failures, never restart a publisher blindly.
            self.stop.wait(2)
    def run_one(self):
        job=store.claim(self.worker_id)
        if not job:return False
        stop=Event();lease_lost=Event()
        def renewal():
            while not stop.wait(10):
                try:
                    if not store.heartbeat(job):lease_lost.set();return
                except Exception:lease_lost.set();return
        renewer=Thread(target=renewal,daemon=True);renewer.start();published=False
        try:
            generation,records=store.dataset(job,self.fail)
            job['requested_generation_id']=generation['generation_id']
            store.collection('intelligence_jobs').update_one(store.lease_query(job),{'$set':{'requested_generation_id':generation['generation_id']}})
            kind='search' if job['target']=='SEARCH_INDEX' else 'kg'
            final=store.directory(job['library_id'],kind,job['artifact_generation_id'])
            temporary=final.with_name(final.name+'.building')
            if temporary.resolve()!=temporary:raise HTTPException(409,'ARTIFACT_NAMESPACE_INVALID')
            temporary.mkdir(parents=True,exist_ok=False)
            store.durable_json(temporary/'metadata.json',records)
            progress=lambda stage,current=0,total=0:store.progress(job,stage,current,total)
            if kind=='search':
                with self.model_lock:details=artifacts.build_search(temporary,records,self.encoder,self.model_version,job['library_id'],progress,self.fail)
            else:details=artifacts.build_graph(temporary,records,progress,self.fail)
            self.fail('CHECKSUM');files={p.name:store.checksum(p) for p in temporary.iterdir() if p.is_file()}
            manifest={'library_id':job['library_id'],'generation_id':job['artifact_generation_id'],'source_generation_id':generation['generation_id'],
                'source_fingerprint':generation['source_fingerprint'],'target':job['target'],'schema_version':store.SCHEMA,'book_count':len(records),
                'created_by_user_id':job['requested_by_user_id'],'job_id':job['job_id'],'built_at':store.now().isoformat(),'files':files,**details}
            self.fail('MANIFEST_WRITE');store.durable_json(temporary/'manifest.json',manifest)
            store.progress(job,'VALIDATION',len(records),len(records),'VALIDATING');self.fail('VALIDATION')
            artifacts.validate(job['library_id'],job['target'],job['artifact_generation_id'],records,temporary)
            self.fail('SERIALIZATION_ACK');os.replace(temporary,final)
            digest=store.checksum(final/'manifest.json')
            self.fail('HEARTBEAT')
            if lease_lost.is_set():raise HTTPException(409,'HEARTBEAT_LOSS')
            store.progress(job,'PUBLISH',len(records),len(records),'PUBLISHING')
            with store.intelligence_barrier(job['library_id'],job):
                store.check_lease(job);store.build_guard(job['library_id'],{'sub':str(job['requested_by_user_id'])},True)
                if store.fingerprint(store.source_records(job['library_id']))!=generation['source_fingerprint']:raise HTTPException(409,'SOURCE_CHANGED')
                self.fail('PUBLISH')
                previous=store.collection('intelligence_targets').find_one({'library_id':job['library_id'],'target':job['target']})
                change={'active_generation_id':job['artifact_generation_id'],'source_generation_id':generation['generation_id'],'source_fingerprint':generation['source_fingerprint'],
                    'manifest_checksum':digest,'record_count':len(records),'built_at':store.now(),'state':'EMPTY' if not records else 'READY','previous_generation_id':previous.get('active_generation_id'),
                    'published_by_job_id':job['job_id'],'node_count':details.get('node_count'),'edge_count':details.get('edge_count'),'artifact_bytes':sum(p.stat().st_size for p in final.iterdir()),'error_code':None}
                result=store.collection('intelligence_targets').update_one({'library_id':job['library_id'],'target':job['target'],'active_job_id':job['job_id'],'fence_token':job['fence_token']},{'$set':change,'$unset':{'stale_since':''}})
                if not result.matched_count:raise HTTPException(409,'WORKER_FENCED')
                published=True;self.fail('ACKNOWLEDGEMENT_LOSS')
                store.build_audit(job,'SUCCEEDED')
                if not store.collection('intelligence_jobs').update_one(store.lease_query(job),{'$set':{'state':'SUCCEEDED','stage':'COMPLETE','effective_active':False,'completed_at':store.now()}}).matched_count:raise HTTPException(409,'WORKER_FENCED')
                store.collection('intelligence_targets').update_one({'library_id':job['library_id'],'target':job['target'],'active_job_id':job['job_id']},{'$unset':{'active_job_id':'','fence_token':''}})
        except Exception as error:
            code=error.detail if isinstance(error,HTTPException) and isinstance(error.detail,str) and len(error.detail)<60 else 'BUILD_FAILED'
            unknown=published or code in ['WORKER_FENCED','WORKER_CRASH','HEARTBEAT_LOSS']
            state='RECOVERY_REQUIRED' if unknown else 'FAILED'
            # A fenced worker may never overwrite a newer worker's job/target state.
            query={'job_id':job['job_id'],'fence_token':job['fence_token'],'effective_active':True}
            if store.collection('intelligence_jobs').update_one(query,{'$set':{'state':state,'stage':state,'effective_active':unknown,'error_code':code,'error_message':'Build requires reconciliation.' if unknown else 'Build failed; previous validated generation is retained.','completed_at':store.now()}}).matched_count:
                store.collection('intelligence_targets').update_one({'library_id':job['library_id'],'target':job['target'],'active_job_id':job['job_id'],'fence_token':job['fence_token']},{'$set':{'state':state,'error_code':code},**({} if unknown else {'$unset':{'active_job_id':'','fence_token':''}})})
                store.build_audit(job,'RECOVERY_REQUIRED' if unknown else 'FAILED')
        finally:stop.set();renewer.join(timeout=1)
        return True
    def semantic(self,library_id,actor,query,*,staff=False,offset=0,limit=20,subject='',author='',circulation_status='',sort='title'):
        from backend.services.library_intelligence_service import target_status
        with catalogue.read_context(library_id,actor,staff=staff):status=target_status(library_id,'SEARCH_INDEX')
        if status['status']!='READY':
            page=catalogue.books(library_id,actor,search=query,subject=subject,author=author,circulation_status=circulation_status,sort=sort,offset=offset,limit=limit,staff=staff)
            page['source'].update(search_source='LOCAL_FALLBACK',intelligence_status=status['status']);return page
        try:
            manifest,records,index=self.cache.load(library_id,'SEARCH_INDEX',status['active_generation_id'],status['manifest_checksum'])
            if manifest['model_version']!=self.model_version:raise HTTPException(409,'MODEL_VERSION_CHANGED')
            import numpy as np
            with self.model_lock:
                vector=np.asarray(self.encoder([query]),dtype=np.float32)
                if vector.shape!=(1,384) or not np.isfinite(vector).all() or np.linalg.norm(vector)<1e-8:raise HTTPException(409,'EMBEDDING_INVALID')
                vector/=np.linalg.norm(vector,axis=1,keepdims=True)
                scores,labels=index.search(vector,min(artifacts.PARAMETERS['candidate_count'],len(records)))
                candidates=[(records[int(label)],float(score)) for label,score in zip(labels[0],scores[0]) if 0<=label<len(records)][:artifacts.PARAMETERS['reranking_count']]
                if self.reranker and candidates:
                    ranked=self.reranker([[query,artifacts.embedding_text(r)] for r,_ in candidates])
                    if len(ranked)!=len(candidates) or not np.isfinite(ranked).all():raise HTTPException(409,'RERANKER_INVALID')
                    candidates=[(r,float(score)) for (r,_),score in zip(candidates,ranked)]
                candidates=sorted(candidates,key=lambda pair:(-pair[1],pair[0]['library_book_id']))[:artifacts.PARAMETERS['reranking_count']]
            ids=[r['library_book_id'] for r,_ in candidates]
            with catalogue.read_context(library_id,actor,staff=staff) as (library,membership,canonical):
                # Recheck freshness and hydrate from canonical tenant state, never vector metadata alone.
                if store.fingerprint(store.source_records(library_id))!=manifest['source_fingerprint']:raise HTTPException(409,'SOURCE_CHANGED')
                pipeline=[*catalogue.usable(library_id,subject=subject,author=author,circulation_status=circulation_status,staff=staff),{'$match':{'library_book_id':{'$in':ids}}}]
                rows={r['library_book_id']:r for r in store.collection('library_books').aggregate(pipeline)}
                selected=[rows[i] for i in ids if i in rows]
                source=catalogue.source_locked(library_id,library,membership,canonical,staff=staff)
                source.update(search_source='TENANT_SEMANTIC',intelligence_status='READY',search_generation_id=status['active_generation_id'])
                return {'source':source,'results':catalogue.hydrate(library_id,actor,selected[offset:offset+limit],canonical,staff=staff),'total':len(selected),'offset':offset,'limit':limit,'has_more':offset+limit<len(selected)}
        except (HTTPException,OSError,ValueError):
            page=catalogue.books(library_id,actor,search=query,subject=subject,author=author,circulation_status=circulation_status,sort=sort,offset=offset,limit=limit,staff=staff)
            page['source'].update(search_source='LOCAL_FALLBACK',intelligence_status='RECOVERY_REQUIRED');return page
