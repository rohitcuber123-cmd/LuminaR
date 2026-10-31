"""Accepted native L worker harness,151-book disposable tenant shape and full retained-pointer checks."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
wrapper=(ROOT/'scripts/institution_v2l_native_child.py').read_text(encoding='utf8').replace('V2L','V2M').replace('v2l','v2m')
marker="assert 'NativeAdapter' not in source and 'store.claim=' not in source"
assert marker in wrapper
extra="""
source=source.replace("lib=seed(101 if target=='KNOWLEDGE_GRAPH' else 10)","lib=seed(int(os.environ.get('LUMINAR_V2M_BOOK_COUNT','151')))")
source=source.replace("result['worker_thread_ended']=not worker.thread.is_alive();save();mongo.close()",\
    "result['worker_thread_ended']=not worker.thread.is_alive()\\n"\
    "    checked=[]\\n"\
    "    for pointer in repo.collection('intelligence_targets').find({'active_generation_id':{'$ne':None}}).limit(100):\\n"\
    "        artifacts.validate(pointer['library_id'],pointer['target'],pointer['active_generation_id'])\\n"\
    "        checked.append({'library_id':pointer['library_id'],'target':pointer['target'],'generation_id':pointer['active_generation_id']})\\n"\
    "    result['retained_targets_validated']=checked;save();mongo.close()")
"""
wrapper=wrapper.replace(marker,extra+'\n'+marker)
exec(compile(wrapper,str(ROOT/'scripts/institution_v2l_native_child.py'),'exec'),{'__file__':str(Path(__file__).resolve()),'__name__':'__main__'})
