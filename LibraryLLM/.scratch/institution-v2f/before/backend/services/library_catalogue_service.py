"""Tenant catalogue and holdings; canonical lending mutations use durable journal plans."""
from datetime import timezone
import re
from uuid import uuid4
from fastapi import HTTPException
from backend.institution_dependencies import actor_id
from backend.services.library_inventory_access import require_library_membership, require_library_staff
from backend.schemas.library_catalogue import BookCreate, BOOK_FIELDS, book_payload, normalize_values, LibraryBookRecord, LibraryHolding, LibraryCopy
from backend.services.institution_repository import audit, collection, library_mutation, now, require_readable
from backend.services.library_catalogue_repository import TenantInventory
from backend.services.library_catalogue_linking import verified_work, isbn_candidates
from backend.services.library_catalogue_identity import normalized_title, compatible


BOOK_PUBLIC = ('library_book_id', 'library_id', 'accession_number', 'accession_sequence', 'global_work_id', *BOOK_FIELDS,
               'source', 'status', 'needs_review', 'created_at', 'updated_at', 'created_by_user_id', 'updated_by_user_id')
HOLDING_PUBLIC = ('holding_id', 'library_id', 'library_book_id', 'total_copies', 'available_copies', 'shelf_location',
                  'call_number', 'local_tags', 'acquisition_note', 'quantity_semantics', 'created_at', 'updated_at', 'circulation_status', 'allocation_mode', 'unavailable_stock')
COPY_PUBLIC = ('copy_id', 'library_id', 'library_book_id', 'holding_id', 'copy_number', 'barcode', 'status',
               'acquisition_date', 'created_at', 'updated_at')


def prepare_book(request, candidates=None):
    data = book_payload(request)
    work = data.get('global_work_id')
    if work:
        if not verified_work(work):
            raise HTTPException(422, 'Global catalogue link was not found. Remove the optional link to save a library record.')
        data['global_work_id'] = work.strip()
    else:
        numbers = [data.get('isbn_10'), data.get('isbn_13')]
        candidates = isbn_candidates(numbers) if candidates is None else candidates
        ids = {candidates[n] for n in numbers if n in candidates}
        if len(ids) == 1:
            candidate = verified_work(next(iter(ids)))
            if candidate and compatible(data, candidate):
                data['global_work_id'] = candidate['work_id']
        data.setdefault('global_work_id', None)
    return data


def duplicate(repo, data, *, exclude=None):
    query = {'status': 'ACTIVE'}
    if exclude:
        query['library_book_id'] = {'$ne': exclude}
    if data.get('global_work_id'):
        match = repo.one('library_books', {**query, 'global_work_id': data['global_work_id']})
        if match:
            return match, 'EXISTING_HOLDING'
    numbers = [{field: data[field]} for field in ('isbn_10', 'isbn_13') if data.get(field)]
    if numbers:
        for row in repo.rows('library_books', {**query, '$or': numbers}):
            if compatible(data, row):
                return row, 'EXISTING_HOLDING'
    match = repo.one('library_books', {**query, 'normalized_title': normalized_title(data['title'])})
    return match, 'POSSIBLE_DUPLICATE' if match else ('GLOBAL_MATCH' if data.get('global_work_id') else 'NEW_LOCAL')


def search_text(row):
    values = [row.get('title'), row.get('accession_number'), row.get('local_call_number'), row.get('isbn_10'), row.get('isbn_13')]
    values.extend(row.get('subjects') or []); values.extend(row.get('authors') or [])
    return ' '.join(str(v) for v in values if v).casefold()


def display_book(repo, row):
    holding = repo.one('holdings', {'library_book_id': row['library_book_id']})
    return {**{k: row.get(k) for k in BOOK_PUBLIC},
            'holding': {k: holding.get(k) for k in HOLDING_PUBLIC} if holding else None,
            'global_link_status': 'GLOBAL_CATALOGUE_LINKED' if row.get('global_work_id') else 'LIBRARY_RECORD'}


def required_book(repo, book_id, active=True):
    query = {'library_book_id': book_id}
    if active:
        query['status'] = 'ACTIVE'
    row = repo.one('library_books', query)
    if not row:
        raise HTTPException(404, 'Library book not found.')
    return row


