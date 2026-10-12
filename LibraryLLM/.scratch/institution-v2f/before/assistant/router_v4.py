"""Experimental context-conditioned CPU router. No natural-language matchers."""
from concurrent.futures import Future
import asyncio, hashlib, json, logging, multiprocessing as mp, queue, threading, uuid
from pathlib import Path
from time import perf_counter
import numpy as np
from assistant import router_v3 as v3
from assistant.router_v3 import FAMILIES, features, context_pool, head_logits, probabilities, BOOK_SUBTYPES
from assistant.schemas import AssistantIntentDecision, Intent, ReferenceScope, ClarificationType
from assistant.semantic import literal_ids
from assistant.profiling import current
MODEL_DIR=Path(__file__).parent/'models/router_v4'
ENCODER=v3.ENCODER
LOG=logging.getLogger('luminar.assistant')


def serialize_context(message,context):
    """Public titles + structural state only. Current message is the first segment.

    Private document identifiers/facts, account data, authors, descriptions and
    canonical work IDs never cross IPC. Token budget is applied in the worker.
    """
    def clean(text,limit):
        text=' '.join(str(text).split())
        for identifier in literal_ids(text):
            # Work-ID validation, not a natural-language intent matcher.
            if identifier.startswith('OL') and identifier[-1:] in {'W','M'} and identifier[2:-1].isdigit():
                text=text.replace(identifier,'[identifier]')
        # Also redact synthetic/legacy IDs supplied in structured context.
        identifiers=set(context_pool(context)[1])
        for group in ['selected_books','previous_comparison','page_books']:
            identifiers.update(b.get('work_id','') for b in context.get(group,[]))
        for identifier in identifiers:
            if identifier:text=text.replace(identifier,'[identifier]')
        # Titles cannot inject the serialisation delimiters.
        return text.replace('[','(').replace(']',')')[:limit]
    lines=['[MSG] '+clean(message,4000)]
    active=context.get('active_result_context',{})
    rec=context.get('previous_recommendations',{})
    groups=[('SEL',context.get('selected_books',[])),('CMP',context.get('previous_comparison',[])),
            ('REC',rec.get('books',[]) or (active.get('books',[]) if active.get('type')=='recommendations' else [])),
            ('PAGE',context.get('page_books',[])),('RECENT',active.get('books',[]) if active.get('type') not in {'comparison','recommendations'} else [])]
    for name,books in groups:
        text=' ; '.join(str(i+1)+'|'+clean(b.get('title','book'),64) for i,b in enumerate(books[:4]))
        lines.append('['+name+'] '+(text or 'none'))
    source,pool=context_pool(context);focus=context.get('last_referenced_work_ids',[])
    positions=[str(pool.index(w)+1) for w in focus if w in pool][:4]
    lines.insert(1,'[STATE] active='+str(active.get('type','none'))[:20]+' focus='+(','.join(positions) or 'none')+
        ' changed='+str(int(bool(context.get('selection_changed'))))+' awaiting='+str(int(bool(context.get('awaiting_criteria'))))+
        ' document='+str(int(bool(context.get('document_id'))))+' book_access='+str(int(bool(context.get('book_rag_context')))))
    return '\n'.join(lines)


def bounded_text(tokenizer,text,limit=256):
    # Prefix allocation keeps current message ahead of every fallback context.
    # Only a message that itself exceeds the entire budget is truncated.
    ids=tokenizer.encode(text,add_special_tokens=False)
    return tokenizer.decode(ids[:limit-2],skip_special_tokens=False) if len(ids)>limit-2 else text


def artifact_hashes(directory):
    directory=Path(directory)
    return {p.relative_to(directory).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob('*') if p.is_file() and p.name!='manifest.json'}


def embedding_encoder(directory):
    import torch
    from sentence_transformers import SentenceTransformer
    torch.set_num_threads(2)
    model=SentenceTransformer(str(Path(directory)/'encoder'),device='cpu',local_files_only=True)
    model.max_seq_length=256;model.eval()
    for p in model.parameters():p.requires_grad_(False)
    return model


