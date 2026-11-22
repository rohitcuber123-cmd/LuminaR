"""Real Mongo library gate contention, not a simulated dependency error."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from backend.services.institution_repository import library_mutation
from tests.institution_v2q_ai.test_integration import fixture
from backend.database.mongodb import db


def test_recommendation_waits_for_short_authority_lock(client, fixture):
    _, libs, books, _ = fixture
    with ThreadPoolExecutor(max_workers=1) as pool:
        with library_mutation(libs[0]):
            future = pool.submit(client.post, f'/libraries/{libs[0]}/catalogue/recommendations',
                headers={'x-test-user':'2'}, json={'work_ids': [], 'limit':10})
            try:
                premature = future.result(timeout=0.3)
            except TimeoutError:
                premature = None
        response = premature or future.result(timeout=35)
    assert response.status_code == 200, response.text
    assert {x['library_book_id'] for x in response.json()['results']} == {books[0]}


def test_revocation_during_wait_is_denied(client, fixture):
    _, libs, _, _ = fixture
    with ThreadPoolExecutor(max_workers=1) as pool:
        with library_mutation(libs[0]):
            future = pool.submit(client.post, f'/libraries/{libs[0]}/catalogue/recommendations',
                headers={'x-test-user':'2'}, json={'work_ids': [], 'limit':10})
            try:
                early = future.result(timeout=0.2)
            except TimeoutError:
                early = None
            db.institution_memberships.update_one({'library_id':libs[0],'user_id':2}, {'$set':{'status':'REMOVED'}})
        response = early or future.result(timeout=35)
    assert response.status_code == 404


def test_overlapping_recommendations_keep_tenant_ownership(client, fixture):
    _, libs, books, _ = fixture
    attempted = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for _ in range(2):
            calls = [(i, pool.submit(client.post, f'/libraries/{libs[i]}/catalogue/recommendations',
                headers={'x-test-user':'2'}, json={'work_ids':['OL999W'], 'limit':10})) for i in [0,1,0,1]]
            for i, future in calls:
                response = future.result(timeout=35)
                attempted += 1
                assert response.status_code == 200, response.text
                assert {x['library_book_id'] for x in response.json()['results']} == {books[i]}
    assert attempted == 8
