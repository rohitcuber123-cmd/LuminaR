"""Bounded source-derived study model. Independent of retrieval and generation."""
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict, field
from difflib import SequenceMatcher
import math
import re
import time

from rag.services import knowledge_algorithms as legacy
from rag.services.knowledge_quiz_sources import note_facts, GENERIC

VERSION = '3.2.1'
MAX_UNITS = 2200
MAX_CONCEPTS = 30
MAX_EMBEDDINGS = 192
GENERIC_CONTEXT = GENERIC | set('idea difference result thing process diagram description statement'.split())
LOW_SECTIONS = re.compile(r'^(?:acknowledg(?:e)?ments?|preface|table of contents|contents|references|bibliography|index)\b', re.I)
RELATION = re.compile(r'\b(is defined as|refers to|consists of|is used for|means|is|are)\b', re.I)
VERBAL = re.compile(r'\b(?:is|are|was|were|has|have|allows?|provides?|uses?|can|must|will|should|refers?|means|contains?|requires?|ensures?|enables?|defines?|tells?|consists?|represents?|determines?|needs?|relies|transmits?|sends?|receives?|governs?|senses?|avoids?|reduces?|controls?|limits?|stores?|protects?)\b', re.I)
LABEL_VERBAL = re.compile(r'\b(?:is|are|was|were|has|have|allows?|provides?|uses?|can|must|will|should|refers?|means|contains?|requires?|ensures?|enables?|defines?|tells?|consists?|represents?|determines?|needs?)\b', re.I)
BULLET = re.compile(r'^\s*(?:\d+[.)]|[ivx]+[.)]|[•\-])\s*', re.I)


