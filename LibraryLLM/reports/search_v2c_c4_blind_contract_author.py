"""Independently authored C.4 semantic contracts; imports no application code."""

import collections
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "search_v2c_c4_review_query_only_input.json"
ADDITIONAL = ROOT / "search_v2c_c4_additional_review_query_input.json"
OUTPUT = ROOT / "search_v2c_c4_blind_contract_authored.json"
MANIFEST = ROOT / "search_v2c_c4_blind_contract_frozen_manifest.json"


def sha(value):
    return hashlib.sha256(value).hexdigest()


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


source = json.loads(SOURCE.read_text(encoding="utf-8-sig"))
additional = json.loads(ADDITIONAL.read_text(encoding="utf-8-sig"))
queries = source["queries"] + additional["queries"]
SCHEMA_CLARIFICATION = {
    "title_text": "Single literal Title/Author OR predicate: the normalized operand must occur in title OR author; it is not necessarily an inferred title entity.",
    "author_text": "Separate author-only AND predicate.",
    "exact_text": "Exact title/identifier identity, with normalization at matching. Preserve supplied punctuation and permitted identifier hyphens in the authored operand.",
    "intent": {"FIND_EXACT": "literal/identity", "FIND_AUTHOR": "author-only", "DISCOVER_TOPIC": "soft topic", "BROWSE_CATEGORY": "canonical subjects with no topic"},
    "provenance": "Coordinator supplied field-semantics-only clarification before authoring/freeze; no predictions, prior labels, source, or results supplied.",
}

RULES = {
    "CATEGORY_NEGATIVE": "A bare canonical category excluded by not, but not, excluding, without, or except contributes its scoped canonical exclusion predicate. It does not additionally prohibit its wording in title, author, or description.",
    "TOPIC_NEGATIVE": "Not about explicitly addresses content/topic. Under the supplied text-negative predicate contract it contributes a literal text exclusion, not an independently inferred canonical category exclusion.",
    "NO_DOUBLE_NEGATIVE_INFERENCE": "Do not infer both canonical subject and literal text prohibition from one negative phrase without separate evidence for both predicates.",
    "NOT_ONLY": "Not only is additive/nonexclusive, not a prohibition. It does not by itself justify either excluding Romance or making Romance a mandatory hard gate for every result.",
    "HYPHENATED_LEXEME": "Non-fiction is a lexical category phrase; non- is not a standalone canonical subject-exclude operator. Do not split off Fiction as a negative or invent an unavailable canonical label.",
    "CANONICAL_CONFLICT": "Requiring and excluding the same canonical subject is contradictory until an explicit choice edits that subject predicate.",
    "CANONICAL_CONFLICT_CHOICE": "Selecting Exclude Romance resolves the canonical conflict by removing Romance from required subjects and retaining it in excluded subjects. It does not add a broad literal romance text ban.",
    "REFINEMENT_PRESERVATION": "An explicit negative/rating refinement preserves the unrelated accepted machine-learning topic from the prior query.",
    "CHIP_ITEM_PRESERVATION": "Removing the Fiction include chip and Romance exclude chip removes only those items; Mystery, excluded Biography, and the rating threshold survive, with or without a session.",
    "LITERAL_MODE": "TITLE_AUTHOR carries the complete supplied raw query in title_text, the single title OR author operand. It does not activate SMART author extraction or discard request words, punctuation, or spacing.",
    "SMART_IDENTITY": "Complete ISBN identity syntax is accepted in SMART and can execute even when no catalog record exists. Retain the raw identifier spelling in exact_text; matching may normalize permitted hyphens.",
    "FREE_PREFIX_NOT_TITLE": "Free text before by AUTHOR is not sufficient title evidence. Keep the explicit author predicate and preserve the prefix as soft text; do not create title_text or exact title identity without explicit title syntax/evidence.",
    "PARTIAL_AUTHORING": "Only expected_fields are direct authored field values. Omitted fields remain untouched; unresolved projections are visible. Synthetic eligibility examples express semantic predicates independently of application behavior.",
}


