# V2C-C.1 review

PASS for this corrective patch only. Root cause reproduced before editing, both in isolated Mongo and on the authoritative live service. Five application files change only canonical authorization-loss classification and exact ownership cleanup. Existing logout policy, role boundaries and B1 CAS/claim lifecycle remain intact.

Twenty matrix/interleaving cases pass. Real Chromium public/private patron denial→valid-resolution flows and actual membership revocation are correlated with complete Mongo snapshots. Staff public/private search and suggestions work. Outsider API and UI deny access without observed private content. The repeated private capture corrects evidence-file routing; no application workaround was used. Disposable users494/495 are disabled, their memberships removed and private QA library archived. Normal Test User Global catalogue restored.

1803 disjoint backend tests and903 frontend tests pass; TypeScript/build pass. Inventory95 cases and catalogue staff/recommendation tests are included. Broad first tenant attempt exposed only immutable vocabulary test-copy plumbing; the complete suite was rerun successfully after correcting it. Model/index preservation uses SHA256 for smaller captured files and size/mtime for large files; this is not a new full9GB index integrity certification. Global health stays STALE/degraded, baseline_verified=false.

Timing is reported without a speedup claim. Denial gets fresh canonical proof and therefore costs more; ordinary Search p50 is118.869→120.833ms. Clarification resolution p50 rises122.848→147.186ms in the observed50-sample series; this difference is disclosed rather than attributed conclusively. Fresh revocation cleanup p50/p95 is16.582/24.938ms over30 repetitions. Initial timing-context accumulation exercised normal QA account capacity eviction; browser revocation used freshly recreated accepted scopes, and the timing script now cleans each iteration outside timing.

The540/530/54 draft population,320/110/110 split, original holdout manifest retain exact baseline hashes; the authoring source was not edited. AI-reviewed0; human-reviewed0. No C heldout evaluation, parser tuning, confidence calibration, optional LLM or Part2I. Original C finalQA remains PARTIAL. This is a primary-agent review; no additional independent reviewer was commissioned for C.1.

All18 requested C.1 gates pass on their scoped evidence. C security preflight may now be rerun separately; do not infer full V2C-C acceptance or resume benchmark work automatically.
