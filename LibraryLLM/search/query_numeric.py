"""Versioned numeric comparison semantics, independent of parser/IO."""
import math
import re

COMPARATOR_VERSION = 'search-v2c-c3-comparators-1'
COMPARATOR_GROUPS = {
    '>': ('greater than', 'more than', 'higher than', 'above', 'over', 'exceeding', 'exceeds', 'exceed', '>'),
    '>=': ('at least', 'no less than', 'no lower than', 'no fewer than', 'not below', 'not less than', 'minimum', '>=', '≥'),
    '<': ('less than', 'fewer than', 'lower than', 'below', 'under', '<'),
    '<=': ('at most', 'no more than', 'no higher than', 'no greater than', 'not above', 'not more than', 'maximum', '<=', '≤'),
    '=': ('equal to', 'equals', 'equal', 'exactly', '='),
}
_COMPARATORS = {phrase: op for op, phrases in COMPARATOR_GROUPS.items() for phrase in phrases}


def _phrase(value):
    return re.escape(value).replace(r'\ ', r'[\s-]+')


COMPARATOR_PATTERN = '(?:' + '|'.join(_phrase(p) for p in sorted(_COMPARATORS, key=len, reverse=True)) + ')'
_WORDS = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5}
RATING_NUMBER_PATTERN = r'(?<![\w.])(?:-?(?:\d+(?:\.\d+)?|\.\d+)|(?:zero|one|two|three|four|five)(?:[\s-]+and[\s-]+a[\s-]+half)?)(?!\w|\.\d)'


def comparator(text):
    """Return a known exact operator; unknown grammar must never imply equality."""
    return _COMPARATORS.get(re.sub(r'[\s-]+', ' ', text.strip()))


def parse_rating_number(text):
    value = re.sub(r'[\s-]+', ' ', text.strip()) if not re.match(r'^-?\d|^\.', text.strip()) else text.strip()
    if value in _WORDS:
        return float(_WORDS[value])
    if value.endswith(' and a half') and value.removesuffix(' and a half') in _WORDS:
        return _WORDS[value.removesuffix(' and a half')] + .5
    return float(value)


def range_contradiction(low, high, low_exclusive=False, high_exclusive=False):
    return low is not None and high is not None and (low > high or low == high and (low_exclusive or high_exclusive))


def valid_numeric_domain(field, value):
    if value is None:
        return True
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return False
    if field == 'rating':
        return 0 <= value <= 5
    if field == 'year':
        return 1000 <= value <= 2100 and float(value).is_integer()
    return False


_RATING_FIELD = r'(?:(?:a|the)\s+)?(?:(?:review|average)\s+)?(?:ratings?|rated|scoring)'
_FIELD_GLUE = r'\s*(?:(?:is|are|of|must(?:\s+be)?|should(?:\s+be)?)\s+)?'
_UNIT = r'(?:[\s-]+stars?\b)'
_SUFFIX = r'(?:or\s+(?:higher|more|better|lower|less|fewer)|and\s+(?:above|below))'
_RANGE = r'(?:between|from|within)\s+(?P<lo>' + RATING_NUMBER_PATTERN + r')\s+(?:and|to|through)\s+(?P<hi>' + RATING_NUMBER_PATTERN + r')'
_GAP = r'[\s,;]*(?:(?:and|but)\s+)?(?:(?:stay|remain|be)\s+)?'
_TRAIL = r'(?![\w])'


def _add(source, match, field, op, value, recognizer):
    if recognizer in ('rating.unit_suffix', 'rating.star_unit', 'rating.exact_star_unit', 'rating.bare_plus', 'rating.pure_suffix'):
        # Unit-like wording inside an unresolved explicit entity is not field
        # evidence. A subsequent with/rating clause starts a separate filter.
        prefix = source.text[:match.start()]
        entity = list(re.finditer(r'\b(?:written\s+by|by|titled|called|title\s+is)\b', prefix))
        if entity and not re.search(r'[,;]|\b(?:with|ratings?|rated|scoring|published|released|issued|printed|publication)\b', prefix[entity[-1].end():]):
            return
    source.add(field, op, value, match, recognizer,
               repair='reordered field/operator with optional article/of'
               if recognizer=='rating.operator_field' else None)


