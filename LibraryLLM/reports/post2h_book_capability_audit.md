# Canonical book capabilities

`backend/services/library_book_formats.py` derives physical presence from a real canonical holding and online presence from currently authorized READY assets. Patron derivation includes MEMBERS only; Staff derivation may include STAFF_ONLY. “Format” describes current-user-accessible capabilities, not every resource known to staff. No holding, shelf or copies are fabricated for online-only records.

`frontend/src/lib/libraryBookCapabilities.ts:resolveLibraryBookCapabilities` is shared by presentation, BookCard, BookDetailView and CatalogueBookActions. Exact ACTIVE GENERAL_USER membership and current session are required for Patron actions. Physical Request/Waitlist also follows the backend availability/action flags. Online access does not depend on physical availability. Admin/Librarian cards retain Staff navigation/management; they receive no same-library Patron controls.

| Surface | Canonical path | Result |
|---|---|---|
| Home / For You / Recommendations | canonical DisplayBook → BookCard → CatalogueBookActions | Read Online and physical actions share resolver |
| New Arrivals / Popular / Browse | LibraryCatalogue/Home section → BookCard | same resolver |
| Library Search | canonical hydration → BookCard | same resolver; no ranking changes |
| Book Detail | BookDetailView + CatalogueBookActions + Digital Resources | online-only physical facts absent; BOTH exposes both |
| Local Reading List | exact saved library/book identities → authorized canonical batch hydration → BookCard | current READY/stock capabilities, no cached grants |
| Global Reading List / Related Books | GLOBAL_WORK identity → global BookCard | remains global personal/discovery data, no invented tenant holdings; linked saves retain existing unique global identity |
| Reservation / loan references | exact canonical book detail links | shared actions on detail; queue/history pages remain operational references |

A single permitted READY asset routes to its canonical resource with `book=<UUID>&open=1`. Fresh metadata must match that book before the existing protected PDF/text viewer mounts. Two or more assets return no arbitrary first resource; Read Online routes to `#digital-resources` for explicit choice. The async resource section scrolls into view after loading. Protected content endpoints revalidate current authorization.

Reading List previously reconstructed local records from global metadata with `owned_by_current_library=false` and no asset/format flags. It now hydrates local saved entries in bounded batches (200 maximum) using the accepted current-user catalogue and canonical read barrier. Unavailable saved entries expose no capabilities and remain removable. Globally saved identities stay global; no first membership or first holding is guessed.

Book-cover palette, geometry and renderer are unchanged. Shared rail navigation reserves the same 84px edge lane as the rail so the Assistant launcher cannot cover Next; actual Chromium checks show no action/launcher intersections at all six sizes. Intentional horizontal carousel scrolling remains.
