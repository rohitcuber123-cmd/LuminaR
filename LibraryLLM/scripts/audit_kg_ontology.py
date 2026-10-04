"""Full read-only catalogue audit with bounded batches and disk-backed degrees."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from knowledge_graph.core import canonical, terms

FIELDS = ['series', 'series_name', 'publisher', 'publishers', 'language', 'languages',
          'first_publish_date', 'first_publish_year', 'publication_year', 'publication_date',
          'publish_date', 'genre', 'genres', 'format', 'type', 'edition_of', 'editions',
          'isbn', 'isbn_10', 'isbn_13', 'classifications', 'dewey_decimal_class',
          'lc_classifications', 'description', 'shelf_location', 'created_at']


def main():
    reports = ROOT / 'reports'
    target = reports / 'kg_ontology_enrichment_audit.json'
    database = reports / 'kg31_audit.sqlite'
    assert not target.exists() and not database.exists(), 'Preserve existing audit evidence'
    # Freeze current source/evaluation evidence without duplicating the 5.87GB artifact.
    baseline = {}
    for folder in ['knowledge_graph', 'assistant', 'backend', 'frontend/src', 'frontend/tests', 'tests', 'recommendation', 'search', 'rag']:
        for path in (ROOT / folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix in {'.py', '.tsx', '.ts', '.md'}:
                baseline[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ['kg3_evaluation.json', 'kg3_seeds.json', 'kg1_kg2_build.json', 'knowledge_graph_final.json']:
        path = reports / name
        baseline[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    started = time.perf_counter()
    graph_path = ROOT / 'knowledge_graph/data/catalogue.sqlite'
    graph_hash = hashlib.sha256()
    with graph_path.open('rb') as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            graph_hash.update(chunk)
    frozen = {'created_at': datetime.now(timezone.utc).isoformat(), 'files': baseline,
              'v1_artifact': {'path': str(graph_path), 'bytes': graph_path.stat().st_size, 'sha256': graph_hash.hexdigest()}}
    if not (reports / 'kg31_baseline.json').exists():
        (reports / 'kg31_baseline.json').write_text(json.dumps(frozen, indent=2), encoding='utf-8')
    from backend.database.mongodb import books_collection
    db = sqlite3.connect(database)
    db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; CREATE TABLE degrees(field TEXT, value TEXT, degree INTEGER, PRIMARY KEY(field,value));')
    keys = Counter(); nonnull = Counter(); types = defaultdict(Counter); lengths = Counter()
    pending = Counter(); examples = defaultdict(list)
    description_stats = Counter()
    count = 0
    def flush():
        db.executemany('INSERT INTO degrees VALUES(?,?,?) ON CONFLICT(field,value) DO UPDATE SET degree=degree+excluded.degree',
                       [(field, value, degree) for (field, value), degree in pending.items()])
        db.commit(); pending.clear()
    for row in books_collection.find({}, {'_id': 0}).batch_size(2000):
        count += 1; keys.update(row.keys())
        for field in FIELDS:
            value = row.get(field)
            if value is None or value == '' or value == [] or value == {}:
                continue
            nonnull[field] += 1; types[field][type(value).__name__] += 1
            if field == 'description':
                if not isinstance(value, str):
                    description_stats['unsupported_type'] += 1; continue
                text = canonical(value); tokens = re.findall(r'\w+', text)
                lengths[len(tokens)] += 1
                description_stats['empty_whitespace'] += not bool(text)
                boilerplate = text in {'no description', 'no description available', 'none', 'null', 'n/a', 'not available'}
                description_stats['boilerplate_exact'] += boilerplate
                description_stats['very_short_under_20_tokens'] += len(tokens) < 20
                description_stats['usable_at_least_20_tokens'] += len(tokens) >= 20 and not boilerplate
                description_stats['html_or_markup'] += bool(re.search(r'<[^>]+>|\[[^\]]+\]\([^)]*\)|\*\*|#{1,6}\s', value))
                if text:
                    pending[(field, hashlib.sha256(text.encode()).hexdigest())] += 1
                if len(examples[field]) < 6:
                    examples[field].append({'work_id': row['work_id'], 'tokens': len(tokens), 'excerpt': value[:240]})
            else:
                if isinstance(value, (str, list, tuple)):
                    values = list(terms(value))
                elif isinstance(value, (int, float)):
                    values = [str(value)]
                else:
                    values = [json.dumps(value, sort_keys=True, default=str)]
                for item in set(values):
                    pending[(field, item)] += 1
                if len(examples[field]) < 3:
                    examples[field].append({'work_id': row['work_id'], 'value': value})
        if count % 2000 == 0:
            flush()
        if count % 100000 == 0:
            progress = {'books': count, 'seconds': time.perf_counter()-started, 'observed_keys': sorted(keys)}
            (reports / 'kg31_audit_progress.json').write_text(json.dumps(progress), encoding='utf-8')
            print(json.dumps(progress), flush=True)
    flush()
    def quantile(values, p):
        total = sum(values.values())
        rank = max(1, math.ceil(total*p)); seen = 0
        for value, number in sorted(values.items()):
            seen += number
            if seen >= rank:
                return value
        return None
    result = {'created_at': datetime.now(timezone.utc).isoformat(), 'books_scanned': count, 'scope': 'full catalogue',
              'observed_field_counts': dict(keys), 'fields': {}, 'description': dict(description_stats),
              'description_token_lengths': {key: quantile(lengths, p) for key, p in [('median',.5),('p90',.9),('p99',.99),('maximum',1)]},
              'description_language': 'Cannot determine from missing structured language metadata; non-English rate unknown, not guessed.',
              'examples': dict(examples), 'audit_seconds': time.perf_counter()-started,
              'disk_free_bytes': shutil.disk_usage(ROOT).free}
    for field in FIELDS:
        distribution = Counter(dict(db.execute('SELECT degree,COUNT(*) FROM degrees WHERE field=? GROUP BY degree', (field,))))
        unique = sum(distribution.values())
        result['fields'][field] = {'non_null_count': nonnull[field], 'coverage_percent': nonnull[field]/count*100,
                                  'unique_normalized_value_count': unique, 'value_types': dict(types[field]),
                                  'degree': {key: quantile(distribution, p) for key,p in [('median',.5),('p90',.9),('p99',.99),('largest',1)]}}
    unique_descriptions = result['fields']['description']['unique_normalized_value_count']
    descriptions = db.execute("SELECT COALESCE(SUM(degree),0),COUNT(*) FROM degrees WHERE field='description' AND degree>1").fetchone()
    result['description'].update(unique_normalized_descriptions=unique_descriptions,
                                 duplicate_groups=descriptions[1], books_in_duplicate_groups=descriptions[0],
                                 excess_duplicate_books=db.execute("SELECT COALESCE(SUM(degree-1),0) FROM degrees WHERE field='description'").fetchone()[0])
    db.close()
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    print(json.dumps({'complete': True, 'books': count, 'description': result['description'], 'seconds': result['audit_seconds']}), flush=True)


if __name__ == '__main__':
    main()