def _previous_numeric(source, field, start):
    original = source.span(start, start + 1)[0]
    previous = [c for c in source.items if c.field == field and c.source_span_end <= original]
    if not previous:
        return False
    end = max(c.source_span_end for c in previous)
    return bool(re.fullmatch(_GAP, source.raw[end:original], re.I))


def _suffix_operator(text):
    return '<=' if re.search(r'lower|less|fewer|below', text) else '>='


def recognize_ratings(source):
    """Extract field/unit-evidenced rating clauses, then adjacent conjunctions.

    Pure coordinated comparator phrases and the accepted plus notation are the
    only fieldless numeric shorthands. Topic/title/author numbers are not cues.
    """
    text = source.text
    # Consume complete intervals before their individual numbers can match.
    for pattern, rid in (
        (r'\b' + _RATING_FIELD + _FIELD_GLUE + _RANGE + _UNIT + '?', 'rating.field_range'),
        (r'\b' + _RANGE + _UNIT, 'rating.unit_range'),
    ):
        for m in re.finditer(pattern, text):
            _add(source, m, 'rating', 'RANGE', [parse_rating_number(m['lo']), parse_rating_number(m['hi'])], rid)
    # Prefix minimum/maximum is not equality even when followed by a field.
    for m in re.finditer(r'\b(?P<op>minimum|maximum)\s+' + _RATING_FIELD + r'\s+(?:of\s+)?(?P<n>' + RATING_NUMBER_PATTERN + r')' + _UNIT + '?', text):
        _add(source, m, 'rating', comparator(m['op']), parse_rating_number(m['n']), 'rating.extremum')
    # A suffix belongs to the full field value, before a shorter equality match.
    for m in re.finditer(r'\b' + _RATING_FIELD + _FIELD_GLUE + r'(?P<n>' + RATING_NUMBER_PATTERN + r')' + _UNIT + r'?\s*(?P<suffix>' + _SUFFIX + r'|\+)(?!\w)', text):
        _add(source, m, 'rating', _suffix_operator(m['suffix']), parse_rating_number(m['n']), 'rating.field_suffix')
    for m in re.finditer(r'\b' + _RATING_FIELD + _FIELD_GLUE + r'(?P<op>' + COMPARATOR_PATTERN + r')\s*(?:a\s+)?(?:rating\s+)?(?:of\s+)?(?P<n>' + RATING_NUMBER_PATTERN + r')' + _UNIT + '?', text):
        _add(source, m, 'rating', comparator(m['op']), parse_rating_number(m['n']), 'rating.field_operator')
    for m in re.finditer(r'(?<!\w)(?P<op>' + COMPARATOR_PATTERN + r')\s+(?:a\s+)?' + _RATING_FIELD + r'\s+(?:of\s+)?(?P<n>' + RATING_NUMBER_PATTERN + r')' + _UNIT + '?', text):
        _add(source, m, 'rating', comparator(m['op']), parse_rating_number(m['n']), 'rating.operator_field')
    # Unit-led clauses: suffix first, then comparison, then plain exact stars.
    for m in re.finditer(r'(?P<n>' + RATING_NUMBER_PATTERN + r')' + _UNIT + r'\s+(?P<suffix>' + _SUFFIX + r')\b', text):
        _add(source, m, 'rating', _suffix_operator(m['suffix']), parse_rating_number(m['n']), 'rating.unit_suffix')
    for m in re.finditer(r'(?<!\w)(?P<op>' + COMPARATOR_PATTERN + r')\s+(?P<n>' + RATING_NUMBER_PATTERN + r')' + _UNIT, text):
        _add(source, m, 'rating', comparator(m['op']), parse_rating_number(m['n']), 'rating.star_unit')
    for m in re.finditer(r'\b' + _RATING_FIELD + _FIELD_GLUE + r'(?P<n>' + RATING_NUMBER_PATTERN + r')' + _UNIT + '?', text):
        _add(source, m, 'rating', '=', parse_rating_number(m['n']), 'rating.explicit_value')
    for m in re.finditer(r'(?P<n>' + RATING_NUMBER_PATTERN + r')' + _UNIT, text):
        _add(source, m, 'rating', '=', parse_rating_number(m['n']), 'rating.exact_star_unit')
    for m in re.finditer(r'(?P<n>' + RATING_NUMBER_PATTERN + r')\s*\+(?!\w|\+)' + _UNIT + '?', text):
        _add(source, m, 'rating', '>=', parse_rating_number(m['n']), 'rating.bare_plus')
    # Existing pure suffix construction: "4 or higher", not a topic mention.
    remaining = source.remaining().strip(' \t\r\n,.!?;')
    pure_suffix = re.fullmatch(r'(?P<n>' + RATING_NUMBER_PATTERN + r')\s+(?P<suffix>' + _SUFFIX + r')', remaining)
    if pure_suffix:
        for m in re.finditer(r'(?P<n>' + RATING_NUMBER_PATTERN + r')\s+(?P<suffix>' + _SUFFIX + r')\b', text):
            _add(source, m, 'rating', _suffix_operator(m['suffix']), parse_rating_number(m['n']), 'rating.pure_suffix')
    clause = r'(?P<op>' + COMPARATOR_PATTERN + r')\s*(?P<n>' + RATING_NUMBER_PATTERN + r')' + _UNIT + '?'
    plain_clause = r'(?:' + COMPARATOR_PATTERN + r')\s*' + RATING_NUMBER_PATTERN + _UNIT + '?'
    pure = bool(re.fullmatch(plain_clause + r'(?:\s+(?:and|but)\s+' + plain_clause + r')+', remaining))
    for m in re.finditer(r'(?<!\w)' + clause, text):
        if pure or _previous_numeric(source, 'rating', m.start()):
            _add(source, m, 'rating', comparator(m['op']), parse_rating_number(m['n']), 'rating.coordinated_bound')


