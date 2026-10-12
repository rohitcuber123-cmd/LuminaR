# Workspace design system

The implementation extends LuminaR's existing paper/ink/rust palette and existing
display/sans typography. Shared tokens live in frontend/src/styles/workspaces.css;
they do not impose an unrelated visual identity on the global product.

| Token | Value or existing alias |
|---|---|
| Background / surface | existing paper / #fffdf8 |
| Text / muted | existing ink / ink-soft |
| Primary | existing brand rust (#b3401f fallback) |
| Success / warning / danger | #36533d / #75511e / #9e2929 |
| Control boundary | #8e877b |
| Card / control radius | 12px / 8px |
| Spacing | 4, 8, 12, 16, 24, 32px |
| Header / sidebar | 64px / 232px |

PageHeading provides the eyebrow, page h1, description and contextual actions.
StatePanel provides consistent loading, empty and retryable error surfaces.
ActionMenu provides bounded per-row controls. Existing Modal uses native dialog focus
containment, labelled headings, Escape/outside close and focus restoration. Menu arrow
navigation lives in menuKeyboard.ts. Buttons, cards, badges, inputs and table wrappers
share sizes, contrast and focus treatment. Add Book requires only Title and Subject;
optional metadata is collapsed. Confirmation semantics remain those of existing actions.

Staff tables have explicit headers and a contained horizontal scroll area on small
screens; the document itself does not overflow. Patron browsing retains its card
presentation. Page headings and actions wrap on phones. Staff navigation collapses
below 1024px; the avatar becomes a bounded scrollable sheet. Ask LuminaR is hidden in
staff workspace and compact on account gateways, with bottom space on patron pages.

Five structural axe checks and browser contrast measurements passed. Text contrast
minimum is 4.90:1 in the nine measured surfaces. Dark mode redesign was intentionally
left for a separately approved phase.
