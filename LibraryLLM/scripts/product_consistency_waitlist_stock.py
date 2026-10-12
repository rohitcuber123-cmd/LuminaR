"""Temporarily make one QA holding unavailable; restore via canonical API."""
import argparse
import getpass
import json
import os
from pathlib import Path
from uuid import uuid4
import httpx
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = 'e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
BOOK = '0118641f-a0e3-44ac-84a1-62689951faaa'


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--restore', action='store_true'); args = parser.parse_args()
    load_dotenv(ROOT / '.env'); database = MongoClient(os.getenv('MONGO_URI'))['luminar_library']
    scope = {'library_id': LIBRARY, 'library_book_id': BOOK}
    row = database.institution_holdings.find_one(scope)
    assert row and row['circulation_status'] == 'CIRCULATING' and row['total_copies'] == 1
    assert not database.institution_loans.find_one({**scope, 'status': 'ACTIVE'})
    assert not database.institution_lending_requests.find_one({**scope, 'status': 'PENDING'})
    target = ROOT / 'reports/product_consistency_waitlist_stock.json'
    report = json.loads(target.read_text(encoding='utf8')) if target.exists() else {'library_id': LIBRARY, 'book_id': BOOK}
    if not args.restore:
        assert row.get('unavailable_stock', 0) == 0
        report['before'] = {key: row.get(key) for key in ['total_copies', 'unavailable_stock', 'circulation_status', 'shelf_location']}
    password = getpass.getpass('TEST owner development password (runtime only): ')
    with httpx.Client(timeout=90) as client:
        response = client.post('http://127.0.0.1:8088/auth/login', json={'email':'rohitcuber123@gmail.com', 'password': password})
        response.raise_for_status(); headers = {'Authorization':'Bearer ' + response.json()['access_token']}
        response = client.put('http://127.0.0.1:8088/libraries/' + LIBRARY + '/staff/lending/books/' + BOOK + '/stock',
            headers=headers, json={'idempotency_key':str(uuid4()), 'total_copies':1, 'unavailable_stock':0 if args.restore else 1,
                'circulation_status':'CIRCULATING', 'allocation_mode':'AGGREGATE'})
        response.raise_for_status()
    report['restored' if args.restore else 'unavailable_for_qa'] = True
    report['canonical_api_used'] = True
    target.write_text(json.dumps(report, indent=2), encoding='utf8')
    print('QA stock restored.' if args.restore else 'One QA holding is unavailable for waitlist validation.')


if __name__ == '__main__': main()
