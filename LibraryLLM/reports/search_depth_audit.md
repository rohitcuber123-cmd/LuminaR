# Search depth audit (before edits)

Frontend SearchPage -> searchBooks(query,12,LIB001,false,true) -> POST /search top_k=12 (schema default10; route maximum50) -> LuminaRSearchEngine.search -> normalized384D MiniLM -> one immutable HNSW snapshot -> fetch max(50,top_k*2), retry up to1000 after Mongo invalidation -> retain max(50,top_k) viable candidates -> CrossEncoder L6 on retained50 -> existing author-intent priority/optional lexical ranking -> fresh Mongo hydration + inventory -> availability filtering -> results[:min(top_k,50)]. FINAL_TOP_K=10 is unused. No active Search 10-result hard cap was found.

Recommendation get_recommendations -> build profile/seed query -> generate_semantic_candidates(CANDIDATE_COUNT=50) -> Search POST top_k50 -> receives up to50 -> active issue/reservation/seed exclusions -> existing weighted scoring -> score sort -> existing greedy diversity selection(limit) -> returned[:limit]. GET default10 maximum50; seeded POST default10 maximum50. ForYou requests12, auto-refresh recomputes that same first list. There is no recommendation pagination route.

Assistant searches once for50 IDs and pages its retained list. Personalized recommendation continuation requests progressively deeper prefixes (page+lookahead), while seeded recommendation requests50 per seed and retains existing RRF fusion up to200. Search model/index and recommendation weights must remain unchanged. Search frontend's assistant page context limit4 is selected context, not result depth. History limit50/100 and feedback limit50/200 do not limit Search ranking. Profile query limit10 limits interest text, not candidate count.

| File/function | Default | Maximum | Caller/meaning |
|---|---:|---:|---|
| SearchPage/searchBooks |12 /10|API50|UI output count, no continuation|
| SearchRequest/search route |10|50|API returned count|
| LuminaRSearchEngine.search |10|50|final returned count|
| HNSW fetch |50 minimum,2x requested|1000|semantic overfetch, Mongo validity headroom|
| viable rerank target |50 minimum|50 at supported API depth|CrossEncoder inputs|
| FINAL_TOP_K |10|unused|dead legacy constant|
| Recommendation CANDIDATE_COUNT |50|Search50|internal semantic candidate pool|
| Recommendation API GET/seed POST |10|50|final recommendation output|
| ForYou |12|12 requested|visible initial carousel, repeated refresh|
| Assistant Search |50|50|retained ranked IDs|
| Assistant personalized |page size+1|50|progressive prefix recomputation|
| Assistant seed fusion |50 per seed|200 fused|existing RRF pool|