def base_fields(intent="BROWSE_CATEGORY"):
    result = {"decision": "EXECUTABLE", "executable": True, "title_text": None, "author_text": None, "exact_text": None, "subjects": [], "exclude_subjects": [], "exclude_terms": [], "rating_min": None, "rating_max": None}
    if intent is not None:
        result["intent"] = intent
    return result


def book(title, subjects, *, author="Review Example Author", description="Independent review example.", rating=4.7):
    return {"title": title, "author": author, "subjects": subjects, "description": description, "rating": rating}


def example(candidate, eligible, reason):
    return {"candidate": candidate, "eligible": eligible, "reason": reason}


def category_examples(positive, excluded, *, rating=None):
    positive_list = [] if positive is None else [positive]
    visible_negative = excluded[0]
    threshold = 4.7 if rating is None else rating + 0.5
    return [
        example(book("A critical discussion of " + visible_negative, positive_list or ["History"], description="The phrase " + visible_negative + " appears here, but the book is not catalogued in that category.", rating=threshold), True, "The canonical excluded subject is absent. Mere negative wording in title/description does not trigger a category-only exclusion."),
        example(book("A catalogue example", positive_list + excluded, description="No excluded wording is needed in title/description.", rating=threshold), False, "At least one excluded canonical subject is present, so category exclusion rejects the candidate."),
    ]


