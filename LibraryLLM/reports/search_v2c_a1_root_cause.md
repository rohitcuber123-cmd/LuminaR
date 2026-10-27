# V2C-A.1 root cause — 15 October 2026 addendum

The pre-patch command reproduced7passed/1failed. A fresh authorized Global vocabulary and the accepted snapshot both contain Romance. Source normalization preserves `include romance but exclude romance` and original offsets.

The existing exclusion recognizer first adds `exclude romance` at20..35. The inclusion regex only recognizes an `and` boundary or end-of-input, so its next match is0..35 with operand `romance but exclude romance`. Source.free rejects that overlap. No inclusion candidate reaches composition. Canonical exclusion resolves to Romance; the remaining text `include romance but` is passed to the legacy facet/topic grammar and becomes semantic text. The final subject-intersection validator is correct but receives no included subject.

The fix bounds clauses before overlap resolution in query_constraints.subject_clauses. Canonical operands and aliases are resolved through the supplied scoped dictionary; each included/excluded operand has a distinct original span. Candidate precedence still protects quotes, identifiers and previously consumed rating/year/format spans. Conjunctions are consumed only in grammatical gaps between recognized spans. Multiple included subjects retain existing ALL semantics; explicit include-OR is unsupported. Unknown explicit inclusion is unsupported; meaningful noncanonical exclusions remain text exclusions. Incomplete clauses do not execute.

query_repair.compose merges canonical subject/excluded_subject candidates and preserves genuine topic suffixes. query_confidence.validate still checks the final normalized subject intersection, now attaching internal source spans. Public messages retain the safe existing contract. Parser version advances to search-v2c-a1-compositional-1 to avoid idempotent replay of the old nonempty parse.

A live query with two included subjects exposed the existing first-subject-only metadata shortcut: Fiction was too common, so the query timed out on the old structured fallback. query_execution now picks the rarest included subject for the same bounded indexed projection, retains all authoritative predicates, and refuses broad-scan fallback for this new multi-subject path. No HNSW/KG artifact, model, index or ranking algorithm is replaced.

See baseline.trace for observed normalization, candidate stages, rejected overlap and remainder. Exact source hashes are in baseline/changed_files; final candidates and decisions are in clause_recognition/contradictions/leftover_validation. Historical V2C-A reports are unchanged.
