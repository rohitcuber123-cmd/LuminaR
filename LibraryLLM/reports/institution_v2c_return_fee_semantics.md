# Return timestamp fairness

The accepted Part 2B return workflow remains authoritative: a member submits a return request, staff physically receives the item, then Confirm Received releases stock. A request alone never proves receipt.

The loan retains return_requested_at as legacy/first-request metadata, valid_return_requested_at for the particular request that staff completes, and physical_received_at for confirmed receipt. Every rejected request stays in request history. Fee calculation stores due_at, both request fields, physical_received_at, chosen charge_stop_at, charge_stop_policy, calendar boundary, grace, rate and days.

Under PHYSICAL_RECEIPT, staff delay can add calendar-day charges until receipt; an admin can record an audited adjustment or waiver. Under FIRST_VALID_RETURN_REQUEST, later-confirmed genuine returns stop on the completed request's UTC day. Rejected/fake earlier requests are ignored, even if the loan's first return_requested_at is older. Policies are fixed at issuance and displayed in fee details.

Both choices finalize only at physical confirmation. An overdue loan that remains active has an ESTIMATED amount and cannot be passed to final fee generation. Zero charge creates no fee. Finalization, stock release and next queue hold are within the same durable operation, so unpaid fees never withhold physical return.

Live G demonstrates a request on the due UTC day and receipt on the next day producing zero charge with FIRST_VALID_RETURN_REQUEST. Live H demonstrates an earlier rejected request followed by genuine completion still producing the correct charge. Tests cover both policies, staff delay, grace and preservation of policy versions. Synthetic date fixtures are explicitly labeled in the live report.
