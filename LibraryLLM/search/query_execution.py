"""Shared human-query execution over accepted catalogue providers."""
from dataclasses import asdict
import re
from time import perf_counter
from fastapi import HTTPException
from search.query_plan import parse_query, matches, normalize, sort_books, primary_match
from search.query_expansion import global_expansion,tenant_expansion,apply_expansion,expansion_query
from search.catalogue import current_books
from search.session_store import resolve as resolve_session
from search import personalization
from search.query_session import active
from search.query_confidence import executable

STRUCTURED_LIMIT = 1000


def interpretation(plan, notice=''):
    result = plan.public()
    from search.query_session import item_edit_key
    for chip in result['chips']:
        if chip['key']=='subject' and len(plan.subjects)>1:
            value=next(s for s in plan.subjects if chip['label']=='Genre / Subject: '+s)
            chip['remove_key']=item_edit_key('subject',value)
        elif chip['key']=='exclude' and len(set(plan.exclude_terms+plan.exclude_subjects))>1:
            value=next(s for s in plan.exclude_terms+plan.exclude_subjects if chip['label'] in ('Exclude: '+s,'Exclude subject: '+s))
            chip['remove_key']=item_edit_key('exclude',value)
    if notice: result['notice'] = notice
    return result


def interaction_for(plan,session,actor,**options):
    if executable(plan) and not plan.corrections:return None
    from search.query_interaction import offer
    return offer(plan,session,actor,**options)

def guarded_response(query,plan,session,personalized,offset,limit,start,source=None,diagnostics=False):
    response={'query':query,'results':[],'returned':0,'total':0,'total_ranked_candidates':0,'has_more':False,
      'offset':offset,'limit':limit,'next_offset':None,
      'interpretation':{**interpretation(plan,plan.decision['safe_public_message']),'session':session,'personalized':personalized},
      'timing_ms':{'total':round((perf_counter()-start)*1000,2)}}
    if source:
        source['catalogue_source']='LIBRARY_LOCAL';source['capabilities'].update(local_search=True,global_discovery=False)
        response['source']=source
    if diagnostics:response['diagnostics']={'plan':asdict(plan),'provider':'GUARDED_QUERY','hnsw_used':False,'kg_used':False,'reranker_used':False,'profile':{'cache':'OFF','elapsed_ms':0}}
    return response


def global_facets(engine):
    # Facets are optional enrichment for catalogue providers exposing only find.
    # Preserve normal Mongo failures (including authorization), rather than
    # substituting another client or changing semantic ranking on an error.
    database = getattr(engine.books_collection, 'database', None)
    rows = [] if database is None else list(database.book_categories.find({}, {'_id':0,'name':1,'category':1,'count':1}).sort('count',-1).limit(4096))
    facets = [{'subject':r.get('name') or r.get('category'),'count':r.get('count',0)} for r in rows if r.get('name') or r.get('category')]
    return {'results':facets,'capabilities':{'rating':True,'year':False,'language':False,
            'formats':['ONLINE'],'availability':False},'has_more':len(rows)==4096}


