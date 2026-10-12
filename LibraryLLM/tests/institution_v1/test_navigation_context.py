"""Generic account-discovery regressions in the existing disposable Mongo DB."""
import pytest

@pytest.mark.parametrize('private', [False, True])
def test_me_libraries_returns_general_user_membership(client, register, h, private):
    lid = register(private=private)['library']['library_id']
    body = {'access_code': 'Institution Test Passphrase'} if private else {}
    assert client.post(f'/libraries/{lid}/join', headers=h(2), json=body).status_code == 200
    result = client.get('/me/libraries?limit=100', headers=h(2, 'ADMIN')).json()
    assert len(result['results']) == 1
    row = result['results'][0]
    assert row['library_id'] == lid
    assert row['membership']['role'] == 'GENERAL_USER'
    assert row['membership']['status'] == 'ACTIVE'
    direct = client.get(f'/libraries/{lid}/context', headers=h(2)).json()
    assert direct['membership'] == row['membership']

def test_account_discovery_pagination_keeps_all_active_memberships(client, register, h, database):
    ids = [register()['library']['library_id'] for _ in range(4)]
    for lid in ids:
        assert client.post(f'/libraries/{lid}/join', headers=h(2), json={}).status_code == 200
    # A lifecycle-disabled library is deliberately inaccessible on both paths.
    database.institution_libraries.update_one({'library_id': ids[1]}, {'$set': {'status': 'SUSPENDED'}})
    returned = []
    offset = 0
    while True:
        page = client.get(f'/me/libraries?limit=2&offset={offset}', headers=h(2)).json()
        returned.extend(row['library_id'] for row in page['results'])
        if not page['has_more']:
            break
        offset += 2
    assert set(returned) == set(ids) - {ids[1]}
    assert client.get(f'/libraries/{ids[1]}/context', headers=h(2)).status_code == 404

def test_membership_role_change_updates_authoritative_discovery(client, register, invite, accept, h):
    lid = register()['library']['library_id']
    accept(invite(lid, role='LIBRARIAN'))
    row = client.get('/me/libraries', headers=h(2)).json()['results'][0]
    assert row['membership']['role'] == 'LIBRARIAN'
    mid = row['membership']['membership_id']
    assert client.patch(f'/libraries/{lid}/memberships/{mid}', json={'role':'GENERAL_USER'}).status_code == 200
    assert client.get('/me/libraries', headers=h(2)).json()['results'][0]['membership']['role'] == 'GENERAL_USER'
