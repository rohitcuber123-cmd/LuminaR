"""Bounded, source-grounded document algorithms. Standard library only."""
import hashlib
import math
import re
from collections import Counter

VERSION = '1.0.0'
MAX_CHUNKS = 1200
MAX_SENTENCES = 6000
MAX_CANDIDATES = 30000
STOP = set('a an the and or of to in on at by for from with without as is are was were be been being it its this that these those they their them we our you your he she his her i not no yes can could may might will would should shall must do does did have has had also such than then there here which who what when where how all any some each other only very more most into over under between through about both same used use using refers means defined consists including include includes example figure table chapter section page document text content information based system new many one two'.split())
VERBS = set('allows allow provides provide enables enable uses supports support contains contain represents represent describes describe requires require ensures ensure allocates divides performs helps makes becomes'.split())
WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-'][A-Za-z0-9]+)*")
DEFINITION = re.compile(r'^((?:[A-Za-z][A-Za-z0-9-]*\s+){0,5}[A-Za-z][A-Za-z0-9-]*)\s+(is defined as|refers to|consists of|is used for|means|is|are)\s+(.+?[.!?])$', re.I | re.S)


def normalize(text):
    return ' '.join(WORD.findall(text.lower()))


def identifier(prefix, text):
    return prefix + '_' + hashlib.sha256(text.encode()).hexdigest()[:16]


def provenance(chunk):
    page = chunk.get('pageStart', chunk.get('page'))
    return {'sourceChunkIds': [chunk['chunk_id']], 'pageStart': page,
            'pageEnd': chunk.get('pageEnd', page),
            **{key: chunk.get(key) for key in ('chapter', 'section', 'heading')}}


def valid_phrase(label):
    words = normalize(label).split()
    return (0 < len(words) <= 5 and 3 <= len(label) <= 65
            and words[0] not in STOP and words[-1] not in STOP
            and not any(w in VERBS for w in words)
            and sum(w not in STOP for w in words) >= max(1, len(words) - 1)
            and not re.search(r'(.)\1{3,}', label.lower()))


