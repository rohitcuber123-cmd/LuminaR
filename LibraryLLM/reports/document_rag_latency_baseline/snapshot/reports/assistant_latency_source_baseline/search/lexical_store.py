"""Optional immutable lexical readers; no production ranking or live events."""
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
from search.typo_assistance import normalize_structured, conservative_similarity

SCHEMA_VERSION = 2
NORMALIZATION_VERSION = 'nfkc-casefold-space-v1'
MAX_CANDIDATES = 100
DEFAULT_CANDIDATES = 50
MAX_WORK_IDS_PER_VALUE = 50
MAX_CANDIDATE_SEEKS = 512
MAX_QUERY_LENGTH = 256
MIN_FUZZY_LENGTH = 5
FUZZY_THRESHOLD = .86
FUZZY_MARGIN = .05
MAX_EDIT_PREFIXES = 256
VERSION_RE = re.compile(r'^[0-9a-f]{32}$')
LOG = logging.getLogger(__name__)
INDEXES = {'idx_lexical_exact': ['value_type','normalized_value','work_id'],
           'idx_lexical_work': ['work_id']}
RANGE_SQL = ('SELECT normalized_value,work_id FROM lexical_values '
             'WHERE value_type=? AND normalized_value>=? AND normalized_value<? '
             'ORDER BY normalized_value,work_id LIMIT ?')
FIRST_VALUE_SQL = ('SELECT normalized_value FROM lexical_values '
                   'WHERE value_type=? AND normalized_value>=? AND normalized_value<? '
                   'ORDER BY normalized_value LIMIT 1')
NEXT_VALUE_SQL = ('SELECT normalized_value FROM lexical_values '
                  'WHERE value_type=? AND normalized_value>? AND normalized_value<? '
                  'ORDER BY normalized_value LIMIT 1')
EXPAND_WORK_IDS_SQL = ('SELECT work_id FROM lexical_values '
                       'WHERE value_type=? AND normalized_value=? ORDER BY work_id LIMIT ?')
EDIT_VALUE_SQL = ('SELECT normalized_value FROM lexical_values '
                  'WHERE value_type=? AND normalized_value=? LIMIT 1')


def default_path():
    return Path(os.getenv('LUMINAR_LEXICAL_PATH', Path(__file__).resolve().parents[1] / 'datasets/ai/lexical/published'))


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): digest.update(block)
    return digest.hexdigest()


def read_json(path):
    # Windows can briefly reject opens while another process replaces a pointer.
    for attempt in range(5):
        try:
            return json.loads(Path(path).read_text(encoding='utf-8'))
        except PermissionError:
            if attempt==4: raise
            time.sleep(.01)


def prefix_upper(prefix):
    for i in range(len(prefix)-1,-1,-1):
        if ord(prefix[i]) < 0x10ffff:
            return prefix[:i]+chr(ord(prefix[i])+1)
    raise ValueError('Prefix has no finite upper bound')


def edit_prefixes(query):
    """Bounded deterministic single-edit whole-query probes."""
    seen=set()
    positions=range(min(32,len(query)))
    for i in positions:
        if i+1<len(query):
            value=query[:i]+query[i+1]+query[i]+query[i+2:]
            if value!=query and value not in seen:
                seen.add(value); yield value
    for i in positions:
        value=query[:i]+query[i+1:]
        if len(value)>=4 and value not in seen:
            seen.add(value); yield value
    insertion_positions=list(range(min(8,len(query)+1)))
    insertion_positions += [i+1 for i,c in enumerate(query[:32]) if c==' ']
    for i in dict.fromkeys(insertion_positions):
        for letter in 'abcdefghijklmnopqrstuvwxyz':
            value=query[:i]+letter+query[i:]
            if value not in seen:
                seen.add(value); yield value
                if len(seen)>=MAX_EDIT_PREFIXES: return


