"""Authoritative, quiz-only relation view of the accepted knowledge model.

Core concept/fact/relation selection and study renderers remain unchanged.
Every record binds subject, target and provenance before format construction.
"""
from collections import Counter
import re
from rag.services import knowledge_algorithms as a
from rag.services import knowledge_quiz_evidence as e

VERSION = 3


def key(text):
    text = re.sub(r'\s*\([A-Z][A-Z0-9/-]{1,12}\)', '', text)
    return re.sub(r'^(?:the|a|an)\s+', '', e.normalize(text))


def value_key(text):
    # The legacy concept normalizer intentionally drops digits. Quiz values
    # must preserve quantities: 10 seconds and 20 seconds are different targets.
    return ' '.join(re.findall(r'[+-]?\d+(?:\.\d+)?|[^\W\d_]+|%', text.lower().replace('−','-')))


def equivalent(left, right):
    x, y = value_key(left), value_key(right)
    if re.search(r'\d',x) or re.search(r'\d',y):
        units={'ms':.001,'millisecond':.001,'milliseconds':.001,'s':1,'second':1,'seconds':1,
               'min':60,'minute':60,'minutes':60,'h':3600,'hour':3600,'hours':3600,'day':86400,'days':86400}
        def quantity(text):
            match=re.fullmatch(r'([+-]?\d+(?:\.\d+)?)\s+([a-z]+)',text)
            return float(match[1])*units[match[2]] if match and match[2] in units else None
        a_value,b_value=quantity(x),quantity(y)
        if a_value is not None and b_value is not None:
            return abs(a_value-b_value)<=max(1e-9,max(abs(a_value),abs(b_value))*1e-9)
        return x==y
    return bool(x and y and (x == y or x in y or y in x or e.similarity(x, y) >= .66))


def bound(record):
    """Round trip to source identity; never find a new answer in an option pool."""
    expected = a.identifier('quiz_relation', '|'.join((record['sourceFactId'],
        key(record['subjectText']), record['relationType'], value_key(record['targetText']))))
    return (record['id'] == expected and record['subjectId'] == a.identifier('quiz_subject', key(record['subjectText']))
            and record.get('evidenceUnitIds') and record.get('sourceChunkIds')
            and value_key(record['targetText']) in value_key(record['sourceExcerpt'])
            and record.get('bindingValidated') is True)