def add_copy_locked(repo, book, request, actor):
    from backend.services import library_lending_journal as journal
    canonical = journal.state(repo.library_id) == 'CANONICAL'
    payload = {'library_book_id': book['library_book_id'], **request.model_dump(mode='json')}
    if canonical:
        if not request.idempotency_key:
            raise HTTPException(422, 'Canonical copy registration requires a UUID idempotency_key.')
        receipt = journal.receipt(repo.library_id, actor, request.idempotency_key, 'LIBRARY_COPY_REGISTERED', payload)
        if receipt is not None:
            return receipt
        from backend.services.library_lending_service import availability_locked
        counts = availability_locked(repo.library_id, book['library_book_id'])
        if counts['allocation_mode'] == 'COPY':
            raise HTTPException(409, 'Switch an unallocated holding to aggregate mode before registering more copies.')
        if request.status != 'AVAILABLE' and (counts['pending_holds'] + counts['active_loans'] or counts['physical_available'] < 1):
            raise HTTPException(409, 'Cannot identify unavailable units while aggregate allocations are unresolved.')
    holding = repo.one('holdings', {'library_book_id': book['library_book_id']})
    if not holding or holding['library_id'] != book['library_id']:
        raise HTTPException(409, 'Same-library holding is required.')
    if repo.count('copies', {'holding_id': holding['holding_id']}) >= holding['total_copies']:
        raise HTTPException(409, 'Known copy identities cannot exceed the holding quantity.')
    barcode = request.barcode.strip() if request.barcode else None
    if barcode and repo.one('copies', {'barcode': barcode}):
        raise HTTPException(409, 'This barcode already exists in this library.')
    ordinal = holding.get('next_copy_number', 0) + 1
    if not canonical:
        repo.update('holdings', {'holding_id': holding['holding_id']}, {'next_copy_number': ordinal})
    row = {'copy_id': str(uuid4()), 'library_id': repo.library_id, 'library_book_id': book['library_book_id'],
           'holding_id': holding['holding_id'], 'copy_number': ordinal, 'barcode': barcode, 'status': request.status,
           'acquisition_date': request.acquisition_date.isoformat() if request.acquisition_date else None, 'created_at': now(), 'updated_at': now()}
    LibraryCopy.model_validate(row)
    if canonical:
        effects = [journal.effect('holdings', {'library_id': repo.library_id, 'holding_id': holding['holding_id']}, {'next_copy_number': ordinal}),
                   journal.effect('copies', {'library_id': repo.library_id, 'copy_id': row['copy_id']}, row, True)]
        return journal.commit(repo.library_id, actor, request.idempotency_key, 'LIBRARY_COPY_REGISTERED', payload, effects, {k: row.get(k) for k in COPY_PUBLIC})
    repo.insert('copies', row)
    audit(repo.library_id, 'LIBRARY_COPY_REGISTERED', actor, metadata={'library_book_id': book['library_book_id'], 'copy_id': row['copy_id']})
    return {k: row.get(k) for k in COPY_PUBLIC}