def read_connection(path):
    # Only closed, never-mutated published snapshots: immutable prevents SHM/WAL creation.
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro&immutable=1',
                       uri=True, timeout=.1, check_same_thread=False)
    db.execute('PRAGMA query_only=ON')
    db.execute('PRAGMA cache_size=-2048')
    db.execute('PRAGMA mmap_size=0')
    return db


def validate_snapshot(path,m,verify_checksum=True,timings=None,mode='full'):
    timings=timings if timings is not None else {}
    validation_started=time.perf_counter()
    if mode not in ('full','startup','quick'):
        raise ValueError('Invalid lexical validation mode')
    if not isinstance(m,dict): raise ValueError('Invalid lexical manifest object')
    required={'schema_version','normalization_version','sidecar_version','created_at',
              'source_db_name','book_count','title_relationship_count','author_relationship_count',
              'row_count','file_size','sha256','build_duration_seconds','builder_version',
              'lexical_generation','last_sync','source_event_checkpoint'}
    if not required.issubset(m): raise ValueError('Incomplete lexical manifest')
    if m['schema_version']!=SCHEMA_VERSION: raise ValueError('Unsupported lexical schema')
    if m['normalization_version']!=NORMALIZATION_VERSION: raise ValueError('Unsupported normalization')
    for key in ('created_at','source_db_name','builder_version'):
        if not isinstance(m[key],str) or not m[key]: raise ValueError('Invalid manifest text')
    from datetime import datetime
    if datetime.fromisoformat(m['created_at']).tzinfo is None: raise ValueError('Build timestamp needs timezone')
    if not isinstance(m['sha256'],str) or not re.fullmatch(r'[0-9a-f]{64}',m['sha256']): raise ValueError('Invalid checksum field')
    if not isinstance(m['build_duration_seconds'],(int,float)) or m['build_duration_seconds']<0: raise ValueError('Invalid build duration')
    if not VERSION_RE.fullmatch(str(m['sidecar_version'])): raise ValueError('Invalid lexical version')
    for key in ('book_count','title_relationship_count','author_relationship_count','row_count','file_size','lexical_generation'):
        if type(m[key]) is not int or m[key]<0: raise ValueError('Invalid manifest count')
    if m['title_relationship_count']+m['author_relationship_count']!=m['row_count']:
        raise ValueError('Inconsistent lexical manifest counts')
    path=Path(path)
    if not path.is_file() or not path.stat().st_size: raise ValueError('Missing or empty lexical database')
    if path.stat().st_size!=m['file_size']: raise ValueError('Lexical size mismatch')
    checksum_started=time.perf_counter()
    if verify_checksum and digest_file(path)!=m['sha256']: raise ValueError('Lexical checksum mismatch')
    timings['checksum_seconds']=time.perf_counter()-checksum_started
    reader_open_started=time.perf_counter()
    db=read_connection(path)
    timings['reader_open_seconds']=time.perf_counter()-reader_open_started
    try:
        if mode in ('full','quick'):
            stage=time.perf_counter()
            pragma='PRAGMA integrity_check' if mode=='full' else 'PRAGMA quick_check'
            if db.execute(pragma).fetchone()[0]!='ok': raise ValueError('Lexical integrity error')
            timings['integrity_check_seconds' if mode=='full' else 'quick_check_seconds']=time.perf_counter()-stage
        stage=time.perf_counter()
        if [r[1] for r in db.execute('PRAGMA table_info(lexical_values)')]!=['value_type','normalized_value','work_id']:
            raise ValueError('Missing lexical table/columns')
        info={r[1]:r for r in db.execute('PRAGMA index_list(lexical_values)')}
        for name,fields in INDEXES.items():
            if name not in info or [r[2] for r in db.execute('PRAGMA index_info('+name+')')]!=fields:
                raise ValueError('Missing or incompatible lexical index')
            if any(r[4]!='BINARY' for r in db.execute('PRAGMA index_xinfo('+name+')') if r[5]):
                raise ValueError('Invalid lexical collation')
        if not info['idx_lexical_exact'][2]: raise ValueError('Missing lexical uniqueness')
        meta=dict(db.execute('SELECT key,value FROM metadata'))
        for key in ('sidecar_version','schema_version','normalization_version','lexical_generation','source_db_name'):
            if meta.get(key)!=str(m[key]): raise ValueError('Mixed lexical metadata/manifest')
        timings['schema_validation_seconds']=time.perf_counter()-stage
        if mode=='full':
            stage=time.perf_counter()
            counts=dict(db.execute('SELECT value_type,count(*) FROM lexical_values GROUP BY value_type'))
            if set(counts)-{'TITLE','AUTHOR'}: raise ValueError('Invalid lexical type')
            if counts.get('TITLE',0)!=m['title_relationship_count'] or counts.get('AUTHOR',0)!=m['author_relationship_count'] or sum(counts.values())!=m['row_count']:
                raise ValueError('Lexical count mismatch')
            if db.execute('SELECT count(DISTINCT work_id) FROM lexical_values').fetchone()[0]!=m['book_count']:
                raise ValueError('Lexical book count mismatch')
            if db.execute("SELECT count(*) FROM lexical_values WHERE work_id IS NULL OR normalized_value IS NULL OR work_id='' OR normalized_value=''").fetchone()[0]:
                raise ValueError('Invalid lexical row')
            timings['count_validation_seconds']=time.perf_counter()-stage
    except Exception:
        db.close()
        raise
    timings['total_validation_seconds']=time.perf_counter()-validation_started
    return db


