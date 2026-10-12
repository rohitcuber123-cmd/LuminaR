"""Read-only same-tenant references, quantities, identity, links and sequence reconciliation."""
from collections import Counter
import json
import os
from pathlib import Path
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def reconcile(database, library_id):
    library_id = str(UUID(library_id))
    if not database.institution_libraries.find_one({'library_id': library_id}):
        raise ValueError('Canonical library not found.')
    books = list(database.institution_library_books.find({'library_id': library_id}))
    holdings = list(database.institution_holdings.find({'library_id': library_id}))
    copies = list(database.institution_copies.find({'library_id': library_id}))
    by_book = {row.get('library_book_id'): row for row in books}; by_holding = {row.get('holding_id'): row for row in holdings}
    errors = []
    for rows, field in ((books, 'library_book_id'), (holdings, 'holding_id'), (copies, 'copy_id')):
        for row in rows:
            try:
                UUID(str(row.get(field)))
            except (ValueError, TypeError):
                errors.append({'reason': 'INVALID_' + field.upper()})
        if len({row.get(field) for row in rows}) != len(rows):
            errors.append({'reason': 'DUPLICATE_' + field.upper()})
    for field in ('library_book_id', 'accession_number', 'accession_sequence'):
        counts = Counter(row.get(field) for row in books)
        if None in counts or any(v > 1 for v in counts.values()):
            errors.append({'reason': 'MISSING_OR_DUPLICATE_' + field.upper()})
    pairs = Counter(row.get('library_book_id') for row in holdings)
    if any(value > 1 for value in pairs.values()):
        errors.append({'reason': 'DUPLICATE_HOLDING'})
    for row in holdings:
        book = by_book.get(row.get('library_book_id'))
        if not book or book['library_id'] != row['library_id']:
            errors.append({'holding_id': row.get('holding_id'), 'reason': 'MISSING_OR_CROSS_LIBRARY_BOOK'})
        total, available = row.get('total_copies'), row.get('available_copies')
        if type(total) is not int or type(available) is not int or not 0 <= available <= total:
            errors.append({'holding_id': row.get('holding_id'), 'reason': 'INVALID_QUANTITIES'})
    for row in books:
        if pairs[row.get('library_book_id')] != 1:
            errors.append({'library_book_id': row.get('library_book_id'), 'reason': 'MISSING_OR_MULTIPLE_HOLDING'})
        if row.get('status') == 'PROVISIONING':
            errors.append({'library_book_id': row.get('library_book_id'), 'reason': 'INCOMPLETE_PROVISIONING'})
        if row.get('global_work_id') and not database.books.find_one({'work_id': row['global_work_id'], 'active': {'$ne': False}, 'is_active': {'$ne': False}}, {'_id': 1}):
            errors.append({'library_book_id': row.get('library_book_id'), 'reason': 'INVALID_GLOBAL_LINK'})
    barcodes = Counter(row['barcode'] for row in copies if row.get('barcode'))
    if any(v > 1 for v in barcodes.values()):
        errors.append({'reason': 'DUPLICATE_BARCODE'})
    copy_counts = Counter(row.get('holding_id') for row in copies)
    for row in copies:
        holding = by_holding.get(row.get('holding_id'))
        if not holding or row.get('library_book_id') not in by_book or holding.get('library_book_id') != row.get('library_book_id'):
            errors.append({'copy_id': row.get('copy_id'), 'reason': 'MISSING_OR_CROSS_LIBRARY_COPY_REFERENCE'})
    for holding_id, count in copy_counts.items():
        holding = by_holding.get(holding_id)
        if holding and isinstance(holding.get('total_copies'), int) and count > holding['total_copies']:
            errors.append({'holding_id': holding_id, 'reason': 'KNOWN_COPIES_EXCEED_QUANTITY'})
    sequence = database.institution_sequences.find_one({'library_id': library_id, 'sequence_type': 'BOOK_ACCESSION'})
    maximum = max((row.get('accession_sequence', 0) for row in books if isinstance(row.get('accession_sequence'), int)), default=0)
    counter = (sequence or {}).get('value', 0)
    if type(counter) is not int or counter < maximum:
        errors.append({'reason': 'SEQUENCE_BELOW_ISSUED_ACCESSIONS'})
    if sequence:
        for row in books:
            issued = row.get('accession_sequence')
            if type(issued) is not int or issued < 1 or not isinstance(sequence.get('prefix'), str) or row.get('accession_number') != f"{sequence['prefix']}-{issued:06d}":
                errors.append({'library_book_id': row.get('library_book_id'), 'reason': 'ACCESSION_FORMAT_OR_PREFIX_MISMATCH'})
    return {'status': 'PASS' if not errors else 'FAIL', 'library_id': library_id, 'books': len(books), 'holdings': len(holdings),
            'copies': len(copies), 'sequence_value': (sequence or {}).get('value', 0), 'highest_issued_sequence': maximum,
            'errors': errors, 'read_only': True}


def main():
    import argparse
    from dotenv import load_dotenv
    from pymongo import MongoClient
    load_dotenv(ROOT / '.env')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library-id', required=True)
    parser.add_argument('--database', default=os.getenv('MONGO_DB_NAME', 'luminar_library'))
    parser.add_argument('--report', type=Path)
    args = parser.parse_args(); client = MongoClient(os.getenv('MONGO_URI'), serverSelectionTimeoutMS=5000)
    try:
        result = reconcile(client[args.database], args.library_id)
        output = json.dumps(result, indent=2)
        if args.report:
            args.report.write_text(output + '\n', encoding='utf8')
        print(output)
        return 0 if result['status'] == 'PASS' else 1
    finally:
        client.close()


if __name__ == '__main__':
    raise SystemExit(main())
