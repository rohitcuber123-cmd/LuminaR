import re


# ============================================================
# CONFIGURATION — HYBRID SCORING WEIGHTS
# ============================================================

CROSSENCODER_WEIGHT = 0.30
EVIDENCE_WEIGHT = 0.55
FAISS_WEIGHT = 0.15


# ============================================================
# GENERIC CONCEPT MAP
#
# Maps root concepts to synonyms / morphological variants.
#
# These are generic literary and thematic concepts.
# No book-specific entries.
# ============================================================

CONCEPT_MAP = {

    "create": {
        "creation", "created", "creating",
        "creator", "produce", "construct",
        "make", "form", "animate",
        "animation", "fashion", "build",
        "creature", "monster", "being",
    },

    "life": {
        "living", "alive", "lifeless",
        "death", "existence",
        "vital", "spark",
    },

    "motivation": {
        "desire", "ambition", "curiosity",
        "purpose", "reason", "sought",
        "wanted", "hoped", "wished",
        "intended", "driven", "compelled",
    },

    "knowledge": {
        "science", "philosophy", "study",
        "learn", "discovery", "research",
        "experiment", "inquiry", "wisdom",
    },

    "power": {
        "control", "dominion", "mastery",
        "authority", "command", "rule",
        "strength", "might",
    },

    "fear": {
        "dread", "terror", "horror",
        "fright", "alarm", "anxiety",
        "afraid", "frightened", "terrified",
    },

    "love": {
        "affection", "devotion", "attachment",
        "tenderness", "compassion", "beloved",
        "passion", "fond",
    },

    "evil": {
        "wicked", "malice", "villain",
        "sin", "corrupt", "depravity",
        "fiend", "malicious", "cruel",
    },

    "journey": {
        "travel", "voyage", "expedition",
        "passage", "quest", "wander",
        "adventure", "roam",
    },

    "death": {
        "dying", "dead", "mortal",
        "mortality", "funeral", "grave",
        "perish", "corpse", "tomb",
    },

    "nature": {
        "natural", "landscape", "wilderness",
        "mountain", "sea", "storm",
        "forest", "earth",
    },

    "guilt": {
        "remorse", "shame", "regret",
        "conscience", "repentance", "blame",
        "responsible", "fault",
    },

    "revenge": {
        "vengeance", "retribution",
        "retaliation", "avenge",
    },

    "isolation": {
        "solitude", "lonely", "loneliness",
        "alone", "exile", "outcast",
        "abandoned", "forsaken",
    },

    "secret": {
        "mystery", "hidden", "conceal",
        "unknown", "enigma", "obscure",
    },

    "supernatural": {
        "ghost", "spirit", "apparition",
        "phantom", "spectre", "undead",
        "vampire",
    },
}

# Build reverse lookup: word → set of concept roots
_REVERSE_CONCEPT = {}
for _root, _synonyms in CONCEPT_MAP.items():
    _REVERSE_CONCEPT[_root] = _root
    for _syn in _synonyms:
        _REVERSE_CONCEPT[_syn] = _root


# ============================================================
# CAUSAL / EXPLANATORY INDICATORS
#
# Generic words and phrases that signal causal or
# explanatory language in a passage.
# ============================================================

CAUSAL_INDICATORS = {
    # Conjunctions / transitions
    "because", "since", "therefore", "thus",
    "hence", "consequently", "accordingly",

    # Motivational verbs / nouns
    "motivated", "desire", "wanted", "sought",
    "believed", "determined", "resolved",
    "purpose", "ambition", "curiosity",
    "intended", "reason", "cause",

    # Result / intention phrases
    "led to", "in order to", "so that",
    "driven by", "compelled", "inspired",
    "urged", "hoped", "wished",
}


# ============================================================
# MOTIVATION INDICATORS
#
# Generic words that signal forward-looking intention,
# ambition, desire, curiosity, or purpose. These indicate
# a passage explains WHY someone does something.
#
# Used for causal direction detection.
# ============================================================

MOTIVATION_INDICATORS = {
    "ambition", "aspire", "aspired", "aspiring",
    "curiosity", "curious",
    "desire", "desired", "desiring",
    "discover", "discovery",
    "dream", "dreamed", "dreamt",
    "endeavour", "endeavor",
    "enterprise",
    "glory", "glorious",
    "goal", "hoped", "hoping",
    "imagination", "imagined",
    "inquire", "inquiry",
    "inspiration", "inspired",
    "intend", "intended", "intention",
    "investigate", "investigation",
    "longed", "longing",
    "mastery", "mastered",
    "motivation", "motivated",
    "passion", "passionate",
    "plan", "planned", "planning",
    "power", "powers",
    "prospect", "prospects",
    "pursue", "pursued", "pursuit",
    "purpose",
    "resolved", "resolution",
    "science", "scientific",
    "secret", "secrets",
    "sought", "seek", "seeking",
    "study", "studied",
    "undertaking",
    "venture",
    "vision", "visionary",
    "wanted", "wanting",
    "wished", "wishing",
    "wonder", "wondered",
    "zeal", "zealous",
}


# ============================================================
# CONSEQUENCE INDICATORS
#
# Generic words that signal aftermath, reaction, result,
# regret, or consequence. These indicate a passage
# describes WHAT HAPPENED AFTER, not WHY.
#
# Used for causal direction detection.
# ============================================================