def insert_locked(repo, library, data, actor, *, source='MANUAL', source_key=None, candidates=None, allow_existing=False, canonical_key=None, canonical_payload=None):
    if source_key:
        old = repo.one('library_books', {'source_key': source_key})
        if old:
            return display_book(repo, old), False
    # Links and duplicate identity are revalidated at commit, never inferred from title.
    data = prepare_book(BookCreate.model_validate(data), candidates)
    from backend.services.library_lending_journal import state
    canonical = state(repo.library_id) == 'CANONICAL'
    if canonical and data.get('available_copies') is not None:
        raise HTTPException(422, 'Canonical availability is derived. Specify total copies only.')
    if canonical and not canonical_key:
        from uuid import uuid5, NAMESPACE_URL
        canonical_key = str(uuid5(NAMESPACE_URL, 'luminar-inventory-import:' + source_key)) if source_key else None
        if not canonical_key:
            raise HTTPException(422, 'Canonical inventory creation requires a UUID idempotency_key.')
    match, classification = duplicate(repo, data)
    if classification == 'EXISTING_HOLDING':
        if allow_existing:
            return display_book(repo, match), False
        raise HTTPException(409, {'message': 'A matching library record already exists. Use its holding or import policy.',
                                  'library_book_id': match['library_book_id'], 'accession_number': match['accession_number']})
    if data.get('barcode') and repo.one('copies', {'barcode': data['barcode']}):
        raise HTTPException(409, 'This barcode already exists in this library.')
    sequence, accession = repo.accession(library)
    stamp = now(); book_id = str(uuid4())
    row = {k: data.get(k) for k in BOOK_FIELDS}
    row.update({'library_book_id': book_id, 'library_id': repo.library_id, 'accession_number': accession,
                'accession_sequence': sequence, 'global_work_id': data.get('global_work_id'), 'normalized_title': normalized_title(data['title']),
                'source': source, 'status': 'PROVISIONING', 'needs_review': classification == 'POSSIBLE_DUPLICATE',
                'created_at': stamp, 'updated_at': stamp, 'created_by_user_id': actor, 'updated_by_user_id': actor})
    if source_key:
        row['source_key'] = source_key
    row['search_text'] = search_text(row)
    LibraryBookRecord.model_validate(row)
    if not canonical:
        repo.insert('library_books', row)
    holding = {'holding_id': str(uuid4()), 'library_id': repo.library_id, 'library_book_id': book_id,
               'total_copies': data['copies'], 'available_copies': data['available_copies'] if data['available_copies'] is not None else data['copies'],
               'shelf_location': data.get('shelf_location'), 'call_number': data.get('local_call_number'), 'local_tags': data.get('local_tags', []),
               'acquisition_note': data.get('acquisition_note'), 'quantity_semantics': 'INVENTORY_SNAPSHOT_NOT_CIRCULATION',
               'created_at': stamp, 'updated_at': stamp, 'created_by_user_id': actor, 'updated_by_user_id': actor}
    holding['circulation_status'] = data.get('circulation_status', 'CIRCULATING')
    if canonical:
        holding.update({'allocation_mode': 'AGGREGATE', 'unavailable_stock': 0})
    LibraryHolding.model_validate(holding)
    if canonical:
        from backend.services import library_lending_journal as journal
        row['status'] = 'ACTIVE'; holding['quantity_semantics'] = 'CANONICAL_CIRCULATION'
        effects = [journal.effect('library_books', {'library_id': repo.library_id, 'library_book_id': book_id}, row, True),
                   journal.effect('holdings', {'library_id': repo.library_id, 'holding_id': holding['holding_id']}, holding, True)]
        if data.get('barcode'):
            copy = {'library_id': repo.library_id, 'library_book_id': book_id, 'holding_id': holding['holding_id'], 'copy_id': str(uuid4()),
                    'copy_number': 1, 'barcode': data['barcode'], 'status': 'AVAILABLE', 'created_at': stamp, 'updated_at': stamp}
            holding['next_copy_number'] = 1
            effects.append(journal.effect('copies', {'library_id': repo.library_id, 'copy_id': copy['copy_id']}, copy, True))
        result = {**{k: row.get(k) for k in BOOK_PUBLIC}, 'holding': {k: holding.get(k) for k in HOLDING_PUBLIC},
                  'global_link_status': 'GLOBAL_CATALOGUE_LINKED' if row.get('global_work_id') else 'LIBRARY_RECORD'}
        journal.commit(repo.library_id, actor, canonical_key, 'LIBRARY_BOOK_CREATED', canonical_payload or data, effects, result)
        return result, True
    repo.insert('holdings', holding)
    if data.get('barcode'):
        from backend.schemas.library_catalogue import CopyCreate
        add_copy_locked(repo, row, CopyCreate(barcode=data['barcode'], status='UNVERIFIED' if source == 'LEGACY_MIGRATION' else 'AVAILABLE'), actor)
    metadata = {'library_book_id': book_id, 'accession_number': accession, 'global_work_id': row['global_work_id'], 'holding_id': holding['holding_id']}
    audit(repo.library_id, 'LIBRARY_BOOK_CREATED', actor, metadata=metadata)
    audit(repo.library_id, 'HOLDING_CREATED', actor, metadata={**metadata, 'counts': {'total': holding['total_copies'], 'available_snapshot': holding['available_copies']}})
    repo.update('library_books', {'library_book_id': book_id}, {'status': 'ACTIVE'})
    row['status'] = 'ACTIVE'
    return display_book(repo, row), True


def create_book(library_id, request, current_user):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        library, _ = require_library_staff(library_id, current_user, locked=True)
        from backend.services import library_lending_journal as journal
        if journal.state(library_id) == 'CANONICAL':
            if not request.idempotency_key:
                raise HTTPException(422, 'Canonical creation requires a UUID idempotency_key.')
            old = journal.receipt(library_id, actor_id(current_user), request.idempotency_key, 'LIBRARY_BOOK_CREATED', request.model_dump(mode='json'))
            if old is not None:
                return old
        data = prepare_book(request)
        result, _ = insert_locked(TenantInventory(library_id), library, data, actor_id(current_user), canonical_key=request.idempotency_key, canonical_payload=request.model_dump(mode='json'))
    return result


