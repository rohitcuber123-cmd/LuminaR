# Assistant layout cleanup

The existing assistant now uses a 520px desktop panel, up to 800px tall, positioned 24px from the bottom. Header is compact. A collapsed Quick actions menu replaces four permanent shortcut buttons. Selected books use one compact action row and horizontally scrollable title chips; duplicate recommendation controls are removed. The message composer is shorter, with inline Send and accessible keyboard/length help. New responses scroll to the start of their results instead of the end.

Book cards emphasize readable mixed-case titles and authors, rating and availability. Primary actions use compact Select / View / Similar labels and an overflow icon. Full action names remain accessible. Subjects and secondary actions are in the overflow. Existing selection, recommendation, reading-list, confirmation and KG connection behavior is preserved; no backend/scoring/model changes.

Measured with the actual components on an isolated development fixture: desktop conversation area 556.18px of 800px (69.5%); phone 536.68px of 780.50px (68.8%). Phone CSS viewport 375×812, scroll width 375: no horizontal overflow. Fixture uses sample books and no service calls, on a separate origin/port so real account storage is untouched. Temporary preview tab/server closed and viewport reset after captures.

Validation: 106 product, assistant and independent contract checks passed; production build passed; lint exits zero with the same 19 existing warnings. Tests now explicitly expect one selection recommendation action and open the collapsed shortcut menu before invoking its actions. No assertions on sent actions, selected IDs, metadata, confirmations or accessibility were removed.

Evidence: assistant_layout_tests.log, assistant_layout_build.log, assistant_layout_lint.log, assistant_layout_preview.jpg, assistant_layout_mobile.jpg. The normal frontend on port 5173 and assistant on port 8005 remain running.
