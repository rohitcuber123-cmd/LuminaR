import json, re, hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'reports'
BASE = json.loads((OUT / 'institution_v2e_baseline.json').read_text(encoding='utf8'))
GROUPS = []

def group(key, names, classification, file, anchor, source, authority, scope, bounds, semantics, decision):
    path = ROOT / file
    if not path.exists():
        raise ValueError('Missing evidence: ' + file)
    lines = path.read_text(encoding='utf8', errors='replace').splitlines()
    matches = [i + 1 for i, line in enumerate(lines) if anchor in line]
    if not matches:
        raise ValueError('Missing anchor: ' + file + ' ' + anchor)
    GROUPS.append(dict(id=key, metric_names=names.split('|'), classification=classification,
        evidence=dict(file=file, line=matches[0], anchor=anchor,
        absolute_path=str(path.resolve()).replace('\\', '/')),
        canonical_source=source, authority=authority, scope=scope, bounds=bounds,
        semantics=semantics, decision=decision))

P='PLATFORM_GLOBAL'; T='LIBRARY_TENANT'; U='PERSONAL_USER'; H='OPERATIONAL_HEALTH'; L='LEGACY_AMBIGUOUS'; X='UNKNOWN_REVIEW_REQUIRED'
PLATFORM='Fresh eligible identity and active explicitly approved PlatformRoleAssignment; legacy User.role or library membership is not authority.'
TENANT='Fresh eligible account and exact ACTIVE LibraryMembership; ACTIVE library and readable recovery gate.'
STAFF=TENANT+' ADMIN or LIBRARIAN.'
PATRON=TENANT+' GENERAL_USER for personal workspace.'

group('platform_summary','Accounts|Catalogue records|Active platform assignments|Global events',P,
 'backend/routes/notifications.py','def summary():','users; books; platform_role_assignments; events',PLATFORM,
 'Installation. Events scope_match(): library_id null plus GLOBAL or missing scope legacy.',
 'Scalar counts; books estimated_document_count.',
 'Accounts include inactive identities. Global event count includes global lifecycle states. Raw ACTIVE assignment count is not tenant staff count.',
 'Retain Platform Overview; never use as tenant totals.')
group('platform_directory','Library directory total',P,'backend/services/platform_library_service.py','def directory(',
 'institution_libraries',PLATFORM,'Optional lifecycle,type,name,slug,owner filters.',
 'Page<=50,offset<=1M,maxTimeMS=10000.',
 'Exact server-side facet total; safe owner identity lookup. No tenant business aggregates.', 'Retain Platform Libraries.')
group('platform_library_safe','Active patron members|Active staff|Active local books',T,
 'backend/services/platform_library_service.py','def safe_summary(',
 'institution_memberships; institution_library_books',PLATFORM,
 'Exact library_id and status ACTIVE; patrons GENERAL_USER; staff ADMIN/LIBRARIAN.',
 'Three indexed counts per directory row; page<=50.',
 'Previously approved safe Platform library metadata exception; no loan/fee/member-interest detail.',
 'Retain approved directory/detail counts; does not permit Staff Analytics.')
group('platform_audit','Committed lifecycle audit total',P,'backend/services/platform_library_service.py','def audit_rows(',
 'platform_audit',PLATFORM,'Exact library_id and state COMMITTED.','Page<=50; scalar count.',
 'Platform lifecycle transitions, not tenant business performance.','Retain audited lifecycle history.')
group('platform_accounts','Account directory total',P,'backend/services/platform_account_service.py','def directory(',
 'users',PLATFORM,'Optional identity search.','Page<=100.','Counts accounts; never implies any authority.','Retain account administration.')
group('platform_recipients','Eligible recipient directory total',P,'backend/services/notification_service.py','def directory(',
 'users',PLATFORM,'is_active!=false,is_email_verified=true,email query.','Page<=50.',
 'Verified global notification recipients, not tenant members.','Retain platform send picker.')
group('authority_review','Legacy ADMIN/LIBRARIAN review total|Active memberships per reviewed legacy identity',X,
 'backend/routes/platform.py','def migration_review(', 'users.role; institution_memberships',PLATFORM,
 'Legacy role filter and exact account lookup.','Page<=100.',
 'Rows remain UNKNOWN_REVIEW_REQUIRED. No role grants or tenant ownership inferred.','Keep explicit operator review only.')
group('discovery','Filtered active library total',P,'backend/services/institution_service.py','def discover(',
 'institution_libraries; institution_memberships','Authenticated account',
 'Libraries ACTIVE; mine also actor user_id and ACTIVE membership.','Page<=100;offset<=100000.',
 'Directory pagination count; no private business metrics.','Retain Explore/My Libraries.')
group('membership_operations','Filtered membership total|Last-active-ADMIN invariant',T,
 'backend/services/institution_service.py','def list_staff(','institution_memberships',TENANT+' ADMIN for management.',
 'Exact library UUID; optional role/status/search.','Page<=100; server counts.',
 'Management total can include all statuses. Analytics role snapshot must explicitly ACTIVE. Last-admin count protects authority.',
 'Retain management; new Analytics derives role aggregates without identities.')
group('invitation_operations','Staff invitation total',T,'backend/services/institution_service.py','def list_invitations(',
 'institution_invitations',TENANT+' ADMIN.','Exact library UUID and status.','Page<=100.',
 'Invitation count is identity operation, not member activity.','Retain operation; exclude secrets/emails from Analytics.')
