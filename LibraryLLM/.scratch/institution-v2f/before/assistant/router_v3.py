"""Opt-in CPU selective router. No held-out data, intent regex or tool calls.

The worker owns one frozen encoder. Only message text and bounded numeric
features cross its queue: identity binding stays in the authenticated executor.
"""
from concurrent.futures import Future
from dataclasses import dataclass
import asyncio
import hashlib
import json
import logging
import multiprocessing as mp
from pathlib import Path
import queue
import threading
from time import perf_counter
import uuid

import numpy as np

from assistant.schemas import AssistantIntentDecision, Intent, ReferenceScope, SemanticGoal, ClarificationType
from assistant.profiling import current
from assistant.semantic import bind_position, unique, literal_ids

MODEL_DIR = Path(__file__).parent / 'models' / 'router_v3'
LOG = logging.getLogger('luminar.assistant')
ENCODER = 'sentence-transformers/all-MiniLM-L6-v2'
FEATURE_VERSION = 'bounded-context-v1'
FAMILIES = {
    'SEARCH':'DISCOVER', 'RECOMMEND':'DISCOVER', 'SIMILAR':'DISCOVER', 'ALTERNATIVES':'DISCOVER',
    'FACTUAL':'COMPARE', 'FIELD':'COMPARE', 'PREFERENCE':'COMPARE',
    'DETAILS':'BOOK', 'AVAILABILITY':'BOOK', 'BORROW':'BOOK', 'RETURN':'BOOK', 'RESERVE':'BOOK',
    'ADD_LIST':'BOOK', 'REMOVE_LIST':'BOOK',
    'LOANS':'ACCOUNT', 'FEES':'ACCOUNT', 'RESERVATIONS':'ACCOUNT', 'HISTORY':'ACCOUNT', 'READING_LIST':'ACCOUNT',
    'BOOK_CONTENT':'CONTENT', 'DOCUMENT_CONTENT':'CONTENT', 'HELP':'HELP', 'UNKNOWN':'UNKNOWN',
    'SHOW_MORE':'CONTEXT', 'REFINE':'CONTEXT', 'CLEAR_LIST':'ACCOUNT',
}
INTENTS = {
    'SEARCH':Intent.SEARCH_BOOKS, 'RECOMMEND':Intent.RECOMMEND_BOOKS, 'SIMILAR':Intent.MORE_LIKE_THIS,
    'ALTERNATIVES':Intent.RECOMMEND_AVAILABLE_SIMILAR, 'FACTUAL':Intent.COMPARE_BOOKS,
    'FIELD':Intent.COMPARE_BOOKS, 'PREFERENCE':Intent.COMPARE_BOOKS, 'DETAILS':Intent.BOOK_DETAILS,
    'AVAILABILITY':Intent.CHECK_AVAILABILITY, 'BORROW':Intent.BORROW_BOOK, 'RETURN':Intent.RETURN_BOOK,
    'RESERVE':Intent.RESERVE_BOOK, 'ADD_LIST':Intent.ADD_TO_READING_LIST,
    'REMOVE_LIST':Intent.REMOVE_FROM_READING_LIST, 'LOANS':Intent.USER_LOANS, 'FEES':Intent.USER_FEES,
    'RESERVATIONS':Intent.USER_RESERVATIONS, 'HISTORY':Intent.USER_HISTORY,
    'READING_LIST':Intent.USER_READING_LIST, 'BOOK_CONTENT':Intent.BOOK_CONTENT_QUESTION,
    'DOCUMENT_CONTENT':Intent.DOCUMENT_QUESTION, 'HELP':Intent.GENERAL_LIBRARY_HELP,
    'UNKNOWN':Intent.UNKNOWN, 'SHOW_MORE':Intent.SEARCH_BOOKS, 'REFINE':Intent.SEARCH_BOOKS,
    'CLEAR_LIST':Intent.CLEAR_READING_LIST,
}
MUTATIONS = {'BORROW','RETURN','RESERVE','ADD_LIST','REMOVE_LIST','CLEAR_LIST'}
BOOK_SUBTYPES = {'SIMILAR','ALTERNATIVES','FACTUAL','FIELD','PREFERENCE','DETAILS','AVAILABILITY',
                 'BORROW','RETURN','RESERVE','ADD_LIST','REMOVE_LIST','BOOK_CONTENT'}
