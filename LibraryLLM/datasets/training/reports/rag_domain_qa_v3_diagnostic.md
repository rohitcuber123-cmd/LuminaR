# V3 high-confidence source diagnostic — below review threshold

**EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS**

This is an engineering diagnostic, not a human-review packet or REVIEWED data. Only five candidates passed automatic checks; the ≥10 review threshold failed.

## DQ3-6b7b413dd647 — Great Expectations

- Relation: ENTITY_RELATION; confidence: HIGH
- Clause: Camilla was Mr. Pocket’s sister.
- Proposition: `{"relation_type": "ENTITY_RELATION", "v3_relation": "ENTITY_RELATION", "subject": "Camilla", "predicate": "was", "object": "Mr. Pocket’s sister", "entity_a": "Camilla", "entity_b": "Mr. Pocket"}`
- Template: Which person was identified as Mr. Pocket's sister?
- Final: Which person was identified as Mr. Pocket's sister?
- Answer: Camilla
- Evidence: Camilla was Mr. Pocket’s sister.
- Automatic validation: {'passed': True, 'checks': {'TEST_LEAKAGE': True, 'SOURCE_MAPPING_FAILED': True, 'SOURCE_HASH_INTEGRITY': True, 'EVIDENCE_NOT_EXACT': True, 'MISSING_PROPOSITION': True, 'WRONG_PROPOSITION_SLOT': True, 'ANSWER_NOT_IN_EVIDENCE': True, 'ANSWER_TYPE_MISMATCH': True, 'QUESTION_TOO_GENERIC': True, 'TRIVIAL_METADATA': True, 'UNRESOLVED_REFERENT': True, 'QUESTION_CONTAINS_ANSWER': True}, 'rejection_reasons': [], 'entailment': {'label': 'ENTAILED', 'reason': 'Exact relation pattern and fixed question template', 'supporting_text': 'Camilla was Mr. Pocket’s sister.'}}

## DQ3-bdaf81551732 — Jane Eyre

- Relation: INSTRUCTION; confidence: HIGH
- Clause: Miss Temple
told Helen Burns to be seated in a low arm-chair on one side of the
hearth, and herself taking another, she called me to her side.
- Proposition: `{"relation_type": "ENTITY_ACTION", "v3_relation": "INSTRUCTION", "subject": "Miss Temple", "predicate": "told", "object": "Helen Burns", "instruction": "be seated in a low arm-chair on one side of the\nhearth"}`
- Template: Whom did Miss Temple tell to be seated in a low arm-chair on one side of the
hearth?
- Final: Whom did Miss Temple tell to be seated in a low arm-chair on one side of the
hearth?
- Answer: Helen Burns
- Evidence: Miss Temple
told Helen Burns to be seated in a low arm-chair on one side of the
hearth, and herself taking another, she called me to her side.
- Automatic validation: {'passed': True, 'checks': {'TEST_LEAKAGE': True, 'SOURCE_MAPPING_FAILED': True, 'SOURCE_HASH_INTEGRITY': True, 'EVIDENCE_NOT_EXACT': True, 'MISSING_PROPOSITION': True, 'WRONG_PROPOSITION_SLOT': True, 'ANSWER_NOT_IN_EVIDENCE': True, 'ANSWER_TYPE_MISMATCH': True, 'QUESTION_TOO_GENERIC': True, 'TRIVIAL_METADATA': True, 'UNRESOLVED_REFERENT': True, 'QUESTION_CONTAINS_ANSWER': True}, 'rejection_reasons': [], 'entailment': {'label': 'ENTAILED', 'reason': 'Exact relation pattern and fixed question template', 'supporting_text': 'Miss Temple\ntold Helen Burns to be seated in a low arm-chair on one side of the\nhearth, and herself taking another, she called me to her side.'}}

## DQ3-8341fb07768d — Dracula

