# LuminaR Frontend Polish — Baseline Audit

## Stack Summary
- Framework: React 19 + Vite 8
- Styling: Tailwind CSS v4 + custom CSS modules
- Icons: lucide-react
- Router: react-router-dom v7
- No animation library (CSS-only)

## CSS Architecture
| File | Role |
|------|------|
| src/index.css | Global @theme tokens, animations, auth, assistant |
| src/styles/workspaces.css | Staff/patron workspace, header, sidebar, buttons, dialogs, tables |
| src/styles/product.css | Public catalogue, book cards, search, carousel, pagination |
| src/pages/Staff.css | Staff typography, stats, panels, pager, badges, forms |
| src/pages/Institutions.css | Patron institution layout, cards, toolbar |
| src/pages/LibraryInventory.css | Inventory/reservations/fees filter rows |

## Existing Design Tokens
### @theme (index.css)
--font-display, --font-sans
--color-paper #faf8f4, --color-ink #191714, --color-ink-soft #4a463f
--color-line #e4dfd5, --color-panel #f1ede4
--color-brand #b3401f, --color-brand-dark #8f3016, --color-moss #4c5b3f

### :root (workspaces.css)
--ui-radius: 12px, --ui-control-radius: 8px
--ui-space-1..8: 4px 8px 12px 16px 24px 32px

## Button Variants Found
.ui-button: min-height 42px, radius 8px (STANDARD)
.staff-primary: ~38px, radius 6px (INCONSISTENT)
.assistant-button: ~30px, radius 2px (INCONSISTENT)

## Pagination — All lack scroll restoration
- ProductPagination (components/ProductPagination.tsx)
- Pager (components/StaffUI.tsx)
- Inline in LibraryReservationsFees.tsx, LibraryInventory, LibraryCirculation

## Key Inconsistencies
1. No scroll-to-results on any paginator
2. Button heights 30-44px in same UI regions
3. Input border-radius 4-12px across pages
4. Filter row label/control baseline misalignment
5. BookCard actions below variable-height metadata
6. Cover hover scale-[1.02] too dramatic
7. No overflow protection for More actions in carousel
8. prefers-reduced-motion incomplete
9. No motion tokens
10. Disabled pagination opacity .4 only — contrast risk
11. No nav hover/active transitions
12. Focus ring inconsistent (ink vs brand)
