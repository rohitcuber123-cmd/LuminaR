"""Actual isolated Mongo authorization; never connects to the existing endpoint."""
import json
from pathlib import Path
from urllib.parse import quote

import pytest
from pymongo import MongoClient
from pymongo.errors import OperationFailure

from backend.database.mongo_configuration import MongoConfigurationError, connect, settings
from scripts.institution_v2n_fixture import AuthMongo, provision, provision_application, seed_database


@pytest.fixture(scope='module')
def server():
    with AuthMongo() as fixture:
        seed_database(fixture); provision(fixture); provision_application(fixture)
        yield fixture


def configuration(server, **overrides):
    return settings({'LUMINAR_MONGO_MODE': 'AUTHENTICATED', 'MONGO_URI': server.app_uri,
                     'MONGO_DB_NAME': server.database, **overrides})


def denied(call):
    with pytest.raises(OperationFailure) as error:
        call()
    assert error.value.code in {13, 18}


def test_authenticated_mongo_connect(server):
    with connect(configuration(server)) as client:
        assert client[server.database].command('connectionStatus')['authInfo']['authenticatedUsers'][0]['user'] == 'fixture_application'


def test_anonymous_mongo_denied(server):
    with MongoClient(f'mongodb://127.0.0.1:{server.port}', serverSelectionTimeoutMS=1000) as client:
        denied(lambda: client[server.database].users.find_one({}))


def test_invalid_credential_denied(server):
    uri = server.app_uri.replace(quote(server.app_password), 'invalid-fixture-secret')
    with pytest.raises(MongoConfigurationError, match='MONGO_AUTH_CONNECTION_NOT_QUALIFIED'):
        connect(configuration(server, MONGO_URI=uri))


def test_wrong_auth_source_denied(server):
    with pytest.raises(MongoConfigurationError):
        connect(configuration(server, MONGO_URI=server.app_uri.replace('authSource=' + server.database, 'authSource=admin')))


def test_wrong_database_denied(server):
    wrong = server.database + '_typo'
    with pytest.raises(MongoConfigurationError):
        connect(configuration(server, MONGO_URI=server.app_uri.replace('/' + server.database + '?', '/' + wrong + '?'), MONGO_DB_NAME=wrong))
    assert wrong not in server.writer.list_database_names()


def test_application_runtime_permissions(server):
    with connect(configuration(server)) as client:
        coll = client[server.database].institution_libraries
        coll.create_index('library_id', unique=True)
        coll.insert_one({'library_id': 'n-auth-test'})
        coll.update_one({'library_id': 'n-auth-test'}, {'$set': {'status': 'ACTIVE'}})
        assert list(coll.aggregate([{'$match': {'library_id': 'n-auth-test'}}]))[0]['status'] == 'ACTIVE'
        coll.delete_one({'library_id': 'n-auth-test'})
        denied(lambda: client.drop_database(server.database))
        denied(lambda: client[server.database].command('createUser', 'forbidden', pwd='disposable', roles=[]))


def test_worker_job_claim_permission(server):
    with connect(configuration(server)) as client:
        coll = client[server.database].institution_intelligence_jobs
        coll.insert_one({'job_id': 'n-claim', 'state': 'QUEUED', 'library_id': 'fixture', 'target': 'SEARCH_INDEX'})
        assert coll.find_one_and_update({'job_id': 'n-claim', 'state': 'QUEUED'}, {'$set': {'state': 'RUNNING'}})


def test_worker_lease_renewal_permission(server):
    with connect(configuration(server)) as client:
        assert client[server.database].institution_intelligence_jobs.update_one({'job_id': 'n-claim'}, {'$set': {'lease_test': True}}).matched_count == 1


def test_worker_generation_publish_permission(server):
    with connect(configuration(server)) as client:
        client[server.database].institution_intelligence_generations.insert_one({'generation_id': 'n-generation'})
        client[server.database].institution_intelligence_targets.update_one({'library_id': 'fixture', 'target': 'SEARCH_INDEX'}, {'$set': {'active_generation_id': 'n-generation'}}, upsert=True)


def test_telemetry_writer_restricted(server):
    with MongoClient(server.telemetry_uri) as client:
        db = client[server.database]
        assert db.institution_worker_telemetry_v2k.find_one({})
        for name in ['institution_intelligence_jobs', 'institution_intelligence_targets', 'institution_intelligence_generations',
                     'institution_locks', 'institution_library_books', 'institution_memberships', 'books']:
            denied(lambda: db[name].update_one({'_id': '__no_match__'}, {'$set': {'denied': True}}))
        denied(lambda: db.institution_memberships.find_one({}))
        denied(lambda: client['unrelated_global'].books.find_one({}))


def test_operator_reader_read_only(server):
    from backend.services.library_operator_access import connect_operator
    reader = connect_operator(server.reader_uri, server.database)
    try:
        assert reader.client[server.database].users.find_one({})
    finally:
        reader.close()


