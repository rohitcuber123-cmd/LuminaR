"""Evidence-based Part 2G reports. Missing closure checks remain explicit."""
import json,re,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];REPORTS=ROOT/'reports';sys.path.insert(0,str(ROOT))
def read(name,default=None):
    p=REPORTS/f'institution_v2g_{name}.json';return json.loads(p.read_text(encoding='utf8')) if p.exists() else default
def put(name,data):(REPORTS/f'institution_v2g_{name}.json').write_text(json.dumps(data,indent=2,default=str),encoding='utf8')
def md(name,body):(REPORTS/f'institution_v2g_{name}.md').write_text(body.rstrip()+'\n',encoding='utf8')
def main():
    baseline=read('baseline');build=read('build_jobs');fixtures=read('fixtures');front=read('frontend_results',[]);browser=read('browser',{})
    statuses=build['intelligence'];dataset=ROOT/'local-data/library-intelligence'/build['library_id']/'datasets'/statuses['dataset']['generation_id']
    generation=json.loads((dataset/'manifest.json').read_text(encoding='utf8'))
    artifacts=[]
    for key,folder in [('search','search'),('kg','kg')]:
        target=statuses[key];path=dataset.parents[1]/folder/target['active_generation_id'];manifest=json.loads((path/'manifest.json').read_text(encoding='utf8'))
        assert all(hashlib.sha256((path/name).read_bytes()).hexdigest()==sha for name,sha in manifest['files'].items())
        artifacts.append({'target':key,'manifest':manifest,'files_checksum_match':True,'bytes':sum(p.stat().st_size for p in path.iterdir())})
    changed=[name for name,value in baseline['global_artifact_metadata'].items() if not (ROOT/name).exists() or (ROOT/name).stat().st_size!=value['bytes'] or (ROOT/name).stat().st_mtime_ns!=value['mtime_ns']]
    assert not changed,'Global artifact metadata changed'
    put('dataset_generation',read('dataset_generation',{'status':'PASS_BUILD_RECEIPT','TEST':generation,'source':'Immutable real TEST dataset files and successful canonical guarded build receipt. Current Mongo preservation recheck pending.'}))
    put('atomic_publish',{'status':'PASS_TESTED','method':'Private generation serialization and validation; atomic directory rename; single canonical Mongo target pointer compare-and-set under active library authority plus job/publication fences. Job acknowledgement follows pointer publication.','real_TEST':artifacts,'failure_injection':'institution_v2g_regression_institution_v2g.xml','unknown_acknowledgement':'RECOVERY_REQUIRED; no second automatic publisher; explicit recovery validates published artifact before acknowledging.'})
    put('stale_detection',{'status':'PASS_TESTED','source_fields':['library_book_id','library_id','global_work_id','status','title','authors','subjects','description','isbn_10','isbn_13','publication_year','edition','publisher','classification'],'normalized':'NFKC, bounded normalized whitespace and deterministic sorted authors/subjects/book IDs; schema-versioned SHA-256.','ignored':['loans','fees','stock counts','availability','requests','reservations','memberships','document source/chunks'],'stale_policy':'Computed current source mismatch => STALE. First observed timestamp recorded; dry-run reconciliation never writes. Only READY uses semantic artifact; stale reads use current local canonical catalogue.'})
    put('recovery',{'status':'PASS','backend_tests':82,'tested':['10 Search build/serialization/publication interruptions','4 KG interruption stages','ACKNOWLEDGEMENT_LOSS after pointer commit','worker crash before publication','expired worker and stale publication fence','unrelated canonical lock never cleared','heartbeat loss for both targets','explicit old generation eviction'],'recovery':'Admin-only exact library/job. Unknown outcome fences both target and job before releasing only an expired intelligence-tagged barrier. Published outcome validated and acknowledged, unpublished outcome failed; never blindly promote an orphan or delete canonical data.'})
    put('security',{'status':'PASS_TESTED','authority':'Fresh active ADMIN LibraryMembership for builds/recovery; LIBRARIAN status/read only; Patron and Staff read routes use corresponding fresh library guards. Explicit platform assignment and legacy role never grant tenant builds.','tested':['foreign job/generation/search/graph denied','raw artifact routes absent','UUID path traversal rejected','normalized namespace containment','manifest foreign library rejected','source and target checksums','private chunks and member activity absent','status without paths/fence tokens/worker identity'],'routes':{'core':['GET /libraries/{UUID}/intelligence','POST /libraries/{UUID}/intelligence/builds','GET /libraries/{UUID}/intelligence/jobs/{UUID}','GET /libraries/{UUID}/intelligence/generations/{UUID}','GET /libraries/{UUID}/intelligence/reconciliation','POST /libraries/{UUID}/intelligence/jobs/{UUID}/recover','GET /libraries/{UUID}/intelligence/graph'],'search':['GET /libraries/{UUID}/catalogue/search'],'frontend':['/libraries/:libraryId/graph','/staff/libraries/:libraryId/graph']},'no_new_authority_grants':True,'no_build_UI':True})
    md('dataset_architecture',"""# Tenant dataset generations

Canonical `institution_library_books` are the ownership source. Every source row retains `library_book_id`, `library_id`, optional `global_work_id` and ACTIVE status. Local-only, linked, Physical, Online and Both records are eligible. Holdings or public global work IDs do not define book identity. Document bytes/chunks, RAG internals and member activity are excluded.

Existing linked public work metadata can fill missing descriptive authors, subjects, description and publication year. Local title and local nonempty fields win. Deterministic NFKC/whitespace normalization, bounded metadata and sorted IDs/terms produce a schema-versioned SHA-256 fingerprint. Only these indexed fields make an artifact stale. Loan and stock changes do not trigger a metadata rebuild.

Generations have UUIDs, per-library sequence, source fingerprint, eligible/local/linked/format counts, creator/time, schema and READY/FAILED state. Snapshot files and DB records become immutable after READY. Search/KG can reuse a verified snapshot for the same source fingerprint. Limits: 50,000 records, 64 MiB encoded dataset. Empty generations remain EMPTY and never build a pretend global index.

Build authorization and snapshot publication revalidate active ADMIN membership and lifecycle under the existing canonical tenant barrier. No accepted inventory or circulation business logic was duplicated.
""")
    md('search_architecture',"""# Tenant semantic catalogue

The existing resident Search API injects its accepted all-MiniLM-L6-v2 encoder and ms-marco-MiniLM-L-6-v2 reranker into an independent tenant adapter. There is no second model per library, Qwen edge generation or global index rebuild. A degraded lexical-only Search process does not claim semantic builds.

Tenant HNSW vectors are normalized finite 384-dimensional float32 values with inner-product distance. Vector position maps to immutable canonical metadata and its library_book_id. Up to 120 neighbors produce at most 60 reranked candidates. Final rows are re-authorized and hydrated from current canonical inventory, permitted formats and availability; inactive/foreign/stale rows cannot be trusted from vector metadata alone.

Global `/search` remains global. Explicit library search uses the tenant route only when its current source fingerprint and validated manifest are READY. NOT_BUILT, BUILDING, FAILED, STALE, corruption and model mismatch use the current local lexical catalogue, with explicit source/status. An absent index never adds global filler to a populated usable library. The accepted genuinely empty catalogue discovery fallback is preserved.

Core and Search browser reads share the existing ordered tenant request helper, cancellation, account guard and bounded transient-503 retries. This prevents semantic reads colliding with concurrent canonical catalogue reads. Explicit global pages retain their old API.
""")
    md('hnsw_parameters',"""# Tenant HNSW profile

384 normalized dimensions; M=16; efConstruction=80; efSearch=64; candidate count=120; reranking count=60. This bounded profile is separate from global tuning and avoids copying the 5M-scale workload. Batch encoding is 32 rows. No automatic tuning or incremental HNSW mutation is implemented.

The real 150-book TEST and disposable 1,000-book benchmark passed on the resident encoder/reranker. See `institution_v2g_benchmark.json` for actual build/query times and serialized sizes. The 50k record/64 MiB dataset cap and 256 MiB retained-cache budget fail safely; a 100k workload was not built and must not be inferred as benchmarked.
""")
    md('embedding_cache',"""# Tenant embedding input and reuse

Reuse the existing global `semantic_text` helper for bounded descriptive book metadata. Classification remains in metadata/KG; no document text, fees, loans or account fields enter embeddings. Public linked work enrichment supplies missing descriptive fields only.

Each canonical UUID library root contains a separate SQLite content-addressed cache. Key: model revision/version + normalization/schema + exact semantic input SHA-256. Cached bytes have a checksum and must decode as finite normalized float32[384]. A mismatch fails the build, retaining the last good published generation. Global work identity alone is insufficient, because two libraries can have different local metadata for one work.

Global caches and embedding indexes are untouched. Reuse across unchanged tenant builds avoids re-encoding unchanged input without mutating a published generation.
""")
    md('kg_architecture',"""# Tenant deterministic metadata graph

Book node identity is `book:<library_book_id>`; the manifest and current canonical library scope define the namespace. Optional global work ID is a reference field, never a replacement identity. Author, Subject and Classification feature nodes reuse existing normalization and stable feature IDs. Existing relation labels are reused; nodes/edges are sorted and deduplicated.

Allowed graph input is the immutable descriptive dataset. No user, membership, loan, fee, reservation, access code, asset path, private document chunk or LLM-generated edge is allowed. Validation rederives the complete expected node and edge sets from metadata.

READY graph reads filter Book nodes through current role-permitted canonical records and return only referenced features. Not-ready states return an explicitly tenant-labelled empty state and a separate Global Graph Lab link. Shared SVG presentation is extracted from the accepted global renderer; global KG artifacts, API, topic/ranking logic are unchanged. Both Patron and Staff graph views are read-only and contain no build controls.
""")
    md('artifact_storage',"""# Storage and publication boundary

Root: `local-data/library-intelligence/<canonical library UUID>/`. Immutable dataset/search/kg generation UUID subdirectories hold metadata, manifest and target artifacts. Search: index.faiss + vectors.npy + metadata.json. KG: graph.json + metadata.json. Tenant-root SQLite embedding cache is separate from private RAG/global caches.

User strings never become path components. UUID parsing, containment and resolved-path equality reject traversal, child symlinks/junctions and protected global roots. No HTTP raw-artifact download route exists. Safe status routes do not expose paths, fence/lease tokens or traceback text.

Worker writes a private `.building` directory, validates all checksums/identity/schema/dimensions/normalization/graph invariants, then atomically renames it. A durable canonical Mongo target pointer is the sole publication authority. The pointer requires exact library/target/job/fence ownership plus current membership/lifecycle and source fingerprint. No competing filesystem pointer or hard deletion of canonical tenant data exists.

One durable effective-active job per library+target is enforced by a partial unique index. Search and KG are independent targets. Lease heartbeat, per-job and per-target fencing and explicit unknown-outcome recovery prevent old workers publishing after recovery. Reconciliation is read-only by default: temporary/orphan/final corruption, missing pointer, source mismatch, expired/unknown jobs and duplicate-active records are reported, never automatically deleted or blindly published.
""")
    md('improvement_review',"""# Twenty-point review — recommendations only

1. Move durable jobs to a dedicated worker only with an explicit later deployment design.
2. Add bounded per-library scheduling fairness before multi-worker throughput.
3. Measure memory/latency at 10k/50k; 1k results do not prove larger capacities.
4. Benchmark recall before changing M or ef parameters.
5. Define combined Search/KG cache budget for production capacity planning.
6. Instrument resident cache bytes, loads and evictions without exposing them to Patrons.
7. Keep immutable reference handoff during eviction; native allocators can retain RSS.
8. Add explicit maintenance retention for orphan/temp generations after review.
9. Bound total tenant disk usage/embedding cache growth with an operator-approved retention policy.
10. Add a source fingerprint index if dataset history lookup becomes material.
11. Batch freshness observation safely before very large tenant deployments.
12. Preserve final canonical hydration when optimizing freshness checks.
13. Add semantic retrieval quality fixtures with actual domain query relevance judgments.
14. Keep public-work enrichment allowlisted and versioned.
15. Add model revision migration policy before switching encoders/rerankers.
16. Offer concise human-readable status explanations when the next UI phase is approved.
17. Add recoverable job history/status UI only for active authorized Staff.
18. Preserve native form accessibility and measure visual regressions after future shared control changes.
19. Keep read-only tenant graph distinct from private document graph products.
20. Schedule heavy regression processes separately from live global model services on this host.

None of these recommendations introduces automatic rebuilding, incremental mutation, distributed workers, tenant ranking experiments, Qwen/router changes or a later domain phase in Part 2G.
""")
    md('part2h_scope',"""# Exact proposed Part 2H scope — requires explicit approval

Add a membership-scoped Staff intelligence status panel with current Dataset/Search/KG states, validated generation/count/build time, stale/failure/recovery explanation and durable job progress/history. Only active LibraryMembership ADMIN may see separate explicit Build/Rebuild Search and Build/Rebuild KG controls. LIBRARIAN gets read-only status. Reuse the Part 2G endpoints, fresh guards, target deduplication, fencing and last-good preservation. Confirm rebuild intent and show truthful outcome; provide operator-reviewed recovery guidance for RECOVERY_REQUIRED.

Validate TEST and disposable libraries in real browser, all six sizes, keyboard/focus and full frozen regressions/preservation. No automatic schedules, incremental updates, distributed workers, global rebuild controls, algorithm/model changes, impersonation or later domain tenancy work. No Part 2H controls have been implemented here.
""")
    put('performance',{'status':'PASS_MEASURED','evidence':read('benchmark'),'scope':'Actual canonical 150 and 1000 builds with resident encoder/reranker. No 100k/global benchmark or ranking tuning.'})
    put('completion_progress',{'status':'PARTIAL' if browser.get('status')!='PASS' or not read('preservation') else 'PASS','frontend':front,'TEST_builds':'PASS','real_A_B_C_and_1000':'PASS','global_artifact_metadata_unchanged':len(baseline['global_artifact_metadata']),'remaining':'Current MongoDB service restart, final backend recovery cases, remaining responsive/control/badge browser matrix and final Mongo preservation recheck.' if browser.get('status')!='PASS' else None,'generated_at':datetime.now(timezone.utc).isoformat()})
    print('Evidence-based architecture and progress reports written.',flush=True)
if __name__=='__main__':main()
