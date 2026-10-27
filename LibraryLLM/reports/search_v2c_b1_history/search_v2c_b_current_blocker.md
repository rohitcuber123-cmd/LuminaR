# V2C-B stopped: forged choice deletes accepted Search context

Current V2C-A/A.1 gate passes. This is a new V2C-B interaction lifecycle defect.

An authenticated, authorized patron first commits an accepted Search context.
A contradictory query correctly leaves it intact and issues a pending choice.
Submitting an unissued choice UUID returns 404, but the accepted context is then
missing. The isolated Mongo reproducer fails the required unchanged-state assertion.
See search_v2c_b_stop_condition_observed.json and search_v2c_b_stop_condition.xml.

Cause: search/interaction_api.py authorized() wraps `yield` in the same
HTTPException handler as authorization. The operation's expected choice-not-found
404 reaches that handler, which calls invalidate(actor, library_id). This deletes
the caller's accepted contexts and pending clarifications. It does not require
foreign data access. No cross-user/private vocabulary leak was observed.

The prompt explicitly requires stopping if a forged clarification/choice can
mutate Search state. Implementation stopped; the defect has not been repaired
or hidden by changing the assertion. FINAL is PARTIAL, not accepted.

Next authorized development must separate actual authorization loss from an
operation's ordinary 403/404. Invalidation must require fresh confirmed loss of
membership/access. Forged choices must return a denial without deleting, touching,
creating or replacing accepted contexts. A valid pending choice must remain usable.
Run the retained reproducer first, then the complete final gates and browser checks.

Additional validation note: one earlier test incorrectly assumed an owner ADMIN
could browse a GENERAL_USER patron workspace; the fixture has been corrected to
test a real patron-to-librarian role change. That corrected test was not rerun after
the stop condition. The production patron-role policy was preserved.

Disposable accounts 488/489 were disabled, their memberships removed, their Search
contexts cleared, and only the V2CB Clause QA library archived. Original Test User
was restored to the Global Catalogue. Existing services remain running. Some final
source edits were tested in isolated processes after the last Search-service boot;
restart Search after fixing this blocker before claiming running-service acceptance.