class GlobalQuerySearch:
    def __init__(self,engine):self.engine=engine

    def search(self, query, actor, *, mode='SMART', filters=None, omit=(), offset=0, limit=10, diagnostics=False,kg_enabled=True,session_id=None,personalized=False,resolution=None,runtime=None):
        start=perf_counter();engine=self.engine;facets=global_facets(engine)
        plan,session=(runtime.resolve if runtime else resolve_session)(query,actor,[r['subject'] for r in facets['results']],mode=mode,filters=filters,omit=omit,session_id=session_id,capabilities=facets['capabilities'],**(resolution or {}))
        interaction=interaction_for(plan,session,actor,query=query,mode=mode,filters=filters,omit=omit,session_id=session_id,capabilities=facets['capabilities']) if not resolution and runtime is None else None
        if not executable(plan):
            response=guarded_response(query,plan,session,personalized,offset,limit,start,diagnostics=diagnostics)
            response['interpretation']['clarification']=interaction
            return response
        expansion=global_expansion(plan,engine.books_collection) if kg_enabled and plan.semantic_text else {'status':'NOT_USED','concepts':[],'generation':None,'elapsed_ms':0}
        apply_expansion(plan,expansion)
        # Online means this account's existing digital reading entitlement.
        online=set()
        if plan.formats or plan.availability or runtime is not None and plan.excluded_formats:
            from backend.services.book_capability_service import active_borrow_ids, catalog_capabilities
            online={r['work_id'] for r in catalog_capabilities(list(active_borrow_ids(int(actor['sub'])))) if r.get('readable')}
        def canonical(book):
            return dict(book,has_online=book.get('work_id') in online,has_physical=False)
        def accepted(book):return (runtime.matches if runtime else matches)(plan,canonical(book))
        provider='STRUCTURED_METADATA';hnsw=False;reranked=False;count=0;retrieval_diagnostics={}
        if plan.semantic_text and not plan.unknown_subject:
            constrained=bool(plan.subjects or plan.author_text or plan.rating_min is not None or plan.rating_max is not None or plan.year_min is not None or plan.year_max is not None or plan.formats or plan.availability or plan.language or plan.exclude_terms or plan.exclude_subjects)
            if runtime is not None:constrained=runtime.has_hard(plan)
            options={}
            if plan.kg_expansion_used:options.update(expansion_query=expansion_query(plan),primary_predicate=lambda book:primary_match(plan,book))
            if plan.ranking_query()!=plan.semantic_text:options['rerank_query']=plan.ranking_query()
            response=engine.search(query=runtime.semantic_query(plan) if runtime else plan.semantic_text,top_k=50,library_id=None,
                                   available_at_library=False,diagnostics=True,metadata_predicate=accepted if constrained else None,**options)
            retrieval_diagnostics=response.get('diagnostics',{})
            ids=[r['work_id'] for r in response['results']];metadata=current_books(engine.books_collection,ids)
            rows=[dict(metadata[r['work_id']],rerank_score=r.get('rerank_score'),hnsw_score=r.get('hnsw_score')) for r in response['results'] if r['work_id'] in metadata and accepted(metadata[r['work_id']])]
            count=retrieval_diagnostics.get('candidate_count',len(retrieval_diagnostics.get('raw_hnsw',[])));provider='GLOBAL_SEMANTIC';hnsw=True;reranked=True
        else:
            predicates=[];subject_candidates=None
            if plan.subjects and not plan.author_text and not plan.exact_text and not plan.title_text:
                counts={}
                for row in facets['results']:counts[normalize(row['subject'])]=max(counts.get(normalize(row['subject']),0),row['count'])
                subject=min(plan.subjects,key=lambda s:counts.get(normalize(s),float('inf'))) if len(plan.subjects)>1 else plan.subjects[0]
                if len(plan.subjects)>1 or 0 < counts.get(normalize(subject),0) < 10000:
                    from search.structured_subjects import candidate_ids
                    try:indexed=any(list(index['key'])==[('work_id',1)] for index in engine.books_collection.index_information().values())
                    except (AttributeError,TypeError):indexed=False
                    shortcut=candidate_ids(subject,STRUCTURED_LIMIT) if indexed else None
                    if shortcut:
                        predicates.append({'work_id':{'$in':shortcut}})
                        subject_candidates=shortcut
                        provider='STRUCTURED_SUBJECT_METADATA'
                    elif len(plan.subjects)>1:
                        # Newly composed ALL-subject clauses require the existing
                        # bounded indexed path, never a broad Mongo regex scan.
                        raise HTTPException(503,'Indexed subject lookup is unavailable. Retry with a topic or narrower subject.')
            lexical=getattr(engine,'lexical_store',None)
            if plan.author_text and lexical:
                # Existing AUTHOR sidecar provides indexed IDs. Hydration and
                # the canonical predicate still verify the author's current text.
                author_ids=[wid for _,wid in lexical.exact('AUTHOR',plan.author_text,limit=100)]
                if not author_ids:
                    try:
                        first=next(iter(engine.books_collection.find({'authors':{'$regex':re.escape(plan.author_text),'$options':'i'}},{'_id':0,'authors':1}).sort('book_id',1).limit(1).max_time_ms(1500)),None)
                        if first:
                            from search.query_plan import values
                            for author in values(first.get('authors'),';'):
                                if normalize(plan.author_text) in normalize(author):author_ids.extend(wid for _,wid in lexical.exact('AUTHOR',author,limit=100))
                    except Exception:pass
                if author_ids:predicates.append({'work_id':{'$in':list(dict.fromkeys(author_ids))}})
            for subject in plan.subjects:
                predicates.append({'subjects':{'$regex':r'(^|\|)\s*'+re.escape(subject)+r'\s*(\||$)','$options':'i'}})
            if plan.author_text:predicates.append({'authors':{'$regex':re.escape(plan.author_text),'$options':'i'}})
            rating={}
            for value,exclusive,low in [(plan.rating_min,plan.rating_min_exclusive,True),(plan.rating_max,plan.rating_max_exclusive,False)]:
                if value is not None:rating[('$gt' if exclusive else '$gte') if low else ('$lt' if exclusive else '$lte')]=value
            if rating:predicates.append({'average_rating':{'$type':'number',**rating}})
            if plan.formats or plan.availability:predicates.append({'work_id':{'$in':sorted(online)}})
            if runtime is not None and 'ONLINE' in plan.excluded_formats:predicates.append({'work_id':{'$nin':sorted(online)}})
            ids=None
            if plan.title_text or plan.exact_text:
                ids=[];text=plan.exact_text or plan.title_text
                if lexical:
                    for kind in ('TITLE',) if plan.exact_text else ('TITLE','AUTHOR'):
                        found=lexical.exact(kind,text,limit=50)
                        ids.extend(wid for _,wid in found)
                        if not found and not plan.exact_text:
                            result=lexical.fuzzy(kind,text)
                            match=result.get('match')
                            if match:
                                ids.extend(result.get('work_ids',[]));plan.corrections.append({'from':text,'to':match['value'],'kind':'title_author_typo'})
                                plan.title_text=match['value']
                if plan.exact_text and re.fullmatch(r'OL\d+W',plan.exact_text,re.I):ids.append(plan.exact_text.upper())
                if ids:predicates.append({'work_id':{'$in':list(dict.fromkeys(ids))}})
                elif plan.exact_text:
                    predicates.append({'$or':[{k:plan.exact_text} for k in ('isbn_10','isbn_13','work_id')]+[{'title':{'$regex':'^'+re.escape(plan.exact_text)+'$','$options':'i'}}]})
                else:predicates.append({'$or':[{'title':{'$regex':re.escape(text),'$options':'i'}},{'authors':{'$regex':re.escape(text),'$options':'i'}}]})
                provider='EXACT_LOOKUP' if plan.exact_text else 'TITLE_AUTHOR_LEXICAL'
            if plan.unknown_subject or session is not None and not active(plan):rows=[]
            else:
                mongo_query={'$and':predicates} if predicates else {}
                try:
                    cursor=engine.books_collection.find(mongo_query,{'_id':0})
                    if subject_candidates:cursor=cursor.hint([('work_id',1)])
                    raw=list(cursor.sort('book_id',1).limit(STRUCTURED_LIMIT).max_time_ms(6000))
                except Exception as error:raise HTTPException(503,'Structured catalogue lookup is busy. Retry with a narrower filter.') from error
                count=len(raw);rows=[b for b in raw if accepted(b)]
        rows=[canonical(book) for book in sort_books(rows,plan)[:50]]
        profile,profile_diagnostics=personalization.safe_profile(actor,engine.books_collection) if personalized else (None,{'cache':'OFF','elapsed_ms':0})
        rows,ranking_diagnostics=personalization.rerank(rows,plan,profile,personalized)
        total=len(rows);page=rows[offset:offset+limit]
        result=[]
        from backend.services.book_capability_service import with_capabilities
        page=with_capabilities(page)
        for i,book in enumerate(page,offset+1):
            result.append(dict(canonical(book),rank=i,rating=book.get('average_rating'),read_logs=book.get('reading_log_count'),
                               physical_copies=0,available_physical_copies=0,library_available=False))
        notices=[]
        if plan.year_min is not None or plan.year_max is not None:notices.append('Publication year is not available in the current global catalogue metadata.')
        if any(f in ('PHYSICAL','BOTH') for f in plan.formats) or plan.availability:notices.append('Physical availability is library-specific. Choose a library for authoritative stock.')
        response={'system':'LuminaR','query':query,'results':result,'returned':len(result),'offset':offset,'limit':limit,
                  'total_ranked_candidates':total,'has_more':offset+limit<total,'next_offset':offset+limit if offset+limit<total else None,
                  'interpretation':{**interpretation(plan,' '.join(notices)),'session':session,'personalized':personalized,'clarification':interaction},
                  'timing_ms':{'total':round((perf_counter()-start)*1000,2)}}
        if diagnostics:response['diagnostics']={'plan':asdict(plan),'provider':provider,'hnsw_used':hnsw,'kg_used':plan.kg_expansion_used,'kg':expansion,'reranker_used':reranked,'candidate_count':count,'strict_filters':True,'fallback_used':False,'candidate_bound':STRUCTURED_LIMIT,'final_count':len(result),'expansion_added_candidates':retrieval_diagnostics.get('expansion_added_candidates',0),'expansion_reranked_count':retrieval_diagnostics.get('expansion_reranked_count',0),'hnsw_generation':getattr(getattr(getattr(engine,'index_manager',None),'snapshot',None),'manifest',None)}
        if diagnostics:response['diagnostics'].update(personalization=ranking_diagnostics,profile=profile_diagnostics)
        return response


