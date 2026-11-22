# Protected approval proposal - NOT APPLIED

Current protected source hashes match the completed reproduction source. Eight prior Search/KG failure records are retained. No new protected edit is authorized.


Eight new controlled reproductions used the existing approved failpoint harness adapted only to the new task-owned Mongo/filesystem roots and run names. Worker termination checked a task/run/PID marker. No resident lock, pointer or generation was changed. All eight reproduce a failed invariant; those failures are retained separately from passing regression totals.

| Issue | Exact boundary and durable result | Root cause and affected function | Proposal and required safety checks |
|---|---|---|---|
| E-03, priority | Alter owned manifest library_id at SERIALIZATION_ACK after validation; Search and KG both become SUCCEEDED with the new active pointer, while reader status is RECOVERY_REQUIRED | `TenantIntelligence.run_one` validates the pending generation, then renames and accepts a fresh manifest digest before pointer CAS | Bind the pointer to the already validated digest; validate final identity/file set before CAS. Test library/generation/source/file corruption at rename, successful unchanged output, expired fences, changed authority/source and concurrent predecessor/successor. Preserve previous serving pointer on failure. |
| E-01 | Terminate after SUCCEEDED update before tagged lock release; success is durable and lock remains; explicit recovery after controlled expiry returns 409 on both targets | `run_one` has a success-to-release gap; `library_intelligence_service.recover` terminal/inactive tagged-job handling cannot reconcile it | Admit only exact tagged ownership plus validated terminal pointer/audit outcome; idempotent cleanup. Test active lease denial, unrelated token/holder denial, terminal published and unpublished cases, repeated/concurrent cleanup. |
| E-02 | Terminate after recovery changes target fence but before job fence; job remains PUBLISHING, mismatched fences and lock remain; retry returns 409 on both targets | `recover` performs two fence writes without a persisted resumable recovery intent | Persist exact old/next fence intent under tagged-lock CAS, replay both writes, verify completion before release. Test every interruption, concurrent recovery and former-worker late resume. |
| E-04 | Terminate inside generic barrier after insertion but before intelligence tag; QUEUED job and untagged lock remain; explicit recovery returns 503 on both targets | `library_intelligence_store.intelligence_barrier` tags after `institution_repository.library_mutation` inserts the durable lock | Include exact intelligence job ownership at insertion through a narrowly scoped reviewed API. Test before/after insertion, queued work and unrelated generic tenant mutations. Existing unknown/untagged locks must still block unsafe takeover. |

These are proposals, not applied patches. Required changes touch frozen worker/service/store and native-protocol contracts. Separate explicit approval is required for the exact reviewed patch and any narrowly necessary guard update. There is no blanket lock deletion, fence bypass or manifest rebaseline. Recovery must preserve exact authority and last-good evidence, quarantine uncertain candidates and leave unknown ownership blocked. E-03 demonstrates invalid-pointer publication followed by read-side refusal; it does not demonstrate cross-tenant content serving.


## Exact current source fingerprints

~~~json
{
  "search/library_intelligence.py": "ad5323f77b7686ab10c1c6defc081ceb7e26688d204ee8594c2e2fd04693f8d4",
  "backend/services/library_intelligence_service.py": "f90c4948ea7db781e143d100b7ad6d24e5a698b0c2a10c19c3c1e5c8989a7b01",
  "backend/services/library_intelligence_store.py": "54b5efbba8713ced652bdafa4aa055d05ffa25dfd046c9446580d6d8a22fb153",
  "backend/services/library_intelligence_artifacts.py": "79374d4a8a093ab02757f2465ed42b5455c32839bcad73c8eae01872b271c388",
  "tests/contracts/staff_boundary_v2o3.json": "6ad35f5603f185edd5d5665d2d624f906ebdc8c58fe5c5c306a3d8e7ec727588",
  "rag/qa.py": "4a1141649a4ce9b4bce6413627c27557f5817bb8718a4e842a4d12021bd89de3",
  "rag/llm.py": "d369e26fcbe458964bf642a057ca79212a63f48a6acf2b1c0a12590003f5cc1b"
}
~~~