CONSEQUENCE_INDICATORS = {
    "abandoned", "abandonment",
    "aftermath",
    "anguish",
    "ashamed", "shame",
    "blame", "blamed",
    "consequence", "consequences",
    "cursed",
    "despair", "despairing",
    "destroyed", "destruction",
    "dread", "dreaded",
    "fled", "flee", "fleeing",
    "grief", "grieved",
    "guilt", "guilty",
    "hatred",
    "horror", "horrified",
    "lament", "lamented",
    "miserable", "misery",
    "mourn", "mourned", "mourning",
    "punishment", "punished",
    "regret", "regretted",
    "remorse",
    "repent", "repentance",
    "result", "resulted",
    "revenge", "vengeance",
    "ruin", "ruined",
    "shudder", "shuddered",
    "suffered", "suffering",
    "torment", "tormented",
    "tragedy", "tragic",
    "wretched", "wretchedness",
}


# ============================================================
# SPEAKER VERBS
#
# Generic verbs indicating speech or internal thought.
# Used for the speaker-aware heuristic.
# ============================================================

SPEAKER_VERBS = {
    "said",
    "replied",
    "answered",
    "cried",
    "exclaimed",
    "observed",
    "thought",
    "reflected",
    "added",
    "continued",
    "whispered"
}


# ============================================================
# FIRST PERSON PRONOUNS
# ============================================================

FIRST_PERSON_PRONOUNS = {
    "i", "my", "me", "myself", "we", "our"
}


# ============================================================
# PSYCHOLOGICAL & TEMPORAL INDICATORS
# ============================================================

PSYCHOLOGICAL_VERBS = {
    "hate", "hates", "hated", "love", "loves", "loved",
    "fear", "fears", "feared", "resent", "resents", "resented",
    "despise", "despises", "despised", "anger", "angers", "angered"
}

ORIGIN_TEMPORAL_CUES = {
    "first", "initially", "begins", "starts", "motivates",
    "come to", "origin", "begin", "start", "initial"
}

LATER_TEMPORAL_CUES = {
    "after", "later", "eventually", "subsequently", "then"
}


# ============================================================
# QUESTION INTENT DETECTION
#
# Lightweight regex patterns that classify a question
# into a broad intent category (fallback if no semantic intent).
# ============================================================

NEGATION_INDICATORS = {
    "refuse", "refused", "refusing",
    "avoid", "avoided", "avoiding",
    "abandon", "abandoned", "abandoning",
    "destroy", "destroyed", "destroying",
    "decide against", "decided against",
    "doesn't", "did not", "didn't", "not", "never",
    "prevent", "prevented", "preventing",
    "stop", "stopped", "stopping",
    "reject", "rejected", "rejecting",
    "deny", "denied", "denying",
    "hadn't", "had not",
    "hasn't", "has not",
    "haven't", "have not",
    "isn't", "is not",
    "aren't", "are not",
    "wasn't", "was not",
    "weren't", "were not",
    "can't", "cannot", "couldn't", "could not",
    "won't", "will not", "wouldn't", "would not",
    "shouldn't", "should not",
    "don't", "do not"
}

REGRET_INDICATORS = {
    "regret", "regretted", "regretting",
    "remorse", "remorseful",
    "guilt", "guilty",
    "repent", "repentance", "repented",
    "shame", "ashamed",
    "sorrow", "sorrowful",
    "lament", "lamented", "lamenting"
}

REACTION_INDICATORS = {
    "feel", "felt", "feeling",
    "react", "reacted", "reaction",
    "horror", "horrified", "horrifying",
    "dread", "dreaded",
    "shock", "shocked",
    "surprise", "surprised",
    "terror", "terrified",
    "fear", "feared",
    "joy", "joyful",
    "delight", "delighted",
    "disgust", "disgusted",
    "shudder", "shuddered"
}


_INTENT_PATTERNS = [

    (
        "causal",
        re.compile(
            r"(?i)\b(?:"
            r"why\b"
            r"|what\s+motivat"
            r"|what\s+caus"
            r"|what\s+led\s+to"
            r"|what\s+driv"
            r"|what\s+compel"
            r"|how\s+did\s+\w+\s+come\s+to"
            r"|what\s+is\s+the\s+reason"
            r"|what\s+made\s+\w+\s"
            r")"
        )
    ),

    (
        "descriptive",
        re.compile(
            r"(?i)\b(?:"
            r"what\s+is\b"
            r"|what\s+are\b"
            r"|describe\b"
            r"|who\s+is\b"
            r"|who\s+are\b"
            r"|explain\s+what"
            r")"
        )
    ),

    (
        "temporal",
        re.compile(
            r"(?i)\b(?:"
            r"when\s+did"
            r"|when\s+does"
            r"|what\s+happen"
            r"|after\s+\w+\s"
            r"|before\s+\w+\s"
            r"|sequence\s+of"
            r")"
        )
    ),

    (
        "procedural",
        re.compile(
            r"(?i)\b(?:"
            r"how\s+does"
            r"|how\s+is"
            r"|what\s+process"
            r"|what\s+steps"
            r"|how\s+to"
            r")"
        )
    ),

]


# ============================================================
# STOPWORDS FOR TERM EXTRACTION
# ============================================================

