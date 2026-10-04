"""Bounded book-reference grammar; never guesses titles or performs search."""
import re
import unicodedata


def normalize(message):
    phrase = ' '.join(unicodedata.normalize('NFKC', message).casefold().split())
    phrase = phrase.replace('’', "'").rstrip('.!?')
    # Only command-word typos, not a general spellchecker or title rewrite.
    return re.sub(r'\bdiffernces\b', 'differences', phrase)


PLURAL = r'(?:these(?: two)?(?: books)?|those books|them|the selected books|my selected books|my selections|the books i selected|all selected books|both(?: books)?|the two books)'
SINGULAR = r'(?:this(?: book| one)?|the selected book|my selected book)'
REFERENCE = rf'(?:{PLURAL}|{SINGULAR})'


def reference_kind(message):
    phrase = normalize(message)
    if re.search(r'\b(?:both(?: books)?|the two books|these two(?: books)?)\b', phrase):
        return 'two'
    if re.search(rf'\b{PLURAL}\b|\btheir (?:authors|subjects)\b', phrase):
        return 'plural'
    if re.search(rf'\b{SINGULAR}\b', phrase):
        return 'singular'
    return None


def generic_title(title):
    phrase = normalize(title)
    return phrase in {'book', 'books'} or bool(re.fullmatch(REFERENCE, phrase))


def comparison_fields(message):
    phrase = normalize(message)
    patterns = [
        rf'compare {PLURAL}(?: by (rating|availability))?',
        r'compare their (authors|subjects)',
        rf'(?:what are the |what is the |what\'s the )?(?:differences?|comparison) (?:in|between|among) {PLURAL}',
        rf"(?:what's|what is) different about {PLURAL}",
        rf'how (?:are|do) {PLURAL} (?:differ|different|compare)',
        rf'which features differ between {PLURAL}',
    ]
    for pattern in patterns:
        match = re.fullmatch(pattern, phrase)
        if match:
            return [match.group(1)] if match.lastindex and match.group(1) else []
    return None


def selected_command(message):
    """Return a high-confidence operation only for complete closed grammars."""
    phrase = normalize(message)
    fields = comparison_fields(phrase)
    if fields is not None:
        return 'compare', fields
    if re.fullmatch(rf'(?:recommend(?: (?:something|books))? (?:based on|from) {REFERENCE}|what should i read based on {REFERENCE}|find books like {REFERENCE})', phrase):
        return 'recommend', []
    if re.fullmatch(rf'(?:(?:is|are) {REFERENCE} available(?: (?:now|today))?|availability of {REFERENCE}|which of {PLURAL} are available|can i borrow {REFERENCE})', phrase):
        return 'availability', []
    if re.fullmatch(rf'(?:tell me about|details about) {SINGULAR}|who wrote {SINGULAR}|what subjects does {SINGULAR} have', phrase):
        return 'details', []
    return None