RESULT_TYPES = ('search','recommendations','comparison','details','availability')


def context_pool(context):
    """Select live authority without examining prose or trusting classifier IDs."""
    selected = [b['work_id'] for b in context.get('selected_books', [])]
    active = context.get('active_result_context', {})
    comparison = [b['work_id'] for b in context.get('previous_comparison', [])]
    page = [b['work_id'] for b in context.get('page_books', [])]
    if selected:
        return 'SELECTION', unique(selected)
    if active.get('type') == 'comparison' and active.get('work_ids'):
        return 'PREVIOUS_COMPARISON', unique(active['work_ids'])
    if active.get('type') == 'recommendations' and active.get('work_ids'):
        return 'PREVIOUS_RECOMMENDATIONS', unique(active['work_ids'])
    if comparison and 'active_result_context' not in context:
        return 'PREVIOUS_COMPARISON', unique(comparison)
    if page:
        return 'PAGE', unique(page)
    if 'active_result_context' in context:
        return ('RECENT', unique(active['work_ids'])) if active.get('work_ids') else ('AMBIGUOUS', [])
    focus = context.get('last_referenced_work_ids', [])
    return ('RECENT', unique(focus)) if focus else ('AMBIGUOUS', [])


def features(context):
    """No titles, authors, IDs, private content, query text or history embedding."""
    source, pool = context_pool(context)
    active = context.get('active_result_context', {})
    focus = [w for w in context.get('last_referenced_work_ids', []) if w in pool]
    return np.asarray([
        min(4,len(context.get('selected_books',[])))/4,
        bool(context.get('page_books')), bool(context.get('previous_comparison')),
        bool(context.get('previous_recommendations')), active.get('type')=='search',
        bool(context.get('document_id')), bool(context.get('book_rag_context')),
        bool(context.get('pending_action')), context.get('authenticated',True),
        bool(context.get('awaiting_criteria')), bool(context.get('selection_changed')),
        min(4,len(pool))/4, len(focus)==1,
        *[active.get('type')==t for t in RESULT_TYPES],
        *[source==s for s in ('SELECTION','PAGE','PREVIOUS_COMPARISON','PREVIOUS_RECOMMENDATIONS','RECENT','AMBIGUOUS')],
    ], dtype=np.float32)


def embedding_encoder():
    # Called only in the dedicated worker/offline trainer, never per request.
    import torch
    from sentence_transformers import SentenceTransformer
    torch.set_num_threads(2)
    model = SentenceTransformer(ENCODER, device='cpu', local_files_only=True)
    model.max_seq_length = 256
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    assert model.get_sentence_embedding_dimension() == 384
    return model


def probabilities(logits, temperature=1):
    logits = logits / temperature
    logits = logits - logits.max(axis=-1,keepdims=True)
    out = np.exp(logits)
    return out/out.sum(axis=-1,keepdims=True)


def head_logits(x, weights):
    if 'hidden_weight' in weights:
        x = np.maximum(0, x @ weights['hidden_weight'].T + weights['hidden_bias'])
    return x @ weights['weight'].T + weights['bias']


