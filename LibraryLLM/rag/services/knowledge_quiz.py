"""Document-grounded quiz formats. No model, retrieval or inference dependency."""
from itertools import combinations
import random
import re

from rag.services.knowledge_algorithms import (
    DEFINITION, definitions, flashcards, identifier, normalize, provenance_from_row,
)
from rag.services.knowledge_quiz_sources import note_facts, term

VERSION = '2.1.0'
QUESTION_TYPES = ('mcq', 'fill_blank', 'matching')
DEFAULT_TYPES = ('mcq', 'fill_blank')
DEFAULT_COUNT = 12
MAX_COUNT = 30
MAX_FACTS = 160


def quiz_options(question_types=None, question_count=DEFAULT_COUNT):
    values = list(DEFAULT_TYPES) if question_types is None else question_types
    if (not isinstance(values, list) or not values
            or any(not isinstance(value, str) or value not in QUESTION_TYPES for value in values)):
        raise ValueError('Select at least one valid question type: mcq, fill_blank, matching.')
    if isinstance(question_count, bool) or not isinstance(question_count, int) or not 1 <= question_count <= MAX_COUNT:
        raise ValueError(f'questionCount must be an integer from 1 to {MAX_COUNT}.')
    return {'questionTypes': sorted(set(values)), 'questionCount': question_count}


def similar(a, b):
    left, right = set(normalize(a).split()), set(normalize(b).split())
    return len(left & right) / max(1, len(left | right))


def aliases(a, b):
    left, right = normalize(a).split(), normalize(b).split()
    return (left == right or set(left) <= set(right) or set(right) <= set(left)
            or (len(left) > 1 and ''.join(w[0] for w in left) == ''.join(right))
            or (len(right) > 1 and ''.join(w[0] for w in right) == ''.join(left)))


def category(answer):
    # A category must be explicitly stated, e.g. "a scheduling algorithm that...".
    match = re.match(r'^(?:a|an)\s+(.+?)(?:\s+(?:that|which|for|of|to|using|with|by)\b|[.!?])', answer, re.I | re.S)
    if not match:
        return None
    tokens = normalize(match[1]).split()
    generic = {'algorithm', 'technique', 'scheme', 'method', 'process', 'approach', 'system', 'type', 'form'}
    if len(tokens) > 5 or not tokens or not (set(tokens) - generic):
        return None
    # Nearby algorithms/techniques with the same explicit domain are compatible choices.
    return ' '.join(tokens[:-1] if tokens[-1] in generic and len(tokens) > 1 else tokens)


def reliable_facts(rows, extra=()):
    statements = {}
    for row in rows:
        match = DEFINITION.match(row['text'])
        if match:
            subject = re.sub(r'^(?:the|a|an)\s+', '', match[1], flags=re.I)
            statements.setdefault(normalize(subject), set()).add(normalize(match[2]+' '+match[3]))
    for row in extra:
        statements.setdefault(normalize(row['concept']), set()).add(normalize(row['relation']+' '+row['answer']))
    facts, seen = [], {}
    for row in [*definitions(rows), *extra]:
        label = term(row['concept'])
        if not label or len(statements.get(normalize(row['concept']), ())) != 1:
            continue  # Conflicting descriptions of one term are not quiz facts.
        relation = row['relation'].lower()
        if relation in ('is', 'are') and re.match(r'(?:manufactured|required|calculated|added|sorted|stored|changed|accumulated)\b', row['answer'], re.I):
            continue
        description = row['answer'] if relation in ('is', 'are', 'means', 'is defined as', 'described in this section as') else relation.capitalize()+' '+row['answer']
        key = normalize(label)
        if key in seen:
            if row.get('group'):
                seen[key]['group'] = row['group']
            continue
        fact = {**row, 'concept': label, 'description': description, 'category': category(row['answer']),
                'fact': normalize(row['text']), 'conceptKey': key}
        facts.append(fact); seen[key] = fact
        if len(facts) == MAX_FACTS:
            break
    # Exclude aliases and nearly identical descriptions rather than guessing their distinction.
    ambiguous = set()
    for i, a in enumerate(facts):
        for b in facts[i+1:]:
            # Related parent/child terms are not automatically synonyms. Keep the facts,
            # but never put contained terms together as candidate choices/pairs below.
            left, right = normalize(a['concept']).split(), normalize(b['concept']).split()
            acronym = (len(left) > 1 and ''.join(w[0] for w in left) == ''.join(right)
                       or len(right) > 1 and ''.join(w[0] for w in right) == ''.join(left))
            if acronym or similar(a['description'], b['description']) >= .72:
                ambiguous.update((a['conceptKey'], b['conceptKey']))
    return [fact for fact in facts if fact['conceptKey'] not in ambiguous]


def candidate(question, facts):
    return {**question, '_facts': {f['fact'] for f in facts}, '_concepts': {f['conceptKey'] for f in facts}}


