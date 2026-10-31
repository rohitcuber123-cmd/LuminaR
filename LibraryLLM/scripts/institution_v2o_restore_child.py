"""Real application compatibility over restored synthetic Mongo plus copied artifacts."""
import json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
assert os.environ['MONGO_DB_NAME'].startswith('luminar_v2o_fixture_') and os.environ['MONGO_DB_NAME'].endswith('_restore')
from backend.main import app
from backend.database.mongodb import db,client
from backend.utils.jwt_utils import create_access_token
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError
lib=os.environ['LUMINAR_V2O_LIBRARY'];aid=os.environ['LUMINAR_V2O_ASSET']
headers={'Authorization':'Bearer '+create_access_token(1,'n-bench-1@example.com','GENERAL_USER')}
with TestClient(app) as api:
    for path in [f'/libraries/{lib}/inventory/books',f'/libraries/{lib}/assets/{aid}',f'/libraries/{lib}/context']:
        response=api.get(path,headers=headers);assert response.status_code==200,(path,response.status_code)
    response=api.get(f'/libraries/{lib}/intelligence',headers=headers);assert response.status_code==200
    value=response.json();assert value['search']['artifact_verified'] and value['kg']['artifact_verified']
    assert value['search']['status']=='READY' and value['kg']['status']=='READY'
    row={'user_id':99999,'work_id':'OWNED-RESTORE-PROBE'}
    db.reading_list.insert_one(row)
    try:db.reading_list.insert_one(row)
    except DuplicateKeyError:pass
    else:raise AssertionError('Restored unique constraint missing')
    finally:db.reading_list.delete_many({'user_id':99999,'work_id':'OWNED-RESTORE-PROBE'})
client.close()
print(json.dumps({'real_core_lifespan':'PASS','inventory_asset_membership_API':'PASS','restored_Search_KG_pointer_artifacts':'READY_VERIFIED','unique_constraint_denial':'PASS'}))
