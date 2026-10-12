# Durability and operator recovery

1. Existing domain guards serialize the canonical library command.
2. Existing Part 2B/2C logic constructs absolute effects and immutable audit events.
3. The journal appends deterministic notification intents to that same plan before
   the durable operation record is written.
4. The accepted effect/recovery machinery persists canonical effects, audit and
   outbox rows, then marks the operation COMMITTED.
5. The bounded worker checks COMMITTED and fresh recipient authority, upserts the
   inbox under its durable unique dedupe key, then acknowledges the outbox row.

An interrupted prepared operation cannot dispatch. Replay preserves the same
outbox identities. A failure before inbox persistence retries; a failure after
inbox persistence also retries but cannot duplicate that notice. Delivery failure
never changes an already successful domain receipt or stock/loan/queue/fee result.
Suppressed recipients are explicit history in the outbox and are not delivered to
new unrelated members. Existing delivered account history is preserved.

Worker failures store bounded secret-free codes, attempts and backoff. Scans cap
at 100 by default (explicit drain caps at 500). Uncommitted rows defer 30 seconds;
failed rows back off up to one hour. A shutdown joins the worker for at most five
seconds. Do not clear a retained domain mutation gate automatically: reconcile
the interrupted operation through the existing recovery workflow first.

Local operator tools:

```
.venv\Scripts\python.exe scripts/notification_outbox_v2d.py
.venv\Scripts\python.exe scripts/notification_outbox_v2d.py --drain --limit 100
```

The production substrate is standalone Mongo. Journal acknowledgements and the
accepted immutable-plan replay mechanism are used; no replica-set transaction,
exactly-once external delivery, automatic interrupted-domain rollback or external
email/push guarantee is claimed. Tests inject prepared origins, failed delivery
and an inbox write followed by lost acknowledgement. All 45 Part 2D tests passed.
