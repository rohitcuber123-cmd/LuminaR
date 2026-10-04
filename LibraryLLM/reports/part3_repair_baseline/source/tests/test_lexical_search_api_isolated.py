"""Real /search HTTP route with isolated Mongo and stub semantic index."""
import json
from pathlib import Path
import subprocess
import sys


def test_search_api_lexical_batches_without_real_hnsw():
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run([sys.executable,str(root/'scripts/run_isolated_search_api_lexical.py')],
                          cwd=root,text=True,capture_output=True,timeout=120)
    assert result.returncode==0,result.stderr
    marker=next(line for line in result.stdout.splitlines() if line.startswith('RESULT_JSON:'))
    report=json.loads(marker[len('RESULT_JSON:'):])
    assert report['database']=='isolated' and report['actual_search_route'] and report['auth']
    assert report['concurrent_completed']==5
    assert all(report[key]=='PASS' for key in (
        'flag_off','flag_on','exact_title','author','typos','dedupe',
        'mongo_authority','fallback','public_schema'))
