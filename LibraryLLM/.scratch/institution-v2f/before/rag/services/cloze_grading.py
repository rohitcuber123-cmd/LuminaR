"""Conservative short-answer grading. No retrieval, Qwen or GPU dependency."""
from collections import OrderedDict
from concurrent.futures import Future
from decimal import Decimal, InvalidOperation
import hashlib
import math
import re
from threading import Lock, Thread
import time
import unicodedata

VERSION='1.0.0'
UNITS={'ms':('time',Decimal('.001')),'millisecond':('time',Decimal('.001')),'milliseconds':('time',Decimal('.001')),
       's':('time',Decimal(1)),'second':('time',Decimal(1)),'seconds':('time',Decimal(1)),
       'min':('time',Decimal(60)),'minute':('time',Decimal(60)),'minutes':('time',Decimal(60)),
       'h':('time',Decimal(3600)),'hour':('time',Decimal(3600)),'hours':('time',Decimal(3600)),
       '%':('percent',Decimal('.01')),'percent':('percent',Decimal('.01'))}
NUMBER=re.compile(r'^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)\s*([a-z%]*)$',re.I)
NEGATION=re.compile(r'\b(?:not|never|no|cannot|without)\b|n[’\']t\b',re.I)
STOP=set('a an the of to for in on and or is are be it that which this with as by how can so does do its'.split())

def normalize(value,articles=False):
    value=unicodedata.normalize('NFKC',value).casefold().replace('−','-')
    value=re.sub(r"\b(\w+)n['’]t\b",r'\1 not',value)
    value=re.sub(r'(?<=[^\W\d_])\s*[-‐‑–—]\s*(?=[^\W\d_])',' ',value)
    value=re.sub(r'[^\w\s.%+\-]',' ',value)
    value=re.sub(r'\s+',' ',value).strip().rstrip('.')
    return re.sub(r'^(?:a|an|the)\s+','',value) if articles else value

def quantity(value):
    match=NUMBER.fullmatch(normalize(value))
    if not match:
        # A bare source symbol has coefficient one, not a missing numeric value.
        if re.fullmatch(r'[A-Z]',value.strip()):return Decimal(1),'symbol:'+value.strip().casefold()
        return None
    try:number=Decimal(match[1])
    except InvalidOperation:return None
    unit=match[2].casefold()
    if not number.is_finite() or abs(number)>Decimal('1e20'):return None
    dimension,factor=UNITS.get(unit,('symbol:'+unit,Decimal(1))) if unit else ('number',Decimal(1))
    return number*factor,dimension

def answer_type(answer):
    q=quantity(answer)
    if q:return 'NUMBER' if q[1]=='number' else 'NUMBER_WITH_UNIT'
    words=normalize(answer).split()
    if re.search(r'\b(?:controll?ing|controls?|regulating|regulates?|allows?|permits?|splits?|limits?|provides?|protects?|prevents?|sends?|receives?|removes?|selects?|divides?|converts?|ensures?|transmits?|gives?|runs?|assigns?|resolves?|transfers?)\b',answer,re.I):
        return 'DESCRIPTION'
    return 'SHORT_PHRASE' if len(words)>5 else 'ENTITY' if re.fullmatch(r'[A-Z][A-Z0-9 -]{1,14}',answer) else 'TERM'

def edit_distance_one(a,b):
    if a==b:return True
    if abs(len(a)-len(b))>1:return False
    if len(a)==len(b):return sum(x!=y for x,y in zip(a,b))==1
    if len(a)>len(b):a,b=b,a
    i=j=errors=0
    while i<len(a) and j<len(b):
        if a[i]==b[j]:i+=1;j+=1
        else:
            errors+=1;j+=1
            if errors>1:return False
    return True

def typo(a,b):
    left,right=a.split(),b.split()
    if len(left)!=len(right):return False
    changes=0
    for x,y in zip(left,right):
        if x==y:continue
        if x+'s'==y or y+'s'==x or x+'es'==y or y+'es'==x:return False
        # One edit total, in a long word only; acronyms and short qualifiers stay exact.
        if min(len(x),len(y))<6 or max(len(x),len(y))<7 or not edit_distance_one(x,y):return False
        changes+=1
    return changes==1

def rate_frame(text):
    """Small compositional language rule, never a technical term alias table.

    Match an entire rate-control phrase, retaining sender/receiver and purpose.
    This closes MiniLM's weak equivalence for 'how fast ... is sent'.
    """
    text=normalize(text,True)
    match=re.fullmatch(r'(?:controls?|regulates?|limits?) (?:the )?(?:(sender|receiver|transmission) )?(?:rate|speed)'
        r'(?:(?: so (?:the )?receiver is not overwhelmed)|(?: to protect (?:the )?receiver))?',text)
    if match:return (match[1] or 'unspecified',bool(re.search(r'overwhelmed|protect',text)))
    if re.fullmatch(r'(?:controls?|regulates?|limits?) how fast data (?:can be |is )?(?:sent|transmitted)',text):
        return ('transmission',False)
    return None

