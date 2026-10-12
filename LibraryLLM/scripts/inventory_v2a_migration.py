"""Read-only planning shared by the explicit legacy migration/ID assignment CLIs."""
import hashlib
import json
import os
from pathlib import Path
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.schemas.library_catalogue import BookCreate, book_payload, normalize_values
from backend.services.library_isbn_lookup import isbn_candidates
from backend.services.library_catalogue_identity import compatible
from pydantic import ValidationError

VERSION = 'inventory-v2a-1'


def mapping_input(values):
    mappings = {}
    for value in values:
        alias, separator, target = value.partition('=')
        if not separator or not alias.strip():
            raise ValueError('Aliases use LEGACY_ID=CANONICAL_UUID.')
        target = str(UUID(target.strip())); alias = alias.strip()
        mappings.setdefault(alias, set()).add(target)
    return mappings


def source_key(row):
    identity = type(row['_id']).__name__ + ':' + str(row['_id'])
    return VERSION + ':' + hashlib.sha256(('library_inventory:' + identity).encode()).hexdigest()


def plan(database, library_id, aliases=(), actor_user_id=None):
    library_id = str(UUID(library_id))
    library = database.institution_libraries.find_one({'library_id': library_id, 'status': 'ACTIVE'})
    if not library:
        raise ValueError('An explicit ACTIVE canonical library is required.')
    actor = actor_user_id or library['owner_user_id']
    member = database.institution_memberships.find_one({'library_id': library_id, 'user_id': actor, 'status': 'ACTIVE', 'role': {'$in': ['ADMIN', 'LIBRARIAN']}})
    account = database.users.find_one({'user_id': actor, 'is_active': {'$ne': False}, 'is_email_verified': True})
    if not member or not account:
        raise ValueError('Migration attribution requires an active verified library staff account.')
    mappings = mapping_input(aliases)
    for row in database.institution_library_aliases.find({}, {'_id': 0}):
        mappings.setdefault(row['legacy_library_id'], set()).add(row['canonical_library_id'])
    counts = {'records_scanned': 0, 'already_has_library_book_id': 0, 'already_has_accession': 0, 'already_migrated': 0,
              'global_work_linked': 0, 'isbn_present': 0, 'private_records_generated': 0, 'accession_numbers_generated': 0,
              'missing_title': 0, 'missing_subject': 0, 'ambiguous_library': 0, 'skipped': 0, 'errors': 0}
    rows = []
    # Cursor traversal is bounded in memory by batches; CLI report has per-row details.
    for row in database.library_inventory.find({}).batch_size(250):
        counts['records_scanned'] += 1
        counts['already_has_library_book_id'] += bool(row.get('library_book_id'))
        counts['already_has_accession'] += bool(row.get('accession_number'))
        key = source_key(row); targets = mappings.get(str(row.get('library_id', '')), set())
        item = {'source_key': key, 'legacy_library_id': row.get('library_id')}
        if len(targets) != 1:
            counts['ambiguous_library'] += 1; counts['skipped'] += 1
            rows.append({**item, 'status': 'AMBIGUOUS_LIBRARY_MAPPING'}); continue
        if library_id not in targets:
            counts['skipped'] += 1; rows.append({**item, 'status': 'OTHER_EXPLICIT_LIBRARY'}); continue
        done = database.institution_inventory_migrations.find_one({'library_id': library_id, 'source_key': key, 'complete': True})
        if done:
            counts['already_migrated'] += 1
            rows.append({**item, 'status': 'ALREADY_MIGRATED', 'library_book_id': done['library_book_id'], 'accession_number': done['accession_number']}); continue
        work_id = row.get('global_work_id') or row.get('work_id')
        global_record = database.books.find_one({'work_id': work_id, 'active': {'$ne': False}, 'is_active': {'$ne': False}}, {'_id': 0}) if work_id else None
        title = row.get('title') or (global_record or {}).get('title')
        subjects = row.get('subjects') or row.get('subject') or row.get('genre') or (global_record or {}).get('subjects')
        if not isinstance(title, str) or not title.strip():
            counts['missing_title'] += 1; counts['skipped'] += 1
            rows.append({**item, 'status': 'MISSING_REQUIRED_TITLE'}); continue
        try:
            subjects = normalize_values(subjects)
            authors = normalize_values(row.get('authors') or row.get('author') or (global_record or {}).get('authors'))
            tags = normalize_values(row.get('local_tags') or row.get('tags'))
        except ValueError as error:
            counts['errors'] += 1; counts['skipped'] += 1
            rows.append({**item, 'status': 'INVALID_METADATA', 'reason': str(error)}); continue
        if not subjects:
            counts['missing_subject'] += 1; counts['skipped'] += 1
            rows.append({**item, 'status': 'MISSING_REQUIRED_SUBJECT'}); continue
        if work_id and not global_record:
            counts['errors'] += 1; counts['skipped'] += 1
            rows.append({**item, 'status': 'UNRESOLVED_GLOBAL_LINK', 'reason': 'Remove/correct the legacy work reference explicitly before migration.'}); continue
        data = {'title': title, 'subjects': subjects, 'global_work_id': work_id or None,
                'copies': row.get('total_copies', row.get('quantity', 1)),
                'available_copies': row.get('available_copies', row.get('total_copies', row.get('quantity', 1))),
                'isbn': row.get('isbn'), 'isbn_10': row.get('isbn_10'), 'isbn_13': row.get('isbn_13'),
                'authors': authors,
                'shelf_location': row.get('shelf_location') or row.get('shelf'), 'local_call_number': row.get('local_call_number') or row.get('call_number'),
                'local_tags': tags, 'acquisition_note': row.get('acquisition_note'),
                'barcode': row.get('barcode')}
        for field in ('publisher', 'publication_year', 'edition', 'language', 'description'):
            if row.get(field) is not None:
                data[field] = row[field]
        try:
            data = book_payload(BookCreate.model_validate(data))
            if not data['global_work_id']:
                candidates = isbn_candidates([data['isbn_10'], data['isbn_13']])
                ids = set(candidates.values())
                if len(ids) == 1:
                    linked = database.books.find_one({'work_id': next(iter(ids)), 'active': {'$ne': False}, 'is_active': {'$ne': False}}, {'_id': 0})
                    if linked and compatible(data, linked):
                        data['global_work_id'] = linked['work_id']
            rows.append({**item, 'status': 'READY', 'data': data,
                         'metadata_origin': 'VERIFIED_GLOBAL_FALLBACK' if not row.get('title') or not (row.get('subjects') or row.get('subject') or row.get('genre')) else 'LEGACY_ROW'})
            counts['global_work_linked'] += bool(data['global_work_id'])
            counts['isbn_present'] += bool(data['isbn_10'] or data['isbn_13'])
        except (ValueError, ValidationError) as error:
            counts['errors'] += 1; counts['skipped'] += 1
            reason = error.errors()[0]['msg'] if isinstance(error, ValidationError) else str(error)
            rows.append({**item, 'status': 'INVALID_METADATA', 'reason': reason})
    return {'migration_version': VERSION, 'library_id': library_id, 'actor_user_id': actor,
            'aliases': {key: sorted(value) for key, value in mappings.items()}, 'counts': counts, 'rows': rows,
            'legacy_collection_preserved': True, 'circulation_migrated': False}


