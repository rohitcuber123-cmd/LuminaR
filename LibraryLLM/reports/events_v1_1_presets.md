# LuminaR Events V1.1: preset-driven publishing UX

Result: **PASS**. This extends the existing canonical Events V1 module. No migration, new Event schema field, category-specific collection, separate preset identity, or router experiment was introduced. V1 reports and unrelated production source hashes remain unchanged.

## Architecture and event type control

`frontend/src/lib/eventPresets.ts` is the single `EVENT_PRESETS` configuration: helpers, section ordering, field labels, book-picker mode, schedule folding and default featured state. The editor consumes these properties rather than category-specific form branches. Existing EventIcon components provide the selected type icon. The full-width native Event Type select is the first form control, labelled “What kind of event are you publishing?”, and defaults new drafts to New Arrivals. Existing edits load their saved canonical category. It contains all 11 categories, including Community Event and Library Closure with the requested labels.

The Python validator and TypeScript validation import the same `backend/schemas/event_publish_requirements.json`. The shared contract has no executable code and is bundled into the frontend. Backend validation remains authoritative, including direct API calls. Existing category, dates, summary, description, location, featured and ordered canonical work IDs are the only stored content fields. Speaker information uses summary/description.

## Preset matrix

| Event Type | Primary section and books | Dates / location | Additional requirements to publish |
|---|---|---|---|
| New Arrivals | Prominent **New Books** picker | Optional collapsed schedule/location | At least one book |
| Book Sale | Schedule first; optional **Books in Sale** | **Sale Starts / Sale Ends**, sale venue | Start and location |
| Workshop | Schedule first; optional related books | **Workshop Starts / Workshop Ends**, venue | Start, description and location |
| Author Event | Speaker-aware summary/description; optional related books | **Author Event Starts / Author Event Ends**, venue | Base schema only; speaker information in existing text |
| Reading Club | Prominent **Reading Club Books**, one or several | **Meeting Starts / Meeting Ends**, venue | At least one book |
| Community Event | Schedule first; optional books | **Community Event Starts / Community Event Ends** | Base schema only |
| Library Program | Schedule first; optional books | **Program Starts / Program Ends** | Base schema only |
| Library Notice | Concise information; optional books collapsed | Optional schedule/location collapsed | Base schema only |
| Library Closure | **Reason / Description**; book controls hidden | **Closure Starts / Reopens / Closure Ends**; optional whole-library venue | Start, end and reason |
| Exhibition | Schedule first; optional books | **Exhibition Starts / Exhibition Ends** | Base schema only |
| Other | Full generic V1 form | Generic dates/location | Base schema only |

New Arrivals helper starts “Choose the new books you want to highlight.” Reading Club supports multiple ordered books rather than introducing a single-book schema. Book Sale is an offline announcement: there are no price, cart, checkout, payment or purchasing controls. Author Event explicitly guides staff to enter speaker details in existing text. Closure can apply to the whole library without a location. Other keeps the entire generic form available.

## Drafts, publication and corrections

Drafts may omit dates, venue, summary, description and books. Base validation still requires a title of at least three characters, bounded plain text, a valid date range, existing distinct canonical work IDs and at most 12 linked books. End without start, end before start and invalid catalogue references remain rejected.

Publish Now runs base and preset validation before saving or opening confirmation. The backend applies the same category requirements before the first DRAFT → PUBLISHED transition. Specific errors explain the missing field/book. The accessible error summary links to the corresponding input or picker and expands its optional section on explicit activation. Changing a draft type keeps focus on the select and preserves valid generic values, dates, featured state and selected book order. Hidden books remain linked; unavailable catalogue IDs are shown explicitly and must be removed rather than silently dropped.

Published type changes open an explicit confirmation before adopting the new selection. Saving uses the existing PATCH path. It preserves status, first published_at, first author and existing seen identity; the server continues to own audit values. Compliant publications cannot be edited into a state that violates their category requirements. Changing the category of any publication adopts its new requirements. Existing V1 publications that never met V1.1 requirements can still receive same-category corrections without a backfill. Idempotent publish does not reset publication or create a new signal. Cancel/archive/draft-delete rules, role checks and receipt semantics stay unchanged.

Both editor and management-list publish confirmations show type, title, start/end dates when available, location and linked-book count. Confirmation is still a separate explicit action after draft saving.

## Responsive validation

Desktop layouts place basic information beside the primary preset section, with the Event Type control spanning the full width. At tablet/mobile widths the sections stack; mobile dates stack and catalogue search remains usable. Actual rendered DOM dimensions were verified at **1440×900, 1366×768, 768×1024 and 375×812** for New Arrivals and Workshop, including real selected books/search results. `scrollWidth == clientWidth` at all four sizes. At 375×812 the two Workshop dates have the same x coordinate and separate y coordinates. The picker was used successfully in the preview with real catalogue results.

The in-app browser scales viewport overrides. Overrides were calibrated against measured page dimensions before acceptance. Screenshot captures use provider scaling and clipping; they are proof of UI interaction, not full-resolution layout exports. The authoritative dimensions and element bounds are in the JSON reports.

## Live A–F acceptance

