"""Discover actual scoped commands, grant only those actions, then subtract groups."""
import json,os,secrets,subprocess,sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.institution_v2o_fixture import AuthMongo,provision_application


def actions(row):
    cmd=row['command']
    if cmd in {'find','count','distinct','aggregate'}:return ['collStats'] if row.get('collStats') else ['find']
    if cmd=='findAndModify':return ['find','remove' if row.get('remove') else 'update']+(['insert'] if row.get('upsert') else [])
    if cmd=='update':return ['update']+(['insert'] if row.get('upsert') else [])
    return {'insert':['insert'],'delete':['remove'],'createIndexes':['createIndex'],'listIndexes':['listIndexes'],
            'listCollections':['listCollections'],'collStats':['collStats']}.get(cmd,[])


def main():
    report={'scope':'Exact command-derived roles for the explicitly tested service methods only; not full deployment minimums.', 'services':[]}
    with AuthMongo() as server:
        provision_application(server)
        lib=str(uuid4());aid=str(uuid4())
        def seed():
            # Administrative fixture reset is separate from the measured principal.
            for name in server.db.list_collection_names():
                if not name.startswith('system.'):server.db[name].delete_many({})
            server.db.users.insert_one({'user_id':1,'email':'o@example.com','name':'Owned fixture','role':'GENERAL_USER','is_active':True,'is_email_verified':True})
            server.db.books.insert_one({'work_id':'OL1W','title':'Networks','subjects':['Networks']})
            server.db.institution_libraries.insert_one({'library_id':lib,'name':'Owned private','status':'ACTIVE','library_type':'PRIVATE_INSTITUTION','access_mode':'PRIVATE_CODE'})
            server.db.institution_memberships.insert_one({'membership_id':str(uuid4()),'library_id':lib,'user_id':1,'role':'ADMIN','status':'ACTIVE'})
            server.db.institution_library_assets.insert_one({'library_id':lib,'asset_id':aid,'status':'READY','visibility':'MEMBERS'})
            server.db.institution_library_books.insert_many([{'library_id':lib,'library_book_id':str(uuid4()),'title':f'Networks {n}','subjects':['Networks'],'authors':['Fixture'],'status':'ACTIVE','accession_sequence':n} for n in range(3)])
        def run(case,label,uri):
            trace=ROOT/f'reports/institution_v2o_role_{case}_{label}_commands.json'
            env={**os.environ,'MONGO_URI':uri,'MONGO_DB_NAME':server.database,'LUMINAR_MONGO_MODE':'AUTHENTICATED',
                 'LIBRARY_INTELLIGENCE_ROOT':str(server.artifact_root),'LUMINAR_SESSION_DB':str(server.root/'sessions.sqlite'),
                 'LUMINAR_WORKER_TELEMETRY_ENABLED':'0','LUMINAR_V2O_LIBRARY':lib,'LUMINAR_V2O_ASSET':aid,
                 'LUMINAR_V2O_TRACE_OUTPUT':str(trace),'JWT_SECRET_KEY':'o-owned-role-key'}
            p=subprocess.run([sys.executable,str(ROOT/'scripts/institution_v2o_permission_child.py'),case],cwd=ROOT,env=env,capture_output=True,text=True,timeout=90)
            assert server.app_password not in p.stdout+p.stderr
            (ROOT/f'reports/institution_v2o_role_{case}_{label}.log').write_text(p.stdout+p.stderr)
            return p.returncode,json.loads(trace.read_text())
        for case in ['core','recommendation','rag_metadata','native']:
            seed();code,trace=run(case,'discovery',server.app_uri)
            assert code==0, 'Scoped service discovery failed; inspect safe O role log.'
            seed();code,warm=run(case,'discovery_warm',server.app_uri)
            assert code==0,'Warm initialization discovery failed'
            trace['commands']+=warm['commands']
            privileges=defaultdict(set);evidence=[]
            for row in trace['commands']:
                if row['database']!=server.database or row['collection']=='__luminar_auth_gate__':continue
                required=actions(row)
                for joined in row.get('lookup_collections',[]):
                    privileges[joined].add('find')
                    evidence.append({**row,'joined_collection':joined,'required_actions':['find'],'classification':'REQUIRED_LOOKUP_SOURCE'})
                if required:
                    resource='' if row['command']=='listCollections' else row['collection']
                    privileges[resource].update(required)
                    evidence.append({**row,'required_actions':required,'classification':'INITIALIZATION_ONLY' if row['command'] in {'createIndexes','listIndexes','listCollections'} else 'REQUIRED_FOR_TESTED_OPERATION'})
            role='o_'+case;password=secrets.token_urlsafe(32)
            def specs(without=None):return [{'resource':{'db':server.database,'collection':name},'actions':sorted(value-{without})} for name,value in privileges.items() if value-{without}]
            server.db.command('createRole',role,privileges=specs(),roles=[])
            server.db.command('createUser',role,pwd=password,roles=[{'role':role,'db':server.database}])
            uri=f'mongodb://{role}:{quote(password)}@127.0.0.1:{server.port}/{server.database}?authSource={server.database}'
            seed();code,_=run(case,'positive',uri);assert code==0,'Command-derived role failed positive replay'
            removals=[]
            for action in sorted(set.union(*privileges.values())):
                server.db.command('updateRole',role,privileges=specs(action),roles=[])
                seed();code,_=run(case,'without_'+action,uri)
                removals.append({'removed_action_group':action,'exit':code,'denied':code==13})
                assert code==13,'Unproven action group: successful replay without it; review before retaining grant'
            server.db.command('updateRole',role,privileges=specs(),roles=[])
            server.db.command('dropUser',role)
            seed();code,_=run(case,'revoked',uri);assert code==13
            report['services'].append({'service':case,'positive':'PASS','privileges':specs(),'runtime_source_evidence':evidence,'group_subtraction':removals,'revoked_fresh_login_denied':True})
            (ROOT/'reports/institution_v2o_least_privilege_tests.json').write_text(json.dumps(report,indent=2))
            print(case,'command-derived role and all action-group removals PASS',flush=True)
    report['owned_fixture_removed']=True
    (ROOT/'reports/institution_v2o_least_privilege_tests.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':main()
