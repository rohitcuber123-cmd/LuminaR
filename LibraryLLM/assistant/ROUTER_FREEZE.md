# Production routing freeze

`ASSISTANT_ROUTER_MODE=existing_qwen` is the production router. A missing
variable uses that value. Invalid values (including empty strings) fail
startup with `ValueError: Unsupported ASSISTANT_ROUTER_MODE` before assistant
clients, gateways or workers are created. There is no artifact auto-detection.

`router_v3`, `router_v3_shadow`, `router_v4`, `router_v4_shadow` and `router_v5`
are **EXPERIMENTAL / NOT PRODUCTION APPROVED**. They are retained only for
archived reproducibility, imported only inside explicit mode branches.
Normal app installation ignores legacy `ASSISTANT_ROUTER_V2_VARIANT` and
`ASSISTANT_ROUTER_V2_RETRY` overrides. Direct archived scripts retain their
explicit V2 settings. No new router research is authorized by this freeze.

Normal startup does not scan/load experiment models, datasets or reports.
RAG's own existing retrieval/reranking and Qwen models remain resident; they
must not be mistaken for rejected assistant router models.

Assistant reading-list add/remove use the existing pending-action mechanism,
including for buttons inside the assistant. Ordinary Book Detail/reading-list
buttons continue to call the existing Core endpoints directly. Reading-list
editing remains enabled independently of the circulation-write feature flag;
borrow/return/reserve keep `ASSISTANT_MUTATING_ACTIONS_ENABLED` unchanged.
Clear still requires its dedicated explicit action. No extra confirmation
system, phrase grammar or generative model is introduced.
