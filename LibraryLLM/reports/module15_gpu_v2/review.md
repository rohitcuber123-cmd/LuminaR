# Module 15 GPU verification V2 — FAIL (one observed routing failure; substantial coverage incomplete)

The historical archive is reconciled with the previous GPU evidence; see archive_inventory.json and cross_machine_matrix.json. The five CPU helper checks were synthetic, not model inference. Prior GPU direct model and gateway results remain separate.

A task-owned Mongo instance and synthetic identities supported real application login and HTTP Assistant requests through the existing handler with one resident CUDA Qwen. The isolated assembly used a controlled Global Search fixture and did not run the full normal service topology. The model and Assistant gateway shared the actual engine lock in that assembly. Search returned a synthetic catalogue item, missing authentication returned 401, and an ambiguous request returned clarification. A request to show the reading list was classified USER_LOANS: this is a live integration failure for that sample. The unsupported action produced clarification, while no independent state verification was performed. The document request did not reach the unavailable callback, so it does not verify that failure handling. See assistant_live_api.json and assistant_routing.json.

Document preparation and grounding, tenant privacy, injection, actual shared GPU contention, timeout recovery, knowledge workflows and browser acceptance remain untested. Production Mongo authentication and index integrity remain unqualified. A single routing result does not establish a population error rate.

Current qa.py satisfies the reviewed contract and projects to the frozen hash; mixed line endings do not fully explain the historical snapshot mismatch. No production source, model, router, or indexes were intentionally changed.