def apply_plan(database, proposed, existing_policy='skip'):
    os.environ['MONGO_DB_NAME'] = database.name
    # Only apply imports modules that may create legacy Mongo indexes.
    from backend.database.mongodb import db
    from backend.services.institution_repository import audit, library_mutation, now
    from backend.services.library_catalogue_repository import ensure_indexes, TenantInventory
    from backend.services.library_catalogue_service import insert_locked, add_copy_locked
    from backend.schemas.library_catalogue import CopyCreate
    if db.name != database.name:
        raise ValueError('Selected database differs from the loaded backend database; use a fresh CLI process.')
    ensure_indexes()
    library_id = proposed['library_id']; actor = proposed['actor_user_id']
    repo = TenantInventory(library_id); created = increased = existing = 0; outcomes = []
    with library_mutation(library_id, wait_seconds=30):
        from backend.services.library_inventory_access import require_library_staff
        library, _ = require_library_staff(library_id, {'sub': str(actor)}, locked=True)
        for alias, targets in proposed['aliases'].items():
            if targets == [library_id]:
                database.institution_library_aliases.update_one({'legacy_library_id': alias}, {'$setOnInsert': {
                    'legacy_library_id': alias, 'canonical_library_id': library_id, 'created_at': now(), 'created_by_user_id': actor}}, upsert=True)
                if database.institution_library_aliases.find_one({'legacy_library_id': alias})['canonical_library_id'] != library_id:
                    raise ValueError('Alias mapping changed concurrently; operator review required.')
        for item in proposed['rows']:
            if item['status'] != 'READY':
                outcomes.append({k: v for k, v in item.items() if k != 'data'}); continue
            marker = repo.one('inventory_migrations', {'source_key': item['source_key'], 'complete': True})
            if marker:
                outcomes.append({'source_key': item['source_key'], 'status': 'ALREADY_MIGRATED', 'library_book_id': marker['library_book_id']}); continue
            # One legacy source identity owns one completed marker, including explicit existing-holding policy.
            value, added = insert_locked(repo, library, item['data'], actor, source='LEGACY_MIGRATION', source_key=item['source_key'], allow_existing=True)
            if added:
                created += 1
            elif existing_policy == 'increase_quantity':
                holding = value['holding']; data = item['data']
                barcode = data.get('barcode')
                known_copy = repo.one('copies', {'barcode': barcode}) if barcode else None
                if known_copy and known_copy['library_book_id'] != value['library_book_id']:
                    raise ValueError('Legacy barcode belongs to a different library book; operator review required.')
                total = holding['total_copies'] + data['copies']
                available = holding['available_copies'] + (data['available_copies'] if data['available_copies'] is not None else data['copies'])
                if total > 1000000:
                    raise ValueError('Merged legacy quantity exceeds the supported bound.')
                repo.update('holdings', {'holding_id': holding['holding_id']}, {'total_copies': total, 'available_copies': available, 'updated_at': now(), 'updated_by_user_id': actor})
                audit(library_id, 'HOLDING_UPDATED', actor, metadata={'library_book_id': value['library_book_id'], 'holding_id': holding['holding_id'], 'counts': {'total': total, 'available_snapshot': available}})
                if barcode and not known_copy:
                    book = repo.one('library_books', {'library_book_id': value['library_book_id']})
                    add_copy_locked(repo, book, CopyCreate(barcode=barcode, status='UNVERIFIED'), actor)
                increased += 1
            else:
                existing += 1
            marker = {'source_key': item['source_key'], 'version': VERSION, 'legacy_library_id': item['legacy_library_id'],
                      'library_book_id': value['library_book_id'], 'accession_number': value['accession_number'], 'complete': True,
                      'completed_at': now(), 'created_by_user_id': actor, 'existing_policy': existing_policy,
                      'outcome': 'CREATED' if added else 'QUANTITY_INCREASED' if existing_policy == 'increase_quantity' else 'SKIPPED_EXISTING'}
            repo.insert('inventory_migrations', marker)
            audit(library_id, 'LEGACY_INVENTORY_MIGRATED', actor, metadata={'library_book_id': value['library_book_id'],
                  'accession_number': value['accession_number'], 'migration': VERSION, 'reason': marker['outcome']}, event_id=item['source_key'])
            outcomes.append({'source_key': item['source_key'], 'status': marker['outcome'], 'library_book_id': value['library_book_id'], 'accession_number': value['accession_number']})
    counts = {**proposed['counts'], 'private_records_generated': created, 'accession_numbers_generated': created,
              'created_records': created, 'increased_holdings': increased, 'skipped_existing': existing}
    return {**{k: v for k, v in proposed.items() if k not in ('rows', 'counts')}, 'mode': 'APPLY', 'counts': counts, 'rows': outcomes}


