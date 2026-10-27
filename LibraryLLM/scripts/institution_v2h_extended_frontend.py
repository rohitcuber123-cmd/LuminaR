"""Run frontend files outside the already executed default suite."""
import json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];FRONT=ROOT/'frontend'
package=json.loads((FRONT/'package.json').read_text());default=package['scripts']['test']
named=re.findall(r'npm run ([\w:-]+)',default)
used=set(re.findall(r'tests/[\w.-]+',default+' '+' '.join(package['scripts'][n] for n in named)))
extra=[p.relative_to(FRONT).as_posix() for p in (FRONT/'tests').glob('*.test.*') if p.relative_to(FRONT).as_posix() not in used]
with (ROOT/'reports/institution_v2h_frontend_extended.log').open('w',encoding='utf8') as log:
    result=subprocess.run(['npx.cmd','tsx','--tsconfig','tsconfig.app.json','--test',*extra],cwd=FRONT,stdout=log,stderr=subprocess.STDOUT,timeout=900)
print('Extended frontend exit',result.returncode);raise SystemExit(result.returncode)