class Classifiers:
    def __init__(self, directory=MODEL_DIR):
        import torch
        directory = Path(directory)
        self.manifest = json.loads((directory/'manifest.json').read_text(encoding='utf8'))
        if self.manifest['encoder'] != ENCODER or self.manifest['feature_version'] != FEATURE_VERSION:
            raise ValueError('Unsupported V3 artifact contract')
        self.labels = json.loads((directory/'labels.json').read_text(encoding='utf8'))
        self.calibration = json.loads((directory/'calibration.json').read_text(encoding='utf8'))
        for name in ['labels.json','calibration.json']:
            if hashlib.sha256((directory/name).read_bytes()).hexdigest()!=self.manifest['artifact_sha256'][name]:
                raise ValueError('V3 metadata digest mismatch')
        self.weights = {}
        for head, label in self.labels.items():
            path = directory/(head+'.pt')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != self.manifest['artifact_sha256'][path.name]:
                raise ValueError('V3 artifact digest mismatch')
            state = torch.load(path,map_location='cpu',weights_only=True)
            allowed = {'weight','bias','hidden_weight','hidden_bias'}
            if set(state)-allowed or not {'weight','bias'} <= set(state):
                raise ValueError('Unsupported classifier weights')
            weights = {k:v.numpy() for k,v in state.items()}
            input_dimension = 384+len(features({}))
            first = weights.get('hidden_weight',weights['weight'])
            if first.shape[1]!=input_dimension or weights['weight'].shape[0]!=len(label):
                raise ValueError('V3 tensor shape mismatch')
            if not all(np.isfinite(v).all() for v in weights.values()):
                raise ValueError('Non-finite classifier weights')
            self.weights[head] = weights
        self.centroids = np.asarray(self.calibration['centroids'],dtype=np.float32)

    def predict(self,x):
        result = []
        vectors = {h:probabilities(head_logits(x,w),self.calibration['temperatures'][h])
                   for h,w in self.weights.items()}
        for index in range(len(x)):
            row = {}
            for head, values in vectors.items():
                p = values[index]; order = np.argsort(p)
                row[head] = {'label':self.labels[head][int(order[-1])],
                             'confidence':float(p[order[-1]]),
                             'margin':float(p[order[-1]]-p[order[-2]]) if len(p)>1 else 1.,
                             'entropy':float(-(p*np.log(p+1e-12)).sum())}
            row['ood_similarity'] = float((x[index,:384] @ self.centroids.T).max())
            result.append(row)
        return result


