"""Dedicated relation-set assessment. No dependency on MCQs or distractors."""
from collections import Counter, defaultdict
from itertools import combinations, islice
import random
from rag.services import knowledge_algorithms as a
from rag.services import knowledge_quiz_evidence as e
from rag.services import knowledge_quiz_relations as r

PROMPTS={'DEFINITION':'Match each concept to its definition.', 'PURPOSE':'Match each mechanism to its purpose.',
         'PROPERTY':'Match each concept to its characteristic.', 'FUNCTION':'Match each component to its function.',
         'COMPOSITION':'Match each item to its composition.', 'APPLICATION':'Match each topic to its source description.',
         'PROCESS':'Match each process to its specified step.'}


def verify(question, relations):
    records={x['id']:x for x in relations}
    left,right=question['leftItems'],question['rightItems']
    if not 3<=len(left)<=6 or len(left)!=len(right): return 'PAIR_COUNT'
    if len({x['id'] for x in left})!=len(left) or len({x['id'] for x in right})!=len(right): return 'DUPLICATE_ID'
    if len({r.key(x['text']) for x in left})!=len(left) or len({r.value_key(x['text']) for x in right})!=len(right): return 'DUPLICATE_PAIR'
    if set(question['correctMatches'])!={x['id'] for x in left} or set(question['correctMatches'].values())!={x['id'] for x in right}: return 'NOT_BIJECTION'
    source=[]
    for item in left:
        record=records.get(item.get('relationId'))
        target=next((x for x in right if x['id']==question['correctMatches'][item['id']]),None)
        if not record or not r.bound(record) or not target: return 'RELATION_BINDING'
        if (item['text']!=record['subjectText'] or target['text']!=record['targetText'] or item['sourceFactId']!=record['sourceFactId']
                or item['sourceExcerpt']!=record['sourceExcerpt'] or item.get('pageStart')!=record.get('pageStart')): return 'SOURCE_BINDING'
        if record['relationType']!=question['relationFamily']: return 'INCOMPATIBLE_FAMILY'
        source.append(record)
    if any(not r.compatible(x,y,relations) or not r.compatible(y,x,relations) for x,y in combinations(source,2)): return 'AMBIGUOUS_PAIR'
    return None


def candidates(relations, rejected, seed=0):
    groups=defaultdict(list)
    for relation in relations:
        if e.normalize(relation['subjectText']) in e.normalize(relation['targetText']): continue
        groups[relation['relationType']].append(relation)
    result=[];seen=set()
    for family, group in groups.items():
        random.Random(family+str(seed)).shuffle(group)
        # Up to 20 groups per family, at most 100 total, with bounded search.
        tried=0; accepted=0
        # Seed disjoint windows before exploring alternatives: taking only the
        # first combinations would make every group share the same first item.
        windows=[tuple(group[start:start+size]) for size in (4,6,3) for start in range(0,len(group),size)
                 if len(group[start:start+size])>=3]
        for size in (4,5,6,3):
            for selected in [*(windows if size==4 else []), *list(islice(combinations(group,size),1500))]:
                tried+=1
                if tried>1500 or accepted>=20 or len(result)>=100: break
                if any(not r.compatible(x,y,relations) or not r.compatible(y,x,relations) for x,y in combinations(selected,2)):
                    rejected['AMBIGUOUS_PAIR']=rejected.get('AMBIGUOUS_PAIR',0)+1;continue
                qid=a.identifier('matching','|'.join(x['id'] for x in selected)+str(seed))
                if qid in seen:continue
                left=[{'id':a.identifier('left',qid+x['id']), 'text':x['subjectText'], 'relationId':x['id'],
                       'sourceFactId':x['sourceFactId'], **r.source(x)} for x in selected]
                right=[{'id':a.identifier('right',x['id']+qid), 'text':x['targetText']} for x in selected]
                mapping={l['id']:v['id'] for l,v in zip(left,right)}
                random.Random(qid).shuffle(right)
                if [x['id'] for x in right]==list(mapping.values()): right=right[1:]+right[:1]
                pages=[x['pageStart'] for x in selected if isinstance(x.get('pageStart'),int)]
                prompt=f'Match each concept to its {family.split(":",1)[1]}.' if family.startswith('NUMERIC:') else PROMPTS.get(family,PROMPTS['PROPERTY'])
                question={'id':qid,'type':'matching','question':prompt,
                    'relationFamily':family,'leftItems':left,'rightItems':right,'correctMatches':mapping,
                    'sourceExcerpt':'\n'.join(x['sourceExcerpt'] for x in selected),
                    'sourceChunkIds':sorted({c for x in selected for c in x['sourceChunkIds']}),
                    'sources':[{'chunkId':c,'page':x.get('pageStart')} for x in selected for c in x['sourceChunkIds']],
                    'pageStart':min(pages) if pages else None,'pageEnd':max(pages) if pages else None,
                    'qualityScore':round(sum(x['confidence']+min(x.get('score',0)/15,1) for x in selected)/len(selected),3),
                    '_facts':{e.normalize(x['sourceExcerpt']) for x in selected}, '_fact_ids':{x['sourceFactId'] for x in selected},
                    '_relations':{x['id'] for x in selected},'_concepts':{e.normalize(x['subjectText']) for x in selected},
                    '_targets':{r.value_key(x['targetText']) for x in selected},
                    '_sections':{x.get('section') or x.get('pageStart') for x in selected}}
                reason=verify(question,relations)
                if reason: rejected[reason]=rejected.get(reason,0)+1;continue
                seen.add(qid);result.append(question);accepted+=1
            if tried>1500 or accepted>=20 or len(result)>=100: break
    return result


def select(candidates, requested_pairs, used_facts=(), used_concepts=(), used_relations=()):
    # Bounded global search avoids a first attractive group starving later sets.
    # At most 100 candidates, 80 beam states and ten allocation steps.
    pool=sorted(candidates,key=lambda x:(-x['qualityScore'],len(x['leftItems'])!=4,x['id']))[:100]
    initial=([],set(used_facts),set(used_concepts),set(used_relations),set(),0,0.0,-1)
    beam=[initial];best=initial
    for _ in range(min(10,requested_pairs//3)):
        states={}
        for chosen,facts,concepts,relations,targets,total,score,start in beam:
            for index in range(start+1,len(pool)):
                q=pool[index];size=len(q['leftItems'])
                if total+size>requested_pairs or q['_facts']&facts or q['_concepts']&concepts or q['_relations']&relations or q['_targets']&targets:continue
                state=([*chosen,q],facts|q['_facts'],concepts|q['_concepts'],relations|q['_relations'],targets|q['_targets'],
                       total+size,score+q['qualityScore']*size+.01*(size==4),index)
                identity=frozenset(state[3])
                if identity not in states or state[6]>states[identity][6]:states[identity]=state
        if not states:break
        beam=sorted(states.values(),key=lambda s:(s[5],s[6]),reverse=True)[:80]
        if (beam[0][5],beam[0][6])>(best[5],best[6]):best=beam[0]
    selected,pairs=best[0],best[5]
    return selected,{'sets':len(selected),'pairs':pairs,'requestedPairs':requested_pairs,
        'duplicateLeft':0,'duplicateRight':0,'duplicateRelations':0}
