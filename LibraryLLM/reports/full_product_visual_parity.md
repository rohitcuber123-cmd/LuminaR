# Visual parity validation

Status: NOT_VERIFIED. Source composition reuse and JSDOM assertions do not prove rendered layout/overflow.

Existing IAB tabs are stuck on internal data:text/html connection-error pages; browser tool denies inspection/navigation. User asked asynchronously to reopen http://127.0.0.1:5173/. No usable tab/reply available. No alternate automation or fabricated screenshots.

| Viewport | Global screen | TEST screen | Layout/spacing/typography/overflow |
| --- | --- | --- | --- |
| 1440x900 | NOT_CAPTURED | NOT_CAPTURED | NOT_VERIFIED |
| 1366x768 | NOT_CAPTURED | NOT_CAPTURED | NOT_VERIFIED |
| 1024x768 | NOT_CAPTURED | NOT_CAPTURED | NOT_VERIFIED |
| 768x1024 | NOT_CAPTURED | NOT_CAPTURED | NOT_VERIFIED |
| 390x844 | NOT_CAPTURED | NOT_CAPTURED | NOT_VERIFIED |
| 375x812 | NOT_CAPTURED | NOT_CAPTURED | NOT_VERIFIED |


Implemented: common two-column detail/cover/typography; shared search/chips/filters/grid/paging and personal actions; wrapping metadata/long words/min-width:0; mobile one-column details and wrapped controls; accepted responsive Header/Modal/Carousel retained. Axe semantic checks run with color-contrast disabled because JSDOM cannot compute rendered contrast. Browser contrast, focus, overlays, touch layout, dimensions and no-overflow remain required. User screenshots were not re-labelled as after-change evidence.
