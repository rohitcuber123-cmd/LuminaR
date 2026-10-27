"""Bounded source-evidenced recognizers; no catalogue/model/authorization IO."""
from dataclasses import dataclass, asdict
import re
import unicodedata

@dataclass
class Candidate:
    field: str
    operator: str
    normalized_value: object
    source_span_start: int
    source_span_end: int
    source_text: str
    recognizer_id: str
    specificity: int = 100
    support_status: str = 'SUPPORTED'
    repair_provenance: str | None = None

class Source:
    def __init__(self, raw):
        self.raw=raw; chars=[]; self.offsets=[]
        for i,char in enumerate(raw):
            for c in unicodedata.normalize('NFKC',char).casefold():
                chars.append({'−':'-','－':'-','–':'-'}.get(c,c));self.offsets.append(i)
        self.text=''.join(chars);self.items=[];self.protected=[]
        for m in re.finditer(r'"[^"\n]*"|“[^”\n]*”|\bOL\d+W\b|\b(?:\d[ -]?){9,12}[\dXx]\b|(?<!\w)(?:C\+\+|C#|\.NET\s+\d+(?:\.\d+)?)(?!\w)|\b(?:Python|Windows|Dune)\s+\d+(?:\.\d+)?\b|\bCatch-\d+\b|\bThe Three-Body Problem\b',raw,re.I):
            self.protected.append((m.start(),m.end()))

    def span(self,a,b):
        return (self.offsets[a],self.offsets[b-1]+1) if b>a else (0,0)

    def free(self,a,b):
        x,y=self.span(a,b)
        return not any(x<e and y>s for s,e in self.protected) and not any(x<c.source_span_end and y>c.source_span_start for c in self.items)

    def add(self,field,op,value,m,rid,support='SUPPORTED',repair=None):
        a,b=m.span()
        self.add_span(field,op,value,a,b,rid,support,repair)

    def add_span(self,field,op,value,a,b,rid,support='SUPPORTED',repair=None):
        if not self.free(a,b):return
        x,y=self.span(a,b)
        self.items.append(Candidate(field,op,value,x,y,self.raw[x:y],rid,100,support,repair))

    def scan(self,pattern,field,op,value,rid,support='SUPPORTED',repair=None):
        for m in re.finditer(pattern,self.text,re.I):
            self.add(field,op(m) if callable(op) else op,value(m) if callable(value) else value,m,rid,support,repair)

    def remaining(self, protect=True):
        chars=list(self.text)
        ranges=[(c.source_span_start,c.source_span_end) for c in self.items]+(self.protected if protect else [])
        for i,original in enumerate(self.offsets):
            if any(a<=original<b for a,b in ranges):chars[i]=' '
        return ''.join(chars)

    def segment(self,start,end):
        # A known consumed span is a clause boundary. Ordinary doubled user
        # whitespace is not; preserving it avoids truncating multiword names
        # and exclusions while retaining the original source offset map.
        original=self.offsets[start] if start<len(self.offsets) else len(self.raw)
        for c in self.items:
            if c.source_span_start>=original:
                position=next((i for i,n in enumerate(self.offsets) if n>=c.source_span_start),end)
                end=min(end,position)
        delimiter=re.search(r'[;]',self.text[start:end])
        if delimiter:end=start+delimiter.start()
        return self.text[start:end].rstrip()

from search.query_numeric import (
    COMPARATOR_PATTERN, RATING_NUMBER_PATTERN, comparator,
    recognize_ratings, recognize_years,
)

NUM = '(' + RATING_NUMBER_PATTERN + ')'
OPS = '(' + COMPARATOR_PATTERN + ')'

def ratings(s):
    recognize_ratings(s)

def years(s):
    recognize_years(s)

