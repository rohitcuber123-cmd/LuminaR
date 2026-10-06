"""Explicit offline training. Never trains or activates a model at startup."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from scipy.optimize import minimize_scalar
from assistant.router_v3 import (ENCODER, FEATURE_VERSION, FAMILIES, features, embedding_encoder,
    probabilities, head_logits, structural_decision, Classifiers)
from router_v3_data import generate
REPORT_PREFIX='assistant_router_v3'


def write(name,data):
    name=name.replace('assistant_router_v3',REPORT_PREFIX,1)
    (ROOT/'reports'/name).write_text(json.dumps(data,indent=2,default=str),encoding='utf8')


def norm(message):
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in message.casefold()).split())


def train(output=None, report_prefix='assistant_router_v3'):
    global REPORT_PREFIX
    REPORT_PREFIX=report_prefix
    torch.manual_seed(731);np.random.seed(731);torch.set_num_threads(2)
    directory=Path(output) if output else ROOT/'assistant/models/router_v3';directory.mkdir(parents=True,exist_ok=True)
    if (directory/'manifest.json').exists():raise SystemExit('Artifact exists. Preserve evaluated artifacts; use a new version for further experiments.')
    started=perf_counter();encoder=embedding_encoder();load_ms=(perf_counter()-started)*1000
    import psutil,sentence_transformers
    frozen=[]
    for name in ['existing','hidden']:
        frozen+=json.loads((ROOT/'reports/assistant_router_v3_baseline_snapshot'/(name+'_sealed.json')).read_text(encoding='utf8'))
    rows=generate();generated_count=len(rows)
    forbidden={norm(r['message']) for r in frozen};seen=set();clean=[];rejected=[]
    for row in rows:
        key=norm(row['message'])
        if key in forbidden or key in seen:
            rejected.append({'id':row['id'],'reason':'TEST_EXACT_DUPLICATE' if key in forbidden else 'DATA_EXACT_DUPLICATE'});continue
        seen.add(key);clean.append(row)
    rows=clean
    assert all(1<=len(r['message'])<=4000 and r['intent_family']==FAMILIES[r['intent_subtypes']] for r in rows)
    assert len(rows)>=2000
    vectors=encoder.encode([r['message'] for r in rows],batch_size=64,normalize_embeddings=True,show_progress_bar=False)
    test_vectors=encoder.encode([r['message'] for r in frozen],batch_size=64,normalize_embeddings=True,show_progress_bar=False)
    similarity=vectors@test_vectors.T;nearest=similarity.argmax(axis=1);maxima=similarity.max(axis=1)
    flags=[{'training_id':r['id'],'test_index':int(nearest[i]),'similarity':float(maxima[i])}
           for i,r in enumerate(rows) if maxima[i]>=.97]
    write('assistant_router_v3_leakage.json',{'generated':generated_count,'retained':len(rows),'normalization':'casefold alphanumeric tokens',
        'rejections':rejected,'exact_test_overlap_after_filter':0,'near_duplicate_threshold':.97,'near_duplicate_flags':flags,
        'max_similarity':float(maxima.max()),'p95_similarity':float(np.quantile(maxima,.95)),
        'policy':'Independent definitions authored before similarity check; flags are reported, not used for TEST-driven phrasing or label changes.',
        'test_usage':'Only exact duplicate rejection and similarity audit before fitting. No TEST labels used to train or calibrate.'})
    dataset=ROOT/'training'/REPORT_PREFIX;dataset.mkdir(parents=True,exist_ok=True)
    data_path=dataset/'dataset.jsonl';data_path.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf8')
    digest=hashlib.sha256(data_path.read_bytes()).hexdigest()
    train_idx=np.asarray([i for i,r in enumerate(rows) if r['split']=='train']);dev_idx=np.asarray([i for i,r in enumerate(rows) if r['split']=='dev'])
    x=np.concatenate([vectors,np.asarray([features(r['context']) for r in rows])],axis=1).astype(np.float32)
    heads=['intent_family','intent_subtypes','reference','position','fields','criterion']
    labels={h:sorted({r[h] for r in rows}) for h in heads}
    comparisons={};chosen={};temperatures={};policies={};dev_preds={};dev_probs={};architecture={}
    parameter_count=0
    for head in heads:
        y=np.asarray([labels[head].index(r[head]) for r in rows]);xt=x[train_idx];yt=y[train_idx];xd=x[dev_idx];yd=y[dev_idx]
        n=len(labels[head]); counts=np.bincount(yt,minlength=n)
        centroids=np.stack([xt[yt==i].mean(axis=0) for i in range(n)]);centroids/=np.maximum(1e-8,np.linalg.norm(centroids,axis=1,keepdims=True))
        centroid_pred=(xd@centroids.T).argmax(axis=1)
        linear=LogisticRegression(C=8,class_weight='balanced',max_iter=700,solver='lbfgs').fit(xt,yt)
        if n==2:
            linear_w=np.concatenate([-linear.coef_/2,linear.coef_/2]);linear_b=np.concatenate([-linear.intercept_/2,linear.intercept_/2])
        else:linear_w=linear.coef_;linear_b=linear.intercept_
        linear_state={'weight':linear_w.astype(np.float32),'bias':linear_b.astype(np.float32)}
        network=torch.nn.Sequential(torch.nn.Linear(x.shape[1],64),torch.nn.ReLU(),torch.nn.Linear(64,n))
        optimizer=torch.optim.AdamW(network.parameters(),lr=.008,weight_decay=.01)
        loss_fn=torch.nn.CrossEntropyLoss(weight=torch.tensor(len(yt)/np.maximum(1,counts)/n,dtype=torch.float32))
        tx=torch.from_numpy(xt);ty=torch.from_numpy(yt.astype(np.int64))
        for epoch in range(100):
            optimizer.zero_grad();loss=loss_fn(network(tx),ty);loss.backward();optimizer.step()
        state={'hidden_weight':network[0].weight.detach().numpy(),'hidden_bias':network[0].bias.detach().numpy(),
               'weight':network[2].weight.detach().numpy(),'bias':network[2].bias.detach().numpy()}
        lp=head_logits(xd,linear_state);mlp=head_logits(xd,state)
        scores={'centroid':float((centroid_pred==yd).mean()),'linear':float((lp.argmax(1)==yd).mean()),'mlp64':float((mlp.argmax(1)==yd).mean())}
        winner='mlp64' if scores['mlp64']>scores['linear']+.005 else 'linear'
        weights=state if winner=='mlp64' else linear_state;chosen[head]=weights;architecture[head]=winner
        logits=head_logits(xd,weights)
        def nll(t):
            return float(-np.log(probabilities(logits,t)[np.arange(len(yd)),yd]+1e-10).mean())
        temperature=float(minimize_scalar(nll,bounds=(.25,3),method='bounded').x)
        p=probabilities(logits,temperature);pred=p.argmax(1);conf=p.max(1);margin=np.sort(p,axis=1)[:,-1]-np.sort(p,axis=1)[:,-2]
        temperatures[head]=temperature;dev_preds[head]=pred;dev_probs[head]=p
        policy={}
        for i,label in enumerate(labels[head]):
            best={'confidence':1.01,'margin':1.01,'accepted_dev':0,'dev_precision':None}
            for threshold in sorted(set([.5,*np.quantile(conf[pred==i],np.linspace(0,1,20)).tolist()])) if (pred==i).any() else []:
                mask=(pred==i)&(conf>=threshold)&(margin>=.05)
                support=int(mask.sum());precision=float((pred[mask]==yd[mask]).mean()) if support else 0
                target=.99 if head=='intent_subtypes' and label in {'BORROW','RETURN','RESERVE','ADD_LIST','REMOVE_LIST','CLEAR_LIST'} else .97
                if support>=8 and precision>=target and support>best['accepted_dev']:
                    best={'confidence':float(threshold),'margin':.05,'accepted_dev':support,'dev_precision':precision,'precision_target':target}
            policy[label]=best
        policies[head]=policy
        comparisons[head]={**scores,'selected':winner,'temperature':temperature,'dev_nll_before':nll(1),'dev_nll_after':nll(temperature),
            'class_counts_train':dict(zip(labels[head],counts.tolist()))}
        parameter_count+=sum(v.size for v in weights.values())
        torch.save({k:torch.from_numpy(v.copy()) for k,v in weights.items()},directory/(head+'.pt'))
        print('TRAIN',head,scores,'selected',winner,flush=True)
    # Compare joint flat subtype vs explicit family-constrained hierarchy on DEV.
    st=dev_probs['intent_subtypes'];fp=dev_preds['intent_family'];hier=[]
    for i in range(len(dev_idx)):
        family=labels['intent_family'][fp[i]];allowed=[j for j,s in enumerate(labels['intent_subtypes']) if FAMILIES[s]==family]
        hier.append(allowed[int(st[i,allowed].argmax())])
    gold=np.asarray([labels['intent_subtypes'].index(rows[i]['intent_subtypes']) for i in dev_idx])
    flat_accuracy=float((dev_preds['intent_subtypes']==gold).mean());hier_accuracy=float((np.asarray(hier)==gold).mean())
    # Preserve independent agreement check at runtime rather than masking errors.
    family_centroids=np.stack([vectors[train_idx][np.asarray([rows[i]['intent_family'] for i in train_idx])==label].mean(0) for label in labels['intent_family']])
    family_centroids/=np.linalg.norm(family_centroids,axis=1,keepdims=True)
    nearest_dev=(vectors[dev_idx]@family_centroids.T).max(1)
    ood_min=float(np.quantile(nearest_dev,.01))
    calibration={'temperatures':temperatures,'policies':policies,'centroids':family_centroids.tolist(),
        'ood_min_similarity':ood_min,'selection_data':'DEV ONLY','accepted_precision_target':.97,
        'mutations_always_fallback':True,'finite_dev_support_limitation':'Per-class empirical precision, minimum 8 accepted examples; not a statistical guarantee.'}
    (directory/'labels.json').write_text(json.dumps(labels,indent=2),encoding='utf8')
    (directory/'calibration.json').write_text(json.dumps(calibration,indent=2),encoding='utf8')
    artifact_sha={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.is_file()}
    manifest={'version':'3.0.0','created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'dataset_sha256':digest,'encoder':ENCODER,'dimension':384,'feature_dimension':x.shape[1]-384,
        'feature_version':FEATURE_VERSION,'label_sets':labels,'architecture':architecture,'parameter_count':parameter_count,
        'artifact_bytes':sum(p.stat().st_size for p in directory.iterdir() if p.is_file()),
        'artifact_sha256':artifact_sha,'thresholds':'calibration.json','evaluation_version':'frozen-116-and-121-v1',
        'activation':'explicit opt-in; existing_qwen default','miniLM_frozen':True}
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    models=Classifiers(directory);predictions=models.predict(x[dev_idx]);accepted=[];curve=[]
    for index,prediction in zip(dev_idx,predictions):
        decision,reason=structural_decision(prediction,rows[index]['context'],rows[index]['message'],calibration)
        correct=all(prediction[h]['label']==rows[index][h] for h in ['intent_family','intent_subtypes'])
        if FAMILIES[rows[index]['intent_subtypes']] in {'BOOK','COMPARE','DISCOVER'} and rows[index]['intent_subtypes']!='SEARCH':
            correct=correct and all(prediction[h]['label']==rows[index][h] for h in ['reference','position'])
        if rows[index]['intent_subtypes'] in {'FIELD','PREFERENCE'}:
            correct=correct and all(prediction[h]['label']==rows[index][h] for h in ['fields','criterion'])
        accepted.append({'id':rows[index]['id'],'accepted':decision is not None,'correct':correct,'reason':reason,
                         'confidence':min(prediction[h]['confidence'] for h in ['intent_family','intent_subtypes'])})
    for cutoff in np.linspace(.5,.999,15):
        selected=[r for r in accepted if r['accepted'] and r['confidence']>=cutoff]
        curve.append({'confidence_cutoff':float(cutoff),'coverage':len(selected)/len(accepted),
            'precision':sum(r['correct'] for r in selected)/len(selected) if selected else None})
    chosen_rows=[r for r in accepted if r['accepted']]
    write('assistant_router_v3_risk_coverage.json',{'split':'DEV ONLY','operating_point_selected_before_TEST':True,
        'coverage':len(chosen_rows)/len(accepted),'precision':sum(r['correct'] for r in chosen_rows)/len(chosen_rows) if chosen_rows else None,
        'curve':curve,'decisions':accepted})
    write('assistant_router_v3_calibration.json',calibration)
    write('assistant_router_v3_training.json',{'head_comparisons':comparisons,'flat_subtype_accuracy':flat_accuracy,
        'hierarchical_subtype_accuracy':hier_accuracy,'chosen_policy':'Independent factorized classifiers with family agreement gate',
        'manifest':manifest,'train_count':len(train_idx),'dev_count':len(dev_idx),'training_ms':(perf_counter()-started)*1000,
        'optimizer':'balanced LR C=8 or balanced-loss MLP64 AdamW 100 epochs; DEV architecture selection',
        'miniLM_finetuned':False,'test_labels_used':False})
    review=[rows[int(i)] for i in np.linspace(0,len(rows)-1,32)]
    write('assistant_router_v3_dataset.json',{'path':str(data_path),'sha256':digest,'generated':generated_count,'retained':len(rows),
        'train_count':len(train_idx),'dev_count':len(dev_idx),'split':'Disjoint TRAIN/DEV template authoring groups before augmentation',
        'provenance':'New hand-authored intent definitions + compositional topics/reference/purpose/polite variants; no Qwen authoring and no private chats',
        'limitations':'Synthetic coverage, repeated structures and polite variants inflate sample count; DEV differs by templates but shares vocabulary.',
        'template_groups':len({r['template_group'] for r in rows}),
        'manual_review_samples':review,'validation':'length, labels, normalization deduplication, exact TEST rejection, embedding-neighbor flags'})
    latencies={}
    for size in [1,8,16]:
        times=[]
        for _ in range(12):
            t=perf_counter();encoder.encode([r['message'] for r in rows[:size]],normalize_embeddings=True,show_progress_bar=False);times.append((perf_counter()-t)*1000)
        latencies[str(size)]={'median_batch_ms':float(np.median(times)),'p95_batch_ms':float(np.quantile(times,.95))}
    write('assistant_router_v3_encoder_audit.json',{'model':ENCODER,'sentence_transformers':sentence_transformers.__version__,
        'device':str(encoder.device),'dimension':384,'max_seq_length':encoder.max_seq_length,'startup_ms':load_ms,
        'rss_mb':psutil.Process().memory_info().rss/1048576,'parameter_count':sum(p.numel() for p in encoder.parameters()),
        'torch_threads':torch.get_num_threads(),'inference_benchmarks':latencies,
        'existing_instances':'Search and RAG load cached MiniLM on CUDA; not reused to avoid GPU contention and altered search settings.',
        'thread_safety':'Dedicated serialized CPU worker; bounded queue. No Search HTTP embedding calls. No per-request encoder load.'})
    print('ARTIFACT',manifest['parameter_count'],manifest['artifact_bytes'],'bytes DEV accepted',len(chosen_rows),'of',len(accepted),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',help='New artifact directory; an existing manifest is never overwritten')
    parser.add_argument('--report-prefix',default='assistant_router_v3',help='Use a new evidence namespace for reproduction')
    args=parser.parse_args();train(args.output,args.report_prefix)
