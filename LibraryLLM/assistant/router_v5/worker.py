"""One bounded CPU worker, opaque tickets, cancellation-safe ownership isolation."""
from concurrent.futures import Future
import asyncio
import multiprocessing as mp
import os
import queue
import threading
from time import perf_counter
import uuid


class RouterOverloaded(RuntimeError):
    pass


def run_worker(requests,responses,verifier,batch_size,delay,verifier_examples):
    os.environ['CUDA_VISIBLE_DEVICES']=''
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    try:
        from .matcher import Matcher
        matcher=Matcher(verifier,verifier_examples)
        responses.put(('READY',matcher.audit,None))
    except Exception as exc:
        responses.put(('FAILED',None,type(exc).__name__))
        return
    while True:
        first=requests.get()
        if first is None:
            break
        batch=[first];deadline=perf_counter()+delay
        while len(batch)<batch_size and delay:
            remaining=deadline-perf_counter()
            if remaining<=0:
                break
            try:
                item=requests.get(timeout=remaining)
            except queue.Empty:
                break
            if item is None:
                return
            batch.append(item)
        started=perf_counter()
        try:
            predictions=matcher.score([item[1] for item in batch])
            for item,prediction in zip(batch,predictions):
                responses.put((item[0],{'prediction':prediction,'queue_ms':max(0,(started-item[2])*1000),
                                       'batch_size':len(batch)},None))
        except Exception as exc:
            for item in batch:
                responses.put((item[0],None,type(exc).__name__))


class CPUWorker:
    def __init__(self,verifier=False,capacity=64,batch_size=1,batch_delay=0,verifier_examples=True):
        if not 1<=capacity<=256 or not 1<=batch_size<=16 or not 0<=batch_delay<=.010:
            raise ValueError('Invalid bounded worker configuration')
        context=mp.get_context('spawn')
        self.requests=context.Queue(maxsize=capacity);self.responses=context.Queue(maxsize=capacity+1)
        self.pending={};self.lock=threading.Lock();self.capacity=capacity;self.closed=False
        self.process=context.Process(target=run_worker,args=(self.requests,self.responses,verifier,batch_size,batch_delay,verifier_examples),daemon=True)
        self.process.start()
        try:
            ticket,result,error=self.responses.get(timeout=120)
            if ticket!='READY':
                raise RuntimeError('V5 worker initialization failed: '+str(error))
        except Exception:
            self.close()
            raise
        self.audit=result
        self.collector=threading.Thread(target=self._collect,name='router-v5-replies',daemon=True)
        self.collector.start()

    def _collect(self):
        while not self.closed:
            try:
                ticket,result,error=self.responses.get(timeout=.2)
            except queue.Empty:
                if not self.process.is_alive():
                    self.closed=True;self._fail(RuntimeError('V5 worker stopped'))
                    return
                continue
            with self.lock:
                future=self.pending.pop(ticket,None)
            if future is not None and future.set_running_or_notify_cancel():
                if error:
                    future.set_exception(RuntimeError('V5 CPU scoring failed: '+error))
                else:
                    future.set_result(result)

    def _fail(self,error):
        with self.lock:
            pending=list(self.pending.values());self.pending.clear()
        for future in pending:
            if not future.done():
                future.set_exception(error)

    async def predict_payload(self,payload,timeout=10):
        ticket=uuid.uuid4().hex;future=Future()
        with self.lock:
            if self.closed or len(self.pending)>=self.capacity:
                raise RouterOverloaded('V5 CPU queue full or stopped')
            self.pending[ticket]=future
            try:
                self.requests.put_nowait((ticket,payload,perf_counter()))
            except queue.Full:
                self.pending.pop(ticket,None)
                raise RouterOverloaded('V5 CPU queue full')
        try:
            return await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(future)),timeout)
        finally:
            if not future.done():
                future.cancel()

    async def predict(self,message,context,timeout=10):
        from .binding import make_plan,model_payload
        return await self.predict_payload(model_payload(message,make_plan(context,message)),timeout)

    def close(self):
        if getattr(self,'_cleanup_done',False):
            return
        self._cleanup_done=True;self.closed=True
        try:
            self.requests.put_nowait(None)
        except queue.Full:
            pass
        if hasattr(self,'process'):
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.terminate();self.process.join(timeout=2)
        self._fail(RuntimeError('V5 worker closed'))
        if hasattr(self,'collector') and threading.current_thread() is not self.collector:
            self.collector.join(timeout=.5)
        self.requests.close();self.responses.close()
