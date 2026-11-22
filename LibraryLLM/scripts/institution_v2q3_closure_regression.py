"""Run final accepted full inventory after preliminary run releases report files."""
from pathlib import Path
from time import sleep,perf_counter
import hashlib,json,subprocess,sys,psutil
R=Path(__file__).resolve().parents[1]
for _ in range(5400):
 active=[p for p in psutil.process_iter(['name','cmdline']) if p.info['name'].lower() in ['python.exe','pythonw.exe'] and any(a.endswith('institution_v2q3_final_regression.py') for a in p.info['cmdline'] or [])]
 if not active:break
 sleep(1)
else:raise RuntimeError('Initial runner still active')
for name in ['backend_tests','final_source']:
 original=R/f'reports/institution_v2q3_{name}.json'
 if original.exists():(R/f'reports/institution_v2q3_preliminary_{name}.json').write_bytes(original.read_bytes())
baseline=json.loads((R/'reports/institution_v2q3_checkpoint.json').read_text())
names=set(baseline['source_sha256'])|{'assistant/digital_availability.py','backend/services/book_digital_availability.py','tests/institution_v2q_ai/test_digital_availability.py','frontend/tests/assistant-library-scope.test.tsx'}
sha=lambda name:hashlib.sha256((R/name).read_bytes()).hexdigest()
freeze={n:sha(n) for n in names}
(R/'reports/institution_v2q3_final_source.json').write_text(json.dumps({'source_sha256':freeze},indent=2))
start=perf_counter()
with (R/'reports/institution_v2q3_closure_backend.log').open('w',encoding='utf8') as out:
 p=subprocess.run([sys.executable,str(R/'scripts/institution_v2q_ai_checks.py'),'backend','2q3_closure'],cwd=R,stdout=out,stderr=subprocess.STDOUT,timeout=5400)
rows=json.loads((R/'reports/institution_v2q_2q3_closure_backend.json').read_text())
counts={k:sum(x.get(k,0) for x in rows) for k in ['passed','failed','skipped']}
drift=[n for n,v in freeze.items() if sha(n)!=v]
data={'counts':counts,'exit':p.returncode,'groups':rows,'group_count':len(rows),'seconds':perf_counter()-start,'source_stable':not drift,'unexpected_source_changes':drift,'source_sha256':freeze,'inventory':'Accepted complete product inventory through Part2Q,38isolated groups including Events; additional Part2Q.2 tests collected in institution_v2q_ai.','baseline':[3102,0,20]}
(R/'reports/institution_v2q3_backend_tests.json').write_text(json.dumps(data,indent=2))
print(json.dumps({'counts':counts,'exit':p.returncode,'groups':len(rows),'source_stable':not drift}),flush=True)
raise SystemExit(p.returncode or bool(drift) or len(rows)!=38)
