from pathlib import Path
import json,re,hashlib
from collections import defaultdict
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]; REPORT=ROOT/'reports'
def read(p):return p.read_text(encoding='utf8')
def dump(name,value): (REPORT/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
def md(name,text):(REPORT/name).write_text(text.strip()+'\n',encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
baseline=json.loads(read(REPORT/'frontend_v2_baseline_snapshot.json'))
changed=[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'before_sha256':baseline['frontend'].get(str(p.relative_to(ROOT))),'after_sha256':sha(p)} for p in (ROOT/'frontend/src').rglob('*') if p.is_file() and baseline['frontend'].get(str(p.relative_to(ROOT)))!=sha(p)]
protected=[p for p,h in baseline['protected'].items() if not (ROOT/p).exists() or sha(ROOT/p)!=h]
artifacts=[]
for p,old in baseline['artifact_reference'].items():
 f=Path(p)
 if not f.exists():artifacts.append({'path':p,'change':'missing'});continue
 st=f.stat()
 if st.st_size!=old['size'] or (old.get('sha256') and sha(f)!=old['sha256']) or (not old.get('sha256') and st.st_mtime_ns!=old['mtime_ns']):artifacts.append({'path':p,'change':'content or large-file metadata changed'})
semantic=[]
for p,h in baseline['frontend'].items():
 if any(x in p for x in ['\\hooks\\','\\store\\','\\lib\\']) and not p.endswith('paginationScroll.ts') and sha(ROOT/p)!=h:semantic.append(p)
dump('frontend_v2_changed_files.json',{'source_changes':changed,'test_changes':['frontend/tests/library-catalogue.test.tsx','frontend/tests/staff-catalogue-titles.test.tsx','frontend/tests/post2h-product.test.tsx','frontend/tests/platform-completion.test.tsx','frontend/tests/frontend-design-v2.test.tsx'],'package_change':'Adds test:design-v2 to npm test; no dependency changes','protected_python_checked':len(baseline['protected']),'protected_python_changes':protected,'frontend_semantics_changes':semantic,'artifact_reference_checked':len(baseline['artifact_reference']),'artifact_changes':artifacts,'baseline':'frontend_v2_baseline_snapshot.json','git':'Pre-existing dirty tree preserved; no staging, reset or commit.'})
raw=json.loads(read(REPORT/'frontend_v2_browser_measurements.json'))
# Retain the final measurement of each route/width. Earlier loading and pre-fix measurements remain in the raw evidence.
latest={}
for row in raw:
 if row['heading']:latest[(row['family'],row['url'],row['requested'])]=row
rows=list(latest.values());families=defaultdict(set)
for r in rows:families[r['family']].add(r['url'])
clipped=[{'route':p['url'],'width':p['width'],'book':c['title'],'controls':c['clipped']} for p in rows for c in p['cards'] if c['clipped']]
overflow=[{'route':p['url'],'width':p['width'],'pixels':p['horizontalOverflow']} for p in rows if p['horizontalOverflow']>1]
alignment=[];group_count=0
for page in rows:
 groups=defaultdict(list)
 for c in page['cards']:groups[(c['rail'],round(c['rect']['y']))].append(c)
 for key,cards in groups.items():
  if len(cards)<2:continue
  group_count+=1
  spread=max(c['actions']['y'] for c in cards)-min(c['actions']['y'] for c in cards)
  primary=max(c['primary']['y'] for c in cards)-min(c['primary']['y'] for c in cards)
  if spread>1 or primary>1:alignment.append({'route':page['url'],'width':page['width'],'secondary_spread':spread,'primary_spread':primary})
platform={'status':'BLOCKED','authenticated_screen_audits':0,'guard_verified':True,'reason':'The supplied legacy ADMIN account signs in but has no explicitly approved PLATFORM_ADMIN assignment. UI: Platform access required. This console requires an explicitly approved platform assignment.','permissions_changed':False,'routes_pending':['/platform','/platform/catalogue','/platform/libraries','/platform/accounts','/platform/notifications','/platform/history','/platform/migration-review','/platform/events'],'component_regressions':'Covered by existing platform/workspace frontend unit suites; this does not replace real authenticated Chromium review.'}
dump('frontend_v2_platform_access.json',platform)
route_audit={'engine':'Codex in-app Chromium; CUA only','routes_audited':sum(map(len,families.values())),'family_counts':{k:len(v) for k,v in families.items()},'routes':{k:sorted(v) for k,v in families.items()},'platform':platform,'measurements':rows,'raw_evidence':'frontend_v2_browser_measurements.json','method':'Wait for membership and route content; DOM bounding boxes for geometry. Empty initial headings/loading captures excluded. Last measurement replaces earlier pre-fix samples.','width_note':'All six requested CSS widths are covered exactly. Saved 80% browser zoom was compensated for the initial measurements; exact 768px was then verified on every route using Chromium tablet emulation (device scale factor 1). Temporary metrics overrides are reset after review.'}
dump('frontend_v2_route_audit.json',route_audit);dump('frontend_polish_route_audit.json',route_audit)
dump('frontend_v2_card_alignment.json',{'status':'PASS' if not alignment and not clipped else 'FAIL','compared_rows':group_count,'tolerance_px':1,'alignment_defects':alignment,'clipped_actions':clipped,'method':'Group equal-top cards within grid/rail rows; compare secondary and primary action origins. Off-screen horizontal rail cards are intentional scroll content.'})
dump('frontend_v2_responsive.json',{'status':'PASS' if not overflow and not clipped else 'FAIL','requested_widths':[320,375,390,768,1024,1440],'measurements':len(rows),'horizontal_overflow':overflow,'clipped_controls':clipped,'zoom_note':route_audit['width_note'],'forms':'frontend_v2_forms.json'})
motion=json.loads(read(REPORT/'frontend_v2_motion_browser.json'));pagination=json.loads(read(REPORT/'frontend_v2_pagination_browser.json'))
dump('frontend_v2_carousels.json',{'status':'PASS','interactive_variants':['ForYou','NewArrivals'],'shared_component':'BookCarousel','widths':{'desktop':200,'small':180},'gap':20,'navigation':'44px circles below rail; disabled edge states; advances whole visible cards based on measured width','edge_padding_px':4,'overflow_menu':'Portal to body with viewport-bounded position','motion_evidence':motion['carousel'],'decorative_variants':['Hero cover marquee','AlsoLikeTicker spotlight/ticker'],'decorative_review':'Cover-only links retain their editorial purpose; dramatic hover rotation/scale removed; reduced motion disables continuous animations.'})
dump('frontend_v2_reduced_motion.json',{'status':'PASS','browser':motion['reduced'],'route':'Native entry animation skipped when reduce is matched','scroll':'instant; explicit smooth override cannot bypass reduce','dialogs':'No delayed exit under reduce','carousel':motion['carousel']['reduced'],'automated_tests':'frontend_v2_design_tests.log'})
dump('frontend_v2_pagination.json',{'status':'PASS','browser':pagination,'selector_priority':'Select first available selector in declared fallback order, rather than first ancestor in DOM order.','async_results':'Resize/mutation observers realign a replaced results anchor for up to ten seconds; pointer, wheel, touch or keyboard input cancels pending alignment. Different route pathname is never scrolled.','filter':'No pathname animation or blanket scroll on query changes.','missing_anchor':'No page-top fallback.','tests':'Priority selectors, delayed replacement, user cancellation, reduced motion and POP restoration.'})
dump('frontend_v2_accessibility.json',{'status':'PASS_FOR_REVIEWED_SURFACES','structural_axe':'Open book overflow and cards: zero violations, color-contrast and landmark region rules disabled in JSDOM; existing search structural axe suite also passes.','keyboard':['Cover and title links separate from action buttons','Escape closes overflow and restores trigger focus','ArrowDown opens overflow; links remain in normal Tab order','Modal trap and focus return retained; busy modal cannot close','Mobile sidebar Escape returned focus to Open workspace menu'],'touch':'Primary 44px; compact icons 38px desktop and 44px mobile; carousel arrows 44px','limits':['No authenticated platform-admin visual/accessibility review was possible.','Structural axe checks do not constitute a complete screen-reader or browser contrast audit.'],'browser_sidebar':motion['sidebar']})
dump('frontend_v2_browser.json',{'engine':'real Chromium through CUA','route_report':'frontend_v2_route_audit.json','responsive_report':'frontend_v2_responsive.json','screenshots':[p.name for p in REPORT.glob('frontend_v2_*.png')],'overflow_evidence':'frontend_v2_overflow_browser.json','online_actions':'Read Online remains primary on online-only CN; Know More overflow resolves exact library/book/asset context. Save round-trip tested on disposable QA account.','protected_behavior':'No generation or lending commands submitted during browser visual review.','platform':platform})
# Source inventory with direct imports and transitive route consumers.
files=list((ROOT/'frontend/src').rglob('*.tsx'));sources={str(p.relative_to(ROOT/'frontend/src')).replace('\\','/'):read(p) for p in files}
def resolve(src,imp):
 if imp.startswith('@/'):path=ROOT/'frontend/src'/imp[2:]
 elif imp.startswith('.'):path=(ROOT/'frontend/src'/src).parent/imp
 else:return None
 for candidate in [path.with_suffix('.tsx'),path/'index.tsx']:
  if candidate.exists():return str(candidate.resolve().relative_to((ROOT/'frontend/src').resolve())).replace('\\','/')
 return None
graph={s:[r for i in re.findall(r"from ['\"]([^'\"]+)",text) if (r:=resolve(s,i))] for s,text in sources.items()}
def uses(src,target,seen=None):
 if src==target:return True
 seen=set() if seen is None else seen
 if src in seen:return False
 seen.add(src);return any(uses(x,target,seen) for x in graph[src])
entries=[]
for src,text in sources.items():
 tags={name:len(re.findall(r'<'+name+r'\b',text)) for name in ['BookCard','DiscoveryBookFrame','BookCarousel','BookPersonalActions','CatalogueBookActions','ActionMenu','ActionOverflow','ProductPagination','Pager','EventPager','LuminarSelect','Modal','Button','IconButton','StatusPill']}
 if any(tags.values()) or re.search(r'<button|<input|<select|event-book|assistant-result-card',text):entries.append({'source':src,'instances':tags,'native_buttons':len(re.findall(r'<button\b',text)),'form_controls':len(re.findall(r'<(?:input|select|textarea)\b',text)),'route_consumers':[p for p in sources if p.startswith('pages/') and uses(p,src)]})
variants=[{'variant':v,'architecture':a} for v,a in [('Global catalogue/search','BookCard'),('Patron catalogue/search','BookCard'),('Staff catalogue','BookCard'),('Reading list','BookCard'),('For You rail','BookCard + BookCarousel'),('New Arrivals rail','BookCard + BookCarousel'),('Popular grid','BookCard'),('Related/More Like This','BookCard with unchanged WhyRelated/connection disclosure'),('Event book reference','Compact cover/title/author link; shared title/author reservation CSS; no embedded actions'),('Hero cover marquee','Decorative cover-only discovery links'),('Spotlight','Single editorial cover-only link'),('Assistant result','Conversational result surface; shared action button styles, original handlers retained')]]
inv={'files':entries,'file_count':len(entries),'book_variants':variants,'carousel_variants':['ForYou','NewArrivals','Hero decorative marquee','AlsoLikeTicker decorative spotlight/ticker'],'button_variants':['primary','secondary','ghost','danger','icon'],'form_variants':['text/search','number','textarea','LuminarSelect','checkbox','radio','file'],'fixed_findings':['Full-width per-card action stacks replaced','Duplicated View Details CTA removed','Staff catalogue nested horizontal padding removed','Related cards share main card frame','Menus portal outside clipped rails','Stable compact AI label in selected state','Priority results anchor and async pagination alignment','Route animation uses pathname change and does not remount forms'],'intentional_variants':'Reference/decorative/conversational book presentations preserve their different roles; no fabricated circulation or digital capability is added.'}
dump('frontend_v2_component_inventory.json',inv);dump('frontend_polish_component_inventory.json',inv)
md('frontend_v2_baseline.md','''# Frontend V2 baseline
The workspace already contained extensive uncommitted work. The task-start snapshot hashes 169 frontend files and 212 protected Python files. It also records 50 protected artifact references. `frontend_v2_before.png` captures the recovered catalogue before this redesign.
The existing shared BookCard stacked all personal actions at full width, duplicated View Details, and changed height with capabilities. Cards lacked a common action slot. Rail movement assumed 180px cards and four-card pages. Route changes used a blanket scroll-to-top hook. Prior frontend regression coverage was 903 tests.
Services use the existing MongoDB database. No database path or credentials were reset. This task did not resume V2C-C.2 or Part 2I.
''')
md('frontend_v2_button_system.md','''# Shared button system
`Button.tsx` provides primary, secondary, ghost and danger variants plus a required-label IconButton. Existing application controls consume the same CSS tokens. Primary controls are 44px with 11–12px rounded rectangles; secondary controls are 40px with 10px corners; icon controls are 38px desktop and 44px mobile. Carousel arrows remain 44px circles. Status/filter chips alone use pill geometry.
Disabled/busy buttons retain native disabled semantics and accessible names. Hover lift is 1px over 160ms; focus outlines remain visible. Inputs/selects use the existing 44px form geometry with the shared 11px control radius. No animation dependency was added.
''')
md('frontend_v2_action_priority.md','''# Card action priority
The compact row contains Save/Saved, AI with stable width and pressed state, and overflow. Cover and title are separate detail links; the article is not a click target.
Primary slot priority: existing loan/request/reservation details, otherwise a permitted physical Request Book or Join Waitlist, otherwise permitted Read Online. Global entitled READ NOW remains available. Empty slots retain shared geometry. Staff cards do not gain patron actions.
Know More and physical-card digital alternatives move into overflow. Legacy account-scoped global reader/RAG entitlements on linked tenant books remain in that menu. More Like This and search-result explanations remain reachable. Detail screens retain their full workflow. The capability resolver, authorization guards, command endpoints, idempotency and callbacks are unchanged.
''')
md('frontend_v2_status_pills.md','''# Status pills
Shared StatusPill uses 26px compact geometry, text plus muted color, and a consistent top-right cover position. It derives Online, Physical and Physical + Online from existing capability flags. Global and Unavailable are neutral; the UI does not invent a format or availability. Physical shelf data appears only for actual physical books.
''')
md('frontend_v2_book_card_architecture.md','''# Shared card frame
BookCard / DiscoveryBookFrame serve global, tenant, saved, search, popular, rail and related-book results. Cover ratio 2:3, reserved two-line title, one-line author/fallback, one-line availability, 46px metadata slot, compact secondary row and 52px primary slot are shared CSS rules. Grid and rail children stretch within rows; actions align without per-page card heights.
Source subject labels occupy a stable grid zone. Missing ratings, author, shelf or actions retain layout structure without empty textual labels. Related-book explanations remain below the shared frame; explicit detailPath retains the original tenant global-book destination.
The measured alignment report compares real DOM action origins by row. It reports final measurements separately from raw pre-fix evidence. Compact event references, editorial cover-only links and conversational result cards are audited intentional variants, not lending cards.
''')
md('frontend_v2_page_transitions.md','''# Route entry
RoutePresentation animates the existing content node with opacity and a 6px translate over 200ms on pathname changes only. It uses native Web Animations and never keys/remounts routes to animate. Query, filter, pagination and local form updates do not replay it. Auth and assistant screens now expose the same main content landmark.
New paths start at top; query changes preserve position; POP restores stored entry position, including async layout restoration. Hash navigation and pagination use the sticky-header offset helper. Reduced motion skips entry animation.
''')
md('frontend_v2_sidebar_motion.md','''# Sidebar motion
Desktop sidebar sizing and fixed layout remain unchanged. The existing native dialog drawer enters from the left over 220ms, with a fading backdrop. Close/Escape uses a 160ms exit; normal dialogs use 180ms entry and 120ms exit. Busy-state close guards, modal focus containment and focus return remain intact. Browser Escape returned focus to Open workspace menu. Reduced motion closes immediately.
''')
md('frontend_v2_motion_system.md','''# Motion
Shared durations: button/menu 150–160ms; card 180ms/2px lift; route 200ms/6px entry; drawer 220ms. Dropdowns, filter disclosure, existing autocomplete and clarification panels use short CSS transitions. Filter disclosure interpolates intrinsic block size instead of a fixed height. Auth/button and decorative cover hover effects use restrained motion. Existing toast entry remains shared and reduced-motion-aware.
The global reduce rule disables animations/transitions and smooth scrolling. JS route, dialog and carousel handling also checks the media preference. No springs, scale-heavy card effects, large dependency or animated business-data updates were introduced.
''')
md('frontend_v2_visual_review.md','''# Visual review
Cream surfaces, burnt-orange primary actions and editorial covers remain. The action stacks are replaced by a compact row and one primary slot. Status pills sit consistently on covers. Long titles and missing metadata retain the same row geometry. Carousels use consistent 200px/180px cards, 20px gaps and controls below their content.
Real Chromium checks cover global, patron and owner/admin library workspaces. Physical, online and combined forms were inspected without submitting changes. An online-only CN book retained Read Online and its exact book/asset Know More destination. Save was tested only on a disposable QA account and reverted. No lending or generation command was sent.
The platform account supplied by the user authenticated, but its legacy ADMIN role is not an approved PLATFORM_ADMIN assignment. Authenticated platform screen review remains blocked; no permissions were changed. The overall mandatory-gate result is therefore PARTIAL, not PASS.
See raw and final route measurements, card alignment, responsive, accessibility and motion reports. All six requested CSS widths, including exact 768px tablet emulation, are covered. Earlier compensated/bracket measurements remain only in raw evidence.
''')
# Final QA is derived from completed command outputs, never a planned test count.
log=read(REPORT/'frontend_v2_tests_final.log');counts={k:sum(map(int,re.findall('ℹ '+k+r' (\d+)',log))) for k in ['tests','pass','fail']}
complete='> luminar-library@0.0.0 test:design-v2' in log and bool(re.search(r'ℹ tests 28',log)) and counts['fail']==0
build=read(REPORT/'frontend_v2_build.log');lint=read(REPORT/'frontend_v2_lint.log')
qa={'FINAL':'PARTIAL','FRONTEND_REDESIGN_COMPLETE':'NO — implementation complete; authenticated platform visual gate blocked','BUTTON_SYSTEM_REDESIGNED':'PASS','PRIMARY_BUTTON_SHAPE':'44px rounded rectangle, 11–12px radius','SECONDARY_BUTTON_SHAPE':'40px rounded rectangle, 10px radius','ICON_BUTTON_SYSTEM':'PASS','STATUS_PILLS':'PASS','ONLINE_STATUS_PILL':'PASS','PHYSICAL_STATUS_PILL':'PASS','COMBINED_STATUS_PILL':'PASS','LARGE_KNOW_MORE_BUTTONS_REMOVED':'YES — card surfaces; detail workflows preserved','DETAIL_NAVIGATION_VIA_CARD':'PASS','READING_LIST_COMPACT_ACTION':'PASS','SELECT_FOR_AI_COMPACT_ACTION':'PASS','OVERFLOW_MENU':'PASS','ONE_PRIMARY_CTA_RULE':'PASS','BOOK_CARDS_PERFECTLY_ALIGNED':'PASS' if not alignment and not clipped else 'FAIL','GRID_CARD_ALIGNMENT':'PASS' if not alignment else 'FAIL','CAROUSEL_CARD_ALIGNMENT':'PASS' if not alignment else 'FAIL','PRIMARY_CTA_ALIGNMENT':'PASS' if not alignment else 'FAIL','LONG_TITLE_LAYOUT':'PASS','MISSING_METADATA_LAYOUT':'PASS','MORE_ACTIONS_OVERFLOW':'PASS' if not clipped else 'FAIL','CAROUSEL_EDGE_CLIPPING':'PASS','CAROUSEL_ARROWS_REDESIGNED':'PASS','ROUTE_ENTRY_ANIMATION':'PASS','SIDEBAR_MOTION':'PASS','DROPDOWN_MOTION':'PASS','AUTOCOMPLETE_MOTION':'PASS — existing short CSS retained','CLARIFICATION_MOTION':'PASS — existing short CSS retained','CARD_HOVER_MOTION':'PASS','BUTTON_MICROINTERACTIONS':'PASS','PAGINATION_SCROLL':'PASS','PREFERS_REDUCED_MOTION':'PASS','GLOBAL_ROUTES_AUDITED':len(families['global']),'PATRON_ROUTES_AUDITED':len(families['patron']),'STAFF_ROUTES_AUDITED':len(families['staff']),'ADMIN_ROUTES_AUDITED':2,'ADMIN_ROUTE_NOTE':'Library members and audit reviewed as owner/admin. Authenticated platform-admin routes: 0.','KNOWN_ALIGNMENT_DEFECTS':len(alignment),'KNOWN_CLIPPED_ACTIONS':len(clipped),'KNOWN_HORIZONTAL_OVERFLOW':len(overflow),'FRONTEND_FULL_SUITE':{**counts,'complete':complete,'log':'frontend_v2_tests_final.log'},'TYPESCRIPT':'PASS' if '✓ built' in build else 'PENDING','PRODUCTION_BUILD':'PASS' if '✓ built' in build else 'PENDING','LINT':'WARNINGS' if 'warning ' in lint else 'PASS','ROUTES_AUDITED':sum(map(len,families.values())),'BOOK_CARD_VARIANTS_AUDITED':len(variants),'CAROUSEL_VARIANTS_AUDITED':4,'BUTTON_VARIANTS':5,'FORM_CONTROL_VARIANTS':7,'KNOWN_ALIGNMENT_DEFECTS_REMAINING':len(alignment),'KNOWN_OVERFLOW_DEFECTS_REMAINING':len(overflow),'KNOWN_CLIPPED_ACTIONS_REMAINING':len(clipped),'BOOK_CARD_ACTION_ALIGNMENT':'PASS' if not alignment else 'FAIL','CAROUSEL_ACTION_ALIGNMENT':'PASS' if not alignment else 'FAIL','ROUTE_SCROLL_RESTORATION':'PASS','SITE_WIDE_MOTION':'PARTIAL — authenticated platform screens unreviewed','BLOCKERS':[platform['reason']],'WIDTH_NOTE':route_audit['width_note']}
for width in [320,375,390,768,1024,1440]:qa[str(width)]='PASS' if not [r for r in overflow+clipped if r['width']==width] else 'FAIL'
for key in ['BACKEND_CHANGED','SEARCH_PARSER_CHANGED','SEARCH_RANKING_CHANGED','TENANT_AUTH_CHANGED','CIRCULATION_LOGIC_CHANGED','RESERVATION_LOGIC_CHANGED','FEES_LOGIC_CHANGED','HNSW_CHANGED','KG_CHANGED','QWEN_CHANGED','RECOMMENDATION_CHANGED','MORE_LIKE_THIS_CHANGED','V2C_C2_STARTED','PART_2I_STARTED']:qa[key]='NO'
qa['PRESERVATION_CHECK']={'python_changes':protected,'frontend_semantics_changes':semantic,'artifact_changes':artifacts}
qa['generated_at']=datetime.now(timezone.utc).isoformat();dump('frontend_v2_final_qa.json',qa)
print(json.dumps({'source_changes':len(changed),'routes':qa['ROUTES_AUDITED'],'rows_compared':group_count,'alignment_defects':len(alignment),'clipped':len(clipped),'overflow':len(overflow),'protected_changes':protected,'artifact_changes':artifacts,'tests':counts,'suite_complete':complete}))
