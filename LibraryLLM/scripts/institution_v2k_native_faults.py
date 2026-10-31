"""Native correctness during actual auxiliary timeout/permission failure."""
import json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.institution_v2k_fixture import AuthMongo,provision,seed_database


def main():
    result={'cases':[],'qualification':'Actual authenticated mongod auxiliary faults during native MiniLM/FAISS Search, then native KG; no mandatory job DB outage.'}
    out=ROOT/'reports/institution_v2k_native_faults.json'
    for mode in ['permission','timeout']:
        with AuthMongo() as s:
            seed_database(s);provision(s)
            env={**os.environ,'LUMINAR_V2K_ISOLATED_CHILD':'1','MONGO_URI':s.writer_uri,'MONGO_DB_NAME':s.database,
                 'LIBRARY_INTELLIGENCE_ROOT':str(s.artifact_root),'V2K_TELEMETRY_URI':s.telemetry_uri,'V2K_READER_URI':s.reader_uri}
            path=ROOT/f'reports/institution_v2k_native_fault_{mode}.json';at=time.perf_counter()
            with path.with_suffix('.log').open('w',encoding='utf8') as f:
                p=subprocess.run([sys.executable,str(ROOT/'scripts/institution_v2k_native_child.py'),'--scenario','benchmark','--enabled',
                    '--telemetry-fault',mode,'--output',str(path)],env=env,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=180)
            case={'fault':mode,'exit':p.returncode,'seconds':time.perf_counter()-at,'evidence':path.name}
            result['cases'].append(case);out.write_text(json.dumps(result,indent=2),encoding='utf8')
            assert p.returncode==0,case
            value=json.loads(path.read_text(encoding='utf8'))
            case['agent_errors']=value.get('agent_errors');case['telemetry_metrics']=value.get('telemetry_metrics')
            case['native_outcomes']=[{'target':b['target'],'state':b['state'],'pointer_ack_match':b['pointer_ack_match']} for b in value['builds']]
            assert all(b['state']=='SUCCEEDED' and b['pointer_ack_match'] for b in value['builds'])
            assert sum(value.get('agent_errors',{}).values())>0
            out.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({'actual_auxiliary_faults':len(result['cases']),'native_builds_succeeded':4}))


if __name__=='__main__':main()
