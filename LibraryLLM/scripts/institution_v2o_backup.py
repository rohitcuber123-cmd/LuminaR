"""Coherent stopped-fixture dump/restore with real app and cross-store validation."""
import hashlib,json,os,secrets,shutil,subprocess,sys
from pathlib import Path
from urllib.parse import quote
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.institution_v2n_backup import snapshot


def validate(server,fullstack):
    assert server.database.startswith('luminar_v2o_fixture_') and fullstack['completed']
    tools=Path('C:/Program Files/MongoDB/Tools/bin');before=snapshot(server.db)
    script=server.root/'tools.ps1';script.write_text((ROOT/'scripts/institution_v2n_tools_secret.ps1').read_text().replace('v2n','v2o'))
    uri=server.writer_uri.replace('/'+server.database+'?','/?')
    p=subprocess.run([shutil.which('pwsh.exe'),'-NoProfile','-NonInteractive','-File',str(script)],input=json.dumps({'fixture_root':str(server.root),'uri':uri}),capture_output=True,text=True,timeout=20)
    assert p.returncode==0
    config=server.root/'tools-secret/mongo-tools.yml';dump=server.root/'dump'
    restore_db=server.database+'_restore'
    for tool,args in [('mongodump',['--db='+server.database,'--out='+str(dump)]),('mongorestore',['--nsInclude='+server.database+'.*','--nsFrom='+server.database+'.*','--nsTo='+restore_db+'.*',str(dump)])]:
        p=subprocess.run([str(tools/(tool+'.exe')),'--config='+str(config),*args],capture_output=True,text=True,timeout=120)
        assert server.password not in p.stdout+p.stderr
        (ROOT/f'reports/institution_v2o_{tool}.log').write_text(p.stdout+p.stderr)
        assert p.returncode==0
    restored=server.writer[restore_db];after=snapshot(restored)
    # Index enumeration order is not an index contract; compare named specs.
    for collection in before.values():collection['indexes']=sorted(collection['indexes'],key=lambda item:item['name'])
    for collection in after.values():collection['indexes']=sorted(collection['indexes'],key=lambda item:item['name'])
    if before!=after:(ROOT/'reports/institution_v2o_restore_difference.json').write_text(json.dumps({'before':before,'after':after},indent=2,default=str))
    assert before==after
    filesystem=[]
    for name in ['tenant-artifacts','assets']:
        original=server.root/name;destination=server.root/'restored-files'/name
        shutil.copytree(original,destination)
        hashes=lambda folder:{p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}
        assert hashes(original)==hashes(destination)
        filesystem.append({'root':name,'files':len(hashes(original)),'hashes_equal':True})
    grants=server.db.command('rolesInfo','fixture_application_envelope',showPrivileges=True)['roles'][0]['privileges']
    for grant in grants:grant['resource']['db']=restore_db
    restored.command('createRole','restored_application',privileges=grants,roles=[])
    password=secrets.token_urlsafe(32)
    restored.command('createUser','restored_application',pwd=password,roles=[{'role':'restored_application','db':restore_db}])
    uri=f'mongodb://restored_application:{quote(password)}@127.0.0.1:{server.port}/{restore_db}?authSource={restore_db}'
    asset=restored.institution_library_assets.find_one({'library_id':fullstack['serving_library']})
    env={**os.environ,'MONGO_URI':uri,'MONGO_DB_NAME':restore_db,'LUMINAR_MONGO_MODE':'AUTHENTICATED','JWT_SECRET_KEY':'o-owned-restore-key',
         'LIBRARY_INTELLIGENCE_ROOT':str(server.root/'restored-files/tenant-artifacts'),'LIBRARY_ASSET_ROOT':str(server.root/'restored-files/assets'),
         'LUMINAR_SESSION_DB':str(server.root/'restored-files/sessions.sqlite'),'NOTIFICATION_DUE_WORKER_ENABLED':'0','NOTIFICATION_OUTBOX_WORKER_ENABLED':'0',
         'LUMINAR_WORKER_TELEMETRY_ENABLED':'0','LUMINAR_V2O_LIBRARY':fullstack['serving_library'],'LUMINAR_V2O_ASSET':asset['asset_id']}
    p=subprocess.run([sys.executable,str(ROOT/'scripts/institution_v2o_restore_child.py')],cwd=ROOT,env=env,capture_output=True,text=True,timeout=90)
    (ROOT/'reports/institution_v2o_restored_API.log').write_text(p.stdout+p.stderr)
    assert p.returncode==0
    final=snapshot(server.db)
    for collection in final.values():collection['indexes']=sorted(collection['indexes'],key=lambda item:item['name'])
    assert final==before
    result={'result':'FIXTURE_PASS','collections':len(before),'snapshots':before,'BSON_counts_indexes_options_validators_equal':True,'cross_store':filesystem,
            'restored_API':json.loads(p.stdout),'source_unchanged':True,'real_production_restore':'NOT_VERIFIED','checkpoint':'Owned fixture app/Search closed; no active writer during dump/copy. No production data export.'}
    (ROOT/'reports/institution_v2o_backup_fixture.json').write_text(json.dumps(result,indent=2,default=str))
