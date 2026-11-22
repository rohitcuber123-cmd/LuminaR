from pathlib import Path
import subprocess,json,time
R=Path(__file__).resolve().parents[1];rows=[]
for name,command in [('frontend',['npm.cmd','test']),('build',['npm.cmd','run','build']),('lint',['npm.cmd','run','lint'])]:
 log=R/f'reports/institution_v2q2_{name}.log';start=time.perf_counter()
 with log.open('w',encoding='utf8') as out:p=subprocess.run(command,cwd=R/'frontend',stdout=out,stderr=subprocess.STDOUT,timeout=900)
 rows.append({'check':name,'exit':p.returncode,'seconds':time.perf_counter()-start,'log':log.name});(R/'reports/institution_v2q2_frontend_checks.json').write_text(json.dumps(rows,indent=2));print(name,p.returncode,flush=True)
raise SystemExit(any(x['exit'] for x in rows))
