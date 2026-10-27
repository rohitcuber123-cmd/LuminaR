"""Materialize independently reviewed development contracts, without evaluation imports.

The policy below was authored from query-only development input and scope vocabulary.
The script only expands reviewed SMART wording variants and computes audit hashes.
It does not call or import the search parser, evaluator, API, or tests.
"""

import collections
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "search_v2c_c3_development_label_query_input.json"
VOCAB = ROOT / "search_v2c_c_scope_vocabularies.json"
OUTPUT = ROOT / "search_v2c_c3_development_label_blind_authored.json"
MANIFEST = ROOT / "search_v2c_c3_development_label_blind_manifest.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


source = json.loads(INPUT.read_text(encoding="utf-8-sig"))
vocab = json.loads(VOCAB.read_text(encoding="utf-8-sig"))
allowed_fields = set(source["schema"]["fields"])


RULES = {
    "SMART_WORDING_ONLY": "In SMART, a request preface, politeness suffix, or terminal request punctuation does not alter the reviewed semantic constraints. This normalization is never applied in TITLE_AUTHOR.",
    "AUTHOR_VS_ABOUT": "An explicit by/written by/authored by phrase establishes authorship. About/on/influence language concerns a topic and does not establish an author equality filter.",
    "ABOUT_IS_SOFT": "An ordinary about/on topic remains semantic text even when a topic word also happens to occur in the scoped subject vocabulary.",
    "SCOPED_CANONICAL_NEGATIVE": "A clearly named canonical scoped subject exclusion populates excluded subjects. It does not additionally prohibit occurrences of those words in title, author, description, or semantic text.",
    "UNLISTED_NEGATIVE_UNRESOLVED": "When the excluded phrase is absent from the authorized scoped canonical vocabulary, this review does not invent a subject alias or a literal exclusion projection.",
    "MULTI_CONSTRAINT_COMPOSITION": "Supported rating, year, format, availability, canonical subject, author, and soft-topic constraints compose without their order changing their meaning.",
    "COMMA_SCOPE_AMBIGUITY": "In 'exclude Romance, Fiction', the final Fiction can continue the excluded list or name a separate included genre. Neither interpretation is uniquely established; choosing one as a unique gold label would invent meaning.",
    "TYPO_POLICY_UNRESOLVED": "The intended spelling can be highly plausible while hard subject enforcement, soft fallback, correction notice, and execution policy remain underdetermined by the supplied contract. No forced decision or subject label is authored.",
    "SMART_ISBN_ACCEPTED": "A syntactically valid ISBN identity request is accepted in SMART. An exact lookup may return no records; assignment or result existence is not required to establish that the request is executable.",
    "ISBN_LIKE_TEXT_IS_TEXT": "A phrase explicitly asking for 'the text' does not become an ISBN lookup merely because it contains grouped digits. Literal-versus-soft text projection is left unresolved here.",
    "LITERAL_TITLE_AUTHOR": "TITLE_AUTHOR matches the complete supplied literal query against title/author. It does not activate SMART by-author grammar or discard request-looking words, punctuation, or spacing.",
    "PROJECTION_RESTRAINT": "Only explicitly authored fields are normative. Omitted fields remain untouched. Canonical casing alternatives, unspecified normalization, and unavailable enum values are not invented.",
}


def smart_core(text):
    text = re.sub(r"^(Please find,?\s+|Find me\s+|Show me\s+)", "", text)
    text = re.sub(r"\s*([!?]+|\.)$", "", text)
    text = re.sub(r"\s+please$", "", text)
    return text.strip()


def fields(*, author=None, subjects=None, excluded=None, semantic_marker=False, semantic=None):
    result = {
        "expected_decision": "EXECUTABLE",
        "execution_allowed": True,
        "expected_author": author,
        "expected_title": None,
        "expected_exact_text": None,
        "expected_excluded_subjects": [] if excluded is None else excluded,
        "expected_exclude_terms": [],
    }
    if subjects is not None:
        result["expected_subjects"] = subjects
    if semantic_marker:
        result["expected_semantic_text"] = semantic
    return result


