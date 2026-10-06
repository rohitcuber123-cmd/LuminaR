"""Semantic selected-book fallback; no text matching or independent router."""
from assistant.schemas import Intent, ReferenceScope, SemanticGoal, ClarificationType
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class SelectedContextAnswer(BaseModel):
    """Internal answer plan; factual sentences must be verified metadata."""
    model_config = ConfigDict(extra='forbid')
    facts: list[str] = Field(min_length=1, max_length=3)
    limitation: Literal['NONE', 'INFERENCE', 'NOT_ESTABLISHED']


def evidence_packet(books):
    """Bounded public observations, independent of the user's wording."""
    packet = metadata_packet(books)
    facts = {}
    for row in packet:
        i = row['position']
        for key, label in [('title', 'title'), ('authors', 'author field'), ('subjects', 'subjects'), ('description', 'description')]:
            value = row[key]
            if value:
                text = ' | '.join(value) if isinstance(value, list) else value
                limit = 300 if key == 'description' else 240
                excerpt = text[:limit] + ('\u2026' if len(text) > limit else '')
                facts[f'{i}_{key}'] = f'Book {i} lists {label}: \u201c{excerpt}\u201d.'
    def terms(value):
        entries = value if isinstance(value, list) else (value or '').split('|')
        return {str(item).strip().casefold(): str(item).strip() for item in entries if str(item).strip()}
    def words(title):
        return [w.strip('.,:;!?()[]{}\"\'').casefold() for w in (title or '').split()]
    for i, left in enumerate(packet):
        for right in packet[i+1:]:
            pair = f'{left["position"]}_{right["position"]}'
            a, b = words(left['title']), words(right['title'])
            longest = []
            for start in range(len(a)):
                for other in range(len(b)):
                    size = 0
                    while start+size < len(a) and other+size < len(b) and a[start+size] == b[other+size]:
                        size += 1
                    if size > len(longest): longest = a[start:start+size]
            if len(longest) >= 2:
                facts[f'{pair}_title_overlap'] = f'The titles of books {left["position"]} and {right["position"]} share the words \u201c{" ".join(longest)}\u201d.'
            for key in ['authors', 'subjects']:
                aa, bb = terms(left[key]), terms(right[key])
                shared = [aa[k] for k in aa if k in bb][:4]
                if shared:
                    facts[f'{pair}_shared_{key}'] = f'Books {left["position"]} and {right["position"]} both list {key}: \u201c{" | ".join(shared)[:240]}\u201d.'
                if aa and bb and aa.keys() != bb.keys():
                    facts[f'{pair}_different_{key}'] = f'The {key} field differs: book {left["position"]} lists \u201c{" | ".join(aa.values())[:240]}\u201d; book {right["position"]} lists \u201c{" | ".join(bb.values())[:240]}\u201d.'
            for key in ['description', 'subjects']:
                if bool(left[key]) != bool(right[key]):
                    known, missing = (left, right) if left[key] else (right, left)
                    facts[f'{pair}_{key}_coverage'] = f'Book {known["position"]} has a recorded {key} field; book {missing["position"]} has no recorded {key} field. That missing metadata does not establish a difference in the books\u2019 contents.'
    if not facts:
        facts['metadata_absent'] = 'The selected records have no title, author, subject or description metadata available.'
    return packet, facts


def answer_schema(facts):
    class EvidenceAnswerSchema:
        @classmethod
        def model_json_schema(cls):
            schema = SelectedContextAnswer.model_json_schema()
            schema['properties']['facts']['items']['enum'] = list(facts)
            return schema
    return EvidenceAnswerSchema


def render_answer(plan, books, facts):
    if any(key not in facts for key in plan.facts):
        raise ValueError('Answer facts must come from the current metadata packet.')
    titles = ' and '.join(f'\u201c{(book.title or book.work_id)[:200]}\u201d' for book in books)
    body = ' '.join(facts[key] for key in dict.fromkeys(plan.facts))
    note = {'NONE': '', 'INFERENCE': ' A broader thematic connection is an inference from these catalogue fields.',
            'NOT_ESTABLISHED': ' The catalogue metadata does not establish the underlying reason or a publication relationship.'}[plan.limitation]
    return f'About {titles}:\n\n{body}{note}'


def is_selected_context_question(request, decision):
    if request.action or not request.selected_work_ids or decision.unsupported_filters:
        return False
    # Named entities, account/search/content operations keep their own routes.
    if decision.reference_scope != ReferenceScope.SELECTED_BOOKS:
        return False
    if decision.intent == Intent.GENERAL_LIBRARY_HELP:
        return True
    if (decision.intent == Intent.COMPARE_BOOKS and decision.goal == SemanticGoal.DISCOVER
            and decision.reference_position in {None, 'ALL'} and not decision.comparison_fields):
        # A relationship over the supplied set is not a single-seed graph
        # lookup and has no requested field for the structured comparison.
        return True
    if (decision.intent in {Intent.COMPARE_BOOKS, Intent.BOOK_CONTENT_QUESTION} and decision.goal == SemanticGoal.EXPLAIN
            and not decision.comparison_fields):
        # Explanation has no objective field for the comparison tool. A
        # model-supplied purpose does not turn causal reasoning into a choice.
        return True
    # Guard only a semantic explanation of the current selection. Missing
    # positions are still checked by canonical reference binding afterwards.
    return (decision.intent in {Intent.CLARIFICATION, Intent.UNKNOWN}
            and decision.goal == SemanticGoal.EXPLAIN
            and decision.clarification_type in {None, ClarificationType.REFERENCE_AMBIGUITY})


def metadata_packet(books):
    def bounded(value, limit):
        return value[:limit] if isinstance(value, str) else None

    def values(value, count, limit):
        return [str(item)[:limit] for item in value[:count]] if isinstance(value, list) else bounded(value, count * limit)

    return [{'position': i + 1, 'title': bounded(book.title, 200),
             'authors': values(book.authors, 4, 80), 'subjects': values(book.subjects, 8, 80),
             'description': bounded(book.description, 1200)} for i, book in enumerate(books[:4])]
