# Router V4 HTTP contention audit

The per-request HTTP client was the dominant measured event-loop bottleneck. On this Windows host, constructing twenty AsyncClient objects took 7804.6 ms (median 388.4 ms each). Reusing the installed client removes this request-path TLS trust-store work.

The assistant now installs one bounded async connection pool before accepting traffic and closes it at shutdown. AssistantTools remains request-local, and ServiceTransport passes each bearer token explicitly on each call. Tests verify twenty concurrent tokens remain separate. No auth defaults were put on the shared client.

The event loop performs bounded context construction, IPC await and async tool calls. Encoder inference stays in one CPU child with two threads. RAG calls use the original thread-pool callback and inference lock. Qwen retains one nonblocking bounded slot, with a friendly busy message; accepted classifier traffic never enters it. ConversationStore already locks per conversation, not globally. Synchronous JWT validation runs through FastAPI's dependency thread pool. No extra RAG uvicorn worker or duplicate Search instance was launched.

The previous V3 coexistence server/HTTP p95 was around 8 seconds. Exact trace-linked V4 server timings, excluding client-side profile-file inspection:

document: 20/20 classifier accepts, Qwen calls 0, server p95 741.7 ms, gateway p95 665.8 ms.

book: 20/20 classifier accepts, Qwen calls 0, server p95 841.5 ms, gateway p95 739.1 ms.

Document and authorized book RAG both returned HTTP 200 with an answer. A second user was denied access to the disposable document (404), and the new document was deleted through its owning API. Existing RAG/Search/Recommendation/KG algorithms remain hash-identical.

Limits: CPU queue latency remains under load; the optional microbatch did not meet the preferred 500ms target. Search tools still use their existing GPU service. This fixes HTTP contention, not semantic routing quality or production capacity. V4 failed precision and remains opt-in. The shared client fix also benefits the unchanged default Qwen path.
