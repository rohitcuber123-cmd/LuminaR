"""Extract explicit relationships from lecture-note lines, without model inference."""
import re
from collections import Counter

from rag.services.knowledge_algorithms import WORD, normalize, provenance, valid_phrase

GENERIC = set('syllabus applications introduction approach approaches example examples input output explanation solution algorithm pseudocode signature returns complexity observations note statement task steps procedure implementation principles conclusion'.split())
BAD_START = set('if let so this that it we they there here hence generally bigger smaller each given suppose consider for now however after before in then similarly since when your notice variable image solutions'.split())
BULLETS = r'[ \t\uf0d8\uf0b7•\-]*'
LABEL = re.compile(r'^' + BULLETS + r'(?:\d+(?:[.)]|\s*[.:])\s*)?([^:\n]{3,90}):\s*', re.M)
DEFINITION_LINE = re.compile(r'^' + BULLETS + r'([^\n:;.!?]{3,110}?)\s+(is defined as|refers to|consists of|is used for|means|is|are)\s+', re.I | re.M)


def term(value):
    value = re.sub(r'\s*\([A-Za-z][A-Za-z0-9-]{0,12}\)', '', value)
    value = re.sub(r'^(?:the|a|an)\s+', '', value.strip(), flags=re.I)
    value = ' '.join(value.split()).strip(' .')
    words = normalize(value).split()
    if (not 1 <= len(words) <= 8 or len(value) > 90 or not words
            or words[0] in BAD_START or len(words) == 1 and words[0] in GENERIC
            or set(words) & {'and', 'vs', 'versus'}
            or any(len(word) == 1 and word not in {'a', 'n'} for word in words)
            or re.search(r'[^A-Za-z0-9 /-]|\b(?:to|which|where|when|taken|will|time to|introduction|steps|principles|solution|implementation|calculation)\b', value, re.I)
            or re.search(r'[{};=<>]|\b(?:program|java|class|step|case|iteration|complexity|procedure|example|input|output|statement)\b', value, re.I)):
        return None
    return value


def description(text, start):
    # Preserve exact source slices, including PDF line wrapping.
    match = re.match(r'[ \t\r\n\uf0d8\uf0b7•-]*(.+?[.!?])(?=\s|$)', text[start:start+800], re.S)
    if not match:
        return None
    answer = match[1].strip()
    words = WORD.findall(answer)
    if (not 6 <= len(words) <= 80 or not 30 <= len(answer) <= 550
            or re.search(r'[{};]|\b(?:public static|System\.out|import java)\b', answer)
            or sum(c.isalpha() for c in answer) / len(answer) < .55):
        return None
    return answer


def note_facts(chunks):
    chunks = chunks[:1200]
    repeated = Counter(line.strip() for chunk in chunks for line in set(chunk['text'].splitlines())
                       if len(line.strip()) > 20)
    groups, labels = {}, []
    # Explicit enumerated Applications lists establish a source-backed distractor family.
    for chunk in chunks:
        text = chunk['text'][:12000]
        for match in re.finditer(r'(?mi)^\s*Applications\s*:\s*\n', text):
            members = []
            for line in text[match.end():].splitlines():
                listed = re.match(r'^\s*\d+[.)]\s+([^:]+)\.\s*$', line)
                if listed:
                    label = term(listed[1])
                    if label:
                        members.append(normalize(label))
                elif line.strip() and members:
                    break
            if len(members) >= 3:
                for member in members:
                    groups[member] = 'applications:'+chunk['chunk_id']+':'+str(match.start())
        for match in LABEL.finditer(text):
            label = term(match[1])
            if label and repeated[match[0].strip()] < 3:
                labels.append((chunk, match, label))

    heading_terms = {normalize(label) for _, _, label in labels}
    def heading_key(label):
        words = normalize(label.replace('-', ' ')).split()
        return ' '.join(word[:-1] if len(word) > 3 and word.endswith('s') else word for word in words)
    heading_names = {heading_key(label): label for _, _, label in labels}
    facts = []
    for chunk in chunks:
        text = chunk['text'][:12000]
        for match in DEFINITION_LINE.finditer(text):
            label = term(match[1])
            answer = description(text, match.end())
            if not label or not answer or normalize(label) in normalize(answer):
                continue
            short = re.sub(r'\s+problem$', '', label, flags=re.I)
            if heading_key(short) in heading_names:
                label = heading_names[heading_key(short)]
            named = normalize(label) in heading_terms or normalize(label) in groups
            if not named and (not valid_phrase(label) or not re.match(r'(?:a|an)\s+', answer, re.I)):
                continue
            # Opinion-like or negative statements do not become identity definitions.
            if re.match(r'(?:not|also|often|sometimes|usually|indeed|very useful|effective when)\b', answer, re.I):
                continue
            answer_start = text.find(answer, match.end())
            facts.append({'concept': label, 'answer': answer, 'relation': match[2].lower(),
                'text': text[match.start():answer_start+len(answer)],
                'group': groups.get(normalize(label)) or 'note-page:'+chunk['chunk_id'], **provenance(chunk)})
    direct_labels = {normalize(fact['concept']) for fact in facts}
    for chunk, match, label in labels:
        if normalize(label) in direct_labels:
            continue
        text = chunk['text'][:12000]
        start = match.end()
        # A nearby generic subheading may precede the actual problem statement.
        tail = text[start:start+800]
        intro = re.match(r'\s*(?:Problem Statement|Introduction)\s*:\s*', tail, re.I)
        if intro:
            start += intro.end()
        answer = description(text, start)
        if not answer:
            continue
        # Only application members or explicit term: description constructions are eligible.
        # Never treat an arbitrary heading/code label as a fact.
        group = groups.get(normalize(label))
        if not group and not re.match(r'(?:a|an|the|dynamic programming)\b', answer, re.I):
            continue
        if normalize(label) in normalize(answer):
            # E.g. "Optimal Substructure: A problem has ... if [definition]".
            conditional = re.search(r'\bif\s+(.+[.!?])$', answer, re.I | re.S)
            if not conditional or normalize(label) in normalize(conditional[1]):
                continue
            answer = conditional[1]
        excerpt_start = match.start()
        answer_start = text.find(answer, start)
        facts.append({'concept': label, 'answer': answer, 'relation': 'described in this section as',
            'text': text[excerpt_start:answer_start+len(answer)],
            'group': group or 'note-page:'+chunk['chunk_id'], **provenance(chunk)})
    for order, fact in enumerate(facts):
        fact['order'] = order
    return facts[:320]
