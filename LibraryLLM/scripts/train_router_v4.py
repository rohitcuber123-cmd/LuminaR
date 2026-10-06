"""Explicit offline fine-tuning; DEV calibration, independent INTERNAL test."""
import argparse
from collections import Counter,defaultdict
import copy
import datetime
import hashlib
import json
from pathlib import Path
import random
import shutil
import sys
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import numpy as np
import torch
from scipy.optimize import minimize_scalar
from sklearn.linear_model import LogisticRegression
from assistant import router_v3 as v3
from assistant.router_v4 import serialize_context,bounded_text,Classifiers,structural_decision,artifact_hashes
from router_v4_data import HEADS,seed_rows,build,norm,loss_mask
from prepare_router_v4 import statistics,write

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def split_guard(rows):
    splits=defaultdict(set);messages=defaultdict(set)
    for r in rows:splits[r['family_id']].add(r['split']);messages[norm(r['message'])].add(r['split'])
    if any(len(s)>1 for s in splits.values()) or any(len(s)>1 for s in messages.values()):raise ValueError('Seed-family or normalized-message split leak')

def masked_loss(logits,targets,masks,weights):
    loss=next(iter(logits.values())).sum()*0
    for h,p in logits.items():
        m=masks[h].bool()
        if m.any():loss=loss+weights[h]*torch.nn.functional.cross_entropy(p[m],targets[h][m])
    return loss

class Heads(torch.nn.Module):
    def __init__(self,labels,dim):
        super().__init__();self.heads=torch.nn.ModuleDict({h:torch.nn.Linear(dim,len(ls)) for h,ls in labels.items()})
    def forward(self,x):return {h:f(x) for h,f in self.heads.items()}
    def arrays(self):return {h:{'weight':f.weight.detach().cpu().numpy(),'bias':f.bias.detach().cpu().numpy()} for h,f in self.heads.items()}

def components(rows,pred):
    return {h:{'accuracy':float(np.mean([p[h]['label']==r[h] for r,p in zip(rows,pred) if loss_mask(r,h)])),
               'n':sum(loss_mask(r,h) for r in rows)} for h in HEADS}

def accepted_summary(rows,pred,calibration):
    items=[]
    for r,p in zip(rows,pred):
        decision,reason=structural_decision(p,r['context'],r['message'],calibration)
        if calibration['routing_head']=='joint':sub,_,field=p['action']['label'].partition(':');okay=sub==r['intent_subtypes'] and (sub!='FIELD' or field==r['fields'])
        else:okay=p['intent_subtypes']['label']==r['intent_subtypes'] and p['intent_family']['label']==r['intent_family'] and (r['intent_subtypes']!='FIELD' or p['fields']['label']==r['fields'])
        if r['intent_subtypes'] in v3.BOOK_SUBTYPES|{'RECOMMEND'}:
            okay=okay and p['reference']['label']==r['reference']
            if r['reference'] not in {'NONE','EXPLICIT','AMBIGUOUS'}:
                # Accepted precision measures actual canonical binding. FIRST
                # and FOCUS can identify the same book in a one-book context;
                # raw position-head accuracy remains separately reported.
                try:
                    _,pool=v3.context_pool(r['context']);focus=r['context'].get('last_referenced_work_ids',[])
                    okay=okay and v3.bind_position(pool,p['position']['label'],focus)==v3.bind_position(pool,r['position'],focus)
                except ValueError:okay=False
        if r['intent_subtypes']=='PREFERENCE':okay=okay and p['criterion']['label']==r['criterion']
        items.append({'id':r['id'],'accepted':decision is not None,'correct':bool(okay),'reason':reason})
    selected=[r for r in items if r['accepted']]
    return {'coverage':len(selected)/len(rows),'accepted_precision':sum(r['correct'] for r in selected)/len(selected) if selected else None,
            'accepted':len(selected),'cases':len(rows),'components':components(rows,pred),'reasons':dict(Counter(r['reason'] for r in items)),'decisions':items}

