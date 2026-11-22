# Private B: fourteen observed stages

1. **Authentication** — Real JWT/login/dependency path; per-request authentication-only time not separately captured.

2. **Current membership** — Repository authorization calls and timings recorded; repeated checks overlap prepared-stage timing.

3. **Document permission** — Authorized A/B metadata200; outsider/foreign/revoked paths denied; no private generation on denied security cases.

4. **Document retrieval** — Prepared artifact identity/checksum/generation/chunks observed; expected fact exists in processed chunks.

5. **Embedding lookup** — Actual MiniLM embedding duration in retriever timing_ms.

6. **FAISS candidates** — Actual selected-document native candidates and fact presence recorded.

7. **Chunk selection** — Definition/document selection before/after counts and fact presence recorded.

8. **Reranking** — Actual reranker result/timing_ms and selected fact presence recorded.

9. **Evidence selection** — Expected fact retained through context selection for all baseline A/B owner runs.

10. **Prompt construction** — Context/prompt character counts, hashes, fact-presence booleans and timing recorded; no token-limit loss observed.

11. **Qwen inference** — Actual generation duration and token counts in profile; no model substitution.

12. **Grounding verification** — Baseline A3/3 SUPPORTED; B3/3 NOT_SUPPORTED despite expected fact at validator input. Internal judge rationale not exposed.

13. **Citation validation** — Original page boundary unchanged; it did not cause B abstention. Unsupported document verdict drops sources earlier in protected qa.py.

14. **Final formatting** — Baseline B refusal follows the unsupported evidence gate. Final output hashes/verdict/source counts retained; formatting-only time not isolated.

Per-request observed timings/fact-presence fields: institution_v2q1d_private_stages.jsonl and institution_v2q1d_private_B_analysis.json. No unmeasured duration is presented as zero.