records = []
for query in queries:
    rid = query["review_id"]
    raw = query["query"]
    fields = base_fields()
    unresolved = {}
    predicates = []
    examples = []
    rules = ["PARTIAL_AUTHORING"]
    field_reasons = {}
    extras = {}
    stage = "QUERY"

    if query["mode"] == "TITLE_AUTHOR":
        fields = base_fields("FIND_EXACT")
        fields["title_text"] = raw
        reason = "Explicit literal TITLE_AUTHOR mode uses the complete supplied query as the title_text OR operand. By-looking words are literal input and do not create an author_text AND filter. Every prefix, punctuation mark, and internal space is retained in the authored operand."
        predicates = [{"operation": "OR", "predicates": [{"field": "title", "operator": "literal_match", "operand": raw}, {"field": "author", "operator": "literal_match", "operand": raw}]}]
        examples = [example(book(raw, [], author="Another Person"), True, "The complete literal operand matches the title; matching the separate author is not required."), example(book("A separate title", [], author=raw), True, "The complete literal operand matches the author side of the OR predicate."), example(book("Unrelated collected works", [], author=raw.rsplit(" by ", 1)[-1].rstrip("?! .")), False, "A match to only the person-looking suffix is insufficient when the complete literal operand does not occur in title or author.")]
        rules.append("LITERAL_MODE")
        field_reasons["title_text"] = "This field is defined as the single literal title-OR-author predicate, so its operand is the complete raw supplied query."
        field_reasons["author_text"] = "No separate author-only AND predicate is justified in literal mode."

    elif rid in {"v2:v2cc-authored-d22_isbn_like-01", "v2:v2cc-authored-d22_isbn_like-03"}:
        fields = base_fields("FIND_EXACT")
        fields["exact_text"] = raw
        normalized = raw.replace("-", "")
        reason = "The complete supplied token is ISBN identity syntax accepted in SMART. Execution does not require an existing catalog match. The authored exact_text retains the raw hyphenation; normalization belongs to matching."
        predicates = [{"field": "isbn", "operator": "identity", "raw_operand": raw, "normalized_identity": normalized}]
        examples = [example({"isbn": normalized}, True, "The supplied ISBN identity matches after permitted hyphen normalization."), example({"isbn": "9780000000002", "title": raw}, False, "An incidental title occurrence is not a match to a different ISBN identity.")]
        rules.append("SMART_IDENTITY")
        field_reasons["exact_text"] = "The entire raw ISBN is the exact identity operand, including permitted hyphens."

    elif rid in {"gold-065", "gold-066", "gold-069", "natural-01", "natural-02", "natural-03", "natural-04", "natural-05", "natural-09", "natural-10"}:
        if rid == "gold-069":
            positive, excluded = "History", ["Military History"]
        elif rid == "natural-09":
            positive, excluded = "Java", ["JavaScript"]
        elif rid == "natural-10":
            positive, excluded = None, ["Deep learning"]
            fields["intent"] = "DISCOVER_TOPIC"
            extras["preserved_soft_topic"] = "AI"
            predicates.append({"kind": "soft_topic", "operand": "AI"})
            unresolved["soft_topic_production_carrier"] = "The supplied production-field list has no soft-topic remainder field; AI must remain soft rather than being lost or invented as a canonical subject."
        else:
            positive = "Fiction" if rid in {"gold-065", "gold-066"} else None
            excluded = ["Romance"]
        fields["subjects"] = [] if positive is None else [positive]
        fields["exclude_subjects"] = excluded
        reason = "The bare category phrase explicitly excludes the scoped canonical subject " + ", ".join(excluded) + ". It supplies a category predicate only, not a second literal-text ban."
        if positive:
            reason += " The positive " + positive + " independently names a scoped canonical subject."
        if rid == "natural-10":
            reason += " AI is not a supplied canonical category; it remains the soft positive topic."
        predicates.extend([{"kind": "canonical_subject_include", "values": fields["subjects"]}, {"kind": "canonical_subject_exclude_any", "values": excluded}])
        examples = category_examples(positive, excluded)
        if rid == "natural-10":
            examples[0]["candidate"]["title"] = "AI and the limits of Deep learning"
            examples[0]["candidate"]["description"] = "A discussion of AI with incidental wording Deep learning; no Deep learning subject is assigned."
        rules.extend(["CATEGORY_NEGATIVE", "NO_DOUBLE_NEGATIVE_INFERENCE"])

    elif rid in {"gold-094", "gold-095"}:
        fields.update(decision="CONTRADICTORY", executable=False, subjects=["Fiction"], exclude_subjects=["Fiction"])
        reason = "The request requires canonical Fiction and excludes the same canonical Fiction. No candidate can satisfy both predicates until the conflict is resolved; no literal text exclusion is needed to establish the contradiction."
        predicates = [{"kind": "canonical_subject_include", "values": ["Fiction"]}, {"kind": "canonical_subject_exclude_any", "values": ["Fiction"]}]
        examples = [example(book("A book", ["Fiction"]), False, "It satisfies inclusion but violates the same subject exclusion."), example(book("A book", ["History"]), False, "It avoids exclusion but fails required Fiction inclusion.")]
        rules.extend(["CANONICAL_CONFLICT", "NO_DOUBLE_NEGATIVE_INFERENCE"])

    elif rid == "mixed_refinement":
        fields.update(intent="DISCOVER_TOPIC", exclude_subjects=["Romance"], rating_min=4)
        reason = "The current input adds canonical Romance exclusion and a rating strictly above 4. It does not revoke the prior machine-learning topic. The topic, category exclusion, and rating bound must all survive the refinement."
        predicates = [{"kind": "soft_topic", "operand": "machine learning", "origin": "prior_query"}, {"kind": "canonical_subject_exclude_any", "values": ["Romance"]}, {"field": "rating", "operator": ">", "value": 4}]
        extras["preserved_soft_topic"] = "machine learning"
        extras["rating_min_inclusive"] = False
        unresolved["soft_topic_production_carrier"] = "The supplied field list has no soft-topic remainder field; preserve machine learning in the production carrier rather than clearing it."
        examples = [example(book("Machine learning and romance vocabulary", ["History"], description="An account of machine learning; Romance is incidental wording, not a canonical subject.", rating=4.5), True, "The prior topic is present, canonical Romance is absent, and rating exceeds 4."), example(book("Machine learning", ["Romance"], rating=4.5), False, "The canonical excluded category is present."), example(book("Machine learning", ["History"], rating=4), False, "Above 4 is strict; equality at 4 does not satisfy the semantic bound.")]
        rules.extend(["REFINEMENT_PRESERVATION", "CATEGORY_NEGATIVE", "NO_DOUBLE_NEGATIVE_INFERENCE"])

    elif rid == "kg_negative":
        fields.update(intent="DISCOVER_TOPIC", exclude_subjects=["Romance"], rating_min=4)
        reason = "About neural networks supplies a soft content topic, but not romance supplies a bare canonical Romance exclusion, and rated above 4 supplies a strict rating bound. These are distinct predicates; Romance wording alone does not justify rejection."
        predicates = [{"kind": "soft_topic", "operand": "neural networks"}, {"kind": "canonical_subject_exclude_any", "values": ["Romance"]}, {"field": "rating", "operator": ">", "value": 4}]
        extras.update(preserved_soft_topic="neural networks", rating_min_inclusive=False)
        unresolved["soft_topic_production_carrier"] = "The supplied production-field list has no soft-topic remainder field; neural networks remains a soft topic, not an invented canonical category."
        examples = [example(book("Neural networks: beyond the romance of AI", ["History"], description="A discussion of neural networks.", rating=4.8), True, "Topic and rating are satisfied and canonical Romance is absent, despite romance appearing in the title."), example(book("Neural networks", ["Romance"], rating=4.8), False, "The excluded canonical category is present."), example(book("Neural networks", ["History"], rating=4), False, "Rating equal to 4 does not satisfy above 4.")]
        rules.extend(["CATEGORY_NEGATIVE", "NO_DOUBLE_NEGATIVE_INFERENCE"])

    elif rid in {"chip_removal_without_session", "chip_removal_with_session"}:
        stage = "AFTER_POST_ACTION"
        fields.update(subjects=["Mystery"], exclude_subjects=["Biography"], rating_min=3)
        reason = "The chip action removes only included Fiction and excluded Romance. Included Mystery, excluded Biography, and rating strictly above 3 remain. The absence or presence of a session does not authorize deleting the other list items or unrelated rating."
        extras["initial_expected_fields"] = {"subjects": ["Fiction", "Mystery"], "exclude_subjects": ["Romance", "Biography"], "exclude_terms": [], "rating_min": 3, "rating_max": None}
        extras["rating_min_inclusive"] = False
        predicates = [{"kind": "canonical_subject_include", "values": ["Mystery"]}, {"kind": "canonical_subject_exclude_any", "values": ["Biography"]}, {"field": "rating", "operator": ">", "value": 3}]
        examples = [example(book("A mystery", ["Mystery", "Romance"], rating=3.8), True, "Mystery remains required, removed Romance exclusion no longer rejects, and the rating bound is met."), example(book("A biography mystery", ["Mystery", "Biography"], rating=4.2), False, "The unaddressed Biography exclusion must remain active."), example(book("A mystery", ["Mystery"], rating=3), False, "The unaddressed strict rating bound must remain active.")]
        rules.extend(["CHIP_ITEM_PRESERVATION", "CATEGORY_NEGATIVE", "NO_DOUBLE_NEGATIVE_INFERENCE"])

    elif rid == "natural-06":
        fields.update(intent="DISCOVER_TOPIC", exclude_terms=["romance"])
        reason = "Not about romance negates content/topic, not just a catalog category. Under the supplied text-negative contract this is represented by the romance literal text negative across the specified searchable fields. A canonical Romance exclusion is not separately inferred."
        predicates = [{"kind": "literal_text_exclude", "fields": ["title", "author", "subjects", "description"], "operand": "romance"}]
        examples = [example(book("A social history", ["History"], description="An account of romance and courtship."), False, "The description contains the negated romance content even without a canonical Romance category."), example(book("A social history", ["History"], description="An account of trade and infrastructure."), True, "The excluded text is absent from all specified searchable fields.")]
        rules.extend(["TOPIC_NEGATIVE", "NO_DOUBLE_NEGATIVE_INFERENCE"])

    elif rid == "natural-07":
        fields = base_fields(None)
        del fields["decision"]
        del fields["executable"]
        reason = "Not only romance requests nonexclusivity or broader variety. It does not prohibit Romance and does not justify requiring Romance for every result. The supplied contract does not specify a deterministic diversity/ranking plan or whether to execute a soft preference versus ask for clarification, so no decision or executable gold is forced."
        predicates = [{"kind": "nonexclusive_preference", "operand": "romance", "hard_prohibition": False, "mandatory_subject_for_each_candidate": False}]
        unresolved = {"decision": "The nonexclusive request is meaningful, but supported diversity/ranking versus clarification behavior is not supplied.", "executable": "Dependent on the unspecified treatment of the nonexclusive preference.", "intent": "No supplied enum uniquely captures a nonexclusive variety request.", "soft_preference_production_carrier": "Do not discard the request or convert it into a Romance ban/mandatory gate; the supplied production-field list has no diversity preference carrier."}
        examples = [example(book("A romance", ["Romance"]), True, "Romance is not prohibited; eligibility here is with respect to hard predicates only."), example(book("A history", ["History"]), True, "The request is not confined to Romance, so absence of Romance must not trigger a hard failure.")]
        rules.append("NOT_ONLY")

    elif rid == "natural-08":
        fields = base_fields("DISCOVER_TOPIC")
        reason = "Non-fiction is a complete lexical category phrase. The review scope supplies no Nonfiction canonical subject, so this review preserves it as a soft category/topic request and does not manufacture a canonical Fiction exclusion or a literal fiction-word ban."
        predicates = [{"kind": "soft_topic", "operand": "non-fiction", "lexical_unit": True}]
        extras["preserved_soft_topic"] = "non-fiction"
        unresolved = {"soft_topic_production_carrier": "Preserve the whole lexical phrase in the soft-query carrier; no such field is named in the supplied output schema.", "canonical_nonfiction_alias": "No Nonfiction subject/alias is supplied in CANONICAL_REVIEW; do not invent one."}
        examples = [example(book("The history of fiction", ["History"], description="A factual critical study of literary fiction."), True, "A nonfiction work can contain the word fiction. Splitting non-fiction into a literal fiction ban would wrongly reject it."), example(book("An invented tale", ["Fiction"], description="A fictional narrative."), None, "No automatic Fiction exclusion was specified. Soft relevance should favor nonfiction, but hard classification eligibility cannot be fabricated from an absent canonical category.")]
        rules.append("HYPHENATED_LEXEME")

    elif rid in {"gold-043", "gold-056"}:
        fields = base_fields(None)
        author = "Asimov" if rid == "gold-043" else "George Orwell"
        prefix = "Foundation" if rid == "gold-043" else "1984"
        fields["author_text"] = author
        reason = "By explicitly supplies the author operand " + author + ". The prefix " + prefix + " is free text without explicit title syntax. The user explicitly forbids inferring title_text from this position, and no title catalog is supplied. Preserve the prefix as soft text rather than exact title identity or an inferred numeric constraint."
        predicates = [{"field": "author", "operator": "literal_author_match", "operand": author}, {"kind": "soft_topic_or_free_text", "operand": prefix}]
        extras["preserved_free_prefix"] = prefix
        unresolved = {"soft_prefix_production_carrier": "The supplied output field list has no separate soft remainder field. Preserve the prefix there when applying this contract; do not put it in title_text or exact_text.", "intent": "The supplied intent descriptions do not uniquely classify combined author and soft-prefix text."}
        examples = [example(book(prefix + ": an essay collection", [], author=author), True, "The author predicate is satisfied; the free prefix is relevant without requiring exact title identity."), example(book(prefix, [], author="An unrelated author"), False, "Matching free text does not remove the explicitly supplied author-only AND predicate.")]
        rules.append("FREE_PREFIX_NOT_TITLE")
        field_reasons["title_text"] = "The explicitly supplied normative instruction forbids creating title_text merely from a free prefix before by AUTHOR."
        field_reasons["exact_text"] = "No explicit title syntax or complete exact identifier supports exact identity."
        field_reasons["author_text"] = "The literal by AUTHOR phrase explicitly supplies this author-only operand without expanding the name."

    elif rid == "clarification_subject_exclude":
        stage = "AFTER_POST_ACTION"
        fields["exclude_subjects"] = ["Romance"]
        reason = "The selected Exclude Romance clarification resolves the canonical inclusion/exclusion conflict by choosing exclusion: Romance is removed from required subjects and retained in exclude_subjects. This choice edits only the canonical predicate; it does not add a literal romance ban."
        extras["initial_expected_fields"] = {"subjects": ["Romance"], "exclude_subjects": ["Romance"], "exclude_terms": [], "decision": "CONTRADICTORY", "executable": False}
        predicates = [{"kind": "canonical_subject_exclude_any", "values": ["Romance"]}]
        examples = category_examples(None, ["Romance"])
        rules.extend(["CANONICAL_CONFLICT_CHOICE", "NO_DOUBLE_NEGATIVE_INFERENCE"])

    else:
        raise ValueError("Unreviewed query: " + rid)

    defaults = {
        "decision": "The supplied request has a uniquely executable interpretation under the stated predicates, except explicit canonical contradictions which require resolution.",
        "executable": "Execution follows the authored decision; unresolved decision/execution is omitted instead of forced.",
        "title_text": "No separately justified literal Title/Author OR operand is supplied by this SMART field syntax.",
        "author_text": "No independent author-only AND predicate is supplied by this query.",
        "exact_text": "No exact title or identifier identity is supplied by this query.",
        "subjects": "Only explicitly justified scoped canonical positive categories are required; ordinary soft topics and absent category aliases do not become hard subjects.",
        "exclude_subjects": "Only explicitly justified canonical category prohibitions are represented here; topic/text negatives and nonexclusive phrases do not create a second category gate.",
        "exclude_terms": "Only explicit topic/text prohibition evidence justifies a literal searchable-text negative; a canonical category prohibition alone does not.",
        "rating_min": "The named numeric lower threshold is retained; an explicit greater-than predicate in semantic_predicates fixes strictness for above wording. Null means no lower rating bound was requested.",
        "rating_max": "No upper rating bound is requested.",
        "intent": "The intent follows the independently established literal/identity, topic, or category role described in the schema clarification.",
    }
    for name in fields:
        field_reasons.setdefault(name, defaults[name])
    # This is an internal authoring consistency check against only the authorized vocabulary.
    scope = source["CANONICAL_REVIEW"] if query["scope"] == "CANONICAL_REVIEW" else source["scopes"][query["scope"]]
    for name in ["subjects", "exclude_subjects"]:
        assert all(value in scope["subjects"] for value in fields[name]), (rid, name)
    records.append({"review_id": rid, "query_sha256": sha(raw.encode("utf-8")), "input_record_sha256": sha(canonical_bytes(query)), "scope": query["scope"], "mode": query["mode"], "evaluation_stage": stage, "review_status": "AI_REVIEWED", "resolution": "PARTIAL" if unresolved else "ESTABLISHED_FIELDS", "expected_fields": fields, "field_reasons": field_reasons, "semantic_reason": reason, "semantic_predicates": predicates, "eligibility_examples": examples, "rule_ids": rules, "unresolved_fields": unresolved, **extras})