def list_books(library_id, current_user, *, search='', kind='all', state='active', offset=0, limit=20, _locked=False):
    from backend.services import library_lending_service as lending
    canonical = lending.journal.state(library_id) == 'CANONICAL'
    if canonical and not _locked:
        with library_mutation(library_id, wait_seconds=30, durable=True):
            lending.access_locked(library_id, current_user)
            return list_books(library_id, current_user, search=search, kind=kind, state=state, offset=offset, limit=limit, _locked=True)
    library, membership = require_library_membership(library_id, current_user, locked=_locked)
    repo = TenantInventory(library_id); query = {}
    if state != 'all':
        query['status'] = 'ACTIVE' if state == 'active' else 'WITHDRAWN'
    else:
        query['status'] = {'$in': ['ACTIVE', 'WITHDRAWN']}
    if search:
        query['search_text'] = {'$regex': re.escape(search.strip().casefold())}
    if kind == 'local':
        query['global_work_id'] = None
    elif kind == 'global':
        query['global_work_id'] = {'$type': 'string'}
    elif kind == 'review':
        query['needs_review'] = True
    total = repo.count('library_books', query)
    rows = list(repo.rows('library_books', query).sort('accession_sequence', -1).skip(offset).limit(limit))
    holdings = {h['library_book_id']: h for h in repo.rows('holdings', {'library_book_id': {'$in': [r['library_book_id'] for r in rows]}})}
    result = [{**{k: r.get(k) for k in BOOK_PUBLIC}, 'holding': {k: holdings[r['library_book_id']].get(k) for k in HOLDING_PUBLIC} if r['library_book_id'] in holdings else None,
               'global_link_status': 'GLOBAL_CATALOGUE_LINKED' if r.get('global_work_id') else 'LIBRARY_RECORD'} for r in rows]
    if canonical:
        from backend.services.library_catalogue_experience import hydrate
        if any(item['holding'] is None for item in result):
            raise HTTPException(404, 'Library book holding not found.')
        hydrated = hydrate(library_id, current_user, result, True)
        for item, display in zip(result, hydrated):
            item['availability'] = display['availability']
            item['holding']['available_copies'] = item['availability']['requestable']
            item['holding']['quantity_semantics'] = 'CANONICAL_CIRCULATION'
    if not _locked:
        require_readable(library_id)
    return {'results': result, 'total': total, 'offset': offset, 'limit': limit, 'has_more': offset + len(result) < total,
            'library': {'library_id': library_id, 'name': library['name'], 'accession_prefix': library.get('accession_prefix')}, 'role': membership['role'],
            'quantity_semantics': 'CANONICAL_CIRCULATION' if canonical else 'INVENTORY_SNAPSHOT_NOT_CIRCULATION', 'lending_state': lending.journal.state(library_id)}


def get_book(library_id, book_id, current_user, _locked=False):
    from backend.services import library_lending_service as lending
    canonical = lending.journal.state(library_id) == 'CANONICAL'
    if canonical and not _locked:
        with library_mutation(library_id, wait_seconds=30, durable=True):
            lending.access_locked(library_id, current_user)
            return get_book(library_id, book_id, current_user, _locked=True)
    require_library_membership(library_id, current_user, locked=_locked)
    repo = TenantInventory(library_id)
    result = display_book(repo, required_book(repo, book_id, active=False))
    if canonical:
        result['availability'] = lending.availability_locked(library_id, book_id)
        result['holding']['available_copies'] = result['availability']['requestable']
        result['holding']['quantity_semantics'] = 'CANONICAL_CIRCULATION'
    if not _locked:
        require_readable(library_id)
    return result