class LexicalSearchStore:
    def __init__(self,path=None,*,enabled=True,expected_source_db=None,required_generation=None,
                 validation_mode='startup'):
        self.root=Path(path or default_path())
        self.db=None
        self.manifest={}
        self.error=None
        self.enabled=enabled
        self.pending=False
        self.lock=threading.RLock()
        self.startup_timings={}
        if not enabled: return
        try:
            stage=time.perf_counter()
            pointer=read_json(self.root/'active_lexical.json')
            if not isinstance(pointer,dict): raise ValueError('Invalid active pointer object')
            version=pointer['version']
            if not isinstance(version,str) or not VERSION_RE.fullmatch(version): raise ValueError('Invalid active lexical pointer')
            self.startup_timings['pointer_load_seconds']=time.perf_counter()-stage
            stage=time.perf_counter()
            self.path=self.root/('lexical_'+version+'.sqlite')
            m=read_json(self.path.with_suffix('.json'))
            if not isinstance(m,dict): raise ValueError('Invalid lexical manifest object')
            if m.get('sidecar_version')!=version: raise ValueError('Mixed lexical pointer/manifest')
            if expected_source_db is not None and m.get('source_db_name')!=expected_source_db: raise ValueError('Wrong lexical source database')
            if required_generation is not None and m.get('lexical_generation',-1)<required_generation:
                self.pending=True
                raise ValueError('Lexical generation behind requirement')
            self.startup_timings['manifest_load_seconds']=time.perf_counter()-stage
            self.db=validate_snapshot(self.path,m,timings=self.startup_timings,mode=validation_mode)
            self.manifest=m
        except (OSError,ValueError,TypeError,KeyError,sqlite3.Error) as error:
            self.error=type(error).__name__+': '+str(error)
            LOG.warning('lexical_unavailable error_type=%s',type(error).__name__)

    def close(self):
        with self.lock:
            if self.db is not None:
                self.db.close()
                self.db=None

    def _query(self,sql,args):
        with self.lock:
            if self.db is None: return []
            try: return self.db.execute(sql,args).fetchall()
            except sqlite3.Error as error:
                self.error=type(error).__name__
                self.db.close()
                self.db=None
                LOG.warning('lexical_lookup_failed error_type=%s',type(error).__name__)
                return []

    def _seek_candidate(self,sql,args):
        found=self._query(sql,args)
        return found[0][0] if found else None

    def _candidate_eligible(self,value_type,normalized_value):
        return True

    @staticmethod
    def _limit(limit):
        return min(MAX_CANDIDATES,max(0,int(limit)))

    def exact(self,value_type,query,limit=50):
        q=normalize_structured(query)
        if value_type not in ('TITLE','AUTHOR') or not q or len(q)>MAX_QUERY_LENGTH: return []
        return self._query('SELECT normalized_value,work_id FROM lexical_values WHERE value_type=? AND normalized_value=? ORDER BY work_id LIMIT ?',
                           (value_type,q,self._limit(limit)))

    def candidates(self,value_type,query,limit=DEFAULT_CANDIDATES):
        return self._candidate_result(value_type,query,limit)[0]

    def _candidate_result(self,value_type,query,limit=DEFAULT_CANDIDATES):
        q=normalize_structured(query)
        limit=self._limit(limit)
        evidence={'seeks':0,'probes':0,'inspected_values':0}
        if value_type not in ('TITLE','AUTHOR') or len(q)<MIN_FUZZY_LENGTH or len(q)>MAX_QUERY_LENGTH or not limit:
            return [],False,evidence
        def seek(sql,args):
            if evidence['seeks']>=MAX_CANDIDATE_SEEKS: return None,True
            value=self._seek_candidate(sql,args)
            evidence['seeks']+=1
            return value,False
        def range_values(prefix):
            evidence['probes']+=1
            upper=prefix_upper(prefix)
            values=[]
            previous=None
            while True:
                if previous is None:
                    value,exhausted=seek(FIRST_VALUE_SQL,(value_type,prefix,upper))
                else:
                    value,exhausted=seek(NEXT_VALUE_SQL,(value_type,previous,upper))
                if exhausted: return values,True
                if value is None: return values,False
                evidence['inspected_values']+=1
                previous=value
                if not self._candidate_eligible(value_type,value): continue
                if len(values)>=limit: return values,True
                values.append(value)
        def promising(values):
            return bool(values) and max(conservative_similarity(q,v) for v in values)>=FUZZY_THRESHOLD
        longest=min(16,max(8,len(q)-2))
        primary,primary_full=range_values(q[:longest])
        if promising(primary) and not primary_full:
            return primary,False,evidence
        # Exact single-edit variants are selective equality seeks, including
        # late transpositions. They are tried before broadening a crowded range.
        edits=[]
        seen=set()
        for variant in edit_prefixes(q):
            value,exhausted=seek(EDIT_VALUE_SQL,(value_type,variant))
            if exhausted: return edits or primary,True,evidence
            evidence['probes']+=1
            if value is not None and value not in seen and self._candidate_eligible(value_type,value):
                evidence['inspected_values']+=1
                if len(edits)>=limit: return edits,True,evidence
                edits.append(value); seen.add(value)
        if edits:
            combined=list(dict.fromkeys((primary if not primary_full else [])+edits))
            if len(combined)>limit: return combined[:limit],True,evidence
            if promising(combined): return combined,False,evidence
        # Shorter literal prefixes and finally a four-character fallback are
        # each B-tree seeks. A crowded/incomplete range cannot be selected.
        last=edits or primary
        for width in range(longest-1,7,-1):
            values,truncated=range_values(q[:width])
            if promising(values) or truncated:
                return values,truncated,evidence
            if values: last=values
        values,truncated=range_values(q[:4])
        return (values or last),truncated,evidence

    def work_id(self,work_id,limit=100):
        return self._query('SELECT value_type,normalized_value FROM lexical_values WHERE work_id=? LIMIT ?',
                           (work_id,self._limit(limit)))

    def work_ids_for_value(self,value_type,normalized_value,limit=MAX_WORK_IDS_PER_VALUE):
        if value_type not in ('TITLE','AUTHOR') or not normalized_value:
            return []
        return list(dict.fromkeys(row[0] for row in self._query(
            EXPAND_WORK_IDS_SQL,(value_type,normalized_value,
                                 min(MAX_WORK_IDS_PER_VALUE,self._limit(limit))))))

    def _has_leading_token(self,value_type,query):
        prefix=query+' '
        return bool(self._query(FIRST_VALUE_SQL,(value_type,prefix,prefix_upper(prefix))))

    def fuzzy(self,value_type,query,limit=DEFAULT_CANDIDATES):
        q=normalize_structured(query)
        started=time.perf_counter()
        exact=self.exact(value_type,q,limit)
        rows=[]
        scores=[]
        candidate_ms=0.0
        scoring_ms=0.0
        expansion_ms=0.0
        evidence={'seeks':0,'probes':0,'inspected_values':0}
        work_ids=[]
        match=None
        gap=None
        truncated=False
        if self.db is None: reason='unavailable'
        elif exact: reason='exact_match_precedence'
        elif len(q)<MIN_FUZZY_LENGTH: reason='short_query'
        elif len(q)>MAX_QUERY_LENGTH: reason='query_too_long'
        else:
            stage=time.perf_counter()
            rows,truncated,evidence=self._candidate_result(value_type,q,limit)
            candidate_ms=(time.perf_counter()-stage)*1000
            stage=time.perf_counter()
            scores=sorted(((conservative_similarity(q,v),v) for v in rows),reverse=True)
            scoring_ms=(time.perf_counter()-stage)*1000
            gap=scores[0][0]-scores[1][0] if len(scores)>1 else None
            if self.db is None: reason='unavailable'
            elif truncated: reason='candidate_cap_reached'
            elif ' ' not in q and self._has_leading_token(value_type,q): reason='exact_title_token_evidence'
            elif not scores or scores[0][0]<FUZZY_THRESHOLD: reason='below_threshold'
            elif gap is not None and gap<FUZZY_MARGIN: reason='ambiguous'
            else:
                match={'value':scores[0][1],'similarity':scores[0][0]}
                reason='selected'
                stage=time.perf_counter()
                work_ids=self.work_ids_for_value(value_type,match['value'])
                expansion_ms=(time.perf_counter()-stage)*1000
        if exact:
            work_ids=list(dict.fromkeys(wid for _,wid in exact))
        return {'normalized_query':q,'exact':exact,'candidates':rows,'scores':scores,'match':match,
                'margin':gap,'reason':reason,'candidate_truncated':truncated,
                'candidate_generation_ms':candidate_ms,'fuzzy_scoring_ms':scoring_ms,
                'work_id_expansion_ms':expansion_ms,'candidate_generation_seeks':evidence['seeks'],
                'candidate_probe_count':evidence['probes'],'inspected_values':evidence['inspected_values'],
                'work_ids':work_ids,
                'elapsed_ms':(time.perf_counter()-started)*1000}

    def health(self):
        m=self.manifest
        return {'lexical_enabled':self.enabled,'lexical_available':self.db is not None,
                'lexical_version':m.get('sidecar_version'),'lexical_generation':m.get('lexical_generation'),
                'lexical_schema_version':m.get('schema_version'),'lexical_file_size':m.get('file_size'),
                'lexical_last_build':m.get('created_at'),'lexical_last_sync':m.get('last_sync'),
                'lexical_pending':self.pending,'lexical_last_error':self.error}


def search_with_lexical_diagnostics(engine,store,query,**kwargs):
    """Internal adapter. Public API and production semantic engine unchanged."""
    result=engine.search(query,**kwargs)
    try:
        result['lexical_diagnostics']={'health':store.health(),'title':store.fuzzy('TITLE',query),'author':store.fuzzy('AUTHOR',query)}
    except Exception as error:
        result['lexical_diagnostics']={'health':{'lexical_available':False,'lexical_last_error':type(error).__name__}}
    return result