class Classifiers:
    def __init__(self,directory=MODEL_DIR):
        import torch
        directory=Path(directory)
        self.manifest=json.loads((directory/'manifest.json').read_text(encoding='utf8'))
        if self.manifest['encoder']!=ENCODER or self.manifest['version']!='4.0.0':raise ValueError('Unsupported V4 artifact')
        if artifact_hashes(directory)!=self.manifest['artifact_sha256']:raise ValueError('V4 artifact digest mismatch')
        self.labels=json.loads((directory/'labels.json').read_text(encoding='utf8'))
        self.calibration=json.loads((directory/'calibration.json').read_text(encoding='utf8'))
        tensors=torch.load(directory/'heads.pt',map_location='cpu',weights_only=True)
        self.weights={}
        for h,labels in self.labels.items():
            state={k:v.numpy() for k,v in tensors[h].items()}
            if set(state)-{'weight','bias','hidden_weight','hidden_bias'}:raise ValueError('Invalid V4 head keys')
            first=state.get('hidden_weight',state['weight'])
            if first.shape[1]!=self.manifest['input_dimension'] or state['weight'].shape[0]!=len(labels):raise ValueError('V4 tensor dimensions')
            if not all(np.isfinite(v).all() for v in state.values()):raise ValueError('Non-finite V4 tensor')
            self.weights[h]=state
        self.centroids=np.asarray(self.calibration['centroids'],dtype=np.float32)
    def predict(self,x):
        result=[]
        logits={h:probabilities(head_logits(x,w),self.calibration['temperatures'][h]) for h,w in self.weights.items()}
        for i in range(len(x)):
            row={}
            for h,values in logits.items():
                p=values[i];order=np.argsort(p)
                row[h]={'label':self.labels[h][int(order[-1])],'confidence':float(p[order[-1]]),
                        'margin':float(p[order[-1]]-p[order[-2]]) if len(p)>1 else 1.,'entropy':float(-(p*np.log(p+1e-12)).sum())}
            row['ood_similarity']=float((x[i,:384]@self.centroids.T).max());result.append(row)
        return result


def structural_decision(prediction,context,message,calibration):
    """Joint semantic action removes redundant independent agreement gates.

    References still must pass learned confidence and canonical structural
    checks. Mutation, entity extraction and free criteria remain Qwen-only.
    """
    # A literal machine identifier requires server catalogue validation through
    # the existing extractor. Redacting it from embeddings must not turn it
    # into a tray-relative reference. This is identifier syntax, not NLP.
    if any(w.startswith('OL') and w[-1:] in {'W','M'} and w[2:-1].isdigit() for w in literal_ids(message)):
        return None,'EXPLICIT_ENTITY_EXTRACTION_REQUIRED'
    p={k:dict(v) if isinstance(v,dict) else v for k,v in prediction.items()}
    if calibration.get('routing_head','joint')=='joint':
        action=p['action'];sub,_,field=action['label'].partition(':')
        p['intent_subtypes']={**action,'label':sub};p['intent_family']={**action,'label':FAMILIES[sub]}
        p['fields']={**action,'label':field or 'NONE'}
        gate={**calibration,'policies':dict(calibration['policies'])}
        gate['policies']['intent_subtypes']={sub:calibration['policies']['action'][action['label']]}
        gate['policies']['intent_family']={FAMILIES[sub]:calibration['policies']['action'][action['label']]}
        if sub=='FIELD':gate['policies']['fields']={field:calibration['policies']['action'][action['label']]}
        elif sub=='PREFERENCE':gate['policies']['fields']={'NONE':{'confidence':0,'margin':0}}
    else:gate={**calibration,'policies':dict(calibration['policies'])}
    # Loss-masked heads are undefined for these routes and cannot be confidence
    # gates. Only the relevant semantic output is required: FIELD needs a
    # field, PREFERENCE needs criterion presence. Keep all trained thresholds.
    sub=p['intent_subtypes']['label']
    if sub=='FIELD':
        p['criterion']={'label':'ABSENT','confidence':1.,'margin':1.}
        gate['policies']['criterion']={'ABSENT':{'confidence':0,'margin':0}}
    if sub=='PREFERENCE':
        p['fields']={'label':'NONE','confidence':1.,'margin':1.}
        gate['policies']['fields']={'NONE':{'confidence':0,'margin':0}}
    # Position is masked for non-references and EXPLICIT. V3's recommendation
    # NONE position gate is redundant, so provide the neutral ALL declaration.
    if p['intent_subtypes']['label']=='RECOMMEND' and p['reference']['label']=='NONE':
        p['position']={'label':'ALL','confidence':1.,'margin':1.}
    return v3.structural_decision(p,context,message,gate)


