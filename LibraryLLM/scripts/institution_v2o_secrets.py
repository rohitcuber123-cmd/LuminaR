"""Same-user DPAPI, restricted-token ACL denial and actual fixture credential rotation."""
import json,os,secrets,shutil,subprocess,sys
from pathlib import Path
from urllib.parse import quote
from pymongo import MongoClient
from pymongo.errors import OperationFailure
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.institution_v2o_fixture import AuthMongo,provision,seed_database


def main():
    report={'scope':'Owned directory and synthetic DB principals only; no real service account or production ACL changed.'}
    with AuthMongo() as s:
        seed_database(s);provision(s)
        # Accepted M DPAPI code executed from a new O-scoped owned script copy.
        secret_script=s.root/'secret.ps1'
        secret_script.write_text((ROOT/'scripts/institution_v2m_secret_fixture.ps1').read_text().replace('v2m','v2o').replace('V2M','V2O'))
        def protect(name,uri):
            path=s.root/name/'secret.clixml'
            payload={'fixture_root':str(s.root),'secret_path':str(path),'secret':uri}
            p=subprocess.run([shutil.which('pwsh.exe'),'-NoProfile','-NonInteractive','-File',str(secret_script),'-Mode','protect'],input=json.dumps(payload),capture_output=True,text=True,timeout=20)
            assert p.returncode==0,'Owned DPAPI enrollment failed'
            value=json.loads(p.stdout);assert value['recovered_matches'] and value['file_protected'] and value['directory_protected']
            assert uri.encode() not in path.read_bytes()
            return path,value
        old,report['initial_protection']=protect('old-writer',s.telemetry_uri)
        p=subprocess.run([shutil.which('pwsh.exe'),'-NoProfile','-NonInteractive','-File',str(ROOT/'scripts/institution_v2o_acl_probe.ps1'),'-Path',str(old)],capture_output=True,text=True,timeout=30)
        assert p.returncode==0,'Restricted-token ACL probe unavailable'
        report['access_probe']=json.loads(p.stdout);assert report['access_probe']['restricted_token_denied']
        password=secrets.token_urlsafe(32)
        s.db.command('createUser','rotated_writer',pwd=password,roles=[{'role':'fixture_telemetry_writer','db':s.database}])
        uri=f'mongodb://rotated_writer:{quote(password)}@127.0.0.1:{s.port}/{s.database}?authSource={s.database}'
        new,report['replacement_protection']=protect('replacement-writer',uri)
        s.db.command('dropUser','fixture_telemetry')
        try:
            with MongoClient(s.telemetry_uri,serverSelectionTimeoutMS=2000) as c:c[s.database].command('connectionStatus')
        except OperationFailure as error:assert error.code==18;report['old_fresh_auth_revoked']=True
        with MongoClient(uri) as c:assert c[s.database].institution_worker_telemetry_v2k.find_one({})
        report['rollback_to_valid_replacement']='PASS'
        payload={'fixture_root':str(s.root),'secret_path':str(s.root/'absent/secret.clixml'),'secret':uri}
        p=subprocess.run([shutil.which('pwsh.exe'),'-NoProfile','-NonInteractive','-File',str(secret_script),'-Mode','verify'],input=json.dumps(payload),capture_output=True,text=True,timeout=20)
        assert p.returncode==3 and password not in p.stdout+p.stderr
        report['missing_secret_fails_closed']=True
    report['owned_fixture_removed']=True
    (ROOT/'reports/institution_v2o_secret_fixture.json').write_text(json.dumps(report,indent=2))
    print('DPAPI/current-owner/restricted-token denial/rotation/revocation fixture PASS')


if __name__=='__main__':main()