def sentences(chunks):
    # Evenly sample chunk positions, retaining source order and exact source substrings.
    indexes = range(len(chunks)) if len(chunks) <= MAX_CHUNKS else [i * (len(chunks)-1) // (MAX_CHUNKS-1) for i in range(MAX_CHUNKS)]
    result, seen = [], set()
    per_chunk = max(1, MAX_SENTENCES // max(1, len(indexes)))
    for i in indexes:
        chunk = chunks[i]
        candidates = []
        for match in re.finditer(r'[^.!?]+[.!?](?=\s|$)', chunk.get('text', '')[:12000]):
            text = match.group().strip()
            words = WORD.findall(text)
            key = normalize(text)
            if (not 6 <= len(words) <= 85 or not 30 <= len(text) <= 650
                    or not text[0].isupper() or '\ufffd' in text
                    or re.search(r'(.)\1{4,}|https?://|\.{3}', text)
                    or sum(c.isalpha() for c in text) / len(text) < .65):
                continue
            candidates.append((text, key))
        if len(candidates) > per_chunk:
            candidates = [candidates[j * (len(candidates) - 1) // max(1, per_chunk - 1)] for j in range(per_chunk)]
        for text, key in candidates:
            if key not in seen:
                seen.add(key)
                result.append({'text': text, 'order': len(result), **provenance(chunk)})
            if len(result) >= MAX_SENTENCES:
                return result
    return result


def definitions(rows):
    result, seen = [], set()
    for row in rows:
        match = DEFINITION.match(row['text'])
        if not match:
            continue
        subject, relation, answer = match.groups()
        subject = re.sub(r'^(?:The|A|An)\s+', '', subject, flags=re.I)
        key, answer_key = normalize(subject), normalize(answer)
        if (not valid_phrase(subject) or key in seen or not 4 <= len(WORD.findall(answer)) <= 45
                or len(answer) > 320 or key in answer_key
                or re.match(r'(?:not|also|often|sometimes|usually|one|another|important|useful)\b', answer_key)
                or relation.lower() == 'are' and len(key.split()) > 3):
            continue
        seen.add(key)
        # Retain the entire original statement: relations such as "used for" are not definitions of identity.
        result.append({**row, 'concept': subject, 'answer': answer, 'relation': relation})
    return result


def concepts(rows, chunks, limit=24):
    candidates = {}
    definition_keys = {normalize(d['concept']) for d in definitions(rows)}
    for row in rows:
        words = WORD.findall(row['text'])
        phrases = []
        for start, word in enumerate(words):
            if word.lower() in STOP | VERBS:
                continue
            for size in (1, 2, 3):
                phrase = ' '.join(words[start:start + size])
                if len(words[start:start + size]) == size and valid_phrase(phrase) and not any(w.lower() in STOP | VERBS for w in words[start:start + size]):
                    phrases.append(phrase)
        match = DEFINITION.match(row['text'])
        if match:
            phrases.append(re.sub(r'^(The|A|An)\s+', '', match[1], flags=re.I))
        for phrase in phrases:
            if not valid_phrase(phrase):
                continue
            key = normalize(phrase)
            if key not in candidates and len(candidates) >= MAX_CANDIDATES and key not in definition_keys:
                continue
            item = candidates.setdefault(key, {'label': phrase, 'count': 0, 'refs': set(), 'first': row})
            item['count'] += 1
            item['refs'].update(row['sourceChunkIds'])
    heading_terms = {normalize(c.get(k) or '') for c in chunks for k in ('heading', 'section', 'chapter')}
    ranked = []
    for key, item in candidates.items():
        if item['count'] < 2 and key not in definition_keys and key not in heading_terms:
            continue
        # Frequency with a length preference; definitional subjects provide the strongest signal.
        score = math.log1p(item['count']) * (1 + .3 * len(key.split())) + 7 * (key in definition_keys) + 3 * (key in heading_terms)
        ranked.append((score, key, item))
    selected = []
    for score, key, item in sorted(ranked, key=lambda r: (-r[0], r[1])):
        tokens = set(key.split())
        if any(tokens <= set(normalize(c['label']).split()) or set(normalize(c['label']).split()) <= tokens
               or len(tokens & set(normalize(c['label']).split())) / len(tokens | set(normalize(c['label']).split())) >= .75 for c in selected):
            continue
        selected.append({**provenance_from_row(item['first']), 'id': identifier('concept', key), 'label': item['label'],
                         'score': round(score, 3), 'sourceChunkIds': sorted(item['refs'])[:12]})
        if len(selected) >= limit:
            break
    return selected


def explicit_cloze_phrases(rows):
    """Narrow factual construction: e.g. 'uses a fixed time quantum'."""
    labels = set()
    for row in rows:
        match = re.search(r'\b(?:uses?|allocates?)\s+(?:a|an)\s+fixed\s+([A-Za-z-]+(?:\s+[A-Za-z-]+){1,3})[.!?]$', row['text'], re.I)
        if match and valid_phrase(match[1]):
            labels.add(match[1])
    return labels


def provenance_from_row(row):
    return {k: row.get(k) for k in ('sourceChunkIds', 'pageStart', 'pageEnd', 'chapter', 'section', 'heading')}


def summary(rows, key_concepts, mode):
    frequencies = Counter(w for r in rows for w in normalize(r['text']).split() if w not in STOP)
    ranked = sorted(rows, key=lambda r: -(sum(math.log1p(frequencies[w]) for w in set(normalize(r['text']).split()) if w not in STOP)
                    / math.sqrt(len(WORD.findall(r['text'])))
                    + sum(2 for c in key_concepts if normalize(c['label']) in normalize(r['text'])) + 1 / (1 + r['order'])))
    chosen, sets = [], []
    for row in ranked:
        words = set(normalize(row['text']).split()) - STOP
        if any(len(words & other) / max(1, len(words | other)) > .65 for other in sets):
            continue
        chosen.append(row)
        sets.append(words)
        if len(chosen) == (5 if mode == 'quick' else 12):
            break
    return {'mode': mode, 'sentences': [{'text': r['text'], **provenance_from_row(r)} for r in sorted(chosen, key=lambda r: r['order'])]}


def flashcards(rows, key_concepts):
    cards = []
    for row in definitions(rows)[:20]:
        label = row['concept']
        cards.append({'id': identifier('definition', normalize(label)), 'type': 'definition',
                      'front': f'What does the document say about {label}?', 'back': row['text'],
                      'concept': label, 'sourceExcerpt': row['text'], **provenance_from_row(row)})
    # A phrase must occur once, with substantial remaining context. Conflicting templates are discarded.
    candidates, templates = [], Counter()
    labels = sorted({c['label'] for c in key_concepts} | {d['concept'] for d in definitions(rows)} | explicit_cloze_phrases(rows), key=lambda x: (-len(x), x))
    for row in rows:
        for label in labels:
            pattern = re.compile(r'(?<!\w)' + r'\s+'.join(re.escape(w) for w in label.split()) + r'(?!\w)', re.I)
            matches = list(pattern.finditer(row['text']))
            if len(matches) != 1 or len(WORD.findall(row['text'])) - len(label.split()) < 6:
                continue
            match = matches[0]
            front = row['text'][:match.start()] + '_____' + row['text'][match.end():]
            candidates.append({'id': identifier('cloze', front), 'type': 'cloze', 'front': front,
                               'back': match.group(), 'concept': label, 'sourceExcerpt': row['text'], **provenance_from_row(row)})
            templates[normalize(front)] += 1
            break
    cards.extend(c for c in candidates if templates[normalize(c['front'])] == 1)
    return {'cards': cards[:40]}


def mind_map(key_concepts, chunks, title):
    nodes = [{'id': 'document', 'label': title, 'type': 'document', 'sourceChunkIds': []}]
    edges, groups = [], {}
    by_id = {c['chunk_id']: c for c in chunks}
    for concept in key_concepts[:24]:
        parent = 'document'
        source = by_id.get(concept['sourceChunkIds'][0], {})
        for kind in ('chapter', 'section'):
            label = source.get(kind)
            if not isinstance(label, str) or not label.strip() or len(nodes) >= 35:
                continue
            key = (parent, kind, label)
            if key not in groups:
                group_id = identifier(kind, '|'.join(key))
                groups[key] = group_id
                nodes.append({'id': group_id, 'label': label, 'type': kind, **provenance(source)})
                edges.append({'source': parent, 'target': group_id, 'relation': 'contains'})
            parent = groups[key]
        nodes.append({**concept, 'type': 'concept'})
        edges.append({'source': parent, 'target': concept['id'], 'relation': 'contains'})
    return {'title': title, 'nodes': nodes if key_concepts else [], 'edges': edges}


def quiz(cards):
    # Without a trustworthy taxonomy we cannot establish that distractors are incorrect.
    # Use source-explicit fill blanks and verified true statements instead of weak MCQs.
    questions = []
    seen = set()
    for card in sorted(cards, key=lambda c: c['type'] != 'cloze'):
        key = normalize(card['sourceExcerpt'])
        if key in seen:
            continue
        seen.add(key)
        cloze = card['type'] == 'cloze'
        questions.append({'id': identifier('question', card['id']), 'type': 'fill_blank' if cloze else 'true_false',
                          'question': ('Complete the source sentence: ' + card['front']) if cloze else card['sourceExcerpt'],
                          'correctAnswer': card['back'] if cloze else 'True',
                          'sourceExcerpt': card['sourceExcerpt'], **provenance_from_row(card)})
        if len(questions) == 12:
            break
    return {'questions': questions}


def generate(kind, chunks, title, options):
    rows = sentences(chunks)
    keys = concepts(rows, chunks)
    if kind == 'KEY_CONCEPTS':
        return {'concepts': keys}
    if kind == 'EXTRACTIVE_SUMMARY':
        return summary(rows, keys, options['mode'])
    if kind == 'FLASHCARDS':
        return flashcards(rows, keys)
    if kind == 'MIND_MAP':
        return mind_map(keys, chunks, title)
    if kind == 'QUIZ':
        from rag.services.knowledge_quiz import generate_quiz
        return generate_quiz(rows, keys, options, chunks)
    raise ValueError('Unsupported artifact type')
