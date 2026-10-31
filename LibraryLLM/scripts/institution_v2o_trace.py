"""Disposable-process client/call instrumentation, no URI/command payload values."""
import atexit
from collections import Counter
import inspect
import json
import os
from pathlib import Path
import pymongo
from pymongo import monitoring
ROOT=Path(__file__).resolve().parents[1]
EVENTS=Counter(); CLIENTS=[]; HINTS={}


def caller():
    frames=[]
    for frame in inspect.stack(context=0):
        path=Path(frame.filename)
        try: name=path.resolve().relative_to(ROOT).as_posix()
        except ValueError: continue
        if name.startswith(('.venv/','scripts/institution_v2o_trace.py')): continue
        frames.append(f'{name}:{frame.lineno}:{frame.function}')
    return frames[:8]


class Trace(monitoring.CommandListener):
    def started(self,event):
        if event.command_name in {'hello','isMaster','saslStart','saslContinue','authenticate'}: return
        resource=event.command.get(event.command_name)
        if not isinstance(resource,str):resource=event.command.get('collection','<database>')
        key=(event.database_name,resource,event.command_name,' | '.join(caller()))
        EVENTS[key]+=1
        def lookups(value):
            found=[]
            if isinstance(value,dict):
                for key,item in value.items():
                    if key in {'$lookup','$graphLookup'} and isinstance(item,dict) and isinstance(item.get('from'),str):found.append(item['from'])
                    found+=lookups(item)
            elif isinstance(value,list):
                for item in value:found+=lookups(item)
            return found
        HINTS[key]={'lookup_collections':sorted(set(lookups(event.command.get('pipeline',[])))),
                    'upsert': bool(event.command.get('upsert') or any(item.get('upsert') for item in event.command.get('updates',[]))),
                    'remove': bool(event.command.get('remove')), 'collStats': any('$collStats' in stage for stage in event.command.get('pipeline',[]))}
    def succeeded(self,event): pass
    def failed(self,event): EVENTS[('<failed>','<redacted>',event.command_name,'server denial/error')]+=1


monitoring.register(Trace())
Original=pymongo.MongoClient


class TracedClient(Original):
    def __init__(self,*args,**kwargs):
        self._o_trace_record={'source':caller(),'pid':os.getpid(),'closed':False,'option_names':sorted(kwargs)}
        CLIENTS.append(self._o_trace_record)
        super().__init__(*args,**kwargs)
    def close(self):
        self._o_trace_record['closed']=True
        return super().close()


pymongo.MongoClient=TracedClient


@atexit.register
def save():
    output=os.getenv('LUMINAR_V2O_TRACE_OUTPUT')
    if output:Path(output).write_text(json.dumps({'clients':CLIENTS,'commands':[{'database':db,'collection':coll,'command':cmd,'source_stack':stack,'count':n,**HINTS.get((db,coll,cmd,stack),{})} for (db,coll,cmd,stack),n in EVENTS.items()]},indent=2))
