"""Strict informational grammar; causal and negated clauses fall through.

Expanded to recognise common informational book questions (main character,
themes, overview, summary, setting, etc.) while keeping strict exclusions
for causal / temporal / relationship / adversarial queries.
"""
import re


# ============================================================
# CAUSAL / CLAIM EXCLUSION WORDS
#
# If ANY of these appear in the normalised question the query
# is NOT classified as purely informational.  This prevents
# claim-style questions from bypassing strict validation.
# ============================================================

_CAUSAL_EXCLUSION_WORDS = frozenset({
    'why', 'because', 'cause', 'caused', 'prove', 'proves',
    'before', 'after', 'betray', 'betrayed', 'defeat',
    'defeated', 'intentionally', 'deliberately', 'poison',
    'poisoned', 'murder', 'murdered', 'kill', 'killed',
})

# Patterns that indicate a relationship query (strict validation)
_RELATIONSHIP_PATTERNS = [
    re.compile(r"who\s+is\s+\w+'s\s+", re.IGNORECASE),
    re.compile(r"what\s+is\s+the\s+relationship\s+between", re.IGNORECASE),
    re.compile(r"who\s+is\s+\w+\s+to\s+\w+", re.IGNORECASE),
]


def _normalise(question):
    """Normalise a question for pattern matching.

    - lowercase
    - collapse whitespace
    - strip trailing punctuation
    - expand common contractions
    - remove filler words (``of this book``, ``in this book``)
    """
    key = ' '.join(question.lower().split())
    # strip trailing punctuation
    key = key.rstrip('?.!,;:')
    # expand contractions
    key = key.replace("what's", "what is").replace("who's", "who is")
    key = key.replace("it's", "its")
    # remove trailing "of this book" / "in this book" / "of the book"
    key = re.sub(r'\s+(?:of|in|for)\s+(?:this|the)\s+book$', '', key)
    # remove leading filler
    key = re.sub(r'^(?:can you |please |could you )', '', key)
    return key.strip()


# ============================================================
# GROUNDED BOOK AUTHOR
# ============================================================

def grounded_book_author(question, evidence_items, work_id):
    key = _normalise(question)
    if key not in {'what is the author', 'who is the author',
                   'what is the author of this book', 'who is the author of this book',
                   'who wrote this book', 'who is the writer'}:
        return False
    if not work_id or not re.fullmatch(r'OL\d+W', work_id) or not evidence_items:
        return False
    authors = {str(item.get('author') or '').strip() for item in evidence_items}
    return (len(authors) == 1 and next(iter(authors)).lower() not in {'', 'unknown', 'n/a', 'none'}
            and all(item.get('work_id') == work_id and item.get('title') and item.get('chunk_id') for item in evidence_items))


# ============================================================
# GROUNDED BOOK OVERVIEW
#
# Expanded from 3 exact queries to ~20 normalised patterns.
# Still requires multiple substantive, uniquely identified
# passages from one indexed book.
# ============================================================

_OVERVIEW_PATTERNS = frozenset({
    # summary
    'what is the summary',
    'what is its summary',
    'what is a summary',
    'give me a summary',
    'give me the summary',
    'summarize this book',   
    'summarise this book',
    'provide a summary',
    # about / overview
    'what is this book about',
    'what is the book about',
    'what is it about',
    # themes
    'what are the major themes',
    'what are the main themes',
    'what are the themes',
    'what are its themes',
    # characters (overview-type, not claim)
    'who is the main character',
    'who is the protagonist',
    'who are the main characters',
    'who are the important characters',
    'who are the major characters',
    'who are the characters',
    # setting
    'where does the story take place',
    'where is the story set',
    'what is the setting',
    # plot
    'what happens in the story',
    'what happens in the book',
    'what is the plot',
    'what is the storyline',
})


def grounded_book_overview(question, evidence_items, work_id):
    """A scoped request to summarize supplied text asserts no factual premise.

    Require multiple substantive, uniquely identified passages from one indexed
    book. This never establishes a topical, causal, character or temporal claim.
    """
    key = _normalise(question)
    if key not in _OVERVIEW_PATTERNS:
        return False
    if not work_id or not re.fullmatch(r'OL\d+W', work_id) or len(evidence_items) < 3:
        return False
    return (
        all(item.get('work_id') == work_id and item.get('title')
            and item.get('chunk_id') and len(item.get('text', '').strip()) >= 200
            for item in evidence_items)
        and len({item['chunk_id'] for item in evidence_items}) >= 3
    )


# ============================================================
# IS INFORMATIONAL BOOK QUERY
#
# Returns a string tag describing the informational category
# or None if the query is not a simple informational question.
#
# Categories: 'author', 'character', 'overview', 'summary',
#             'themes', 'setting', 'plot', 'factual'
#
# Used by the fast filter and validator to apply appropriate
# grounding logic (evidence-sufficiency rather than
# claim-validation).
# ============================================================

