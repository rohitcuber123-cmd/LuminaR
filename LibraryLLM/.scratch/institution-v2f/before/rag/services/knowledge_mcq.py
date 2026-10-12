"""Bounded source-bound MCQ candidates and quiz-wide correctness finalizer."""
from collections import Counter
from itertools import combinations
import random
from rag.services import knowledge_algorithms as a
from rag.services import knowledge_quiz_evidence as e
from rag.services import knowledge_quiz_relations as r


def stem(record, identify, qid):
    if identify:
        text = f'Which concept is defined by this source description: “{record["targetText"]}”?'
    elif record['relationType'] == 'DEFINITION':
        text = (f'Which description best defines {record["subjectText"]}?' if int(qid[-1],16)%2
                else f'According to the document, how is {record["subjectText"]} defined?')
    elif record['relationType'] == 'PURPOSE':
        text = f'What is {record["subjectText"]} used for according to the document?'
    elif record['relationType'] == 'PROCESS':
        text = f'Which step is specified for {record["subjectText"]}?'
    elif record['relationType'] == 'COMPOSITION':
        text = f'What does {record["subjectText"]} consist of according to the document?'
    elif record['relationType'].startswith('NUMERIC:'):
        text = f'What {record["relationType"].split(":",1)[1]} is specified for {record["subjectText"]}?'
    else:
        text = f'Which {record["relationType"].split(":")[0].lower()} is stated for {record["subjectText"]}?'
    return text


def candidate(record, others, seed=0, identify=False):
    qid = a.identifier('mcq', record['id'] + '|'.join(x['id'] for x in others) + str(seed) + str(identify))
    chosen = [record, *others]
    answer = record['subjectText'] if identify else record['targetText']
    options = [x['subjectText'] if identify else x['targetText'] for x in chosen]
    random.Random(qid).shuffle(options)
    return {'id': qid, 'type': 'mcq', 'question': stem(record,identify,qid), 'options': options, 'correctAnswer': answer,
        'sourceFactId': record['sourceFactId'], 'subjectId': record['subjectId'],
        'relationId': record['id'], 'relationFamily': record['relationType'],
        'questionForm': 'IDENTIFICATION' if identify else record['relationType'],
        'subjectText': record['subjectText'], 'explanation': record['sourceExcerpt'], **r.source(record),
        'optionSources': {x['subjectText'] if identify else x['targetText']: r.source(x) for x in chosen},
        'quality': {'sourceConfidence': record['confidence'], 'integrity': 1, 'compatibleOptions': 1,
                    'importance': round(min(1, record.get('score', 0)/15), 3),
                    'clarity': round(min(1, len(e.normalize(record['targetText']).split())/8),3)},
        '_relation': record, '_options': chosen, '_identify': identify,
        '_facts': {e.normalize(record['sourceExcerpt'])}, '_fact_ids': {record['sourceFactId']},
        '_relations': {record['id']}, '_concepts': {e.normalize(record['subjectText'])},
        '_sections': {record.get('section') or record.get('pageStart')}}


def verify(question, relations):
    record = next((x for x in relations if x['id'] == question.get('relationId')), None)
    if not record or not r.bound(record): return 'SOURCE_BINDING'
    if question['question'] != stem(record, question.get('_identify',False), question['id']): return 'STEM_ANSWER_BINDING'
    if (question.get('sourceFactId') != record['sourceFactId'] or question.get('subjectId') != record['subjectId']
            or question.get('subjectText') != record['subjectText'] or question.get('relationFamily') != record['relationType']):
        return 'STEM_ANSWER_BINDING'
    expected = record['subjectText'] if question.get('_identify') else record['targetText']
    if question['correctAnswer'] != expected or question['options'].count(expected) != 1: return 'ANSWER_KEY'
    if e.normalize(expected) in e.normalize(question['question']): return 'ANSWER_LEAK'
    if question['sourceExcerpt'] != record['sourceExcerpt'] or question.get('pageStart') != record.get('pageStart') or question['explanation'] != record['sourceExcerpt']:
        return 'SOURCE_PROVENANCE'
    if set(question['options']) != set(question['optionSources']): return 'OPTION_BINDING'
    options = question['_options']
    if len(options) != 4 or len(set(question['options'])) != 4: return 'DUPLICATE_OPTION'
    if sum(x['id']==record['id'] for x in options)!=1: return 'OPTION_BINDING'
    if any(question['optionSources'].get(x['subjectText'] if question['_identify'] else x['targetText']) != r.source(x) for x in options): return 'OPTION_BINDING'
    if question['_identify'] and any(e.labels_overlap(x['subjectText'], y['subjectText']) for x,y in combinations(options,2)):
        return 'AMBIGUOUS_OPTION'
    if any(not r.bound(x) or not r.bound(y) or not r.compatible(x,y,relations) or not r.compatible(y,x,relations)
           for x,y in combinations(options,2)): return 'MULTIPLE_CORRECT_OR_INCOMPATIBLE'
    if not question['_identify'] and any(e.normalize(x['subjectText']) in e.normalize(x['targetText']) for x in options):
        return 'ANSWER_LEAK'
    return None


