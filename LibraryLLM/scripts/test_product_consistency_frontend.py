"""Sequential frontend checks with retained logs; avoids host memory contention."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / 'frontend'
REPORTS = ROOT / 'reports'


def main():
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    node = shutil.which('node')
    extended = ['admin-notifications', 'document-cache', 'events', 'kg-product', 'knowledge-graph',
        'loan-renewal', 'mind-map', 'part3-contract', 'rag-answer', 'search-depth']
    runs = [
        ('default', [npm, 'test']),
        ('extended', [node, str(FRONTEND / 'node_modules/tsx/dist/cli.mjs'), '--tsconfig', 'tsconfig.app.json', '--test']
            + [next(str(p.relative_to(FRONTEND)) for p in (FRONTEND / 'tests').glob(label + '.test.*')) for label in extended]),
        ('build', [npm, 'run', 'build']), ('lint', [npm, 'run', 'lint'])]
    results = []
    for label, command in runs:
        path = REPORTS / ('product_consistency_frontend_' + label + '.log')
        with path.open('w', encoding='utf8') as log:
            run = subprocess.run(command, cwd=FRONTEND, stdout=log, stderr=subprocess.STDOUT)
        content = path.read_text(encoding='utf8')
        result = {'group': label, 'exit': run.returncode, 'log': path.name,
            'passed': sum(map(int, re.findall(r'ℹ pass (\d+)', content))),
            'failed': sum(map(int, re.findall(r'ℹ fail (\d+)', content))),
            'warnings': len(re.findall(r': warning ', content))}
        results.append(result)
        (REPORTS / 'product_consistency_frontend_results.json').write_text(json.dumps(results, indent=2), encoding='utf8')
        print(label, run.returncode, result['passed'], flush=True)
        if run.returncode: sys.exit(run.returncode)


if __name__ == '__main__': main()