def update_book(library_id, book_id, request, current_user):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        require_library_staff(library_id, current_user, locked=True)
        repo = TenantInventory(library_id); old = required_book(repo, book_id)
        patch = request.model_dump(exclude_unset=True)
        key = patch.pop('idempotency_key', None)
        from backend.services import library_lending_journal as journal
        canonical = journal.state(library_id) == 'CANONICAL'
        payload = {'library_book_id': book_id, **request.model_dump(mode='json', exclude_unset=True)}
        if canonical:
            if not key:
                raise HTTPException(422, 'Canonical metadata update requires a UUID idempotency_key.')
            receipt = journal.receipt(library_id, actor_id(current_user), key, 'LIBRARY_BOOK_UPDATED', payload)
            if receipt is not None:
                return receipt
        if not patch:
            raise HTTPException(422, 'Choose metadata to update.')
        if 'isbn' in patch:
            isbn = patch.pop('isbn')
            if isbn is None:
                patch.update({'isbn_10': None, 'isbn_13': None})
            else:
                patch.update({'isbn_10': None, 'isbn_13': None})
                patch['isbn_10' if len(isbn) == 10 else 'isbn_13'] = isbn
        combined = {k: old.get(k) for k in BOOK_FIELDS}
        combined.update(patch)
        validated = book_payload(BookCreate.model_validate(combined))
        match, classification = duplicate(repo, {**validated, 'global_work_id': old.get('global_work_id')}, exclude=book_id)
        if classification == 'EXISTING_HOLDING':
            raise HTTPException(409, 'Metadata would conflict with another matching library record.')
        values = {k: validated.get(k) for k in BOOK_FIELDS}
        values.update({'normalized_title': normalized_title(values['title']), 'updated_at': now(), 'updated_by_user_id': actor_id(current_user), 'needs_review': classification == 'POSSIBLE_DUPLICATE'})
        values['search_text'] = search_text({**old, **values})
        if canonical:
            holding = repo.one('holdings', {'library_book_id': book_id})
            hpatch = {'shelf_location': values['shelf_location'], 'call_number': values['local_call_number'], 'local_tags': values['local_tags'], 'acquisition_note': values['acquisition_note'], 'updated_at': now()}
            effects = [journal.effect('library_books', {'library_id': library_id, 'library_book_id': book_id}, values),
                       journal.effect('holdings', {'library_id': library_id, 'holding_id': holding['holding_id']}, hpatch)]
            result = {**{k: {**old, **values}.get(k) for k in BOOK_PUBLIC}, 'holding': {k: {**holding, **hpatch}.get(k) for k in HOLDING_PUBLIC}, 'global_link_status': 'GLOBAL_CATALOGUE_LINKED' if old.get('global_work_id') else 'LIBRARY_RECORD'}
            if old.get('shelf_location') != values['shelf_location'] or old.get('local_call_number') != values['local_call_number']:
                event_id = str(uuid4())
                effects.append(journal.effect('audit', {'library_id': library_id, 'event_id': event_id}, {'event_id': event_id, 'library_id': library_id, 'actor_user_id': actor_id(current_user), 'event': 'SHELF_UPDATED', 'metadata': {'library_book_id': book_id, 'holding_id': holding['holding_id']}, 'created_at': now()}, True))
            return journal.commit(library_id, actor_id(current_user), key, 'LIBRARY_BOOK_UPDATED', payload, effects, result)
        repo.update('library_books', {'library_book_id': book_id}, values)
        repo.update('holdings', {'library_book_id': book_id}, {'shelf_location': values['shelf_location'], 'call_number': values['local_call_number'],
                    'local_tags': values['local_tags'], 'acquisition_note': values['acquisition_note'], 'updated_at': now(), 'updated_by_user_id': actor_id(current_user)})
        audit(library_id, 'LIBRARY_BOOK_UPDATED', actor_id(current_user), metadata={'library_book_id': book_id, 'accession_number': old['accession_number']})
        result = display_book(repo, required_book(repo, book_id))
    return result


def update_holding(library_id, book_id, request, current_user):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        require_library_staff(library_id, current_user, locked=True)
        from backend.services.library_lending_journal import state
        if state(library_id) == 'CANONICAL':
            raise HTTPException(409, 'Use canonical Manage Stock; requestable availability cannot be overridden.')
        repo = TenantInventory(library_id); required_book(repo, book_id)
        if repo.count('copies', {'library_book_id': book_id}) > request.total_copies:
            raise HTTPException(409, 'Quantity cannot be below the number of registered copy identities.')
        if not repo.one('holdings', {'library_book_id': book_id}):
            raise HTTPException(404, 'Holding not found.')
        repo.update('holdings', {'library_book_id': book_id}, {**request.model_dump(), 'updated_at': now(), 'updated_by_user_id': actor_id(current_user)})
        audit(library_id, 'HOLDING_UPDATED', actor_id(current_user), metadata={'library_book_id': book_id, 'counts': {'total': request.total_copies, 'available_snapshot': request.available_copies}})
        result = display_book(repo, required_book(repo, book_id))
    return result