def _worker(requests,responses,directory,batch_size,batch_delay):
    import psutil,os,torch
    started=perf_counter();models=Classifiers(directory);encoder=embedding_encoder(directory)
    responses.put(('READY',{'pid':os.getpid(),'device':str(encoder.device),'startup_ms':(perf_counter()-started)*1000,
        'rss_mb':psutil.Process().memory_info().rss/1048576,'dimension':384,'encoder_instances':1,'cpu_threads':2,
        'cuda_initialized':torch.cuda.is_initialized(),'cuda_allocated_bytes':0}))
    while True:
        first=requests.get()
        if first is None:break
        batch=[first];deadline=perf_counter()+batch_delay
        while len(batch)<batch_size:
            remaining=deadline-perf_counter()
            if remaining<=0:break
            try:
                extra=requests.get(timeout=remaining)
                if extra is None:return
                batch.append(extra)
            except queue.Empty:break
        started=perf_counter()
        try:
            texts=[bounded_text(encoder.tokenizer,b[1]) for b in batch]
            vectors=encoder.encode(texts,batch_size=batch_size,normalize_embeddings=True,show_progress_bar=False,convert_to_numpy=True)
            x=np.concatenate([vectors,np.asarray([b[2] for b in batch],dtype=np.float32)],axis=1)
            predicted=models.predict(x);duration=(perf_counter()-started)*1000
            for item,row in zip(batch,predicted):responses.put((item[0],{'prediction':row,'encoder_ms':duration,'batch_size':len(batch),
                'queue_ms':max(0,(started-item[3])*1000)},None))
        except Exception as exc:
            for item in batch:responses.put((item[0],None,type(exc).__name__))

class RouterOverloaded(RuntimeError):
    pass


class CPUWorker:
    """Singleton per gateway, bounded inflight work, cancellation-safe replies."""
    def __init__(self, directory=MODEL_DIR, capacity=64,batch_size=1,batch_delay=0):
        if not 1<=batch_size<=16 or not 0<=batch_delay<=.010:
            raise ValueError('Invalid CPU batching budget')
        ctx=mp.get_context('spawn')
        self.requests=ctx.Queue(maxsize=capacity); self.responses=ctx.Queue(maxsize=capacity+1)
        self.pending={}; self.lock=threading.Lock(); self.capacity=capacity; self.closed=False
        self.process=ctx.Process(target=_worker,args=(self.requests,self.responses,str(directory),batch_size,batch_delay),daemon=True)
        self.process.start()
        try:ready=self.responses.get(timeout=120)
        except queue.Empty:
            self.close();raise RuntimeError('CPU router startup timed out')
        if ready[0]!='READY':
            self.close(); raise RuntimeError('CPU router failed to initialize')
        self.audit=ready[1]
        self.collector=threading.Thread(target=self._collect,name='router-v4-replies',daemon=True)
        self.collector.start()

    def _collect(self):
        while not self.closed:
            try:
                ticket,result,error=self.responses.get(timeout=.2)
            except queue.Empty:
                if not self.process.is_alive():
                    self.closed=True
                    self._fail_pending(RuntimeError('CPU router worker stopped'))
                    return
                continue
            with self.lock:
                future=self.pending.pop(ticket,None)
            if future is not None and future.set_running_or_notify_cancel():
                if error: future.set_exception(RuntimeError('CPU router inference failed: '+error))
                else: future.set_result(result)

    def _fail_pending(self,error):
        with self.lock:
            pending=list(self.pending.values());self.pending.clear()
        for future in pending:
            if not future.done():future.set_exception(error)

    async def predict(self,message,context,timeout=5):
        ticket=uuid.uuid4().hex; future=Future()
        with self.lock:
            if self.closed or len(self.pending)>=self.capacity:
                raise RouterOverloaded('CPU router queue is full or stopped')
            self.pending[ticket]=future
            try:self.requests.put_nowait((ticket,serialize_context(message,context),features(context).tolist(),perf_counter()))
            except queue.Full:
                self.pending.pop(ticket,None);raise RouterOverloaded('CPU router queue is full')
        try:
            return await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(future)),timeout)
        finally:
            # Keep cancelled jobs counted until their result arrives, preserving
            # the capacity bound even when callers repeatedly cancel requests.
            if not future.done():future.cancel()

    def close(self):
        if getattr(self,'_cleanup_done',False):return
        self._cleanup_done=True
        self.closed=True
        try:self.requests.put_nowait(None)
        except queue.Full:pass
        if hasattr(self,'process'):
            self.process.join(timeout=2)
            if self.process.is_alive():self.process.terminate();self.process.join(timeout=2)
        self._fail_pending(RuntimeError('CPU router shut down'))
        if hasattr(self,'collector') and threading.current_thread() is not self.collector:
            self.collector.join(timeout=.5)
        self.requests.close();self.responses.close()