def calibration_for(rows,labels,weights,x,train_x,train_rows):
    temperatures={};policies={}
    for h,w in weights.items():
        mask=np.array([loss_mask(r,h) for r in rows]);yd=np.array([labels[h].index(r[h]) for r in rows]);logits=v3.head_logits(x,w)
        def nll(t):return float(-np.log(v3.probabilities(logits[mask],t)[np.arange(mask.sum()),yd[mask]]+1e-10).mean())
        t=float(minimize_scalar(nll,bounds=(.3,3),method='bounded').x) if mask.any() else 1.
        temperatures[h]=t;p=v3.probabilities(logits,t);pred=p.argmax(1);conf=p.max(1);margin=np.sort(p,axis=1)[:,-1]-np.sort(p,axis=1)[:,-2]
        policies[h]={}
        for i,label in enumerate(labels[h]):
            best={'confidence':1.01,'margin':1.01,'accepted_dev':0,'dev_precision':None}
            subset=(pred==i)&mask
            for threshold in sorted(set([.5,*np.quantile(conf[subset],np.linspace(0,1,25)).tolist()])) if subset.any() else []:
                selected=subset&(conf>=threshold)&(margin>=.05);n=int(selected.sum());precision=float((pred[selected]==yd[selected]).mean()) if n else 0
                if n>=12 and precision>=.97 and n>best['accepted_dev']:
                    best={'confidence':float(threshold),'margin':.05,'accepted_dev':n,'dev_precision':precision,
                          'dev_seed_families':len({r['family_id'] for j,r in enumerate(rows) if selected[j]})}
            policies[h][label]=best
    centroids=np.stack([train_x[[r['intent_family']==f for r in train_rows],:384].mean(0) for f in labels['intent_family']]);centroids/=np.maximum(1e-8,np.linalg.norm(centroids,axis=1,keepdims=True))
    nearest=(x[:,:384]@centroids.T).max(1)
    return {'temperatures':temperatures,'policies':policies,'centroids':centroids.tolist(),'ood_min_similarity':float(np.quantile(nearest,.01)),
        'routing_head':'joint','selection_data':'DEV ONLY','accepted_precision_target':.97,'mutations_always_fallback':True,
        'limitation':'Empirical precision with >=12 examples/class; context variants are correlated. No population guarantee.'}

def predictions(labels,weights,x,cal):
    obj=Classifiers.__new__(Classifiers);obj.labels=labels;obj.weights=weights;obj.calibration=cal;obj.centroids=np.array(cal['centroids']);return obj.predict(x)

def train_frozen(x,rows,labels):
    weights={}
    for h,ls in labels.items():
        mask=np.array([loss_mask(r,h) for r in rows]);y=np.array([ls.index(r[h]) for r in rows])[mask]
        clf=LogisticRegression(C=8,class_weight='balanced',max_iter=300).fit(x[mask],y)
        w=np.zeros((len(ls),x.shape[1]),dtype=np.float32);b=np.zeros(len(ls),dtype=np.float32)
        if len(clf.classes_)==2:
            cw=np.concatenate([-clf.coef_/2,clf.coef_/2]);cb=np.concatenate([-clf.intercept_/2,clf.intercept_/2])
        else:cw=clf.coef_;cb=clf.intercept_
        w[clf.classes_]=cw;b[clf.classes_]=cb;weights[h]={'weight':w,'bias':b}
    return weights

