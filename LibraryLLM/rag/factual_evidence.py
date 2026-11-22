"""Bounded checks for explicit factual assignments, not a general entailment model.

Only an unambiguous, bound relationship can establish deterministic support.
Other grammar falls through; explicit conflicts veto even a confident model.
Authorization and citation entitlement remain the caller's responsibility.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
import unicodedata

VERSION = 'explicit-facts-v1'
MAX_TEXT = 24000
NEGATION = re.compile(r"\b(?:not|never|no|neither|without|cannot)\b|n['’]t\b", re.I)
CAUSAL = re.compile(r'\b(?:why|because|before|after|motivates?|regrets?|relationship|happens|feels?)\b', re.I)
SIMPLE_QUESTION = re.compile(r'^(?:what\s+(?:is|was|are|were)\b|(?:what|which)\s+.+?\s+(?:(?:is|was|were)\s+(?:recorded|listed|specified)|(?:did|does|do)\b)|how\s+(?:many|much)\b|(?:is|was|are|were|did|does|do|has|have)\b)', re.I)
STOP = {'the','a','an','of','for','its','is','was','are','were','recorded','listed','specified','documented'}
UNIT = {'minute':('time',Decimal(60)), 'minutes':('time',Decimal(60)),
        'second':('time',Decimal(1)), 'seconds':('time',Decimal(1)), 's':('time',Decimal(1)),
        'ms':('time',Decimal('.001')), 'hour':('time',Decimal(3600)), 'hours':('time',Decimal(3600))}
VALUE = r'(?:\d{4}-\d{2}-\d{2}|[+-]?\d+(?:\.\d+)?(?:\s+[A-Za-z%]+)?|[A-Za-z][A-Za-z0-9_./:-]*)'


@dataclass(frozen=True)
class Assessment:
    verdict: str
    reason: str


def words(value):
    text = unicodedata.normalize('NFKC', value).casefold().replace("'s", '').replace('’s', '')
    return tuple(w for w in re.findall(r'[^\W_]+', text) if w not in STOP)


def literal_factual_intent(question):
    text = question.strip()
    if len(text) > 2000 or not SIMPLE_QUESTION.match(text) or CAUSAL.search(text):
        return None
    # This classifies the question's grammar, never the truth of its premise.
    target = re.sub(r'^(?:what|which|how many|how much|is|was|are|were|did|does|do|has|have)\s+', '', text, flags=re.I)
    target = re.sub(r'^(?:is|was|are|were)\s+(?:the\s+)?', '', target, flags=re.I).rstrip('?.!')
    return {'intent':'FACTUAL','actor':None,'action':None,'target':target,
            'polarity':'negative' if NEGATION.search(text) else 'positive',
            'temporal_relation':None,'question_focus':None,'tier_used':'Tier 1 (literal factual grammar)'}


def value_key(value):
    value = unicodedata.normalize('NFKC', value).strip(' \t\r\n.\"\'')
    number = re.fullmatch(r'([+-]?\d+(?:\.\d+)?)\s*([A-Za-z%]*)', value)
    if number:
        try:
            amount = Decimal(number[1])
            if not amount.is_finite() or abs(amount) > Decimal('1e30'): return None
        except InvalidOperation:
            return None
        unit = number[2].casefold()
        dimension, factor = UNIT.get(unit, ('unit:'+unit, Decimal(1))) if unit else ('number', Decimal(1))
        return ('quantity', dimension, amount * factor)
    # Identifiers are compared exactly, not with fuzzy/edit/embedding similarity.
    if re.fullmatch(VALUE, value): return ('identifier', value)
    return ('text', ' '.join(value.casefold().split()))


def _question(question):
    text = question.strip().rstrip('?.!')
    claim = re.fullmatch(r'(?i:Is|Was|Are|Were)\s+(.+?)\s+(?i:(not)\s+)?('+VALUE+r')', text)
    if claim:
        return words(claim[1]), value_key(claim[3]), bool(claim[2]), None
    match = re.fullmatch(r'(?:What|Which)\s+(.+?)\s+(?:is|was|are|were)\s+(?:recorded|listed|documented|specified)(?:\s+for\s+(.+))?', text, re.I)
    if match: return words(match[1]), None, False, words(match[2]) if match[2] else None
    match = re.fullmatch(r'What\s+(?:is|was|are|were)\s+(.+)', text, re.I)
    if match: return words(match[1]), None, False, None
    match = re.fullmatch(r'How\s+(?:many|much)\s+([a-z]+)(?:\s+.+)?', text, re.I)
    if match and match[1].casefold() in UNIT:
        return ('duration',), None, False, None
    return None


EVENTS = {
    'approve': 'approve', 'approved': 'approve', 'approves': 'approve',
    'reject': 'reject', 'rejected': 'reject', 'rejects': 'reject',
    'open': 'open', 'opened': 'open', 'opens': 'open',
    'close': 'close', 'closed': 'close', 'closes': 'close',
    'send': 'send', 'sent': 'send', 'sends': 'send',
    'record': 'record', 'recorded': 'record', 'records': 'record',
    'complete': 'complete', 'completed': 'complete', 'completes': 'complete',
    'pass': 'pass', 'passed': 'pass', 'passes': 'pass',
    'fail': 'fail', 'failed': 'fail', 'fails': 'fail',
}
EVENT_PATTERN = '|'.join(EVENTS)


def _event_assessment(question, texts):
    query = re.fullmatch(r'(?:did|does|do)\s+(.+?)\s+(not\s+)?(' + EVENT_PATTERN + r')\s+(.+?)[?.!]*', question.strip(), re.I)
    if not query:
        return None
    actor, negative, action, target = query.groups()
    expected = (words(actor), EVENTS[action.casefold()], words(target))
    signs = set()
    observed = False
    for text in texts:
        for clause in re.split(r'(?<=[.!?])\s+|\n+|;\s*', text):
            statement = re.fullmatch(r'(.+?)\s+(?:(did not|does not|never)\s+)?(' + EVENT_PATTERN + r')\s+(.+?)[.!?]*', clause.strip(), re.I)
            if not statement:
                continue
            subject, negation, verb, obj = statement.groups()
            observed = True
            if (words(subject), EVENTS[verb.casefold()], words(obj)) == expected:
                signs.add(bool(negation))
    if len(signs) > 1:
        return Assessment('UNCERTAIN', 'opposed assertions of the same actor/action/target')
    if signs:
        supported = bool(negative) in signs
        return Assessment('SUPPORTED' if supported else 'NOT_SUPPORTED', 'explicit actor/action/target and scoped polarity')
    return Assessment('NOT_SUPPORTED', 'actor/action/target relationship absent') if observed else None


def assess_factual_evidence(question, intent, items):
    if intent.get('intent', 'FACTUAL') != 'FACTUAL' or CAUSAL.search(question): return None
    if intent.get('question_focus'):
        # Existing informational book semantics retain their own validator.
        return None
    texts = [item.get('text','') for item in items if isinstance(item.get('text',''),str)]
    if sum(map(len,texts)) > MAX_TEXT:
        return Assessment('UNCERTAIN', 'factual evidence exceeds bounded inspection budget')
    if any(re.search(r'\b(?:ignore (?:previous|the)|pretend|supported\s*=|system\s*:|respond with)\b', t, re.I) for t in texts):
        return Assessment('UNCERTAIN', 'instruction-like evidence is not an entailment instruction')
    event = _event_assessment(question, texts)
    if event is not None: return event
    query = _question(question)
    if query is None: return None
    field, proposed, query_negative, anchor = query
    if not field: return None
    matches = []
    saw_assignments = False
    for text in texts:
        if anchor and not set(anchor) <= set(words(text)): continue
        previous = None
        for clause in re.split(r'(?<=[.!?])\s+|\n+|;\s*', text):
            if re.search(r'\b(?:ignore (?:previous|the)|pretend|supported\s*=|system\s*:|respond with)\b', clause, re.I):
                return Assessment('UNCERTAIN', 'instruction-like evidence is not an entailment instruction')
            clause = clause.strip().rstrip('.!?')
            assignment = re.fullmatch(r'(.+?)\s+(?:is recorded as|was recorded as|is|was|are|were|equals?)\s+(.+)', clause, re.I)
            duration = re.fullmatch(r'(.+?)\s+(?:takes?|lasts?|requires?)\s+('+VALUE+r')', clause, re.I)
            if duration:
                lhs, value, negative = words(duration[1]) + ('duration',), duration[2], False
            elif assignment:
                lhs = words(assignment[1]); value = assignment[2]
                negative = bool(re.match(r'not\s+',value,re.I))
                value = re.sub(r'^not\s+','',value,flags=re.I)
                if lhs in (('it',),('this',)) and previous:
                    return Assessment('UNCERTAIN', 'pronoun reference cannot independently establish factual support')
                if lhs and lhs[0] in ('no','neither'):
                    lhs = lhs[1:];negative=True
            else:
                continue
            saw_assignments = True
            previous = lhs
            if not set(field) <= set(lhs): continue
            if re.search(r'\b(?:some|all|every|each|if|unless|might|may|possibly)\b', clause, re.I):
                return Assessment('UNCERTAIN', 'quantified or conditional relationship needs interpretation')
            # A separately named subject cannot borrow a different heading's identity.
            if anchor and set(lhs)-set(field)-set(anchor): continue
            if re.fullmatch(r'(?:defined|recorded|listed|specified|available|known)',value,re.I):
                if negative: matches.append((None,True))
                continue
            if re.search(r'\b(?:or|and|but|might|may|possibly|if|unless|proposed|hypothetical)\b',value,re.I):
                return Assessment('UNCERTAIN','conditional or alternative factual value')
            matches.append((value_key(value),negative))
    if not matches:
        return Assessment('NOT_SUPPORTED','requested factual field/entity is absent') if saw_assignments else None
    positives = {value for value,negative in matches if not negative and value is not None}
    negatives = {value for value,negative in matches if negative and value is not None}
    if len(positives)>1 or positives & negatives:
        return Assessment('UNCERTAIN','conflicting values for the same factual relationship')
    if proposed is not None:
        if query_negative:
            supported = proposed in negatives and proposed not in positives
        else:
            supported = proposed in positives and proposed not in negatives
    else:
        supported = len(positives)==1
    return Assessment('SUPPORTED' if supported else 'NOT_SUPPORTED',
                      'unambiguous explicit factual relationship' if supported else 'factual value/polarity is not supported')