def mcqs(facts):
    result = []
    for fact in facts:
        choices = [other for other in facts if fact['category'] and other['category'] == fact['category'] and other is not fact and not aliases(fact['concept'], other['concept'])]
        if len(choices) < 3 and fact.get('group'):
            choices = [other for other in facts if other.get('group') == fact['group'] and other is not fact and not aliases(fact['concept'], other['concept'])]
        choices.sort(key=lambda other: (
            other.get('section') != fact.get('section'), other.get('pageStart') != fact.get('pageStart'),
            abs(other['order']-fact['order']), other['conceptKey']))
        if len(choices) < 3:
            continue
        chosen = [fact]
        for choice in choices:
            if not any(aliases(choice['concept'], other['concept']) for other in chosen):
                chosen.append(choice)
            if len(chosen) == 4:
                break
        if len(chosen) < 4:
            continue
        choices = chosen
        qid = identifier('mcq', fact['fact'])
        options = [choice['concept'] for choice in choices]
        random.Random(qid).shuffle(options)
        result.append(candidate({'id': qid, 'type': 'mcq',
            'question': (f'Which topic’s section contains this passage: “{fact["description"]}”?' if fact['relation'] == 'described in this section as'
                         else f'Which concept does the document describe as “{fact["description"]}”?'),
            'options': options, 'correctAnswer': fact['concept'], 'sourceExcerpt': fact['text'],
            **provenance_from_row(fact),
            'optionSources': {choice['concept']: {'sourceExcerpt': choice['text'], **provenance_from_row(choice)} for choice in choices}}, [fact]))
    return result


def fill_blanks(cards, facts):
    by_source = {f['fact']: f for f in facts}
    result = []
    seen = set()
    for card in cards:
        if card['type'] != 'cloze':
            continue
        key = normalize(card['sourceExcerpt'])
        if key in seen:
            continue
        seen.add(key)
        fact = by_source.get(key, {'fact': key, 'conceptKey': normalize(card['concept'])})
        result.append(candidate({'id': identifier('question', card['id']), 'type': 'fill_blank',
            'question': 'Complete the source sentence: '+card['front'], 'correctAnswer': card['back'],
            'sourceExcerpt': card['sourceExcerpt'], **provenance_from_row(card)}, [fact]))
    return result


def matching_sets(facts):
    groups = {}
    category_sizes = {f['category']: sum(other['category'] == f['category'] for other in facts) for f in facts if f['category']}
    for fact in facts:
        # Prefer the explicit category; otherwise keep nearby source relationships together.
        key = ('category', fact['category']) if category_sizes.get(fact['category'], 0) >= 3 else (
            ('group', fact['group']) if fact.get('group') else ('source', tuple(fact['sourceChunkIds'])))
        groups.setdefault(key, []).append(fact)
    result, seen = [], set()
    for group in groups.values():
        # Small overlapping windows allow balancing to select a still-unused set of 3–4 pairs.
        for start in range(0, len(group), 4):
            window = group[start:start+5]
            for size in (4, 3):
                for selected in combinations(window, size):
                    if any(aliases(a['concept'], b['concept']) for a, b in combinations(selected, 2)):
                        continue
                    key = '|'.join(f['fact'] for f in selected)
                    if key in seen:
                        continue
                    seen.add(key)
                    qid = identifier('matching', key)
                    left = [{'id': f'L{i+1}', 'text': fact['concept'], 'sourceExcerpt': fact['text'], **provenance_from_row(fact)} for i, fact in enumerate(selected)]
                    right = [{'id': f'R{i+1}', 'text': fact['description']} for i, fact in enumerate(selected)]
                    random.Random(qid).shuffle(right)
                    if [item['id'] for item in right] == [f'R{i+1}' for i in range(size)]:
                        right = right[1:]+right[:1]
                    pages = [fact['pageStart'] for fact in selected if isinstance(fact.get('pageStart'), int)]
                    result.append(candidate({'id': qid, 'type': 'matching', 'question': 'Match the concepts with their descriptions.',
                        'leftItems': left, 'rightItems': right,
                        'correctMatches': {f'L{i+1}': f'R{i+1}' for i in range(size)},
                        'sourceExcerpt': '\n'.join(f['text'] for f in selected),
                        'sourceChunkIds': sorted({chunk for f in selected for chunk in f['sourceChunkIds']}),
                        'pageStart': min(pages) if pages else None, 'pageEnd': max(pages) if pages else None}, selected))
                    if len(result) >= 240:
                        return result
    return result


def generate_quiz(rows, keys, options, chunks=()):
    options = quiz_options(options.get('questionTypes'), options.get('questionCount', DEFAULT_COUNT))
    selected, count = options['questionTypes'], options['questionCount']
    facts = reliable_facts(rows, note_facts(chunks)) if any(t in selected for t in ('mcq', 'matching')) else []
    pools = {}
    if 'mcq' in selected:
        pools['mcq'] = mcqs(facts)
    if 'fill_blank' in selected:
        pools['fill_blank'] = fill_blanks(flashcards(rows, keys)['cards'], facts)
    if 'matching' in selected:
        pools['matching'] = matching_sets(facts)
    questions, used_facts, used_concepts = [], set(), set()
    # Reserve matching pairs first, then round-robin across requested formats only.
    order = [t for t in ('matching', 'mcq', 'fill_blank') if t in selected]
    while len(questions) < count:
        added = False
        for kind in order:
            for item in pools[kind]:
                if item['_facts'].isdisjoint(used_facts) and item['_concepts'].isdisjoint(used_concepts):
                    used_facts.update(item['_facts']); used_concepts.update(item['_concepts'])
                    questions.append({key: value for key, value in item.items() if not key.startswith('_')})
                    added = True
                    break
            if len(questions) == count:
                break
        if not added:
            break
    counts = {kind: sum(q['type'] == kind for q in questions) for kind in selected}
    names = {'mcq': 'Multiple Choice', 'fill_blank': 'Fill in the Blanks', 'matching': 'Match the Following'}
    messages = [f'Not enough reliable source material was available for {names[kind]}.' for kind in selected if not counts[kind]]
    if len(questions) < count:
        messages.append(f'Generated {len(questions)} of {count} requested questions; only distinct, grounded facts were used.')
    return {'questions': questions, 'generatedCounts': counts, 'requestedCount': count, 'messages': messages}