assert len(records) == 68
assert len({record["review_id"] for record in records}) == 68
counts = {"input_records": len(records), "AI_REVIEWED": len(records), "records_with_authored_fields": sum(bool(record["expected_fields"]) for record in records), "records_with_unresolved_fields": sum(bool(record["unresolved_fields"]) for record in records), "authored_field_values": sum(len(record["expected_fields"]) for record in records), "eligibility_examples": sum(len(record["eligibility_examples"]) for record in records), "by_mode": dict(sorted(collections.Counter(record["mode"] for record in records).items())), "by_decision": dict(sorted(collections.Counter(record["expected_fields"].get("decision", "UNAUTHORED") for record in records).items())), "by_resolution": dict(sorted(collections.Counter(record["resolution"] for record in records).items())), "by_authored_field": dict(sorted(collections.Counter(field for record in records for field in record["expected_fields"]).items()))}
artifact = {"artifact_type": "independently_authored_semantic_contract_review", "version": "C4-blind-contract-v1", "review_status": "AI_REVIEWED", "stage": "BLIND_AUTHORED_BEFORE_OLD_LABEL_COMPARISON", "provenance": {"authorized_query_only_inputs": [SOURCE.name, ADDITIONAL.name], "schema_clarification": SCHEMA_CLARIFICATION, "original_labels_read": False, "predictions_read": False, "parser_or_source_read": False, "score_or_failure_reports_read": False, "current_user_attachment_read": False, "sealed_files_read": False, "parser_api_or_tests_called": False, "prior_authored_labels_reused": False, "method": "Each of 68 supplied records was independently authored from query semantics, scoped capabilities/vocabulary, the supplied normative contract, and field-semantics-only clarification. Literal-mode records preserve their individual raw query operands; prior authored contracts or original labels were not copied."}, "field_policy": "Only expected_fields are proposed direct field values. Omission is not a command to clear a field. Null is explicit absence. Semantic predicates and eligibility examples specify meaning and strict rating boundaries. AI_REVIEWED is provenance, not certainty for unresolved projections.", "query_hash_definition": "SHA-256 of exact query string encoded UTF-8 without trimming/normalization", "field_semantics": SCHEMA_CLARIFICATION, "rating_boundary_policy": "rating_min records the numeric threshold. Above is strictly greater; semantic_predicates and rating_min_inclusive=false specify the required boundary independently of unspecified DTO strictness encoding.", "eligibility_policy": "Examples refer to authored semantic constraints and assume ordinary access/catalogue eligibility. Soft topic evidence supports relevance but is not converted to a hard canonical gate. Null eligible explicitly means hard classification cannot be established from supplied information.", "versioning_policy": "This is a new independently authored C4 artifact. It does not claim that any unseen historical assertion or earlier label has been compared, disproved, or automatically replaced. The frozen independent contracts must precede such comparison.", "rules": RULES, "counts": counts, "records": records}
OUTPUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
manifest = {"artifact_type": "independent_C4_semantic_contract_freeze_manifest", "version": "C4-blind-contract-v1", "stage": "FROZEN_BEFORE_OLD_LABEL_COMPARISON", "hash_algorithm": "SHA-256", "source_files": [{"path": str(path), "sha256": sha(path.read_bytes())} for path in [SOURCE, ADDITIONAL]], "authoring_script": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).read_bytes())}, "authored_file": {"path": str(OUTPUT), "sha256": sha(OUTPUT.read_bytes())}, "schema_clarification_sha256": sha(canonical_bytes(SCHEMA_CLARIFICATION)), "records_canonical_json_sha256": sha(canonical_bytes(records)), "query_identity_manifest_sha256": sha(canonical_bytes([{key: record[key] for key in ["review_id", "query_sha256", "input_record_sha256"]} for record in records])), "canonical_json_definition": "UTF-8 JSON, ensure_ascii=false, recursively sorted keys, separators comma/colon without whitespace; source record order preserved", "counts": counts, "blindness_attestation": "Only the two authorized query-only source files and this newly authored script were read. No current user attachment, application parser/source/tests, old labels, predictions, C3/C4 scores/failures, sealed file, or old authored record file was read. No parser/API/tests were called. The new fields, semantic predicates, counterexamples, and aggregate hashes were frozen before any old-label comparison."}
MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"authored_path": str(OUTPUT), "authored_sha256": sha(OUTPUT.read_bytes()), "manifest_path": str(MANIFEST), "manifest_sha256": sha(MANIFEST.read_bytes()), "counts": counts}, indent=2))
