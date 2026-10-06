"""Validate offline paraphrases and audit corpus diversity without TEST tuning."""
import json
import random
import re
import sys
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from router_v4_data import seed_rows,build,norm
from assistant.router_v3 import embedding_encoder

def write(name,data): (ROOT/'reports'/('assistant_router_v4_'+name+'.json')).write_text(json.dumps(data,indent=2),encoding='utf8')

def statistics(rows):
    messages=[r['message'] for r in rows];tokens=[norm(m).split() for m in messages];vocab=Counter(t for ts in tokens for t in ts)
    unique=list(dict.fromkeys(norm(m) for m in messages));grams=Counter(g for m in unique for g in zip(m.split(),m.split()[1:]))
    # Delexicalised skeletons remove changing politeness, topic/title/ordinal
    # slots. This diagnostic deliberately is not used by production routing.
    from router_v3_data import TOPICS as V3_TOPICS, REFERENCES as V3_REFS, FIELDS as V3_FIELDS, PURPOSES as V3_PURPOSES
    from router_v4_data import TOPICS,REFS,FIELDS,PURPOSES
    slots=sorted(set([*V3_TOPICS,*TOPICS,*V3_PURPOSES,*PURPOSES,*[s for g in V3_REFS.values() for s in g],
            *[s for g in REFS.values() for s in g],*[s for g in V3_FIELDS.values() for s in g],*[s for g in FIELDS.values() for s in g]]),key=len,reverse=True)
    skeletons=[]
    for m in messages:
        text=norm(m)
        for slot in slots:
            if slot:text=text.replace(norm(slot),'SLOT')
        for prefix in ['please','hello','could you help','for me']:
            if text.startswith(prefix+' '):text=text[len(prefix):].strip()
        text=re.sub(r'\b(first|second|former|latter|last|final|one|two)\b','SLOT',text)
        skeletons.append(text)
    return {'cases':len(rows),'unique_messages':len(unique),'unique_skeletons':len(set(skeletons)),
        'cases_per_skeleton':len(rows)/max(1,len(set(skeletons))),
        'semantic_families':len({r.get('family_id',r.get('template_group',r['message'])) for r in rows}),
        'unique_messages_per_family':len(unique)/max(1,len({r.get('family_id',r.get('template_group',r['message'])) for r in rows})),
        'words_mean':float(np.mean([len(x) for x in tokens])),
        'words_quantiles':np.quantile([len(x) for x in tokens],[0,.25,.5,.75,1]).tolist(),
        'vocabulary':len(vocab),'top_words':vocab.most_common(25),'distinct_bigram_ratio':len(grams)/max(1,sum(grams.values())),
        'question_fraction':sum('?' in m for m in messages)/len(messages),
        'first_word_distribution':dict(Counter(ts[0] for ts in tokens if ts)),
        'context':dict(Counter(r.get('context_kind',r.get('context','unknown')) if not isinstance(r.get('context'),dict) else
             r.get('context_kind','sel'+str(len(r['context'].get('selected_books',[])))+'focus'+str(len(r['context'].get('last_referenced_work_ids',[])))) for r in rows)),
        'intent':dict(Counter(r.get('intent_subtypes',r.get('expected_intent')) for r in rows)),
        'reference':dict(Counter(r.get('reference',r.get('context_kind',r.get('context','unknown'))) if not isinstance(r.get('context'),dict) else r.get('reference','unknown') for r in rows)),
        'position':dict(Counter(r.get('position','not independently labelled') for r in rows))}

def main():
    data=ROOT/'training/assistant_router_v4';seeds=seed_rows();raw={r['seed_id']:r for r in map(json.loads,(data/'generation_raw.jsonl').read_text(encoding='utf8').splitlines())}
    if len(raw)!=len(seeds):raise SystemExit('Generation unfinished; refusing partial corpus')
    encoder=embedding_encoder();pairs=[];rejections=Counter();seen=set()
    for s in seeds:
        slots=re.findall(r'\{[^}]+\}',s['message'])
        for i,text in enumerate(raw[s['seed_id']]['texts']):
            reason=None
            if not 8<=len(text)<=300:reason='length'
            elif any(text.count(slot)!=1 for slot in slots) or sorted(re.findall(r'\{[^}]+\}',text))!=sorted(slots):reason='placeholder_drift'
            elif '\n' in text or text.count('?')>1 or text.count('"') or re.search(r'https?://|\bOL\d+W\b',text):reason='format_or_entity'
            elif norm(text) in seen or norm(text)==norm(s['message']):reason='duplicate'
            if reason:rejections[reason]+=1;continue
            seen.add(norm(text));pairs.append({'seed_id':s['seed_id'],'seed':s['message'],'text':text,'split':s['split'],'subtype':s['subtype'],'index':i})
    seed_vec=encoder.encode([p['seed'] for p in pairs],normalize_embeddings=True,batch_size=64,show_progress_bar=False)
    para_vec=encoder.encode([p['text'] for p in pairs],normalize_embeddings=True,batch_size=64,show_progress_bar=False)
    accepted=[]
    for p,sim in zip(pairs,np.sum(seed_vec*para_vec,axis=1)):
        p['similarity']=float(sim)
        if .55<=sim<=.965:accepted.append(p)
        else:rejections['similarity_'+('too_close' if sim>.965 else 'too_far')]+=1
    (data/'validated_paraphrases.json').write_text(json.dumps(accepted,indent=2),encoding='utf8')
    grouped=defaultdict(list)
    for p in accepted:grouped[p['subtype']].append(p)
    rng=random.Random(947);review=[]
    for group in grouped.values():review.extend(rng.sample(group,min(8,len(group))))
    remaining=[p for p in accepted if p not in review];review+=rng.sample(remaining,max(0,200-len(review)))
    (data/'manual_review.json').write_text(json.dumps(review,indent=2),encoding='utf8')
    write('generation_quality',{'generated':sum(len(r['texts']) for r in raw.values()),'validated':len(accepted),'rejections':dict(rejections),
        'similarity_band':[.55,.965],'label_source':'Manually authored seed; Qwen only paraphrases','review_samples':len(review),
        'review_status':'PENDING manual inspection; training guard requires approved_review.json','sources':['manual semantic seeds','existing local Qwen2.5-3B offline paraphrases','context permutations','generic character swaps']})
    print('VALIDATED',len(accepted),'REVIEW',len(review),flush=True)

if __name__=='__main__':main()
