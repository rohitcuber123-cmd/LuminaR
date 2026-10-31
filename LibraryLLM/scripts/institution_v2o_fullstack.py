"""Parent owns all server/data/artifacts and emits no fixture credentials."""
import json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.institution_v2o_fixture import AuthMongo,provision,seed_database,provision_application


def main():
    with AuthMongo() as server:
        seed_database(server);provision(server);provision_application(server)
        env={**os.environ,'MONGO_URI':server.app_uri,'MONGO_DB_NAME':server.database,'LUMINAR_MONGO_MODE':'AUTHENTICATED',
             'LIBRARY_INTELLIGENCE_ROOT':str(server.artifact_root),'LIBRARY_ASSET_ROOT':str(server.root/'assets'),
             'LUMINAR_SESSION_DB':str(server.root/'sessions.sqlite'),'LUMINAR_SEARCH_INDEX_DIR':str(server.root/'empty-global-index'),
             'LUMINAR_LEXICAL_DIR':str(server.root/'lexical'),'SEARCH_GLOBAL_READ_ONLY':'1','LUMINAR_LEXICAL_SYNC_ENABLED':'false',
             'LUMINAR_WORKER_TELEMETRY_ENABLED':'0','NOTIFICATION_DUE_WORKER_ENABLED':'0','NOTIFICATION_OUTBOX_WORKER_ENABLED':'0',
             'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','JWT_SECRET_KEY':'o-owned-stack-key','OMP_NUM_THREADS':'2',
             'LUMINAR_V2O_TRACE_OUTPUT':str(ROOT/'reports/institution_v2o_fullstack_commands.json')}
        output=ROOT/'reports/institution_v2o_fullstack.json'
        with output.with_suffix('.log').open('w',encoding='utf8') as log:
            p=subprocess.run([sys.executable,str(ROOT/'scripts/institution_v2o_fullstack_child.py'),str(output)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300)
        assert p.returncode==0,'Owned full-stack rehearsal failed; inspect O log'
        env.update(LUMINAR_MOCK_LLM='0',LUMINAR_V2O_TRACE_OUTPUT=str(ROOT/'reports/institution_v2o_rag_commands.json'))
        with (ROOT/'reports/institution_v2o_rag_entrypoint.log').open('w',encoding='utf8') as log:
            p=subprocess.run([sys.executable,str(ROOT/'scripts/institution_v2o_rag_child.py'),str(output)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240)
        assert p.returncode==0,'Owned RAG probe process failed unexpectedly'
        from scripts.institution_v2o_backup import validate
        validate(server,json.loads(output.read_text()))
    result=json.loads(output.read_text());result['owned_fixture_removed']=True;output.write_text(json.dumps(result,indent=2))
    print('Actual authenticated Core/Search/Recommendation + document adapter rehearsal PASS; full production stack remains partial.')


if __name__=='__main__':main()
