"""Independent authenticated fixture server; no production DB or worker starts."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import pytest
from scripts.institution_v2j_fixture import AuthMongo,seed_database


@pytest.fixture(scope='session')
def auth_server():
    with AuthMongo() as server:
        seed_database(server)
        yield server


@pytest.fixture(autouse=True)
def empty_rows(auth_server,tmp_path):
    for name in auth_server.db.list_collection_names():
        if not name.startswith('system.'):
            auth_server.db[name].delete_many({})
    auth_server.artifact_root=tmp_path/'artifacts'
    auth_server.artifact_root.mkdir()
