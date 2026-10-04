"""Stable fifty-result search pool; facts/availability are hydrated per request."""
import os
from time import perf_counter
from backend.services.ranked_result_cache import RankedResultCache
from search.catalogue import current_books

SEARCH_MAX_RETURN_RESULTS = 50
SEARCH_RANKED_POOL_SIZE = 50  # Existing measured CrossEncoder depth.
SEARCH_DISPLAY_PAGE_SIZE = 10

class RankedSearchPages:
    def __init__(self, engine, cache=None):
        self.engine = engine
        self.cache = cache or RankedResultCache()
    def generation(self):
        snapshot = self.engine.index_manager.snapshot
        manifest = getattr(snapshot, "manifest", {})
        lexical = None
        if os.getenv('LEXICAL_SEARCH_ENABLED','false').lower() == 'true':
            store = getattr(self.engine, 'lexical_store', None)
            try:
                health = store.health() if store else {}
            except Exception as error:
                health = {'lexical_available': False, 'lexical_version': type(error).__name__}
            lexical = (health.get('lexical_available', False), health.get('lexical_version'),
                       health.get('lexical_generation'), health.get('lexical_delta_generation'))
        return (manifest.get('version'),manifest.get('semantic_generation'),lexical)
    def search(self, query, limit=10, offset=0, library_id=None, available_at_library=False, _attempt=0):
        if not 1 <= limit <= SEARCH_MAX_RETURN_RESULTS or not 0 <= offset <= SEARCH_RANKED_POOL_SIZE or offset+limit > SEARCH_RANKED_POOL_SIZE:
            raise ValueError('limit must be 1–50 and offset + limit must not exceed 50.')
        if available_at_library and not library_id:
            raise ValueError('library_id is required for availability filtering.')
        query = query.strip()
        if not query: raise ValueError('Query cannot be empty.')
        start = perf_counter()
        generation = self.generation()
        key = (query, library_id, available_at_library, generation)
        def rank():
            result = self.engine.search(query=query, top_k=SEARCH_RANKED_POOL_SIZE,
                                        library_id=library_id, available_at_library=False, diagnostics=True)
            diagnostic = result.get('diagnostics', {})
            return {'ranked': [{k:row[k] for k in ('work_id','rerank_score','hnsw_score')} for row in result['results']],
                    'timing_ms':result['timing_ms'],
                    'candidate_count':len(diagnostic.get('raw_hnsw',[])),
                    'reranked_count':len(diagnostic.get('reranked',[]))}
        pool, hit = self.cache.get_or_create(key, rank)
        # A publication during ranking must not label old-generation results current.
        if self.generation() != generation:
            if _attempt >= 2: raise RuntimeError("Catalogue changed repeatedly during ranking; retry.")
            return self.search(query, limit, offset, library_id, available_at_library, _attempt+1)
        hydrate_start = perf_counter()
        ids = [row['work_id'] for row in pool['ranked']]
        metadata = current_books(self.engine.books_collection, ids)
        inventory = self.engine._get_library_inventory(ids, library_id)
        rows = []
        for rank_row in pool['ranked']:
            wid=rank_row['work_id']; book=metadata.get(wid)
            if book is None: continue
            inv=inventory.get(wid)
            available=book.get('available_copies',0)
            if available_at_library and (not inv or available <= 0): continue
            rows.append(dict(rank_row, title=book.get('title'),authors=book.get('authors'),subjects=book.get('subjects'),
                description=book.get('description'),rating=book.get('average_rating'),rating_count=book.get('rating_count'),
                read_logs=book.get('reading_log_count'),library_id=library_id,library_available=inv is not None,
                physical_copies=book.get('total_copies',0),available_physical_copies=available,
                shelf_location=book.get('shelf_location'),isbn=inv.get('isbn') if inv else None))
        page = rows[offset:offset+limit]
        for i,row in enumerate(page,offset+1):row['rank']=i
        more=len(rows)>offset+limit
        hydration_ms=(perf_counter()-hydrate_start)*1000
        timing={name:(0 if hit else value) for name,value in pool['timing_ms'].items()}
        timing.update(page_hydration=round(hydration_ms,2),total=round((perf_counter()-start)*1000,2))
        return {'system':'LuminaR','query':query,'library_id':library_id,'available_at_library':available_at_library,
                'offset':offset,'limit':limit,'returned':len(page),'has_more':more,'next_offset':offset+len(page) if more else None,
                'total_ranked_candidates':len(rows),'results':page,'timing_ms':timing,
                'ranking':{'candidate_count':pool['candidate_count'],'reranked_count':pool['reranked_count'],'cache_hit':hit,
                           'index_generation':generation[1],'pool_limit':SEARCH_RANKED_POOL_SIZE}}
