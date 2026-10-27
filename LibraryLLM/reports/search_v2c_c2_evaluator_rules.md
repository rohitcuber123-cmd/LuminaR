# C2 evaluator rules (c2-development-1)

No evaluator semantic correction is justified by the current review. Reuse the
V1 strict expected-plan adapter, atom definitions, comparator and safety metrics.
Raw V1 rates remain available alongside V2 deduplicated rates. The documented
atomic view compares canonical field/value/operator atoms. No additional
normalization or case-specific exception is applied.

Subject exclusion and text exclusion are NOT equivalent: a book whose subject
is History but title mentions Romance is rejected only by the latter. Therefore
an extra exclude_terms atom stays an error. Do not collapse those fields.

Pure list order/case/whitespace adapters are inherited and disclosed; literal
source JSON and original labels remain preserved. Strict plan match means all
authored dimensions compared, not byte equality of dataclass provenance.

Blocked-case unsafe auto-parse uses blocked gold rows, with all-case incidence
reported separately. Completeness, unsupported and contradiction denominators
are frozen labels. Supported contradiction diagnostic is additive and excludes
only the pre-existing independently flagged rating_domain_assumption cases;
the raw full contradiction metric is never replaced.

No calibration/heldout entry point exists in the C2 development evaluator.

Native evaluator c2-native-1: workspace permission denial is HTTP403; private
resource/membership/choice concealment uses HTTP404. Store original authored
status and actual status side by side; an accepted API error-code adapter does
not alter corpus labels or count a parser pass. Public patron access may have
an explicitly false membership-only applicability precondition; execute and
record that action, publish applicable and all-security denominators. Literal
UI clear controls bind to the real clear API, not an invented NL command.
Legacy session-delta rows lack full prior-state oracles. Run an explicit
synthetic prior and publish delta mismatches and retention diagnostics; do not
call these raw exact lifecycle passes. Security state-oracle pass is separate
from raw native label/status accuracy and semantic session correctness.
