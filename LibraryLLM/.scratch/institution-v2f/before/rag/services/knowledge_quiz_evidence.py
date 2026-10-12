"""A bounded quiz evidence facet of the accepted session knowledge model.

Does not alter concept selection, cards, summaries, maps or RAG source text.
"""
from collections import Counter, defaultdict
from itertools import combinations
import re

from rag.services import knowledge_algorithms as a
from rag.services.knowledge_quiz_sources import term, GENERIC

VERSION = 2
LIMIT = 100
REASONS = ('NO_COMPLETE_FACT', 'NO_ANSWER_TERM', 'NO_COMPATIBLE_DISTRACTORS',
           'DISTRACTOR_ANSWER_OVERLAP', 'AMBIGUOUS_QUESTION', 'DUPLICATE',
           'INSUFFICIENT_RELATION_EVIDENCE', 'PAIR_RIGHT_TOO_SIMILAR', 'ANSWER_LEAK',
           'SOURCE_FRAGMENT', 'GENERIC_CANDIDATE', 'INSUFFICIENT_PAIR_GROUP')


def normalize(value):
    return a.normalize(value)


def display(value):
    return ' '.join(value.replace('\u200b', '').split()).strip(' •\uf0d8')


def labels_overlap(left, right):
    x, y = set(normalize(left).split()), set(normalize(right).split())
    return bool(x and y and (x <= y or y <= x))


def similarity(left, right):
    x, y = set(normalize(left).split())-a.STOP, set(normalize(right).split())-a.STOP
    return len(x & y)/max(1, len(x | y))


def compatible(left, right):
    if left['family'] != right['family'] or labels_overlap(left['concept'], right['concept']):
        return False
    # Explicit source associations and normalized semantic-role families are
    # combined with lexical ambiguity checks; proximity/page is never a gate.
    if (similarity(left['description'], right['description']) >= .66
            or right['id'] in left.get('semanticPeers', [])):
        return False
    return not (normalize(left['concept']) in normalize(right['description'])
                or normalize(right['concept']) in normalize(left['description']))


