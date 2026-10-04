# LuminaR RAG bi-encoder training workspace

The directories `hf_cache`, `raw`, `processed`, `luminar`, `models`,
`checkpoints`, `manifests`, `evaluation_indexes`, and `reports` contain only
isolated training and evaluation artifacts.

Training is gated by `reports/rag_embedding_truncation_audit.md`: the active
256-token model truncates 3,958/3,959 current RAG chunks, and 33/55 draft
accepted spans are entirely invisible in every matching indexed chunk.
Fine-tuning on the current long-chunk index would not make that evidence
available to the retriever. Production RAG chunks and indexes remain unchanged.

The isolated `datasets/rag_experiments/chunking_v1/tokens_220` variant now
provides 16,895 passages that fit the model window. Its corpus/label hashes
and unchanged-MiniLM baseline were reproduced before the generic pilot.
The 2026-09-27 generic pilot used 2,000 streamed Natural Questions and 1,000
SQuAD pairs. Its model and FAISS index live under this training workspace.
See `reports/minilm_generic_pilot_dev_v1.json` for exploratory DEV results.
All evaluation labels are DRAFT, and no model has been deployed.

Scaled B/C/D training is gated by source-grounded LuminaR domain questions,
verified hard negatives, and a clean quality/decontamination audit. The
20-passage domain-generation probe did not yield reliable verified QA pairs;
`reports/domain_qa_generation_probe_v1.json` records the evidence. Do not
use those generated questions as training data.

Reproduce the audit from the project root:

```powershell
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe scripts\audit_rag_embedding_lengths.py
.\.venv\Scripts\python.exe -m pytest tests\test_rag_embedding_truncation_audit.py -q
```

When training becomes justified, set the Hugging Face cache explicitly to
`D:\SDC\LibraryLLM\datasets\training\hf_cache` and use streaming for the
first Natural Questions pilot. Keep transformed datasets, checkpoints, and
evaluation indexes here, away from the production RAG index.
