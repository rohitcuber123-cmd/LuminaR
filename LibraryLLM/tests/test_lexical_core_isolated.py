"""Run real authenticated Core routes in a fresh isolated Mongo/queue process."""
import json
from pathlib import Path
import subprocess
import sys


def test_authenticated_core_lexical_lifecycle_isolated():
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run([sys.executable,str(root/'scripts/run_isolated_core_lexical.py')],
                          cwd=root,text=True,capture_output=True,timeout=120)
    assert result.returncode==0,result.stderr
    report=json.loads(result.stdout)
    assert report['database']=='isolated'
    assert report['authenticated_core_routes']
    assert all(report[key]=='PASS' for key in (
        'create','inventory_only','title','author','description_only','delete','cleanup'))
    assert report['source_checkpoint']==5
