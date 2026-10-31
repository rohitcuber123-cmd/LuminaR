# Exact RAG exception retained

Status: AWAITING_APPROVAL. Final patch SHA `76c09bfef7e676595e0af6974e55aa232e63c684ec51961c558eabf97e45431b` is unchanged from O.2. Original hashes.json, protected rag/qa.py, Qwen, retrieval/ranking and Assistant routing are untouched.

Allowed qa.py raw SHA256 values only:

- LEGACY_SHA256: 0e78a7c780f691b14c8e3a3337f62054e4c117f0c2df7828099d80da90a793c6
- REVIEWED_SHA256: 4a1141649a4ce9b4bce6413627c27557f5817bb8718a4e842a4d12021bd89de3

The exact reverse projection to the original frozen bytes is retained. The unchanged original manifest is pinned by the proposal. Unknown bytes, whitespace/newline-only variants, changed prompts/retrieval/citations/grounding/identity, modified helpers/manifests and other protected source changes fail. Both exact positive versions and all eleven RAG negative cases passed again in O.3 candidate fixtures.

Actual original RAG guard still fails against the historic source delta. Passing candidate tests do not authorize it. Prior semantic grounding/ownership evidence is preserved in institution_v2o2_rag_source_review.md and institution_v2o2_rag_grounding_tests.json; that focused run had 273 grounding checks plus 183 asset-security and 3 lexical checks passing. It was not rerun or represented as fresh O.3 semantic validation. After explicit approval, run the original assertion first, then the full requested grounding/security/regression sequence without suppressing failures.