group('personal_invitations','Own pending invitation total',U,'backend/services/institution_service.py','def pending_invitations(',
 'institution_invitations','Current canonical identity','Actor email and pending status.','Bounded page.',
 'Pending invitation is not an active membership.','Retain personal invitations only.')
group('library_audit','Admin audit total|Staff operational activity total',T,'backend/services/institution_service.py','def audit_events(',
 'institution_audit',STAFF+' Full audit ADMIN only.','Exact library UUID; operational activity whitelist.',
 'Bounded page and count.', 'Canonical histories include actor/source IDs; Analytics aggregates without individual histories.',
 'Retain activity surface; trends use committed journal provenance.')
group('staff_overview','Inventory records|Pending borrow requests|Pending return requests|Current loans|Membership records',T,
 'frontend/src/components/LibraryShells.tsx','type Summary =',
 'Canonical inventory + staff Part2B requests/loans + V1 members','WorkspaceRoute staff and fresh guard on each API.',
 'Explicit current library UUID.','Bounded page totals; no all-record client aggregation.',
 'Existing Overview assembles API totals. Unavailable lending uses null/setup-required, not invented zero.',
 'Keep operational Overview; one new server Analytics response adds historical aggregates.')
group('inventory','Filtered record total|ACTIVE records|WITHDRAWN records|Holding total quantity|Available inventory snapshot|Known copies',T,
 'backend/services/library_catalogue_service.py','def list_books(',
 'institution_library_books;holdings;copies',TENANT,'TenantInventory enforces canonical UUID in every predicate.',
 'Page<=100; strict integer quantities<=1M.',
 'available_copies is old snapshot, not canonical requestable. Metadata link does not imply global corpus ownership.',
 'Canonical Analytics source; no duplicate stock arithmetic.')
group('inventory_import','Rows total|Valid rows|Invalid rows|Global matches|New local records|Existing holdings|Possible duplicates|Classification counts',T,
 'backend/services/library_inventory_import.py','def summary(',
 'Validated scoped import preview',STAFF,'Exact library UUID and actor.',
 'Existing upload/row bounds.', 'Global match is metadata classification, not book ownership in 5M corpus.',
 'Retain preview/receipt only; Analytics never runs import.')
group('catalogue_source','Usable active local books|Recommendation intersection count',T,
 'backend/services/library_catalogue_experience.py','def source_locked(',
 'ACTIVE titled library_books joined same-library holdings',TENANT,'Exact library UUID.',
 'Home rails12; recommendation candidate IDs<=200.',
 'Usable discovery count may differ from ACTIVE inventory if invalid/unheld metadata exists. Empty discovery GLOBAL_FALLBACK is explicitly non-owned.',
 'Preserve catalogue UX; Analytics zero local never filled globally.')
group('local_subjects','Local distinct subject total|Subject record counts',T,
 'backend/services/library_catalogue_experience.py','def subject_rows(',
 'Usable local books, setUnion subjects per record',PATRON,'Exact UUID; active metadata and holdings.',
 'Home24; genres page<=100. New Analytics top<=20.',
 'One book may contribute to multiple subjects; repeated tokens deduped per record.',
 'Reuse real local subject semantics.')
group('tenant_popular','Weighted popularity score|Popularity loan count|Popularity approved-request count|Popularity reservation count|Ranked-book total',T,
 'backend/services/library_catalogue_experience.py','def popular_rows(',
 'Part2B loans/requests + Part2C reservations + same-library usable books',PATRON,
 'Each match/union/join includes same library UUID.', 'Fixed90days; Home12;browse<=50.',
 'Weights8 loans ACTIVE/RETURNED borrowed_at;2 BORROW APPROVED/COMPLETED reviewed_at;1 reservations WAITING/CONVERTED/FULFILLED requested_at.',
 'Preserve canonical Home ranking. Staff selected-range book counts may reuse operation semantics; no member rankings.')
group('patron_summary','Own pending requests|Own active loans|Own waiting reservations',U,
 'backend/services/library_catalogue_experience.py','def summary(',
 'Canonical Part2B/C records',PATRON,'Exact library UUID plus actor user_id.',
 'Three indexed scalar counts.', 'Personal My Library snapshot, not whole-library totals.',
 'Retain patron Home; never use as staff aggregate source.')
group('allocation_counts','Pending holds per book|Active loans per book|Known copies per book|Unavailable copy conditions|Available identified copies',T,
 'backend/services/library_lending_service.py','def availability_locked(',
 'Same-library holding/copies/requests/loans',TENANT,'library_id+library_book_id.',
 'Indexed per-book counts; new analytics should group in batch.',
 'COPY mode validates known==total and available==derived allocation.',
 'Reuse canonical projection; avoid per-book N+1 in Analytics.')
group('availability_projection','Total physical units|Requestable units|Physical available units|Unavailable stock units|Pending holds|Active loans|Queue priority',T,
 'backend/services/library_catalogue_availability.py','def project(',
 'Canonical supplied scoped quantities and allocations',TENANT,'library_id+book_id+holding_id from canonical caller.',
 'Pure projection, O(1) per supplied aggregate; no writes.',
 'units=total-pending-active-(unavailable_stock+copy_conditions); requestable zero if not circulating/active or waiting queue.',
 'ONE shared availability formula; never use snapshot available_copies as truth.')
