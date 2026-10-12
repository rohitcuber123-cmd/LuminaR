from uuid import uuid4
import pytest
from backend.database.mongodb import db


def command(**fields): return {'idempotency_key': str(uuid4()), **fields}
def borrow(client, library, user=1):
    return client.post(library['base'] + '/lending/borrow-requests', headers={'x-test-user': str(user)}, json=command(library_book_id=library['book']))
def loan(client, library):
    requested = borrow(client, library); assert requested.status_code == 201, requested.text
    issued = client.post(library['base'] + '/staff/lending/borrow-requests/' + requested.json()['lending_request_id'] + '/approve',
        headers={'x-test-user': str(library['owner'])}, json=command())
    assert issued.status_code == 200, issued.text
    return client.get(library['base'] + '/me/loans').json()['results'][0]


@pytest.mark.parametrize('index', [0, 2], ids=['admin', 'librarian'])
def test_staff_cannot_create_patron_borrow_request_same_library(client, libraries, index):
    before = db.institution_lending_requests.count_documents({})
    assert borrow(client, libraries[index]).status_code == 403
    assert db.institution_lending_requests.count_documents({}) == before


def test_general_user_patron_actions_allowed(client, libraries):
    row = loan(client, libraries[1]); base = libraries[1]['base']
    assert client.post(base + '/loans/' + row['loan_id'] + '/renew', json=command(expected_due_at=row['due_at'])).status_code == 200
    assert client.post(base + '/loans/' + row['loan_id'] + '/return-request', json=command()).status_code == 201
    assert client.get(base + '/me/loans').json()['results'][0]['status'] == 'ACTIVE'


@pytest.mark.parametrize('role', ['ADMIN', 'LIBRARIAN'])
def test_staff_cannot_use_personal_return_renew_or_views_after_promotion(client, libraries, role):
    library = libraries[1]; row = loan(client, library)
    membership = db.institution_memberships.find_one({'library_id': library['id'], 'user_id': 1})
    assert client.patch(library['base'] + '/memberships/' + membership['membership_id'], json={'role': role}, headers={'x-test-user': '2'}).status_code == 200
    base = library['base']
    assert client.post(base + '/loans/' + row['loan_id'] + '/return-request', json=command()).status_code == 403
    assert client.post(base + '/loans/' + row['loan_id'] + '/renew', json=command(expected_due_at=row['due_at'])).status_code == 403
    for path in ['/me/loans', '/me/borrow-requests', '/me/reservations', '/me/fees']:
        assert client.get(base + path).status_code == 403
    assert client.get(base + '/staff/loans').status_code == 200
    assert db.institution_loans.find_one({'loan_id': row['loan_id']})['status'] == 'ACTIVE'


@pytest.mark.parametrize('index', [0, 2], ids=['admin', 'librarian'])
def test_staff_operations_allowed_without_personal_endpoints(client, libraries, index):
    base = libraries[index]['base']
    for path in ['/inventory/books', '/staff/lending/borrow-requests', '/staff/lending/return-requests', '/staff/loans', '/staff/reservations', '/staff/fees']:
        response = client.get(base + path); assert response.status_code == 200, (path, response.text)


def test_mixed_role_account_different_libraries(client, libraries):
    assert [client.get(row['base'] + '/context').json()['membership']['role'] for row in libraries] == ['ADMIN', 'GENERAL_USER', 'LIBRARIAN']
    assert [borrow(client, row).status_code for row in libraries] == [403, 201, 403]
    assert client.get(libraries[1]['base'] + '/staff/loans').status_code == 403


def test_member_cancellation_allowed_then_rejected_after_staff_promotion(client, libraries):
    library = libraries[1]; first = borrow(client, library).json()
    assert client.post(library['base'] + '/lending/borrow-requests/' + first['lending_request_id'] + '/cancel', json=command()).status_code == 200
    second = borrow(client, library).json()
    db.institution_memberships.update_one({'library_id': library['id'], 'user_id': 1}, {'$set': {'role': 'LIBRARIAN'}})
    assert client.post(library['base'] + '/lending/borrow-requests/' + second['lending_request_id'] + '/cancel', json=command()).status_code == 403
    assert db.institution_lending_requests.find_one({'lending_request_id': second['lending_request_id']})['status'] == 'PENDING'


@pytest.mark.parametrize('index', [0, 2], ids=['admin', 'librarian'])
def test_staff_reservation_and_member_fee_endpoints_require_patron_role(client, libraries, index):
    library = libraries[index]; base = library['base']
    assert client.post(base + '/reservations', json=command(library_book_id=library['book'])).status_code == 403
    assert client.post(base + '/reservations/' + str(uuid4()) + '/cancel', json=command()).status_code == 403
    for path in ['/me/fees', '/me/fees/' + str(uuid4()), '/me/reservations', '/inventory/' + library['book'] + '/reservation-status']:
        assert client.get(base + path).status_code == 403


def test_patron_reservation_and_fee_read_allowed(client, libraries):
    library = libraries[1]; base = library['base']
    assert client.put(base + '/staff/lending/books/' + library['book'] + '/stock', headers={'x-test-user': '2'}, json=command(total_copies=0, circulation_status='CIRCULATING')).status_code == 200
    response = client.post(base + '/reservations', json=command(library_book_id=library['book']))
    assert response.status_code == 201, response.text
    assert client.get(base + '/me/fees').status_code == 200
    assert client.post(base + '/reservations/' + response.json()['reservation_id'] + '/cancel', json=command()).status_code == 200


def test_inactive_membership_and_account_cannot_use_patron_guard(client, libraries):
    library = libraries[1]
    db.institution_memberships.update_one({'library_id': library['id'], 'user_id': 1}, {'$set': {'status': 'SUSPENDED'}})
    assert borrow(client, library).status_code == 404
    db.institution_memberships.update_one({'library_id': library['id'], 'user_id': 1}, {'$set': {'status': 'ACTIVE'}})
    db.users.update_one({'user_id': 1}, {'$set': {'is_active': False}})
    assert borrow(client, library).status_code == 401
