# Actual security boundary

AUDITED, read-only: host_audit.json and boundary.json. Mongo8.3.4 responds on loopback27017. getCmdLineOpts reports bindIp127.0.0.1 and authorization absent; configured connection has zero authenticated users and anonymous tenant _id read succeeds. That establishes absent database authorization for this local endpoint, not public internet exposure. No remote write/read probe was attempted.

Supplemental PID5548 lookup identifies Windows service MongoDB, Running/Auto, StartName NT AUTHORITY\NetworkService. Process owner retrieval remains NOT_VERIFIED and executable path unavailable through that provider. The generic listener inventory returned zero rows despite connectivity; absence of application process records does not prove those services are stopped. Service owner approval and deployment purpose remain unconfirmed.

Domain/Private/Public firewall profiles report enabled. Default action fields are raw0/NotConfigured; effective inherited policy, port-specific rules, router/NAT and remote reachability are NOT_VERIFIED. CURRENT_EXTERNAL_EXPOSURE UNKNOWN. No firewall mutation occurred.

Database path C:\Program Files\MongoDB\Server\8.3\data has NetworkService full control and inherited Builtin Users/application-package ReadAndExecute grants at the directory. This is directory-level evidence, not a recursive ACL/effective access audit of every data file. Review actual child file ACLs under approved owner control before migration. Backup location/retention/encryption/restore ownership NOT_VERIFIED; no production data export performed.

Application Mongo roles cover collections, not tenant rows. Infrastructure credentials remain trusted service secrets; users, tenants and Platform Admin still pass application JWT and current membership checks. Mongo authentication does not replace document filesystem/SQLite/DPAPI and code integrity boundaries. Actual security qualification remains incomplete.