group('staff_circulation','BORROW pending badge|RETURN pending badge|Filtered request total|Filtered loan total',T,
 'backend/services/library_lending_service.py','badges =',
 'institution_lending_requests;loans',STAFF,'Exact UUID; kind,status,date filters.',
 'Page<=100; server totals.', 'Existing read helper may expire holds. Analytics must avoid access_locked()/expire_locked().',
 'Keep operations; aggregate directly for read-only Analytics.')
group('personal_circulation','Own request total|Own loan total|Loan renewal count|Remaining renewals',U,
 'backend/services/library_lending_service.py','def rows(', 'institution_lending_requests;loans',PATRON,
 'Exact UUID+actor user_id.', 'Bounded rows; existing renewal policy.',
 'Own operational facts, not member activity ranking.', 'Retain My Library.')
group('staff_reservations','Filtered reservation total|Queue position|Queue length',T,
 'backend/services/library_reservation_service.py','def rows(', 'institution_reservations',STAFF,
 'Exact UUID+book_id; waiting sequence.', 'Bounded operational page; queue indexed counts.',
 'CONVERTED means ready borrow-request stage; FULFILLED real issuance. Waiting count is per-book queue.',
 'Retain queue operations; Analytics safe state/book aggregate only.')
group('personal_reservations','Own reservation total|Own queue position|Own queue length',U,
 'backend/routes/library_reservations_fees.py','queue_position', 'institution_reservations',PATRON,
 'Exact UUID+actor and linked book queue.', 'Bounded rows.',
 'User sees own position; no individual rankings.', 'Retain patron Reservations.')
group('fees_operations','Filtered fee total|Original charge minor units|Current charge minor units|Paid minor units|Balance minor units|Estimated overdue days|Estimated overdue minor units',T,
 'backend/services/library_fee_service.py','def rows(', 'institution_fees;fee_ledger;fee_policy snapshots',STAFF,
 'Exact library UUID.', 'Page<=100; verify_ledger invariant per operational fee.',
 'Exact integer minor-unit CHARGE/CREDIT/WAIVER/PAYMENT_RECORD semantics. Immutable currency/unit factor. UTC_CALENDAR_DAY/grace/physical receipt cutoff.',
 'Analytics currency-separated aggregates only; never float or member names+balance.')
group('fees_personal','Own fee total|Own fee balance|Own active-loan overdue estimate',U,
 'backend/services/library_fee_service.py','if not staff:', 'Own canonical fees/loans',PATRON,
 'Exact UUID+actor user_id.', 'Bounded fee list; at most100 own active-loan estimates.',
 'Finalized fee balance and active-loan estimate are distinct.', 'Retain patron Fees only.')
group('global_events','Global event list count',P,'backend/services/event_service.py','def listing(', 'events',
 'Public listing; global management explicit platform grant.', 'library_id null + GLOBAL or missing-scope legacy.',
 'Page_size<=50;page<=20000;query<=120.', 'All filters maintain global scope; ambiguous non-null legacy tenant IDs excluded.',
 'Retain global Events; no tenant publication/attendance inclusion.')
group('tenant_events','Tenant event list count|Upcoming events|Past published events|Cancelled events',T,
 'backend/services/library_event_service.py','def listing(', 'events',STAFF+' Patron/member/PUBLIC listing has separate guard.',
 'scope LIBRARY + exact UUID.', 'Page_size<=50; Home preview3.',
 'Upcoming from actual schedule including undated published; past is derived schedule, no attendance. First published_at retained.',
 'Reuse Part2D fields; no RSVP/engagement invented.')
group('unseen_events','Own unseen global event count|Unseen capped flag',U,
 'backend/services/event_service.py','def unseen(', 'Global events and event_user_state',
 'Authenticated owner and signed seen receipt.', 'Exact user_id/sid; GLOBAL only.',
 '14days;500 receipts explicitly capped.', 'First access establishes baseline, not attendance.',
 'Keep bell; never member surveillance source.')
group('inbox','Account inbox total|Unresolved inbox total|Unread unresolved total',U,
 'backend/services/notification_service.py','def list_own(', 'notifications',
 'Fresh current account, own user_id; fresh membership on action.',
 'User-owned inbox across GLOBAL/PLATFORM/LIBRARY scopes intentionally.', 'Page<=50; user_id/read/resolved indexes.',
 'Unavailable historical action after role/lifecycle revocation; unread excludes resolved.',
 'Keep bell; Analytics cannot inspect recipient content.')
group('platform_sent','Sent platform notification count',P,'backend/services/notification_service.py','def sent(',
 'notifications source ADMIN',PLATFORM,'Platform send history; tenant materialization excluded.', 'Page<=50.',
 'ADMIN source historical compatibility is platform account notice provenance.', 'Retain platform Notifications.')
group('outbox_worker','Scanned intents|Delivered intents|Skipped/suppressed intents|Failed intents|Uncommitted intents|Retry attempts',H,
 'backend/services/tenant_notification_service.py','def materialize(',
 'notification_outbox with committed lending_operations', 'Core worker/local operator; tenant Analytics would be ADMIN only.',
 'Worker installation scope; Analytics must explicitly library-match.', 'Default100,max500; retry<=3600s; attempts<=10000.',
 'Last-scan values transient per-process, not lifetime totals. Durable PENDING/DELIVERED/SUPPRESSED + generic error codes.',
 'Safe operational aggregate only; exclude content, recipients, private source history.')