_STOPWORDS = {
    "a", "an", "the", "is", "are", "was",
    "were", "be", "been", "being", "have",
    "has", "had", "do", "does", "did",
    "will", "would", "could", "should",
    "may", "might", "shall", "can",
    "and", "or", "but", "if", "of",
    "at", "by", "for", "with", "about",
    "to", "from", "in", "on", "into",
    "it", "its", "this", "that", "these",
    "those", "he", "she", "they", "we",
    "you", "i", "me", "him", "her",
    "us", "them", "my", "his", "our",
    "your", "their", "not", "no", "nor",
    "so", "as", "up", "out", "just",
    "what", "when", "where", "why", "who",
    "how", "which", "whom", "whose",
    "very", "too", "also", "then",
    "than", "more", "most", "some",
    "any", "all", "each", "every",
}


# ============================================================
# DETECT QUERY INTENT
# ============================================================

def detect_query_intent(query):
    """
    Classify the broad intent of a question.

    Returns one of:
        "causal", "descriptive", "temporal",
        "procedural", or None

    Uses lightweight regex matching — no model.
    """

    if not query:
        return None

    for intent, pattern in _INTENT_PATTERNS:

        if pattern.search(query):
            return intent

    return None


# ============================================================
# EXTRACT IMPORTANT TERMS
# ============================================================

def extract_important_terms(text):
    """
    Extract non-stopword terms from text.

    Returns a list of lowercased terms (len >= 3)
    in the order they appear.
    """

    if not text:
        return []

    words = re.findall(
        r"\b[a-zA-Z]{3,}\b",
        text.lower()
    )

    return [
        w for w in words
        if w not in _STOPWORDS
    ]


# ============================================================
# EXPAND TERMS WITH CONCEPT MAP
# ============================================================

def expand_terms_with_concepts(terms):
    """
    For each term, if it matches a concept root or
    synonym in CONCEPT_MAP, collect all related terms.

    Returns:
        expanded: set of all expanded terms
        matched_roots: set of concept root names
    """

    expanded = set()
    matched_roots = set()

    for term in terms:

        # Direct root match
        if term in CONCEPT_MAP:

            expanded.add(term)
            expanded.update(CONCEPT_MAP[term])
            matched_roots.add(term)

        # Reverse lookup — term is a synonym
        elif term in _REVERSE_CONCEPT:

            root = _REVERSE_CONCEPT[term]
            expanded.add(root)
            expanded.update(CONCEPT_MAP[root])
            matched_roots.add(root)

        else:
            # Keep the term even if no concept match
            expanded.add(term)

    return expanded, matched_roots


# ============================================================
# EXTRACT BIGRAMS
# ============================================================

def _extract_bigrams(terms):
    """
    Generate adjacent term pairs as phrases.
    """

    bigrams = []

    for i in range(len(terms) - 1):

        bigrams.append(
            f"{terms[i]} {terms[i + 1]}"
        )

    return bigrams


# ============================================================
# MAX CHUNK INDEX CACHE
# ============================================================

_MAX_CHUNK_CACHE = {}

def get_max_chunk_index(work_id, all_chunks_dict):
    if work_id in _MAX_CHUNK_CACHE:
        return _MAX_CHUNK_CACHE[work_id]
    max_idx = 1
    if all_chunks_dict:
        prefix = f"{work_id}_"
        for k in all_chunks_dict.keys():
            if k.startswith(prefix):
                try:
                    idx = int(k.split("_")[-1])
                    if idx > max_idx:
                        max_idx = idx
                except: pass
    _MAX_CHUNK_CACHE[work_id] = max_idx
    return max_idx


# ============================================================
# CALCULATE EVIDENCE SCORE
# ============================================================

