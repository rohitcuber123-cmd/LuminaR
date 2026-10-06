"""Cached CPU semantic retrieval and optional relevance verification; no fitting."""
import gc
from time import perf_counter
import numpy as np
from .contracts import CONTRACTS, BY_ID, POSITIONS, FIELDS, CRITERIA, registry_hash

ENCODER = 'sentence-transformers/all-MiniLM-L6-v2'
VERIFIER = 'cross-encoder/ms-marco-MiniLM-L-6-v2'


class Matcher:
    def __init__(self, verifier=False, verifier_examples=True):
        import torch
        import psutil
        from sentence_transformers import SentenceTransformer, CrossEncoder
        torch.set_num_threads(2)
        started = perf_counter()
        self.encoder = SentenceTransformer(ENCODER, device='cpu', local_files_only=True)
        self.encoder.max_seq_length = 256
        self.encoder.eval()
        for p in self.encoder.parameters():
            p.requires_grad_(False)
        texts = [c.meaning for c in CONTRACTS]
        self.definition_indices = list(range(len(texts)))
        self.example_indices = []
        for c in CONTRACTS:
            self.example_indices.append(list(range(len(texts), len(texts)+len(c.examples))))
            texts.extend(c.examples)
        self.aux_indices = {}
        for group, bank in [('position', POSITIONS), ('field', FIELDS), ('criterion', CRITERIA)]:
            self.aux_indices[group] = {}
            for label, (meaning, examples) in bank.items():
                self.aux_indices[group][label] = list(range(len(texts), len(texts)+1+len(examples)))
                texts += [meaning, *examples]
        with torch.inference_mode():
            self.vectors = self.encoder.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
        self.verifier = None
        self.verifier_examples = verifier_examples
        process = psutil.Process()
        self.audit = {'device':'cpu','cpu_threads':2,'encoder_instances':1,'verifier_requested':verifier,
                      'encoder':ENCODER,'verifier_model':VERIFIER,'verifier_examples':verifier_examples,'registry_sha256':registry_hash(),
                      'rss_before_verifier_mb':process.memory_info().rss/1048576,
                      'commit_before_verifier_mb':process.memory_info().vms/1048576,
                      'host_available_before_verifier_mb':psutil.virtual_memory().available/1048576,
                      'cuda_initialized':torch.cuda.is_initialized(),'cuda_allocated_bytes':0}
        if verifier:
            self.verifier = CrossEncoder(VERIFIER, device='cpu', local_files_only=True, max_length=256)
            self.verifier.model.eval()
            for p in self.verifier.model.parameters():
                p.requires_grad_(False)
            self.audit.update(rss_with_verifier_mb=process.memory_info().rss/1048576,
                              commit_with_verifier_mb=process.memory_info().vms/1048576,
                              host_available_with_verifier_mb=psutil.virtual_memory().available/1048576)
            if self.audit['rss_with_verifier_mb']>1.3*1024 or self.audit['host_available_with_verifier_mb']<512:
                self.verifier = None
                gc.collect()
                self.audit['verifier_disabled_reason']='RSS/host memory gate'
        self.audit.update(verifier_enabled=self.verifier is not None,pid=process.pid,
                          rss_mb=process.memory_info().rss/1048576,commit_mb=process.memory_info().vms/1048576,
                          startup_ms=(perf_counter()-started)*1000)

    def score(self, payloads):
        import torch
        started = perf_counter()
        messages = [p['message'] for p in payloads]
        # The current message always leads; structural history is bounded and
        # contains a semantic meaning rather than identity/private facts.
        queries = []
        for p in payloads:
            q = p['message']
            if p.get('awaiting_criteria'):
                q += '\nContext: answering a request for a reading purpose to choose between known books.'
            elif len(q.split())<=5 and p.get('last_meaning'):
                q += '\nPrior library task: '+p['last_meaning'][:240]
            queries.append(q)
        with torch.inference_mode():
            embeddings = self.encoder.encode(queries+messages,batch_size=max(1,len(payloads)*2),
                           normalize_embeddings=True,show_progress_bar=False)
        encoder_ms=(perf_counter()-started)*1000
        sims=embeddings[:len(payloads)] @ self.vectors.T
        raw_sims=embeddings[len(payloads):] @ self.vectors.T
        out=[];pairs=[];pair_keys=[]
        for i,p in enumerate(payloads):
            definition=sims[i,self.definition_indices]
            maxima=np.array([sims[i,idx].max() for idx in self.example_indices])
            averages=np.array([np.sort(sims[i,idx])[-3:].mean() for idx in self.example_indices])
            combined=.70*maxima+.20*averages+.10*definition
            methods={}
            for name,values in [('A',definition),('B',maxima),('C',combined)]:
                items=[{'id':c.id,'score':float(values[j])} for j,c in enumerate(CONTRACTS) if c.id in p['eligible']]
                methods[name]=sorted(items,key=lambda x:(-x['score'],x['id']))
            aux={}
            for group,bank in self.aux_indices.items():
                aux[group]=sorted([{'label':label,'score':float(.85*raw_sims[i,idx[1:]].max()+.15*raw_sims[i,idx[0]])}
                                   for label,idx in bank.items()],key=lambda x:(-x['score'],x['label']))
            item={'methods':methods,'aux':aux,'encoder_ms':encoder_ms,'verifier_ms':0,'top_k':3}
            out.append(item)
            if self.verifier is not None:
                for candidate in methods['C'][:3]:
                    c=BY_ID[candidate['id']]
                    # Human meaning plus two distinct examples; static content
                    # is reused, not encoded by the bi-encoder per request.
                    document=c.meaning+(' Examples: '+'; '.join(c.examples[:2]) if self.verifier_examples else '')
                    pairs.append((queries[i],document))
                    pair_keys.append((i,c.id))
        if pairs:
            ce_start=perf_counter()
            with torch.inference_mode():
                values=self.verifier.predict(pairs,batch_size=min(64,len(pairs)),show_progress_bar=False,
                                             activation_fn=torch.nn.Identity(),convert_to_numpy=True)
            ce_ms=(perf_counter()-ce_start)*1000
            for (i,key),value in zip(pair_keys,np.asarray(values).reshape(-1)):
                out[i]['methods'].setdefault('D',[]).append({'id':key,'score':float(value)})
            for item in out:
                item['methods']['D'].sort(key=lambda x:(-x['score'],x['id']))
                item['verifier_ms']=ce_ms
        for item in out:
            item['matcher_ms']=(perf_counter()-started)*1000
        return out
