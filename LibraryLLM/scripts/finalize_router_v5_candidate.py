"""Freeze the DEV-selected runtime before any sealed/old evaluation."""
import json
from pathlib import Path
import sys
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from assistant.router_v5.contracts import registry_hash
from router_v5_evidence import digest,write

def main():
    seal_path=ROOT/'reports/assistant_router_v5_candidate_seal.json'
    if seal_path.exists():raise SystemExit('Already frozen')
    dev=json.loads((ROOT/'reports/assistant_router_v5_dev.json').read_text(encoding='utf8'))
    hybrid=json.loads((ROOT/'reports/assistant_router_v5_dev_hybrid.json').read_text(encoding='utf8'))
    assert hybrid['complete'] and len(hybrid['cases'])==244
    directory=ROOT/'assistant/models/router_v5';directory.mkdir(parents=True,exist_ok=True)
    calibration=dev['selected_calibration']
    (directory/'calibration.json').write_text(json.dumps(calibration,indent=2),encoding='utf8')
    (directory/'contracts.json').write_bytes((ROOT/'reports/assistant_router_v5_contracts.json').read_bytes())
    files=['assistant/api.py','assistant/profiling.py','assistant/semantic.py']+[p.relative_to(ROOT).as_posix() for p in (ROOT/'assistant/router_v5').glob('*.py')]
    runtime={p:digest(ROOT/p) for p in files}
    model_caches={}
    cache=Path.home()/'.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots'
    for path in cache.rglob('*'):
        if path.is_file() and path.name in {'model.safetensors','config.json','tokenizer.json','modules.json','sentence_bert_config.json'}:
            model_caches[str(path)]=digest(path)
    manifest={'created_at':datetime.now(timezone.utc).isoformat(),'registry_sha256':registry_hash(),
              'method':dev['selected_method'],'verifier_enabled':False,'verifier_examples':True,
              'batch_size':dev['selected_batch_size'],'batch_delay_ms':5 if dev['selected_batch_size']>1 else 0,
              'dev_sha256':digest(ROOT/'evaluation/assistant_router_v5/dev.json'),
              'sealed_sha256':digest(ROOT/'evaluation/assistant_router_v5/sealed.json'),
              'artifact_sha256':{p:digest(directory/p) for p in ['calibration.json','contracts.json']},
              'cached_encoder_files':model_caches,'encoder_training':False,'default_mode':'existing_qwen',
              'framework_versions':{p:__import__('importlib.metadata').metadata.version(p) for p in ['torch','sentence-transformers','transformers','numpy']}}
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    seal={'created_at':datetime.now(timezone.utc).isoformat(),'manifest_sha256':digest(directory/'manifest.json'),
          'runtime_sha256':runtime,'dev_sha256':manifest['dev_sha256'],'sealed_sha256':manifest['sealed_sha256'],
          'registry_sha256':registry_hash(),'threshold_adjustment_after_seal_allowed':False,
          'dev_e_gateway_safety_note':'A regression test added a conservative minimum-three-character extracted title guard during DEV E. Thresholds were unchanged; any such DEV output must be rejected when summarizing final evidence.'}
    seal_path.write_text(json.dumps(seal,indent=2),encoding='utf8')
    print('CANDIDATE FROZEN',manifest['method'],manifest['batch_size'],flush=True)

if __name__=='__main__':main()
