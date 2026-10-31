"""Read-only deployment evidence; never serialize existing URI/password/command-line values."""
import json,os,subprocess,sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def mongo_audit():
    from dotenv import dotenv_values
    from pymongo import MongoClient
    from pymongo.uri_parser import parse_uri
    from pymongo.errors import OperationFailure
    env={**dotenv_values(ROOT/'.env'),**os.environ};uri=env.get('MONGO_URI','mongodb://127.0.0.1:27017');database=env.get('MONGO_DB_NAME','luminar_library')
    result={'database':database,'production_mutations_attempted':False,'probe':'Anonymous tenant _id read plus sanitized server configuration; all denial/write experiments occur only in disposable fixtures.'}
    parsed=parse_uri(uri);assert len(parsed['nodelist'])==1 and parsed['nodelist'][0][0] in ['localhost','127.0.0.1','::1'] and database=='luminar_library'
    host,port=parsed['nodelist'][0];result['configured_native_uri_has_credentials']=bool(parsed['username'] and parsed['password'])
    configured=MongoClient(uri,serverSelectionTimeoutMS=2000,socketTimeoutMS=2000,retryReads=False)
    anonymous=MongoClient(host=host,port=port,serverSelectionTimeoutMS=2000,socketTimeoutMS=2000,retryReads=False)
    try:
        result['server_version']=configured.admin.command('buildInfo').get('version')
        server=configured.admin.command('serverStatus')
        result['server_reported_pid']=server.get('pid');result['server_reported_process']=server.get('process')
        info=configured[database].command('connectionStatus',showPrivileges=False).get('authInfo',{})
        result['configured_connection_authenticated_user_count']=len(info.get('authenticatedUsers',[]))
        try:
            options=configured.admin.command('getCmdLineOpts').get('parsed',{})
            result['security_authorization_option']=options.get('security',{}).get('authorization','NOT_SET_DEFAULT')
            result['network']={k:options.get('net',{}).get(k) for k in ['bindIp','port']}
        except OperationFailure as e:result['server_options_read_denied_code']=e.code
        try:
            anonymous[database].institution_intelligence_targets.find_one({}, {'_id':1},max_time_ms=500)
            result['anonymous_tenant_read_allowed']=True
        except OperationFailure as e:
            result['anonymous_tenant_read_allowed']=False;result['anonymous_read_denied_code']=e.code
        result['authorization_qualified']=bool(result.get('security_authorization_option')=='enabled' and result.get('configured_connection_authenticated_user_count') and result.get('anonymous_tenant_read_allowed') is False)
    except Exception as e:result['audit_unavailable']=type(e).__name__;result['authorization_qualified']=False
    finally:configured.close();anonymous.close()
    dotenv=dotenv_values(ROOT/'.env')
    result['telemetry_configuration']={
        'process_explicit_enabled':os.environ.get('LUMINAR_WORKER_TELEMETRY_ENABLED')=='1',
        'dotenv_explicit_enabled':dotenv.get('LUMINAR_WORKER_TELEMETRY_ENABLED')=='1',
        'process_writer_uri_present':bool(os.environ.get('LUMINAR_WORKER_TELEMETRY_MONGO_URI')),
        'dotenv_writer_uri_present':bool(dotenv.get('LUMINAR_WORKER_TELEMETRY_MONGO_URI')),
        'process_operator_uri_present':bool(os.environ.get('LUMINAR_OPERATOR_MONGO_URI')),
        'dotenv_operator_uri_present':bool(dotenv.get('LUMINAR_OPERATOR_MONGO_URI'))}
    return result


def main():
    p=subprocess.run([shutil.which('pwsh.exe') or 'powershell.exe','-NoProfile','-NonInteractive','-File',str(ROOT/'scripts/institution_v2m_host_audit.ps1')],capture_output=True,text=True,timeout=45)
    assert p.returncode==0,'Read-only host audit failed; raw exception output intentionally not persisted.'
    result={'host':json.loads(p.stdout),'mongo':mongo_audit(),'scope':'No credentials, raw command lines, process kill/restart, production authorization or ACL mutation.'}
    if not result['host']['listeners']:
        result['host']['process_inventory_status']='NOT_VERIFIED: bounded Windows listener provider returned no records despite successful Mongo connection. Do not infer absence or supervisor identity.'
    (ROOT/'reports/institution_v2m_host_audit.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({'listeners':len(result['host']['listeners']),'authorization_qualified':result['mongo']['authorization_qualified'],
        'anonymous_read_allowed':result['mongo'].get('anonymous_tenant_read_allowed'),'telemetry_enabled':result['mongo']['telemetry_configuration']['process_explicit_enabled'] or result['mongo']['telemetry_configuration']['dotenv_explicit_enabled']}))


if __name__=='__main__':main()