class SemanticCache:
    """Bounded short-lived scalar cache; no private text/vectors retained."""
    def __init__(self):
        self.lock=Lock();self.values=OrderedDict();self.jobs={};self.pending=[];self.running=False

    def similarities(self,texts,encoder):
        key=hashlib.sha256('\0'.join(texts).encode()).hexdigest()
        with self.lock:
            old=self.values.get(key)
            if old and old[0]>time.monotonic():
                self.values.move_to_end(key);return old[1]
            future=self.jobs.get(key);start=False
            if future is None:
                if len(self.jobs)>=64:raise RuntimeError('Phrase grading busy')
                future=Future();self.jobs[key]=future
                self.pending.append((key,texts,encoder,future))
                if not self.running:self.running=True;start=True
        if start:Thread(target=self._drain,daemon=True).start()
        return future.result(timeout=.7)

    def _drain(self):
        # A five-millisecond collection window shares repeated source/context
        # vectors across concurrent phrase answers. The existing CPU singleton
        # still performs every embedding; no generation/GPU lock is acquired.
        while True:
            time.sleep(.005)
            with self.lock:
                if not self.pending:self.running=False;return
                encoder=self.pending[0][2]
                batch=[x for x in self.pending if x[2] is encoder]
                self.pending=[x for x in self.pending if x[2] is not encoder]
            try:
                texts=batch[0][1] if len(batch)==1 else list(dict.fromkeys(t for x in batch for t in x[1]))
                raw=encoder(texts)
                if len(raw)!=len(texts):raise ValueError('Invalid semantic result')
                vectors=[list(map(float,v)) for v in raw]
                if any(not v or any(not math.isfinite(x) for x in v) for v in vectors):raise ValueError('Invalid semantic result')
                if len({len(v) for v in vectors})!=1:raise ValueError('Invalid semantic result')
                vectors=[[x/max(1e-9,math.sqrt(sum(y*y for y in v))) for x in v] for v in vectors]
                lookup=dict(zip(texts,vectors))
                for key,original,_,future in batch:
                    selected=vectors if len(batch)==1 else [lookup[t] for t in original]
                    result=[sum(x*y for x,y in zip(v,selected[0])) for v in selected[1:]]
                    with self.lock:
                        self.values[key]=(time.monotonic()+300,result)
                        while len(self.values)>512:self.values.popitem(last=False)
                        self.jobs.pop(key,None)
                    future.set_result(result)
            except BaseException as error:
                for key,_,_,future in batch:
                    with self.lock:self.jobs.pop(key,None)
                    if not future.done():future.set_exception(error)

CACHE=SemanticCache()