# Each entry is a manually reviewed semantic template, independent of existing gold.
AUTHOR = {
    "books by Ursula K. Le Guin": (fields(author="Ursula K. Le Guin", subjects=[], semantic_marker=True), "The explicit by phrase selects Ursula K. Le Guin as author; generic books adds no topic.", []),
    "books about Ursula K. Le Guin": (fields(subjects=[]), "Ursula K. Le Guin is the subject of the requested books, not a requested author.", ["expected_semantic_text"]),
    "fiction by George Orwell": (fields(author="George Orwell", subjects=["Fiction"], semantic_marker=True), "Fiction names a scoped canonical genre and by George Orwell names its author.", []),
    "books on the ideas of George Orwell": (fields(subjects=[]), "On the ideas of George Orwell describes a topic, not authorship.", ["expected_semantic_text"]),
    "poetry written by Emily Dickinson": (fields(author="Emily Dickinson", subjects=["Poetry"], semantic_marker=True), "Poetry is explicitly requested and written by assigns Emily Dickinson as author.", []),
    "about the poetry of Emily Dickinson": (fields(subjects=[]), "The entire poetry-of-Dickinson phrase is an about topic; it need not be a book authored by Dickinson or classified as Poetry.", ["expected_semantic_text"]),
    "books authored by Octavia Butler": (fields(author="Octavia Butler", subjects=[], semantic_marker=True), "Authored by explicitly assigns Octavia Butler as author.", []),
    "biographies about Octavia Butler": (fields(), "About Octavia Butler makes Butler the biographical topic, not the author. The exact Biography/Biographies canonical projection is not forced.", ["expected_subjects", "expected_semantic_text"]),
    "by Terry Pratchett about witches": (fields(author="Terry Pratchett", subjects=[], semantic_marker=True, semantic="witches"), "By assigns Terry Pratchett as author, while about witches supplies a soft topic.", []),
    "study the influence of Terry Pratchett": (fields(subjects=[]), "Studying Pratchett's influence does not request authorship by Pratchett.", ["expected_semantic_text"]),
}

MULTI = {
    "rated above 4, online Fiction about wizards": (fields(subjects=["Fiction"], semantic_marker=True, semantic="wizards"), "Fiction is explicit; about wizards is soft. The private scope supports rating and online constraints.", []),
    "exclude Romance; after publication year 2020; include Fiction": (fields(subjects=["Fiction"], excluded=["Romance"], semantic_marker=True), "Include Fiction and exclude Romance are explicit scoped canonical subject constraints. The year constraint is supported in this scope.", []),
    "physical only, Mystery, rated below 4": (fields(subjects=["Mystery"], semantic_marker=True), "Mystery is an independently listed canonical genre; physical format and rating are supported.", []),
    "Neural Networks available now rated at least 3": (fields(subjects=["Neural Networks"], semantic_marker=True), "Neural Networks exactly names a private-scope canonical subject, with supported availability and rating constraints.", []),
    "before 2018 in publication year, online books on bridges": (fields(subjects=[], semantic_marker=True, semantic="bridges"), "On bridges is a soft topic; supported year and online constraints do not create a canonical bridge subject.", []),
    "by Synthetic A1 Author, include Wizards, rating above 3": (fields(author="Synthetic A1 Author", subjects=["Wizards"], semantic_marker=True), "By explicitly assigns the complete author name, including A1. Include Wizards names the scoped canonical subject.", []),
    "include Fiction, rating at most 4.5, exclude Romance": (fields(subjects=["Fiction"], excluded=["Romance"], semantic_marker=True), "The include/exclude operators unambiguously assign Fiction and Romance. Decimal rating is a separate supported constraint.", []),
    "about waterways, physical books published in 2021": (fields(subjects=[], semantic_marker=True, semantic="waterways"), "About waterways is soft text with supported physical and publication-year constraints.", []),
    "online only; include Mystery; available now": (fields(subjects=["Mystery"], semantic_marker=True), "Include Mystery is explicit canonical subject syntax. Online availability constraints are supported in the private scope.", []),
    "rated 4+ about wizards, exclude Romance, Fiction": ({"expected_decision": "AMBIGUOUS", "execution_allowed": False, "expected_author": None, "expected_title": None, "expected_exact_text": None, "expected_exclude_terms": [], "expected_semantic_text": "wizards"}, "The trailing Fiction can be the second excluded subject or a separate requested genre. The user has not selected a unique scope for the comma list. Wizards remains an about topic under either reading.", ["expected_subjects", "expected_excluded_subjects"]),
}

