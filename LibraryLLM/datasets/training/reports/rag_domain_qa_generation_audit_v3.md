# V3 deterministic domain QA: 50-source audit

**EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS**

Review gate: FAIL; 5 AUTO_VALIDATED against the required ≥10.
Human review: NOT YET COMPLETE. Training gate: CLOSED.

## Counts

- AUTO_VALIDATED: 5
- HIGH: 5
- MEDIUM: 15
- clauses_examined: 547
- duplicate_propositions_removed: 4
- paraphrases_accepted: 0
- paraphrases_attempted: 0
- relation_patterns_matched: 24
- review_packet_rows: 0
- sentences_examined: 451
- source_chunks_attempted: 50
- template_questions_built: 5
- template_questions_validated: 5

## Per relation

- ATTRIBUTE: {'matches': 15, 'MEDIUM': 12, 'duplicates': 3}
- ENTITY_RELATION: {'matches': 1, 'HIGH': 1, 'passed_validation': 1}
- INSTRUCTION: {'matches': 2, 'HIGH': 2, 'passed_validation': 2}
- LOCATION_TO: {'matches': 1, 'HIGH': 1, 'passed_validation': 1}
- MOTIVATION: {'matches': 4, 'HIGH': 1, 'passed_validation': 1, 'MEDIUM': 2, 'duplicates': 1}
- TEMPORAL_AT: {'matches': 1, 'MEDIUM': 1}

## Extractor can-match attempts

- ActionExtractor: 7
- AttributeExtractor: 18
- CauseExtractor: 10
- EntityRelationExtractor: 29
- InstructionExtractor: 8
- LocationExtractor: 12
- MotivationExtractor: 5
- StatementExtractor: 2
- TemporalExtractor: 22

## Rejection codes


AUTO_VALIDATED propositions also seen in the probe: 5/5. The pilot therefore does not provide independent quality confirmation for those examples.
No Qwen paraphrases were attempted. The template question was kept for every emitted candidate.
