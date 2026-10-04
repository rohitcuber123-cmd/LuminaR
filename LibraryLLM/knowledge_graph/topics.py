"""Deterministic adjacent source phrases, ranked using corpus degree/TF-IDF."""
from collections import Counter
import hashlib
import math
import re
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
from knowledge_graph.core import canonical
from knowledge_graph.relations import TOPIC_POLICY

STOP = frozenset(ENGLISH_STOP_WORDS) | {'book', 'books', 'story', 'stories', 'guide', 'novel', 'novels',
    'new', 'edition', 'editions', 'introduction', 'author', 'authors', 'reader', 'readers', 'volume',
    'copyright', 'http', 'https', 'www', 'isbn', 'paperback', 'hardcover', 'publisher', 'published'}
WORD = re.compile(r'\b[^\W\d_]{3,40}\b', re.UNICODE)


def description_hash(value):
    return hashlib.sha256(canonical(value or '').encode('utf-8')).hexdigest()


def phrases(description):
    if not isinstance(description, str):
        return Counter()
    source = canonical(description)
    if len(re.findall(r'\w+', source)) < TOPIC_POLICY['min_description_tokens']:
        return Counter()
    tokens = list(WORD.finditer(source))[:TOPIC_POLICY['max_description_tokens']]
    result = Counter()
    for size in (2, 3):
        for start in range(len(tokens)-size+1):
            group = tokens[start:start+size]
            if any(token.group() in STOP for token in group):
                continue
            if any(not source[a.end():b.start()].isspace() for a,b in zip(group,group[1:])):
                continue
            phrase = ' '.join(token.group() for token in group)
            result[phrase] += 1
    return result


def choose_topics(description, degrees, corpus_size):
    candidates = phrases(description)
    maximum = max(TOPIC_POLICY['min_degree'], int(corpus_size*TOPIC_POLICY['maximum_degree_fraction']))
    ranked = sorted((phrase for phrase in candidates if TOPIC_POLICY['min_degree'] <= degrees.get(phrase,0) <= maximum),
                    key=lambda phrase: (-(1+math.log(candidates[phrase]))*(1+math.log((corpus_size+1)/(degrees[phrase]+1))), phrase))
    chosen = []
    for phrase in ranked:
        if any(phrase in other or other in phrase for other in chosen):
            continue
        chosen.append(phrase)
        if len(chosen) == TOPIC_POLICY['max_topics_per_book']:
            break
    return chosen