def tenant_facets(library_id,actor,staff=False):
    from backend.services import library_catalogue_experience as catalogue
    with catalogue.read_context(library_id,actor,staff=staff):
        rows=catalogue.subject_rows(library_id,limit=2048,staff=staff)
        return {**rows,'capabilities':{'rating':True,'year':True,'language':True,'formats':['PHYSICAL','ONLINE','BOTH'],'availability':True}}


def tenant_search(service,library_id,actor,query,**options):
    try:
        return _tenant_search(service,library_id,actor,query,**options)
    except HTTPException as error:
        if error.status_code in (401,403,404):
            from search.scope_authorization import invalidate_if_access_lost
            invalidate_if_access_lost(actor,library_id,staff=options.get('staff',False))
        raise


def _tenant_search(service,library_id,actor,query,*,staff=False,mode='SMART',filters=None,omit=(),offset=0,limit=20,diagnostics=False,kg_enabled=True,session_id=None,personalized=False,resolution=None,runtime=None):
    from backend.services import library_catalogue_experience as catalogue
    from backend.services import library_intelligence_store as store, library_intelligence_artifacts as artifacts
    from backend.services.library_intelligence_service import target_status
    start=perf_counter()
    # Authority precedes every facet lookup, cache/index access and hydration.
    with catalogue.read_context(library_id,actor,staff=staff) as (library,membership,canonical):
        facets=catalogue.subject_rows(library_id,limit=2048,staff=staff)
        capabilities={'rating':True,'year':True,'language':True,'availability':True,'formats':['ONLINE','PHYSICAL','BOTH']}
        plan,session=(runtime.resolve if runtime else resolve_session)(query,actor,[r['subject'] for r in facets['results']],mode=mode,filters=filters,omit=omit,session_id=session_id,library_id=library_id,staff=staff,capabilities=capabilities,**(resolution or {}))
        interaction=interaction_for(plan,session,actor,query=query,mode=mode,filters=filters,omit=omit,session_id=session_id,capabilities=capabilities,library_id=library_id,staff=staff) if not resolution and runtime is None else None
        status=target_status(library_id,'SEARCH_INDEX')
        source=catalogue.source_locked(library_id,library,membership,canonical,staff=staff)
        if not executable(plan):
            response=guarded_response(query,plan,session,personalized,offset,limit,start,source,diagnostics)
            response['interpretation']['clarification']=interaction
            return response
    expansion=tenant_expansion(plan,library_id,actor,staff) if kg_enabled and plan.semantic_text else {'status':'NOT_USED','concepts':[],'generation':None,'elapsed_ms':0}
    apply_expansion(plan,expansion)
    provider='STRUCTURED_METADATA';hnsw=False;reranked=False;fallback=False;scores={};ids=None;generation=None;extra_ids=set()
    if plan.semantic_text:
        if status['status']=='READY':
            try:
                manifest,records,index=service.cache.load(library_id,'SEARCH_INDEX',status['active_generation_id'],status['manifest_checksum'])
                if manifest['model_version']!=service.model_version:raise ValueError('Model version changed')
                import numpy as np
                with service.model_lock:
                    vector=np.asarray(service.encoder([runtime.semantic_query(plan) if runtime else plan.semantic_text]),dtype=np.float32)
                    if vector.shape!=(1,384) or not np.isfinite(vector).all() or np.linalg.norm(vector)<1e-8:raise ValueError('Invalid query vector')
                    vector/=np.linalg.norm(vector,axis=1,keepdims=True)
                    constrained=bool(plan.subjects or plan.author_text or plan.rating_min is not None or plan.rating_max is not None or plan.year_min is not None or plan.year_max is not None or plan.formats or plan.availability or plan.language or plan.exclude_terms or plan.exclude_subjects)
                    values,labels=index.search(vector,min(1000 if constrained else artifacts.PARAMETERS['candidate_count'],len(records)))
                candidates=[(records[int(label)]['library_book_id'],float(value)) for label,value in zip(labels[0],values[0]) if 0<=label<len(records)]
                if plan.kg_expansion_used:
                    with service.model_lock:
                        vector=np.asarray(service.encoder([expansion_query(plan)]),dtype=np.float32)
                        if vector.shape!=(1,384) or not np.isfinite(vector).all() or np.linalg.norm(vector)<1e-8:raise ValueError('Invalid expansion vector')
                        vector/=np.linalg.norm(vector,axis=1,keepdims=True)
                        extra_values,extra_labels=index.search(vector,min(60,len(records)))
                    primary_ids={i for i,_ in candidates}
                    extra=[(records[int(label)]['library_book_id'],float(value)) for label,value in zip(extra_labels[0],extra_values[0]) if 0<=label<len(records) and records[int(label)]['library_book_id'] not in primary_ids]
                    candidates.extend(extra);extra_ids={i for i,_ in extra}
                ids=[i for i,_ in candidates];scores=dict(candidates);generation=status['active_generation_id']
                hnsw=True;provider='TENANT_SEMANTIC'
            except (HTTPException,OSError,ValueError):fallback=True
        else:fallback=True
        if fallback:provider='LOCAL_FALLBACK'
    with catalogue.read_context(library_id,actor,staff=staff) as (library,membership,canonical):
        if hnsw and store.fingerprint(store.source_records(library_id))!=manifest['source_fingerprint']:
            hnsw=False;fallback=True;ids=None;provider='LOCAL_FALLBACK'
        if not hnsw:plan.kg_expansion_used=False;plan.expanded_subjects=[];plan.kg_generation=None
        pipeline=catalogue.usable(library_id,staff=staff)
        if ids is not None:pipeline.append({'$match':{'library_book_id':{'$in':ids}}})
        if plan.subjects:pipeline.append({'$match':{'subjects':{'$all':plan.subjects}}})
        if runtime is not None:
            pipeline.extend(runtime.pushdown(plan))
            raw=runtime.collect(store.collection('library_books'),pipeline)
        else:raw=list(store.collection('library_books').aggregate([*pipeline,{'$limit':STRUCTURED_LIMIT}]))
        rows=catalogue.hydrate(library_id,actor,raw,canonical,staff=staff)
        rows=[row for row in rows if (runtime.matches if runtime else matches)(plan,row) and (not filters or not filters.get('circulation_status') or row.get('circulation_status')==filters['circulation_status'])]
        if fallback and plan.semantic_text:
            terms=normalize(plan.semantic_text).split()
            rows=[row for row in rows if all(term in normalize(' '.join([row.get('title',''), ' '.join(row.get('authors',[])), ' '.join(row.get('subjects',[])),row.get('description') or ''])) for term in terms)]
        if hnsw:
            rows.sort(key=lambda row:-scores.get(row['library_book_id'],-1))
            depth=artifacts.PARAMETERS['reranking_count'];extra=[r for r in rows if r['library_book_id'] in extra_ids];reserve=min(depth//5,len(extra))
            rows=[r for r in rows if r['library_book_id'] not in extra_ids][:depth-reserve]+extra[:reserve]
            if service.reranker and rows:
                with service.model_lock:ranked=service.reranker([[plan.ranking_query(),artifacts.embedding_text(r)] for r in rows])
                if len(ranked)!=len(rows) or not np.isfinite(ranked).all():raise HTTPException(503,'Library ranking is temporarily unavailable.')
                rows=[dict(row,_search_relevance=float(score)) for score,row in sorted(zip(ranked,rows),key=lambda pair:-float(pair[0]))];reranked=True
            if plan.kg_expansion_used:rows.sort(key=lambda row:not primary_match(plan,row))
        rows=sort_books(rows,plan)
        profile,profile_diagnostics=personalization.safe_profile(actor,store.books_collection,library_id=library_id,staff=staff,canonical=canonical) if personalized else (None,{'cache':'OFF','elapsed_ms':0})
        rows,ranking_diagnostics=personalization.rerank(rows,plan,profile,personalized)
        source.update(search_source='TENANT_SEMANTIC' if hnsw else 'LOCAL_FALLBACK' if fallback else 'STRUCTURED_METADATA',intelligence_status=status['status'])
        # A scoped Search never falls through to the global candidate universe,
        # including a public library whose collection is currently empty.
        source['catalogue_source']='LIBRARY_LOCAL'
        source['capabilities'].update(local_search=True,global_discovery=False)
        response={'source':source,'results':rows[offset:offset+limit],'total':len(rows),'offset':offset,'limit':limit,'has_more':offset+limit<len(rows),
                  'interpretation':{**interpretation(plan),'session':session,'personalized':personalized,'clarification':interaction},'timing_ms':{'total':round((perf_counter()-start)*1000,2)}}
        if diagnostics:response['diagnostics']={'plan':asdict(plan),'provider':provider,'hnsw_used':hnsw,'kg_used':plan.kg_expansion_used and hnsw,'kg':expansion,'reranker_used':reranked,'fallback_used':fallback,'candidate_count':len(raw),'generation':generation,'strict_filters':True,'final_count':len(response['results']),'expansion_added_candidates':len(extra_ids)}
        if diagnostics:response['diagnostics'].update(personalization=ranking_diagnostics,profile=profile_diagnostics)
        return response