def calculate_evidence_score(
    original_query,
    expanded_queries,
    chunk_text,
    chunk_metadata=None,
    all_chunks_dict=None,
    intent_data=None
):
    """
    Calculate a deterministic evidence score for
    how well a chunk addresses the original query.

    Parameters:
        original_query:   the user's original question
        expanded_queries: list of retrieval queries
        chunk_text:       the candidate chunk's text

    Returns:
        score:    float in [0.0, 1.0]
        signals:  list of string explanations
        metrics:  dict containing raw diagnostic scores
    """

    metrics = {
        "actor_alignment": 0.0,
        "event_alignment": 0.0,
        "local_causal_score": 0.0,
        "speaker_score": 0.0,
        "first_person_narrative": 0.0,
        "motivation_strength": 0.0,
        "consequence_strength": 0.0,
        "motivation_priority": 0.0,
        "directional_subject_alignment": 0.5,
        "temporal_phase_alignment": 0.5,
    }

    if not original_query or not chunk_text:
        return 0.0, [], metrics

    signals = []
    chunk_lower = chunk_text.lower()
    chunk_words = set(re.findall(r"\b[a-zA-Z\']+\b", chunk_lower))

    # --------------------------------------------------------
    # DETECT QUERY INTENT
    # --------------------------------------------------------

    semantic_intent = None
    if intent_data and intent_data.get("intent"):
        semantic_intent = intent_data["intent"].upper()
        intent = semantic_intent
    else:
        intent = detect_query_intent(
            original_query
        )

    is_causal = intent in ("causal", "MOTIVATION", "NEGATED_MOTIVATION", "REGRET")
    is_temporal = intent in ("temporal", "CONSEQUENCE", "REACTION")

    # --------------------------------------------------------
    # EXTRACT IMPORTANT QUERY TERMS
    # --------------------------------------------------------

    query_terms = extract_important_terms(
        original_query
    )

    if not query_terms:
        return 0.0, [], metrics

    # --------------------------------------------------------
    # EXPAND WITH CONCEPT MAP
    # --------------------------------------------------------

    expanded_terms, matched_roots = (
        expand_terms_with_concepts(
            query_terms
        )
    )

    if semantic_intent and intent_data.get("actor"):
        actor_terms = extract_important_terms(intent_data["actor"])
    else:
        actor_terms = [t for t in query_terms if t not in matched_roots and t not in _REVERSE_CONCEPT]
        if not actor_terms:
            actor_terms = query_terms
            
    if semantic_intent and intent_data.get("action"):
        action_terms = extract_important_terms(intent_data["action"])
        if intent_data.get("target"):
            action_terms.extend(extract_important_terms(intent_data["target"]))
        event_terms, _ = expand_terms_with_concepts(action_terms)
    else:
        event_terms = expanded_terms

    # --------------------------------------------------------
    # SENTENCE-BASED PROXIMITY ANALYSIS
    # --------------------------------------------------------

    first_person_narrative = 0.0
    if actor_terms and chunk_metadata and all_chunks_dict:
        meta_text = f"{chunk_metadata.get('title', '')} {chunk_metadata.get('chapter', '')}".lower()
        actor_in_meta = any(a in meta_text for a in actor_terms)
        
        actor_in_neighbors = False
        if not actor_in_meta:
            chunk_id = chunk_metadata.get("chunk_id", "")
            if "_" in chunk_id:
                prefix, idx_str = chunk_id.rsplit("_", 1)
                try:
                    idx = int(idx_str)
                    n_texts = []
                    for offset in range(-15, 16):
                        if offset == 0:
                            continue
                        nid = f"{prefix}_{idx+offset:06d}"
                        if nid in all_chunks_dict:
                            n_texts.append(all_chunks_dict[nid].lower())
                    n_text = " ".join(n_texts)
                    n_words = set(re.findall(r"\b[a-zA-Z\']+\b", n_text))
                    if any(a in n_words for a in actor_terms):
                        actor_in_neighbors = True
                except ValueError:
                    pass
                    
        if actor_in_meta or actor_in_neighbors:
            if chunk_words & FIRST_PERSON_PRONOUNS:
                first_person_narrative = 1.0
                metrics["first_person_narrative"] = 1.0
                signals.append("first person narrative: inferred")
                # Inject inferred actor directly into chunk_words
                # so that global overlap metrics recognize them.
                chunk_words.update(actor_terms)

    sentences = [s.strip() for s in re.split(r'[.!?]+', chunk_lower) if s.strip()]
    sentence_data = []

    for s in sentences:
        s_words = set(re.findall(r"\b[a-zA-Z\']+\b", s))
        
        # 1. Which query terms appear?
        s_terms = set()
        for term in query_terms:
            if term in s_words:
                s_terms.add(term)
            elif term in _REVERSE_CONCEPT:
                root = _REVERSE_CONCEPT[term]
                family = CONCEPT_MAP[root] | {root}
                if family & s_words:
                    s_terms.add(term)
                    
        # 1.b Which actor and event terms appear?
        s_actors = set(t for t in actor_terms if t in s_words)
        
        # Inject actor if we confidently inferred first-person narration
        if first_person_narrative > 0 and (s_words & FIRST_PERSON_PRONOUNS):
            s_actors.update(actor_terms)
            
        s_events = event_terms & s_words
        
        # 2. Which causal indicators appear?
        s_causals = set()
        if is_causal:
            for indicator in CAUSAL_INDICATORS:
                if re.search(r"\b" + re.escape(indicator) + r"\b", s):
                    s_causals.add(indicator)

        # 3. Which motivation/consequence/emotion indicators?
        s_motivation = s_words & MOTIVATION_INDICATORS
        s_consequence = s_words & CONSEQUENCE_INDICATORS
        s_negation = set()
        for ind in NEGATION_INDICATORS:
            if re.search(r"\b" + re.escape(ind) + r"\b", s):
                s_negation.add(ind)
        s_regret = s_words & REGRET_INDICATORS
        s_reaction = s_words & REACTION_INDICATORS
        
        # 4. Speaker verbs
        s_speakers = s_words & SPEAKER_VERBS

        sentence_data.append({
            "terms": s_terms,
            "actors": s_actors,
            "events": s_events,
            "causals": s_causals,
            "motivation": s_motivation,
            "consequence": s_consequence,
            "negation": s_negation,
            "regret": s_regret,
            "reaction": s_reaction,
            "speakers": s_speakers,
        })

    # --------------------------------------------------------
    # SIGNAL 1: IMPORTANT-TERM OVERLAP
    #
    # What fraction of query terms (or their
    # concept expansions) appear in the chunk?
    # --------------------------------------------------------

    matched_query_terms = []

    for term in query_terms:

        # Check direct match
        if term in chunk_words:

            matched_query_terms.append(term)
            continue

        # Check concept expansion match
        if term in _REVERSE_CONCEPT:

            root = _REVERSE_CONCEPT[term]
            family = (
                CONCEPT_MAP[root] | {root}
            )

            family_in_chunk = (
                family & chunk_words
            )

            if family_in_chunk:

                matched_query_terms.append(
                    term
                )

                example = next(
                    iter(family_in_chunk)
                )

                signals.append(
                    f"concept match: "
                    f"{term} -> {example}"
                )

    term_overlap = (
        len(matched_query_terms)
        / len(query_terms)
        if query_terms
        else 0.0
    )

    if matched_query_terms:

        direct = [
            t for t in matched_query_terms
            if t in chunk_words
        ]

        if direct:

            signals.append(
                f"term overlap: "
                f"{', '.join(direct[:5])}"
            )

    # --------------------------------------------------------
    # SIGNAL 2: PHRASE OVERLAP
    #
    # Do multi-word phrases from the query appear
    # in the chunk as substrings?
    # --------------------------------------------------------

    query_bigrams = _extract_bigrams(
        query_terms
    )

    matched_phrases = 0

    for bigram in query_bigrams:

        if bigram in chunk_lower:

            matched_phrases += 1

            signals.append(
                f"phrase match: \"{bigram}\""
            )

    phrase_overlap = (
        matched_phrases / len(query_bigrams)
        if query_bigrams
        else 0.0
    )

    # --------------------------------------------------------
    # SIGNAL 3: CONCEPT DENSITY
    #
    # How many distinct concept families from the
    # query are represented in the chunk?
    # --------------------------------------------------------

    if matched_roots:

        families_present = 0

        for root in matched_roots:

            family = (
                CONCEPT_MAP[root] | {root}
            )

            if family & chunk_words:
                families_present += 1

        concept_density = (
            families_present
            / len(matched_roots)
        )

        if families_present > 0:

            signals.append(
                f"concept families: "
                f"{families_present}/"
                f"{len(matched_roots)}"
            )

    else:
        concept_density = 0.0

    # --------------------------------------------------------
    # SIGNAL 4 & 5 & Speaker: LOCAL WINDOW ALIGNMENT
    #
    # Evaluate 3-sentence rolling windows.
    # --------------------------------------------------------

    best_actor_alignment = 0.0
    best_event_alignment = 0.0
    best_local_causal = 0.0
    speaker_score = 0.0

    for i in range(len(sentence_data)):
        window_terms = set(sentence_data[i]["terms"])
        window_actors = set(sentence_data[i]["actors"])
        window_events = set(sentence_data[i]["events"])
        window_causals = set(sentence_data[i]["causals"])
        window_motivation = set(sentence_data[i]["motivation"])
        window_consequence = set(sentence_data[i]["consequence"])
        window_speakers = set(sentence_data[i]["speakers"])
        window_negation = set(sentence_data[i]["negation"])
        window_regret = set(sentence_data[i]["regret"])
        window_reaction = set(sentence_data[i]["reaction"])
        
        # Include adjacent sentences (prev and next)
        if i > 0:
            window_terms.update(sentence_data[i-1]["terms"])
            window_actors.update(sentence_data[i-1]["actors"])
            window_events.update(sentence_data[i-1]["events"])
            window_causals.update(sentence_data[i-1]["causals"])
            window_motivation.update(sentence_data[i-1]["motivation"])
            window_consequence.update(sentence_data[i-1]["consequence"])
            window_speakers.update(sentence_data[i-1]["speakers"])
            window_negation.update(sentence_data[i-1]["negation"])
            window_regret.update(sentence_data[i-1]["regret"])
            window_reaction.update(sentence_data[i-1]["reaction"])
        if i + 1 < len(sentence_data):
            window_terms.update(sentence_data[i+1]["terms"])
            window_actors.update(sentence_data[i+1]["actors"])
            window_events.update(sentence_data[i+1]["events"])
            window_causals.update(sentence_data[i+1]["causals"])
            window_motivation.update(sentence_data[i+1]["motivation"])
            window_consequence.update(sentence_data[i+1]["consequence"])
            window_speakers.update(sentence_data[i+1]["speakers"])
            window_negation.update(sentence_data[i+1]["negation"])
            window_regret.update(sentence_data[i+1]["regret"])
            window_reaction.update(sentence_data[i+1]["reaction"])
            
        # Actor alignment: fraction of required actor terms in window
        a_align = len(window_actors) / max(len(actor_terms), 1)
        if a_align > best_actor_alignment:
            best_actor_alignment = a_align
            
        # Event alignment: fraction of required event families in window (approx using count)
        e_align = min(len(window_events), 2) / 2.0
        if e_align > best_event_alignment:
            best_event_alignment = e_align
            
        # Local causal/temporal logic
        if semantic_intent == "NEGATED_MOTIVATION":
            if window_actors and window_events and window_negation:
                c_score = min(len(window_negation) + len(window_motivation) + len(window_consequence), 3) / 3.0
                if c_score > best_local_causal:
                    best_local_causal = c_score
        elif semantic_intent == "REGRET":
            if window_actors and window_regret:
                c_score = min(len(window_regret), 3) / 3.0
                if c_score > best_local_causal:
                    best_local_causal = c_score
        elif semantic_intent == "CONSEQUENCE":
            if window_actors and window_events and window_consequence:
                c_score = min(len(window_consequence), 3) / 3.0
                if c_score > best_local_causal:
                    best_local_causal = c_score
        elif semantic_intent == "REACTION":
            if window_actors and (window_reaction or window_consequence):
                c_score = min(len(window_reaction) + len(window_consequence), 3) / 3.0
                if c_score > best_local_causal:
                    best_local_causal = c_score
        elif semantic_intent == "MOTIVATION" or intent == "causal":
            if window_actors and window_events and (window_causals or window_motivation):
                c_score = min(len(window_causals) + len(window_motivation), 3) / 3.0
                if c_score > best_local_causal:
                    best_local_causal = c_score
        elif intent == "temporal":
            if window_actors and window_events and window_consequence:
                t_score = min(len(window_consequence), 3) / 3.0
                if t_score > best_local_causal:
                    best_local_causal = t_score
            elif window_actors and window_events:
                if 0.5 > best_local_causal:
                    best_local_causal = 0.5
                    
        # Speaker heuristic: if an actor is near a speaker verb
        if window_actors and window_speakers:
            speaker_score = 1.0
            
    metrics["actor_alignment"] = best_actor_alignment
    metrics["event_alignment"] = best_event_alignment
    metrics["local_causal_score"] = best_local_causal
    metrics["speaker_score"] = speaker_score

    if semantic_intent in ("FACTUAL", "RELATIONSHIP"):
        alignment_score = best_actor_alignment
    else:
        alignment_score = (best_actor_alignment + best_event_alignment) / 2.0
        
    if alignment_score > 0:
        signals.append(f"local alignment: {alignment_score:.2f}")

    if is_causal and best_local_causal > 0:
        signals.append(f"local causal: {best_local_causal:.2f}")
        
    if is_temporal and best_local_causal > 0:
        signals.append(f"local temporal: {best_local_causal:.2f}")
        
    if speaker_score > 0:
        signals.append(f"speaker proximity: present")

    # --------------------------------------------------------
    # SIGNAL 6: MOTIVATION PRIORITY
    #
    # For causal-intent queries, distinguish passages
    # that explain WHY (motivation, intention, purpose)
    # from passages that describe WHAT HAPPENED AFTER
    # (consequence, regret, aftermath).
    #
    # This is generic — it uses motivation vs consequence
    # indicator word sets, not book-specific logic.
    # --------------------------------------------------------

    motivation_priority = 0.0

    if is_causal:

        # Count motivation and consequence indicators
        # in sentences that are near query terms
        # (same sentence or adjacent).

        near_motivation = 0
        near_consequence = 0

        for i in range(len(sentence_data)):

            # Check if this sentence or neighbors
            # contain query terms
            has_terms = bool(
                sentence_data[i]["terms"]
            )

            if (
                not has_terms
                and i > 0
                and sentence_data[i - 1]["terms"]
            ):
                has_terms = True

            if (
                not has_terms
                and i + 1 < len(sentence_data)
                and sentence_data[i + 1]["terms"]
            ):
                has_terms = True

            if has_terms:
                near_motivation += len(
                    sentence_data[i]["motivation"]
                )
                near_consequence += len(
                    sentence_data[i]["consequence"]
                )

        # Also count chunk-wide motivation/consequence
        # with reduced weight
        chunk_motivation = len(
            chunk_words & MOTIVATION_INDICATORS
        )
        chunk_consequence = len(
            chunk_words & CONSEQUENCE_INDICATORS
        )

        total_mot = near_motivation + 0.3 * chunk_motivation
        total_con = near_consequence + 0.3 * chunk_consequence

        motivation_strength = min(total_mot / 3.0, 1.0)
        consequence_strength = min(total_con / 3.0, 1.0)
        
        if semantic_intent == "CONSEQUENCE":
            motivation_priority = max(0.0, consequence_strength - motivation_strength)
        elif semantic_intent == "NEGATED_MOTIVATION":
            # For negated motivation, consequences (avoidance, aftermath) are as important as motivation
            motivation_priority = max(0.0, consequence_strength)
        elif semantic_intent == "REGRET":
            motivation_priority = consequence_strength # Regret relies on consequence indicators often
        else:
            motivation_priority = max(0.0, motivation_strength - consequence_strength)

        metrics["motivation_strength"] = motivation_strength
        metrics["consequence_strength"] = consequence_strength
        metrics["motivation_priority"] = motivation_priority

        if near_motivation > 0:
            signals.append(
                f"motivation: {near_motivation} near"
            )

        if near_consequence > 0:
            signals.append(
                f"consequence: {near_consequence} near"
            )

    # --------------------------------------------------------
    # SIGNAL 7: MULTI-QUERY COVERAGE
    #
    # What fraction of the expanded retrieval
    # queries have key terms in the chunk?
    # --------------------------------------------------------

    if (
        expanded_queries
        and len(expanded_queries) > 1
    ):

        queries_covered = 0

        for eq in expanded_queries:

            eq_terms = extract_important_terms(
                eq
            )

            if not eq_terms:
                continue

            eq_matched = sum(
                1 for t in eq_terms
                if t in chunk_words
            )

            # At least 30% of query terms match
            if (
                eq_matched / len(eq_terms) >= 0.3
            ):

                queries_covered += 1

        multi_q_coverage = (
            queries_covered
            / len(expanded_queries)
        )

    else:
        multi_q_coverage = 0.0

    # --------------------------------------------------------
    # POLARITY ALIGNMENT
    # --------------------------------------------------------
    
    polarity_alignment = 1.0
    if intent_data and intent_data.get("polarity") == "negative":
        # Heavily penalize if no negation indicator is present
        if not (chunk_words & NEGATION_INDICATORS):
            polarity_alignment = 0.0
        else:
            polarity_alignment = 1.0
            
    metrics["polarity_alignment"] = polarity_alignment

    # --------------------------------------------------------
    # DIRECTIONAL SUBJECT-OBJECT ALIGNMENT
    # --------------------------------------------------------

    directional_subject_alignment = 0.5
    if semantic_intent in ("MOTIVATION", "REGRET") and intent_data:
        subject_str = intent_data.get("actor")
        object_str = intent_data.get("target")
        
        if subject_str:
            sub_terms = set(extract_important_terms(subject_str))
            obj_terms = set(extract_important_terms(object_str)) if object_str else set()
            
            if first_person_narrative > 0:
                directional_subject_alignment = 1.0
                signals.append("directional alignment: 1.0 (subject narrator)")
            else:
                object_is_narrator = False
                if obj_terms and chunk_metadata and all_chunks_dict:
                    meta_text = f"{chunk_metadata.get('title', '')} {chunk_metadata.get('chapter', '')}".lower()
                    if any(o in meta_text for o in obj_terms):
                        object_is_narrator = True
                    else:
                        prefix = chunk_metadata.get("chunk_id", "").rsplit("_", 1)[0] if "_" in chunk_metadata.get("chunk_id", "") else ""
                        try:
                            idx = int(chunk_metadata.get("chunk_id", "").rsplit("_", 1)[1])
                            n_text = " ".join([all_chunks_dict.get(f"{prefix}_{idx+offset:06d}", "").lower() for offset in range(-5, 6) if offset != 0])
                            n_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", n_text))
                            if obj_terms & n_words:
                                object_is_narrator = True
                        except:
                            pass
                
                if object_is_narrator and (chunk_words & FIRST_PERSON_PRONOUNS):
                    directional_subject_alignment = 0.0
                    signals.append("directional alignment: 0.0 (object narrator)")
                else:
                    sub_count = len(sub_terms & chunk_words)
                    obj_count = len(obj_terms & chunk_words) if obj_terms else 0
                    if sub_count > 0:
                        directional_subject_alignment = 0.7
                        signals.append("directional alignment: 0.7 (3rd person subject)")
                    elif obj_count > 0 and sub_count == 0:
                        directional_subject_alignment = 0.3
                        signals.append("directional alignment: 0.3 (object only)")
                        
    metrics["directional_subject_alignment"] = directional_subject_alignment

    # --------------------------------------------------------
    # TEMPORAL PHASE PRIOR
    # --------------------------------------------------------

    temporal_phase_alignment = 0.5
    if chunk_metadata and all_chunks_dict:
        work_id = chunk_metadata.get("work_id", "")
        chunk_id = chunk_metadata.get("chunk_id", "")
        if work_id and "_" in chunk_id:
            try:
                chunk_index = int(chunk_id.rsplit("_", 1)[1])
                max_idx = get_max_chunk_index(work_id, all_chunks_dict)
                if max_idx > 0:
                    fraction = chunk_index / max_idx
                    q_lower = original_query.lower()
                    has_origin = any(cue in q_lower for cue in ORIGIN_TEMPORAL_CUES)
                    has_later = any(cue in q_lower for cue in LATER_TEMPORAL_CUES)
                    
                    if semantic_intent == "MOTIVATION":
                        action_str = intent_data.get("action", "").lower() if intent_data else ""
                        if any(v in action_str for v in ["study", "learn", "begin", "start", "create"]):
                            has_origin = True
                            
                    if has_origin and not has_later:
                        temporal_phase_alignment = max(0.0, 1.0 - fraction)
                        if first_person_narrative > 0 and fraction < 0.3:
                            temporal_phase_alignment = min(1.0, temporal_phase_alignment + 0.2)
                        signals.append(f"temporal phase (origin): {temporal_phase_alignment:.2f}")
                    elif has_later and not has_origin:
                        temporal_phase_alignment = min(1.0, fraction)
                        signals.append(f"temporal phase (later): {temporal_phase_alignment:.2f}")
            except:
                pass
    metrics["temporal_phase_alignment"] = temporal_phase_alignment

    # --------------------------------------------------------
    # COMBINE SIGNALS (DYNAMIC SCORING)
    # --------------------------------------------------------
    
    if semantic_intent == "MOTIVATION":
        score = (
            0.10 * term_overlap + 
            0.17 * alignment_score + 
            0.25 * best_local_causal + 
            0.25 * motivation_priority + 
            0.05 * multi_q_coverage +
            0.10 * directional_subject_alignment +
            0.08 * temporal_phase_alignment
        )
    elif semantic_intent == "NEGATED_MOTIVATION":
        score = (
            0.10 * term_overlap + 
            0.20 * alignment_score + 
            0.25 * polarity_alignment + 
            0.20 * best_local_causal + 
            0.20 * motivation_priority +
            0.05 * temporal_phase_alignment
        )
    elif semantic_intent == "REGRET":
        score = (
            0.05 * term_overlap + 
            0.25 * alignment_score + 
            0.35 * best_local_causal + 
            0.20 * motivation_priority +
            0.05 * multi_q_coverage +
            0.10 * directional_subject_alignment
        )
    elif semantic_intent == "CONSEQUENCE":
        score = (
            0.15 * term_overlap + 
            0.20 * alignment_score + 
            0.30 * best_local_causal + 
            0.25 * motivation_priority + 
            0.10 * multi_q_coverage
        )
    elif semantic_intent == "REACTION":
        score = (
            0.15 * term_overlap + 
            0.20 * alignment_score + 
            0.30 * best_local_causal + 
            0.25 * motivation_priority + 
            0.10 * speaker_score
        )
    elif semantic_intent == "RELATIONSHIP":
        score = (
            0.30 * term_overlap + 
            0.15 * phrase_overlap + 
            0.40 * alignment_score + 
            0.15 * multi_q_coverage
        )
    elif semantic_intent == "FACTUAL":
        score = (
            0.25 * term_overlap + 
            0.15 * phrase_overlap + 
            0.10 * concept_density + 
            0.40 * alignment_score + 
            0.10 * multi_q_coverage
        )
    else:
        # Fallback
        score = (
            0.20 * term_overlap + 
            0.20 * phrase_overlap + 
            0.10 * concept_density + 
            0.30 * alignment_score + 
            0.15 * multi_q_coverage + 
            0.05 * speaker_score
        )

    # Clamp to [0, 1]
    score = max(0.0, min(1.0, score))

    return score, signals, metrics