group('outbox_cli','Outbox state/error distribution',H,'scripts/notification_outbox_v2d.py','summary=list(',
 'institution_notification_outbox','Trusted local operator CLI.', 'Installation grouping by finite state/error; not a tenant web endpoint.',
 'Output groups bounded by finite states/errors; drain<=500 explicit flag.',
 'Inspect is read-only; --drain writes only when explicitly operator requested.',
 'Analytics must never invoke --drain.')
group('legacy_operations','Legacy filtered operation count',L,'backend/services/admin_operation_service.py','def operations(',
 'Legacy activity/issues/reservations/fines',PLATFORM,'No reliable canonical library attribution.',
 'Rows<=50; title/identity matching can scan legacy source.',
 'No institution_loans/reservations/fees query. Legacy amounts/identity are historical compatibility.',
 'Read-only history only; exclude from tenant Analytics and fleet business sums.')
group('legacy_user_snapshot','Legacy issued-loan count|Legacy active/ready reservation count|Legacy fine count|Legacy activity count|Non-library notice count',L,
 'backend/services/admin_operation_service.py','def user_activity(',
 'Legacy issues/reservations/fines/activity; non-LIBRARY notifications',PLATFORM,'user_id only, no canonical tenant UUID.',
 'Legacy record pages20 and counts.', 'Tenant inbox explicitly excluded. No new surveillance or tenant business metric.',
 'Retain accepted read-only historical display; do not reuse for Analytics.')
for key,file,anchor,names in [
 ('legacy_all_issues','backend/routes/issues.py','def all_issues(','Legacy issue total'),
 ('legacy_all_reservations','backend/routes/reservations.py','def all_reservations(','Legacy reservation total'),
 ('legacy_all_fines','backend/routes/fines.py','def all_fines(','Legacy fine count|Legacy unpaid fine amount'),
 ('legacy_all_activity','backend/routes/activity.py','def all_activity(','Legacy activity total')]:
    group(key,names,L,file,anchor,'Unattributed legacy collections',PLATFORM,
     'No canonical UUID attribution.', 'Some legacy reads unbounded Python list; exclude from new analytics.',
     'Historical global-role comments are stale; actual route uses require_platform_admin.',
     'Read-only compatibility; canonical writes are retired.')
for key,file,anchor,names in [
 ('legacy_own_issues','backend/routes/issues.py','def my_issues(','Own legacy issue count'),
 ('legacy_own_reservations','backend/routes/reservations.py','def my_reservations(','Own legacy reservation count'),
 ('legacy_own_fines','backend/routes/fines.py','def my_fines(','Own legacy fine count|Own legacy unpaid amount'),
 ('legacy_own_activity','backend/routes/activity.py','def my_activity(','Own legacy activity count')]:
    group(key,names,U,file,anchor,'Personal legacy history', 'get_current_user + actor user_id.',
     'No inferred library.', 'Some old personal history lists unbounded; no new Analytics reuse.',
     'Accepted historical account surface separate from current canonical library operations.',
     'Personal history only.')
group('legacy_inventory','Legacy inventory page count',L,'backend/routes/inventory.py','def list_inventory(',
 'library_inventory','Explicit legacy alias mapping + require_library_staff; unmapped retired410.',
 'Legacy alias, never first library guess.', 'Page<=100; count is returned length.',
 'Read-only legacy data; cannot mutate canonical inventory.', 'Compatibility only, excluded from tenant Analytics.')
group('legacy_availability','Global-display legacy available copies|Global-display legacy total copies',L,
 'backend/services/availability_service.py','def with_batch_availability(',
 'Legacy library_inventory keyed work_id or global books fallback','Public catalogue display.',
 'Global work identity, not canonical institution stock.', 'Bounded card batch.',
 'No canonical tenant attribution; global detail does not assert local ownership.',
 'Keep accepted global display only; no tenant availability analytics source.')
group('global_catalogue','Estimated global total|Filtered exact count or unavailable|Global category count|Average rating|Rating count|Reading-log count',P,
 'backend/services/book_service.py','def get_books(', 'books + prebuilt book_categories',
 'Public global discovery; global metadata mutation PlatformRoleAssignment.', 'Installation corpus.',
 'Page<=100;filtered count maxTimeMS1000;category top14.',
 'Imported global ratings/logs not local borrowing. Categories prebuilt by backend/scripts/build_book_categories.py; unavailable exact count is null.',
 'Preserve global5M/count/ranking; never scan for tenant Analytics.')
group('global_discovery_pages','Popular returned-book count|New-arrivals returned-book count',P,
 'backend/routes/books.py','def popular_books(', 'Global books metadata','Public global discovery.',
 'Global corpus.', 'Rails<=50.', 'Page length, not unique users or corpus total.', 'Keep global Home/catalogue.')
