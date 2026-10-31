"""Execute installed current-tree guard assertions on owned mutation fixtures."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]


def main():
    kind,fixture=sys.argv[1:]
    path,name={'j':('tests/institution_v2j/test_diagnostics.py','test_existing_staff_status_unchanged'),
               'rag':('tests/test_assistant_backend.py','test_protected_rag_files_match_original_hashes')}[kind]
    tree=ast.parse((ROOT/path).read_text())
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    namespace={'ROOT':Path(fixture),'hashlib':hashlib,'json':json,'Path':Path}
    sys.path.insert(0,str(ROOT))
    exec(compile(ast.Module(body=[function],type_ignores=[]),str(ROOT/path),'exec'),namespace)
    try:namespace[name]()
    except (AssertionError,subprocess.CalledProcessError) as error:
        print(json.dumps({'accepted':False,'reason':str(error),'guard_source':'installed_actual_tree'}));return 2
    print(json.dumps({'accepted':True,'guard_source':'installed_actual_tree'}));return 0


if __name__=='__main__':raise SystemExit(main())
