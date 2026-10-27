# Implemented interaction layer — acceptance blocked

search/query_interaction.py consumes the accepted typed decision and candidates;
it does not recognize a replacement query grammar. Choices address one bounded
field; operands and rewritten fragments use the existing parser and validator.
No Qwen/model calls were added. Literal choices retain explicit controls.

Pending documents share search_sessions_v2b with a clarification: UUID prefix,
five-minute expiry, max16 per user/login/scope/workspace. IDs and choice IDs are
opaque UUIDs. User, JWT sid, workspace, scope, parser version, query, mode and
accepted context version are checked. Preview precedes one-use CAS consumption;
the existing execution pipeline repeats validation and session version checks.
Normal unaccepted queries do not commit/touch the accepted plan. Clear/context
invalidation also deletes attached pending documents. Actual lookup failures must
not invalidate accepted state: the current authorized() handler violates this
invariant on an unissued choice 404. See current_blocker and the retained failing test.
