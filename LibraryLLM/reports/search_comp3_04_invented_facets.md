# Inherited facet fallback investigation

Legacy _parse_legacy could promote the noun left after extracting other fields to a category. Global vocabulary made the grammatical noun Records a hard facet. [ownership.py](D:/SDC/LibraryLLM/scratch/search_compositional_recovery_v3/ownership.py) now requires proof from a supported explicit subject owner, a complete scoped category expression, established category-first bibliographic/topical grammar, or supported postfix category syntax. The same rule applies to every category, including aliases; no Records-specific exception exists. Unsupported inherited proposals are removed and recorded in query_ir.rejected_unowned_facets.

Development tests pair ordinary prose with explicit category ownership for Records, Maps, History and Physics. The initial ownership attempt was too restrictive and lost historical category-first positives; all failed test reports remain. The final rule preserves the broad inherited regression suite. General natural-language meaning still needs fresh validation.

**Fresh acceptance finding:** Fresh limitation: the positive fallback proof does not govern all negative facet proposals. Five exclude books by cases invent an excluded Books category. Every final hard field still needs the same typed ownership proof; this fix is PARTIAL.
