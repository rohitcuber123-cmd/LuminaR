"""Audit historical documents without inferring library ownership.

This phase supplies a dry-run mapping validator, never a production importer.
Actual transfer requires a future reviewed migration with explicit source-owner
consent and canonical destination authorization; personal originals are untouched.
"""
import argparse
import json
import sqlite3
import sys
import re
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.database.mongodb import db


def inspect_mappings(mappings):
    result = []
    for entry in mappings:
        source_id = str(entry.get('source_id', ''))[:200]
        try:
            library_id = str(UUID(str(entry.get('library_id', ''))))
            evidence = str(entry.get('ownership_evidence', '')).strip()
            owner_consent = entry.get('source_owner_consent') is True
            library = db.institution_libraries.find_one({'library_id': library_id, 'status': 'ACTIVE'}, {'library_id': 1})
            valid = bool(source_id and library and evidence and len(evidence) <= 1000 and owner_consent)
        except (ValueError, TypeError):
            library_id, valid = None, False
        result.append({'source_id': source_id, 'library_id': library_id,
            'classification': 'EXPLICIT_MAPPING_REVIEW_REQUIRED' if valid else 'AMBIGUOUS_DOCUMENT_OWNERSHIP',
            'eligible_for_review': valid, 'applied': False})
    return result


def audit_documents(mappings=None):
    rows = []
    # Collection names alone do not prove ownership; only accepted personal IDs do.
    for name in db.list_collection_names():
        if name == 'institution_library_assets' or not any(word in name.lower() for word in ('document', 'upload', 'rag')):
            continue
        for row in db[name].find({}, {'document_id': 1, 'owner_user_id': 1, 'owner_session_id': 1,
                                   'library_id': 1, 'asset_id': 1}).limit(10000):
            document_id = row.get('document_id')
            personal = bool(document_id and str(document_id).startswith('doc_') and row.get('owner_user_id') and row.get('owner_session_id'))
            rows.append({'source_collection': name, 'source_id': str(document_id or row['_id']),
                'classification': 'PERSONAL_PRIVATE' if personal else 'AMBIGUOUS_DOCUMENT_OWNERSHIP', 'applied': False})
    personal_root = Path(__file__).resolve().parents[1] / 'rag' / 'private_documents'
    # Existing personal registry roots may be operator-configured. Only inventory;
    # do not copy PDFs or extracted text and never use membership to assign them.
    import os
    configured = os.getenv('RAG_PRIVATE_DOCUMENT_ROOT')
    registry = Path(configured) / 'registry.sqlite' if configured else personal_root / 'registry.sqlite'
    if registry.is_file():
        uri = registry.resolve().as_uri() + '?mode=ro'
        with sqlite3.connect(uri, uri=True) as conn:
            for row in conn.execute('SELECT id FROM documents LIMIT 10000'):
                rows.append({'source_collection': 'personal_session_registry', 'source_id': row[0],
                    'classification': 'PERSONAL_PRIVATE', 'applied': False})
    rag_root = Path(__file__).resolve().parents[1] / 'rag'
    historical_storage = []
    for family in ('documents', 'extracted', 'chunks', 'index', 'book_chunks', 'book_embeddings', 'book_index'):
        directory = rag_root / family
        if not directory.is_dir():
            continue
        count = 0
        classifications = {'BOOK_RAG': 0, 'LEGACY_AMBIGUOUS': 0}
        for path in directory.rglob('*'):
            if path.is_file():
                count += 1
                # Permanent per-work family is already Book RAG; other flat files
                # lack canonical tenant ownership regardless of uploader membership.
                known_book = family.startswith('book_') and re.fullmatch(r'OL\d+W', path.stem)
                classifications['BOOK_RAG' if known_book else 'LEGACY_AMBIGUOUS'] += 1
        historical_storage.append({'family': family, 'files': count, 'classifications': classifications,
            'ownership_inferred': False, 'files_modified': 0})
    return {'mode': 'DRY_RUN', 'documents': rows, 'explicit_mappings': inspect_mappings(mappings or []),
        'historical_storage': historical_storage,
        'automatic_library_assignments': 0, 'personal_documents_modified': 0,
        'apply_supported': False, 'reason': 'Historical source ownership requires review; no production auto-apply.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping', type=Path, help='JSON list with source_id, library_id, ownership_evidence and source_owner_consent.')
    parser.add_argument('--output', type=Path)
    options = parser.parse_args()
    mappings = json.loads(options.mapping.read_text(encoding='utf-8')) if options.mapping else []
    if not isinstance(mappings, list) or len(mappings) > 1000:
        raise SystemExit('Mappings must be a JSON list containing at most 1,000 reviewed entries.')
    body = json.dumps(audit_documents(mappings), indent=2, default=str)
    if options.output:
        options.output.write_text(body + '\n', encoding='utf-8')
    else:
        print(body)


if __name__ == '__main__':
    main()