def build(model):
    units = {u['id']: u for u in model.source_units}
    rejected = Counter({key: 0 for key in REASONS})
    facts, seen = [], set()
    ambiguous = set()
    definitions = defaultdict(list)
    for f in model.definitions:
        definitions[normalize(f['concept'])].append(f)
    for key, variants in definitions.items():
        if any(similarity(x['answer'], y['answer']) < .66 for x,y in combinations(variants,2)):
            ambiguous.add(key)

    def add(label, description, excerpt, unit_ids, provenance, family, score=0, category=None):
        label = term(label)
        if not label:
            rejected['NO_ANSWER_TERM'] += 1
            return
        if re.match(r'^(?:any|both|each|every|these|those|their|it|this|that)\b',label,re.I):
            rejected['GENERIC_CANDIDATE'] += 1
            return
        if normalize(label) in ambiguous:
            rejected['AMBIGUOUS_QUESTION'] += 1
            return
        text = display(description)
        if (not unit_ids or any(uid not in units or units[uid]['low_value'] for uid in unit_ids)):
            rejected['INSUFFICIENT_RELATION_EVIDENCE'] += 1
            return
        if (not text or '?' in text or len(text)>650 or '\ufffd' in text
                or re.search(r'\b(?:and|or|because|which|that|with|of|to|in|for|such as)[.!]?$',text,re.I)
                or re.search(r'\b\d+[a-z][+-]\d+\b',text,re.I)):
            rejected['SOURCE_FRAGMENT'] += 1
            return
        if len(normalize(label).split())==1 and normalize(label) in GENERIC:
            rejected['GENERIC_CANDIDATE'] += 1
            return
        key = (normalize(label), normalize(text), family)
        if key in seen:
            rejected['DUPLICATE'] += 1
            return
        seen.add(key)
        facts.append({'id':a.identifier('quiz_evidence','|'.join(key)), 'concept':label,
            'description':text, 'sourceExcerpt':excerpt, 'sourceChunkIds':provenance['sourceChunkIds'],
            **a.provenance_from_row(provenance), 'family':family, 'category':category,
            'evidenceUnitIds':unit_ids, 'score':score, 'conceptKey':normalize(label),
            'fact':normalize(excerpt)})

    # First reuse the existing accepted definition and best concept facts.
    from rag.services.knowledge_quiz import category
    for concept in model.concepts:
        rows = [f for f in model.facts if f['conceptId']==concept['id']]
        primary = next((f for f in rows if f.get('definitionEvidence')), rows[0] if rows else None)
        if not primary:
            rejected['NO_COMPLETE_FACT'] += 1
            continue
        if primary.get('group','').startswith('applications:'):
            add(concept['label'],primary['answer'],primary['text'],[primary['unit_id']],primary,
                'APPLICATION',concept['score'],'source-family:'+primary['group'])
        elif primary.get('definitionEvidence'):
            add(concept['label'],primary['answer'],primary['text'],[primary['unit_id']],primary,
                'DEFINITION',concept['score'],category(primary['answer']))
        elif primary['relation'] in {'is used for','has characteristic','has step','consists of'}:
            family={'is used for':'PURPOSE','has characteristic':'PROPERTY','has step':'PROCESS','consists of':'COMPOSITION'}[primary['relation']]
            add(concept['label'],primary['answer'],primary['text'],[primary['unit_id']],primary,family,concept['score'])
        else:
            text=display(primary['text'])
            label=concept['label']
            acronym=re.search(r'\(([A-Z][A-Z0-9/-]{1,12})\)',label)
            mentioned=normalize(term(label) or label) in normalize(text) or bool(acronym and re.search(r'\b'+re.escape(acronym[1])+r'\b',text))
            if (not mentioned or re.match(r'^(?:it|this|that|the idea|if|suppose|at time)\b',text,re.I)
                    or re.search(r'\b(?:created|invented)\b.{0,40}\b\d{4}\b',text,re.I)):
                rejected['SOURCE_FRAGMENT'] += 1
                continue
            family='FUNCTION' if re.search(r'\b(?:component|layer|site|address|field|delimiter)\b',label,re.I) else 'PROPERTY'
            add(label,text,primary['text'],[primary['unit_id']],primary,family,concept['score'])

    # Structured notes can state a relation without sentence punctuation. Keep
    # both the heading and bullet/label-value source units as evidence.
    heading = None
    for unit in model.source_units:
        if unit['low_value']:
            heading=None
            continue
        raw=unit['sourceExcerpt']
        if '\n' in raw:
            for line in raw.splitlines():
                colon=re.match(r'^\s*([^:\n]{3,70}):\s*((?:a|an|the)\s+.+)\s*$',line,re.I)
                if colon and len(normalize(colon[2]).split())>=6:
                    add(colon[1],colon[2],line,[unit['id']],unit,'DEFINITION',5,category(colon[2]))
        value_match=re.match(r'^\s*(?:[•\uf0d8-]|\d+[.)])?\s*([^:\n]{3,70}):\s*([^\n]{1,500})\s*$',raw)
        if value_match:
            label,value=value_match.groups(); value=display(value)
            if re.match(r'^(?:a|an|the)\b',value,re.I) and len(normalize(value).split())>=6:
                add(label,value,raw,[unit['id']],unit,'DEFINITION',5,category(value))
            elif heading and term(label) and len(normalize(label).split())>=2 and (
                    re.fullmatch(r'[\d .%×x^*/()+−-]+[A-Za-z]{0,8}',value)
                    or len(normalize(value).split())>=4):
                add(heading['text'],label.strip()+': '+value,raw,[heading['id'],unit['id']],unit,
                    'PROPERTY:'+normalize(label),5)
            else:
                rejected['SOURCE_FRAGMENT'] += 1
            continue
        if unit['unit_kind']=='HEADING':
            heading=unit if term(unit['text']) and not re.match(r'^(?:step|phase|part|event)\s+\d+',unit['text'],re.I) else None
            continue
        # Short complete definition-style bullets use exact source text and
        # normalize punctuation for parsing only.
        line=display(re.sub(r'^\s*(?:[•\uf0d8-]|\d+[.)])\s*','',raw))
        if unit['unit_kind'] != 'LIST_ITEM' and raw.strip().endswith(('.', '!', '?')):
            continue  # Complete prose already belongs to the accepted core facts.
        parsed=a.DEFINITION.match(line.rstrip('.')+'.')
        if parsed and len(normalize(parsed[3]).split())>=6:
            if parsed[2].lower() in {'is','are'} and not re.match(r'^(?:a|an|the|both)\b',parsed[3],re.I):
                rejected['SOURCE_FRAGMENT']+=1
                continue
            family='PURPOSE' if parsed[2].lower()=='is used for' else 'COMPOSITION' if parsed[2].lower()=='consists of' else 'DEFINITION'
            add(parsed[1],parsed[3],raw,[unit['id']],unit,family,5,category(parsed[3]))
        elif heading and unit['unit_kind']=='LIST_ITEM' and len(normalize(line).split())>=6:
            if re.search(r'\b(?:is|are|has|have|uses|allows|provides|requires|must|can)\b',line,re.I) and not line.endswith('?'):
                add(heading['text'],line,raw,[heading['id'],unit['id']],unit,'PROPERTY',4)
    facts.sort(key=lambda f:(-f['score'],f['conceptKey'],f['id']))
    # One best statement per subject/family avoids treating different correct
    # properties as contradictory definitions or answer alternatives.
    unique={}
    for f in facts:
        unique.setdefault((f['conceptKey'],f['family']),f)
    return list(unique.values())[:LIMIT], dict(rejected)


def attach(model, encoder=None):
    if model.quiz_evidence_version != VERSION:
        model.quiz_evidence,model.quiz_rejections=build(model)
        for f in model.quiz_evidence:
            peer_labels={b if a==normalize(f['concept']) else a for a,b in model.quiz_semantic_pairs
                         if normalize(f['concept']) in (a,b)}
            f['semanticPeers']=[other['id'] for other in model.quiz_evidence if normalize(other['concept']) in peer_labels]
        if encoder and not model.quiz_semantic_prepared and len(model.quiz_evidence)>1:
            # One bounded preparation batch; persist only ambiguity identities.
            # Views and quiz generation never call an encoder.
            import numpy as np
            vectors=np.asarray(encoder([f['description'] for f in model.quiz_evidence]),dtype='float32')
            if vectors.ndim!=2 or len(vectors)!=len(model.quiz_evidence) or not np.isfinite(vectors).all():
                raise ValueError('Invalid quiz evidence embeddings')
            vectors/=np.maximum(np.linalg.norm(vectors,axis=1,keepdims=True),1e-9)
            if float(np.std(vectors,axis=0).max())>1e-6:
                similarities=vectors@vectors.T
                for i,f in enumerate(model.quiz_evidence):
                    f['semanticPeers']=[other['id'] for j,other in enumerate(model.quiz_evidence)
                                        if j!=i and float(similarities[i,j])>=.88]
            model.quiz_semantic_prepared=True
        model.quiz_evidence_version=VERSION
    return model