def is_informational_book_query(question):
    """Classify whether *question* is a simple informational book question.

    Returns a category string ('author', 'character', 'overview', 'summary',
    'themes', 'setting', 'plot', 'factual') or ``None`` if the query is
    causal, temporal, relationship, or adversarial.

    Conservative: when in doubt, returns None so the query falls through
    to full claim-oriented validation.
    """
    key = _normalise(question)
    words = set(key.split())

    # ---- Exclusion: causal / adversarial / relationship ----
    if words & _CAUSAL_EXCLUSION_WORDS:
        return None
    for pat in _RELATIONSHIP_PATTERNS:
        if pat.search(question):
            return None
    # "did X do Y" / "does X prove" patterns
    if re.match(r'^did\s+', key) or re.match(r'^does\s+.*\s+prove', key):
        return None

    # ---- Author ----
    if re.match(r'^(?:who\s+(?:is|was|wrote)\s+the\s+(?:author|writer))', key):
        return 'author'
    if key in {'who wrote this book', 'who is the author', 'what is the author'}:
        return 'author'

    # ---- Character ----
    # "who is the main character" / "who is the protagonist"
    if re.match(r'^who\s+(?:is|are)\s+the\s+(?:main|primary|central|important|major|key)\s+character', key):
        return 'character'
    if re.match(r'^who\s+(?:is|are)\s+the\s+protagonist', key):
        return 'character'
    if re.match(r'^who\s+are\s+the\s+characters\b', key):
        return 'character'
    # "who is [Name]" — single entity lookup (NOT "who is X to Y" or "who is X's Y")
    m = re.match(r'^who\s+is\s+([a-z][a-z\s]{1,40})$', key)
    if m and 'to' not in key.split() and "'" not in question:
        return 'character'

    # ---- Overview ----
    if key in {'what is this book about', 'what is the book about', 'what is it about'}:
        return 'overview'

    # ---- Summary ----
    if re.match(r'^(?:what\s+is\s+(?:the|its|a)\s+summary|give\s+me\s+(?:a|the)\s+summary|summarize|summarise|provide\s+a\s+summary)', key):
        return 'summary'

    # ---- Themes ----
    if re.match(r'^what\s+(?:is|are)\s+(?:the|its)\s+(?:main|major|key|central|primary|important)?\s*themes?', key):
        return 'themes'

    # ---- Setting ----
    if re.match(r'^(?:where\s+(?:does|did|is)\s+(?:the\s+)?(?:story|book|novel|narrative)\s+(?:take\s+place|set|occur))', key):
        return 'setting'
    if key in {'what is the setting'}:
        return 'setting'

    # ---- Plot ----
    if re.match(r'^what\s+happens\s+in\s+(?:the|this)\s+(?:story|book|novel)', key):
        return 'plot'
    if key in {'what is the plot', 'what is the storyline'}:
        return 'plot'

    return None


# ============================================================
# ORDINARY BOOK INTENT
#
# Expanded template set with normalised matching.
# ============================================================

def ordinary_book_intent(question):
    key = _normalise(question)
    templates = {
        # summaries
        'what is the summary': ('is summarized', 'summary'),
        'what is its summary': ('is summarized', 'summary'),
        'what is a summary': ('is summarized', 'summary'),
        'give me a summary': ('is summarized', 'summary'),
        'give me the summary': ('is summarized', 'summary'),
        'summarize this book': ('is summarized', 'summary'),
        'summarise this book': ('is summarized', 'summary'),
        'provide a summary': ('is summarized', 'summary'),
        # overview
        'what is this book about': (None, 'overview'),
        'what is the book about': (None, 'overview'),
        'what is it about': (None, 'overview'),
        # author
        'what is the author': (None, 'author'),
        'who is the author': (None, 'author'),
        'who wrote this book': (None, 'author'),
        # characters
        'who is the main character': (None, 'main character'),
        'who is the protagonist': (None, 'main character'),
        'who are the main characters': (None, 'main characters'),
        'who are the important characters': (None, 'main characters'),
        'who are the major characters': (None, 'main characters'),
        'who are the characters': (None, 'main characters'),
        # themes
        'what is the main theme': (None, 'main theme'),
        'what are the main themes': (None, 'major themes'),
        'what are the major themes': (None, 'major themes'),
        'what are the themes': (None, 'major themes'),
        'what are its themes': (None, 'major themes'),
        # setting
        'where does the story take place': (None, 'setting'),
        'where is the story set': (None, 'setting'),
        'what is the setting': (None, 'setting'),
        # plot
        'what happens in the story': (None, 'plot'),
        'what happens in the book': (None, 'plot'),
        'what is the plot': (None, 'plot'),
        'what is the storyline': (None, 'plot'),
    }
    if key not in templates:
        # "who is [Name]" — entity lookup
        m = re.match(r'^who\s+is\s+([a-z][a-z\s]{1,40})$', key)
        if m and 'to' not in key.split() and "'" not in question:
            name = m.group(1).strip()
            return {'intent': 'FACTUAL', 'actor': name, 'action': None,
                    'target': None, 'polarity': 'positive',
                    'temporal_relation': None, 'question_focus': 'character',
                    'tier_used': 'Tier 1 (character lookup)'}

        # These grammar forms identify an explicit topic, not a character's
        # motivation or an asserted event. Evidence validation still runs.
        topic = re.fullmatch(r'does this book discuss ([a-z]+(?:[ -][a-z]+){0,4})', key)
        definition = re.fullmatch(r'what is (?:a|an) ([a-z]+(?:[ -][a-z]+){0,3})', key)
        match = topic or definition
        if match is None:
            return None
        subject = match.group(1)
        if set(subject.split()) & {'why', 'how', 'when', 'before', 'after', 'because', 'if', 'not', 'never', 'without', 'whose', 'who'}:
            return None
        return {'intent': 'FACTUAL', 'actor': 'the book' if topic else subject,
                'action': f'discuss {subject}' if topic else None,
                'target': subject if topic else None, 'polarity': 'positive',
                'temporal_relation': None, 'question_focus': None if topic else 'definition',
                'tier_used': 'Tier 1 (explicit informational topic)'}
    action, focus = templates[key]
    return {'intent': 'FACTUAL', 'actor': 'the book', 'action': action,
            'target': None, 'polarity': 'positive', 'temporal_relation': None,
            'question_focus': focus, 'tier_used': 'Tier 1 (generic informational)'}
