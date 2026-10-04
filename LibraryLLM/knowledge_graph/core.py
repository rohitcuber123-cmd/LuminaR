"""Typed metadata graph on SQLite, with deterministic two-hop reason paths."""
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import unicodedata
from contextlib import contextmanager
from knowledge_graph.relations import RELATIONS

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_GRAPH=ROOT/'knowledge_graph/data/catalogue.sqlite'
VERSION='kg1-2-metadata-cosine-v1'

def canonical(value):return ' '.join(unicodedata.normalize('NFKC',value).casefold().split())

def terms(value):
    items=value.split('|') if isinstance(value,str) else value if isinstance(value,(list,tuple)) else []
    result={}
    for item in items:
        if isinstance(item,str) and item.strip():result.setdefault(canonical(item),item.strip())
    return result

def feature_id(kind,term):return kind+':'+hashlib.sha256(term.encode('utf-8')).hexdigest()

def public_book(book):
    return {'work_id':book['work_id'],'title':book['title'],
            'authors':list(terms(book.get('authors')).values()),'subjects':list(terms(book.get('subjects')).values())}

@contextmanager
def connect(path=DEFAULT_GRAPH):
    if not Path(path).is_file():raise FileNotFoundError('The catalogue graph has not been built yet.')
    connection=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=15)
    connection.row_factory=sqlite3.Row
    connection.execute('PRAGMA query_only=ON')
    try:yield connection
    finally:connection.close()

class CatalogueGraph:
    def __init__(self,path=DEFAULT_GRAPH):self.path=Path(path)
    def meta(self):
        with connect(self.path) as db:return json.loads(db.execute("SELECT value FROM meta WHERE key='summary'").fetchone()[0])
    @staticmethod
    def _book(row):
        book={'work_id':row['work_id'],'title':row['title'],'authors':json.loads(row['authors']),'subjects':json.loads(row['subjects'])}
        if 'description_hash' in row.keys():book['description_hash']=row['description_hash']
        return book
    def book(self,work_id):
        with connect(self.path) as db:
            row=db.execute('SELECT * FROM books WHERE work_id=?',(work_id,)).fetchone()
            if row is None:raise KeyError(work_id)
            return self._book(row)
    def lookup(self,text='',limit=20):
        with connect(self.path) as db:
            # Bound scans to the title index through a normalized prefix range.
            prefix=canonical(text)
            rows=db.execute('SELECT * FROM books WHERE title_key>=? AND title_key<? ORDER BY title_key,work_id LIMIT ?',
                            (prefix,prefix+'\U0010ffff',limit)).fetchall() if prefix else db.execute('SELECT * FROM books ORDER BY id LIMIT ?',(limit,)).fetchall()
            return [self._book(row) for row in rows]
    def more_like_this(self,work_id,limit=10,excluded=()):
        if not 1<=limit<=50:raise ValueError('limit must be between 1 and 50')
        with connect(self.path) as db:
            seed=db.execute('SELECT * FROM books WHERE work_id=?',(work_id,)).fetchone()
            if seed is None:raise KeyError(work_id)
            features=db.execute('SELECT e.kind,e.term,e.label,f.degree,f.weight FROM edges e JOIN features f USING(kind,term) WHERE e.book_id=? ORDER BY f.degree,e.kind,e.term',(seed['id'],)).fetchall()
            catalogue_size=json.loads(db.execute("SELECT value FROM meta WHERE key='summary'").fetchone()[0])['books']
            excluded_ids=set(excluded)|{work_id}
            if not features:return {'seed':self._book(seed),'recommendations':[],'candidate_count':0,'reason':'No author or subject links for this book.'}
            # Every shared feature is considered; there is no sampled neighbor cap.
            score_query='''SELECT e.book_id,SUM(f.weight*f.weight) / SQRT(n.value*?) AS score
                FROM edges e JOIN features f USING(kind,term) JOIN norms n ON n.book_id=e.book_id
                WHERE (e.kind,e.term) IN (SELECT kind,term FROM edges WHERE book_id=?) AND e.book_id!=?
                GROUP BY e.book_id ORDER BY score DESC,e.book_id'''
            norm=db.execute('SELECT value FROM norms WHERE book_id=?',(seed['id'],)).fetchone()[0]
            cursor=db.execute(score_query,(norm,seed['id'],seed['id']))
            recommendations=[];candidate_count=0
            enriched='source_hash' in {row['name'] for row in db.execute('PRAGMA table_info(edges)')}
            for candidate in cursor:
                candidate_count+=1
                if len(recommendations)>=limit:continue
                book=db.execute('SELECT * FROM books WHERE id=?',(candidate['book_id'],)).fetchone()
                if book['work_id'] in excluded_ids:continue
                evidence_columns=',a.source_hash AS seed_source_hash,c.source_hash AS candidate_source_hash' if enriched else ''
                paths=db.execute('''SELECT a.kind,a.term,a.label AS seed_label,c.label AS candidate_label,f.degree,f.weight''' + evidence_columns + '''
                    FROM edges a JOIN edges c USING(kind,term) JOIN features f USING(kind,term)
                    WHERE a.book_id=? AND c.book_id=? ORDER BY f.weight DESC,a.kind,a.term''',(seed['id'],book['id'])).fetchall()
                candidate_norm=db.execute('SELECT value FROM norms WHERE book_id=?',(book['id'],)).fetchone()[0]
                reasons=[]
                for path in paths:
                    predicate,field=RELATIONS[path['kind']]
                    importance=1+math.log((catalogue_size+1)/(path['degree']+1))
                    # Explain the published weight without applying a new runtime policy.
                    relation_weight=path['weight']/importance
                    provenance=[{'work_id':work_id,'field':field,'value':path['seed_label']},
                                {'work_id':book['work_id'],'field':field,'value':path['candidate_label']}]
                    if path['kind']=='topic':
                        for item,hash_field in zip(provenance,['seed_source_hash','candidate_source_hash']):
                            item.update(description_sha256=path[hash_field],extractor='adjacent-source-phrases-tfidf-v1')
                    reasons.append({'nodes':[work_id,feature_id(path['kind'],path['term']),book['work_id']],
                        'kind':path['kind'],'label':path['seed_label'],
                        'predicates':[predicate,predicate],
                        'catalogue_degree':path['degree'],'relation_weight':relation_weight,
                        'importance':importance,'feature_weight':path['weight'],'contribution':path['weight']**2/math.sqrt(norm*candidate_norm),
                        'provenance':provenance})
                recommendations.append(dict(**self._book(book),score=candidate['score'],reason_paths=reasons))
            return {'seed':self._book(seed),'recommendations':recommendations,'candidate_count':candidate_count,
                    'reason':'Shared catalogue authors and subjects, weighted by rarity; scores are similarity, not a relevance probability.'}
    def exploration(self,response,max_reasons=3):
        seed=response['seed'];nodes={seed['work_id']:dict(id=seed['work_id'],kind='book',label=seed['title'],seed=True)};edges={}
        for book in response['recommendations']:
            nodes[book['work_id']]=dict(id=book['work_id'],kind='book',label=book['title'],seed=False)
            for path in book['reason_paths'][:max_reasons]:
                bridge=path['nodes'][1];nodes[bridge]=dict(id=bridge,kind=path['kind'],label=path['label'],seed=False)
                for endpoint in [seed['work_id'],book['work_id']]:
                    edges[endpoint,bridge]=dict(source=endpoint,target=bridge,predicate=path['predicates'][0])
        return {'nodes':list(nodes.values()),'edges':list(edges.values()),'reason_paths_per_book_shown':max_reasons}
