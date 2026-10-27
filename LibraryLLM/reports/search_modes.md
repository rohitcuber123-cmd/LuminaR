# Search modes

| Mode | Interpretation | Provider |
|---|---|---|
| Smart (default) | Recognized facets, numeric bounds, format, availability, author, exact ISBN/work ID and semantic remainder | Shared structured lookup or existing semantic provider |
| Genre / Subject | Canonical facet exact, controlled alias, bounded typo | Strict canonical subject lookup; title-only matches rejected |
| Title / Author | Lexical title/author containment; existing global sidecar typo correction | No unrelated vector matches |
| Exact | Normalized full title, work ID; tenant UUID, accession, ISBN and call number | Deterministic canonical predicate |

The existing themed combobox appears in catalogue inputs and Header search. Header routes retain Global, patron or staff context and transmit the selected mode. Inventory has not acquired these discovery controls. Existing New Arrivals and Popular routes retain their providers when no discovery query/filter is submitted.
