"""Precision-first final operating-point selection; forbidden after frozen TEST."""
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from assistant.router_v4 import artifact_hashes
from train_router_v4 import digest
from prepare_router_v4 import write

def main():
    if (ROOT/'reports/assistant_router_v4_frozen_started.json').exists():raise SystemExit('Selection forbidden after frozen TEST started')
    data=json.loads((ROOT/'reports/assistant_router_v4_training.json').read_text(encoding='utf8'));options=[]
    for trial in data['fine_tune_trials']:
        for policy,results in trial['policies'].items():
            d=results['dev'];t=results['internal'];precision=min(d['accepted_precision'] or 0,t['accepted_precision'] or 0);coverage=min(d['coverage'],t['coverage']);lat=trial['cpu_latency']['p95_ms']
            passed=precision>=.97 and lat<1000
            options.append(((passed,coverage if passed else precision,coverage,-lat),trial,policy,results))
    key,trial,policy,results=max(options,key=lambda x:x[0]);folder=ROOT/'assistant/models/router_v4_candidates'/('fine_'+trial['variant']);out=ROOT/'assistant/models/router_v4'
    for p in folder.rglob('*'):
        if p.is_file():dest=out/p.relative_to(folder);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    cal=json.loads((out/'calibration.json').read_text(encoding='utf8'));cal['routing_head']=policy;cal['required_head_policy']='Only loss-supervised relevant heads gate each route; no thresholds lowered'
    (out/'calibration.json').write_text(json.dumps(cal,indent=2),encoding='utf8')
    manifest=json.loads((out/'manifest.json').read_text(encoding='utf8'));manifest['routing_policy']=policy;manifest['artifact_sha256']=artifact_hashes(out)
    manifest['final_selection']='Precision first across both loss variants and semantic policies; DEV + INTERNAL + CPU latency, before frozen TEST';(out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    data.update(chosen=trial['variant'],chosen_architecture=policy,final_operating_point={'dev':results['dev'],'internal':results['internal'],'cpu_latency':trial['cpu_latency'],'internal_precision_gate':key[0]},
        selection_rule='Among >=97% DEV/INTERNAL candidates maximise coverage. If none passes, maximise minimum precision, then coverage; report failure, never lower thresholds.')
    write('training',data);write('internal_test',results['internal']);write('calibration',cal);write('risk_coverage',{'selection_data':'DEV ONLY calibration; precision-first INTERNAL audit','dev':results['dev'],'internal':results['internal']})
    write('candidate_seal',{'manifest_sha256':digest(out/'manifest.json'),'runtime_sha256':digest(ROOT/'assistant/router_v4.py'),'candidate':str(out),
        'selected_from':'DEV + INTERNAL + CPU latency; precision first','frozen_evaluation_started':False,'internal_gate_passed':key[0]})
    print('SEALED',trial['variant'],policy,'INTERNAL',results['internal']['accepted_precision'],results['internal']['coverage'],'PASS',key[0],flush=True)

if __name__=='__main__':main()
