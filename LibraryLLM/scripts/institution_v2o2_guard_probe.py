"""Execute every assertion of the real proposed frozen test in an owned fixture.

Only the chosen test function is compiled, avoiding unrelated test fixtures and
module imports. Assertion bodies, helper hashes, imports and payloads are intact.
"""
import ast
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
CAND=ROOT/'.scratch/institution-v2o2/candidate/LibraryLLM'


def main():
    kind,fixture=sys.argv[1:]
    path,name={'j':('tests/institution_v2j/test_diagnostics.py','test_existing_staff_status_unchanged'),
               'rag':('tests/test_assistant_backend.py','test_protected_rag_files_match_original_hashes')}[kind]
    tree=ast.parse((CAND/path).read_text())
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    compiled=compile(ast.Module(body=[function],type_ignores=[]),str(CAND/path),'exec')
    sys.path.insert(0,str(CAND))
    namespace={'ROOT':Path(fixture),'hashlib':hashlib,'json':json,'Path':Path}
    exec(compiled,namespace)
    try:namespace[name]()
    except (AssertionError,subprocess.CalledProcessError) as error:
        print(json.dumps({'accepted':False,'reason':str(error)}));return 2
    print(json.dumps({'accepted':True}));return 0


if __name__=='__main__':
    import subprocess
    raise SystemExit(main())
