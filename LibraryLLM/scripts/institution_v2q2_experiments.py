"""Serialize baseline PDF experiment, isolated candidate PDF experiment and matrix."""
from pathlib import Path
import json,time
R=Path(__file__).resolve().parents[1]
S=R/'.scratch/institution-v2q/validator-review/lab'
baseline=R/'reports/institution_v2q2_private_qwen.json'
for _ in range(900):
    if baseline.exists() and len(json.loads(baseline.read_text()))==12:break
    time.sleep(1)
else:raise RuntimeError('Original A/B experiment incomplete; do not overwrite or skip it')
source=(R/'scripts/institution_v2q2_private_qwen.py').read_text()
source=source.replace("out=R/'reports/institution_v2q2_private_qwen.json'", "out=R/'reports/institution_v2q2_private_candidate.json'")
source=source.replace("'iteration':iteration", "'candidate_used_in_owned_process_only':True,'iteration':iteration")
flag=S/'candidate.active';assert not flag.exists()
flag.write_text('Exact53a4bbd candidate prompt, process-local only')
try:exec(compile(source,'owned_candidate_private_experiment','exec'),{'__name__':'__main__','__file__':str(R/'scripts/institution_v2q2_private_qwen.py')})
finally:flag.unlink(missing_ok=True)
(S/'matrix.request').write_text('Start matched original/candidate validator-only matrix')
print('Candidate PDF run complete; matrix requested in the same resident Qwen process.',flush=True)