- **A:** Librarian saw the 11-option dropdown; New Arrivals selected three real catalogue books; explicit summary showed count 3; publication succeeded; public detail displayed three linked books. First-publication API count increased by one; staff UI showed one toast for the observed publication.
- **B:** Empty New Arrivals draft saved; Publish Now identified the missing book without publishing; adding one real book allowed explicit publication.
- **C:** Book Sale showed Sale Starts/Ends, location and optional Books in Sale; start/location with zero books published, with no commerce fields or controls.
- **D:** Closure hid book controls; missing end blocked publishing; adding end and reason allowed publication.
- **E:** Workshop → Library Notice → Workshop preserved title, start, end, venue and description in the actual browser. Automated tests also cover featured and selected book order across Notice/Closure switches.
- **F:** Published Workshop → Community Event opened explicit confirmation, then Save changes used PATCH. Actual published_at stayed unchanged and reader unseen count stayed **4 → 4**; the correction generated no fresh event signal. Existing toast/monitor implementation hashes and deduplication tests remain unchanged.

Tests used synthetic accounts and marker-scoped events on the already allowed local port-3000 origins. The normal 5173 user sessions were untouched. Cleanup removed 15 synthetic events, 2 seen states and 4 disposable accounts, and stopped the temporary preview. The usual five development services remain healthy.

## Tests and regression preservation

Events backend: **76 passed**, comprising 48 V1 cases and 28 new cases. Events frontend: **49 passed**, comprising 28 V1 cases and 21 new cases. New tests cover all category presets, direct publication requirements, empty drafts, switching preservation, explicit published confirmation, compact summary, correction semantics, legacy compatibility and the shared contract.

All production backend regressions passed: unit 37, Assistant 439, security 115 passed/10 existing skips, staff 76, notifications 51, circulation 40 and Search 157. Together with Events: **991 passed, 10 existing skips**. Search includes Recommendation paging/depth regressions; production Assistant/security suites include KG, Book RAG and document-security coverage. The 191 existing frontend regressions also passed, for **240 frontend tests total**. Build passes. Lint has **0 errors and 19 existing warnings**, with no new Events warnings.

No frozen router corpus, training or evaluation was rerun. Assistant remains existing_qwen; the existing RAG process has no child workers. Source hash audit confirms Search, Recommendation, KG, RAG, Admin/Notifications, auth, monitor/store/header/toast and frozen V1 evidence were not changed.

## Performance

Five actual HTTP samples per action, all first publications: draft create median 9.36 ms, draft edit 10.54 ms, first publish 10.30 ms, staff editor detail 9.18 ms. All remain within prior local budgets (writes <500 ms, detail <250 ms); V1 medians were 12.05/13.60/11.16/8.48 ms respectively. Browser edit navigation to controls was 504 ms. Picker click-to-results samples were 1092 ms then 303 ms, including automation overhead and real unchanged Search calls. No new search request path or model loading was added. These warm local samples are contextual, not a controlled large-catalogue benchmark. The production JS bundle grew from 529.67 to 539.18 kB uncompressed (9.51 kB).

## Exact source/config/test files

Existing files modified:
- `backend/services/event_service.py`
- `frontend/src/lib/events.ts`
- `frontend/src/pages/EventEditorPage.tsx`
- `frontend/src/pages/Events.css`
- `frontend/src/pages/ManageEventsPage.tsx`
- `frontend/tests/events.test.tsx`
- `frontend/tsconfig.app.json`
- `tests/events/test_events.py`

Files added:
- `backend/schemas/event_publish_requirements.json`
- `backend/services/event_publish_validation.py`
- `frontend/src/components/events/EventPublishSummary.tsx`
- `frontend/src/lib/eventPresets.ts`
- `scripts/check_events_v1_1_live.py`
- `scripts/start_events_v1_1_stack.ps1`
- `scripts/test_events_v1_1_regressions.py`
- `tests/events/test_event_presets.py`

The two V1 test files changed only to adopt intentional publication requirements and add preset coverage: generic backend lifecycle fixtures now use Other, New Arrivals publication fixtures link a real test book, the explicit frontend publication test selects a book, and generic date validation switches to Other. Frozen V1 report files were preserved.

## Required reports

- `reports/events_v1_1_presets.md` — architecture, matrix, live findings, performance and exact files.
- `reports/events_v1_1_validation.json` — requirements, semantic validation, responsive data and limitations.
- `reports/events_v1_1_live.json` — actual API/browser checks, dimensions, timings and cleanup.
- `reports/events_v1_1_regression.json` — suite totals, build/lint and preservation audit.

Supporting files include V1.1 XML/log outputs, browser evidence JSON, calibrated screenshots, before-correction evidence and baseline/file-audit JSON.

## Known limitations

Speaker information is plain text, without structured speaker identity. Legacy incomplete V1 publications retain same-category correction compatibility. In-app screenshots are provider-scaled/clipped rather than full-resolution exports; exact responsive acceptance uses measured DOM dimensions. Local timings do not guarantee performance at a much larger Events catalogue. Existing security fixture skips and lint warnings remain. No RSVP, attendance, registration, ticketing or commerce work is included.
