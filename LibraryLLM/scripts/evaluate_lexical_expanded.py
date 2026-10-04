"""Broader read-only quality sample derived from verified catalogue values."""
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
from pymongo import MongoClient
from search.lexical_delta import LexicalOverlayStore
from search.lexical_store import FIRST_VALUE_SQL,NEXT_VALUE_SQL,prefix_upper
from search.typo_assistance import normalize_structured


def sample_values(store,books,typ):
    sampled=[]
    seen=set()
    prefixes=list('abcdefghijklmnopqrstuvwxyz')+['é','ñ','ü','中','α']
    for prefix in prefixes:
        upper=prefix_upper(prefix)
        prior=None
        for _ in range(12):
            if prior is None:
                row=store.db.execute(FIRST_VALUE_SQL,(typ,prefix,upper)).fetchone()
            else:
                row=store.db.execute(NEXT_VALUE_SQL,(typ,prior,upper)).fetchone()
            if row is None: break
            value=row[0];prior=value
            if value in seen or len(value)<5 or len(value)>100: continue
            ids=store.work_ids_for_value(typ,value,1)
            if not ids: continue
            doc=books.find_one({'work_id':ids[0]},{'_id':0,'title':1,'authors':1})
            if not doc: continue
            original=[doc.get('title')] if typ=='TITLE' else doc.get('authors') or []
            if isinstance(original,str): original=[original]
            if value not in {normalize_structured(x) for x in original if isinstance(x,str)}:
                continue
            seen.add(value)
            sampled.append({'type':typ,'value':value,'work_id':ids[0],
                            'original':next((x for x in original if isinstance(x,str)
                                             and normalize_structured(x)==value),value)})
    return sampled


def mutation(value,position,kind):
    if kind=='delete': return value[:position]+value[position+1:]
    if kind=='transpose' and position+1<len(value):
        return value[:position]+value[position+1]+value[position]+value[position+2:]
    if kind=='duplicate': return value[:position]+value[position]+value[position:]
    return value


def category(entry):
    value=entry['value']
    if any(ord(c)>127 for c in value): return 'unicode'
    if any(c in value for c in ':;,&/()[]!?'): return 'punctuation'
    if entry['type']=='TITLE' and len(value.split())>=3: return 'multiword_title'
    if entry['type']=='TITLE' and entry['original'][:1].isupper(): return 'capitalized_title'
    if entry['type']=='AUTHOR' and len(value)<=10: return 'short_author'
    if entry['type']=='AUTHOR' and len(value)>=25: return 'long_author'
    return 'other'


def main():
    load_dotenv(ROOT/'.env')
    root=Path(os.getenv('LUMINAR_LEXICAL_PATH',ROOT/'datasets/ai/lexical/published'))
    store=LexicalOverlayStore(root)
    if not store.health()['lexical_available']: raise RuntimeError(store.health())
    with MongoClient(os.getenv('MONGO_URI','mongodb://localhost:27017')) as client:
        books=client[os.getenv('MONGO_DB_NAME','luminar_library')].books
        entries=sample_values(store,books,'TITLE')+sample_values(store,books,'AUTHOR')
    # Take a deterministic spread from each category; expected labels come
    # only from current Mongo-verified normalized fields above.
    selected=[]
    for name in sorted({category(e) for e in entries}):
        selected.extend([e for e in entries if category(e)==name][:12])
    typo_cases=[]
    false_cases=[]
    for entry in selected:
        typ=entry['type']; value=entry['value']
        exact=store.fuzzy(typ,value)
        false_cases.append({'kind':'verified_exact','type':typ,'query':value,
                            'selected':exact['match'],'reason':exact['reason']})
        first_word=value.split(' ')[0]
        if len(first_word)>=5 and first_word!=value:
            result=store.fuzzy(typ,first_word)
            false_cases.append({'kind':'valid_leading_term','type':typ,'query':first_word,
                                'selected':result['match'],'reason':result['reason']})
        alpha=[i for i,c in enumerate(value) if c.isalpha()]
        if not alpha: continue
        positions=[alpha[min(2,len(alpha)-1)]]
        if typ=='AUTHOR' and ' ' in value:
            surname=value.rfind(' ')+1
            if surname<len(value)-2: positions.append(surname+1)
        for position in dict.fromkeys(positions):
            for kind in ('delete','transpose','duplicate'):
                query=mutation(value,position,kind)
                if query==value or len(query)<5 or store.exact(typ,query,1): continue
                result=store.fuzzy(typ,query)
                typo_cases.append({'type':typ,'category':category(entry),'mutation':kind,
                                   'query':query,'expected':value,
                                   'selected':result['match']['value'] if result['match'] else None,
                                   'reason':result['reason'],
                                   'correct':bool(result['match'] and result['match']['value']==value
                                                  and entry['work_id'] in result['work_ids'])})
    # Short, numeric and technology controls are valid uncorrected intents.
    for query in ('AI','it','C++','C#','1984','python','java','foundation'):
        result=store.fuzzy('TITLE',query)
        false_cases.append({'kind':'required_control','type':'TITLE','query':query,
                            'selected':result['match'],'reason':result['reason']})
    output={'sampled_values':len(entries),'verified_selected_values':len(selected),
            'typos':{'total':len(typo_cases),'correct':sum(x['correct'] for x in typo_cases),
                     'cases':typo_cases},
            'false_probes':{'total':len(false_cases),
                            'selections':sum(x['selected'] is not None for x in false_cases),
                            'cases':false_cases}}
    (root/'expanded_benchmark.json').write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'sampled_values':output['sampled_values'],
                      'selected_values':output['verified_selected_values'],
                      'typo_correct':output['typos']['correct'],
                      'typo_total':output['typos']['total'],
                      'false_selections':output['false_probes']['selections'],
                      'false_total':output['false_probes']['total']},indent=2))
    store.close()


if __name__=='__main__': main()