def normalized(text):
    text = text.replace('\u200b', '').replace('\ufeff', '').replace('\u00ad', '')
    text = re.sub(r'([A-Za-z])-\s*\n\s*([a-z])', r'\1\2', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def phrase_key(label):
    words = legacy.normalize(label.replace('-', ' ')).split()
    return ' '.join(w[:-1] if len(w) > 4 and w.endswith('s') and not w.endswith('ss') else w for w in words)


def clean_label(text):
    text = normalized(BULLET.sub('', text)).strip(' :.;')
    text = re.sub(r'^(?:the|a|an)\s+', '', text, flags=re.I)
    text = re.sub(r'^(?:design|disadvantages?|advantages?|importance|procedure|characteristics?)\s+(?:of|for|with)\s+', '', text, flags=re.I)
    text = re.sub(r'^need\s+for\s+', '', text, flags=re.I)
    words = text.split()
    # Collapse confidently equivalent adjacent phrases, never a repeated single word.
    if len(words) >= 4 and len(words) % 2 == 0:
        half = len(words) // 2
        if phrase_key(' '.join(words[:half])) == phrase_key(' '.join(words[half:])):
            text = ' '.join(words[half:])
    return text


def label_ok(label):
    words = legacy.normalize(label).split()
    return (1 <= len(words) <= 8 and 3 <= len(label) <= 90
            and not LABEL_VERBAL.search(label) and not LOW_SECTIONS.match(label)
            and not re.match(r'^(?:if|when|after|before|once|unless|while|during|without|each|every|another|these|those|this|that|their|its)\b', label, re.I)
            and words[0] not in legacy.STOP and words[-1] not in legacy.STOP
            and not re.search(r'[{};=<>]|\ufffd', label)
            and sum(len(w) > 1 for w in words) >= len(words) - 1)


def heading(line):
    value = clean_label(line)
    if LOW_SECTIONS.match(value):
        return True
    return (label_ok(value) and len(value.split()) <= 8
            and not line.strip().endswith(('.', '?', '!'))
            and not re.search(r'\b(?:if|when|which|this|those|that|we|they|you|let|given)\b', value, re.I))


def quality_text(text):
    words = legacy.WORD.findall(normalized(text))
    return (6 <= len(words) <= 90 and 30 <= len(text) <= 650
            and bool(re.search(r'[.!]["”’\']?\s*$', text))
            and not text.strip().endswith(':')
            and sum(c.isalpha() for c in text) / max(1, len(text)) >= .52
            and not re.search(r'\ufffd|https?://|[{}]|(?:\.\s*){4}|(.)\1{5,}', text)
            and not re.search(r'\b(?:above|below)\s+(?:figure|diagram)|\bsince then\b|\bhere\b', text, re.I)
            and not re.search(r'\b(?:actions|steps)\b.{0,35}\b(?:performed|as follows)\s*[.:]?\s*$', normalized(text), re.I)
            and bool(VERBAL.search(text)))


def explanation_score(label, row):
    key = phrase_key(label)
    text = normalized(row['text'])
    acronym = re.search(r'\(([A-Z][A-Z0-9/-]{1,12})\)', label)
    mentioned = key in phrase_key(text) or bool(acronym and re.search(r'\b' + re.escape(acronym[1]) + r'\b', text))
    dependent = bool(re.match(r'(?:suppose|at time|since then|it |this |there |here )', text, re.I))
    return 3 * mentioned + .5 * row.get('definitionEvidence', False) + min(35, len(legacy.WORD.findall(text))) * .03 - 3 * dependent


@dataclass
class DocumentKnowledgeModel:
    version: str
    source_units: list
    concepts: list
    definitions: list
    facts: list
    relations: list
    examples: list
    processes: list
    section_structure: list
    metrics: dict
    # Additive quiz evidence only; the accepted 3.2.1 core and its renderers stay unchanged.
    quiz_evidence: list = field(default_factory=list)
    quiz_evidence_version: int = 0
    quiz_rejections: dict = field(default_factory=dict)
    quiz_semantic_pairs: list = field(default_factory=list)
    quiz_semantic_prepared: bool = False
    # Validated quiz relation view; core relations and renderers stay frozen.
    quiz_relations: list = field(default_factory=list)
    quiz_relation_version: int = 0
    quiz_relation_rejections: dict = field(default_factory=dict)
    quiz_relation_semantic_prepared: bool = False

    def payload(self):
        return asdict(self)


def source_units(chunks):
    """Page/chunk provenance stays intact; normalized text never replaces RAG text."""
    page_lines = defaultdict(set)
    for c in chunks[:legacy.MAX_CHUNKS]:
        page = c.get('pageStart', c.get('page', c['chunk_id']))
        for line in c['text'][:12000].splitlines():
            key = legacy.normalize(normalized(line))
            if 5 <= len(key) <= 140:
                page_lines[key].add(page)
    page_count = len({c.get('pageStart', c.get('page', c['chunk_id'])) for c in chunks})
    repeated = {k for k, pages in page_lines.items() if len(pages) >= max(3, math.ceil(page_count * .4))}
    units, metrics, seen = [], Counter(), set()
    current = None
    for c in chunks[:legacy.MAX_CHUNKS]:
        lines = c['text'][:12000].splitlines(keepends=True)
        buffer = []
        current = c.get('heading') or c.get('section') or current
        low = bool(current and LOW_SECTIONS.match(current))

        def emit(raw, kind, section):
            text = normalized(raw)
            key = (c.get('pageStart', c.get('page')), legacy.normalize(text))
            if not text or key in seen:
                metrics['duplicate_rejections'] += bool(text)
                return
            seen.add(key)
            units.append({'id': legacy.identifier('unit', c['chunk_id'] + str(len(units))),
                          'text': text, 'sourceExcerpt': raw.strip(), 'unit_kind': kind,
                          'section_title': section, 'low_value': low,
                          'extraction_method': c.get('extraction_method', c.get('extractionMethod', 'existing_text')),
                          **legacy.provenance(c)})

        def flush():
            if buffer:
                emit(''.join(buffer), 'PARAGRAPH', current)
                buffer.clear()

        for line_index, raw in enumerate(lines):
            line = normalized(raw)
            key = legacy.normalize(line)
            if not line or re.fullmatch(r'\d{1,5}', line):
                flush()
                continue
            # Definitions repeated through the document are substantive, not headers.
            if key in repeated and not VERBAL.search(line) and len(line.split()) <= 18:
                flush()
                metrics['boilerplate_rejections'] += 1
                continue
            following = normalized(lines[line_index + 1]) if line_index + 1 < len(lines) else ''
            next_definition = legacy.DEFINITION.match(following)
            wrapped_subject = bool(next_definition and 2 <= len(line.split()) <= 3
                                   and not line.endswith(':') and not re.match(r'^(?:the|a|an)\b', following, re.I)
                                   and set(phrase_key(line).split()) & set(phrase_key(next_definition[1]).split())
                                   and phrase_key(line) not in phrase_key(next_definition[1]))
            if heading(line) and not wrapped_subject and (not BULLET.match(line) or line.endswith(':')):
                flush()
                current = clean_label(line)
                low = bool(LOW_SECTIONS.match(current))
                emit(raw, 'HEADING', current)
            elif BULLET.match(line):
                flush()
                emit(raw, 'LIST_ITEM', current)
            else:
                if buffer and normalized(buffer[-1]) == line and len(line.split()) >= 3:
                    metrics['duplicate_rejections'] += 1
                    continue
                buffer.append(raw)
                if line.endswith(('.', '?', '!')):
                    flush()
            if len(units) >= MAX_UNITS:
                break
        flush()
        if len(units) >= MAX_UNITS:
            break
    metrics['source_units'] = len(units)
    metrics['sampled'] = len(chunks) > legacy.MAX_CHUNKS or len(units) >= MAX_UNITS
    return units, metrics


def unit_rows(units):
    rows = []
    for unit in units:
        if unit['low_value'] or unit['unit_kind'] == 'HEADING':
            continue
        raw = unit['sourceExcerpt']
        # Keep source spans exact, including wrapped lines; stop only at sentence punctuation.
        for match in re.finditer(r'[^.!?]+(?:[.!?](?=\s|$)|$)', raw):
            text = match.group().strip()
            if quality_text(text):
                rows.append({'text': text, 'order': len(rows), 'unit_id': unit['id'],
                             **legacy.provenance_from_row(unit), 'section': unit['section_title']})
    return rows[:legacy.MAX_SENTENCES]


def build(chunks, encoder=None):
    started = time.perf_counter()
    units, metrics = source_units(chunks)
    rows = unit_rows(units)
    by_chunk = defaultdict(list)
    for unit in units:
        by_chunk[unit['sourceChunkIds'][0]].append(unit)
    # Extract once, from accepted structural units. All artifacts reuse these facts.
    # Retain distinct definitions of one subject until conflict validation. The
    # compatibility extractor deduplicates subjects when passed an entire list.
    direct = [*(fact for row in rows for fact in legacy.definitions([row])), *note_facts(chunks[:legacy.MAX_CHUNKS])]
    candidates = {}

    def add(label, row, defined=False, heading_signal=False, relation='described in this section as', answer=None):
        label = clean_label(label)
        if not label_ok(label) or not quality_text(row['text']):
            metrics['fragment_rejections'] += 1
            return
        key = phrase_key(label)
        matched_unit = next((u for u in by_chunk[row['sourceChunkIds'][0]]
                             if legacy.normalize(row['text']) in legacy.normalize(u['sourceExcerpt'])
                             or row.get('answer') and legacy.normalize(row['answer']) in legacy.normalize(u['sourceExcerpt'])), None)
        if not matched_unit:
            metrics['unsupported_rejections'] += 1
            return
        if matched_unit['low_value']:
            metrics['boilerplate_rejections'] += 1
            return
        if matched_unit:
            row = {**row, 'section': matched_unit['section_title'], 'unit_id': matched_unit['id']}
        item = candidates.setdefault(key, {'label': label, 'evidence': [], 'supports': [], 'heading': False, 'defined': False})
        for cid in row['sourceChunkIds']:
            support = {'chunkId': cid, 'page': row.get('pageStart')}
            if support not in item['supports']:
                item['supports'].append(support)
        item['heading'] |= heading_signal
        item['defined'] |= defined
        existing = next((e for e in item['evidence'] if legacy.normalize(e['text']) == legacy.normalize(row['text'])
                         or e['relation'] == relation and legacy.normalize(e['answer']) == legacy.normalize(answer or row['text'])), None)
        if existing is None:
            item['evidence'].append({**row, 'concept': label, 'answer': answer or row['text'],
                                    'relation': relation, 'definitionEvidence': defined})
        else:
            existing['definitionEvidence'] |= defined
            if row.get('group'):
                existing['group'] = row['group']

    answer_labels = defaultdict(set)
    for fact in direct:
        answer_labels[legacy.normalize(fact['answer'])].add(fact['concept'])
    for fact in direct:
        # A PDF line can begin halfway through a wrapped subject. Resolve a
        # contained subject against complete, sentence-derived definitions with
        # identical evidence, rather than promoting the truncated line label.
        label = fact['concept']
        for other_label in sorted(answer_labels[legacy.normalize(fact['answer'])]):
            if (len(other_label.split()) > len(label.split())
                    and set(phrase_key(label).split()) < set(phrase_key(other_label).split())):
                label = other_label
        defined = fact['relation'] in {'is', 'are', 'is defined as', 'means', 'refers to'}
        if fact['relation'].lower() in {'is', 'are'}:
            defined = bool(re.match(r'^(?:a|an|the|both)\b', fact['answer'], re.I))
        actual_heading = any((u['unit_kind'] == 'HEADING' and phrase_key(u['text']) == phrase_key(fact['concept']))
                             or u.get('section_title') and phrase_key(u['section_title']) == phrase_key(fact['concept'])
                             for u in by_chunk[fact['sourceChunkIds'][0]])
        add(label, fact, defined, actual_heading, fact['relation'], fact['answer'])
    # A heading requires a complete explanatory sentence in its section.
    for unit in units:
        if unit['unit_kind'] != 'HEADING' or unit['low_value']:
            continue
        related = [r for r in rows if r.get('section') == unit['section_title']
                   and r['sourceChunkIds'][0] == unit['sourceChunkIds'][0]]
        if related:
            key = phrase_key(unit['text'])
            best = max(related, key=lambda r: (explanation_score(unit['text'], r), -r['order']))
            add(unit['text'], best, heading_signal=True)
    for unit in units:
        if unit['unit_kind'] == 'LIST_ITEM' and not unit['low_value'] and quality_text(unit['text']):
            label = unit['section_title']
            if label and label_ok(label):
                row = {'text': unit['sourceExcerpt'], 'order': len(rows), 'unit_id': unit['id'],
                       'section': label, **legacy.provenance_from_row(unit)}
                step = bool(re.match(r'(?:(?:the|a)\s+)?(?:sender|receiver|station|process)\s+(?:(?:must|should|can|will)\s+)?(?:send|transmit|wait|check|store|advance|restart|stop|receive|retain)', normalized(BULLET.sub('', unit['text'])), re.I))
                add(label, row, heading_signal=True, relation='has step' if step else 'described in this section as')
    for row in rows:
        for phrase in legacy.explicit_cloze_phrases([row]):
            add(phrase, row, heading_signal=True, relation='has characteristic')
    # Restrict recurring phrases to explanatory sentences, with phrase specificity.
    recurring = defaultdict(list)
    for row in rows:
        words = legacy.WORD.findall(normalized(row['text']))
        for size in (2, 3, 4):
            for start in range(len(words) - size + 1):
                label = ' '.join(words[start:start+size])
                if label_ok(label) and not any(w.lower() in legacy.STOP | legacy.VERBS for w in words[start:start+size]):
                    key = phrase_key(label)
                    if key not in recurring and len(recurring) >= 3500:
                        metrics['sampled'] = True
                        continue
                    recurring[key].append((label, row))
    for hits in recurring.values():
        pages = {r.get('pageStart') for _, r in hits}
        if len(hits) >= 3 and len(pages) >= 2:
            label = hits[0][0]
            for _, row in hits[:8]:
                add(label, row)

    doc_frequency = Counter(w for r in rows for w in set(legacy.normalize(r['text']).split()))
    ranked = []
    for key, item in candidates.items():
        evidence = item['evidence']
        pages = {r['pageStart'] for r in evidence if r.get('pageStart')}
        words = key.split()
        specificity = sum(math.log1p(len(rows) / max(1, doc_frequency[w])) for w in words) / len(words)
        # Structural support, not raw frequency, determines eligibility.
        genericity = (.7 if item['defined'] else 3 if len(words) == 1 else .25) + max(0, 1.2 - specificity)
        # A small structural vocabulary is one signal, never a rejection list.
        genericity += 2 * (not item['defined'] and bool(set(words) & GENERIC_CONTEXT))
        fragment = 2.5 * bool(re.match(r'^(?:event|step|phase|part)\s+\d+', item['label'], re.I))
        signals = {'heading': 2.8 * item['heading'], 'definition': 4.5 * item['defined'],
                   'frequency': min(1.5, math.log1p(len(evidence)) * .6),
                   'multi_page': min(1.2, len(pages) * .25), 'specificity': min(2, specificity),
                   'relation': .8 * any(e['definitionEvidence'] or e['relation'] in
                                       {'has characteristic', 'consists of', 'is used for', 'has step'} for e in evidence),
                   'multi_word': min(1, (len(words) - 1) * .35), 'genericity_penalty': genericity,
                   'fragment_penalty': fragment}
        score = sum(v for k, v in signals.items() if not k.endswith('penalty')) - genericity - fragment
        if (not item['defined'] and not item['heading'] and (len(words) < 2 or len(pages) < 2)) or score < 4.1:
            metrics['genericity_rejections'] += 1
            continue
        ranked.append({'key': key, 'score': score, 'signals': signals, **item})
    ranked.sort(key=lambda c: (-c['score'], c['key']))
    ranked = ranked[:MAX_EMBEDDINGS]
    vectors = None
    if encoder and len(ranked) > 1:
        import numpy as np
        embedding_started = time.perf_counter()
        vectors = np.asarray(encoder([c['label'] + ': ' + normalized(c['evidence'][0]['text'])[:280] for c in ranked]), dtype='float32')
        metrics['embedding_calls'] = 1
        metrics['embedding_ms'] = round((time.perf_counter() - embedding_started) * 1000, 2)
        if vectors.ndim != 2 or len(vectors) != len(ranked) or not np.isfinite(vectors).all():
            raise ValueError('Invalid knowledge embeddings')
        vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9)
        if float(np.std(vectors, axis=0).max()) < 1e-6:
            vectors = None  # Degenerate test encoders cannot establish semantic similarity.

    selected, suppressed = [], set()
    page_count = len({u['pageStart'] for u in units if u.get('pageStart')})
    target = min(MAX_CONCEPTS, 12 if page_count <= 4 else 20 if page_count <= 20 else 30)
    # Preserve a few complete, explicit educational families. Pure MMR can
    # scatter a 20-item set across eight topics, leaving no compatible quiz
    # distractors despite rich source definitions. These are source categories,
    # not inferred taxonomy or arbitrary same-page groupings.
    from rag.services.knowledge_quiz import category, reliable_facts
    validated = {phrase_key(f['concept']) for f in reliable_facts([], [e for item in ranked for e in item['evidence'] if e['definitionEvidence']])}
    families = defaultdict(list)
    for index, item in enumerate(ranked):
        first = next((e for e in item['evidence'] if e['definitionEvidence']), None)
        family = category(first['answer']) if first else None
        if family and item['key'] in validated:
            families[family].append(index)
    complete = sorted((indices for indices in families.values() if len(indices) >= 4),
                      key=lambda ids: -sum(ranked[i]['score'] for i in ids[:4]))
    for indices in complete[:min(3, target // 6)]:
        for index in indices[:4]:
            selected.append((index, ranked[index]))
    metrics['complete_fact_families'] = min(3, target // 6, len(complete))
    # Bounded MMR; structural facts may be educationally distinct despite related labels.
    while len(selected) < target:
        choices = []
        for index, item in enumerate(ranked):
            if index in suppressed or any(index == i for i, _ in selected):
                continue
            similarity = max((float(vectors[index] @ vectors[i]) for i, _ in selected), default=0) if vectors is not None else 0
            choices.append((item['score'] - 2.2 * max(0, similarity), -index, index, item))
        if not choices:
            break
        _, _, index, item = max(choices, key=lambda x: x[:2])
        duplicate = False
        for other_index, other in selected:
            left, right = set(item['key'].split()), set(other['key'].split())
            lexical = item['key'] == other['key'] or (left <= right or right <= left) and not (item['defined'] and other['defined'])
            semantic = vectors is not None and float(vectors[index] @ vectors[other_index]) >= .90
            same_explanation = SequenceMatcher(None, legacy.normalize(item['evidence'][0]['text']), legacy.normalize(other['evidence'][0]['text'])).ratio() >= .90
            if lexical or semantic and (same_explanation or not (item['defined'] and other['defined'])):
                duplicate = True
                break
        if duplicate:
            suppressed.add(index)
            metrics['duplicate_rejections'] += 1
        else:
            selected.append((index, item))

    concepts, facts, relations = [], [], []
    for _, item in selected:
        evidence = sorted(item['evidence'], key=lambda e: (not e['definitionEvidence'], e.get('order', 0)))
        first = max(evidence, key=lambda e: explanation_score(item['label'], e))
        sources = item['supports'][:12]
        refs = sorted({s['chunkId'] for s in sources})
        concept = {'id': legacy.identifier('concept', item['key']), 'label': item['label'],
                   'explanation': normalized(first['text'])[:650],
                   'score': round(item['score'], 3), 'scoreSignals': item['signals'],
                   'confidence': .95 if item['defined'] else .78, 'evidenceUnitIds': [],
                   **legacy.provenance_from_row(first), 'sourceChunkIds': refs, 'sources': sources[:12]}
        unit = next((u for u in units if u['id'] == first.get('unit_id')), None)
        if unit:
            concept['evidenceUnitIds'] = [unit['id']]
        concepts.append(concept)
        principal_evidence = [first, *(e for e in evidence if e is not first)]
        for evidence_row in principal_evidence[:3]:
            fact = {**evidence_row, 'concept': item['label'], 'id': legacy.identifier('fact', item['key'] + legacy.normalize(evidence_row['text'])),
                    'conceptId': concept['id'], 'confidence': concept['confidence'],
                    'score': concept['score'], 'sources': [{'chunkId': cid, 'page': evidence_row.get('pageStart')} for cid in evidence_row['sourceChunkIds']]}
            facts.append(fact)
            relation_type = {'is used for': 'USED_FOR', 'consists of': 'CONTAINS',
                             'means': 'DEFINED_AS', 'refers to': 'DEFINED_AS', 'is defined as': 'DEFINED_AS',
                             'is': 'DEFINED_AS', 'are': 'DEFINED_AS', 'has step': 'HAS_STEP'}.get(fact['relation'])
            if fact['relation'] in {'is', 'are'} and not fact['definitionEvidence']:
                relation_type = 'DESCRIBED_AS'
            if relation_type:
                relations.append({'id': legacy.identifier('relation', fact['id']), 'source': concept['id'],
                                  'targetText': fact['answer'], 'type': relation_type, 'factId': fact['id'],
                                  'evidenceUnitIds': [fact['unit_id']], 'sources': fact['sources'], **legacy.provenance_from_row(fact)})
    sections = []
    for concept in concepts:
        label = concept.get('section')
        if label and not any(s['title'] == label for s in sections):
            sections.append({'title': label, **legacy.provenance_from_row(concept)})
    processes = [f for f in facts if f['relation'] == 'has step']
    examples = [f for f in facts if re.search(r'\b(?:for example|for instance|such as)\b', f['text'], re.I)]
    metrics.update({'candidate_count': len(candidates), 'accepted_count': len(concepts),
                    'source_pages_used': len({s['page'] for c in concepts for s in c['sources'] if s['page']}),
                    'concept_diversity': len({c.get('section') for c in concepts}),
                    'qwen_calls': 0,
                    'knowledge_model_ms': round((time.perf_counter() - started) * 1000, 2)})
    model = DocumentKnowledgeModel(VERSION, units, concepts, [f for f in facts if f['definitionEvidence']],
                                  facts, relations, examples, processes, sections, dict(metrics))
    # Reuse the existing bounded semantic batch for quiz ambiguity checks.
    # This does not participate in selection/ranking or add an encoder call.
    if vectors is not None:
        model.quiz_semantic_pairs = [[legacy.normalize(left['label']), legacy.normalize(right['label'])]
            for pos,(i,left) in enumerate(selected) for j,right in selected[pos+1:]
            if float(vectors[i] @ vectors[j]) >= .88]
    model.quiz_semantic_prepared = True
    return model


def generate(kind, model, title, options):
    """Render only accepted knowledge; no artifact re-scrapes document chunks."""
    concepts, facts = model.concepts, model.facts
    if kind == 'KEY_CONCEPTS':
        return {'concepts': concepts}
    if kind == 'FLASHCARDS':
        cards = []
        for concept in concepts:
            items = [f for f in facts if f['conceptId'] == concept['id']]
            if not items:
                continue
            fact = next((f for f in items if f in model.definitions),
                        max(items, key=lambda f: explanation_score(concept['label'], f)))
            card_type = 'definition' if fact in model.definitions else 'concept'
            front = f'What does the document explain about {concept["label"]}?'
            back = normalized(fact['text'])
            if fact['relation'] == 'has characteristic':
                card_type = 'cloze'
                pattern = re.compile(r'(?<!\w)' + r'\s+'.join(re.escape(w) for w in concept['label'].split()) + r'(?!\w)', re.I)
                match = pattern.search(fact['text'])
                if match:
                    front = fact['text'][:match.start()] + '_____' + fact['text'][match.end():]
                    back = match.group()
            cards.append({'id': legacy.identifier('card', fact['id']), 'type': card_type,
                          'front': front, 'back': back, 'sourceExcerpt': fact['text'],
                          'concept': concept['label'], 'knowledgeItemId': fact['id'],
                          **legacy.provenance_from_row(fact), 'sources': fact['sources']})
        # One second, distinct supported relation/process/application per concept.
        for fact in [*model.processes, *model.examples, *facts]:
            if any(c['sourceExcerpt'] == fact['text'] for c in cards):
                continue
            relation = fact['relation'] != 'described in this section as'
            card_type = 'process' if fact in model.processes else 'application' if fact in model.examples else 'relationship' if relation else 'concept'
            cards.append({'id': legacy.identifier('card', fact['id']), 'type': card_type,
                          'front': f'According to the source, what does {fact["concept"]} {"involve in this step" if card_type == "process" else "illustrate in this example" if card_type == "application" else "do or require"}?',
                          'back': normalized(fact['text']), 'sourceExcerpt': fact['text'], 'concept': fact['concept'],
                          'knowledgeItemId': fact['id'], **legacy.provenance_from_row(fact), 'sources': fact['sources']})
            if len(cards) >= 40:
                break
        return {'cards': cards[:40]}
    if kind == 'EXTRACTIVE_SUMMARY':
        limit = 5 if options.get('mode') == 'quick' else 12
        selected, seen_sections = [], set()
        for fact in sorted(facts, key=lambda f: (f.get('pageStart') or math.inf, f.get('order', 0))):
            section = fact.get('section') or fact['conceptId']
            if section not in seen_sections:
                seen_sections.add(section)
                selected.append(fact)
            if len(selected) >= limit:
                break
        sections = []
        for fact in selected:
            sections.append({'title': fact.get('section') or fact['concept'],
                             'sentences': [{'text': normalized(fact['text']), 'knowledgeItemId': fact['id'],
                                            **legacy.provenance_from_row(fact), 'sources': fact['sources']}]})
        return {'mode': options.get('mode', 'quick'), 'sections': sections,
                'sentences': [s for section in sections for s in section['sentences']]}
    if kind == 'MIND_MAP':
        nodes = [{'id': 'document', 'label': title, 'type': 'document', 'sourceChunkIds': []}]
        edges = []
        groups = {}
        for concept in concepts[:24]:
            parent = 'document'
            for field in ('chapter', 'section'):
                label = concept.get(field)
                if not label or phrase_key(label) == phrase_key(concept['label']):
                    continue
                key = (parent, field, label)
                if key not in groups and len(groups) < 10:
                    group = legacy.identifier('group', '|'.join(key))
                    groups[key] = group
                    nodes.append({'id': group, 'label': label, 'type': field,
                                  **legacy.provenance_from_row(concept), 'sources': concept['sources']})
                    edges.append({'source': parent, 'target': group, 'relation': 'source organization',
                                  **legacy.provenance_from_row(concept)})
                parent = groups.get(key, parent)
            nodes.append({**concept, 'type': 'concept'})
            # This is source organization, explicitly distinguished from a semantic relation.
            edges.append({'source': parent, 'target': concept['id'], 'relation': 'document topic',
                          'sourceChunkIds': concept['sourceChunkIds']})
        for relation in model.relations[:min(24, 60 - len(nodes))]:
            if not any(n['id'] == relation['source'] for n in nodes):
                continue
            target = relation['id']
            nodes.append({'id': target, 'label': normalized(relation['targetText'])[:160],
                          'type': 'evidence', 'sources': relation['sources'], **legacy.provenance_from_row(relation)})
            edges.append({'source': relation['source'], 'target': target,
                          'relation': relation['type'], **legacy.provenance_from_row(relation)})
        return {'title': title, 'nodes': nodes if concepts else [], 'edges': edges}
    if kind == 'QUIZ':
        from rag.services.knowledge_quiz import generate_from_knowledge
        return generate_from_knowledge(model, options)
    raise ValueError('Unsupported artifact type')
