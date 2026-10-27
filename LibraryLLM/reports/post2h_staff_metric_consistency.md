# Staff metric definitions

Every endpoint requires current exact Staff membership. Overview and Analytics read canonical tenant UUIDs; neither uses legacy/global business rows.

| Metric | Overview source / definition | Analytics source / definition | Current TEST |
|---|---|---|---|
| Local books | staff catalogue source: ACTIVE records with a valid title, including online-only | ACTIVE LibraryBookRecord count | 151 |
| Inventory records | inventory state=all: retained ACTIVE and WITHDRAWN records | separate Active books metric excludes WITHDRAWN | 151 retained, all currently ACTIVE |
| Current loans / Active loans | staff loans status=ACTIVE total | canonical loans status=ACTIVE aggregation | 0 |
| Pending borrow | canonical queue pending_counts.BORROW, request_type=BORROW status=PENDING | same canonical type/status aggregate | 0 |
| Pending return | canonical queue pending_counts.RETURN, request_type=RETURN status=PENDING | same canonical type/status aggregate | 0 |
| Membership count | explicitly labelled “memberships” link: all retained states from memberships endpoint | explicitly labelled Active members: status=ACTIVE, all roles | 3 all-state / 3 ACTIVE |

Inventory records and Active books intentionally differ when a book is withdrawn. Likewise total memberships and active membership totals intentionally differ after suspension/removal; they must not be presented as identical metrics. A catalogue requires valid titles, guaranteed by accepted creation validation. Book format is independent of title count: CN adds one title and zero physical holdings.

Collection physical quantities use canonical holdings plus accepted copy/allocation reconciliation. Activity uses canonical operation/audit history with UTC range boundaries, not current pending-state counts or global circulation. Historical approved/returned/cancelled operations are retained even when current loans and queues are zero. Live Overview and Analytics measurements are in `post2h_browser_validation.json`; isolated count/range/tenant tests are in the backend XML reports.
