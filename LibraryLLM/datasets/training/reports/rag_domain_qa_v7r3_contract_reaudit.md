# V7R3A saved-contract reaudit

All 19 rows are saved V7R3 deterministic passes. No Stage A, Stage B or judge call was rerun.

Engineering audit: 2 plausible, 15 obvious errors, 2 ambiguous.
Corrected contract passes: 4; ready for human review: 2; pilot threshold: 10.
OTHER_EXPLICIT unresolved: 11; mixed semantic spans: 1.
Category metadata changed for 13 rows; category-only repair retained: AQA7R3-032-2.

| Candidate | Question | Answer | Engineering audit | Error type | Intent | Final answer type | Final category | Contract | Judge | Ready |
|---|---|---|---|---|---|---|---|---|---|---|
| AQA7R3-005-1 | What did the eye fall upon? | with | OBVIOUS_SEMANTIC_ERROR | ANSWER_SELECTION_ERROR | WHAT_OBJECT | OBJECT | FACTUAL_DIRECT | ANSWER_SPAN_INCOMPLETE | SEMANTIC_UNCERTAIN | NO |
| AQA7R3-005-2 | What did the eye fall upon? | looking | OBVIOUS_SEMANTIC_ERROR | ANSWER_SELECTION_ERROR | WHAT_OBJECT | OBJECT | FACTUAL_DIRECT | ANSWER_TYPE_COMPATIBILITY_FAILED | SEMANTIC_UNCERTAIN | NO |
| AQA7R3-011-2 | What did Mr. Quincey Morris say? | Count | OBVIOUS_SEMANTIC_ERROR | ANSWER_SELECTION_ERROR | WHAT_QUOTE | NEEDS_REVIEW | QUOTE_OR_PHRASE | OTHER_EXPLICIT_NEEDS_REVIEW, QUESTION_ANSWER_TYPE_MISMATCH | SEMANTIC_UNCERTAIN | NO |
| AQA7R3-012-1 | What were brought up from Woolwich and Chatham to cover Kingston? | guns | PLAUSIBLE_FOR_HUMAN_REVIEW | — | WHAT_OBJECT | OBJECT | FACTUAL_DIRECT | PASS | SUPPORTED | YES |
| AQA7R3-012-2 | What group of people came to clear the public from the station? | squad | AMBIGUOUS | ANSWER_SELECTION_ERROR | WHAT_OBJECT | ACTION | FACTUAL_DIRECT | QUESTION_ANSWER_TYPE_MISMATCH | SEMANTIC_UNCERTAIN | NO |
| AQA7R3-021-2 | Who suggests asking a question of the guardian first? | GWENDOLEN. An admirable | OBVIOUS_SEMANTIC_ERROR | ANSWER_SELECTION_ERROR | WHO | NEEDS_REVIEW | FACTUAL_DIRECT | OTHER_EXPLICIT_NEEDS_REVIEW, QUESTION_ANSWER_TYPE_MISMATCH | INVALID_JSON | NO |
| AQA7R3-025-1 | What did Jaggers do before looking at his boots? | forward | OBVIOUS_SEMANTIC_ERROR | QUESTION_FORMULATION_ERROR | WHAT_ACTION | NEEDS_REVIEW | EVENT | OTHER_EXPLICIT_NEEDS_REVIEW, QUESTION_ANSWER_TYPE_MISMATCH | SEMANTIC_UNCERTAIN | NO |
| AQA7R3-031-2 | What did Mrs. Bennet not do during their walk? | was not | OBVIOUS_SEMANTIC_ERROR | ANSWER_SELECTION_ERROR | WHAT_ACTION | NEEDS_REVIEW | EVENT | ANSWER_SPAN_INCOMPLETE, OTHER_EXPLICIT_NEEDS_REVIEW, QUESTION_ANSWER_TYPE_MISMATCH | SEMANTIC_UNCERTAIN | NO |
| AQA7R3-032-1 | What did the Hatter prefer to do? | finish | AMBIGUOUS | ANSWER_SELECTION_ERROR | WHAT_ACTION | ACTION | EVENT | PASS | SEMANTIC_UNCERTAIN | NO |
| AQA7R3-032-2 | Who said, 'I’d rather finish my tea'? | Hatter | PLAUSIBLE_FOR_HUMAN_REVIEW | — | WHO | PERSON | FACTUAL_DIRECT | PASS | SUPPORTED | YES |
| AQA7R3-033-2 | Who did Cecily think was in the dining room? | look as | OBVIOUS_SEMANTIC_ERROR | ANSWER_SELECTION_ERROR | WHOM | STATE | FACTUAL_DIRECT | ANSWER_SPAN_INCOMPLETE, QUESTION_ANSWER_TYPE_MISMATCH | INVALID_SUPPORT_REFERENCE | NO |
| AQA7R3-034-2 | Where did Georgiana Reed used to be admired for her beauty? | ago in London | OBVIOUS_SEMANTIC_ERROR | ANSWER_TYPE_ERROR | WHERE | NEEDS_REVIEW | LOCATION | MIXED_SEMANTIC_ANSWER_SPAN, OTHER_EXPLICIT_NEEDS_REVIEW, QUESTION_ANSWER_TYPE_MISMATCH | SUPPORTED | NO |
| AQA7R3-038-1 | Who did Miss Pross say to shake her head at her brother? | your | OBVIOUS_SEMANTIC_ERROR | ANSWER_SELECTION_ERROR | WHOM | NEEDS_REVIEW | FACTUAL_DIRECT | ANSWER_SPAN_INCOMPLETE, OTHER_EXPLICIT_NEEDS_REVIEW, QUESTION_ANSWER_TYPE_MISMATCH | SEMANTIC_UNCERTAIN | NO |
| AQA7R3-040-1 | What did Buck's group use for smoking? | ma | OBVIOUS_SEMANTIC_ERROR | ANSWER_SELECTION_ERROR | WHAT_OBJECT | NEEDS_REVIEW | FACTUAL_DIRECT | OTHER_EXPLICIT_NEEDS_REVIEW, QUESTION_ANSWER_TYPE_MISMATCH | SEMANTIC_UNCERTAIN | NO |
| AQA7R3-042-2 | Did Mr. Jones leave the wagon near the door? | not | OBVIOUS_SEMANTIC_ERROR | WRONG_SEMANTIC_ROLE | OTHER | NEEDS_REVIEW | FACTUAL_DIRECT | ANSWER_SPAN_INCOMPLETE, OTHER_EXPLICIT_NEEDS_REVIEW, QUESTION_INTENT_OTHER | SEMANTIC_UNCERTAIN | NO |
| AQA7R3-043-1 | Which boarding house does Jane and her sister Kitty stay at? | Lizzy’s | OBVIOUS_SEMANTIC_ERROR | OUTSIDE_CONTEXT | WHERE | NEEDS_REVIEW | LOCATION | OTHER_EXPLICIT_NEEDS_REVIEW, QUESTION_ANSWER_TYPE_MISMATCH | SEMANTIC_UNCERTAIN | NO |
| AQA7R3-046-1 | What does the phrase 'kindred despoiled' refer to in the given text? | kindred despoiled; Heaven | OBVIOUS_SEMANTIC_ERROR | ANSWER_SELECTION_ERROR | WHAT_OBJECT | NEEDS_REVIEW | FACTUAL_DIRECT | OTHER_EXPLICIT_NEEDS_REVIEW, QUESTION_ANSWER_TYPE_MISMATCH | INVALID_JSON | NO |
| AQA7R3-046-2 | Who does the poet promise to take the orphan child? | will my Father | OBVIOUS_SEMANTIC_ERROR | ANSWER_SELECTION_ERROR | WHOM | NEEDS_REVIEW | FACTUAL_DIRECT | OTHER_EXPLICIT_NEEDS_REVIEW, QUESTION_ANSWER_TYPE_MISMATCH | UNSUPPORTED | NO |
| AQA7R3-049-2 | Who imparted the wish to buy furniture to Herbert? | Jaggers | OBVIOUS_SEMANTIC_ERROR | WRONG_SEMANTIC_ROLE | WHO | PERSON | FACTUAL_DIRECT | PASS | SEMANTIC_UNCERTAIN | NO |

## Decision

Fewer than 10 saved pairs qualify for a human pilot packet.
Stop autonomous QA iteration; move to human-first, Qwen-assisted source authoring.
No candidate is REVIEWED or eligible for training.
