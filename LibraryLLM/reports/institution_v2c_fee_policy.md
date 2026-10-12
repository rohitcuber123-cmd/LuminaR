# Versioned fee policy

Version 1 preserves the repository's INR ₹5/day rate: 500 integer minor units, zero grace days, overdue enabled, PHYSICAL_RECEIPT stop, UTC_CALENDAR_DAY boundaries. It records the legacy source. The supported currency is INR with 100 minor units per rupee; new rates, payment amounts and adjustments are strict integers.

An immutable policy version contains policy_id UUID, library_id UUID, monotonic version, effective_from, overdue_enabled, rate_minor_per_day, currency/minor unit factor, grace_days, charge_stop_policy, day_boundary, created actor/timestamp and provenance. Admin creation writes a new complete version; old versions are never overwritten.

Actual staff issuance snapshots the current version onto the loan. Part 2C activation snapshots already existing loans. Renewals retain that snapshot while updating due_at. A later policy change affects future issuance, not previous loans or fee history. Imported legacy fees preserve original amounts with explicit legacy provenance instead of retroactive recomputation.

The calculation is max(0, UTC(stop).date − UTC(due_at).date − grace_days) × rate_minor_per_day when overdue is enabled. It preserves legacy calendar-day behavior, not elapsed 24-hour blocks. Crossing midnight can therefore add a day even when fewer than 24 hours have elapsed. Policy snapshots and the exact used timestamps/rate/days accompany every final charge.

PHYSICAL_RECEIPT is the default. FIRST_VALID_RETURN_REQUEST is also available: only the request that staff ultimately completes qualifies. An earlier rejected return request never stops accrual. Both timestamps remain stored. Final charges are generated at physical receipt; active loans show clearly labeled nonpayable estimates. Outstanding financial balance does not prevent returning an item.

Grace days support 0–365. Per-library caps, holiday calendars, other currencies, automatic lost/damage charges, provider processing and refunds are deferred. The supported total money range is bounded at 10^12 minor units; exceeding it requires review rather than truncation or floating conversion.
