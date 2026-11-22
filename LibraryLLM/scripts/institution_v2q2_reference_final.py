"""Repeat complete reference matrix after count-aware prompt repair is loaded."""
from pathlib import Path
import json,socket,time,hashlib
R=Path(__file__).resolve().parents[1]
for _ in range(180):
 with socket.socket() as s:ready=s.connect_ex(('127.0.0.1',18005))==0
 runtime=json.loads((R/'reports/institution_v2q2_final_runtime.json').read_text())
 if ready and runtime['source_sha256']['assistant/qwen.py']==hashlib.sha256((R/'assistant/qwen.py').read_bytes()).hexdigest():break
 time.sleep(1)
else:raise RuntimeError('New owned runtime not ready; do not test an old source revision')
source=(R/'scripts/institution_v2q2_references.py').read_text().replace("out=R/'reports/institution_v2q2_references.json'", "out=R/'reports/institution_v2q2_references_final.json'")
exec(compile(source,'owned_reference_after','exec'),{'__name__':'__main__','__file__':str(R/'scripts/institution_v2q2_references.py')})
