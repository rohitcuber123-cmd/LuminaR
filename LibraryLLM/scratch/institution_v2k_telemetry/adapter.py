"""Child-process-only laboratory adapter. Not a production integration seam."""
import os
from .telemetry import PREFIX


class NativeAdapter:
    def __init__(self,worker,store,agent):
        if os.environ.get('LUMINAR_V2K_ISOLATED_CHILD')!='1' or not os.environ.get('MONGO_DB_NAME','').startswith(PREFIX):
            raise RuntimeError('ISOLATED_CHILD_REQUIRED')
        self.worker,self.store,self.agent=worker,store,agent
        self.claim,self.run_one=store.claim,worker.run_one

    def __enter__(self):
        def claim(owner):
            row=self.claim(owner)
            if row:
                try:self.agent.note_claim(row)
                except Exception:self.agent.errors['CALLBACK_UNAVAILABLE']+=1
            return row
        def run_one():
            try:return self.run_one()
            finally:
                try:self.agent.note_finished()
                except Exception:self.agent.errors['CALLBACK_UNAVAILABLE']+=1
        self.store.claim=claim;self.worker.run_one=run_one
        self.agent.start();return self

    def __exit__(self,*exc):
        self.worker.close()
        if self.worker.thread:self.worker.thread.join(timeout=5)
        ended=not self.worker.thread or not self.worker.thread.is_alive()
        self.agent.close(native_stopped=ended)
        self.store.claim,self.worker.run_one=self.claim,self.run_one
