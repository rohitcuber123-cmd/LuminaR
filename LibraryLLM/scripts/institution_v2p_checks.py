"""Accepted full product inventory through O.3, plus Part 2P when present."""
from pathlib import Path
import os,sys,json,shutil
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2i_checks.py').read_text(encoding='utf8').replace('institution_v2i_', 'institution_v2p_').replace('institution-v2i/', 'institution-v2p/')
source=source.replace("if tag != 'baseline' and (ROOT / 'tests/institution_v2i').exists():", "if (ROOT / 'tests/institution_v2i').exists():")
source=source.replace("groups['institution_v2i'] = ['tests/institution_v2i']", "\n".join("    " * (i>0) + f"groups['institution_{v}'] = ['tests/institution_{v}']" for i,v in enumerate(['v2i','v2j','v2k','v2l','v2m','v2n','v2o','v2o1','v2o2','v2o3','v2o3_closure'])) + "\n    if (ROOT/'tests/institution_v2p').exists(): groups['institution_v2p'] = ['tests/institution_v2p']")
owned=None
if len(sys.argv)>1 and sys.argv[1]=='backend':
    # Some accepted legacy tests enter the core lifespan before their own
    # collection monkeypatches. Give every fallback import an owned database;
    # explicit suite fixtures retain their stronger per-suite isolation.
    owned='luminar_v2p_regression_'+uuid4().hex[:24]
    scope_root=(ROOT/'.scratch/institution-v2p/regression'/owned).resolve()
    scope_root.mkdir(parents=True,exist_ok=False)
    os.environ.update(MONGO_URI='mongodb://127.0.0.1:27017',MONGO_DB_NAME=owned,LUMINAR_MONGO_MODE='DEVELOPMENT',
        JWT_SECRET_KEY='part2p-owned-regression-'+uuid4().hex,LUMINAR_SESSION_DB=str(scope_root/'sessions.sqlite'),
        NOTIFICATION_DUE_WORKER_ENABLED='0',NOTIFICATION_OUTBOX_WORKER_ENABLED='0')
try:
    exec(compile(source,str(ROOT/'scripts/institution_v2i_checks.py'),'exec'),{'__file__':str(ROOT/'scripts/institution_v2i_checks.py'),'__name__':'__main__'})
finally:
    if owned:
        from pymongo import MongoClient
        assert owned.startswith('luminar_v2p_regression_') and owned!='luminar_library'
        with MongoClient('mongodb://127.0.0.1:27017') as client:client.drop_database(owned)
        assert scope_root.is_relative_to((ROOT/'.scratch/institution-v2p/regression').resolve()) and scope_root.name==owned
        shutil.rmtree(scope_root)
        (ROOT/f'reports/institution_v2p_{sys.argv[2]}_test_isolation.json').write_text(json.dumps({'fallback_database':owned,
            'owned_database_removed':True,'owned_session_directory_removed':True,'existing_test_bodies_unchanged':True,
            'background_workers_disabled_by_default_in_fixture':True,'explicit_worker_tests_may_enable_their_owned_workers':True},indent=2),encoding='utf8')