def formats_availability(s):
    s.scan(r'\bavailable to borrow physically\b','availability','=','PHYSICAL_REQUESTABLE','availability.physical_request')
    s.scan(r'\b(?:but not|not|nothing|without|excluding|exclude|except|minus|disallow|forbid)\s+(physical|online|digital)(?:\s+books?)?\b','excluded_format','NOT',lambda m:'PHYSICAL' if m[1]=='physical' else 'ONLINE','format.exclusion')
    s.scan(r'\b(physical|online|digital)\s+(?:(?:must|should)\s+be\s+|is\s+)?(?:excluded|forbidden|absent)\b','excluded_format','NOT',lambda m:'PHYSICAL' if m[1]=='physical' else 'ONLINE','format.postfix_exclusion')
    s.scan(r'\b(?:require\s+)?both\s+(?:versions|formats)\b','format','PRESENT','BOTH','format.both_versions')
    s.scan(r'\b(?:both\s+)?(?:physical\s*(?:\+|and)\s*(?:online|digital)|(?:online|digital)\s+and\s+physical(?:ly)?)(?:\s+copies)?\b','format','PRESENT','BOTH','format.combined')
    s.scan(r'\b(?:only[ -]+)?(?:online|digital(?:ly)?)(?:[ -]+only)?\b','format',lambda m:'ONLY' if 'only' in m[0] else 'PRESENT','ONLINE','format.online')
    s.scan(r'\b(?:only[ -]+)?(?:physically|physical|hard cop(?:y|ies))(?:[ -]+only)?\b','format',lambda m:'ONLY' if 'only' in m[0] else 'PRESENT','PHYSICAL','format.physical')
    s.scan(r'\b(?:available\s+to\s+request|(?:books?\s+)?i can request)\b','availability','=','REQUESTABLE','availability.request')
    s.scan(r'\b(?:available now|available copies|access now)\b','availability','=','AVAILABLE_NOW','availability.now')
    if re.search(r'\bavailable\s+physically\s+(?:today|now)\b',s.text):
        s.scan(r'\bavailable\b|\b(?:today|now)\b','availability','=','PHYSICAL_NOW','availability.physical_now')
    s.scan(r'\bcurrently not on loan\b','availability','=','NOT_ON_LOAN','availability.copy_status','UNSUPPORTED')
    s.scan(r'\blanguage\s*[:=]?\s*([a-z][a-z-]{1,59})\b','language','EXACT',lambda m:m[1],'language.explicit')

def unsupported_and_sorts(s):
    s.scan(r'\bif\s+not\b[^;]*\botherwise\b[^;]*','boolean_subject_logic','CONDITIONAL',lambda m:m[0],'boolean.conditional_subject','UNSUPPORTED')
    if re.search(r'\b(?:online|digital|physical)\b[^;]*\bor\b[^;]*\b(?:online|digital|physical)\b',s.text):
        s.scan(r'^.+$','boolean','OR',lambda m:m[0],'boolean.format_disjunction','UNSUPPORTED')
    s.scan(r'\b(?:highest rated|sort by rating)\b','sort','=','RATING','sort.rating')
    s.scan(r'\b(?:newest first|sort by newest)\b','sort','=','NEWEST','sort.newest')
    s.scan(r'\bsort by (relevance|title)\b','sort','=',lambda m:m[1].upper(),'sort.explicit')
    s.scan(r'\b(?:oldest first|sort by author)\b','sort','=',lambda m:m[0],'sort.unsupported','UNSUPPORTED')
    s.scan(r'\b(?:under|over|at most|at least|less than|more than)\s+\d+\s+pages?\b','pages','=',lambda m:m[0],'pages.unsupported','UNSUPPORTED')
    s.scan(r'\b(?:first|second|third|fourth|\d+(?:st|nd|rd|th)?)\s+edition\b','edition','=',lambda m:m[0],'edition.unsupported','UNSUPPORTED')
    s.scan(r'\b(?:a\s+)?(?:revised|latest|new|updated)\s+edition\b','edition','=',lambda m:m[0],'edition.revised','UNSUPPORTED')
    s.scan(r'\bonly\s+books?\s+in\s+([a-z-]+)\b','language','EXACT',lambda m:m[1],'language.strict_unavailable','UNSUPPORTED')
    s.scan(r'\b(?:hardcover|paperback)\s+binding\s+only\b','binding','=',lambda m:m[0],'binding.unsupported','UNSUPPORTED')
    s.scan(r'\b(?:costing|price)\s+(?:under|over|at most|at least)\s+\d+(?:\.\d+)?\s+(?:dollars?|rupees?)\b','price','=',lambda m:m[0],'price.unsupported','UNSUPPORTED')
    s.scan(r'\b(?:difficulty|audience)\s*(?:level\s*)?[:=]\s*[a-z-]+\b','audience','=',lambda m:m[0],'audience.unsupported','UNSUPPORTED')
    s.scan(r'\b(?:reading\s+level|audience|per-copy\s+status)\s*(?::|=|must\s+be|only)\s*[a-z0-9-]+\b','audience','=',lambda m:m[0],'strict.unavailable','UNSUPPORTED')

def topical_not(text, start):
    """A prose negation does not itself authorize a catalogue predicate."""
    before=text[:start]
    after=text[start:]
    return bool(re.search(r'\b(?:about|on|word|phrase|why|do|does|did|are|is|was|were)\s*$',before)
                or re.match(r'not\s+(?:just|only|a\s+(?:beginner|subject|filter))\b',after)
                or re.search(r'\b(?:where|characters|things\s+that)\b[^,;]*$',before))


