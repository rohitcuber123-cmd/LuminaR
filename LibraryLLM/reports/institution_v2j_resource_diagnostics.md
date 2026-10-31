# Resource diagnostics

The worker stores an opaque boot worker_id, not an OS PID or a trustworthy hardware identity. Existing infrastructure supplies no safe PID map, CPU/RAM sampler or GPU allocation record. Worker CPU utilization, process memory and GPU memory therefore return NOT_AVAILABLE. The diagnostic process's own memory is not mislabeled as the worker's.

For an existing validated local tenant root, shutil.disk_usage supplies an actual local-volume total/free byte observation. Missing/unreadable root yields NOT_AVAILABLE. The root path is not output. This is a read-only observation, not a build admission/reservation or retained-generation accounting guarantee. Bounded known artifact file sizes are reported separately from volume capacity. No GPU monitoring, resource daemon, worker telemetry, admission policy, new index or scheduler is introduced.

Performance fixtures measure diagnostic-process CPU/tracemalloc peaks and DB work; those are implementation benchmark costs, not production worker resource measurements. They are labelled as such in the performance report. No hardware/latency SLO is invented.