group('recommendation_profile','Feedback count|Subject interest frequency|Author interest frequency|Borrowed subject frequency|Borrowed author frequency|Reserved subject frequency|Reserved author frequency|Personal recommendation score',U,
 'recommendation/recommendation_service.py','def build_user_profile(',
 'Account search_history, legacy issues/reservations, feedbacks','JWT current account/user_id.',
 'Personal account only; global frozen algorithm.', 'Queries<=10;candidates50;existing ranked paging.',
 'Personal interests/algorithm weights are not tenant operational metrics.',
 'Frozen personal recommendation logic; no staff/platform access or ranking change.')
group('recommendation_feedback','Own feedback returned count',U,'recommendation/api.py','def get_feedback(',
 'recommendation_feedbacks','Token current account.', 'user_id.', 'Existing endpoint limit.',
 'Personal recommendations feedback only.', 'No Analytics private-interest export.')
group('search_history','Own saved-search returned count',U,'search/api.py','def search_history(',
 'search_history','JWT actor/user_id.', 'Personal account.', 'Existing bounded history limit.',
 'save_history at first result page; no new tracking.', 'Exclude search queries from Staff Analytics.')
group('reading_list','Own returned-item count',U,'backend/routes/reading_list.py','def my_reading_list(',
 'reading_list','Actor user_id; local target current patron guard.', 'Own items only.',
 'Existing personal surface, no staff aggregation.', 'Linked items converge global work; local-only target explicit UUID pair.',
 'Keep personal saved content entirely outside Analytics.')
group('kg_comparison','Subject pairwise distance|Subject pairs evaluated|Subject pairs missing|Unique authors|Unique subjects|Books with subjects|Result count|Intersection count|Union count|Overlap at k|Jaccard',H,
 'knowledge_graph/metrics.py','def diversity(', 'Bounded recommendation lists/public KG metadata',
 'Existing KG API auth; public metadata comparison.', 'List comparison; no tenant operations.',
 'Bounded result lists.', 'Metadata diversity/set coverage does not prove relevance.',
 'Frozen exploration diagnostics; not member reading interests or tenant usage.')
group('core_health','Core readiness status|Platform database ping',H,'backend/main.py','def health():',
 'Process readiness; platform route db.command ping','Existing core health; platform health guarded.',
 'Core/database operation.', 'Constant status/ping.', 'Core healthy flag alone not proof of all dependencies.', 'Keep operational health.')
group('search_health','Active HNSW vectors|Deleted vectors|Mapping count|Mutation count since rebuild|Index status|Lexical store health|Lexical worker availability|Lexical ranking enabled',H,
 'search/index_manager.py','def status(', 'Frozen Search manifest and sync state','Existing service health.',
 'Global index, not library collection.', 'Status metadata; no rebuild.',
 'Integrity/generation status not usage analytics.', 'Preserve HNSW and Search ranking.')
group('rag_health','Model loading milliseconds|RAG vectors|Private cache enabled',H,
 'rag/api.py','def health():', 'Loaded engine/index/model flags','Existing health.',
 'Process global.', 'Constant process values.', 'RAG vector count not library documents.', 'Keep operational health; no private content.')
group('personal_private_docs','Own active private documents|Document pages|Document chunks|OCR/warning metadata',U,
 'rag/services/private_document_routes.py','def documents(', 'Session-owned SQLite documents',
 'JWT owner+sid+expiry+revocation; service.owned.', 'No library ownership model exists.',
 'Existing MAX_BYTES,MAX_CHUNKS limits.', 'Private metadata belongs to owner/session.',
 'Exclude from Analytics; future tenancy requires separate design.')
group('private_doc_health','Upload counter|Parse calls|Chunk preparation calls|Embedding calls|Private FAISS builds|Ingest seconds total|Restore seconds total|Export seconds total',H,
 'rag/services/private_documents.py','self.metrics =', 'PrivateDocuments process counters',
 'Internal runtime/testing only.', 'Process-local aggregate operations.', 'Reset with process.',
 'No private source text; not durable tenant usage.', 'Preserve, no Staff Analytics exposure.')
group('private_cache_health','Cache exports|Cache restores|Cache failures|Encrypted bytes|Failures by code|Pipeline incompatibilities|Average encrypted bytes',H,
 'rag/services/local_document_cache.py','self.metrics =', 'LocalDocumentCache process counters',
 'Internal runtime/testing.', 'Personal device cache operations, not library.', 'Existing size bounds/finite error classes.',
 'Operational numeric signals only; no private text.', 'Preserve and exclude from Library Analytics.')
group('reconciliation','Holding integrity errors|Reservation integrity count|Fee integrity count|Unfinished journal count',H,
 'backend/services/library_v2c_integrity.py','def reconcile(', 'Canonical records/journal',
 'Offline operator; no new web role shortcut.', 'Explicit library UUID.',
 'Offline can traverse whole tenant; not web Analytics.', 'Recovery reports may list IDs for operator repair.',
 'Retain offline diagnostics; Analytics never repairs/mutates data.')

group('rag_request_timings','Stage milliseconds|Stage call counts|Input tokens|Generated tokens|Maximum generated tokens|Generation milliseconds|Tokens per second|Total request milliseconds|Outer request milliseconds|Inference queue milliseconds',H,
 'rag/telemetry.py','def record_generation(', 'Request-local ContextVar telemetry',
 'Existing RAG request access; metrics contain no prompt/document text.', 'Request-local; never shared member tracking.',
 'One bounded profile per request.', 'Process diagnostics; no tenant activity attribution.',
 'Frozen Assistant/RAG instrumentation; not new Analytics tracking.')