def structural_decision(prediction, context, message, calibration):
    """Selective policy checked against request-local authority, no language rules."""
    subtype = prediction['intent_subtypes']['label']
    family = prediction['intent_family']['label']
    ref = prediction['reference']['label']
    position = prediction['position']['label']
    field = prediction['fields']['label']
    criterion = prediction['criterion']['label']=='PRESENT'
    if prediction['ood_similarity'] < calibration['ood_min_similarity']:
        return None,'OUT_OF_DISTRIBUTION'
    if FAMILIES.get(subtype)!=family:
        return None,'CONFLICTING_CLASSIFIERS'
    required = ['intent_family','intent_subtypes']
    if subtype in BOOK_SUBTYPES or subtype=='RECOMMEND':
        required += ['reference','position']
    if subtype in {'PREFERENCE','FIELD'}:
        required += ['criterion','fields']
    for head in required:
        value = prediction[head]
        policy = calibration['policies'][head][value['label']]
        if value['confidence'] < policy['confidence'] or value['margin'] < policy['margin']:
            return None,'LOW_CONFIDENCE_REFERENCE' if head in {'reference','position'} else 'LOW_CONFIDENCE_INTENT'
    if subtype in MUTATIONS:
        return None,'MUTATION_REQUIRES_QWEN_AND_CONFIRMATION'
    if subtype in {'UNKNOWN','HELP','BOOK_CONTENT','DOCUMENT_CONTENT','REFINE','SHOW_MORE'}:
        return None,'CONTENT_AMBIGUITY' if family=='CONTENT' else 'COMPLEX_INTERPRETATION_REQUIRED'
    if subtype=='PREFERENCE' and criterion:
        return None,'FREEFORM_CRITERION_REQUIRED'
    if ref=='EXPLICIT' and subtype in BOOK_SUBTYPES|{'RECOMMEND'}:
        return None,'EXPLICIT_ENTITY_EXTRACTION_REQUIRED'
    source,pool = context_pool(context)
    # Source classifier is trained on structural context too. A conflict never
    # overrides current selection, an empty active result, or authenticated IDs.
    if subtype in BOOK_SUBTYPES and ref!=source:
        return None,'CONTEXT_INVALID_REFERENCE'
    if subtype=='SEARCH' or family=='ACCOUNT':
        # These operations don't use book references, regardless of tray state.
        if subtype=='SEARCH' and len(message)>2000:
            return None,'QUERY_CONTRACT_LIMIT'
        if family=='ACCOUNT' and not context.get('authenticated',True):
            return None,'CONTEXT_AUTHENTICATION_REQUIRED'
        scope = ReferenceScope.ACCOUNT if family=='ACCOUNT' else ReferenceScope.NONE
        return AssistantIntentDecision(intent=INTENTS[subtype],confidence=prediction['intent_subtypes']['confidence'],
            query=message if subtype=='SEARCH' else None,reference_scope=scope,
            goal=SemanticGoal.DISCOVER if subtype=='SEARCH' else SemanticGoal.ACCOUNT_QUERY),'ACCEPTED'
    if subtype=='RECOMMEND' and ref=='NONE':
        return AssistantIntentDecision(intent=Intent.RECOMMEND_BOOKS,confidence=prediction['intent_subtypes']['confidence'],
                                       reference_scope=ReferenceScope.NONE,goal=SemanticGoal.DISCOVER),'ACCEPTED'
    if subtype=='RECOMMEND' and ref!=source:
        return None,'CONTEXT_INVALID_REFERENCE'
    try:
        ids=bind_position(pool,position,context.get('last_referenced_work_ids',[]))
    except ValueError:
        return None,'CONTEXT_INVALID_POSITION'
    if not ids or len(ids)>4:
        return None,'CONTEXT_INVALID_REFERENCE'
    if family=='COMPARE' and (len(ids)<2 or position!='ALL'):
        return None,'CONTEXT_INVALID_CARDINALITY'
    if subtype in {'SIMILAR','ALTERNATIVES','DETAILS','BORROW','RETURN','RESERVE'} and len(ids)!=1:
        return None,'CONTEXT_INVALID_CARDINALITY'
    if subtype=='FIELD' and field=='NONE':
        return None,'CONFLICTING_CLASSIFIERS'
    if subtype=='PREFERENCE' and field!='NONE':
        return None,'CONFLICTING_CLASSIFIERS'
    scope={'SELECTION':ReferenceScope.SELECTED_BOOKS,'PAGE':ReferenceScope.CURRENT_PAGE_BOOK,
           'PREVIOUS_COMPARISON':ReferenceScope.PREVIOUS_COMPARISON,
           'PREVIOUS_RECOMMENDATIONS':ReferenceScope.PREVIOUS_RECOMMENDATIONS,'RECENT':ReferenceScope.RECENT_RESULTS}.get(source)
    if scope is None:
        return None,'CONTEXT_INVALID_REFERENCE'
    intent=INTENTS[subtype]
    if subtype=='RECOMMEND':
        intent=Intent.RECOMMEND_FROM_SELECTION if len(ids)>1 else Intent.RECOMMEND_FROM_BOOK
    goal=SemanticGoal.FACTUAL_COMPARE if subtype=='FACTUAL' else SemanticGoal.COMPARE_BY_FIELD if subtype=='FIELD' else SemanticGoal.PREFERENCE_COMPARE if subtype=='PREFERENCE' else SemanticGoal.DETAIL if subtype=='DETAILS' else SemanticGoal.CHECK_STATUS if subtype=='AVAILABILITY' else SemanticGoal.DISCOVER
    return AssistantIntentDecision(intent=intent,confidence=prediction['intent_subtypes']['confidence'],
        reference_scope=scope,reference_position=position,goal=goal,
        comparison_fields=[] if field=='NONE' or subtype!='FIELD' else [field],
        clarification_type=ClarificationType.CRITERIA_AMBIGUITY if subtype=='PREFERENCE' else None,
        clarification_needed=subtype=='PREFERENCE'),'ACCEPTED'


