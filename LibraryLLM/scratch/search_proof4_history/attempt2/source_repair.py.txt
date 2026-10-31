"""Explicit entity operands are protected before proposing grammar repairs."""
import re
from scratch.search_v2c_c5er.candidate_search_v4.semantic_safety import prepare as propose

def prepare_source(query):
    _,proposals,_=propose(query)
    entities=[]
    for m in re.finditer(r'\b(?:by|(?:author|creator|writer)\s*[:=]|titled|called|named)\s+(?![\d\W])([^,;.!?]+)',query,re.I):
        value=m[1]
        boundary=re.search(r'\s+(?:rated|rating|published|available|titled|online|physical|excluding|exclude)\b',value,re.I)
        end=m.start(1)+(boundary.start() if boundary else len(value))
        entities.append((m.start(1),end))
    kept=[];rejected=[]
    for r in proposals:
        (rejected if any(r['start']<b and r['end']>a for a,b in entities) else kept).append(r)
    chunks=[];offsets=[];edits=[];cursor=0
    for r in kept:
        a,b,value=r['start'],r['end'],r['to'];chunks.append(query[cursor:a]);offsets.extend(range(cursor,a));start=sum(map(len,chunks))
        chunks.append(value);offsets.extend(a+min(i,b-a-1) for i in range(len(value)))
        edits.append({**r,'prepared_start':start,'prepared_end':start+len(value)});cursor=b
    chunks.append(query[cursor:]);offsets.extend(range(cursor,len(query)))
    return ''.join(chunks),edits,offsets,rejected
