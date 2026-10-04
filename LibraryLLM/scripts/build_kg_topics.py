"""Add bounded deterministic source phrases to a separately versioned graph."""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from knowledge_graph.core import CatalogueGraph
from knowledge_graph.relations import RELATION_WEIGHTS, TOPIC_POLICY, V2_VERSION
from knowledge_graph.topics import phrases, choose_topics, description_hash


def enrich(source, output, rows, scope='pilot', vocabulary_source=None):
    """rows is a callable that yields the same frozen source on both passes."""
    output = Path(output)
    temporary = output.with_suffix('.building.sqlite')
    compacted = output.with_suffix('.ready.sqlite')
    if any(path.exists() for path in [output, temporary, compacted]):
        raise FileExistsError('Refusing to overwrite a versioned graph/build')
    started = time.perf_counter()
    shutil.copyfile(source, temporary)
    db = sqlite3.connect(temporary,uri=True)
    db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA temp_store=FILE; PRAGMA cache_size=-131072; ALTER TABLE books ADD COLUMN description_hash TEXT; ALTER TABLE edges ADD COLUMN source_hash TEXT; CREATE TABLE phrase_documents(phrase TEXT,book_id INTEGER);')
    meta = CatalogueGraph(source).meta(); size = meta['books']
    maximum = max(TOPIC_POLICY['min_degree'], int(size*TOPIC_POLICY['maximum_degree_fraction']))
    batch, hashes = [], []; described = 0
    for number, row in enumerate(rows(), 1):
        record = db.execute('SELECT id FROM books WHERE work_id=?', (row['work_id'],)).fetchone()
        if record is None:
            continue
        book_id = record[0]
        extracted = phrases(row.get('description'))
        described += bool(extracted)
        batch.extend((phrase, book_id) for phrase in extracted)
        hashes.append((description_hash(row.get('description')), book_id))
        if number % 2000 == 0:
            db.executemany('INSERT INTO phrase_documents VALUES(?,?)', batch)
            db.executemany('UPDATE books SET description_hash=? WHERE id=?', hashes)
            db.commit(); batch.clear(); hashes.clear()
        if number % 50000 == 0:
            print(json.dumps({'stage':'phrase degrees','books':number,'seconds':time.perf_counter()-started}), flush=True)
    db.executemany('INSERT INTO phrase_documents VALUES(?,?)', batch)
    db.executemany('UPDATE books SET description_hash=? WHERE id=?', hashes); db.commit()
    db.executescript('CREATE INDEX phrase_documents_term ON phrase_documents(phrase); CREATE TABLE topic_degrees(phrase TEXT PRIMARY KEY,degree INTEGER);')
    db.execute('INSERT INTO topic_degrees SELECT phrase,COUNT(*) FROM phrase_documents GROUP BY phrase HAVING COUNT(*)>=? AND COUNT(*)<=?', (TOPIC_POLICY['min_degree'], maximum))
    if vocabulary_source is not None:
        # A global catalogue vocabulary constraint, not a list fitted to seeds.
        db.execute('ATTACH DATABASE ? AS vocabulary', (Path(vocabulary_source).resolve().as_uri()+'?mode=ro',))
        db.execute("DELETE FROM topic_degrees WHERE NOT EXISTS (SELECT 1 FROM vocabulary.features f WHERE f.kind='subject' AND f.term=topic_degrees.phrase)")
        db.commit()
        db.execute('DETACH DATABASE vocabulary')
    db.commit()
    batch = []
    for number, row in enumerate(rows(), 1):
        extracted = phrases(row.get('description'))
        if extracted:
            record = db.execute('SELECT id,description_hash FROM books WHERE work_id=?', (row['work_id'],)).fetchone()
            if record is not None:
                degrees = dict(db.execute('SELECT phrase,degree FROM topic_degrees WHERE phrase IN ('+','.join('?' for _ in extracted)+')', list(extracted)))
                topics = choose_topics(row.get('description'), degrees, size)
                batch.extend((record[0], 'topic', phrase, phrase, record[1]) for phrase in topics)
        if number % 2000 == 0:
            db.executemany('INSERT INTO edges VALUES(?,?,?,?,?)', batch); db.commit(); batch.clear()
        if number % 50000 == 0:
            print(json.dumps({'stage':'topic edges','books':number,'seconds':time.perf_counter()-started}), flush=True)
    db.executemany('INSERT INTO edges VALUES(?,?,?,?,?)', batch); db.commit()
    db.execute("INSERT INTO features SELECT kind,term,COUNT(*),0.0 FROM edges WHERE kind='topic' GROUP BY kind,term")
    # Actual retained graph degree, rather than pre-selection phrase frequency.
    db.execute("DELETE FROM edges WHERE kind='topic' AND term IN (SELECT term FROM features WHERE kind='topic' AND (degree<? OR degree>?))", (TOPIC_POLICY['min_degree'], maximum))
    db.execute("DELETE FROM features WHERE kind='topic' AND (degree<? OR degree>?)", (TOPIC_POLICY['min_degree'], maximum))
    pending = []
    for kind, term, degree in db.execute("SELECT kind,term,degree FROM features WHERE kind='topic'"):
        pending.append((RELATION_WEIGHTS[kind]*(1+math.log((size+1)/(degree+1))),kind,term))
        if len(pending) >= 20000:
            db.executemany('UPDATE features SET weight=? WHERE kind=? AND term=?',pending);pending.clear()
    db.executemany('UPDATE features SET weight=? WHERE kind=? AND term=?',pending)
    db.executescript('DELETE FROM norms; INSERT INTO norms SELECT e.book_id,SUM(f.weight*f.weight) FROM edges e JOIN features f USING(kind,term) GROUP BY e.book_id; DROP TABLE phrase_documents; DROP TABLE topic_degrees; ANALYZE;')
    meta.update(version=V2_VERSION,scope=scope,created_at=datetime.now(timezone.utc).isoformat(),
        relation_weights=RELATION_WEIGHTS,topic_policy=TOPIC_POLICY,
        base_snapshot=meta['catalogue_hash'],description_books_with_phrase_candidates=described,
        features=dict(db.execute('SELECT kind,COUNT(*) FROM features GROUP BY kind')),
        edges=db.execute('SELECT COUNT(*) FROM edges').fetchone()[0],
        topic_books=db.execute("SELECT COUNT(DISTINCT book_id) FROM edges WHERE kind='topic'").fetchone()[0],
        weak_feature_qualification='Only author, subject and bounded description-topic connections qualify. Publisher/language/era unavailable and never qualify alone.',
        scoring='Weighted cosine using explicit relation weights and retained graph degree. Topic amplitude 0.5 gives one quarter of subject squared weight at equal degree; conservative untuned initial policy.',
        schema={'nodes':['Book','Author name','Subject label','Description topic'],'edges':['AUTHORED_BY','HAS_SUBJECT','HAS_TOPIC']})
    if vocabulary_source is not None:
        meta['version']='kg31-description-subject-vocabulary-v2'
        meta['topic_vocabulary']='Exact normalized phrases already present as subject labels in frozen full V1 graph; no title inference, generative labels or per-seed allowlist.'
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert db.execute('SELECT COUNT(*) FROM edges e LEFT JOIN books b ON e.book_id=b.id WHERE b.id IS NULL').fetchone()[0]==0
    assert db.execute('SELECT COUNT(*) FROM books WHERE description_hash IS NULL').fetchone()[0]==0
    meta['build_seconds']=time.perf_counter()-started
    db.execute("UPDATE meta SET value=? WHERE key='summary'", (json.dumps(meta),)); db.commit()
    db.execute('VACUUM INTO ?', (str(compacted),)); db.close()
    os.replace(compacted,output)
    assert temporary.parent.resolve()==output.parent.resolve() and temporary.name.endswith('.building.sqlite')
    temporary.unlink()
    meta['database_bytes']=output.stat().st_size
    meta['total_enrichment_seconds_including_compaction']=time.perf_counter()-started
    return meta


if __name__=='__main__':
    raise SystemExit('Use the pilot driver first; full builds are gated on its evidence.')