def _worker(requests, responses, directory, batch_size, batch_delay):
    import psutil
    start=perf_counter(); encoder=embedding_encoder(); models=Classifiers(directory)
    responses.put(('READY',{'pid':__import__('os').getpid(),'device':str(encoder.device),
        'startup_ms':(perf_counter()-start)*1000,'rss_mb':psutil.Process().memory_info().rss/1048576,
        'dimension':384,'encoder_instances':1,'cpu_threads':2}))
    while True:
        first=requests.get()
        if first is None:
            break
        batch=[first]; deadline=perf_counter()+batch_delay
        while len(batch)<batch_size:
            remaining=deadline-perf_counter()
            if remaining<=0:
                break
            try:
                extra=requests.get(timeout=remaining)
                if extra is None:
                    return
                batch.append(extra)
            except queue.Empty:
                break
        started=perf_counter()
        try:
            vectors=encoder.encode([b[1] for b in batch],batch_size=batch_size,
                normalize_embeddings=True,show_progress_bar=False,convert_to_numpy=True)
            x=np.concatenate([vectors,np.asarray([b[2] for b in batch],dtype=np.float32)],axis=1)
            predicted=models.predict(x)
            duration=(perf_counter()-started)*1000
            for item,row in zip(batch,predicted):
                responses.put((item[0],{'prediction':row,'encoder_ms':duration,'batch_size':len(batch),
                    'queue_ms':max(0,(started-item[3])*1000)},None))
        except Exception as exc:
            for item in batch:
                responses.put((item[0],None,type(exc).__name__))


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
        self.collector=threading.Thread(target=self._collect,name='router-v3-replies',daemon=True)
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
            try:self.requests.put_nowait((ticket,message[:4000],features(context).tolist(),perf_counter()))
            except queue.Full:
                self.pending.pop(ticket,None);raise RouterOverloaded('CPU router queue is full')
        try:
            return await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(future)),timeout)
        finally:
            # Keep cancelled jobs counted until their result arrives, preserving
            # the capacity bound even when callers repeatedly cancel requests.
            if not future.done():future.cancel()

    def close(self):
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
    def __init__(self, qwen, mode='router_v3', worker=None, directory=MODEL_DIR):
        if mode not in {'router_v3','router_v3_shadow'}:raise ValueError('Invalid hybrid mode')
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
                    if profile is not None:profile['router_v3']=telemetry
                    # Late results may arrive after the HTTP profile was written.
                    # This sink contains labels/numbers only, never raw text/IDs.
                    LOG.info('router_v3_shadow %s',json.dumps(telemetry))
                except (RouterOverloaded,asyncio.TimeoutError,RuntimeError):
                    LOG.info('router_v3_shadow unavailable=true')
            task=asyncio.create_task(observe());self.shadow_tasks.add(task)
            task.add_done_callback(self.shadow_tasks.discard)

    async def parse(self,message,context):
        if self.mode=='router_v3_shadow':return await self.shadow_parse(message,context)
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
            'batch_size':measured.get('batch_size'),'shadow':self.mode=='router_v3_shadow'}
        profile=current.get()
        if profile is not None:profile['router_v3']=telemetry
        if self.mode=='router_v3_shadow' or decision is None:
            before=perf_counter()
            # Installed with existing compact routing and retries disabled.
            try:result=await self.qwen.parse(message,context)
            finally:telemetry['qwen_ms']=(perf_counter()-before)*1000
            if self.mode=='router_v3_shadow':
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
