"""Freeze existing recommendation order, hydrate current catalogue facts per page."""
import json
from time import perf_counter
from backend.services.ranked_result_cache import RankedResultCache
from backend.database.mongodb import books_collection,issues_collection,reservations_collection
from search.catalogue import current_books
from search.sync_queue import index_root
RECOMMENDATION_RANKED_POOL_SIZE = 50
RECOMMENDATION_MAX_PAGE_SIZE = 50

def generation():
    path=index_root()/'active_index.json'
    try: return json.loads(path.read_text(encoding='utf-8')).get('version')
    except (OSError,ValueError): return None

def exclusions(user_id):
    issued=issues_collection.find({'user_id':user_id,'status':'ISSUED'},{'work_id':1})
    reserved=reservations_collection.find({'user_id':user_id,'status':{'$in':['ACTIVE','READY_FOR_PICKUP']}},{'work_id':1})
    return {row['work_id'] for rows in (issued,reserved) for row in rows if row.get('work_id')}

class RankedRecommendationPages:
    def __init__(self, compute, cache=None, hydrate=None, exclude=None, version=generation):
        self.compute=compute;self.cache=cache or RankedResultCache()
        self.hydrate=hydrate or (lambda ids:current_books(books_collection,ids))
        self.exclude=exclude or exclusions;self.version=version
    def page(self,user,authorization,limit=10,offset=0,seed_work_id=None,strict_service_errors=False):
        if not 1<=limit<=RECOMMENDATION_MAX_PAGE_SIZE or not 0<=offset<=50 or offset+limit>50:
            raise ValueError('limit must be 1–50 and offset + limit must not exceed 50.')
        started=perf_counter();uid=int(user['sub'])
        key=(uid,user.get('sid','legacy'),seed_work_id,self.version())
        def rank():
            rows=self.compute(uid,authorization,limit=RECOMMENDATION_RANKED_POOL_SIZE,seed_work_id=seed_work_id,
                              strict_service_errors=True)
            # Cache only identities/scores: no availability, catalogue facts or token.
            return [{k:row[k] for k in ('work_id','score','score_breakdown')} for row in rows]
        ranking,hit=self.cache.get_or_create(key,rank)
        metadata=self.hydrate([row['work_id'] for row in ranking]);blocked=self.exclude(uid)
        if seed_work_id:blocked=blocked|{seed_work_id}
        rows=[]
        for row in ranking:
            book=metadata.get(row['work_id'])
            if not book or row['work_id'] in blocked:continue
            rows.append(dict(row,**{k:book.get(k) for k in ('book_id','title','authors','subjects','shelf_location')},
                        average_rating=book.get('average_rating',0),total_copies=book.get('total_copies',0),
                        available_copies=book.get('available_copies',0),library_available=True))
        page=rows[offset:offset+limit];more=len(rows)>offset+limit
        return {'user_id':uid,'count':len(page),'recommendations':page,'offset':offset,'limit':limit,
                'has_more':more,'next_offset':offset+len(page) if more else None,'total_ranked_candidates':len(rows),
                'recommendation_mode':'SINGLE_SELECTED_BOOK' if seed_work_id else 'PERSONALIZED_EXISTING_FORMULA',
                'seed_work_ids':[seed_work_id] if seed_work_id else [],
                **({'seed_work_id':seed_work_id} if seed_work_id else {}),
                'ranking':{'pool_limit':50,'cache_hit':hit},'timing_ms':{'total':round((perf_counter()-started)*1000,2)}}