def main(description):
    import argparse
    from dotenv import load_dotenv
    from pymongo import MongoClient
    load_dotenv(ROOT / '.env')
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--library-id', required=True, type=lambda value: str(UUID(value)))
    parser.add_argument('--database', default=os.getenv('MONGO_DB_NAME', 'luminar_library'))
    parser.add_argument('--alias', action='append', default=[], help='Explicit LEGACY_ID=CANONICAL_UUID; repeat for multiple aliases.')
    parser.add_argument('--actor-user-id', type=int)
    parser.add_argument('--existing-policy', choices=['skip', 'increase_quantity'], default='skip')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    client = MongoClient(os.getenv('MONGO_URI', 'mongodb://127.0.0.1:27017'), serverSelectionTimeoutMS=5000)
    try:
        proposed = plan(client[args.database], args.library_id, args.alias, args.actor_user_id)
        result = apply_plan(client[args.database], proposed, args.existing_policy) if args.apply else {
            **{k: v for k, v in proposed.items() if k != 'rows'}, 'mode': 'DRY_RUN',
            'rows': [{k: v for k, v in row.items() if k != 'data'} for row in proposed['rows']]}
        output = json.dumps(result, indent=2, default=str)
        if args.report:
            args.report.write_text(output + '\n', encoding='utf-8')
        print(output)
    except (ValueError, ValidationError) as error:
        parser.exit(2, str(error) + '\n')
    finally:
        client.close()
