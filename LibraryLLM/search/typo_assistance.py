"""Conservative, bounded lexical assistance primitives.

This module deliberately does not query MongoDB. Callers must provide a
bounded candidate vocabulary (for example, already retrieved metadata).
"""
import re
import unicodedata
from difflib import SequenceMatcher


def normalize_structured(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    value = re.sub(r"\s+", " ", value)
    return value


def conservative_similarity(query, candidate):
    q = normalize_structured(query)
    c = normalize_structured(candidate)
    if len(q) < 4 or len(c) < 4:
        return 0.0
    return SequenceMatcher(None, q, c).ratio()


def best_bounded_match(query, candidates, *, threshold=0.86, margin=0.05):
    scored = sorted(
        ((conservative_similarity(query, candidate), candidate) for candidate in candidates),
        reverse=True,
    )
    if not scored or scored[0][0] < threshold:
        return None
    if len(scored) > 1 and scored[0][0] - scored[1][0] < margin:
        return None
    return {"value": scored[0][1], "similarity": scored[0][0]}
