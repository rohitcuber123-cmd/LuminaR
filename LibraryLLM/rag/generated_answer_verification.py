"""Bounded, deterministic final-answer checks over already selected evidence.

The caller owns authorization and source selection. This module never fetches
evidence, grants access, generates text, or creates citations.
"""
from dataclasses import dataclass
import re

from rag.factual_evidence import VALUE, assess_factual_evidence, value_key, words


@dataclass(frozen=True)
class AnswerCheck:
    status: str  # VERIFIED, CONTRADICTED, ABSTAINED, UNKNOWN
    propositions: tuple[str, ...]
    reason: str


_QUANTITY = r"[+-]?\d+(?:\.\d+)?\s*[A-Za-z]+"
_EQ = re.compile(rf"\b({_QUANTITY})\s*(?:=|equals?|is(?:\s+equal\s+to)?)\s*({_QUANTITY})\b", re.I)
_YES_NO = re.compile(r"^(yes|no)\b[.,;!]?\s*", re.I)
_ABSTAIN = re.compile(
    r"\b(?:not enough information|insufficient (?:evidence|information)|"
    r"passages do not (?:establish|provide|contain)|cannot (?:determine|verify))\b", re.I
)
_CLAIM = re.compile(r"^(.+?)\s+(?:is|was|are|were|equals?|takes?|lasts?|requires?)\s+(.+?)[.!]?$", re.I)
_MAX_ITEMS = 12


def bounded_factual_scope(question, evidence, informational_category=None):
    """Select explicit fact questions; retain existing free-form RAG semantics."""
    if informational_category or not isinstance(question, str) or len(question) > 2000:
        return False
    if not evidence or len(evidence) > _MAX_ITEMS:
        return False
    question = question.strip()
    if re.match(r"^(?:does|do|is|was|are|were)\b", question, re.I) and _EQ.search(question):
        return True
    assessment = assess_factual_evidence(question, {"intent": "FACTUAL"}, evidence)
    if assessment is None:
        return False
    if re.match(r"^(?:is|was|are|were)\b", question, re.I):
        return True
    if not re.match(r"^(?:what|which)\b", question, re.I):
        return False
    for item in evidence:
        for clause in re.split(r"(?<=[.!?])\s+|\n+|;\s*", item.get("text", "")):
            claim = _CLAIM.fullmatch(clause.strip())
            value = value_key(claim[2]) if claim else None
            if value and value[0] in {"quantity", "identifier"}:
                return True
    return False


def _equality_status(question, passages):
    query = _EQ.search(question)
    if not query:
        return None
    left, right = value_key(query[1]), value_key(query[2])
    if not left or not right or left[0] != "quantity" or right[0] != "quantity":
        return None
    observed = []
    for passage in passages:
        for match in _EQ.finditer(passage):
            pair = (value_key(match[1]), value_key(match[2]))
            if set(pair) == {left, right}:
                observed.append(pair[0][1:] == pair[1][1:])
    if not observed or len(set(observed)) != 1 or not observed[0]:
        return None
    return left[1:] == right[1:]


def _exact_subject_present(field, passages):
    for passage in passages:
        for clause in re.split(r"(?<=[.!?])\s+|\n+|;\s*", passage):
            assignment = _CLAIM.fullmatch(clause.strip())
            if assignment and words(assignment[1]) == words(field):
                return True
    return False


def _answer_equality(question, sentence, passages):
    """Return an answer status for an explicit numeric equality, if parsed."""
    asked = _EQ.search(question)
    asserted = _EQ.fullmatch(sentence.rstrip(".!? "))
    if not asked or not asserted:
        return None
    evidence_status = _equality_status(question, passages)
    if evidence_status is None:
        return AnswerCheck("UNKNOWN", (sentence,), "numeric source relationship is ambiguous")
    asked_left = value_key(asked[1])
    asserted_left, asserted_right = value_key(asserted[1]), value_key(asserted[2])
    if asserted_left != asked_left:
        return AnswerCheck("UNKNOWN", (sentence,), "answer refers to another quantity")
    if asserted_left[1:] != asserted_right[1:]:
        return AnswerCheck("CONTRADICTED", (sentence,), "answer gives an incorrect explicit conversion")
    return AnswerCheck("VERIFIED", (sentence,), "explicit conversion matches authorized evidence")


