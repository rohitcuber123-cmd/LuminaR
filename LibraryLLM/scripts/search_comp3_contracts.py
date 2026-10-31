"""Exact native schema/choice read contracts with in-memory dependencies."""
import ast,json,math,sys
from pathlib import Path
from copy import deepcopy
from typing import Literal
from uuid import UUID,uuid4
from datetime import datetime,timedelta,timezone
from pydantic import BaseModel,Field,ConfigDict,ValidationError
from fastapi import HTTPException
from scripts.search_v2c_c5er_offline_native import compile_functions
from scratch.search_compositional_recovery_v3 import parser

def forbid(event,args):
    if event in ['socket.connect','socket.bind','socket.getaddrinfo']:raise RuntimeError('No network permitted')
    if event=='import' and str(args[0]).split('.')[0] in ['pymongo','backend']:raise RuntimeError('No application/database initialization')
sys.addaudithook(forbid)

def main():
    schema_env=dict(BaseModel=BaseModel,Field=Field,ConfigDict=ConfigDict,Literal=Literal,UUID=UUID,Mode=Literal['SMART','GENRE_SUBJECT','TITLE_AUTHOR','EXACT'])
    source=Path('search/interaction_api.py');tree=ast.parse(source.read_text(encoding='utf8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ChoiceRequest')
    exec(compile(ast.Module(body=[cls],type_ignores=[]),str(source),'exec'),schema_env)
    Request=schema_env['ChoiceRequest'];checks=[]
    for length in [149,150,151,500]:
        try:Request(clarification_id=uuid4(),choice_id=uuid4(),query='x'*length);accepted=True
        except ValidationError:accepted=False
        assert accepted==(length<=150)
        checks.append({'test':'actual_native_ChoiceRequest','raw_query_length':length,'accepted':accepted})
    env={k:getattr(parser,k) for k in ['parse_query','validate','decide','executable','normalize','FacetVocabulary']}
    env.update(deepcopy=deepcopy,HTTPException=HTTPException)
    transform=compile_functions('search/query_interaction.py',['transformer'],env)['transformer']
    for q in ['include category Fictoin','include category Fictoin; by "'+('Arden Vale '*17).strip()+'"']:
        p=parser.parse_query(q,['Fiction']);assert p.decision['decision_type']=='EXECUTABLE_WITH_NOTICE'
        for operation in ['correction_apply','correction_keep']:
            resolved=transform({'query':q,'mode':'SMART','filters':{},'omit':[]},
                {'operation':operation,'correction':p.corrections[0]},None)(p,['Fiction'],{})
            assert parser.executable(resolved) and not resolved.corrections
            assert resolved.author_text==p.author_text
            json.dumps(resolved.public(),default=str)
            checks.append({'test':'actual_native_transformer_only','operation':operation,'query_length':len(q),'preserves_author':True,
                'reachable_via_existing_request_schema':len(q)<=150})
    for q in ['by [value]','online only; '+('Topic: coastal navigation; '*5)+'by [value]']:
        p=parser.parse_query(q,[])
        try:transform({'query':q,'mode':'SMART','filters':{},'omit':[]},{'operation':'complete','field':'author'},'Elm Vale')(p,[],{})
        except HTTPException as e:assert e.status_code==422
        else:raise AssertionError('Append-only transformer skipped a structural slot')
        checks.append({'test':'actual_native_placeholder_completion_rejects_safely','query_length':len(q),'status':422})
    own=compile_functions('search/session_store.py',['identity','token'],{'UUID':UUID,'HTTPException':HTTPException})
    actor={'sub':'fixture-owner','sid':'login-one'};cid=str(uuid4());choiceid=str(uuid4());sid=str(uuid4())
    class ReadRepository:
        def __init__(self,row):self.row=row;self.reads=0
        def find_one(self,q):
            self.reads+=1
            return deepcopy(self.row) if all(self.row.get(k)==v for k,v in q.items()) else None
    scopes=[('GLOBAL',None,False),('PUBLIC_TENANT_PATRON','public',False),('PUBLIC_TENANT_STAFF','public',True),
        ('PRIVATE_TENANT_PATRON','private',False),('PRIVATE_TENANT_STAFF','private',True)]
    for scope,lid,staff in scopes:
        row={'_id':'clarification:'+cid,**own['identity'](actor,lid,staff),'expires_at':datetime.now(timezone.utc)+timedelta(minutes=1),
            'used':False,'parser_version':parser.PARSER_VERSION,'mode':'SMART','query':'include Fiction','search_session_id':sid,
            'choices':[{'choice_id':choiceid,'operation':'literal'}]}
        repository=ReadRepository(row)
        load=compile_functions('search/query_interaction.py',['load_choice'],dict(own,collection=lambda:repository,
            HTTPException=HTTPException,datetime=datetime,timezone=timezone,PARSER_VERSION=parser.PARSER_VERSION,math=math))['load_choice']
        for variant,expected in [('current',200),('foreign_owner',404),('foreign_login',404),('changed_query',409),('changed_session',409),
            ('expired',410),('used',409),('stale_parser',409)]:
            repository.row=deepcopy(row);a=deepcopy(actor);q=row['query'];session=sid
            if variant=='foreign_owner':a['sub']='other'
            if variant=='foreign_login':a['sid']='other'
            if variant=='changed_query':q='include Physics'
            if variant=='changed_session':session=str(uuid4())
            if variant=='expired':repository.row['expires_at']=datetime.now(timezone.utc)-timedelta(seconds=1)
            if variant=='used':repository.row['used']=True
            if variant=='stale_parser':repository.row['parser_version']='stale'
            try:load(a,cid,choiceid,mode='SMART',query=q,session_id=session,library_id=lid,staff=staff);status=200
            except HTTPException as e:status=e.status_code
            assert status==expected,(scope,variant,status)
            checks.append({'test':'actual_load_choice_read_contract','scope':scope,'variant':variant,'status':status})
    populations={}
    for name,path in [('C5E90','search_v2c_c5e_reviewed_population_v3.jsonl'),('C5ER150','search_v2c_c5er_reviewed_population.jsonl'),('SmartEng150','search_v2c_smarteng_reviewed_population.jsonl')]:
        rows=[json.loads(s) for s in (Path('reports')/path).read_text(encoding='utf8').splitlines()]
        populations[name]={'over150':sum(len(g['query_text'])>150 for g in rows),'denominator':len(rows),
            'case_ids':[g['case_id'] for g in rows if len(g['query_text'])>150]}
    report={'status':'PASS_READ_ONLY_COMPONENT_CONTRACTS','checks':checks,'count':len(checks),'raw_query_length_populations':populations,
        'limit_applies_to':'ChoiceRequest.query raw echoed query, not a stored option or identifier; parser/session resolve max500.',
        'reference_support':'clarification_id and choice_id reference stored state, but load_choice also requires exact raw query equality; no supported reference-only substitute.',
        'long_query_status':'No truncation or production schema change. >150 raw query cannot resolve through current API. Offline transform success is not API qualification.',
        'placeholder_completion':'Append-only completion cannot fill typed structural slots; native transformer rejects422; requires explicit integration proposal.',
        'authorization_limits':'identity binding and expiry/version read checks only; authority dependencies mocked. Real current membership/JWT/CAS/one-use durability not tested.',
        'Mongo_calls':0,'Mongo_writes':0,'production_changes':0,'real_HTTP_requests':0}
    with Path('reports/search_comp3_native_contracts.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({'checks':len(checks),'Mongo_calls':0}))
if __name__=='__main__':main()
