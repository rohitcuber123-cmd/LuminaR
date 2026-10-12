"""Narrow source-bound cloze metadata; core study renderers stay unchanged."""
import re
from rag.services import cloze_grading as g, knowledge_algorithms as a

VERSION=1

def aliases(canonical,source):
    values=[];expected=g.normalize(canonical,True)
    for match in re.finditer(r'([A-Za-z][A-Za-z -]{2,85}?)\s*\(([A-Z][A-Z0-9/-]{1,11})\)',source):
        full=match[1].strip();abbr=match[2]
        if expected in {g.normalize(full,True),g.normalize(abbr),g.normalize(match[0],True)}:
            values.extend([full,abbr])
    return sorted({v for v in values if g.normalize(v,True)!=expected})

def validate(item):
    required=('sourceFactId','subjectId','relationId','canonicalAnswer','blankType','evidenceUnitIds','sourceChunkIds')
    if any(not item.get(key) for key in required):return False
    canonical=item['canonicalAnswer'];source=item['sourceExcerpt']
    prompt=item['question'].removeprefix('Complete the source sentence: ')
    if prompt.count('_____')!=1 or item['correctAnswer']!=canonical:return False
    if g.normalize(prompt.replace('_____',canonical))!=g.normalize(source):return False
    if not re.search(r'(?<!\w)'+re.escape(g.normalize(canonical))+r'(?!\w)',g.normalize(source)):return False
    if any(re.search(r'(?<!\w)'+re.escape(g.normalize(v))+r'(?!\w)',g.normalize(prompt)) for v in [canonical,*item.get('acceptedAliases',[])]):return False
    if item.get('acceptedAliases',[])!=aliases(canonical,source):return False
    return item['blankType'] in {'TERM','ENTITY','SHORT_PHRASE','NUMBER','NUMBER_WITH_UNIT','DESCRIPTION'}

def bind(question,fact,model,relation_type='SUBJECT_IDENTITY'):
    canonical=question['correctAnswer'];source=question['sourceExcerpt']
    if '\ufffd' in source or re.search(r'(.)\1{5,}',canonical) or not canonical.strip():return None
    unit_ids=fact.get('evidenceUnitIds') or [fact.get('unit_id')]
    units=[u for u in model.source_units if u['id'] in unit_ids]
    if not units or not all(u.get('sourceChunkIds') for u in units):return None
    if any(u.get('extraction_method')=='OCR' for u in units) and re.search(r'(?<=[A-Za-z])\d(?=[A-Za-z])',source):return None
    source_fact_id=fact.get('sourceFactId') or fact.get('id')
    subject=fact.get('subjectText') or fact.get('concept') or question.get('concept')
    if not source_fact_id or not subject:return None
    relation_id=fact['id'] if fact.get('sourceFactId') else a.identifier('cloze_relation',source_fact_id+'|'+relation_type)
    kind=g.answer_type(canonical)
    if relation_type=='SUBJECT_IDENTITY':
        kind='ENTITY' if re.fullmatch(r'[A-Z][A-Z0-9 -]{1,14}',canonical) else 'TERM'
    item={**question,'canonicalAnswer':canonical,'blankType':kind,
        'sourceFactId':source_fact_id,'subjectId':a.identifier('quiz_subject',a.normalize(subject)),
        'relationId':relation_id,'relationType':relation_type,'evidenceUnitIds':[u['id'] for u in units],
        'acceptedAliases':aliases(canonical,source),'clozeVersion':VERSION,
        'conflictingTerms':sorted({f['concept'] for f in model.facts}|{r['subjectText'] for r in model.quiz_relations})[:100]}
    return item if validate(item) else None

def candidates(existing,model):
    result=[];core={g.normalize(f['text']):f for f in model.facts}
    for question in existing:
        fact=core.get(g.normalize(question['sourceExcerpt']))
        if not fact:continue
        item=bind(question,fact,model)
        if item:result.append(item)
    for record in model.quiz_relations:
        target=record['targetText'];source=record['sourceExcerpt']
        if len(target.split())>14 or len(target)>140:continue
        pattern=re.compile(r'(?<!\w)'+r'\s+'.join(re.escape(w) for w in target.split())+r'(?!\w)',re.I)
        matches=list(pattern.finditer(source))
        if len(matches)!=1:continue
        found=matches[0];canonical=found.group().rstrip('.');end=found.start()+len(canonical)
        prompt=source[:found.start()]+'_____'+source[end:]
        raw={'id':a.identifier('cloze',record['id']+'|target'),'type':'fill_blank',
            'question':'Complete the source sentence: '+prompt,'correctAnswer':canonical,'sourceExcerpt':source,
            **a.provenance_from_row(record),'_facts':{a.normalize(source)},'_concepts':{a.normalize(record['subjectText'])},
            '_sections':{record.get('section') or record.get('pageStart')}}
        item=bind(raw,record,model,record['relationType'])
        if item:result.append(item)
    groups={kind:[] for kind in ('NUMBER','NUMBER_WITH_UNIT','DESCRIPTION','SHORT_PHRASE','TERM','ENTITY')}
    for item in result:groups[item['blankType']].append(item)
    ordered=[]
    while any(groups.values()):
        for items in groups.values():
            if items:ordered.append(items.pop(0))
    return ordered[:100]
