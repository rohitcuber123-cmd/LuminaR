"""Clean only phase-owned disposable fixtures; preserve TEST and its QA history."""
import json
import os
from pathlib import Path
from uuid import UUID
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
TEST = 'e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'


def main():
    load_dotenv(ROOT / '.env'); mongo = MongoClient(os.getenv('MONGO_URI'))
    database = mongo['luminar_library']
    path = ROOT / 'reports/product_consistency_temporary_library.json'
    row = json.loads(path.read_text(encoding='utf8')); lid = str(UUID(row['library_id']))
    assert lid != TEST and row['name'] == 'Disposable QA Global Fallback'
    actual = database.institution_libraries.find_one({'library_id': lid})
    deleted = {}
    if actual:
        assert actual['owner_user_id'] == 4 and actual['name'] == row['name'] and actual['slug'] == row['slug']
        assert actual['access_mode'] == 'PRIVATE_CODE'
        members = list(database.institution_memberships.find({'library_id':lid}))
        assert {m['user_id'] for m in members} == {4, 6}, 'Unexpected account joined; preserve for review.'
        assert not database.institution_locks.find_one({'_id':lid}), 'Temporary library has an active/uncertain writer.'
        for name in ['library_books', 'holdings', 'lending_requests', 'loans', 'reservations', 'fees']:
            assert database['institution_' + name].count_documents({'library_id':lid}) == 0
        for name in database.list_collection_names():
            if name.startswith('institution_'):
                count = database[name].delete_many({'library_id':lid}).deleted_count
                if count: deleted[name] = count
    assert not database.institution_libraries.find_one({'library_id':lid})
    assert database.institution_libraries.find_one({'library_id':TEST,'status':'ACTIVE'})
    assert database.institution_library_books.count_documents({'library_id':TEST,'status':'ACTIVE'}) == 150
    assert database.institution_memberships.find_one({'library_id':TEST,'user_id':6,'role':'GENERAL_USER','status':'ACTIVE'})
    report = {'temporary_library_id': lid, 'temporary_library_removed': True, 'deleted_scoped_counts': deleted,
        'test_library_id': TEST, 'test_library_preserved': True, 'test_books_preserved':150,
        'separate_test_patron_membership_preserved':True, 'qa_lending_and_reservation_history_preserved':True}
    (ROOT / 'reports/product_consistency_temporary_cleanup.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    (ROOT / '.scratch/product-ui-fixture/stop').write_text('stop',encoding='utf8')
    print('Disposable fallback removed; isolated fixture shutdown requested; TEST preserved.')


if __name__ == '__main__': main()
