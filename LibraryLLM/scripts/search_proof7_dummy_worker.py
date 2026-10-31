"""Process-budget test double; never imports a learned runtime."""
import json,sys,time
cfg=json.loads(sys.stdin.readline())
if cfg.get('sleep'):time.sleep(cfg['sleep'])
print(json.dumps({'event':'test_double','model_calls':0}),flush=True)