NEGATIVE = {
    "Artificial intelligence excluding neural networks": ("Artificial intelligence", None, "neural networks"),
    "Computer science minus cybersecurity": ("Computer science", None, "cybersecurity"),
    "Mathematics excluding calculus": ("Mathematics", ["Calculus"], None),
    "Astronomy excluding astrology": ("Astronomy", ["Astrology"], None),
    "Fiction without Romance": ("Fiction", ["Romance"], None),
    "History excluding military campaigns": ("History", ["Military campaigns"], None),
    "Engineering minus bridge design": ("Engineering", None, "bridge design"),
    "Philosophy except ethics": ("Philosophy", ["Ethics"], None),
    "Technology excluding social media": ("Technology", ["Social media"], None),
    "Science excluding astrology and alchemy": ("Science", ["Astrology", "Alchemy"], None),
}

TYPOS = {
    "scince fiction": "science fiction",
    "histroy books": "history books",
    "mystrey stories": "mystery stories",
    "romnace": "romance",
    "artifical intelligence": "artificial intelligence",
    "astronmy for amateurs": "astronomy for amateurs",
    "philosphy about ethics": "philosophy about ethics",
    "netwroking protocols": "networking protocols",
    "ficiton about islands": "fiction about islands",
    "archtecture of bridges": "architecture of bridges",
}

ISBN = {
    "9780141036144": "9780141036144",
    "ISBN 978-0-14-103614-4": "9780141036144",
    "0-451-52493-4": "0451524934",
    "find 9780307277671": "9780307277671",
    "ISBN-10 014118776X": "014118776X",
    "978-1-59327-928-8 Python": "9781593279288",
    "book identifier 9780201616224": "9780201616224",
    "ISBN 978 0 7432 7356 5": "9780743273565",
    "ISBN: 9780000000002": "9780000000002",
}


def isbn_checksum(identifier):
    if len(identifier) == 13:
        return identifier[:3] in {"978", "979"} and sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(identifier)) % 10 == 0
    return len(identifier) == 10 and sum((10 if c == "X" else int(c)) * (10 - i) for i, c in enumerate(identifier)) % 11 == 0


