"""DEV/INTERNAL-only final selection after auditing irrelevant-head gates."""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import shutil
import sys
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
import numpy as np
import torch
from assistant.router_v4 import Classifiers,embedding_encoder,serialize_context,bounded_text,artifact_hashes
from assistant import router_v3 as v3
from train_router_v4 import train_frozen,calibration_for,predictions,accepted_summary,digest
from prepare_router_v4 import write

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--device',choices=['cpu','cuda'],default='cpu');args=parser.parse_args()
    if (ROOT/'reports/assistant_router_v4_frozen_started.json').exists():raise SystemExit('Frozen TEST already started; candidate/threshold selection is forbidden')
    torch.set_num_threads(2)
    training=json.loads((ROOT/'reports/assistant_router_v4_training.json').read_text(encoding='utf8'))
    rows=list(map(json.loads,(ROOT/'training/assistant_router_v4/dataset.jsonl').read_text(encoding='utf8').splitlines()))
    idx={s:np.array([i for i,r in enumerate(rows) if r['split']==s]) for s in ['train','dev','internal']}
    rr={s:[rows[i] for i in ids] for s,ids in idx.items()}
    labels=json.loads((ROOT/'assistant/models/router_v4/labels.json').read_text(encoding='utf8'))
    base=v3.embedding_encoder();base.to(args.device)
    nums=np.array([v3.features(r['context']) for r in rows]);texts=[bounded_text(base.tokenizer,serialize_context(r['message'],r['context'])) for r in rows]
    unique=list(dict.fromkeys(r['message'] for r in rows));vectors=base.encode(unique,normalize_embeddings=True,batch_size=64,show_progress_bar=False)
    mapping=dict(zip(unique,vectors));mv=np.stack([mapping[r['message']] for r in rows]);cv=base.encode(texts,normalize_embeddings=True,batch_size=64,show_progress_bar=False)
    before=json.loads(json.dumps(training['ablations']));training['ablations_before_mask_gate_audit']=before
    for name,x in [('A_message',mv),('B_message_numeric',np.concatenate([mv,nums],1)),('C_serialized',cv),('D_serialized_numeric',np.concatenate([cv,nums],1))]:
        weights=train_frozen(x[idx['train']],rr['train'],labels);cal=calibration_for(rr['dev'],labels,weights,x[idx['dev']],x[idx['train']],rr['train'])
        training['ablations'][name]={s:accepted_summary(rr[s],predictions(labels,weights,x[idx[s]],cal),cal) for s in ['dev','internal']}
        print('MATCHED GATE ABLATION',name,training['ablations'][name]['dev']['coverage'],flush=True)
    del base;gc.collect();torch.cuda.empty_cache() if args.device=='cuda' else None
    choices=[]
    for trial in training['fine_tune_trials']:
        folder=ROOT/'assistant/models/router_v4_candidates'/('fine_'+trial['variant']);models=Classifiers(folder)
        encoder=embedding_encoder(folder);encoder.to(args.device)
        x=np.concatenate([encoder.encode(texts,normalize_embeddings=True,batch_size=64,show_progress_bar=False),nums],1)
        original=trial['policies'];trial['policies_before_mask_gate_audit']=original;policies={}
        for policy in ['joint','independent']:
            calibration={**models.calibration,'routing_head':policy}
            pred=models.predict(x)
            policies[policy]={s:accepted_summary(rr[s],[pred[i] for i in idx[s]],calibration) for s in ['dev','internal']}
        selected=max(policies,key=lambda p:policies[p]['dev']['coverage'] if (policies[p]['dev']['accepted_precision'] or 0)>=.97 else -1)
        trial['policies']=policies;trial['selected_policy']=selected
        # Reconfirm CPU latency before final seal. CPU runtime remains isolated.
        encoder.to('cpu');times=[]
        for text in [texts[i] for i in idx['dev'][:16]]:
            started=perf_counter();encoder.encode([text],normalize_embeddings=True,show_progress_bar=False);times.append((perf_counter()-started)*1000)
        trial['cpu_latency']={'median_ms':float(np.median(times)),'p95_ms':float(np.quantile(times,.95)),'samples':16,'device':'cpu','selection_data':'DEV'}
        d=policies[selected]['dev'];t=policies[selected]['internal'];lat=trial['cpu_latency']['p95_ms']
        precision=min(d['accepted_precision'] or 0,t['accepted_precision'] or 0);passes=precision>=.97 and lat<1000
        key=(passes,min(d['coverage'],t['coverage']) if passes else precision,min(d['coverage'],t['coverage']),-lat)
        choices.append((key,folder,trial,selected));del encoder,models;gc.collect()
        if args.device=='cuda':torch.cuda.empty_cache()
        print('FINAL DEV/INTERNAL',trial['variant'],selected,d['coverage'],d['accepted_precision'],t['coverage'],t['accepted_precision'],'CPU p95',lat,flush=True)
    _,folder,trial,selected=max(choices,key=lambda x:x[0]);out=ROOT/'assistant/models/router_v4'
    # Copy only known artifact paths inside the existing V4 directory. Preserve
    # earlier candidates and every V3 artifact; no filesystem deletions.
    for p in folder.rglob('*'):
        if p.is_file():dest=out/p.relative_to(folder);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    cal=json.loads((out/'calibration.json').read_text(encoding='utf8'));cal['routing_head']=selected
    cal['required_head_policy']='Only loss-supervised relevant heads gate each route; no thresholds lowered'
    (out/'calibration.json').write_text(json.dumps(cal,indent=2),encoding='utf8')
    manifest=json.loads((out/'manifest.json').read_text(encoding='utf8'));manifest['routing_policy']=selected;manifest['artifact_sha256']=artifact_hashes(out)
    manifest['final_selection']='DEV and INTERNAL only after masked-head audit; CPU latency measured before seal';(out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    training['chosen']=trial['variant'];training['chosen_architecture']=selected;training['mask_gate_audit']='Loss-masked field head cannot gate preference, masked criterion cannot gate field comparison; all class thresholds unchanged.'
    training['accepted_precision_definition']='Semantic action, relevant field/criterion, authoritative source and canonical reference binding. Raw ordinal-label accuracy is separately reported.'
    write('training',training);write('internal_test',trial['policies'][selected]['internal']);write('calibration',cal)
    write('risk_coverage',{'selection_data':'DEV ONLY thresholds, INTERNAL audit before frozen evaluation','dev':trial['policies'][selected]['dev'],'internal':trial['policies'][selected]['internal']})
    write('candidate_seal',{'manifest_sha256':digest(out/'manifest.json'),'runtime_sha256':digest(ROOT/'assistant/router_v4.py'),'candidate':str(out),
        'selected_from':'DEV + INTERNAL + CPU latency only','frozen_evaluation_started':False,'mask_audit_complete':True})
    print('FINAL CANDIDATE SEALED',flush=True)

if __name__=='__main__':main()