group('rag_evidence_diagnostics','Actor alignment|Event alignment|Local causal score|Speaker score|First-person narrative|Motivation strength|Consequence strength|Motivation priority|Directional subject alignment|Temporal phase alignment|Polarity alignment',H,
 'rag/evidence.py','metrics = {', 'Frozen evidence/ranking numeric diagnostic fields',
 'Existing RAG source authorization; internal/request diagnostics.', 'Selected source/request, not canonical tenant activity.',
 'Bounded retrieved evidence.', 'Diagnostic scores do not imply confidence,attendance or member interests.',
 'Preserve retrieval algorithms and exclude from Staff Analytics.')
group('private_knowledge_diagnostics','Source units|Sampled flag|Duplicate rejections|Boilerplate rejections|Fragment rejections|Unsupported rejections|Genericity rejections|Embedding calls|Embedding milliseconds|Complete fact families|Candidate count|Accepted concept count|Source pages used|Concept diversity|Qwen calls|Knowledge model milliseconds|Artifact generation milliseconds',U,
 'rag/services/document_knowledge.py','metrics.update({', 'Owner document knowledge/artifact result',
 'PrivateDocuments owner+sid checks; KnowledgeArtifacts active owner guard.',
 'Private uploaded source, no library attribution.', 'Bounded MAX_UNITS/concepts/chunks; per-document processing.',
 'KnowledgeArtifacts returns model metrics and generation cost to source owner; cannot become institutional education/member analytics.',
 'Keep personal Knowledge Tools; never expose in Staff/Platform Analytics.')
group('private_ocr_diagnostics','Native pages|OCR pages|OCR attempts|Failed pages|Blank pages|Peak raster bytes|OCR page limit|OCR DPI|Concurrent OCR pages',U,
 'rag/services/private_document_ocr.py',"stats={'native_pages'", 'Private document extraction metadata',
 'Owner/session ingest path; private source authorization.', 'Uploaded personal document.',
 'Page limit80;page timeout20s;pixel limit12M;one OCR page at once.',
 'Extraction diagnostics only, not library document usage.', 'Keep bounded private preparation, excluded from Analytics.')
group('offline_retrieval_evaluation','Accepted source span count|First relevant rank|MRR|Hit at depth|Recall at depth|Evaluated query count|Oracle candidate depth|Oracle hit at1|Oracle hit at3',H,
 'rag/evaluation/metrics.py','def evaluate_query(', 'Frozen labeled evaluation corpus and ranked result spans',
 'Offline evaluation/test utility, no product role.', 'Evaluation data only.',
 'Depths1,3,5,10,20,40,50; duplicate spans deduped.',
 'Model evaluation measures, not actual library lending/reading usage.',
 'Not executed for audit; Router research/model evaluation remains outside phase.')
group('offline_search_evaluation','Recall at10|Retrieval latency|Candidate totals',H,
 'search/evaluate_retrieval.py','def recall_at_k(', 'Offline retrieval test corpus and engine',
 'Local research/operator script.', 'Global frozen retrieval evaluation.', 'Script workload only, no product API.',
 'Evaluation quality/performance, never tenant activity.', 'Preserve and do not execute new research.')
group('offline_search_latency','Average milliseconds|Median milliseconds|P95 milliseconds|Minimum milliseconds|Maximum milliseconds|Embedding milliseconds|HNSW milliseconds|Candidate metadata milliseconds|Pair construction milliseconds|Reranking milliseconds|Final metadata milliseconds',H,
 'search/api_benchmark.py','times = []', 'Local fixed HTTP benchmark timing',
 'Operator benchmark script.', 'Legacy hard-coded8001 URL, not tenant endpoint.',
 '20iterations;5warmups.', 'Offline diagnostic; stale port evidence cannot prove live Part2E performance.',
 'Do not run as Analytics benchmark; Part2E must use real selected-library APIs.')
group('lexical_build_diagnostics','Representable book count|Lexical generation|Free disk bytes|Estimated final bytes|Temporary build bytes|Journal/sort allowance|Retained-version bytes|Safety margin|Minimum free bytes|Recommended free bytes|Available RAM bytes|Build RAM reserve bytes',H,
 'search/lexical_build.py','def preflight(', 'Offline lexical snapshot/preflight metadata',
 'Operator explicit build policy; no staff Analytics control.', 'Global search index, not tenant.',
 'Default100K source gate;full5.1M requires explicit flag.',
 'Resource planning stats not tenant catalogue/usage. Some full builds are deliberately expensive offline.',
 'Frozen no build/rebuild in Part2E.')

METRICS=[]
for item in GROUPS:
    for name in item['metric_names']:
        METRICS.append({**{k:v for k,v in item.items() if k not in ['metric_names','id']},
            'metric_id':item['id']+'.'+re.sub('[^a-z0-9]+','_',name.lower()).strip('_'),
            'metric':name,'family_id':item['id']})