def build(model):
    units = {u['id']: u for u in model.source_units}
    core = {f['id']: f for f in model.facts}
    relations, rejected = [], Counter()
    # Quiz evidence is already bounded and sourced. Narrow validation below
    # rejects section association masquerading as an explicit subject relation.
    candidates = list(model.quiz_evidence)
    for f in model.definitions:
        family={'is used for':'PURPOSE','consists of':'COMPOSITION'}.get(f['relation'].lower(),'DEFINITION')
        candidates.append({'concept': f['concept'], 'description': f['answer'], 'family': family,
            'sourceExcerpt': f['text'], 'evidenceUnitIds': [f['unit_id']], 'semanticPeers': [],
            'score': f.get('score', 0), 'fact': e.normalize(f['text']), **a.provenance_from_row(f)})
    # Explicit relations omitted by concept ranking can still be valid quiz
    # evidence. This adds only relation metadata from existing source units;
    # it does not re-read chunks, change core selection or call an encoder.
    for unit in model.source_units:
        if unit['low_value']: continue
        parsed=a.DEFINITION.match(e.display(unit['sourceExcerpt']))
        if not parsed or not e.term(parsed[1]): continue
        label=key(parsed[1])
        if (label in {'copy','range'} or label.split()[-1] in a.STOP
                or re.search(r'\b(?:or|which|that|this|those|these)\b',label)):
            continue
        family={'is used for':'PURPOSE','consists of':'COMPOSITION'}.get(parsed[2].lower(),'DEFINITION')
        if family=='DEFINITION' and not re.match(r'^(?:a|an|the|both)\b',parsed[3],re.I):continue
        if family=='DEFINITION' and len(e.normalize(parsed[3]).split())<6:continue
        if re.search(r'[.!]\s+\w',parsed[3]):continue
        candidates.append({'concept':e.term(parsed[1]),'description':parsed[3],'family':family,
            'sourceExcerpt':unit['sourceExcerpt'],'evidenceUnitIds':[unit['id']], 'semanticPeers':[],
            'score':4,'fact':e.normalize(unit['sourceExcerpt']), **a.provenance_from_row(unit)})
    seen = set()
    for f in candidates[:200]:
        subject, target, excerpt = f['concept'], f['description'], f['sourceExcerpt']
        family = f['family']
        evidence = [units[u] for u in f['evidenceUnitIds'] if u in units]
        if len(evidence) != len(f['evidenceUnitIds']) or not evidence:
            rejected['MISSING_SOURCE'] += 1; continue
        if (not target or '\ufffd' in target or re.search(r'[{}]|(.)\1{5,}', target)
                or re.search(r'\b(?:and|or|the|which|that|with|of|to|in|for)[.!]?$', target, re.I)):
            rejected['AMBIGUOUS_SOURCE'] += 1; continue
        parsed = re.match(r'^(.{3,100}?)\s+(is defined as|refers to|consists of|is used for|means|is|are)\s+(.+)[.!]$', e.display(excerpt).rstrip('.') + '.', re.I)
        authoritative = False
        relation_type = family
        if parsed and key(parsed[1]) == key(subject):
            expected_family = {'is used for': 'PURPOSE', 'consists of': 'COMPOSITION'}.get(parsed[2].lower(), 'DEFINITION')
            authoritative = family == expected_family and e.normalize(parsed[3]) == e.normalize(target)
        if not authoritative and family == 'DEFINITION':
            colon = re.match(r'^\s*([^:\n]{3,70}):\s*(.+)$', excerpt)
            authoritative = bool(colon and key(colon[1]) == key(subject) and e.normalize(colon[2]) == e.normalize(target))
        # Explicit heading + value/bullet is an actual contextual source relation,
        # unlike mere occurrence of a term somewhere in a prose sentence.
        if not authoritative and len(evidence) >= 2:
            heading = evidence[0]
            authoritative = heading['unit_kind'] == 'HEADING' and key(heading['text']) == key(subject)
            if authoritative and family.startswith('PROPERTY:'):
                value = target.split(':',1)[-1].strip()
                if re.fullmatch(r'\d+(?:\.\d+)?\s*(?:[A-Za-z%]+)?',value):
                    relation_type='NUMERIC:'+family.split(':',1)[1]
                    target=value
        if not authoritative and family == 'APPLICATION':
            # Existing application relations explicitly use the subject's heading.
            heading=next((u for u in model.source_units if u['unit_kind']=='HEADING'
                and key(u['text'])==key(subject) and u.get('pageStart')==evidence[0].get('pageStart')
                and set(u['sourceChunkIds'])&set(f['sourceChunkIds'])),None)
            authoritative=bool(heading and any(key(u.get('section_title') or u.get('section') or '')==key(subject) for u in evidence))
            if authoritative and heading['id'] not in f['evidenceUnitIds']:
                f={**f,'evidenceUnitIds':[heading['id'],*f['evidenceUnitIds']]}
        if not authoritative:
            rejected['SUBJECT_RELATION_NOT_EXPLICIT'] += 1; continue
        if any(u.get('extraction_method') == 'OCR' for u in evidence) and (
                (not relation_type.startswith('NUMERIC:') and sum(c.isalpha() for c in target) / max(1, len(target)) < .55)
                or re.search(r'\b\w*\d+\w*\b', target) and family == 'DEFINITION'):
            rejected['OCR_CORRUPTION'] += 1; continue
        signature = (key(subject), relation_type, value_key(target))
        if signature in seen: continue
        seen.add(signature)
        core_fact = next((c for c in core.values() if key(c['concept']) == key(subject)
                          and e.normalize(c['text']) == e.normalize(excerpt)), None)
        fact_id = core_fact['id'] if core_fact else a.identifier('structured_fact', '|'.join(f['evidenceUnitIds']) + e.normalize(excerpt))
        record = {**f, 'legacyEvidenceId': f.get('id'), 'sourceFactId': fact_id, 'subjectId': a.identifier('quiz_subject', key(subject)),
            'subjectText': subject, 'targetText': target, 'relationType': relation_type,
            'bindingValidated': True, 'confidence': .95 if parsed else .88}
        record['id'] = a.identifier('quiz_relation', '|'.join((fact_id, key(subject), relation_type, value_key(target))))
        relations.append(record)
    # Conflicting source definitions are unsuitable for assessment even when
    # each sentence is individually grammatical and sourced.
    bad_subjects = {x['subjectId'] for x in relations for y in relations
                    if x is not y and x['subjectId'] == y['subjectId']
                    and x['relationType'] == y['relationType'] == 'DEFINITION'
                    and not equivalent(x['targetText'], y['targetText'])}
    rejected['CONFLICTING_DEFINITION'] = sum(r['subjectId'] in bad_subjects for r in relations)
    return [r for r in relations if r['subjectId'] not in bad_subjects][:100], dict(rejected)


def attach(model):
    e.attach(model)
    if model.quiz_relation_version != VERSION:
        model.quiz_relations, model.quiz_relation_rejections = build(model)
        model.quiz_relation_version = VERSION
        model.quiz_relation_semantic_prepared = False
    if not model.quiz_relation_semantic_prepared:
        # Reuse the existing bounded CPU batch's persisted peer identities.
        # Core preparation stays one encoder call; quiz construction adds none.
        for relation in model.quiz_relations:
            labels={key(b) if key(a)==key(relation['subjectText']) else key(a)
                    for a,b in model.quiz_semantic_pairs if key(relation['subjectText']) in {key(a),key(b)}}
            relation['semanticPeers']=list(set(relation.get('semanticPeers',[])) | {
                other['id'] for other in model.quiz_relations if key(other['subjectText']) in labels})
        model.quiz_relation_semantic_prepared=True
    return model


def source(r):
    return {'sourceExcerpt': r['sourceExcerpt'], 'evidenceIds': [r['sourceFactId']],
        'relationIds': [r['id']], 'evidenceUnitIds': r['evidenceUnitIds'], **a.provenance_from_row(r)}


def peers(left, right):
    return (right['id'] in left.get('semanticPeers', [])
            or left['id'] in right.get('semanticPeers', [])
            or right.get('legacyEvidenceId') in left.get('semanticPeers', [])
            or left.get('legacyEvidenceId') in right.get('semanticPeers', []))


def compatible(left, right, relations):
    if (left['relationType'] != right['relationType'] or e.labels_overlap(left['subjectText'], right['subjectText'])
            or equivalent(left['targetText'], right['targetText']) or peers(left, right)):
        return False
    # Every source relation for the tested subject participates, not only the
    # candidate's preferred answer. This prevents a second supported answer.
    return not any(r['subjectId'] == left['subjectId'] and r['relationType'] == left['relationType']
                   and equivalent(r['targetText'], right['targetText']) for r in relations)
