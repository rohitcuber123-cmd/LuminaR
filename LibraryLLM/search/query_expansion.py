"""Bounded, read-only co-subject projection of existing metadata graph edges.

No inferred edges are persisted. One projected subject hop is exactly the two
existing HAS_SUBJECT edges through a currently authorized canonical book.
"""
from collections import Counter
from pathlib import Path
import json
import sqlite3
from time import perf_counter
from search.query_plan import normalize, values

MAX_PRIMARY=3
MAX_RELATED=6
MAX_BOOKS=64
MAX_EDGES=1024
GENERIC={'general','fiction','nonfiction','history','science','computers','juvenile literature','congresses'}

def primaries(plan):return list(dict.fromkeys([*plan.subjects,plan.semantic_text or '']))[:MAX_PRIMARY]

def select_related(plan, evidence):
    primary={normalize(v) for v in primaries(plan)}
    excluded=[normalize(v) for v in [*plan.exclude_terms,*plan.exclude_subjects]]
    counts=Counter(label for label in evidence if normalize(label) not in primary|GENERIC
                   and 1<len(label)<=80 and len(label.split())<=8
                   and not any(term in normalize(label) for term in excluded))
    result=[];seen=set()
    for label,_ in sorted(counts.items(),key=lambda p:(-p[1],normalize(p[0]),p[0])):
        if normalize(label) in seen:continue
        result.append(label);seen.add(normalize(label))
        if len(result)==MAX_RELATED:break
    return result

def global_expansion(plan,books,path=None):
    from knowledge_graph.core import DEFAULT_GRAPH,canonical
    started=perf_counter();path=Path(path or DEFAULT_GRAPH)
    result={'status':'UNAVAILABLE','generation':None,'concepts':[],'evidence_book_count':0,'projected_hops':1,'max_related':MAX_RELATED}
    if not plan.semantic_text or plan.mode!='SMART':return result
    try:
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=.1) as graph:
            graph.set_progress_handler(lambda:int(perf_counter()-started>.25),1000)
            meta=json.loads(graph.execute("SELECT value FROM meta WHERE key='summary'").fetchone()[0])
            result.update(status='READY',generation=meta['version']+':'+meta['catalogue_hash'])
            seeds=[]
            for term in primaries(plan):
                seeds.extend(row[0] for row in graph.execute("SELECT book_id FROM edges WHERE kind='subject' AND term=? ORDER BY book_id LIMIT ?",(canonical(term),MAX_BOOKS)))
            seeds=list(dict.fromkeys(seeds))[:MAX_BOOKS]
            if not seeds:return result
            marks=','.join('?' for _ in seeds)
            edges=graph.execute(f"SELECT b.work_id,e.label FROM edges e JOIN books b ON b.id=e.book_id WHERE e.book_id IN ({marks}) AND e.kind='subject' ORDER BY e.book_id,e.term LIMIT ?",[*seeds,MAX_EDGES]).fetchall()
        work_ids=list(dict.fromkeys(wid for wid,_ in edges))
        current={r['work_id']:r for r in books.find({'work_id':{'$in':work_ids}},{'_id':0,'work_id':1,'subjects':1}).max_time_ms(300)}
        primary={normalize(p) for p in primaries(plan)};evidence=[];valid=set()
        for wid,label in edges:
            subjects={normalize(v) for v in values(current.get(wid,{}).get('subjects'))}
            if subjects&primary and normalize(label) in subjects:evidence.append(label);valid.add(wid)
        result.update(concepts=select_related(plan,evidence),evidence_book_count=len(valid))
    except Exception:
        # Optional graph lookup must not affect normal retrieval or authority.
        result.update(status='UNAVAILABLE',concepts=[],generation=None)
    finally:result['elapsed_ms']=round((perf_counter()-started)*1000,3)
    return result

def tenant_expansion(plan,library_id,actor,staff=False):
    from backend.services import library_catalogue_experience as catalogue,library_intelligence_store as store
    from backend.services.library_intelligence_service import target_status,graph_cache
    started=perf_counter();result={'status':'NOT_USED','generation':None,'concepts':[],'evidence_book_count':0,'projected_hops':1,'max_related':MAX_RELATED}
    # Authorization is outside optional graph error handling: never swallow denial.
    with catalogue.read_context(library_id,actor,staff=staff):
        if not plan.semantic_text or plan.mode!='SMART':return result
        try:
            status=target_status(library_id,'KNOWLEDGE_GRAPH',observe_stale=False)
            result['status']=status['status']
            if status['status']!='READY':return result
            manifest,_,graph=graph_cache.load(library_id,'KNOWLEDGE_GRAPH',status['active_generation_id'],status['manifest_checksum'])
            if manifest['library_id']!=library_id:raise ValueError('Graph scope mismatch')
            nodes={n['id']:n for n in graph['nodes']}
            primary={normalize(p) for p in primaries(plan)}
            primary_ids={n['id'] for n in graph['nodes'] if n['type']=='Subject' and normalize(n['label']) in primary}
            seed_nodes=sorted({e['source'] for e in graph['edges'] if e['target'] in primary_ids and e['relation']=='HAS_SUBJECT'})[:MAX_BOOKS]
            bids=[nodes[n]['library_book_id'] for n in seed_nodes]
            canonical=list(store.collection('library_books').aggregate([*catalogue.usable(library_id,staff=staff),{'$match':{'library_book_id':{'$in':bids}}},{'$project':{'library_book_id':1,'subjects':1}}])) if bids else []
            current={r['library_book_id']:{normalize(s) for s in r.get('subjects',[])} for r in canonical}
            evidence=[];valid=set()
            for edge in [e for e in graph['edges'] if e['source'] in seed_nodes and e['relation']=='HAS_SUBJECT'][:MAX_EDGES]:
                node=nodes[edge['target']];bid=nodes[edge['source']]['library_book_id'];subjects=current.get(bid,set())
                if subjects&primary and normalize(node['label']) in subjects:evidence.append(node['label']);valid.add(bid)
            result.update(generation=status['active_generation_id'],concepts=select_related(plan,evidence),evidence_book_count=len(valid))
        except Exception:result.update(status='UNAVAILABLE',concepts=[],generation=None)
        finally:result['elapsed_ms']=round((perf_counter()-started)*1000,3)
    return result

def apply_expansion(plan,expansion):
    plan.expanded_subjects=list(expansion['concepts'])[:MAX_RELATED]
    plan.kg_expansion_used=bool(plan.expanded_subjects)
    plan.kg_generation=expansion['generation'] if plan.kg_expansion_used else None

def expansion_query(plan):
    return (plan.semantic_text or '')+'; related catalogue subjects: '+'; '.join(plan.expanded_subjects)