# ============================================================
# GENERIC QUERY EXPANSION
#
# Replaces the hardcoded Frankenstein expansion with
# concept-aware expansion that works for all books.
# ============================================================

def generate_expanded_queries(query):
    """
    Generate deterministic retrieval queries from
    the user's original question using concept expansion.

    Always returns 3 queries:
        1. Original query
        2. Natural-language reformulation
        3. Keyword-bag query

    Returns list of query strings.
    """

    queries = [query]
    q_lower = query.lower()

    # --------------------------------------------------------
    # EXTRACT AND EXPAND TERMS
    # --------------------------------------------------------

    terms = extract_important_terms(q_lower)

    if not terms:
        return queries

    expanded, roots = (
        expand_terms_with_concepts(terms)
    )

    # --------------------------------------------------------
    # DETECT INTENT FOR PHRASING
    # --------------------------------------------------------

    intent = detect_query_intent(query)

    # --------------------------------------------------------
    # QUERY 2: NATURAL-LANGUAGE REFORMULATION
    #
    # Rephrases the question using expanded concepts
    # to cast a wider semantic net.
    # --------------------------------------------------------

    # Collect a few synonyms per query term
    expansion_terms = []

    for term in terms:

        if term in _REVERSE_CONCEPT:

            root = _REVERSE_CONCEPT[term]
            family = list(
                CONCEPT_MAP[root] | {root}
            )

            # Pick up to 3 synonyms not already
            # in the query
            added = 0

            for syn in family:

                if (
                    syn not in q_lower
                    and added < 3
                ):

                    expansion_terms.append(syn)
                    added += 1

    # --------------------------------------------------------
    # INTENT-DRIVEN EXPANSION
    #
    # For causal queries ("why", "what motivates"),
    # also pull in terms from semantically adjacent
    # concept families that are commonly relevant
    # to explaining motivation or cause.
    #
    # This is generic — it does not assume any specific
    # book or topic. It simply broadens retrieval to
    # catch passages about ambition, curiosity, purpose,
    # knowledge, discovery, etc.
    # --------------------------------------------------------

    intent_expansion = []

    if intent == "causal":

        # Adjacent families for causal queries
        causal_families = [
            "motivation", "knowledge"
        ]

        for family_root in causal_families:

            # Skip if already matched via query
            if family_root in roots:
                continue

            family = CONCEPT_MAP.get(
                family_root, set()
            )

            # Pick a few representative terms
            added = 0

            for syn in sorted(family):

                if (
                    syn not in q_lower
                    and added < 3
                ):

                    intent_expansion.append(syn)
                    added += 1

    if expansion_terms or intent_expansion:

        # Build a reformulation that includes
        # original terms, concept expansions,
        # and intent-driven expansions

        all_expansions = (
            expansion_terms[:5]
            + intent_expansion[:4]
        )

        if intent == "causal":

            reformulated = (
                "What causes or motivates "
                + " ".join(terms[:4])
                + " "
                + " ".join(all_expansions)
            )

        elif intent == "descriptive":

            reformulated = (
                "Describe "
                + " ".join(terms[:4])
                + " "
                + " ".join(all_expansions)
            )

        else:

            reformulated = (
                " ".join(terms[:4])
                + " "
                + " ".join(all_expansions)
            )

        queries.append(reformulated.strip())

    # --------------------------------------------------------
    # QUERY 3: KEYWORD BAG
    #
    # Dense bag of related terms for maximum
    # embedding coverage.
    # --------------------------------------------------------

    # Combine original terms + expanded terms
    keyword_set = set(terms)

    for term in terms:

        if term in _REVERSE_CONCEPT:

            root = _REVERSE_CONCEPT[term]
            family = CONCEPT_MAP[root] | {root}
            keyword_set.update(
                sorted(family)[:5]
            )

    # Also include intent expansion terms
    keyword_set.update(intent_expansion)

    # Remove very short words
    keywords = sorted(
        w for w in keyword_set
        if len(w) >= 3
    )

    if keywords:

        keyword_query = " ".join(
            keywords[:14]
        )

        queries.append(keyword_query)

    # --------------------------------------------------------
    # DEDUPLICATE WHILE PRESERVING ORDER
    # --------------------------------------------------------

    seen = set()
    final = []

    for q in queries:

        if q not in seen:
            final.append(q)
            seen.add(q)

    return final


# ============================================================
# NORMALIZE CROSSENCODER SCORES
# ============================================================

def normalize_scores_minmax(scores):
    """
    Min-max normalize a list of scores to [0, 1].

    If all scores are equal, returns 0.5 for all.
    """

    if not scores:
        return []

    min_s = min(scores)
    max_s = max(scores)
    span = max_s - min_s

    if span == 0:
        return [0.5] * len(scores)

    return [
        (s - min_s) / span
        for s in scores
    ]
