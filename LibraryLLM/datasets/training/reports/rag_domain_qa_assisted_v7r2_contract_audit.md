# V7R2 source presentation and unit contract

V7R0 and V7R1 are frozen; hashes are in the JSON audit. The exact same 50 TRAIN passages are used.
50 presentation views round-trip; 331 deterministic units passed authoritative offset and source-hash checks.
Long unsplit units: 0.
Presentation normalization collapses whitespace and applies NFKC with a per-character source map. Source text and the training positive are unchanged.
Each source unit has stable S-IDs and exact authoritative/presentation spans. Evidence may reference one or two adjacent units.
TEST leakage 0; accepted evaluation-span leakage 0.
