# Existing Events integration

Preserve editable Event V1/Part2D records and routes, categories, dates, ownership, visibility, cancellation reason, first-publication history, global seen receipts and frontend editor/detail pages. Announcements link existing events by canonical ID in the same tenant; they never copy or mutate event content.

Draft links may refer to same-library draft events for staff preparation. Announcement publication requires the linked event to have publication history and status PUBLISHED or CANCELLED. Foreign event IDs return concealed404. If an event later disappears/archives, the announcement remains readable but its link is explicitly unavailable. Existing event routes still validate current membership.

Staff chooses category EVENT and an existing published event from the first50 available choices, or retains an existing saved reference. Event category is presentation, not a permission. No automatic event-published/edited/cancelled broadcast is added: the audited Events module has its own global seen mechanism and no institution inbox transition broadcast to reuse. An explicit linked announcement is the supported communication workflow, avoiding duplicate implicit notifications and preserving existing editable event semantics.

RSVP, attendance, scheduled reminders and scheduling are not added. Existing loan reminders are preserved, not repurposed as an event scheduler. See future roadmap for dependencies and evaluation opportunities.
