"""Capture the previously hidden exception without changing production handlers."""
import json
import sys
import threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import pytest
errors=[]
def trace(frame,event,arg):
    if not frame.f_code.co_filename.replace('\\','/').endswith('/search/api.py'): return None
    if event=='exception' and frame.f_code.co_name=='search':
        kind,value,tb=arg
        errors.append({'type':kind.__name__,'message':str(value),'line':frame.f_lineno})
    return trace
sys.settrace(trace)
threading.settrace(trace)
result=pytest.main(['tests/test_lexical_api_fallback.py','-q'])
sys.settrace(None)
threading.settrace(None)
(ROOT/'reports/institution_v2o_lexical_exception.json').write_text(json.dumps(errors,indent=2))
print(json.dumps(errors))
raise SystemExit(result)
