"""Stream public Mongo catalogue fields into an atomic, locally indexed graph."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from knowledge_graph.core import DEFAULT_GRAPH,VERSION,canonical,public_book,terms
from knowledge_graph.relations import RELATION_WEIGHTS
from search.catalogue import searchable

def build(rows,path,source_count=None,progress=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.building.sqlite')
    if path.exists() or temporary.exists():raise FileExistsError('Refusing to overwrite a graph or unfinished build.')
    started=time.perf_counter();digest=hashlib.sha256();count=skipped=missing_author=missing_subject=isolates=edge_count=0
    db=sqlite3.connect(temporary)
    db.executescript('''PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA temp_store=FILE; PRAGMA cache_size=-131072;
        CREATE TABLE books(id INTEGER PRIMARY KEY,work_id TEXT NOT NULL,title TEXT NOT NULL,title_key TEXT NOT NULL,authors TEXT NOT NULL,subjects TEXT NOT NULL);
        CREATE TABLE edges(book_id INTEGER NOT NULL,kind TEXT NOT NULL,term TEXT NOT NULL,label TEXT NOT NULL);
        CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);''')
    def update(stage):
        value=dict(stage=stage,books=count,edges=edge_count,skipped=skipped,source_count=source_count,elapsed_seconds=time.perf_counter()-started)
        if progress:progress(value)
        print(json.dumps(value),flush=True)
    books=[];edges=[]
    def flush():
        db.executemany('INSERT INTO books VALUES(?,?,?,?,?,?)',books);db.executemany('INSERT INTO edges VALUES(?,?,?,?)',edges);db.commit();books.clear();edges.clear()
    for row in rows:
        if not searchable(row):skipped+=1;continue
        count+=1;book=public_book(row);authors=terms(row.get('authors'));subjects=terms(row.get('subjects'))
        missing_author+=not bool(authors);missing_subject+=not bool(subjects);isolates+=not bool(authors or subjects)
        books.append((count,book['work_id'],book['title'],canonical(book['title']),json.dumps(book['authors'],ensure_ascii=False),json.dumps(book['subjects'],ensure_ascii=False)))
        for kind,labels in [('author',authors),('subject',subjects)]:
            edges.extend((count,kind,term,label) for term,label in labels.items());edge_count+=len(labels)
        digest.update((json.dumps(book,sort_keys=True,ensure_ascii=False)+'\n').encode())
        if len(books)>=2000:flush()
        if count%50000==0:update('streaming')
    flush();update('indexing')
    db.executescript('''CREATE UNIQUE INDEX books_work_id ON books(work_id);
        CREATE INDEX books_title ON books(title_key,work_id);
        CREATE INDEX edges_book ON edges(book_id,kind,term);
        CREATE INDEX edges_feature ON edges(kind,term,book_id);
        CREATE TABLE features(kind TEXT,term TEXT,degree INTEGER,weight REAL,PRIMARY KEY(kind,term));
        INSERT INTO features SELECT kind,term,COUNT(*),0.0 FROM edges GROUP BY kind,term;''')
    update('weighting')
    pending=[]
    for kind,term,degree in db.execute('SELECT kind,term,degree FROM features'):
        weight=RELATION_WEIGHTS[kind]*(1+math.log((count+1)/(degree+1)))
        pending.append((weight,kind,term))
        if len(pending)>=20000:db.executemany('UPDATE features SET weight=? WHERE kind=? AND term=?',pending);pending.clear()
    if pending:db.executemany('UPDATE features SET weight=? WHERE kind=? AND term=?',pending)
    db.commit();update('norms')
    db.executescript('''CREATE TABLE norms(book_id INTEGER PRIMARY KEY,value REAL NOT NULL);
        INSERT INTO norms SELECT e.book_id,SUM(f.weight*f.weight) FROM edges e JOIN features f USING(kind,term) GROUP BY e.book_id;
        ANALYZE;''')
    summary=dict(version=VERSION,source='Mongo books: projected public metadata only',source_count=source_count,books=count,edges=edge_count,
        features=dict(db.execute('SELECT kind,COUNT(*) FROM features GROUP BY kind').fetchall()),
        missing_authors=missing_author,missing_subjects=missing_subject,isolated_books=isolates,skipped_books=skipped,
        created_at=datetime.now(timezone.utc).isoformat(),catalogue_hash=digest.hexdigest(),build_seconds=time.perf_counter()-started,
        schema={'nodes':['Book','Author name','Subject label'],'edges':['AUTHORED_BY','HAS_SUBJECT']},
        normalization='NFKC, case-fold, whitespace; split only pipe delimiters. Names are metadata strings, not resolved human identities.',
        scoring='Weighted cosine over shared typed features. weight=(2 for author else 1)*(1+ln((N+1)/(degree+1))). No embeddings, LLM, behavioral or availability score.',
        scope='full catalogue' if source_count==count+skipped else 'explicit bounded build')
    db.execute("INSERT INTO meta VALUES('summary',?)",(json.dumps(summary),));db.commit();db.close()
    os.replace(temporary,path)
    if progress:progress(dict(stage='complete',**summary,database_bytes=path.stat().st_size))
    return summary

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=DEFAULT_GRAPH);parser.add_argument('--max-books',type=int,default=0);args=parser.parse_args()
    from backend.database.mongodb import books_collection
    projection={'_id':0,'work_id':1,'title':1,'authors':1,'subjects':1,'active':1,'is_active':1,'searchable':1}
    total=books_collection.count_documents({});cursor=books_collection.find({},projection).batch_size(2000)
    if args.max_books:cursor=cursor.limit(args.max_books)
    def progress(value):(ROOT/'reports/kg_build_progress.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
    summary=build(cursor,args.output,total,progress)
    (ROOT/'reports/kg1_kg2_build.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
if __name__=='__main__':main()