def candidates(relations, rejected, seed=0):
    result=[]
    for record in relations[:100]:
        peers=[x for x in relations if x is not record and r.compatible(record,x,relations) and r.compatible(x,record,relations)]
        strict=[x for x in peers if record.get('category') and x.get('category')==record['category']]
        if len(strict)>=3: peers=strict
        # Rotate the compatible pool per authoritative relation; never choose
        # the same first three distractors for the whole document.
        random.Random(record['id']+str(seed)).shuffle(peers)
        emitted=0;tried=0
        for others in combinations(peers,3):
            tried+=1
            if tried>500: break
            if len(result)>=100: return result
            question=candidate(record,others,seed)
            reason=verify(question,relations)
            if reason: rejected[reason]=rejected.get(reason,0)+1; continue
            result.append(question);emitted+=1
            strict=all(record.get('category') and x.get('category')==record['category'] for x in others)
            if strict and len(result)<100:
                inverse=candidate(record,others,seed,True)
                if not verify(inverse,relations): result.append(inverse)
            if emitted>=4: break
        if not emitted: rejected['NO_RELIABLE_OPTIONS']=rejected.get('NO_RELIABLE_OPTIONS',0)+1
    return result


def finalize_mcq_quiz(candidates, requested_count, relations, excluded_facts=(), excluded_concepts=()):
    selected=[];distractor_use=Counter();option_use=Counter();subject_use=Counter();forms=Counter();sections=set();signatures=[];answers=[]
    rejected=Counter(); remaining=list(candidates)
    while remaining and len(selected)<requested_count:
        eligible=[]
        for q in remaining:
            reason=verify(q,relations)
            signature=frozenset(r.value_key(x) for x in q['options'])
            distractors=[r.value_key(x) for x in q['options'] if x!=q['correctAnswer']]
            if not reason and (q['_facts'] & set(excluded_facts) or q['_concepts'] & set(excluded_concepts)): reason='CROSS_FORMAT_REUSE'
            if not reason and any(signature==s or len(signature&s)>=3 for s in signatures): reason='REPEATED_OPTION_SET'
            if not reason and any(distractor_use[x]>=2 for x in distractors): reason='DISTRACTOR_REUSE_LIMIT'
            if not reason and any(r.equivalent(q['correctAnswer'],x) for x in answers): reason='CORRECT_ANSWER_REUSE'
            if not reason and subject_use[q['subjectId']]>=2: reason='SUBJECT_REUSE_LIMIT'
            if reason: rejected[reason]+=1; continue
            base=sum(q['quality'].values())
            score=base+1.2*bool(q['_sections']-sections)+.5*(forms[q['questionForm']]==0)-1.5*sum(distractor_use[x] for x in distractors)-1.5*subject_use[q['subjectId']]
            eligible.append((score,q['id'],q,signature,distractors))
        if not eligible: break
        score,_,q,signature,distractors=max(eligible,key=lambda x:(x[0],x[1]))
        q={**q,'selectionScore':round(score,3)};selected.append(q)
        remaining=[x for x in remaining if x['relationId']!=q['relationId']]
        signatures.append(signature);answers.append(q['correctAnswer']);subject_use[q['subjectId']]+=1
        forms[q['questionForm']]+=1;sections.update(q['_sections']);distractor_use.update(distractors);option_use.update(r.value_key(x) for x in q['options'])
    return selected, {'uniqueOptions':len(option_use),'optionPlacements':sum(option_use.values()),
        'uniqueDistractors':len(distractor_use),'maxDistractorReuse':max(distractor_use.values(),default=0),
        'meanDistractorReuse':round(sum(distractor_use.values())/max(1,len(distractor_use)),3),
        'duplicateOptionSets':len(signatures)-len(set(signatures)), 'subjectDistribution':dict(subject_use),
        'formDistribution':dict(forms),'rejections':dict(rejected)}
