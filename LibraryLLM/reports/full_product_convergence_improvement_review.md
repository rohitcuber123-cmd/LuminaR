# Post-implementation review

| Finding | Severity | Disposition | Evidence / limit |
| --- | --- | --- | --- |
| Lost local saved/AI/actions | HIGH | FIXED_NOW | Shared controls and canonical identity; tests |
| Parallel detail/Browse/card/filter CSS | MEDIUM | FIXED_NOW | 9 clusters converged; 8 files removed |
| Current-page-only global category filter | HIGH | FIXED_NOW | Server literal filter before paging; cross-page tests |
| Unbounded filtered catalogue count | MEDIUM | FIXED_NOW | 1-second exact count budget, truthful unknown total, probe |
| View All lost mode / personal return context | HIGH | FIXED_NOW | Actual datasets and explicit URL helpers |
| Stale-session saved response/toast / reader result | HIGH | FIXED_NOW | Token/version/key guards and scoped toasts |
| Unreachable legacy direct Borrow handlers | HIGH | FIXED_NOW | Removed; Part 2B/C preserved |
| Header account/notification sibling React key collision | LOW | FIXED_NOW | Distinct stable keys; paired navigation regression assertions |
| Six-viewport/browser history/reload gate | HIGH | NEXT_PHASE | Pending completion of same convergence phase; not a new feature phase |
| Runtime HNSW STALE baseline flag | MEDIUM | LATER | 5M vectors/pending=false; no rebuild or manifest rewrite allowed |
| Local-only AI unsupported OL contract | LOW | LATER | Explicit limitation; saving supported |
| Digital reader legacy entitlement dependency | LOW | LATER | Protected reader; digital tenancy excluded |
| Filtered totals unknown / unfiltered count estimate | LOW | LATER | Truthful UI; separate performance/index scope if requested |
| Existing lint warnings / large bundle chunks | LOW | LATER | Baseline signatures compared; no new errors |
| Historical research scripts / unused pure readNow helper | LOW | LATER | Explicit non-product artifacts; no canonical writer |
| Global events/notifications | NICE_TO_HAVE | LATER | Tenancy deliberately excluded |


Final route/component/API/store/CSS/backend inventories were regenerated with decisions per row. Tests/scripts/flag call sites are separately inventoried. Similar names alone were not used to invent bugs. There is no unexplained independent catalogue/detail/dashboard writer, but the browser and visual gate is still open. Overall PARTIAL.
