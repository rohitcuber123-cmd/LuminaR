"""Narrow tenant-required repository; no default library and no global inventory writes."""
from uuid import UUID
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from backend.services.institution_repository import collection, now


def ensure_indexes():
    specs = {
        'library_books': [([('library_book_id', 1)], {'unique': True}),
            ([('library_id', 1), ('accession_number', 1)], {'unique': True}),
            ([('library_id', 1), ('accession_sequence', 1)], {'unique': True}),
            ([('library_id', 1), ('global_work_id', 1)], {'partialFilterExpression': {'global_work_id': {'$type': 'string'}}}),
            ([('library_id', 1), ('isbn_13', 1)], {'partialFilterExpression': {'isbn_13': {'$type': 'string'}}}),
            ([('library_id', 1), ('isbn_10', 1)], {'partialFilterExpression': {'isbn_10': {'$type': 'string'}}}),
            ([('library_id', 1), ('normalized_title', 1)], {}),
            ([('library_id', 1), ('status', 1), ('accession_sequence', 1)], {}),
            ([('library_id', 1), ('source_key', 1)], {'unique': True, 'partialFilterExpression': {'source_key': {'$type': 'string'}}})],
        'holdings': [([('holding_id', 1)], {'unique': True}), ([('library_id', 1), ('library_book_id', 1)], {'unique': True})],
        'copies': [([('copy_id', 1)], {'unique': True}), ([('library_id', 1), ('library_book_id', 1)], {}),
            ([('library_id', 1), ('barcode', 1)], {'unique': True, 'partialFilterExpression': {'barcode': {'$type': 'string'}}}),
            ([('library_id', 1), ('holding_id', 1), ('copy_number', 1)], {'unique': True})],
        'sequences': [([('library_id', 1), ('sequence_type', 1)], {'unique': True})],
        'library_aliases': [([('legacy_library_id', 1)], {'unique': True})],
        'inventory_imports': [([('import_id', 1)], {'unique': True}), ([('library_id', 1), ('actor_user_id', 1), ('created_at', -1)], {})],
        'inventory_previews': [([('import_id', 1)], {'unique': True}), ([('expires_at', 1)], {'expireAfterSeconds': 0})],
        'inventory_migrations': [([('library_id', 1), ('source_key', 1)], {'unique': True})],
    }
    for name, entries in specs.items():
        target = collection(name)
        old = list(target.list_indexes()) if target.name in target.database.list_collection_names() else []
        for keys, options in entries:
            same = [index for index in old if list(index['key'].items()) == keys]
            if same:
                if not any(all(index.get(k) == v for k, v in options.items()) for index in same):
                    raise RuntimeError('Inventory index requires operator review: ' + name)
            else:
                target.create_index(keys, **options)


class TenantInventory:
    def __init__(self, library_id):
        self.library_id = str(UUID(str(library_id)))

    def scope(self, query=None):
        query = dict(query or {})
        if 'library_id' in query and query['library_id'] != self.library_id:
            raise ValueError('Cross-library repository predicate rejected.')
        return {**query, 'library_id': self.library_id}

    def one(self, name, query=None, projection=None):
        return collection(name).find_one(self.scope(query), projection)

    def rows(self, name, query=None):
        return collection(name).find(self.scope(query), {'_id': 0})

    def count(self, name, query=None):
        return collection(name).count_documents(self.scope(query))

    def insert(self, name, document):
        collection(name).insert_one(self.scope(document))

    def update(self, name, query, values):
        if 'library_id' in values and values['library_id'] != self.library_id:
            raise ValueError('Cannot change tenant identity.')
        return collection(name).update_one(self.scope(query), {'$set': values})

    def accession(self, library):
        import re
        prefix = library.get('accession_prefix') or (re.sub(r'[^A-Z0-9]', '', library['name'].upper())[:3] or 'LIB')
        query = self.scope({'sequence_type': 'BOOK_ACCESSION'})
        change = {'$inc': {'value': 1}, '$setOnInsert': {'prefix': prefix, 'created_at': now()}}
        try:
            sequence = collection('sequences').find_one_and_update(query, change, upsert=True, return_document=ReturnDocument.AFTER)
        except DuplicateKeyError:
            sequence = collection('sequences').find_one_and_update(query, {'$inc': {'value': 1}}, return_document=ReturnDocument.AFTER)
        collection('libraries').update_one({'library_id': self.library_id, 'accession_prefix': {'$exists': False}}, {'$set': {'accession_prefix': sequence['prefix']}})
        return sequence['value'], f"{sequence['prefix']}-{sequence['value']:06d}"
