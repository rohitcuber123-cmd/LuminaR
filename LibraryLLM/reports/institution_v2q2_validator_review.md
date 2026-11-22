# Part 2Q.2 exact protected validator review

Approval is absent. Neither protected source nor frozen contracts are changed.

Reviewed patch SHA-256: `53a4bbd40eb950622b28a7e5b2b2c0daf9390d1f9dc5d16c5de3ed5031a31c92`.
Original `rag/llm.py`: `d369e26fcbe458964bf642a057ca79212a63f48a6acf2b1c0a12590003f5cc1b`.
Exact candidate bytes: `a3b141dd175474d941102bb18e75ae15eacd1fd3ad82e2630be2baab08a30940`.
The existing proposal artifact remains byte-for-byte intact. Candidate compilation is confined to the owned process; it does not write application source.

## Model and inputs

`LuminaRLLM.validate_evidence` uses the existing Qwen/Qwen2.5-3B-Instruct resident model and existing constrained decoding. ValidatorSchema exposes only `supported: bool` and confidence in [0,1]; no explanation, entity-match or field-match field exists. Confidence is recorded but does not introduce an acceptance threshold. A parsed truthy supported value produces SUPPORTED. Invalid JSON produces NOT_SUPPORTED. Empty evidence returns NOT_SUPPORTED before inference. The production MOCK_MODE branch is distinguished from genuine Qwen experiments.

The claim-centric prompt includes the question, stringified structured intent and evidence text. IntentSchema has intent, actor, action, target, polarity, temporal_relation, question_focus and confidence. The model performs semantic matching; there is no deterministic entity or field equality test inside this method. The matched validator-only matrix uses an explicit schema-valid authored intent held identical across variants. The full private-PDF pipeline separately invokes actual Qwen intent analysis.

`top-3-comb` concatenates up to three chunk text fields. Other modes use the first chunk (top-3-ind requires caller iteration). Chunk document/library IDs and page metadata are not included in this validator prompt. Positive/negative evidence and conflicting values have no separate typed channels: they are ordinary text plus negation/condition rules. An absent field is not encoded as a sentinel; it is simply missing from evidence. Entity ambiguity, unrelated homonyms, provenance confusion, chronology and source instructions therefore require adversarial testing, rather than assuming two additional prompt lines establish safety.

The candidate adds two instructions only in the claim-centric branch. The separate informational-category prompt accepts relevant or partially answering passages and is unchanged. Private document classification/evidence selection and fast accept/reject logic in `rag/qa.py` determine whether validation is invoked; a direct method experiment is not a measurement of the whole pipeline.

## Verdict consumption and authorization

`rag/qa.py` builds an explicit limitation/refusal prompt on NOT_SUPPORTED and suppresses document sources. SUPPORTED follows the ordinary grounded answer-generation prompt. The boolean schema cannot itself produce PARTIALLY_SUPPORTED although the caller retains a historical branch for that verdict. Acceptance is evidence gating, not proof that final generation is correct.

Private authorization lives before and after inference in `LibraryAssetPipeline`: authorize current member/document; verify manifest, checksum, generation and each chunk's library/asset/document identity; load only the authorized document FAISS artifact; recheck membership/generation before and after engine.ask; reject sources outside the authorized chunk set; clear document runtime in finally. Those mechanisms remain unchanged. Model text must never replace these checks. Matrix categories19/20 deliberately label wrong-library/inaccessible evidence in text; actual HTTP denial evidence is separate.

## Contract impact requiring separate exact approval

`tests/test_assistant_backend.py` freezes the original hash-manifest bytes and full llm.py fingerprint. Its existing exact historical projection covers qa.py only. `tests/test_document_rag_latency.py::test_document_auth_retrieval_validation_verdict_and_sources_code_preserved` independently compares llm.py against the document-latency manifest. Neither original manifest may be broadly rebaselined. A future approved contract revision would need to admit only the exact reviewed llm.py bytes, verify a byte-exact reverse projection to the frozen original, retain arbitrary-third-version rejection, and add negative mutations for entity/field/negation/conflict/provenance and helper tampering. No such contract change is authorized or applied here. Prior Part2O.3 approval does not cover this new source.

## Current review decision

The expanded matched experiment has already exposed candidate false-positive acceptances. The patch is retained for review/history, not recommended for application on the strength of six successful positive questions. Final per-case evidence and aggregate results are in `institution_v2q2_validator_matrix.json` and the completion report. No failing model run is discarded or converted into a passing software regression.

## Patch formatting checks

The original SHA-verified patch uses CRLF context and fails plain `git apply --check` against the LF source. That exact error is retained in `institution_v2q2_patch_checks.json`. The original artifact is unchanged. A separate LF review-format copy, `institution_v2q2_protected_validator_proposal_lf.patch`, passes check-only application and has SHA-256 `ea745e68ab582b252ee9e358a6bb1fbfbf7f75f0f6f57babdc0ed37b9854904f`. Its source delta is identical, and the in-memory candidate source still verifies to `a3b141dd175474d941102bb18e75ae15eacd1fd3ad82e2630be2baab08a30940`. This is a formatting artifact for review, not a source/hash exception or approval. Neither patch is applied or recommended.
