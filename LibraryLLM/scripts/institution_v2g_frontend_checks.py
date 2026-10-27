"""Every frontend test file, production build and lint, with review receipts."""
import json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];FRONT=ROOT/'frontend';REPORTS=ROOT/'reports'
package=json.loads((FRONT/'package.json').read_text());results=[]
commands=[('default',['npm.cmd','test'])]
default=package['scripts']['test'];named=re.findall(r'npm run ([\w:-]+)',default)
used=set(re.findall(r'tests/[\w.-]+',default+' '+ ' '.join(package['scripts'][n] for n in named)))
extra=[p.relative_to(FRONT).as_posix() for p in (FRONT/'tests').glob('*.test.*') if p.relative_to(FRONT).as_posix() not in used and p.name!='institution-intelligence.test.tsx']
commands.append(('extended',['npx.cmd','tsx','--tsconfig','tsconfig.app.json','--test',*extra]))
commands.extend([('build',['npm.cmd','run','build']),('lint',['npm.cmd','run','lint'])])
for name,command in commands:
    with (REPORTS/f'institution_v2g_frontend_{name}.log').open('w',encoding='utf8') as log:
        result=subprocess.run(command,cwd=FRONT,stdout=log,stderr=subprocess.STDOUT,timeout=900)
    text=(REPORTS/f'institution_v2g_frontend_{name}.log').read_text(encoding='utf8')
    results.append({'group':name,'exit':result.returncode,'tests':sum(map(int,re.findall(r'(?:ℹ tests |# tests )(\d+)',text))),'files':extra if name=='extended' else None})
    (REPORTS/'institution_v2g_frontend_results.json').write_text(json.dumps(results,indent=2),encoding='utf8');print(name,result.returncode,flush=True)
raise SystemExit(any(r['exit'] for r in results))
