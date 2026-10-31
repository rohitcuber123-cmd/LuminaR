# Operator authorization and deployment boundary

Inspection found no infrastructure-operator application identity. `backend/platform_dependencies.py` grants installation Platform authority, not tenant authority or infrastructure access. `scripts/library_intelligence_cli.py` uses ordinary tenant JWTs for existing build/reconciliation/recovery routes; it is not suitable as a stronger operator boundary. `reconcile_inventory_v2a.py` is an administrative local script but assumes environment DB access, not an independently authenticated diagnostic operator. Neither is silently promoted.

The new surface is a local command, not a remotely reachable endpoint. `connect_operator` requires an explicit `LUMINAR_OPERATOR_MONGO_URI` (or explicitly named secret environment variable). It never falls back to MONGO_URI or .env. URI must use mongodb://, one loopback endpoint, explicit username/password, matching database/authSource and SCRAM-SHA-1/256. The authenticated server response must contain exactly one database-local user with only built-in `read` role on that same database. Anonymous, remote/SRV, mismatched database, app tokens and write/admin roles are rejected. Each invocation authenticates afresh. Output never contains URI, password, principal username, raw exceptions or credential-bearing arguments.

This is Mongo infrastructure authorization, not a new application/global superuser role. A person with a Platform role or tenant ADMIN role gets no access without a separately provisioned infrastructure credential. Conversely, the diagnostic credential does not mint an app token, change membership, or grant a build/recovery action. Trusted operator access intentionally includes database queue context across tenant UUIDs; jobs/artifacts requested for a library remain scoped.

Deployment prerequisites: operator-managed Mongo authorization enabled, loopback isolation, OS protection of credentials and code/artifact roots, separately approved database-local read account and credential rotation/revocation. The built-in read role is database-wide; the command itself restricts queries to four collections. It is not a per-tenant Mongo credential. An unauthenticated or compromised Mongo server cannot supply a meaningful authorization boundary; do not deploy this tool on such a setup as a security substitute. The command does not weaken or repair the existing database deployment.

No production operator account or secret was created/configured. At task time the operator URI was absent, so production command use fails closed. Authentication and server-enforced denial of writes were actually tested on separate task-owned mongod instances launched with --auth, using independently provisioned fixture read accounts. No existing Mongo service/configuration/user/role was changed. Production authorization deployment is unqualified until an operator provisions and reviews it.

## Usage

From the project root, with a valid secret environment variable already supplied by the approved operator secret mechanism:

```powershell
.venv\Scripts\python.exe scripts/diagnose_library_intelligence.py --library-id <canonical-library-uuid> --format text
.venv\Scripts\python.exe scripts/diagnose_library_intelligence.py --library-id <canonical-library-uuid> --job-id <canonical-job-uuid> --format json
.venv\Scripts\python.exe scripts/diagnose_library_intelligence.py --library-id <canonical-library-uuid> --state FAILED --limit 10 --format json
.venv\Scripts\python.exe scripts/diagnose_library_intelligence.py --library-id <canonical-library-uuid> --verify-checksums --checksum-budget-mib 16 --format json
```

Never put a URI/password on the command line or in a report. The command has no credential-provisioning, grant, recovery, cancellation or write mode. --database/--uri-env exist for explicit deployment/fixture binding, not privilege elevation. Default artifact root is the existing tenant root; --artifact-root cannot point to known global infrastructure or an escaping/reparsed namespace.