def grade(item,answer,encoder):
    """Expected/source metadata is always server retrieved, never client supplied."""
    started=time.perf_counter()
    canonical=item['canonicalAnswer'];kind=item['blankType']
    articles=kind!='ENTITY'
    expected=normalize(canonical,articles);actual=normalize(answer,articles)
    def result(verdict,reason):
        return {'verdict':verdict,'canonical_answer':canonical,'feedback':{
            'CORRECT':'Your answer matches the source meaning.',
            'PARTIAL':'You captured part of the idea. Compare the missing detail with the source.',
            'INCORRECT':'Review the expected answer and its source.'}[verdict],
            'source_pages':sorted(set(p for p in (item.get('pageStart'),item.get('pageEnd')) if isinstance(p,int))),
            'source_chunk_ids':item['sourceChunkIds'],'reason':reason,'grader_version':VERSION,
            'grading_ms':round((time.perf_counter()-started)*1000,2),'qwen_calls':0,'cuda_calls':0}
    if not actual or len(answer)>500 or len(actual.split())>64:return result('INCORRECT','EMPTY_OR_OVERLONG')
    # Quantities bypass spelling/embeddings, preserving decimals, signs and units.
    if kind in {'NUMBER','NUMBER_WITH_UNIT'}:
        return result('CORRECT' if quantity(canonical)==quantity(answer) and quantity(answer) is not None else 'INCORRECT','QUANTITY')
    if expected==actual:return result('CORRECT','NORMALIZED_IDENTITY')
    if actual in {normalize(v,articles) for v in item.get('acceptedAliases',[])}:return result('CORRECT','SOURCE_ALIAS')
    conflicts={normalize(v,articles) for v in item.get('conflictingTerms',[])}-{expected}
    if actual in conflicts:return result('INCORRECT','OTHER_SOURCE_ENTITY')
    if kind in {'TERM','ENTITY'}:
        safe_typo=any(typo(v,actual) for v in [expected,*[normalize(v,articles) for v in item.get('acceptedAliases',[])]])
        return result('CORRECT' if safe_typo else 'INCORRECT','SAFE_TYPO' if safe_typo else 'TERM_IDENTITY')
    if NEGATION.search(actual) and not NEGATION.search(expected):return result('INCORRECT','NEGATION')
    if len(NEGATION.findall(actual))>len(NEGATION.findall(expected)):return result('INCORRECT','NEGATION')
    # Omitting a negated purpose can be partial; explicitly affirming that
    # same predicate reverses the source even when embeddings are very close.
    if not NEGATION.search(actual):
        negated=re.findall(r'\b(?:not|never|no|cannot|without)\s+(\w+)',expected)
        if any(re.search(r'\b'+re.escape(word)+r'\b',actual) for word in negated):
            return result('INCORRECT','NEGATED_PREDICATE_REVERSED')
    if re.search(r'\b(?:multiple|several|many)\b',expected) and re.search(r'\b(?:only one|single|one frame)\b',actual):return result('INCORRECT','QUANTIFIER_CONFLICT')
    if re.search(r'\b(?:only one|single)\b',expected) and re.search(r'\b(?:multiple|several|many)\b',actual):return result('INCORRECT','QUANTIFIER_CONFLICT')
    numbers=lambda text:[quantity(v) for v in re.findall(r'(?<!\w)[+-]?\d+(?:\.\d+)?(?:\s*[a-z%]+)?',text)]
    if numbers(expected)!=numbers(actual):return result('INCORRECT','NUMERIC_CONFLICT')
    if any(len(term)>3 and term not in expected and re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',actual) for term in conflicts):
        return result('INCORRECT','OTHER_SOURCE_ENTITY')
    for left,right in [('sender','receiver'),('transmission','reception'),('outgoing','incoming'),
                       ('earliest','latest'),('largest','smallest'),('first','last'),('increases','decreases')]:
        for a,b in ((left,right),(right,left)):
            if re.search(r'\b'+a+r'\b',expected) and not re.search(r'\b'+b+r'\b',expected) and re.search(r'\b'+b+r'\b',actual) and not re.search(r'\b'+a+r'\b',actual):
                return result('INCORRECT','ROLE_OR_DIRECTION_CONFLICT')
    expected_main=re.split(r'\b(?:so that|so|to protect|while)\b',expected)[0]
    actual_main=re.split(r'\b(?:so that|so|to protect|while)\b',actual)[0]
    for a,b in [('sender','receiver'),('receiver','sender')]:
        if re.search(r'\b'+a+r'\b',expected_main) and not re.search(r'\b'+b+r'\b',expected_main) and re.search(r'\b'+b+r'\b',actual_main) and not re.search(r'\b'+a+r'\b',actual_main):
            return result('INCORRECT','MAIN_CLAUSE_ROLE_CONFLICT')
    parts=[p.strip() for p in re.split(r'\b(?:so that|so|in order to|while|and)\b',expected) if len(p.split())>=3]
    parts=parts if len(parts)>1 else [expected]
    # Student -> canonical, evidence, then each material clause. Source context
    # and clause coverage are required in addition to whole-answer similarity.
    sims=CACHE.similarities([actual,expected,normalize(item['sourceExcerpt']),*parts],encoder)
    semantic,evidence=sims[:2];clauses=sims[2:]
    expected_frame,student_frame=rate_frame(expected),rate_frame(actual)
    if expected_frame and student_frame and expected_frame[0]==student_frame[0]:
        if expected_frame==student_frame:return result('CORRECT','SOURCE_RATE_RELATION')
        if expected_frame[1] and not student_frame[1]:return result('PARTIAL','MISSING_RECEIVER_PURPOSE')
    has_predicate=kind!='DESCRIPTION' or answer_type(actual)=='DESCRIPTION'
    if semantic>=.75 and evidence>=.55 and all(s>=.66 for s in clauses) and has_predicate:return result('CORRECT','SOURCE_PHRASE')
    expected_words=set(expected.split())-STOP;actual_words=set(actual.split())-STOP
    overlap=len(expected_words&actual_words)/max(1,len(actual_words))
    if semantic>=.55 and evidence>=.4 and (overlap>=.6 or any(s>=.73 for s in clauses)):
        return result('PARTIAL','INCOMPLETE_PHRASE')
    return result('INCORRECT','PHRASE_NOT_ESTABLISHED')
