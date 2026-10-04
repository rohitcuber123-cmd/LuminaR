# Show connection follow-up

Added a Show connection button immediately below every shared Why related component, covering product More Like This and assistant KG cards. Each button toggles its own inline SVG connection map: starting book → every verified shared feature → the specified related book. The map uses existing reason paths; no new fetch, Qwen, score, candidate union or selection-tray mutation. Hide connection collapses it. An optional link opens the related book as the Graph Lab seed.

Both book titles are shown in full in the caption; compact SVG labels have full title/description alternatives. Unknown relation kinds have a neutral fallback. Empty paths produce an explicit unavailable message. Buttons expose independent aria-expanded and stable aria-controls targets.

Verified on the authenticated Rich Dad, Poor Dad page: opening the Rich Dad, Poor Dad 2 card shows exactly one graph, two author features and five subject features, while the other nine buttons remain closed and selection remains false. At 375×812 CSS pixels, page scroll width is 375 and graph width is 268.54: no horizontal overflow. Temporary viewport override reset.

Validation: 100 focused product/assistant tests passed (20 product including three connection cases, 80 assistant), production build passed, lint exits zero with the same 19 existing warnings. Logs: kg_show_connection_tests.log, kg_show_connection_build.log, kg_show_connection_lint.log. No backend or graph artifact changes.

![Connection graph](D:/SDC/LibraryLLM/reports/kg_show_connection_preview.jpg)
