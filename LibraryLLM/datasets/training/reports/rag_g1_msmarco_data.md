# G1 MS MARCO data preparation

This is an isolated, experimental retrieval pilot. LuminaR evaluation labels remain DRAFT.

- Source: `sentence-transformers/msmarco-co-condenser-margin-mse-sym-mnrl-mean-v1`, `triplet` configuration, revision `84ed2d35626f617d890bd493b4d6db69a741e0e2`.
- The publisher's `triplet` configuration uses the most query-similar mined passage as a hard negative for each query-positive pair. The more densely repeated `triplet-hard` configuration was inspected first, but its first 50,000 shuffled streamed rows had only 2,054 distinct queries and 1,585 train/validation query overlaps. Those probe artifacts are isolated in `datasets/training/generic/msmarco_g1_triplet_hard_probe/` and were not used for training.
- Hugging Face streaming was performed automatically. No full collection was downloaded. The selected stream was shuffled with seed 42 and buffer size 10,000; 50,000 accepted rows were then shuffled again with seed 42 and split 45,000/5,000. Because this uses a bounded stream, it is not a globally uniform random sample of the full MS MARCO collection.
- Required text columns: `query`, `positive`, `negative`. All selected fields are nonempty, positive and negative differ, and text length bounds are enforced.
- Raw rows inspected: 68,822. Rejected because positive text equalled negative text: 18,822. Selected: 50,000.
- Exact duplicate triplets: 0. Duplicate queries: 0. Duplicate positives: 301. Query overlap between train and validation: 0.
- Under the unchanged MiniLM tokenizer, query lengths are median 9, p95 14, max 70 tokens; positive lengths median 73, p95 146, max 326; negative lengths median 67, p95 130, max 275. Respectively 0, 11, and 2 examples exceed the fixed 256-token model window and will be truncated during training.
- Train Parquet SHA-256: `7fb3fc0802a11efc3cf4b54be71509d36bbea3fc6bf3aa258c16d98ad22b6c16`.
- Validation Parquet SHA-256: `7e34e6325b220155d970192d63d902a8a1d67770f6ef8b4efb77260f2cd7d4a3`.
- Full machine-readable manifest: `datasets/training/generic/msmarco_g1/manifest.json`.

The installed `sentence-transformers` version is 5.6.0. Its `MultipleNegativesRankingLoss` accepts an ordered list of anchor, positive, and explicit negative features; it concatenates positive and negative document embeddings into the candidate matrix. The focused test confirms the trainer retains `negative_input_ids`, supplies three feature groups to the loss, and changing the negative changes the computed loss.
