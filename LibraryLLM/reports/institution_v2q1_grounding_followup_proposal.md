# Part 2Q.1 protected RAG follow-up proposal

Status: proposal only; no protected source or hash exception changed.

Observed evidence:

- RAG013 returned an abstaining answer with `SUPPORTED`; RAG001 previously showed the same output mismatch. The current verdict is an evidence-stage verdict, so a repair must define final-answer consistency without silently changing that existing meaning.
- RAG027 returned `Page 15` with `SUPPORTED`, while all four response sources and matching public chunk records have null page metadata. No reliable page number was established.
- RAG019 may combine a first-journey question with later speculative events; independent source adjudication is still needed.

Proposed narrowly scoped review:

1. Specify how final abstention is represented alongside the existing evidence verdict. Preserve the current API schema unless a separate contract change is explicitly reviewed.
2. Prevent unsupported pagination/citation claims when the selected sources have no pagination evidence. Do not infer page numbers from chunk positions or model memory.
3. Add source-based negative tests for absent page metadata, contradictory/abstaining generation, and mixed-event retrieval. Include supported answers and genuine page metadata as positive controls to avoid blanket abstention.
4. Re-run recorded public cases with the same corpus/model settings, then the original grounding, private-data and frozen-contract suites. Retain failures and independently review citation correctness.

Constraints: no Qwen replacement, architecture change, new model, retrieval/ranking redesign, global rebuild, private-data exposure or automatic frozen-hash rebaseline. Retain original manifests and exact historical exceptions. This proposal requires a separately reviewed implementation patch and explicit authorization before changing the protected source. No such change is applied by Part 2Q.1.

Current protected `rag/qa.py` SHA-256: `4a1141649a4ce9b4bce6413627c27557f5817bb8718a4e842a4d12021bd89de3`.
