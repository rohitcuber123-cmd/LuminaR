# Protected RAG source review

Status: REQUIRES_APPROVAL. The unchanged assistant guard still fails for `rag/qa.py`. This predates O and O.1. Original hash manifest and protected sources remain byte-identical to the O.1 starting checkpoint. Passing behavior does not authorize a protected source exception.

| Path | Expected SHA256 | Actual SHA256 | Asserted by existing guard |
|---|---|---|---|
| `rag/api.py` | `7EA791BACC9A59C14F0679C3738730801986193D213931829D46B9270C1EA1D6` | `2ED6D5C2FA1D9E989CCEAFE443F293E2F5362DB9BC804B46E8B8C6B8C514CD84` | no: existing explicit exclusion |
| `rag/llm.py` | `D369E26FCBE458964BF642A057CA79212A63F48A6ACF2B1C0A12590003F5CC1B` | `D369E26FCBE458964BF642A057CA79212A63F48A6ACF2B1C0A12590003F5CC1B` | yes |
| `rag/qa.py` | `0E78A7C780F691B14C8E3A3337F62054E4C117F0C2DF7828099D80DA90A793C6` | `4A1141649A4CE9B4BCE6413627C27557F5817BB8718A4E842A4D12021BD89DE3` | yes |
| `rag/retriever.py` | `4FA6208B8FAD104D2926F6CA9AC9DA8FE6966EC59CEEE5B1B169A9FE72DD2281` | `4FA6208B8FAD104D2926F6CA9AC9DA8FE6966EC59CEEE5B1B169A9FE72DD2281` | yes |
| `rag/reranker.py` | `E10DBE24EF1CE5F9083241D39B44246317DB62BA5859F9321B6F220FE1079CED` | `E10DBE24EF1CE5F9083241D39B44246317DB62BA5859F9321B6F220FE1079CED` | yes |
| `rag/services/document_service.py` | `56D1B680850B56E3286AD7D899247174ED2CDEF54443C3F630AE3C98E769B6C6` | `56D1B680850B56E3286AD7D899247174ED2CDEF54443C3F630AE3C98E769B6C6` | yes |

`rag/api.py` is already explicitly excluded by the existing test for the previously accepted secure transport change. O.1 adds no exclusion. The remaining four protected files match; only qa.py fails among asserted paths.

Relevant Git history:

- `822b667e092ba251537f0f3647348b7aa6ca641c|2026-10-27T12:48:42+05:30|updated search commit`
- `c449f5486f4f17e96dfdb64127e3dfe4b9b1ec87|2026-10-04T19:22:17+05:30|Initial commit`

Current raw qa.py has 39,923 bytes. Its LF-normalized content exactly matches the 38,793-byte HEAD Git blob; parsed ASTs are equal. The mixed line endings account for raw working-tree/Git differences, but do not by themselves explain the legacy hash. There is no current uncommitted semantic drift in qa.py.

The complete committed delta is in `institution_v2o1_qa_committed.diff`; `institution_v2o1_qa_worktree.diff` is empty. Added imports are valid_work_id and document_grounding helpers. The ask path identifies selected private document IDs distinct from work IDs, narrows document evidence with select_definition_evidence, uses document-specific definition category, and omits document citations after NOT_SUPPORTED. Catalogue retrieval/generation/prompt construction remain on the original paths. Exact reversal of these hunks, including the original CRLF on the citation loop, reconstructs the original frozen SHA `0E78A7C780F691B14C8E3A3337F62054E4C117F0C2DF7828099D80DA90A793C6`. The recovered bytes are a review artifact, never copied over protected code.

This establishes the specific committed source delta and its document-grounding intent. Commit message and matching behavioral fixtures do not prove human authorization of the protected-source change. The historical approval gap therefore remains open (Part H Case 2 candidate, approval unproven). No model, architecture, prompt, protected retriever, reranker or LLM source was changed in O.1.

Controlled validation covers source pages/chunk identity, unsupported evidence, exact selected-document ownership, cross-user and tenant isolation, missing-document/error cleanup, personal cache encryption/session isolation, original classifier/prompt contracts and assistant integration. See rag_behavior.json and independent full assistant/private-knowledge/institution groups. The broader inventory exposed a pre-existing themes shortcut bug in unprotected query_types.py; the narrow repair restores the existing validator without changing protected qa.py.

Candidate approval uses an exact reviewed-current-byte pin plus exact reverse projection to the original frozen bytes. Original hashes.json and all other protected assertions remain unchanged. Unknown byte changes, including whitespace, are rejected. This remains an approval-required contract exception; it is not resolution until explicitly authorized and applied/tested.
