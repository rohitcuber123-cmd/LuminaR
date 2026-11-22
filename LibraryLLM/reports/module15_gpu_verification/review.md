# Module 15 GPU verification — PARTIAL

The project virtual environment loaded the existing local Qwen model on CUDA and generated a correct factual answer. The controlled regression runs passed 110 and 54 tests. These tests are not live authorization or grounding evaluations. See the JSON reports for evidence, limitations, and the existing dirty working tree.

Live Assistant, RAG, privacy, prompt injection, concurrency, knowledge tools and Chromium acceptance remain unverified. Existing MongoDB was not used; no disposable authenticated service environment was established. Production Mongo authentication and index integrity are not qualified. The initial probe used mock and full prompt logging disabled. The loaded model revision is identified; tokenizer commit metadata was absent.

The current qa.py has mixed line endings and its exact bytes satisfy the reviewed contract and project to the frozen hash after the enumerated source changes are reversed. Git normalization makes its blob equal HEAD; this does not by itself explain the historical snapshot hash difference. Historical five helper checks are separate from fresh results.

The loaded model reported 4-bit NF4 double quantization with float16 compute. A direct accepted-gateway probe classified a synthetic search and requested clarification for an ambiguous availability question; this did not exercise authenticated tools or the running API. See native_probe.json.