SCAN=[]
pattern=re.compile(r'\b(?:analytics|statistics|stats|metrics|dashboard|popular|count_documents|estimated_document_count)\b|\.aggregate\(',re.I)
for directory in ['backend','frontend/src','frontend/tests','scripts','tests','search','recommendation','rag','knowledge_graph']:
    for path in (ROOT/directory).rglob('*'):
        rel=path.relative_to(ROOT).as_posix()
        if path.suffix not in {'.py','.ts','.tsx','.ps1'} or any(k in path.parts for k in ['__pycache__','node_modules']) or 'institution_v2e' in rel or rel not in BASE['source_sha256']:
            continue
        hits=[i+1 for i,line in enumerate(path.read_text(encoding='utf8',errors='replace').splitlines()) if pattern.search(line)]
        if hits:
            family='SUPPORTING_TEST_EVIDENCE' if rel.startswith(('tests/','frontend/tests/')) or path.name.startswith('test_') else 'OFFLINE_OPERATIONAL_REPORT_OR_BENCHMARK' if rel.startswith(('scripts/','backend/scripts/')) else 'PRODUCTION_SOURCE_REVIEWED'
            SCAN.append(dict(file=rel,matched_lines=hits,family=family,prechange_sha256=BASE['source_sha256'].get(rel)))
COUNTS=dict(Counter(item['classification'] for item in METRICS))
PAYLOAD=dict(phase='Institution Part2E',status='AUDITED_BASELINE',baseline_captured_at=BASE['captured_at'],
    audited_at=datetime.now(timezone.utc).isoformat(),metrics=METRICS,groups=GROUPS,
    classification_counts=COUNTS,source_scan=SCAN,
    coverage='Actual source fields/counts/projections/diagnostic families reviewed, with repeated frontend presentations sharing source entries. Offline script/test numeric outputs are operational evidence, not live member usage. Internal arithmetic and layout dimensions are not independent product metrics.',
    obsolete_surfaces=[dict(surface=name,classification='OBSOLETE',source='frontend/src/App.tsx',decision='Compatibility redirect only; no independent metric dashboard.') for name in ['Admin dashboard','Librarian dashboard','Staff dashboard']],
    unknowns=['Historical ADMIN/LIBRARIAN identities remain UNKNOWN_REVIEW_REQUIRED; no automatic grants.',
      'Legacy global issues/reservations/fines/activity/stock have no canonical UUID attribution; exclude from Analytics.',
      'No authoritative attendance,RSVP,acquisition-cost,branch/cohort/clickstream source exists; no invented zero series.'],
    convergence='Exactly one planned LibraryAnalyticsService consumes canonical sources. Operational Overview, fixed Home Popular, personal counts, safe Platform directory and offline integrity reports retain different explicit purposes.')