def link_global(library_id, book_id, request, current_user):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        require_library_staff(library_id, current_user, locked=True)
        repo = TenantInventory(library_id); row = required_book(repo, book_id)
        from backend.services import library_lending_journal as journal
        canonical = journal.state(library_id) == 'CANONICAL'
        payload = {'library_book_id': book_id, **request.model_dump(mode='json')}
        if canonical:
            if not request.idempotency_key:
                raise HTTPException(422, 'Canonical link updates require a UUID idempotency_key.')
            receipt = journal.receipt(library_id, actor_id(current_user), request.idempotency_key, 'LIBRARY_BOOK_GLOBAL_LINKED', payload)
            if receipt is not None:
                return receipt
        work = request.global_work_id.strip() if request.global_work_id else None
        if request.global_work_id is not None and not verified_work(work):
            raise HTTPException(422, 'Global catalogue link was not found.')
        if work and repo.one('library_books', {'status': 'ACTIVE', 'global_work_id': work, 'library_book_id': {'$ne': book_id}}):
            raise HTTPException(409, 'That work is already linked to another library record.')
        if canonical:
            result = display_book(repo, {**row, 'global_work_id': work})
            return journal.commit(library_id, actor_id(current_user), request.idempotency_key, 'LIBRARY_BOOK_GLOBAL_LINKED', payload,
                [journal.effect('library_books', {'library_id': library_id, 'library_book_id': book_id}, {'global_work_id': work, 'updated_at': now()})], result)
        repo.update('library_books', {'library_book_id': book_id}, {'global_work_id': work, 'updated_at': now(), 'updated_by_user_id': actor_id(current_user)})
        audit(library_id, 'LIBRARY_BOOK_GLOBAL_LINKED' if work else 'LIBRARY_BOOK_GLOBAL_UNLINKED', actor_id(current_user),
              metadata={'library_book_id': book_id, 'accession_number': row['accession_number'], 'global_work_id': work})
        result = display_book(repo, required_book(repo, book_id))
    return result


def withdraw(library_id, book_id, current_user, idempotency_key=None):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        require_library_staff(library_id, current_user, locked=True)
        repo = TenantInventory(library_id); row = required_book(repo, book_id, active=False)
        from backend.services import library_lending_journal as journal
        if journal.state(library_id) == 'CANONICAL':
            if not idempotency_key:
                raise HTTPException(422, 'Canonical withdrawal requires UUID Idempotency-Key header.')
            payload = {'library_book_id': book_id}
            receipt = journal.receipt(library_id, actor_id(current_user), idempotency_key, 'LIBRARY_BOOK_WITHDRAWN', payload)
            if receipt is not None:
                return receipt
            return journal.commit(library_id, actor_id(current_user), idempotency_key, 'LIBRARY_BOOK_WITHDRAWN', payload,
                [journal.effect('library_books', {'library_id': library_id, 'library_book_id': book_id}, {'status': 'WITHDRAWN', 'updated_at': now()}),
                 journal.effect('holdings', {'library_id': library_id, 'library_book_id': book_id}, {'circulation_status': 'WITHDRAWN', 'updated_at': now()})],
                {'status': 'WITHDRAWN', 'library_book_id': book_id, 'accession_number': row['accession_number']})
        if row['status'] != 'WITHDRAWN':
            repo.update('library_books', {'library_book_id': book_id}, {'status': 'WITHDRAWN', 'updated_at': now(), 'updated_by_user_id': actor_id(current_user)})
            audit(library_id, 'LIBRARY_BOOK_WITHDRAWN', actor_id(current_user), metadata={'library_book_id': book_id, 'accession_number': row['accession_number']})
    return {'status': 'WITHDRAWN', 'library_book_id': book_id, 'accession_number': row['accession_number']}


def copies(library_id, book_id, current_user, offset=0, limit=100):
    require_library_membership(library_id, current_user)
    repo = TenantInventory(library_id); required_book(repo, book_id, active=False)
    query = {'library_book_id': book_id}
    total = repo.count('copies', query)
    rows = [{k: r.get(k) for k in COPY_PUBLIC} for r in repo.rows('copies', query).sort('copy_number', 1).skip(offset).limit(limit)]
    require_readable(library_id)
    return {'results': rows, 'total': total, 'offset': offset, 'limit': limit, 'has_more': offset + len(rows) < total}


def create_copy(library_id, book_id, request, current_user):
    with library_mutation(library_id, wait_seconds=30, durable=True):
        require_library_staff(library_id, current_user, locked=True)
        repo = TenantInventory(library_id); row = required_book(repo, book_id)
        result = add_copy_locked(repo, row, request, actor_id(current_user))
    return result
