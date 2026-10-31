"""Actual-model native build survives an authenticated observer thread failure."""
import json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.institution_v2l_fixture import AuthMongo,provision,seed_database


def main():
    with AuthMongo() as s:
        seed_database(s);provision(s)
        env={**os.environ,'LUMINAR_V2L_ISOLATED_CHILD':'1','LUMINAR_V2L_OBSERVER_CRASH':'1',
            'MONGO_URI':s.writer_uri,'MONGO_DB_NAME':s.database,'LIBRARY_INTELLIGENCE_ROOT':str(s.artifact_root),
            'V2L_TELEMETRY_URI':s.telemetry_uri,'V2L_READER_URI':s.reader_uri}
        path=ROOT/'reports/institution_v2l_native_observer_crash.json'
        with path.with_suffix('.log').open('w',encoding='utf8') as f:
            p=subprocess.run([sys.executable,str(ROOT/'scripts/institution_v2l_native_child.py'),'--scenario','benchmark','--enabled','--output',str(path)],env=env,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=180)
        assert p.returncode==0,'Owned observer-crash child failed; inspect2L log'
        d=json.loads(path.read_text(encoding='utf8'))
        assert d['agent_errors'].get('OBSERVER_LOOP_UNAVAILABLE')==1 and d['observer_thread_ended']
        assert all(b['state']=='SUCCEEDED' and b['pointer_ack_match'] for b in d['builds'])
    print(json.dumps({'observer_thread_failure':'ISOLATED','native_search_and_kg':'SUCCEEDED'}))


if __name__=='__main__':main()