class HybridGateway:
    def __init__(self, qwen, mode='router_v4', worker=None, directory=MODEL_DIR):
        if mode not in {'router_v4','router_v4_shadow'}:raise ValueError('Invalid hybrid mode')
        self.qwen=qwen;self.mode=mode;self.worker=worker or CPUWorker(directory)
        self.calibration=json.loads((Path(directory)/'calibration.json').read_text(encoding='utf8'))
        self.shadow_tasks=set()

    async def shadow_parse(self,message,context):
        """Observe independently; never delay existing routing or duplicate tools."""
        if not hasattr(self,'shadow_tasks'):self.shadow_tasks=set()
        prediction_task=asyncio.create_task(self.worker.predict(message,context))
        started=perf_counter();outcome=None
        try:
            outcome=await self.qwen.parse(message,context)
            return outcome
        finally:
            qwen_ms=(perf_counter()-started)*1000
            profile=current.get()
            async def observe():
                try:
                    measured=await prediction_task
                    decision,reason=structural_decision(measured['prediction'],context,message,self.calibration)
                    telemetry={'shadow':True,'accepted':decision is not None,'fallback_reason':reason,
                        'components':measured['prediction'],'encoder_ms':measured['encoder_ms'],
                        'queue_ms':measured['queue_ms'],'batch_size':measured['batch_size'],'qwen_ms':qwen_ms,
                        'shadow_agreement':bool(outcome and decision and outcome.intent==decision.intent
                                                and outcome.reference_scope==decision.reference_scope),
                        'existing_outcome':outcome.intent.value if outcome else 'UNAVAILABLE'}
                    if profile is not None:profile['router_v4']=telemetry
                    # Late results may arrive after the HTTP profile was written.
                    # This sink contains labels/numbers only, never raw text/IDs.
                    LOG.info('router_v4_shadow %s',json.dumps(telemetry))
                except (RouterOverloaded,asyncio.TimeoutError,RuntimeError):
                    LOG.info('router_v4_shadow unavailable=true')
            task=asyncio.create_task(observe());self.shadow_tasks.add(task)
            task.add_done_callback(self.shadow_tasks.discard)

    async def parse(self,message,context):
        if self.mode=='router_v4_shadow':return await self.shadow_parse(message,context)
        started=perf_counter()
        try:
            measured=await self.worker.predict(message,context)
            prediction=measured['prediction']
            decision,reason=structural_decision(prediction,context,message,self.calibration)
        except (RouterOverloaded,asyncio.TimeoutError,RuntimeError):
            prediction={};measured={};decision=None;reason='CLASSIFIER_UNAVAILABLE'
        telemetry={'accepted':decision is not None,'fallback_reason':reason,'components':prediction,
            'thresholds':{head:self.calibration['policies'][head].get(value['label'])
                          for head,value in prediction.items() if head in self.calibration['policies']},
            'classifier_ms':(perf_counter()-started)*1000,
            'queue_ms':measured.get('queue_ms'),'encoder_ms':measured.get('encoder_ms'),
            'batch_size':measured.get('batch_size'),'shadow':self.mode=='router_v4_shadow'}
        profile=current.get()
        if profile is not None:profile['router_v4']=telemetry
        if self.mode=='router_v4_shadow' or decision is None:
            before=perf_counter()
            # Installed with existing compact routing and retries disabled.
            try:result=await self.qwen.parse(message,context)
            finally:telemetry['qwen_ms']=(perf_counter()-before)*1000
            if self.mode=='router_v4_shadow':
                telemetry['shadow_agreement']=bool(decision and result.intent==decision.intent
                    and result.reference_scope==decision.reference_scope)
            elif result.mentioned_titles or result.reference_scope==ReferenceScope.EXPLICIT_BOOK:
                # Entity extraction is gated independently of Qwen's suggested
                # title. Contextual pronouns cannot cause fuzzy catalogue calls.
                entity=prediction.get('reference',{})
                policy=self.calibration['policies']['reference']['EXPLICIT']
                permitted=(entity.get('label')=='EXPLICIT'
                    and entity.get('confidence',0)>=policy['confidence']
                    and entity.get('margin',0)>=policy['margin']
                    and bool(result.mentioned_titles)
                    and all(t.casefold() in message.casefold() for t in result.mentioned_titles))
                # Literal structured identifiers are not title extraction.
                # The existing executor still checks catalogue and ownership.
                permitted=permitted or (bool(result.resolved_work_ids) and not result.mentioned_titles
                    and set(result.resolved_work_ids)<=literal_ids(message))
                if not permitted:
                    result=AssistantIntentDecision(intent=Intent.CLARIFICATION,
                        clarification_needed=True,clarification_type=ClarificationType.REFERENCE_AMBIGUITY,
                        reference_scope=ReferenceScope.AMBIGUOUS)
                    telemetry['entity_gate']='REJECTED'
                else:telemetry['entity_gate']='LITERAL_AND_CLASSIFIER_VERIFIED'
            return result
        return decision

    async def respond(self,*args,**kwargs):
        return await self.qwen.respond(*args,**kwargs)

    async def generate(self,*args,**kwargs):
        return await self.qwen.generate(*args,**kwargs)

    def close(self):
        for task in getattr(self,'shadow_tasks',set()):task.cancel()
        self.worker.close();self.qwen.close()