records = []
for case in source["cases"]:
    family = case["family_id"]
    raw = case["query_text"]
    core = smart_core(raw) if case["search_mode"] == "SMART" else raw
    rules = ["PROJECTION_RESTRAINT"]
    unresolved = {}
    extras = {}
    if case["search_mode"] == "TITLE_AUTHOR":
        authored = {"expected_decision": "EXECUTABLE", "execution_allowed": True, "expected_author": None, "expected_subjects": [], "expected_excluded_subjects": [], "expected_exclude_terms": []}
        reason = "Explicit TITLE_AUTHOR mode preserves the entire supplied query as literal title/author search input. The words books by do not establish a SMART author equality filter. This holds equally for request-prefixed and punctuated variants."
        unresolved = {"expected_title": "The supplied schema does not define whether a literal title/author OR search is projected into title, exact_text, or a mode-specific field.", "expected_exact_text": "Literal input must remain intact, but its exact destination field is not specified by the supplied schema.", "expected_semantic_text": "Literal TITLE_AUTHOR input must not be rewritten as a semantic SMART remainder; the schema's mode-specific projection is not specified."}
        extras["literal_title_author_query"] = raw
        rules.append("LITERAL_TITLE_AUTHOR")
    elif family == "d05_by_vs_about":
        authored, reason, omitted = AUTHOR[core]
        authored = dict(authored)
        unresolved = {name: "The semantic role is established in the reason, but exact canonical or surface-normalization projection is not uniquely specified." for name in omitted}
        rules.extend(["SMART_WORDING_ONLY", "AUTHOR_VS_ABOUT", "ABOUT_IS_SOFT"])
    elif family == "d12_multi_reordering":
        authored, reason, omitted = MULTI[core]
        authored = dict(authored)
        unresolved = {name: "The final comma-separated Fiction has unresolved inclusion/exclusion scope; do not force one full subject list." for name in omitted}
        rules.extend(["SMART_WORDING_ONLY", "MULTI_CONSTRAINT_COMPOSITION", "ABOUT_IS_SOFT"])
        if omitted:
            rules.append("COMMA_SCOPE_AMBIGUITY")
        if authored.get("expected_excluded_subjects"):
            rules.append("SCOPED_CANONICAL_NEGATIVE")
    elif family == "c03_kg_negative":
        positive, negative, unknown = NEGATIVE[core]
        authored = {"expected_decision": "EXECUTABLE", "execution_allowed": True, "expected_subjects": [positive], "expected_author": None, "expected_title": None, "expected_exact_text": None}
        if negative is not None:
            authored.update(expected_excluded_subjects=negative, expected_exclude_terms=[], expected_semantic_text=None)
            reason = "The request names the scoped canonical subject " + positive + " and excludes scoped canonical subject(s) " + ", ".join(negative) + ". Subject exclusion must not also ban these words from ordinary text fields."
            rules.append("SCOPED_CANONICAL_NEGATIVE")
        else:
            reason = "The positive " + positive + " is an exact scoped canonical subject. The excluded phrase " + unknown + " is absent from the authorized GLOBAL vocabulary; no subject alias or literal exclusion is invented."
            unresolved = {name: "The excluded phrase is not an exact scoped canonical subject. Literal/topic projection is unspecified, so leave this field untouched." for name in ["expected_excluded_subjects", "expected_exclude_terms", "expected_semantic_text"]}
            rules.append("UNLISTED_NEGATIVE_UNRESOLVED")
        rules.append("SMART_WORDING_ONLY")
    elif family == "d17_typographical_noise":
        intended = TYPOS[core]
        authored = {}
        reason = "A plausible intended reading is '" + intended + "'. This establishes a spelling interpretation, not a uniquely required choice between soft search, enforced canonical correction, notice, or confirmation. The supplied contract uses may, so a decision or hard-subject gold is not forced."
        unresolved = {name: "UNSURE: correction enforcement, notice, and execution policy are not uniquely required by the supplied contract." for name in ["expected_decision", "execution_allowed", "expected_subjects", "expected_semantic_text"]}
        extras["plausible_intended_reading"] = intended
        rules.extend(["SMART_WORDING_ONLY", "TYPO_POLICY_UNRESOLVED"])
    elif family == "d22_isbn_like":
        authored = {"expected_decision": "EXECUTABLE", "execution_allowed": True, "expected_author": None, "expected_title": None, "expected_subjects": [], "expected_excluded_subjects": [], "expected_exclude_terms": []}
        if core in ISBN:
            identifier = ISBN[core]
            assert isbn_checksum(identifier), identifier
            extras["independently_identified_isbn"] = identifier
            reason = "The query supplies the valid ISBN " + identifier + ". The supplied contract accepts ISBN identity lookup in SMART, so the request is executable without a mode switch. Identifier existence in the catalog is not a precondition for attempting lookup."
            unresolved["expected_exact_text"] = "The identifier identity is established, but whether exact_text stores normalized digits or the user-supplied spelling is not defined by the schema."
            unresolved["expected_semantic_text"] = "Exact identity is established; treatment of supplementary request words or the Python cue is not specified."
            rules.append("SMART_ISBN_ACCEPTED")
        else:
            assert core == "the text 123-4-567-89012-3", core
            reason = "The user asks for the text 123-4-567-89012-3. This is an executable text query; the explicit text framing and non-ISBN prefix do not justify inventing an ISBN exact identity label."
            unresolved = {name: "Text framing is established, but exact versus soft text projection is not uniquely specified." for name in ["expected_exact_text", "expected_semantic_text"]}
            rules.append("ISBN_LIKE_TEXT_IS_TEXT")
        rules.append("SMART_WORDING_ONLY")
    else:
        raise ValueError("Unreviewed family: " + family)

    assert set(authored) <= allowed_fields
    scope_subjects = vocab[case["scope_type"]]["subjects"]
    for name in ["expected_subjects", "expected_excluded_subjects"]:
        for subject in authored.get(name, []):
            assert subject in scope_subjects, (case["query_id"], name, subject)
    field_reasons = {name: reason for name in authored}
    records.append({
        "query_id": case["query_id"],
        "query_sha256": sha(raw.encode("utf-8")),
        "query_hash_definition": "SHA-256 of exact query_text encoded as UTF-8; no trimming or normalization",
        "family_id": family,
        "scope_type": case["scope_type"],
        "search_mode": case["search_mode"],
        "review_status": "AI_REVIEWED",
        "resolution": "UNSURE" if not authored else ("PARTIAL" if unresolved else "ESTABLISHED_FIELDS"),
        "authored_fields": authored,
        "field_reasons": field_reasons,
        "semantic_reason": reason,
        "rule_ids": rules,
        "unresolved_fields": unresolved,
        **extras,
    })

