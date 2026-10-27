"""Definition evidence selection within one already-authorized document.

This operates on the existing semantic candidates, never an index or another
document. It supplies evidence to the existing validator; it does not decide
whether an answer is supported.
"""
import re


def normalize_document_query(text):
    return ' '.join(re.sub(r'[^\w\s]', ' ', str(text or '').lower()).split())


def document_definition_topic(question):
    normalized = normalize_document_query(question)
    match = re.fullmatch(r'(?:what is|define|explain)\s+(?:(?:a|an|the)\s+)?(.+)', normalized)
    if not match:
        return None
    topic = match[1]
    terms = topic.split()
    if not 1 <= len(terms) <= 8 or len(topic) > 100:
        return None
    if set(terms) & {'and', 'or', 'not', 'never', 'without', 'why', 'because',
                     'before', 'after', 'when', 'if', 'prove', 'between', 'does', 'did'}:
        return None
    return topic


def definition_matches(question, text):
    topic = document_definition_topic(question)
    if not topic:
        return False
    normalized = normalize_document_query(text)
    # A heading or a passing mention is insufficient. Require a substantive
    # explicit definition, then let the existing Qwen validator judge it.
    pattern = rf'\b{re.escape(topic)}\s+(?:is|are|means|refers to|is defined as)\s+(.+)'
    match = re.search(pattern, normalized)
    return bool(match and len(match[1].split()) >= 6
                and not re.match(r'(?:not|never|no)\b', match[1]))


def select_definition_evidence(question, results, document_id, max_chunks):
    selected = [item for item in results
                if item.get('document_id', item.get('work_id')) == document_id
                and item.get('chunk_id') and str(item.get('text') or '').strip()]
    definitions = [item for item in selected if definition_matches(question, item['text'])]
    # Keep unrelated/claim-style questions on their original validation path.
    # For definitions, one to three explicit passages suffice and all are
    # inspected by the existing top-3 evidence check and supplied to generation.
    return definitions[:max(1, min(int(max_chunks), 3))] if definitions else selected


def definition_category(question, evidence, document_id):
    return 'document_definition' if any(
        item.get('document_id', item.get('work_id')) == document_id
        and definition_matches(question, item.get('text', '')) for item in evidence) else None