def subject_requirements(s, vocab):
    """Finite mandatory/forbidden subject syntax, resolved in current scope."""
    patterns = [
        (r'\b(must\s+(?:never\s+)?be|require|forbid)\s+([^,;]+?)(?=\s+(?:and|but|while)\b|[,;]|$)', 'prefix'),
        (r'\b([^,;]+?)\s+(is\s+(?:required|forbidden)|is\s+mandatory|must\s+be\s+absent)\b', 'postfix'),
    ]
    for pattern, form in patterns:
        for m in re.finditer(pattern,s.remaining()):
            cue,operand=(m[1],m[2]) if form=='prefix' else (m[2],m[1])
            operand=re.sub(r'^\s*(?:(?:and|but|while)\s+)?(?:the\s+)?','',operand)
            operand=re.split(r'\s+(?:and|but|while)\s+',operand,maxsplit=1)[0]
            operand=operand.rstrip(' .!?')
            operand=re.sub(r'\s+subject\s*$','',operand).strip()
            subject,_,_=vocab.resolve(operand,fuzzy=False)
            if not subject:continue
            negative=bool(re.search(r'never|forbid|forbidden|absent',cue))
            if form=='prefix':
                stop=m.start(2)+m[2].find(operand)+len(operand)
                if s.text[stop:stop+8]==' subject':stop+=8
                a,b=m.start(),stop
            else:
                a=m.start(1)+m[1].find(operand);b=m.end()
            s.add_span('excluded_subject' if negative else 'subject','NOT' if negative else 'INCLUDE',subject,a,b,'subject.requirement')


