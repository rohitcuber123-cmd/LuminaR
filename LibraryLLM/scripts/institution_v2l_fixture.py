"""Owned authenticated2L fixture; reusable K provisioning, no production actions."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'scripts/institution_v2k_fixture.py').read_text(encoding='utf8')
source=source.replace('luminar-v2k-auth-','luminar-v2l-auth-').replace('luminar_v2k_fixture_','luminar_v2l_fixture_')
exec(compile(source,str(ROOT/'scripts/institution_v2k_fixture.py'),'exec'))


def provision_unauthorized(server):
    assert server.database.startswith('luminar_v2l_fixture_')
    password=secrets.token_urlsafe(32)
    server.db.command('createRole','fixture_unrelated_reader',privileges=[
        {'resource':{'db':server.database,'collection':'unrelated_fixture'},'actions':['find']}],roles=[])
    server.db.command('createUser','fixture_unauthorized',pwd=password,roles=[{'role':'fixture_unrelated_reader','db':server.database}])
    server.unauthorized_uri=f'mongodb://fixture_unauthorized:{quote(password)}@127.0.0.1:{server.port}/{server.database}?authSource={server.database}'
