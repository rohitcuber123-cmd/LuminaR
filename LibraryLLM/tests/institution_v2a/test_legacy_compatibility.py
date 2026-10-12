"""Ensure new catalogue writes leave the preserved legacy flows usable."""


def test_legacy_inventory_crud_still_uses_legacy_collection(client, database, h, register, create):
    library_id = register(); canonical = create(library_id)
    body = {'library_id': 'LIB001', 'work_id': 'OL-Networks', 'total_copies': 3, 'available_copies': 2}
    before = list(database.institution_holdings.find({}))
    assert client.post('/inventory/', json=body, headers=h(20, 'ADMIN')).status_code == 410
    assert client.put('/inventory/LIB001/OL-Networks', json={'total_copies': 4}, headers=h(20, 'ADMIN')).status_code == 410
    assert client.delete('/inventory/LIB001/OL-Networks', headers=h(20, 'ADMIN')).status_code == 410
    assert database.library_inventory.count_documents({}) == 0
    assert list(database.institution_holdings.find({})) == before


def test_reading_list_and_legacy_staff_operation_lists_still_work(client, database, h):
    assert client.post('/reading-list/', json={'work_id': 'OL-Networks'}, headers=h(1)).status_code == 200
    assert client.get('/reading-list/my', headers=h(1)).json()['count'] == 1
    assert client.get('/reading-list/my', headers=h(2)).json()['count'] == 0
    assert client.delete('/reading-list/OL-Networks', headers=h(1)).status_code == 200
    for path in ('/issues/all', '/reservations/all', '/fines/all'):
        assert client.get(path, headers=h(20, 'ADMIN')).status_code == 403
        assert client.get(path, headers=h(1)).status_code == 403
