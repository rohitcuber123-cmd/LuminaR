"""Auth-enforced disposable telemetry laboratory, never production provisioning."""
from pathlib import Path
import secrets
from urllib.parse import quote
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2j_fixture.py').read_text(encoding='utf8')
source=source.replace('luminar-v2j-auth-','luminar-v2k-auth-').replace("'luminar_v2j_test_'","'luminar_v2k_fixture_'")
source=source.replace("'--quiet']","'--quiet','--setParameter','enableTestCommands=1']")
source=source.replace('        self.temp.cleanup()',
    "        expected_root=Path(self.temp.name).resolve()\n"
    "        assert self.root.resolve()==expected_root and expected_root.parent==Path(tempfile.gettempdir()).resolve() and expected_root.name.startswith('luminar-v2k-auth-')\n"
    "        self.temp.cleanup()")
exec(compile(source,str(ROOT/'scripts/institution_v2j_fixture.py'),'exec'))
from scratch.institution_v2k_telemetry.telemetry import COLLECTION,SLOT,MAX_BYTES


def provision(server):
    assert server.database.startswith('luminar_v2k_fixture_')
    validator={'$and':[{'$jsonSchema':{'bsonType':'object','required':['_id','schema','epoch','current','previous'],
        'properties':{'_id':{'enum':[SLOT]},'schema':{'enum':[1]},'epoch':{'bsonType':['int','long'],'minimum':0},
                      'current':{'bsonType':['object','null'],'properties':{'progress':{'bsonType':'array','maxItems':8}}},
                      'previous':{'bsonType':['object','null'],'properties':{'progress':{'bsonType':'array','maxItems':8}}}}}},
        {'$expr':{'$lte':[{'$bsonSize':'$$ROOT'},MAX_BYTES]}}]}
    server.db.create_collection(COLLECTION,validator=validator,validationLevel='strict',validationAction='error')
    server.db[COLLECTION].insert_one({'_id':SLOT,'schema':1,'epoch':0,'current':None,'previous':None})
    server.db.command('createRole','fixture_telemetry_writer',privileges=[
        {'resource':{'db':server.database,'collection':COLLECTION},'actions':['find','update']},
        {'resource':{'db':server.database,'collection':'institution_intelligence_jobs'},'actions':['find']},
        {'resource':{'db':server.database,'collection':'institution_intelligence_targets'},'actions':['find']}],roles=[])
    password=secrets.token_urlsafe(32)
    server.db.command('createUser','fixture_telemetry',pwd=password,roles=[{'role':'fixture_telemetry_writer','db':server.database}])
    server.telemetry_password=password
    server.telemetry_uri=f'mongodb://fixture_telemetry:{quote(password)}@127.0.0.1:{server.port}/{server.database}?authSource={server.database}'