def subject_clauses(s, facets):
    """Bound explicit clauses before overlap resolution; resolve only scoped aliases.

    The existing plan requires ALL included subjects and excludes ANY listed
    subject. An explicit include-OR is not representable and is rejected.
    Lookups are bounded by input tokens, never by a regex for every facet.
    """
    from search.query_plan import FacetVocabulary
    vocab = FacetVocabulary(facets)
    subject_requirements(s,vocab)
    # Affirmative category clauses terminate a preceding negative operand.
    # Only an entire scoped canonical operand licenses this interpretation;
    # arbitrary prose containing "in" or "finding" remains untouched.
    for m in re.finditer(r'(?:,\s*just\b|\bwhen\s+finding\b|\bin\b)\s+([^,;]+)',s.remaining()):
        prefix=s.remaining()[:m.start()]
        if not re.search(r'\b(?:not|no|exclude|excluding|without|except|avoid)\b',prefix):continue
        operand=m[1].rstrip(' .!?')
        subject,_,_=vocab.resolve(operand,fuzzy=False)
        if subject:s.add_span('subject','INCLUDE',subject,m.start(),m.start(1)+len(operand),'subject.affirmative_after_negative')
    masked = s.remaining()
    markers = list(re.finditer(r'\b(?:i\s+am\s+not\s+looking\s+for|please\s+avoid|avoid|leave\s+out|with\s+no|include|exclude|excluding|except|minus|without|with|but\s+not|not|no)\b(?!\s+only\b)', masked))
    if not markers and not re.search(r'\b(?:included|excluded)\b', masked):
        return
    for index, marker in enumerate(markers):
        cue = marker[0]
        # "no more than 2" names a comparator without a field; it is not a
        # text exclusion. Preserve it for the existing numeric ambiguity guard.
        if cue=='no' and re.match(r'no\s+(?:more|less|fewer|higher|lower)\s+than\s+'+RATING_NUMBER_PATTERN,masked[marker.start():]):continue
        # A topical negation belongs to the semantic phrase, e.g. about not
        # giving up / the word not. Explicit exclude and but not still apply.
        if cue=='not' and topical_not(masked,marker.start()):continue
        include = cue in ('include', 'with')
        end = markers[index+1].start() if index+1 < len(markers) else len(masked)
        segment = s.segment(marker.end(), end)
        if index+1 < len(markers):
            segment = re.sub(r'[\s,;]*(?:(?:but|and|then|while)\s*[,;]?\s*)+$', '', segment)
        segment = segment.rstrip(' ,;.!?')
        if cue in ('exclude','excluding','include') and segment.strip() in ('subject','the subject'):
            s.add_span('subject_clause','MISSING',cue,marker.start(),marker.end()+len(segment),'subject.missing_named_operand','INCOMPLETE')
            continue
        start = marker.end()
        leading = len(segment)-len(segment.lstrip())
        start += leading
        segment = segment.lstrip()
        qualifier=re.match(r'(?:(?:any|the)\s+)?(?:subject\s+)?',segment)
        if qualifier and qualifier.end():
            start+=qualifier.end();segment=segment[qualifier.end():]
        topical_exclusion=not include and segment.startswith('about ')
        if topical_exclusion:
            start+=6;segment=segment[6:]
        if not segment:
            if cue != 'with':
                s.add_span('subject_clause', 'MISSING', cue, marker.start(), marker.end(), 'subject.clause_incomplete', 'INCOMPLETE')
            continue
        if topical_exclusion:
            # About explicitly targets content, so canonical membership alone
            # cannot satisfy this request. Never add a category predicate too.
            s.add_span('exclude','TEXT_NOT',' '.join(segment.split()),marker.start(),start+len(segment),'negative.topic_content')
            continue
        # Longest exact phrase first preserves facets containing "and".
        # A canonical list must end at a clause/topic boundary; arbitrary tails
        # remain literal exclusions rather than narrowing to a shorter subject.
        cursor = 0
        found = []
        disjunction = False
        while cursor < len(segment):
            matches = []
            for token in re.finditer(r'\S+', segment[cursor:]):
                stop = cursor+token.end()
                term = segment[cursor:stop].rstrip(' ,;')
                subject, _, _ = vocab.resolve(term, fuzzy=False)
                if subject:
                    matches.append((cursor+len(term), subject))
            if not matches:
                break
            stop, subject = matches[-1]
            found.append((cursor, stop, subject))
            tail = segment[stop:]
            if not tail.strip() or re.match(r'\s+(?:about|on)\b', tail):
                cursor = len(segment)
                break
            separator = re.match(r'\s*(,|;|\band\b|\bor\b)\s*', tail)
            if not separator:
                break
            disjunction |= separator[1] == 'or'
            cursor = stop+separator.end()
            if cursor == len(segment):
                break
        incomplete_list = bool(found) and re.search(r'\b(?:and|or)\s*$', segment)
        complete = bool(found) and cursor == len(segment) and not incomplete_list
        if not complete:
            if incomplete_list:
                s.add_span('subject_clause', 'MISSING', segment, marker.start(), start+len(segment), 'subject.list_incomplete', 'INCOMPLETE')
            elif cue == 'include':
                s.add_span('subject_clause', 'UNRESOLVED', segment, marker.start(), start+len(segment), 'subject.clause_unknown', 'UNSUPPORTED')
            elif not include:
                s.add_span('exclude', 'NOT', ' '.join(segment.split()), marker.start(), start+len(segment), 'negative.explicit')
            # Preserve accepted unstructured negatives (e.g. not JavaScript).
            # "with" remains ordinary prose unless the entire subject resolves.
            continue
        if include and disjunction:
            s.add_span('subject_clause', 'OR', segment, marker.start(), start+len(segment), 'subject.boolean_unsupported', 'UNSUPPORTED')
            continue
        if not include and len(found)>1 and ',' in segment and not re.search(r'\b(?:and|or)\b',segment):
            s.add_span('subject_clause','UNRESOLVED_SCOPE',segment,marker.start(),start+len(segment),'subject.comma_scope_ambiguous','AMBIGUOUS')
            continue
        previous = marker.start()
        for a, b, subject in found:
            s.add_span('subject' if include else 'excluded_subject', 'INCLUDE' if include else 'NOT', subject,
                       previous, start+b, 'subject.explicit_include' if include else 'subject.explicit_exclude')
            previous = start+b
    # Postfix form is accepted only with a complete canonical operand.
    for m in re.finditer(r'([^,;]+?)\s+(included|excluded)\b', s.remaining()):
        operand = re.sub(r'^\s*(?:(?:but|and|then|while)\s+)?', '', m[1])
        subject, _, _ = vocab.resolve(operand, fuzzy=False)
        a = m.start(1)+len(m[1])-len(operand)
        s.add_span('subject' if m[2]=='included' else 'excluded_subject', 'INCLUDE' if m[2]=='included' else 'NOT', subject,
                   a, m.end(), 'subject.postfix', 'SUPPORTED' if subject else 'UNSUPPORTED')


def clause_connectors(s):
    # Consume only an entire grammatical gap BETWEEN consumed clauses. Words
    # such as "but" in a genuine topic are not globally deleted.
    items = sorted(s.items, key=lambda c: c.source_span_start)
    for left, right in zip(items, items[1:]):
        gap = s.raw[left.source_span_end:right.source_span_start]
        if gap.strip() and re.fullmatch(r'(?:\s|[,;]|\b(?:but|and|then|while)\b)+', gap, re.I):
            a = next(i for i,n in enumerate(s.offsets) if n>=left.source_span_end)
            b = next(i for i,n in enumerate(s.offsets) if n>=right.source_span_start)
            s.add_span('connector', 'GRAMMAR', None, a, b, 'subject.clause_connector')