def verify_generated_answer(question, evidence, answer, cited_chunk_ids=(), selected_source_id=None):
    """Inspect explicit claims only; never grant access or fabricate citations."""
    if not isinstance(question, str) or not isinstance(answer, str) or not evidence:
        return AnswerCheck("UNKNOWN", (), "missing question, answer, or evidence")
    if any(not isinstance(item, dict) or not isinstance(item.get("text"), str)
           for item in evidence):
        return AnswerCheck("UNKNOWN", (), "malformed authorized evidence")
    if selected_source_id is not None and any(
        item.get("document_id", item.get("work_id")) != selected_source_id for item in evidence
    ):
        return AnswerCheck("CONTRADICTED", (), "evidence is outside the selected source")
    if len(evidence) > _MAX_ITEMS or sum(len(item["text"]) for item in evidence) > 24000 or len(answer) > 4000:
        return AnswerCheck("UNKNOWN", (), "inspection budget exceeded")
    available = {item.get("chunk_id") for item in evidence}
    if cited_chunk_ids and (None in available or not set(cited_chunk_ids) <= available):
        return AnswerCheck("CONTRADICTED", (), "citation is outside authorized evidence")
    answer = answer.strip()
    passages = [item["text"] for item in evidence]
    equality = _equality_status(question, passages)
    match = _YES_NO.match(answer)
    if match:
        yes = match[1].casefold() == "yes"
        if equality is not None:
            supported = equality
        else:
            result = assess_factual_evidence(question, {"intent": "FACTUAL"}, evidence)
            if result is None or result.verdict == "UNCERTAIN":
                return AnswerCheck("UNKNOWN", (match[1],), "question is outside explicit fact grammar")
            supported = result.verdict == "SUPPORTED"
            polar_field = re.fullmatch(rf"(?:Is|Was|Are|Were)\s+(.+?)\s+({VALUE})\?", question.strip(), re.I)
            field = re.sub(r"\s+not$", "", polar_field[1], flags=re.I) if polar_field else None
            if supported and field and not _exact_subject_present(field, passages):
                return AnswerCheck("CONTRADICTED", (match[1],), "evidence assigns a different entity or field")
            if not yes and not supported:
                polar = re.fullmatch(rf"(?:Is|Was|Are|Were)\s+(.+?)\s+({VALUE})\?", question.strip(), re.I)
                if polar:
                    field, value = polar.groups()
                    field = re.sub(r"\s+not$", "", field, flags=re.I)
                    field_result = assess_factual_evidence(
                        f"What is {field}?", {"intent": "FACTUAL"}, evidence
                    )
                    negative_result = assess_factual_evidence(
                        f"Is {field} not {value}?", {"intent": "FACTUAL"}, evidence
                    )
                    if (field_result is None or field_result.verdict != "SUPPORTED") and (
                        negative_result is None or negative_result.verdict != "SUPPORTED"
                    ):
                        return AnswerCheck("UNKNOWN", (match[1],), "no explicit value establishes the negative answer")
        if yes != supported:
            return AnswerCheck("CONTRADICTED", (match[1],), "answer polarity conflicts with authorized evidence")
        remainder = answer[match.end():].strip()
        if not remainder:
            return AnswerCheck("VERIFIED", (match[1],), "explicit answer matches evidence")
        answer = remainder

    propositions = []
    has_limitation = False
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", answer.strip()):
        sentence = sentence.strip()
        if not sentence:
            continue
        if _ABSTAIN.search(sentence):
            if re.search(r"\b(?:but|however|yet)\b", sentence, re.I):
                return AnswerCheck("UNKNOWN", tuple(propositions), "limitation is mixed with another claim")
            has_limitation = True
            continue
        if equality is not None and re.fullmatch(r"(?:they|these|the two quantities)\s+are\s+equivalent[.!]?", sentence, re.I):
            propositions.append("explicit numeric equivalence")
            continue
        numeric = _answer_equality(question, sentence, passages)
        if numeric is not None:
            propositions.extend(numeric.propositions)
            if numeric.status != "VERIFIED":
                return numeric
            continue
        claim = _CLAIM.fullmatch(sentence)
        if claim:
            subject, value = claim.groups()
            if not value_key(value):
                return AnswerCheck("UNKNOWN", tuple(propositions), "unparsed claim value")
            probe = f"Is {subject} {value}?"
        elif len(re.findall(r"\w+", sentence)) <= 4 and value_key(sentence.rstrip(".!?")):
            question_field = re.fullmatch(r"(?:What|Which)\s+(?:is|was|are|were)\s+(.+?)[?]?", question.strip(), re.I)
            recorded = re.fullmatch(r"(?:What|Which)\s+(.+?)\s+(?:is|was|are|were)\s+(?:recorded|listed|documented|specified)(?:\s+for\s+.+?)?[?]?", question.strip(), re.I)
            field = question_field[1] if question_field else recorded[1] if recorded else None
            if field is None:
                return AnswerCheck("UNKNOWN", tuple(propositions), "short answer has no bound question field")
            probe = f"Is {field} {sentence.rstrip('.!?')}?"
        else:
            return AnswerCheck("UNKNOWN", tuple(propositions), "answer contains an unparsed proposition")
        propositions.append(probe)
        result = assess_factual_evidence(probe, {"intent": "FACTUAL"}, evidence)
        if result is None or result.verdict == "UNCERTAIN":
            return AnswerCheck("UNKNOWN", tuple(propositions), "explicit proposition is ambiguous")
        if result.verdict != "SUPPORTED":
            return AnswerCheck("CONTRADICTED", tuple(propositions), "answer proposition lacks matching authorized evidence")
        polar = re.fullmatch(rf"Is\s+(.+?)\s+({VALUE})\?", probe, re.I)
        field = re.sub(r"\s+not$", "", polar[1], flags=re.I) if polar else None
        if field and not _exact_subject_present(field, passages):
            return AnswerCheck("CONTRADICTED", tuple(propositions), "evidence assigns a different entity or field")
    if has_limitation:
        return (AnswerCheck("UNKNOWN", tuple(propositions), "mixed limitation and factual claims")
                if propositions else AnswerCheck("ABSTAINED", (), "answer expresses an evidence limitation"))
    return (AnswerCheck("VERIFIED", tuple(propositions), "all parsed propositions match evidence")
            if propositions else AnswerCheck("UNKNOWN", (), "no factual proposition parsed"))
