"""Actual command entrypoints fail closed before owned fixture writes; no builds."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
results=[]
with tempfile.TemporaryDirectory(prefix='luminar-v2o-cli-') as directory:
    root=Path(directory)
    env={**os.environ,'LUMINAR_MONGO_MODE':'AUTHENTICATED','MONGO_URI':'mongodb://127.0.0.1:1/owned_missing_secret',
         'MONGO_DB_NAME':'owned_missing_secret','LUMINAR_SEARCH_INDEX_DIR':str(root/'index'),
         'LUMINAR_LEXICAL_SYNC_ENABLED':'true'}
    for command in [['scripts/build_lexical_sidecar.py','--check','--output',str(root/'lexical')],
                    ['scripts/lexical_maintenance.py','process-once','--apply','--root',str(root/'lexical')],
                    ['scripts/lexical_worker.py','--apply','--root',str(root/'lexical')],
                    ['-m','search.maintenance','worker','--index-dir',str(root/'index')]]:
        p=subprocess.run([sys.executable,*command],cwd=ROOT,env=env,capture_output=True,text=True,timeout=45)
        assert p.returncode!=0 and 'MONGO_AUTH_SETTINGS_REQUIRED' in p.stderr
        assert env['MONGO_URI'] not in p.stdout+p.stderr
        results.append({'entrypoint':command[0:2],'result':'MISSING_SECRET_DENIED_BEFORE_MONGO_CONNECTION','exit':p.returncode})
(ROOT/'reports/institution_v2o_cli_configuration.json').write_text(json.dumps({'commands':results,'owned_directory_removed':True},indent=2))
print('Four actual CLI authenticated-mode missing-secret gates PASS')