YEAR_COMPARATOR_GROUPS = {
    '>': ('strictly after', 'later than', 'after', 'following', 'follow', 'follows', '>'),
    '>=': ('no earlier than', 'not before', 'at or after', 'on or after', 'since', '>=', '≥'),
    '<': ('strictly before', 'earlier than', 'before', 'preceding', 'precede', 'precedes', '<'),
    '<=': ('no later than', 'not after', 'at or before', 'on or before', 'by', '<=', '≤'),
    '=': ('dating to', 'during', 'in', 'of', '=', 'equal to', 'exactly'),
}
_YEAR_COMPARATORS = {phrase: op for op, phrases in YEAR_COMPARATOR_GROUPS.items() for phrase in phrases}
_YEAR_COMPARATORS.update(_COMPARATORS)
YEAR_COMPARATOR_PATTERN = '(?:' + '|'.join(_phrase(p) for p in sorted(_YEAR_COMPARATORS, key=len, reverse=True)) + ')'
_YEAR_NUMBER = r'(?<![\w.])-?\d+(?:\.\d+)?(?!\w|\.\d)'
_PUBLICATION = r'(?:(?:a|the)\s+)?(?:published|released|issued|printed|publication(?:\s+year)?)'
_YEAR_RANGE = r'(?:between|from|within)\s+(?P<lo>' + _YEAR_NUMBER + r')\s+(?:and|to|through)\s+(?P<hi>' + _YEAR_NUMBER + r')'


def _year_value(value):
    number = float(value)
    return int(number) if number.is_integer() else number


def _year_op(value):
    return _YEAR_COMPARATORS[re.sub(r'[\s-]+', ' ', value.strip())]


