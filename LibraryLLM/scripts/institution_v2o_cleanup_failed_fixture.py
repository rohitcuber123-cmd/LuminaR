"""Cleanup only the independently identified J startup failure from this O run."""
import json,shutil,tempfile,time
from datetime import datetime,timezone
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parents[1]
target=(Path(tempfile.gettempdir())/'luminar-v2j-auth-8hlg8pdr').resolve()
assert target.parent==Path(tempfile.gettempdir()).resolve() and target.name=='luminar-v2j-auth-8hlg8pdr'
baseline=json.loads((ROOT/'reports/institution_v2o_baseline.json').read_text())
assert target.stat().st_ctime>datetime.fromisoformat(baseline['captured_at']).timestamp()
rows=[json.loads(line) for line in (target/'mongo.log').read_text().splitlines()[:30]]
startup=next(row['attr'] for row in rows if row.get('msg')=='MongoDB starting')
assert Path(startup['dbPath']).resolve()==target/'db' and startup['pid']==56316
process=psutil.Process(startup['pid'])
assert process.name().lower()=='mongod.exe'
arguments=process.cmdline()
assert '--dbpath' in arguments and Path(arguments[arguments.index('--dbpath')+1]).resolve()==target/'db'
assert process.create_time()>datetime.fromisoformat(baseline['captured_at']).timestamp()
process.terminate();process.wait(timeout=15)
shutil.rmtree(target)
(ROOT/'reports/institution_v2o_fixture_cleanup.json').write_text(json.dumps({'owned_startup_failure_root':str(target),'pid':startup['pid'],
    'log_and_process_dbpath_verified':True,'created_after_O_baseline':True,'owned_process_ended':True,'owned_directory_removed':not target.exists(),
    'actual_Mongo_service_controlled':False},indent=2))
print('Verified task-owned failed startup process/root removed; actual Mongo untouched.')
