"""Structural entity guards, not natural-language intent interpretation."""
import unicodedata


def normalize(message):
    return ' '.join(unicodedata.normalize('NFKC', message).casefold().replace('\u2019', "'").split()).rstrip('.!?')


def generic_title(title):
    # Reject model-produced bare referents at the named-entity lookup gate.
    words = set(normalize(title).split())
    return bool(words) and words <= {
        'book', 'books', 'one', 'ones', 'this', 'that', 'these', 'those', 'the',
        'they', 'them', 'their', 'either', 'both', 'all', 'first', 'second',
        'third', 'fourth', 'last', 'other', 'selected', 'my', 'two', 'of', 'which',
    }