- Relation: INSTRUCTION; confidence: HIGH
- Clause: When the three men had gone out to their tasks Van Helsing asked Mrs.
Harker to look up the copy of the diaries and find him the part of
Harker’s journal at the Castle.
- Proposition: `{"relation_type": "ENTITY_ACTION", "v3_relation": "INSTRUCTION", "subject": "Van Helsing", "predicate": "asked", "object": "Mrs.\nHarker", "instruction": "look up the copy of the diaries and find him the part of\nHarker’s journal at the Castle."}`
- Template: Whom did Van Helsing ask to look up the copy of the diaries and find him the part of
Harker’s journal at the Castle?
- Final: Whom did Van Helsing ask to look up the copy of the diaries and find him the part of
Harker’s journal at the Castle?
- Answer: Mrs.
Harker
- Evidence: When the three men had gone out to their tasks Van Helsing asked Mrs.
Harker to look up the copy of the diaries and find him the part of
Harker’s journal at the Castle.
- Automatic validation: {'passed': True, 'checks': {'TEST_LEAKAGE': True, 'SOURCE_MAPPING_FAILED': True, 'SOURCE_HASH_INTEGRITY': True, 'EVIDENCE_NOT_EXACT': True, 'MISSING_PROPOSITION': True, 'WRONG_PROPOSITION_SLOT': True, 'ANSWER_NOT_IN_EVIDENCE': True, 'ANSWER_TYPE_MISMATCH': True, 'QUESTION_TOO_GENERIC': True, 'TRIVIAL_METADATA': True, 'UNRESOLVED_REFERENT': True, 'QUESTION_CONTAINS_ANSWER': True}, 'rejection_reasons': [], 'entailment': {'label': 'ENTAILED', 'reason': 'Exact relation pattern and fixed question template', 'supporting_text': 'When the three men had gone out to their tasks Van Helsing asked Mrs.\nHarker to look up the copy of the diaries and find him the part of\nHarker’s journal at the Castle.'}}

## DQ3-b4302412561d — Adventures of Huckleberry Finn

- Relation: MOTIVATION; confidence: HIGH
- Clause: Bill wanted to
kill Turner.
- Proposition: `{"relation_type": "MOTIVATION", "v3_relation": "MOTIVATION", "subject": "Bill", "predicate": "wanted", "cause": "to\nkill Turner", "effect": "Bill wanted to\nkill Turner"}`
- Template: What action did Bill want to take?
- Final: What action did Bill want to take?
- Answer: to
kill Turner
- Evidence: Bill wanted to
kill Turner.
- Automatic validation: {'passed': True, 'checks': {'TEST_LEAKAGE': True, 'SOURCE_MAPPING_FAILED': True, 'SOURCE_HASH_INTEGRITY': True, 'EVIDENCE_NOT_EXACT': True, 'MISSING_PROPOSITION': True, 'WRONG_PROPOSITION_SLOT': True, 'ANSWER_NOT_IN_EVIDENCE': True, 'ANSWER_TYPE_MISMATCH': True, 'QUESTION_TOO_GENERIC': True, 'TRIVIAL_METADATA': True, 'UNRESOLVED_REFERENT': True, 'QUESTION_CONTAINS_ANSWER': True, 'UNSUPPORTED_CAUSAL': True}, 'rejection_reasons': [], 'entailment': {'label': 'ENTAILED', 'reason': 'Exact relation pattern and fixed question template', 'supporting_text': 'Bill wanted to\nkill Turner.'}}

## DQ3-e04bc985306f — Pride and Prejudice

- Relation: LOCATION_TO; confidence: HIGH
- Clause: When my
niece Georgiana went to Ramsgate last summer, I made a point of her
having two men-servants go with her.
- Proposition: `{"relation_type": "LOCATION", "v3_relation": "LOCATION_TO", "subject": "Georgiana", "predicate": "went", "location": "Ramsgate"}`
- Template: Where did Georgiana go to on the journey?
- Final: Where did Georgiana go to on the journey?
- Answer: Ramsgate
- Evidence: When my
niece Georgiana went to Ramsgate last summer, I made a point of her
having two men-servants go with her.
- Automatic validation: {'passed': True, 'checks': {'TEST_LEAKAGE': True, 'SOURCE_MAPPING_FAILED': True, 'SOURCE_HASH_INTEGRITY': True, 'EVIDENCE_NOT_EXACT': True, 'MISSING_PROPOSITION': True, 'WRONG_PROPOSITION_SLOT': True, 'ANSWER_NOT_IN_EVIDENCE': True, 'ANSWER_TYPE_MISMATCH': True, 'QUESTION_TOO_GENERIC': True, 'TRIVIAL_METADATA': True, 'UNRESOLVED_REFERENT': True, 'QUESTION_CONTAINS_ANSWER': True}, 'rejection_reasons': [], 'entailment': {'label': 'ENTAILED', 'reason': 'Exact relation pattern and fixed question template', 'supporting_text': 'When my\nniece Georgiana went to Ramsgate last summer, I made a point of her\nhaving two men-servants go with her.'}}
