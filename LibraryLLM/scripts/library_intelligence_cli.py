"""Explicit UUID + runtime bearer token; never opens global builder defaults."""
import argparse,json,os,time
from uuid import UUID
import requests
def run(target=None,recovery=False):
    parser=argparse.ArgumentParser()
    parser.add_argument('--library-id',required=True,type=UUID)
    parser.add_argument('--token-env',default='LUMINAR_BUILD_TOKEN')
    parser.add_argument('--core-url',default='http://127.0.0.1:8002')
    parser.add_argument('--wait',action='store_true')
    if recovery:parser.add_argument('--job-id',required=True,type=UUID)
    args=parser.parse_args();token=os.environ.get(args.token_env)
    if not token:parser.error('A runtime bearer-token environment variable is required.')
    url=args.core_url.rstrip('/')+'/libraries/'+str(args.library_id)+'/intelligence';headers={'Authorization':'Bearer '+token}
    if recovery:response=requests.post(url+'/jobs/'+str(args.job_id)+'/recover',headers=headers,timeout=60)
    elif target:response=requests.post(url+'/builds',headers=headers,json={'target':target},timeout=30)
    else:response=requests.get(url+'/reconciliation',headers=headers,timeout=60)
    if not response.ok:raise SystemExit('Library intelligence request failed with HTTP '+str(response.status_code))
    result=response.json();print(json.dumps(result,default=str,indent=2))
    if target and args.wait:
        deadline=time.monotonic()+3600
        while time.monotonic()<deadline:
            response=requests.get(url+'/jobs/'+result['job_id'],headers=headers,timeout=30)
            if not response.ok:raise SystemExit('Build status is no longer authorized or available.')
            result=response.json()
            if result['state'] in ['SUCCEEDED','FAILED','CANCELLED','RECOVERY_REQUIRED']:
                print(json.dumps(result,default=str,indent=2));return result['state']=='SUCCEEDED'
            time.sleep(2)
        raise SystemExit('Build is still durable; status wait timed out.')
    return True
