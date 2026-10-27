# Tenant deterministic metadata graph

Book node identity is `book:<library_book_id>`; the manifest and current canonical library scope define the namespace. Optional global work ID is a reference field, never a replacement identity. Author, Subject and Classification feature nodes reuse existing normalization and stable feature IDs. Existing relation labels are reused; nodes/edges are sorted and deduplicated.

Allowed graph input is the immutable descriptive dataset. No user, membership, loan, fee, reservation, access code, asset path, private document chunk or LLM-generated edge is allowed. Validation rederives the complete expected node and edge sets from metadata.

READY graph reads filter Book nodes through current role-permitted canonical records and return only referenced features. Not-ready states return an explicitly tenant-labelled empty state and a separate Global Graph Lab link. Shared SVG presentation is extracted from the accepted global renderer; global KG artifacts, API, topic/ranking logic are unchanged. Both Patron and Staff graph views are read-only and contain no build controls.