def recognize_years(source):
    """Publication evidence or preserved narrow catalogue/pure-year shorthand."""
    text = source.text
    for m in re.finditer(r'\b' + _PUBLICATION + _FIELD_GLUE + _YEAR_RANGE, text):
        _add(source, m, 'year', 'RANGE', [_year_value(m['lo']), _year_value(m['hi'])], 'year.publication_range')
    # Reordering is explicit field evidence, including a postfix year label.
    for m in re.finditer(r'\b(?P<op>after|before|from)\s+publication\s+year\s+(?P<n>' + _YEAR_NUMBER + r')', text):
        _add(source, m, 'year', '=' if m['op'] == 'from' else _year_op(m['op']), _year_value(m['n']), 'year.reordered_field')
    for m in re.finditer(r'\b(?P<op>after|before)\s+(?P<n>' + _YEAR_NUMBER + r')\s+in\s+publication\s+year\b', text):
        _add(source, m, 'year', _year_op(m['op']), _year_value(m['n']), 'year.postfix_field')
    for m in re.finditer(r'\b' + _PUBLICATION + _FIELD_GLUE + r'from\s+(?P<n>' + _YEAR_NUMBER + r')\s+onward\b', text):
        _add(source, m, 'year', '>=', _year_value(m['n']), 'year.publication_onward')
    for m in re.finditer(r'\b' + _PUBLICATION + _FIELD_GLUE + r'(?P<op>' + YEAR_COMPARATOR_PATTERN + r')\s*(?:the\s+year\s+)?(?P<n>' + _YEAR_NUMBER + r')', text):
        _add(source, m, 'year', _year_op(m['op']), _year_value(m['n']), 'year.publication')
    for m in re.finditer(r'\bbooks?\s+(?P<op>after|before)\s+(?:the\s+)?year\s+(?P<n>' + _YEAR_NUMBER + r')', text):
        _add(source, m, 'year', _year_op(m['op']), _year_value(m['n']), 'year.explicit_year')
    # Retain the previously accepted shorthand only when topical time is absent.
    historical = bool(re.search(r'\b(?:history|historical|events?|war|postwar|era|century)\b', text))
    catalogue = bool(re.search(r'\b(?:online|physical|digital)\b', text) and re.search(r'\bbooks?\b', text) and not historical)
    remainder = source.remaining().strip(' \t\r\n,.!?;')
    year_bound = r'(?:after|before)\s+' + _YEAR_NUMBER
    pure = bool(re.fullmatch(year_bound + r'(?:\s+(?:and\s+|but\s+)?' + year_bound + r')*', remainder))
    for m in re.finditer(r'(?<!\w)(?P<op>' + YEAR_COMPARATOR_PATTERN + r')\s*(?P<n>' + _YEAR_NUMBER + r')', text):
        if _previous_numeric(source, 'year', m.start()) or m['op'] in ('after', 'before') and (pure or catalogue):
            _add(source, m, 'year', _year_op(m['op']), _year_value(m['n']), 'year.coordinated_bound')
    for m in re.finditer(r'\b(?P<op>from)\s+(?P<n>' + _YEAR_NUMBER + r')\s+onward\b', text):
        prefix = text[:m.start()]
        if not historical and not re.search(r'\b(?:about|events?|of|era|war)\b', prefix):
            _add(source, m, 'year', '>=', _year_value(m['n']), 'year.catalogue_onward')
    # Legacy bounded year intervals require an empty or book-qualified prefix,
    # and no topical before/about/of/history vocabulary.
    for m in re.finditer(r'\b' + _YEAR_RANGE, text):
        prefix = text[:m.start()]
        if not re.search(r'\b(?:about|events?|of|era|war|history|historical)\b', prefix) and (not prefix.strip() or re.search(r'\bbooks?\b', prefix)):
            _add(source, m, 'year', 'RANGE', [_year_value(m['lo']), _year_value(m['hi'])], 'year.catalogue_range')
