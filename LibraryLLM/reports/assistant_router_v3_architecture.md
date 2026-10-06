# LuminaR Router V3 experiment

The larger generative-router direction is rejected because a router that
shares the GPU inference lock competes with RAG and explanations. A bigger
model may improve classification but does not solve admission, serialization,
VRAM pressure or multi-user latency. V3 introduces no new generative model.

`ASSISTANT_ROUTER_MODE` defaults to `existing_qwen`. `router_v3` and
`router_v3_shadow` are explicit experiments. Existing V2 evidence and frozen
116/121 test sets remain preserved. No automatic promotion occurs.

An isolated CPU process loads the existing cached `all-MiniLM-L6-v2` once,
freezes all its parameters, and uses two CPU threads. The Search and RAG
encoder instances run on CUDA and are not borrowed or reconfigured. The CPU
worker does not use Search HTTP, Qwen, the RAG inference lock or CUDA.

Each request supplies its current message (maximum 4,000 characters; encoder
maximum 256 tokens) plus 24 bounded context features. Features describe the
tray count, page, previous comparison/recommendations, active result type,
document/book RAG context, pending action, authentication, awaiting criteria,
selection change, cardinality, focus and available structural source. Titles,
authors, descriptions, IDs and private chunks are not embedded or forwarded
to the worker. The worker returns labels, probabilities, margin, entropy and
centroid similarity; it cannot return a work ID.

Six small heads predict family, subtype, reference source, position, catalogue
field and criterion presence. TRAIN fits nearest-centroid, balanced linear
and one-hidden-layer MLP64 baselines. DEV chooses each head, temperature and
class-specific confidence/margin thresholds. Independent family/subtype
agreement and a DEV-selected centroid-distance OOD gate are retained. A
family-constrained subtype alternative is measured separately. Calibration
uses finite synthetic DEV support and cannot guarantee production precision.

The server checks source availability and cardinality and binds positions
against request-local canonical identities. Current selection takes precedence
over stale comparison/page state. Empty active results remain authoritative.
An impossible source, ordinal, field or cardinality falls back. Account routes
ignore book selections. An accepted Search passes the current user message
directly to the unchanged Search adapter, subject to its existing 2,000-character
query contract. Accepted catalogue/account/comparison/recommendation/KG routes
use the existing structured executor with zero Qwen routing or prose calls.

Free-form preference criteria require the existing compact Qwen router.
Explicit entity extraction requires both a calibrated EXPLICIT source and
literal title grounding before catalogue resolution is allowed. Contextual
pronouns cannot become catalogue search strings. All mutation types always
fall back, even above the stricter DEV precision target, and retain existing
pending-action confirmation and authorization. Content and ambiguous RAG
requests fall back to the existing routing and access-control path. No V2
retry is used; fallback makes at most one Qwen routing call.

The queue bounds total in-flight work at 64, including cancelled work awaiting
its reply. A dedicated reply thread associates opaque tickets with futures.
One encoder serializes inference. Shutdown fails pending futures and stops the
worker. Queue overflow or timeout enters the existing bounded fallback/busy
handling. Optional micro-batching is benchmarked at batch size eight and a
five-millisecond collection delay; the default remains batch size one.

Shadow mode returns the existing Qwen decision and performs no duplicate tool
calls. Opt-in development telemetry records only component labels, confidence,
threshold-related policy, numeric timing, acceptance/fallback and agreement.
It does not persist user messages, book IDs, private documents or account data.
Frozen synthetic evaluation scripts may record their synthetic requests.

Artifacts are versioned in `assistant/models/router_v3`. The manifest names
the encoder, dataset digest, dimensions, feature contract, architecture,
label sets, thresholds and evaluation version. Torch files contain tensors
only and load with `weights_only=True`; digests and shapes are checked.
Training is an explicit offline command and never runs at service startup.

The experiment leaves Search, recommendation, KG, RAG, Know More, admin,
notifications, circulation, HTTP schemas and frontend source unchanged.
CPU inference benchmarks distinguish worker latency from authenticated
end-to-end HTTP/tool latency. The existing Qwen gateway rejects simultaneous
inference as busy; that limitation is reported rather than hidden as a queue.
