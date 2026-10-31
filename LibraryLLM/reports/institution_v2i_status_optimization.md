# Optimization decision

Implement only reuse of the verified target observation within a single `control_status` invocation. A private `_target_observation` returns `(existing_status, observed_pointer, verified)`. `target_status` retains its established dictionary contract; Staff presentation uses the same observed pointer and verification result instead of fetching/verifying again. There is no cache lifetime, shared map, tenant key ambiguity, extra lock, background thread or authorization reuse.

Correctness boundary: each request still fully hashes current source and each active immutable generation, queries current jobs, derives expired-lease recovery and checks current membership. One verified generation is presented with the row that named it. Last-good verification stays separate from latest-attempt status. Corruption before the next request is detected on that request. As previously, external filesystem tampering immediately after a checksum observation is outside a point-in-time READY guarantee; redundant same-request checks did not provide a durable integrity lease.

Rejected candidates: dataset sequence is not a mutation revision; counters/dirty markers lack complete mutation coverage including global enrichment and journal replay; TTL snapshots can mask metadata/job/authority changes; stat-only immutable metadata caches would miss same-size corruption; separating verification would weaken current READY semantics; coalescing under the existing readability/barrier behavior needs a new race/linearization proof and must still recheck each caller. No cross-request cache or coalescer is added. No frontend polling changes are needed for this backend-only optimization.

Use `institution_v2i_freshness_benchmark.json` for paired identical-fixture results, not the preliminary smoke run. Exact reductions in checksum work and target reads are distinguished from noisy wall-clock latency. Both the baseline and candidate are executed in one process against the same fixture state, with order alternated by size. First reads are reported separately and are not cold-disk claims. The archived original source hash is preserved in the frozen baseline. The focused checksum-call test demonstrably fails before the change and passes after it.

## Executed paired measurements

| Eligible books | Before median ms | After median ms | Before p95 ms | After p95 ms | Checksum bytes before / after |
|---:|---:|---:|---:|---:|---:|
| 0 | 23.339 | 20.103 | 41.197 | 21.401 | 0 / 0 |
| 1 | 78.429 | 50.409 | 88.137 | 54.179 | 11,964 / 5,982 |
| 10 | 78.196 | 53.144 | 89.863 | 61.832 | 95,650 / 47,825 |
| 100 | 88.079 | 64.154 | 100.105 | 73.781 | 933,014 / 466,507 |
| 1,000 | 152.611 | 110.518 | 186.361 | 123.076 | 9,312,018 / 4,656,009 |
| 10,000 | 796.993 | 725.935 | 837.629 | 758.495 | 93,156,022 / 46,578,011 |
| 50,000 | 3969.336 | 3490.119 | 4564.188 | 3562.193 | 466,036,022 / 233,018,011 |

Populated checksum reads 14 → 7; Mongo commands decrease by two at every size. Full catalogue count/projection/normalization/fingerprint is unchanged. Timings are local development samples; no SLO/cold-disk or model-load status latency claim. Raw CPU, memory, first-read, p90, DB documents/bytes and profile details are in the JSON.

## Fresh application-process measurements

Three new Python processes per size/version also measure the first status call at all seven sizes, with total startup/import wall time separate. The OS/Mongo caches are not flushed. These are application-cold, not cold-disk/server measurements. Raw samples and percentiles are in `institution_v2i_cold_process.json`.