assert len(records) == 607
assert len({row["query_id"] for row in records}) == 607
counts = {
    "input_cases": len(source["cases"]),
    "AI_REVIEWED": len(records),
    "records_with_authored_fields": sum(bool(row["authored_fields"]) for row in records),
    "records_without_forced_fields": sum(not row["authored_fields"] for row in records),
    "records_with_unresolved_fields": sum(bool(row["unresolved_fields"]) for row in records),
    "authored_field_values": sum(len(row["authored_fields"]) for row in records),
    "by_family": dict(sorted(collections.Counter(row["family_id"] for row in records).items())),
    "by_resolution": dict(sorted(collections.Counter(row["resolution"] for row in records).items())),
    "by_authored_decision": dict(sorted(collections.Counter(row["authored_fields"].get("expected_decision", "UNAUTHORED") for row in records).items())),
    "by_authored_field": dict(sorted(collections.Counter(name for row in records for name in row["authored_fields"]).items())),
}
artifact = {
    "artifact_type": "independently_authored_development_label_review",
    "version": 1,
    "review_status": "AI_REVIEWED",
    "stage": "BLIND_AUTHORED_BEFORE_ORIGINAL_LABEL_COMPARISON",
    "provenance": {"read_inputs_only": [INPUT.name, VOCAB.name], "parser_called": False, "api_called": False, "tests_called": False, "original_labels_read": False, "predictions_read": False, "sealed_or_calibration_or_heldout_read": False, "method": "AI independently reviewed the query-only cases as 50 SMART semantic templates and 44 literal TITLE_AUTHOR inputs; mechanically expanded only observed request/politeness/punctuation variants. No current parser behavior or original expected label informed these contracts."},
    "field_policy": "Only authored_fields are proposed normative field values. An omitted field is not an instruction to clear or relabel it. Null is an explicit authored absence. AI_REVIEWED denotes semantic review, not certainty for omitted fields.",
    "field_representation": {"expected_author": "nullable semantic author equality constraint; does not denote the literal author-side operand of TITLE_AUTHOR OR matching", "expected_title": "nullable SMART title entity constraint; TITLE_AUTHOR literal projection is deliberately unresolved", "expected_exact_text": "nullable exact-identity/literal payload; surface normalization is deliberately unresolved for ISBN and TITLE_AUTHOR", "expected_semantic_text": "nullable soft topic remaining after explicit constraints; exact surface projection is left unresolved where underspecified", "expected_subjects": "list of exact canonical scoped vocabulary labels", "expected_excluded_subjects": "list of exact canonical scoped vocabulary labels", "expected_exclude_terms": "literal text exclusions, separate from canonical subject exclusions"},
    "external_field_aliases_supplied_by_coordinator": {"expected_author": "expected_author_entity", "expected_title": "expected_title_entity", "expected_exact_text": "expected_exact_entity", "expected_semantic_text": "expected_semantic_remainder"},
    "rules": RULES,
    "counts": counts,
    "records": records,
}
OUTPUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
manifest = {
    "artifact_type": "development_blind_review_freeze_manifest",
    "stage": "FROZEN_BEFORE_ORIGINAL_LABEL_COMPARISON",
    "hash_algorithm": "SHA-256",
    "source_files": [{"path": str(path), "sha256": sha(path.read_bytes())} for path in [INPUT, VOCAB]],
    "authored_file": {"path": str(OUTPUT), "sha256": sha(OUTPUT.read_bytes())},
    "authoring_script": {"path": str(Path(__file__).resolve()), "sha256": sha(Path(__file__).read_bytes())},
    "records_canonical_json_sha256": sha(canonical_bytes(records)),
    "query_identity_manifest_sha256": sha(canonical_bytes([{"query_id": row["query_id"], "query_sha256": row["query_sha256"]} for row in records])),
    "canonical_json_definition": "UTF-8 JSON, ensure_ascii=false, recursively sorted object keys, separators comma/colon without spaces; input record order preserved",
    "counts": counts,
    "blindness_attestation": "Only the two authorized query/vocabulary inputs were read. No original labels, current predictions, parser, API, evaluator, tests, C2 report/corpus, sealed, calibration, or heldout file was read or called. Authored values and their aggregate hashes were frozen before any original-label comparison.",
}
MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"authored_path": str(OUTPUT), "authored_sha256": sha(OUTPUT.read_bytes()), "manifest_path": str(MANIFEST), "manifest_sha256": sha(MANIFEST.read_bytes()), "counts": counts}, indent=2))