def fine_tune(texts,nums,rows,labels,device,loss_weights,seed):
    from sentence_transformers import SentenceTransformer
    torch.manual_seed(seed);np.random.seed(seed);random.seed(seed)
    encoder=SentenceTransformer(v3.ENCODER,device=device,local_files_only=True);encoder.max_seq_length=256
    heads=Heads(labels,408).to(device)
    # ST 5.6 tokenize/preprocess may return Python lists. Use the unchanged
    # encoder tokenizer with explicit tensors for differentiable mini-batches.
    tokens=encoder.tokenizer(texts,padding=True,truncation=True,max_length=256,return_tensors='pt')
    y={h:torch.tensor([ls.index(r[h]) for r in rows]) for h,ls in labels.items()};m={h:torch.tensor([loss_mask(r,h) for r in rows]) for h in labels}
    train=np.array([i for i,r in enumerate(rows) if r['split']=='train']);dev=np.array([i for i,r in enumerate(rows) if r['split']=='dev']);numbers=torch.tensor(nums,dtype=torch.float32)
    counts=Counter(rows[i]['action'] for i in train);sampling=torch.tensor([1/counts[rows[i]['action']] for i in train],dtype=torch.double)
    opt=torch.optim.AdamW([{'params':encoder.parameters(),'lr':2e-5},{'params':heads.parameters(),'lr':.002}],weight_decay=.01)
    scaler=torch.amp.GradScaler('cuda',enabled=device.startswith('cuda'));best=None;best_loss=float('inf');patience=0;history=[]
    def forward(ids):
        batch={k:v[ids].to(device) for k,v in tokens.items()};v=encoder(batch)['sentence_embedding'];v=torch.nn.functional.normalize(v,dim=1)
        return heads(torch.cat([v,numbers[ids].to(device)],1))
    for epoch in range(6):
        encoder.train();heads.train();picked=train[torch.multinomial(sampling,len(train),replacement=True).numpy()];train_losses=[]
        for start in range(0,len(picked),32):
            ids=torch.tensor(picked[start:start+32]);opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type='cuda',enabled=device.startswith('cuda')):
                logits=forward(ids);loss=masked_loss(logits,{h:v[ids].to(device) for h,v in y.items()},{h:v[ids].to(device) for h,v in m.items()},loss_weights)
            scaler.scale(loss).backward();scaler.unscale_(opt);torch.nn.utils.clip_grad_norm_([*encoder.parameters(),*heads.parameters()],1.)
            scaler.step(opt);scaler.update();train_losses.append(float(loss.detach()))
        encoder.eval();heads.eval();dev_losses=[]
        with torch.inference_mode():
            for start in range(0,len(dev),64):
                ids=torch.tensor(dev[start:start+64]);logits=forward(ids)
                dev_losses.append(float(masked_loss(logits,{h:v[ids].to(device) for h,v in y.items()},{h:v[ids].to(device) for h,v in m.items()},loss_weights)))
        value=float(np.mean(dev_losses));history.append({'epoch':epoch+1,'train_loss':float(np.mean(train_losses)),'dev_loss':value})
        print('FINETUNE',loss_weights,history[-1],flush=True)
        if value<best_loss-.005:
            best_loss=value;patience=0;best=({k:v.detach().cpu().clone() for k,v in encoder.state_dict().items()},{k:v.detach().cpu().clone() for k,v in heads.state_dict().items()})
        else:patience+=1
        if patience>=2:break
    encoder.load_state_dict(best[0]);heads.load_state_dict(best[1]);encoder.eval();heads.eval()
    x=np.concatenate([encoder.encode(texts,normalize_embeddings=True,batch_size=64,show_progress_bar=False),nums],axis=1)
    return encoder,heads.arrays(),x,history

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);parser.add_argument('--seed',type=int,default=947);parser.add_argument('--device',choices=['cpu','cuda'],default='cpu');args=parser.parse_args()
    output=Path(args.output)
    if (output/'manifest.json').exists():raise SystemExit('Preserve evaluated artifact. Use a new output directory.')
    review_path=ROOT/'training/assistant_router_v4/approved_review.json'
    if not review_path.exists():raise SystemExit('Manual review missing; refusing training')
    review=json.loads(review_path.read_text(encoding='utf8'))
    if review['reviewed']<200 or not review['approved']:raise SystemExit('Manual review incomplete/unapproved')
    torch.set_num_threads(2);torch.manual_seed(args.seed);started=perf_counter()
    directory=ROOT/'training/assistant_router_v4';accepted=json.loads((directory/'validated_paraphrases.json').read_text(encoding='utf8'));para=defaultdict(list)
    rejected_review=set(review.get('rejected_keys',[]))
    for p in accepted:
        if p['seed_id']+':'+str(p['index']) not in rejected_review:para[p['seed_id']].append(p['text'])
    rows,rejected=build(para,args.seed);split_guard(rows)
    path=directory/'dataset.jsonl';path.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf8')
    split_path=directory/'seed_split.json';split_path.write_text(json.dumps({s['seed_id']:s['split'] for s in seed_rows()},indent=2),encoding='utf8')
    labels={h:sorted({r[h] for r in rows}) for h in HEADS}
    train=np.array([i for i,r in enumerate(rows) if r['split']=='train']);dev=np.array([i for i,r in enumerate(rows) if r['split']=='dev']);internal=np.array([i for i,r in enumerate(rows) if r['split']=='internal'])
    rtrain=[rows[i] for i in train];rdev=[rows[i] for i in dev];rinternal=[rows[i] for i in internal]
    encoder=v3.embedding_encoder()
    if args.device=='cuda':encoder.to('cuda')
    texts=[bounded_text(encoder.tokenizer,serialize_context(r['message'],r['context'])) for r in rows]
    print('OFFLINE EMBEDDINGS',len(rows),str(encoder.device),flush=True)
    nums=np.array([v3.features(r['context']) for r in rows]);vectors=encoder.encode(texts,normalize_embeddings=True,batch_size=64,show_progress_bar=False)
    unique_messages=list(dict.fromkeys(r['message'] for r in rows))
    message_vectors=encoder.encode(unique_messages,normalize_embeddings=True,batch_size=64,show_progress_bar=False)
    mv=np.stack([message_vectors[unique_messages.index(r['message'])] for r in rows])
    print('OFFLINE EMBEDDINGS COMPLETE',flush=True)
    experiments={};candidates=ROOT/'assistant/models/router_v4_candidates';candidates.mkdir(exist_ok=True,parents=True)
    for name,x in [('A_message',mv),('B_message_numeric',np.concatenate([mv,nums],1)),('C_serialized',vectors),('D_serialized_numeric',np.concatenate([vectors,nums],1))]:
        weights=train_frozen(x[train],rtrain,labels);cal=calibration_for(rdev,labels,weights,x[dev],x[train],rtrain)
        # pad zero numeric columns for the A/C policy only; heads see original x.
        experiments[name]={'dev':accepted_summary(rdev,predictions(labels,weights,x[dev],cal),cal),'internal':accepted_summary(rinternal,predictions(labels,weights,x[internal],cal),cal)}
        print('ABLATION',name,experiments[name]['dev']['coverage'],experiments[name]['internal']['coverage'],flush=True)
    old=v3.Classifiers();oldx=np.concatenate([mv,nums],1);oldpred=old.predict(oldx[internal]);old_summary=[]
    for r,p in zip(rinternal,oldpred):
        d,reason=v3.structural_decision(p,r['context'],r['message'],old.calibration)
        old_summary.append({'accepted':d is not None,'correct':p['intent_subtypes']['label']==r['intent_subtypes'],'reason':reason})
    experiments['V3_old_heads']={'internal':{'coverage':sum(x['accepted'] for x in old_summary)/len(old_summary),
        'subtype_accuracy':float(np.mean([x['correct'] for x in old_summary]))}}
    # Leakage audit is diagnostic/exact-rejection only. No TEST targets enter
    # the loss, architecture selection, early stopping or confidence fitting.
    frozen=sum([json.loads((ROOT/('reports/assistant_router_v3_baseline_snapshot/'+n+'_sealed.json')).read_text(encoding='utf8')) for n in ['existing','hidden']],[])
    unique=list({r['message']:r for r in rows}.values());uv=encoder.encode([r['message'] for r in unique],normalize_embeddings=True,batch_size=64,show_progress_bar=False)
    tv=encoder.encode([r['message'] for r in frozen],normalize_embeddings=True,batch_size=64,show_progress_bar=False);sim=uv@tv.T
    write('leakage',{'exact_overlap':len({norm(r['message']) for r in rows}&{norm(r['message']) for r in frozen}), 'family_split_overlap':0,
        'rejections':rejected,'test_usage':'Only exact duplicate rejection and diagnostic similarity; no training/evaluation tuning',
        'near_threshold':.97,'near_flags':[{'training_id':unique[i]['id'],'similarity':float(s)} for i,s in enumerate(sim.max(1)) if s>=.97],
        'max_similarity':float(sim.max()),'p95_similarity':float(np.quantile(sim.max(1),.95))})
    from sklearn.cluster import MiniBatchKMeans
    cluster=MiniBatchKMeans(n_clusters=min(64,len(unique)),random_state=args.seed,n_init=3).fit(uv)
    v3rows=list(map(json.loads,(ROOT/'training/assistant_router_v3/dataset.jsonl').read_text(encoding='utf8').splitlines()))
    gap={'v3':statistics(v3rows),'frozen_116':statistics(frozen[:116]),'frozen_121':statistics(frozen[116:]),'v4':statistics(rows),
        'v4_embedding_clusters':dict(Counter(map(str,cluster.labels_))), 'hypothesis':'Template overfitting supported by repeated politeness wrappers, synthetic focus bias, and large DEV/frozen performance gap; not a causal proof.',
        'limitations':'Skeleton normalisation is a lower-bound lexical diagnostic. Embedding clusters are descriptive, not semantic-family certification.'}
    write('dataset_gap',gap)
    (ROOT/'reports/assistant_router_v4_dataset_gap.md').write_text('V3 template overfitting is supported, not causally proven.\n\nV3: '+json.dumps(gap['v3'],indent=2)+'\n\nV4: '+json.dumps(gap['v4'],indent=2)+'\n\nFrozen distribution summary is diagnostic only; no labels/text were used to train or calibrate.\n',encoding='utf8')
    write('dataset',{'path':str(path),'sha256':digest(path),'size':len(rows),'split':dict(Counter(r['split'] for r in rows)), 'seeds':len(seed_rows()),'seed_split_sha256':digest(split_path),
        'sources':dict(Counter(r['origin'] for r in rows)),'context_states':dict(Counter(r['context_kind'] for r in rows)),
        'unique_messages':len(unique),'quality_review':review,'template_diversity':gap['v4'],'frozen_labels_in_training':False})
    del encoder,old;import gc;gc.collect()
    chosen=None;trials=[]
    for variant,loss_weights in [('equal',{h:1. for h in HEADS}),('critical',{'intent_family':.3,'intent_subtypes':1.,'reference':1.,'position':1.2,'fields':.8,'criterion':.6,'action':1.2})]:
        model,weights,x,history=fine_tune(texts,nums,rows,labels,args.device,loss_weights,args.seed)
        cal=calibration_for(rdev,labels,weights,x[dev],x[train],rtrain)
        policies={}
        for routing in ['independent','joint']:
            c={**cal,'routing_head':routing};policies[routing]={'dev':accepted_summary(rdev,predictions(labels,weights,x[dev],c),c),'internal':accepted_summary(rinternal,predictions(labels,weights,x[internal],c),c)}
        selected=max(policies,key=lambda k: policies[k]['dev']['coverage'] if (policies[k]['dev']['accepted_precision'] or 0)>=.97 else -1)
        cal['routing_head']=selected;d=policies[selected]['dev'];t=policies[selected]['internal']
        folder=candidates/('fine_'+variant);folder.mkdir(exist_ok=False);model.save_pretrained(str(folder/'encoder'),safe_serialization=True)
        torch.save({h:{k:torch.from_numpy(v.copy()) for k,v in w.items()} for h,w in weights.items()},folder/'heads.pt')
        (folder/'labels.json').write_text(json.dumps(labels,indent=2),encoding='utf8');(folder/'calibration.json').write_text(json.dumps(cal,indent=2),encoding='utf8')
        import sentence_transformers,transformers,sklearn
        manifest={'version':'4.0.0','created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'encoder':v3.ENCODER,'encoder_finetuned':True,
            'dataset_sha256':digest(path),'seed_split_sha256':digest(split_path),'input_dimension':408,'dimension':384,'max_tokens':256,'numeric_features':24,
            'training':{'seed':args.seed,'device':args.device,'learning_rate':2e-5,'head_learning_rate':.002,'epochs_max':6,'early_stopping_patience':2,'gradient_clip':1.,'balanced_action_sampler':True,'history':history},
            'loss_weights':loss_weights,'heads':labels,'routing_policy':selected,'thresholds':'calibration.json',
            'frameworks':{'torch':torch.__version__,'sentence_transformers':sentence_transformers.__version__,'transformers':transformers.__version__,'sklearn':sklearn.__version__},
            'artifact_sha256':artifact_hashes(folder),'activation':'experimental opt-in only; existing_qwen default'}
        manifest['finetuned_encoder_sha256']=hashlib.sha256(json.dumps({k:v for k,v in manifest['artifact_sha256'].items() if k.startswith('encoder/')},sort_keys=True).encode()).hexdigest()
        manifest['artifact_bytes']=sum(p.stat().st_size for p in folder.rglob('*') if p.is_file());(folder/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
        # Explicit CPU latency before selecting/sealing; no Qwen or frozen TEST.
        model.to('cpu');torch.set_num_threads(2);cpu_times=[]
        for r in rdev[:16]:
            t0=perf_counter();model.encode([bounded_text(model.tokenizer,serialize_context(r['message'],r['context']))],normalize_embeddings=True,show_progress_bar=False)
            cpu_times.append((perf_counter()-t0)*1000)
        cpu={'median_ms':float(np.median(cpu_times)),'p95_ms':float(np.quantile(cpu_times,.95)),'device':'cpu','samples':16,'selection_data':'DEV'}
        trial={'variant':variant,'policies':policies,'selected_policy':selected,'history':history,'manifest':manifest,'cpu_latency':cpu};trials.append(trial)
        score=(min(d['accepted_precision'] or 0,t['accepted_precision'] or 0)>=.97, min(d['coverage'],t['coverage']))
        if chosen is None or score>chosen[0]:chosen=(score,folder,trial)
        del model;gc.collect()
        if args.device=='cuda':torch.cuda.empty_cache()
        print('TRIAL',variant,'DEV',d['coverage'],d['accepted_precision'],'INTERNAL',t['coverage'],t['accepted_precision'],flush=True)
    output.mkdir(parents=True,exist_ok=True)
    for p in chosen[1].iterdir():
        if p.is_dir():shutil.copytree(p,output/p.name)
        else:shutil.copy2(p,output/p.name)
    # Candidate is sealed before any frozen-test runner can be invoked.
    seal={'manifest_sha256':digest(output/'manifest.json'),'runtime_sha256':digest(ROOT/'assistant/router_v4.py'),
          'candidate':str(output),'selected_from':'DEV + INTERNAL only','frozen_evaluation_started':False}
    write('candidate_seal',seal);write('training',{'ablations':experiments,'fine_tune_trials':trials,'chosen':chosen[2]['variant'],'chosen_architecture':chosen[2]['selected_policy'],'duration_ms':(perf_counter()-started)*1000,'test_used_for_selection':False})
    write('internal_test',chosen[2]['policies'][chosen[2]['selected_policy']]['internal']);write('calibration',json.loads((output/'calibration.json').read_text(encoding='utf8')))
    write('risk_coverage',{'operating_point':'Selected DEV class thresholds; internal audited before frozen evaluation','dev':chosen[2]['policies'][chosen[2]['selected_policy']]['dev'], 'internal':chosen[2]['policies'][chosen[2]['selected_policy']]['internal']})
    print('CANDIDATE SEALED',seal,flush=True)

if __name__=='__main__':main()
