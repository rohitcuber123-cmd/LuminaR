# Browser repairs and verification

Rendered contrast failures were observed before changes. Opaque text backplates now keep cover lettering readable over rings/stripes, and cover brand/author text no longer loses contrast through opacity. Inactive subject links use the existing readable ink token; detail subject badges and the assistant subtitle use their full foreground colors. Saved state uses brand-dark over its tinted background. A global two-pixel focus outline covers keyboard targets outside component-specific selectors. Mobile chips, personal actions, disclosure controls, detail links, logo and library switcher meet the measured 44-pixel target height.

The repairs are confined to six shared product files: BookCover.tsx, CategoryExplorer.tsx, BookDetailView.tsx, AIChatWidget.tsx, index.css and styles/product.css. No new library CSS or separate catalogue/detail implementation was introduced. Source and CSS convergence remain as accepted. No backend, authority, stock, ranking, router or route logic was changed.

Evidence: the before-repair responsive/accessibility JSON snapshots are preserved. The final matrix has 96 passing geometry checks and zero reported rendered axe violations. Real Tab/Space/Enter/ArrowDown/Escape flows cover menus, Saved, AI select/deselect, category chips, pagination, book cards, carousels, mobile navigation, the Staff drawer and request confirmation/focus restoration. All six account-dialog sizes fit. Critical action hit-testing passed 96 measurements; mobile tested actions meet 44px. Nine computed contrast pairs range from 5.01:1 to 16.86:1. axe incomplete results remain disclosed; this is not an assertion of complete WCAG certification.

Review-harness repairs: a detached-element keyboard locator was replaced with a fresh locator, animations were awaited before axe, the computed RGBA sampler correctly composites painted backgrounds, and global category checks now wait for the actual filtered HTTP response and active chip before asserting. These changes fix timing/measurement, not product behavior. The existing frontend document-answer timeout passed unchanged on the full repeat; both attempts are retained.

Platform remains an explicit coverage gap. The user-supplied legacy Admin account signs in, but correctly receives Platform access required. No PlatformRoleAssignment exists; /platform/libraries is absent from the accepted route inventory. No role or membership was guessed or granted.

[Exact files and SHA256 evidence](full_product_browser_change_manifest.md).
