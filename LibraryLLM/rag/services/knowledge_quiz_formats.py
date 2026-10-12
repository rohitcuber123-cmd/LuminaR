"""Grounded typed question frames, bounded independently of page proximity."""
from collections import Counter, defaultdict
from itertools import combinations
import random

from rag.services import knowledge_algorithms as a
from rag.services import knowledge_quiz_evidence as e


def candidate(question, facts):
    return {**question, '_facts':{f['fact'] for f in facts},
            '_concepts':{f['conceptKey'] for f in facts},
            '_sections':{f.get('section') or f.get('pageStart') for f in facts}}


def source(fact):
    return {'sourceExcerpt':fact['sourceExcerpt'],'evidenceIds':[fact['id']],
            'evidenceUnitIds':fact['evidenceUnitIds'],**a.provenance_from_row(fact)}


def mcqs(facts, rejected):
    result=[]
    for f in facts[:100]:
        choices=[b for b in facts if b is not f and e.compatible(f,b)]
        strict=[b for b in choices if f.get('category') and b.get('category')==f['category']]
        identify=len(strict)>=3 and e.normalize(f['concept']) not in e.normalize(f['description'])
        if identify:
            choices=strict
        chosen=[f]
        for other in choices:
            if all(e.compatible(other,x) for x in chosen):
                chosen.append(other)
            else:
                rejected['DISTRACTOR_ANSWER_OVERLAP']+=1
            if len(chosen)==4:
                break
        if len(chosen)<4:
            rejected['NO_COMPATIBLE_DISTRACTORS']+=1
            continue
        # Description options must not reveal the subject of their source.
        if not identify:
            chosen=[x for x in chosen if e.normalize(x['concept']) not in e.normalize(x['description'])]
            if len(chosen)<4:
                rejected['ANSWER_LEAK']+=1
                continue
        qid=a.identifier('mcq',f['id']+str(identify))
        options=[x['concept'] if identify else x['description'] for x in chosen]
        random.Random(qid).shuffle(options)
        stem=(f'Which concept does the document describe as “{f["description"]}”?' if identify else
              f'Which description best defines {f["concept"]}?' if f['family']=='DEFINITION' else
              f'What is {f["concept"]} used for according to the document?' if f['family']=='PURPOSE' else
              f'Which statement about {f["concept"]} is supported by the document?')
        result.append(candidate({'id':qid,'type':'mcq','question':stem,'options':options,
            'correctAnswer':f['concept'] if identify else f['description'],**source(f),
            'optionSources':{x['concept'] if identify else x['description']:source(x) for x in chosen},
            'relationFamily':f['family']},[f]))
    return result


def matching(facts, rejected):
    groups=defaultdict(list)
    categories=Counter((f['family'],f.get('category')) for f in facts if f.get('category'))
    for f in facts:
        if e.normalize(f['concept']) in e.normalize(f['description']):
            rejected['ANSWER_LEAK']+=1
            continue
        key=(f['family'],f['category']) if f.get('category') and categories[(f['family'],f['category'])]>=3 else (f['family'],None)
        groups[key].append(f)
    result=[]
    for group in groups.values():
        if len(group)<3:
            rejected['INSUFFICIENT_PAIR_GROUP']+=len(group)
            continue
        for start in range(0,len(group),4):
            window=group[start:start+6]
            for size in (4,5,3):
                for selected in combinations(window,size):
                    if any(not e.compatible(x,y) for x,y in combinations(selected,2)):
                        rejected['PAIR_RIGHT_TOO_SIMILAR']+=1
                        continue
                    qid=a.identifier('matching','|'.join(f['id'] for f in selected))
                    left=[{'id':f'L{i+1}','text':f['concept'],**source(f)} for i,f in enumerate(selected)]
                    right=[{'id':f'R{i+1}','text':f['description']} for i,f in enumerate(selected)]
                    random.Random(qid).shuffle(right)
                    if [r['id'] for r in right]==[f'R{i+1}' for i in range(size)]:
                        right=right[1:]+right[:1]
                    pages=[f['pageStart'] for f in selected if isinstance(f.get('pageStart'),int)]
                    result.append(candidate({'id':qid,'type':'matching','question':'Match each concept with its source-supported description.',
                        'relationFamily':selected[0]['family'],'leftItems':left,'rightItems':right,
                        'correctMatches':{f'L{i+1}':f'R{i+1}' for i in range(size)},
                        'sourceExcerpt':'\n'.join(f['sourceExcerpt'] for f in selected),
                        'sourceChunkIds':sorted({cid for f in selected for cid in f['sourceChunkIds']}),
                        'sources':[{'chunkId':cid,'page':f.get('pageStart')} for f in selected for cid in f['sourceChunkIds']],
                        'pageStart':min(pages) if pages else None,'pageEnd':max(pages) if pages else None},selected))
                    if len(result)>=100:
                        return result
    return result
