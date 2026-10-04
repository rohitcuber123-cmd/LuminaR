# Recommendation candidate depth and continuation

No Search50-to10 truncation was found. The existing CANDIDATE_COUNT=50 request already receives up to50 real catalogue candidates. Before the change, personalized API limit50 returned50 and single-seed limit50 returned49 after excluding the seed. ForYou asked for12 and the five-minute refresh recomputed that prefix; the missing behavior was offset continuation.

The new API always computes the existing recommendation formula over the existing50 candidate pool, retains its ordered IDs/scores for180 seconds, and slices by limit/offset. No weights, feedback behavior, scoring/diversity algorithm, profile logic, or RRF logic changed. recommendation_service.py is byte-identical to the pre-edit snapshot (SHA256 c8092770d930a79bd34db7e03dac2aeca6755b1143de2c46b71c93cfcf7dbc43).

GET /recommendations?limit=10&offset=10 and POST /recommendations/from-book with work_id/limit/offset return count, offset, limit, has_more, next_offset, total_ranked_candidates, recommendation_mode and seed_work_ids. Safe limit1–50, nonnegative offset and offset+limit<=50. User/session/seed/index-generation form the cache key. JWT authorization runs on every request; no token/facts are cached. Mongo metadata, current availability and active issue/reservation exclusions are rehydrated per request. Scores are a ranking snapshot; their availability component is not recomputed while paging.

Personalized and single-seed Top10 sequences are unchanged versus the original APIlimit10 outputs. Real HTTP paging visits offsets0,10,20,30,40 with0 overlaps; Previous restores the first slice. Final has_more is false. The personalized pool contains50, seeded pool49. Details and IDs/timings are in recommendation_pagination.json.

The existing assistant multi-seed RRF remains50 per seed with k60 and up to200 fused identities. Selected seeds, mode, filters and seen IDs remain in its server conversation context. Personalized SHOW_MORE now retains one request50 instead of recomputing increasing prefixes. Search and seeded SHOW_MORE already retained pools and are unchanged. Explicit SHOW_MORE uses no Qwen calls; tests cover seed preservation, no repeated IDs and fresh facts. No new multi-seed endpoint or fusion implementation was introduced.

Warm real HTTP timings: personalized uncached ranking85.31ms server/94.32ms wall, cached page2 3.63ms/11.96ms; seeded uncached166.09ms/195.64ms, cached page2 5.89ms/25.73ms. Baseline and after initial comparisons used different cache/startup conditions and are descriptive, not a controlled speedup claim.

Limits: a short profile or excluded/missing metadata can exhaust before50. Current exclusions/deletion can compact the pool between pages. Profile/feedback changes are reflected after TTL/new session; cache is process-local, so multiple workers can recompute. No KG or broad mode is involved.

Actual pipeline tracing (search_depth_live_assistant_trace.log/recommendation_pagination.json) verifies personalized50requested/50received, single-seed50/50, and each of two multi-seed calls50/50. After scoring/exclusions:50personalized,49perseed. Real HTTP AssistantTools with existing orchestrator verifies all three modes: same original seeds despite changed client tray, disjoint10-result pages, zero extra recommendation calls for SHOW_MORE and zero Qwen calls.