def test_operator_reader_cannot_write(server):
    with MongoClient(server.reader_uri) as client:
        denied(lambda: client[server.database].users.insert_one({'denied': True}))


def test_no_unrestricted_fallback(server, monkeypatch):
    import backend.database.mongo_configuration as module
    original = module.MongoClient
    calls = []
    def observed(uri, **options):
        calls.append('authenticated' if '@' in uri else 'anonymous')
        return original(uri, **options)
    monkeypatch.setattr(module, 'MongoClient', observed)
    bad = server.app_uri.replace(quote(server.app_password), 'invalid-fixture-secret')
    with pytest.raises(MongoConfigurationError):
        connect(configuration(server, MONGO_URI=bad))
    assert calls == ['authenticated']


def test_no_credentials_in_logs(server, caplog):
    bad = server.app_uri.replace(quote(server.app_password), 'invalid-fixture-secret')
    with pytest.raises(MongoConfigurationError) as error:
        connect(configuration(server, MONGO_URI=bad))
    assert server.app_password not in caplog.text + str(error.value)
    assert 'mongodb://' not in str(error.value)
    assert server.app_uri not in repr(configuration(server))


def test_no_secrets_in_report(server):
    for path in (Path(__file__).resolve().parents[2] / 'reports').glob('institution_v2n_*'):
        if path.suffix in {'.json', '.md', '.log', '.xml'}:
            content = path.read_text(encoding='utf8', errors='replace')
            assert server.app_password not in content and server.password not in content and server.telemetry_password not in content


def test_private_library_isolation(server):
    # Mongo infrastructure login does not itself mint an application JWT.
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient
    from backend.dependencies import get_current_user
    app = FastAPI()
    @app.get('/private')
    def private(user=Depends(get_current_user)):
        return user
    assert TestClient(app).get('/private', headers={'Authorization': 'Bearer ' + server.app_password}).status_code in {401, 403}


def test_platform_role_no_tenant_bypass():
    # Frozen authenticated API suites and real-JWT native child prove the route
    # boundary; keep an explicit source guard here against legacy-role bypass.
    from backend.dependencies import require_roles
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        require_roles('ADMIN')(current_user={'role': 'ADMIN'})
    assert error.value.status_code == 403


def test_unauthorized_collection_read_denied(server):
    with connect(configuration(server)) as client:
        denied(lambda: client[server.database].unrelated_sensitive_collection.find_one({}))


@pytest.mark.parametrize('change', [{'MONGO_URI': ''}, {'MONGO_DB_NAME': ''}, {'MONGO_URI': 'mongodb://127.0.0.1:27017'}])
def test_auth_mode_missing_secret_fails_closed(server, change):
    with pytest.raises(MongoConfigurationError):
        configuration(server, **change)


def test_authenticated_runtime_reconnect(server):
    for _ in range(3):
        with connect(configuration(server)) as client:
            assert client[server.database].users.find_one({})


def test_authenticated_fixture_rollback(server):
    before = server.db.users.count_documents({})
    with pytest.raises(MongoConfigurationError):
        connect(configuration(server, MONGO_URI=server.app_uri.replace(quote(server.app_password), 'invalid-fixture-secret')))
    with connect(configuration(server)) as client:
        assert client[server.database].users.count_documents({}) == before


def test_global_indexes_unchanged(server):
    before = list(server.db.users.list_indexes())
    with connect(configuration(server)) as client:
        denied(lambda: client['global_outside_fixture'].books.create_index('denied'))
    assert list(server.db.users.list_indexes()) == before


def test_valid_login_unrelated_role_fails_qualification(server):
    password = 'unrelated-disposable-fixture'
    server.db.command('createRole', 'unrelated', privileges=[{'resource': {'db': server.database, 'collection': 'unrelated'}, 'actions': ['find']}], roles=[])
    server.db.command('createUser', 'unrelated', pwd=password, roles=[{'role': 'unrelated', 'db': server.database}])
    uri = server.app_uri.replace('fixture_application:' + quote(server.app_password), 'unrelated:' + password)
    with pytest.raises(MongoConfigurationError):
        connect(configuration(server, MONGO_URI=uri))


def test_auth_mode_rejects_server_without_authorization():
    import scripts.institution_v2n_fixture as fixture
    namespace = {'__file__': fixture.__file__}
    source = fixture.source.replace(",'--auth'", '').replace('luminar-v2n-auth-', 'luminar-v2n-noauth-')
    exec(compile(source, fixture.__file__, 'exec'), namespace)
    with namespace['AuthMongo']() as server:
        # The maintenance principal can authenticate even with enforcement off.
        server.db.users.insert_one({'fixture': True})
        with pytest.raises(MongoConfigurationError, match='MONGO_AUTHORIZATION_NOT_ENFORCED'):
            connect(settings({'LUMINAR_MONGO_MODE': 'AUTHENTICATED', 'MONGO_URI': server.writer_uri, 'MONGO_DB_NAME': server.database}))
