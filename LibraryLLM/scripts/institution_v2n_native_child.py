"""Accepted actual native workflows, now under a named-resource application principal.

Only harness credential assertion, fixture size and privileged resource metrics
change. No worker/store/model method is replaced.
"""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
wrapper = (ROOT / 'scripts/institution_v2l_native_child.py').read_text(encoding='utf8').replace('V2L', 'V2N').replace('v2l', 'v2n')
marker = "assert 'NativeAdapter' not in source and 'store.claim=' not in source"
assert marker in wrapper
extra = '''
source=source.replace("assert os.environ.get('MONGO_URI','').startswith('mongodb://fixture_admin:')", "assert os.environ.get('MONGO_URI','').startswith('mongodb://fixture_application:') or (os.environ.get('LUMINAR_V2N_ANONYMOUS_COMPARISON')=='1' and os.environ.get('MONGO_URI','').startswith('mongodb://127.0.0.1:') and ':27017/' not in os.environ['MONGO_URI'])")
source=source.replace("mongo.admin.command('serverStatus')['connections']['current']", 'None')
source=source.replace("lib=seed(101 if target=='KNOWLEDGE_GRAPH' else 10)", 'lib=seed(151)')
'''
wrapper = wrapper.replace(marker, extra + '\n' + marker)
exec(compile(wrapper, str(ROOT / 'scripts/institution_v2l_native_child.py'), 'exec'), {'__file__': __file__, '__name__': '__main__'})
