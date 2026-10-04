"""
Fast-Filter Gate for Evidence Validation (V7)

A deterministic pre-validation stage that runs BEFORE the expensive
LLM validator. Checks six alignment dimensions to decide whether
LLM validation is unnecessary or obviously impossible.

Three outcomes:
    FAST_REJECT          — evidence clearly does not support the query
    FAST_ACCEPT          — evidence strongly supports (all dimensions align)
    NEEDS_LLM_VALIDATION — ambiguous; defer to LLM validator

The fast filter does NOT independently answer the query.
It only identifies cases where semantic validation is unnecessary.

CRITICAL RULES:
- High lexical overlap alone must NEVER imply FAST_ACCEPT
- Subject-object directionality must be checked
- Polarity (negation) must be verified
- Temporal direction must be verified
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

from rag.evidence import (
    extract_important_terms,
    expand_terms_with_concepts,
    NEGATION_INDICATORS,
    MOTIVATION_INDICATORS,
    CONSEQUENCE_INDICATORS,
    REGRET_INDICATORS,
    FIRST_PERSON_PRONOUNS,
    SPEAKER_VERBS,
    _REVERSE_CONCEPT,
    CONCEPT_MAP,
)


# ============================================================
# ALIGNMENT SIGNALS
# ============================================================

@dataclass
class FastFilterSignals:
    """All alignment signals computed by the fast filter."""

    # Core alignment scores [0.0, 1.0]
    actor_score: float = 0.0
    target_score: float = 0.0
    event_score: float = 0.0

    # Boolean flags
    polarity_aligned: bool = True
    polarity_mismatch: bool = False
    temporal_aligned: bool = True
    temporal_conflict: bool = False
    relationship_check_passed: bool = True
    direction_inverted: bool = False

    # Context
    actor_in_evidence: bool = False
    target_in_evidence: bool = False
    event_terms_found: int = 0
    event_terms_total: int = 0
    negation_in_query: bool = False
    negation_in_evidence: bool = False
    evidence_confirms_action: bool = False
    mere_lexical_cooccurrence: bool = True

    # Diagnostics
    reasons: List[str] = field(default_factory=list)


# ============================================================
# TEMPORAL INDICATORS
# ============================================================

BEFORE_INDICATORS = {
    "before", "prior", "previously", "earlier",
    "preceding", "until", "ere",
}

AFTER_INDICATORS = {
    "after", "afterwards", "subsequently", "later",
    "following", "then", "next", "thereafter",
    "upon", "once",
}


# ============================================================
# RELATIONSHIP VERBS
# ============================================================

POSSESSIVE_RELATIONSHIP_PATTERNS = [
    # "X's father", "father of X"
    re.compile(r"(?P<owner>\b\w+)'s\s+(?P<relation>\w+)", re.IGNORECASE),
    re.compile(r"(?P<relation>\w+)\s+of\s+(?P<owner>\b\w+)", re.IGNORECASE),
]

EXPLICIT_RELATIONSHIP_PHRASES = [
    # "my father", "his mother"
    re.compile(r"\b(my|his|her|their|our)\s+(?P<relation>father|mother|brother|sister|wife|husband|son|daughter|friend|companion|cousin|uncle|aunt)\b", re.IGNORECASE),
]

RELATIONSHIP_TERMS = {
    "father", "mother", "brother", "sister",
    "wife", "husband", "son", "daughter",
    "friend", "companion", "cousin", "uncle",
    "aunt", "fiancé", "fiancée", "betrothed",
    "bride", "groom", "lover", "partner",
}


# ============================================================
# CORE: COMPUTE ALIGNMENT SIGNALS
# ============================================================

def compute_alignment_signals(
    question: str,
    intent_data: dict,
    evidence_text: str,
) -> FastFilterSignals:
    """
    Compute deterministic alignment signals between a query and evidence.

    Parameters:
        question:      the user's original question
        intent_data:   structured intent from LLM (actor, action, target, polarity, etc.)
        evidence_text: the candidate evidence text (may be combined top-3)

    Returns:
        FastFilterSignals with all alignment dimensions populated
    """

    signals = FastFilterSignals()

    if not question or not evidence_text or not intent_data:
        signals.reasons.append("missing input")
        return signals

    q_lower = question.lower().strip()
    ev_lower = evidence_text.lower()
    ev_words = set(re.findall(r"\b[a-zA-Z\']+\b", ev_lower))

    intent = intent_data.get("intent", "FACTUAL")
    actor = intent_data.get("actor", "")
    action = intent_data.get("action", "")
    target = intent_data.get("target", "")
    polarity = intent_data.get("polarity", "positive")
    temporal_relation = intent_data.get("temporal_relation", "")

    # --------------------------------------------------------
    # 1. ACTOR ALIGNMENT
    #
    # IMPORTANT: Literary texts often use first-person narration.
    # If the evidence contains "I"/"my"/"me" pronouns, the
    # narrator IS the actor — do NOT reject for actor absence.
    # --------------------------------------------------------

    # Detect first-person narration in evidence
    first_person_tokens = {"i", "my", "me", "myself", "mine"}
    evidence_has_first_person = bool(ev_words & first_person_tokens)

    if actor:
        actor_terms = extract_important_terms(actor)
        if actor_terms:
            actor_found = sum(1 for t in actor_terms if t in ev_words)
            signals.actor_score = actor_found / len(actor_terms)
            signals.actor_in_evidence = actor_found > 0

            # If actor not found literally but evidence is first-person,
            # the narrator may BE the actor — treat as ambiguous, not absent
            if signals.actor_score == 0.0 and evidence_has_first_person:
                signals.actor_score = 0.5
                signals.actor_in_evidence = True
                signals.reasons.append(
                    f"actor '{actor}' not literal but first-person narration detected"
                )
            elif signals.actor_score == 0.0:
                signals.reasons.append(
                    f"actor '{actor}' absent from evidence"
                )
        else:
            # Actor terms are too short / stopwords
            signals.actor_score = 0.5
            signals.actor_in_evidence = True
    else:
        # No actor specified (e.g., CONSEQUENCE queries)
        signals.actor_score = 0.5
        signals.actor_in_evidence = True

    # --------------------------------------------------------
    # 2. TARGET ALIGNMENT
    # --------------------------------------------------------

    if target:
        target_terms = extract_important_terms(target)
        if target_terms:
            target_found = sum(1 for t in target_terms if t in ev_words)
            signals.target_score = target_found / len(target_terms)
            signals.target_in_evidence = target_found > 0

            if signals.target_score == 0.0:
                signals.reasons.append(
                    f"target '{target}' absent from evidence"
                )
        else:
            signals.target_score = 0.5
            signals.target_in_evidence = True
    else:
        signals.target_score = 0.5
        signals.target_in_evidence = True

    # --------------------------------------------------------
    # 3. ACTION / EVENT ALIGNMENT
    # --------------------------------------------------------

    if action:
        action_terms = extract_important_terms(action)
        if action_terms:
            expanded_action, _ = expand_terms_with_concepts(action_terms)

            action_found = 0
            for t in action_terms:
                if t in ev_words:
                    action_found += 1
                elif t in _REVERSE_CONCEPT:
                    root = _REVERSE_CONCEPT[t]
                    family = CONCEPT_MAP[root] | {root}
                    if family & ev_words:
                        action_found += 1

            signals.event_terms_found = action_found
            signals.event_terms_total = len(action_terms)
            signals.event_score = action_found / len(action_terms) if action_terms else 0.0

            if signals.event_score == 0.0:
                signals.reasons.append(
                    f"action '{action}' terms absent from evidence"
                )
        else:
            signals.event_score = 0.5
    else:
        signals.event_score = 0.5

    # --------------------------------------------------------
    # 4. POLARITY CONSISTENCY
    # --------------------------------------------------------

    signals.negation_in_query = (polarity == "negative")

    # Check for negation indicators in evidence
    ev_negation_terms = ev_words & set(NEGATION_INDICATORS)
    # Also check multi-word negation phrases
    for ind in NEGATION_INDICATORS:
        if " " in ind and ind in ev_lower:
            ev_negation_terms.add(ind)

    signals.negation_in_evidence = len(ev_negation_terms) > 0

    if intent in ("NEGATED_MOTIVATION",):
        # Query asks "why doesn't X do Y?"
        # Evidence must NOT show X doing Y without negation
        # If evidence says "X did Y" (positive action, no negation) → polarity mismatch
        if signals.actor_in_evidence and signals.event_score >= 0.5:
            if not signals.negation_in_evidence:
                # Evidence describes X doing Y positively → mismatch
                signals.polarity_aligned = False
                signals.polarity_mismatch = True
                signals.evidence_confirms_action = True
                signals.reasons.append(
                    "polarity mismatch: query is negated but evidence confirms positive action"
                )

    elif polarity == "positive" and intent == "MOTIVATION":
        # Query asks "why does X do Y?"
        # If evidence contains negation near the action, it is ambiguous
        # (e.g. incidental negation in literary dialogue or narrative).
        # We must NOT FAST_REJECT on mere co-occurrence, but we prevent
        # FAST_ACCEPT so the LLM validator can resolve the nuance.
        if signals.actor_in_evidence and signals.event_score >= 0.5:
            action_terms_set = set(extract_important_terms(action)) if action else set()
            if action_terms_set and signals.negation_in_evidence:
                ev_sentences = [s.strip() for s in re.split(r'[.!?]+', ev_lower) if s.strip()]
                for sent in ev_sentences:
                    sent_words = set(re.findall(r"\b[a-zA-Z\']+\b", sent))
                    has_action = bool(action_terms_set & sent_words)
                    has_neg = bool(set(NEGATION_INDICATORS) & sent_words)
                    if has_action and has_neg:
                        signals.polarity_aligned = False
                        signals.reasons.append(
                            "negation near action terms in positive query; deferring to LLM"
                        )
                        break

    # --------------------------------------------------------
    # 5. TEMPORAL CONSISTENCY
    # --------------------------------------------------------

    if temporal_relation:
        tr_lower = temporal_relation.lower()

        if tr_lower in ("before",):
            # Query asks about something BEFORE event X
            # If evidence only describes AFTER event X → conflict
            ev_has_after = bool(ev_words & AFTER_INDICATORS)
            ev_has_before = bool(ev_words & BEFORE_INDICATORS)

            if ev_has_after and not ev_has_before:
                # Check if "after" relates to the event in question
                action_terms_set = set(extract_important_terms(action)) if action else set()
                if action_terms_set:
                    ev_sentences = [s.strip() for s in re.split(r'[.!?]+', ev_lower) if s.strip()]
                    for sent in ev_sentences:
                        sent_words = set(re.findall(r"\b[a-zA-Z\']+\b", sent))
                        has_action = bool(action_terms_set & sent_words)
                        has_after = bool(AFTER_INDICATORS & sent_words)
                        if has_action and has_after:
                            signals.temporal_conflict = True
                            signals.temporal_aligned = False
                            signals.reasons.append(
                                "temporal conflict: query asks BEFORE but evidence describes AFTER"
                            )
                            break

        elif tr_lower in ("after",):
            ev_has_after = bool(ev_words & AFTER_INDICATORS)
            ev_has_before = bool(ev_words & BEFORE_INDICATORS)

            if ev_has_before and not ev_has_after:
                action_terms_set = set(extract_important_terms(action)) if action else set()
                if action_terms_set:
                    ev_sentences = [s.strip() for s in re.split(r'[.!?]+', ev_lower) if s.strip()]
                    for sent in ev_sentences:
                        sent_words = set(re.findall(r"\b[a-zA-Z\']+\b", sent))
                        has_action = bool(action_terms_set & sent_words)
                        has_before = bool(BEFORE_INDICATORS & sent_words)
                        if has_action and has_before:
                            signals.temporal_conflict = True
                            signals.temporal_aligned = False
                            signals.reasons.append(
                                "temporal conflict: query asks AFTER but evidence describes BEFORE"
                            )
                            break

    # --------------------------------------------------------
    # 6. RELATIONSHIP / ENTITY-DIRECTION CONSISTENCY
    # --------------------------------------------------------

    if intent == "RELATIONSHIP" and actor and target:
        # For "Who is X's Y?" we need evidence that explicitly
        # establishes Y as a role/relation OF X, not just
        # co-occurrence of X and Y.

        actor_terms = set(extract_important_terms(actor))
        target_terms = set(extract_important_terms(target))

        # Check if the relationship is explicitly stated
        relationship_found = False

        # Pattern 1: "X's Y" or "Y of X" where Y is a relationship term
        for pat in POSSESSIVE_RELATIONSHIP_PATTERNS:
            for m in pat.finditer(ev_lower):
                owner = m.group("owner")
                relation = m.group("relation")

                owner_is_actor = any(
                    at in owner for at in actor_terms
                ) if actor_terms else False

                relation_is_target = (
                    relation in target_terms
                    or relation in RELATIONSHIP_TERMS
                )

                if owner_is_actor and relation_is_target:
                    relationship_found = True
                    break

            if relationship_found:
                break

        # Pattern 2: First-person narration: "My father, [Name]"
        if not relationship_found:
            for pat in EXPLICIT_RELATIONSHIP_PHRASES:
                for m in pat.finditer(ev_lower):
                    relation = m.group("relation")
                    if relation in target_terms or relation in RELATIONSHIP_TERMS:
                        # Check if actor name appears nearby
                        match_pos = m.start()
                        context_window = ev_lower[max(0, match_pos - 100):match_pos + 200]
                        if any(at in context_window for at in actor_terms):
                            relationship_found = True
                            break

                if relationship_found:
                    break

        if not relationship_found:
            # Mere co-occurrence of actor and target terms is NOT enough
            if signals.actor_in_evidence and signals.target_in_evidence:
                signals.relationship_check_passed = False
                signals.mere_lexical_cooccurrence = True
                signals.reasons.append(
                    "relationship not explicitly established (mere co-occurrence)"
                )
            else:
                signals.relationship_check_passed = False
                signals.reasons.append(
                    "relationship terms missing from evidence"
                )
        else:
            signals.relationship_check_passed = True
            signals.mere_lexical_cooccurrence = False
            signals.reasons.append(
                "explicit relationship found in evidence"
            )

    # --------------------------------------------------------
    # 6b. SUBJECT-OBJECT DIRECTION CHECK
    #
    # For motivation queries like "Why does X hate Y?" vs
    # "Why does Y hate X?", check directionality.
    # --------------------------------------------------------

    if intent in ("MOTIVATION", "REGRET") and actor and action:
        actor_terms = set(extract_important_terms(actor))
        target_terms = set(extract_important_terms(target)) if target else set()
        
        # Prevent verb positions from being conflated with noun positions
        base_action_terms = set(extract_important_terms(action)) - actor_terms - target_terms
        
        # Expand action terms with concepts so we catch variations (e.g. hunt -> hunted, fear -> feared)
        action_terms_list, _ = expand_terms_with_concepts(list(base_action_terms))
        action_terms = set(action_terms_list)

        if actor_terms and target_terms and action_terms:
            # Check if evidence has SUBJECT doing ACTION to TARGET
            # vs TARGET doing ACTION to SUBJECT
            ev_sentences = [s.strip() for s in re.split(r'[.!?]+', ev_lower) if s.strip()]

            subject_acts_on_target = False
            target_acts_on_subject = False

            for sent in ev_sentences:
                sent_words = set(re.findall(r"\b[a-zA-Z\']+\b", sent))

                has_actor = bool(actor_terms & sent_words)
                has_target = bool(target_terms & sent_words)
                
                # For action terms, use prefix matching to handle conjugations (e.g., hunt -> hunted)
                has_action = any(sw.startswith(at) for at in action_terms for sw in sent_words)

                if has_action and has_actor and has_target:
                    # Check word order: actor before action before target?
                    # This is approximate but useful
                    actor_positions = []
                    target_positions = []
                    action_positions = []

                    words_list = re.findall(r"\b[a-zA-Z\']+\b", sent)
                    for idx, w in enumerate(words_list):
                        if w in actor_terms:
                            actor_positions.append(idx)
                        if w in target_terms:
                            target_positions.append(idx)
                        if any(w.startswith(at) for at in action_terms):
                            action_positions.append(idx)

                    if actor_positions and action_positions:
                        min_actor = min(actor_positions)
                        min_action = min(action_positions)
                        if min_actor < min_action:
                            subject_acts_on_target = True
                        elif target_positions:
                            min_target = min(target_positions)
                            if min_target < min_action:
                                target_acts_on_subject = True

            if target_acts_on_subject and not subject_acts_on_target:
                signals.direction_inverted = True
                signals.reasons.append(
                    f"direction inverted: evidence shows {target} acting, not {actor}"
                )

    # --------------------------------------------------------
    # DETERMINE MERE LEXICAL CO-OCCURRENCE
    #
    # Even if actor and event terms are present, they may not
    # be semantically connected. Check for sentence-level
    # co-occurrence of actor + event.
    # --------------------------------------------------------

    if intent != "RELATIONSHIP":
        actor_terms_set = set(extract_important_terms(actor)) if actor else set()
        action_terms_set = set(extract_important_terms(action)) if action else set()

        if actor_terms_set and action_terms_set:
            ev_sentences = [s.strip() for s in re.split(r'[.!?]+', ev_lower) if s.strip()]
            colocated = False

            for i, sent in enumerate(ev_sentences):
                sent_words = set(re.findall(r"\b[a-zA-Z\']+\b", sent))

                # Check current + adjacent sentences
                window_words = set(sent_words)
                if i > 0:
                    prev_words = set(re.findall(
                        r"\b[a-zA-Z\']+\b",
                        ev_sentences[i - 1]
                    ))
                    window_words |= prev_words
                if i + 1 < len(ev_sentences):
                    next_words = set(re.findall(
                        r"\b[a-zA-Z\']+\b",
                        ev_sentences[i + 1]
                    ))
                    window_words |= next_words

                has_actor = bool(actor_terms_set & window_words)

                # Check action with concept expansion
                has_action = False
                for t in action_terms_set:
                    if t in window_words:
                        has_action = True
                        break
                    if t in _REVERSE_CONCEPT:
                        root = _REVERSE_CONCEPT[t]
                        family = CONCEPT_MAP[root] | {root}
                        if family & window_words:
                            has_action = True
                            break

                if has_actor and has_action:
                    colocated = True
                    break

            signals.mere_lexical_cooccurrence = not colocated
        elif not actor_terms_set:
            signals.mere_lexical_cooccurrence = False

    return signals


# ============================================================
# CORE: FAST FILTER DECISION
# ============================================================

def fast_filter_decision(signals: FastFilterSignals) -> str:
    """
    Determine whether to FAST_REJECT, FAST_ACCEPT, or defer
    to LLM validation based on computed alignment signals.

    Returns one of:
        "FAST_REJECT"
        "FAST_ACCEPT"
        "NEEDS_LLM_VALIDATION"
    """

    # --------------------------------------------------------
    # FAST_REJECT CONDITIONS
    #
    # CONSERVATIVE: Only reject on strong structural signals
    # (polarity, temporal, directionality). Actor/event absence
    # is deferred to LLM because literary text uses first-person
    # narration, synonyms, and indirect references.
    # --------------------------------------------------------

    # R1: Polarity mismatch (negation inverted)
    if signals.polarity_mismatch:
        signals.reasons.append("FAST_REJECT: polarity mismatch")
        return "FAST_REJECT"

    # R2: Temporal conflict (BEFORE/AFTER reversed)
    if signals.temporal_conflict:
        signals.reasons.append("FAST_REJECT: temporal conflict")
        return "FAST_REJECT"

    # R3: Subject-object direction inverted
    if signals.direction_inverted:
        signals.reasons.append("FAST_REJECT: direction inverted")
        return "FAST_REJECT"

    # --------------------------------------------------------
    # FAST_ACCEPT CONDITIONS
    #
    # ALL dimensions must align. High lexical overlap alone
    # is NEVER sufficient.
    # --------------------------------------------------------

    if (signals.actor_score >= 0.8
            and signals.event_score >= 0.6
            and signals.polarity_aligned
            and signals.temporal_aligned
            and signals.relationship_check_passed
            and not signals.direction_inverted
            and not signals.mere_lexical_cooccurrence):
        signals.reasons.append("FAST_ACCEPT: all dimensions aligned")
        return "FAST_ACCEPT"

    # --------------------------------------------------------
    # DEFAULT: NEEDS LLM VALIDATION
    # --------------------------------------------------------

    signals.reasons.append("NEEDS_LLM_VALIDATION: ambiguous signals")
    return "NEEDS_LLM_VALIDATION"


# ============================================================
# PUBLIC API
# ============================================================

def run_fast_filter(
    question: str,
    intent_data: dict,
    evidence_items: list,
    mode: str = "combined",
) -> dict:
    """
    Run the fast filter on evidence items.

    Parameters:
        question:       the user's original question
        intent_data:    structured intent data
        evidence_items: list of chunk dicts with "text" key
        mode:           "combined" (concat top-3) or "individual"

    Returns:
        dict with:
            decision:   FAST_REJECT | FAST_ACCEPT | NEEDS_LLM_VALIDATION
            signals:    FastFilterSignals as dict
            reasons:    list of explanation strings
    """

    if not evidence_items:
        return {
            "decision": "FAST_REJECT",
            "signals": {},
            "reasons": ["no evidence provided"],
        }

    # Build evidence text
    if mode == "combined":
        evidence_text = "\n\n".join(
            item.get("text", "") for item in evidence_items[:3]
        )
    else:
        evidence_text = evidence_items[0].get("text", "")

    # Compute signals
    signals = compute_alignment_signals(
        question=question,
        intent_data=intent_data,
        evidence_text=evidence_text,
    )

    # Make decision
    decision = fast_filter_decision(signals)

    return {
        "decision": decision,
        "signals": {
            "actor_score": signals.actor_score,
            "target_score": signals.target_score,
            "event_score": signals.event_score,
            "polarity_aligned": signals.polarity_aligned,
            "polarity_mismatch": signals.polarity_mismatch,
            "temporal_aligned": signals.temporal_aligned,
            "temporal_conflict": signals.temporal_conflict,
            "relationship_check_passed": signals.relationship_check_passed,
            "direction_inverted": signals.direction_inverted,
            "actor_in_evidence": signals.actor_in_evidence,
            "target_in_evidence": signals.target_in_evidence,
            "event_terms_found": signals.event_terms_found,
            "event_terms_total": signals.event_terms_total,
            "negation_in_query": signals.negation_in_query,
            "negation_in_evidence": signals.negation_in_evidence,
            "evidence_confirms_action": signals.evidence_confirms_action,
            "mere_lexical_cooccurrence": signals.mere_lexical_cooccurrence,
        },
        "reasons": signals.reasons,
    }