(OUT/'institution_v2e_metric_inventory.json').write_text(json.dumps(PAYLOAD,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
baseline=dict(captured_at=BASE['captured_at'],audited_at=PAYLOAD['audited_at'],
    existing_dedicated_tenant_analytics_service=False,existing_staff_analytics_route=False,
    prechange_metric_count=len(METRICS),metric_classification_counts=COUNTS,
    source_inventory=[{k:v for k,v in item.items() if k!='matched_lines'} for item in SCAN],
    TEST=dict(snapshot_reference='reports/institution_v2e_baseline.json'),
    global_catalogue_count=BASE['global_count'],global_count_method=BASE['global_count_method'],
    preservation_baseline='reports/institution_v2e_baseline.json',no_private_domain_data_copied=True,
    no_tracking_system_required=True,
    initial_gap='Accepted Staff Overview has canonical API totals but no central scoped Analytics service/trends or Analytics route.')
(OUT/'institution_v2e_analytics_baseline.json').write_text(json.dumps(baseline,indent=2)+'\n',encoding='utf8')
md=['# Existing LuminaR analytics audit','',
 f'Prechange capture: {BASE["captured_at"]}. Searched {len(SCAN)} metric-bearing source/test/script files and inspected {len(METRICS)} actual metric entries in {len(GROUPS)} families. Source matches were followed into actual sources, guards, limits and frontend consumers; the JSON inventory includes line evidence and baseline hashes. Newly created Part2E files are excluded from this prechange inventory. No private reading data or credentials are copied here.','',
 '## Existing implementation and convergence','',
 'There was no dedicated tenant Analytics route/service. StaffLibraryShell assembles bounded canonical operation totals for the accepted Overview. Patron Home has account-specific counts and one real tenant Popular pipeline. Platform Console has installation counts and approved safe directory counts. Retired Admin/Librarian/Staff URLs redirect only. The new central service adds read-only Staff Analytics inside the accepted shell; it does not replace Home ranking, canonical business logic, personal features or frozen global services.','',
 'PLATFORM_GLOBAL is installation identity/catalogue/discovery. LIBRARY_TENANT requires explicit UUID attribution. PERSONAL_USER remains account owned. OPERATIONAL_HEALTH covers retrieval/worker/recovery/evaluation diagnostics. LEGACY_AMBIGUOUS is unattributed historical read-only compatibility. UNKNOWN_REVIEW_REQUIRED means no authority/tenancy is inferred. Independent old dashboards are OBSOLETE. Approved Platform library member/staff/book counts are a narrow existing exception, not tenant Analytics authority.','',
 '## Actual metric inventory','',
 '| Actual metrics | Classification | Source | Authority / bounds | Decision |','|---|---|---|---|---|']
for item in GROUPS:
    ref=item['evidence']; fields=['<br>'.join(item['metric_names']),item['classification'],
      f'[{ref["file"]}:{ref["line"]}]({ref["absolute_path"]}:{ref["line"]})',
      item['authority']+' '+item['bounds'],item['decision']]
    md.append('| '+' | '.join(v.replace('|','&#124;').replace('\n',' ') for v in fields)+' |')
md += ['', '## Canonical source semantics and risks','',
 '- Canonical tenant collections are institution_library_books, holdings, copies, lending_requests, loans, reservations, fees, fee_ledger, fee_policies, memberships, audit and lending_operations. Shared events require scope=LIBRARY plus exact UUID; outbox is institution_notification_outbox. No work-ID tenancy inference is valid.',
 '- Home Popular has a fixed 90-day weighted score: loan ACTIVE/RETURNED at borrowed_at ×8, BORROW APPROVED/COMPLETED at reviewed_at ×2, reservation WAITING/CONVERTED/FULFILLED at requested_at ×1. Final book/holding join stays in the exact library. Preserve Home ranking; staff book-level selected-range counts use these persisted activity semantics, without member rankings.',
 '- Holdings total_copies is quantity; available_copies is a legacy inventory snapshot, not canonical requestable. Reuse pure project(): physical units minus pending holds, active loans, unavailable_stock and unavailable copies. Queue priority/circulation status affect requestability. COPY mode verifies identified stock.',
 '- Part2C money uses integer minor units, immutable currency/unit factor and append-only CHARGE/CREDIT/WAIVER/PAYMENT_RECORD entries. Outstanding balance, assessed charge, credits/waivers and payments differ. Never float or combine old global fines with current ledger.',
 '- Lending/catalogue/reservation read helpers can expire holds/advance queues. Analytics must never invoke those maintenance paths. Freshly authorize and aggregate directly. Standalone Mongo projected journal effects/audits before COMMITTED are not completed activity.',
 '- Persisted UTC timestamps define ranges; no library timezone setting exists. Snapshot counts remain current. Activity/trend uses real timestamped rows/audit; no synthesis from current status. Event past/completed is schedule-derived, not attendance. First published_at is retained.',
 '- Worker last_scan is process-local health, not tenant lifetime totals. Durable outbox state/error grouping may be ADMIN-only after exact UUID matching; do not expose messages, recipients or source-specific member history.',
 '', '## Query/index review','',
 'Existing indexes scope memberships by library_id/status/role; books by library_id/status/created_at and subjects; holdings by library_id/book; copies by library_id/book and barcode; loans by library_id/borrowed_at/book plus library_id/book/status; requests by library_id/reviewed_at/book and library_id/type/status/requested_at; reservations by library_id/requested_at/book; audit by library_id/created_at; events by library_id/status/start_at and library_id/updated_at/event_id. Fee/ledger indexes are library/fee/state/date scoped. Measure actual explain plans before extra indexes. Global categories are prebuilt; never invoke their global5M build for tenant Analytics.',
 '', 'Start every tenant match and every lookup/union branch with the UUID. Bound top/subject outputs at10–20 and trend buckets by range. Bound query work with maxTimeMS; preserve unavailable/recovery states instead of fake zero. No whole-collection Python/React loading. Existing Platform directory performs three counts per bounded row; this narrow accepted N+1 is not expanded into Analytics. Correctness-first Analytics needs no cache; future keys require UUID/range/metric/filter and fresh authority even for hits.',
 '', '## Script/test classification and accepted compatibility','',
 'Institution V1 tests cover fresh membership/lifecycle. Part2A covers local inventory/import/legacy identity. Part2B/C cover allocation/journal recovery/reservation/fee invariants. Part2D covers event scope/outbox commit. Dashboard convergence tests cover PlatformRoleAssignment, legacy/library admin denial and safe platform counts. Frontend dashboard/catalogue/full-product tests verify accepted routes/presentation. These establish source semantics; new exact Analytics/read-only/denial fixtures are still required.',
 '', 'Offline benchmark/evaluation/report scripts produce recall,MRR,hit rates,latency,memory/index counts,dataset counts and regression totals. They are OPERATIONAL_HEALTH/report evidence, not live tenant usage; none ran for this audit. Router research/model changes stay out of scope. KG set/diversity comparisons are metadata exploration, not recommendation relevance. Private PDF list/pages/chunks are PERSONAL_USER; parse/chunk/cache counters are internal health, never staff analytics.',
 '', 'Legacy Platform historical operations use unattributed activity/issues/reservations/fines. They do not query canonical institution business collections. Retain explicitly read-only compatibility; do not count as tenant performance or expose newly summed private tenant lending/fees through Platform. Some old compatibility APIs have unbounded list reads; exclude them from the new aggregation service rather than duplicating their logic.',
 '', '## Preservation and unknowns','',
 'Audit writes reports only; no production/domain mutation. Full immutable preservation is institution_v2e_baseline.json; initial metric/source inventory is institution_v2e_analytics_baseline.json. No library is chosen from LIB001, legacy role, first membership or work ID. Unknown historical tenancy remains excluded until explicit canonical migration. No authoritative RSVP/attendance/acquisition-price/branch/clickstream metrics exist; they cannot be displayed as synthetic zero/history.', '']
(OUT/'institution_v2e_existing_analytics_audit.md').write_text('\n'.join(md),encoding='utf8')
print(json.dumps(dict(metrics=len(METRICS),families=len(GROUPS),metric_files=len(SCAN),classifications=COUNTS)))