def author_title_entities(s, facets):
    from search.query_plan import FacetVocabulary
    vocab=FacetVocabulary(facets)
    for m in re.finditer(r'\b(?:books?\s+(?:written\s+)?by|written\s+by|by)\s+([^,;]+)',s.remaining()):
        segment=s.segment(m.start(1),m.end(1))
        segment=re.split(r'\s+(?:about|on|excluding|exclude|but\s+not|rated|published|available|with\s+rating|online|physical)\b',segment,maxsplit=1)[0]
        value=' '.join(segment.strip(' .?!').split())
        # A publication boundary or an explicit field label is not a name.
        if not value or re.match(r'\d|(?:subject|category|genre)\b',value):continue
        s.add_span('author','CONTAINS',value,m.start(),m.start(1)+len(segment.rstrip()),'author.by')
        # Free prose before an author clause remains a soft topic. Strict
        # title evidence comes from the explicit title recognizer below.
    for m in re.finditer(r'\b(?:(?:books?\s+)?(?:titled|called|named)|the\s+title\s+is)\s+("[^"\n]+"|“[^”\n]+”|[^,;]+)',s.text):
        value=m[1].strip(' .?!').strip('"“”')
        a,b=s.span(*m.span())
        if value and not any(a<c.source_span_end and b>c.source_span_start for c in s.items):
            # Explicit title syntax owns its protected quoted operand. It can
            # never authorize numeric/subject parsing inside that operand.
            s.items.append(Candidate('title','CONTAINS',value,a,b,s.raw[a:b],'title.explicit'))


def exclusions_entities(s, facets=()):
    author_title_entities(s,facets)
    subject_clauses(s, facets)
    from search.query_plan import FacetVocabulary
    vocab=FacetVocabulary(facets)
    for m in re.finditer(r'\b(?:(?:filter\s+by|restrict\s+to)\s+)?(?:subject|category|genre)\s+([^,;]+)',s.remaining()):
        segment=s.segment(m.start(1),m.end(1)).strip(' .?!')
        if not segment:continue
        subject,_,_=vocab.resolve(segment,fuzzy=False)
        s.add_span('subject' if subject else 'subject_clause','INCLUDE' if subject else 'UNRESOLVED',subject or segment,
                   m.start(),m.start(1)+len(segment),'subject.explicit_field','SUPPORTED' if subject else 'UNSUPPORTED')
    # Work from the already masked constraints. An exclusion ends before the
    # next consumed span; it cannot swallow a following rating/year clause.
    for m in re.finditer(r'\b(?:but not|excluding|exclude|without|not)(?!\s+only\b)\s+([^,;]+)',s.remaining()):
        if m[0].startswith('not') and topical_not(s.remaining(),m.start()):continue
        segment=s.segment(m.start(1),m.end(1));value=' '.join(segment.strip(' .?!').split())
        if not value:continue
        s.add_span('exclude','NOT',value,m.start(),m.start(1)+len(segment),'negative.explicit')
    clause_connectors(s)
    s.scan(r'\b(?:short|shorter)\b','preference','SOFT','Prefer shorter books','preference.length')
    s.scan(r'\b(?:for\s+)?(?:beginners?(?:-friendly)?|first-year)\b','preference','SOFT','Introductory / beginner (preference)','preference.beginner')
    s.scan(r'\b(?:advanced|research-level)\b','preference','SOFT','Advanced (preference)','preference.advanced')

def recognize(raw, facets=()):
    s=Source(raw)
    s.scan(r'^\s*(?:(?:please\s+)?(?:find(?:\s+me)?|show(?:\s+me)?|search(?:\s+for)?|help\s+me\s+find)|(?:could|can)\s+you\s+(?:find|show(?:\s+me)?)|i\s+(?:am\s+looking\s+for|would\s+like(?:\s+to\s+find)?|want\s+to\s+find)|give\s+me)\s*[,;:]?\s+', 'connector','GRAMMAR',None,'grammar.request_prefix')
    s.scan(r'\s+please[?.!\s]*$','connector','GRAMMAR',None,'grammar.request_suffix')
    for recognizer in (unsupported_and_sorts,ratings,years,formats_availability):recognizer(s)
    exclusions_entities(s, facets)
    return s

