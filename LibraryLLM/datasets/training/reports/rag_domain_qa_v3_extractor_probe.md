# V3 deterministic extractor: 20-chunk source probe

**EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS**

Stats: `{'chunks': 20, 'sentences': 164, 'clauses': 202, 'matches': 17, 'HIGH': 5, 'AUTO_VALIDATED': 5, 'MEDIUM': 10, 'MEDIUM_LOW_DIAGNOSTIC': 10, 'duplicate_propositions': 2}`
Relations: `{'INSTRUCTION': 2, 'MOTIVATION': 3, 'LOCATION_TO': 1, 'ENTITY_RELATION': 1, 'ATTRIBUTE': 7, 'TEMPORAL_AT': 1}`

Assistant source spot inspection of all five HIGH propositions passed after the generic subject-anchor regression fix. The 50-chunk pilot is allowed; human REVIEWED status is not implied.

## 1. Jane Eyre — OL36979234W__tokens_220__67e51678a3f1fb52

- Sentences: 9; clauses: 14
- Source clause: Miss Temple
told Helen Burns to be seated in a low arm-chair on one side of the
hearth, and herself taking another, she called me to her side.
- Extractor: INSTRUCTION; confidence: HIGH
- Proposition: `{"relation_type": "ENTITY_ACTION", "v3_relation": "INSTRUCTION", "subject": "Miss Temple", "predicate": "told", "object": "Helen Burns", "instruction": "be seated in a low arm-chair on one side of the\nhearth"}`
- Template question: Whom did Miss Temple tell to be seated in a low arm-chair on one side of the
hearth?
- Answer: Helen Burns
- V2 validation: AUTO_VALIDATED []

## 2. Adventures of Huckleberry Finn — OL35758281W__tokens_220__97dce02a214a9eef

- Sentences: 13; clauses: 16
- Source clause: Bill wanted to
kill Turner.
- Extractor: MOTIVATION; confidence: HIGH
- Proposition: `{"relation_type": "MOTIVATION", "v3_relation": "MOTIVATION", "subject": "Bill", "predicate": "wanted", "cause": "to\nkill Turner", "effect": "Bill wanted to\nkill Turner"}`
- Template question: What action did Bill want to take?
- Answer: to
kill Turner
- V2 validation: AUTO_VALIDATED []

## 3. Pride and Prejudice — OL66524W__tokens_220__68ea6dbca25959fe

- Sentences: 12; clauses: 13
- Source clause: When my
niece Georgiana went to Ramsgate last summer, I made a point of her
having two men-servants go with her.
- Extractor: LOCATION_TO; confidence: HIGH
- Proposition: `{"relation_type": "LOCATION", "v3_relation": "LOCATION_TO", "subject": "Georgiana", "predicate": "went", "location": "Ramsgate"}`
- Template question: Where did Georgiana go to on the journey?
- Answer: Ramsgate
- V2 validation: AUTO_VALIDATED []

## 4. Great Expectations — OL41470186W__tokens_220__ebf24a56d2530896

- Sentences: 10; clauses: 10
- Source clause: Camilla was Mr. Pocket’s sister.
- Extractor: ENTITY_RELATION; confidence: HIGH
- Proposition: `{"relation_type": "ENTITY_RELATION", "v3_relation": "ENTITY_RELATION", "subject": "Camilla", "predicate": "was", "object": "Mr. Pocket’s sister", "entity_a": "Camilla", "entity_b": "Mr. Pocket"}`
- Template question: Which person was identified as Mr. Pocket's sister?
- Answer: Camilla
- V2 validation: AUTO_VALIDATED []

## 5. Dracula — OL85892W__tokens_220__e196c89c12af06cc

- Sentences: 11; clauses: 14
- Source clause: When the three men had gone out to their tasks Van Helsing asked Mrs.
Harker to look up the copy of the diaries and find him the part of
Harker’s journal at the Castle.
- Extractor: INSTRUCTION; confidence: HIGH
- Proposition: `{"relation_type": "ENTITY_ACTION", "v3_relation": "INSTRUCTION", "subject": "Van Helsing", "predicate": "asked", "object": "Mrs.\nHarker", "instruction": "look up the copy of the diaries and find him the part of\nHarker’s journal at the Castle."}`
- Template question: Whom did Van Helsing ask to look up the copy of the diaries and find him the part of
Harker’s journal at the Castle?
- Answer: Mrs.
Harker
- V2 validation: AUTO_VALIDATED []

## 6. Frankenstein — OL45326637W__tokens_220__5bd2e305168f93e8

- Sentences: 4; clauses: 7
- Source clause: and Felix remained with them in
expectation of that event;
- Extractor: ATTRIBUTE; confidence: MEDIUM
- Proposition: `{"relation_type": "ATTRIBUTE", "v3_relation": "ATTRIBUTE", "subject": "Felix", "predicate": "remained", "object": "with"}`
- Template question: What state did Felix become in the account?
- Answer: with
- V2 validation: MEDIUM_LOW_DIAGNOSTIC ['CONFIDENCE_NOT_HIGH']

## 7. The Adventures of Tom Sawyer — OL28944494W__tokens_220__23b6958d78dfd0de

- Sentences: 7; clauses: 7
- Source clause: Wherever Tom and Huck appeared they were courted, admired,
stared at.
- Extractor: ATTRIBUTE; confidence: MEDIUM
- Proposition: `{"relation_type": "ATTRIBUTE", "v3_relation": "ATTRIBUTE", "subject": "Huck", "predicate": "appeared", "object": "they"}`
- Template question: What state did Huck become in the account?
- Answer: they
- V2 validation: MEDIUM_LOW_DIAGNOSTIC ['CONFIDENCE_NOT_HIGH']

## 8. The War of the Worlds — OL33027136W__tokens_220__c26c7738e1a19058

- Sentences: 5; clauses: 5
- Source clause: When, an hour later, a Martian appeared beyond the Clock Tower and
waded down the river, nothing but wreckage floated above Limehouse.
- Extractor: ATTRIBUTE; confidence: MEDIUM
- Proposition: `{"relation_type": "ATTRIBUTE", "v3_relation": "ATTRIBUTE", "subject": "Martian", "predicate": "appeared", "object": "beyond"}`
- Template question: What state did Martian become in the account?
- Answer: beyond
- V2 validation: MEDIUM_LOW_DIAGNOSTIC ['CONFIDENCE_NOT_HIGH']

## 9. The Time Machine — OL27039837W__tokens_220__4a2381af0130e098

- Sentences: 11; clauses: 12
- Source clause: Filby became pensive.
- Extractor: ATTRIBUTE; confidence: MEDIUM
- Proposition: `{"relation_type": "ATTRIBUTE", "v3_relation": "ATTRIBUTE", "subject": "Filby", "predicate": "became", "object": "pensive"}`
- Template question: What state did Filby become in the account?
- Answer: pensive
- V2 validation: MEDIUM_LOW_DIAGNOSTIC ['CONFIDENCE_NOT_HIGH']

## 10. A Tale of Two Cities — OL43032614W__tokens_220__8f6c2db7c3db46ad

- Sentences: 9; clauses: 10
- Source clause: Here, Mr. Lorry became aware, from where he sat, of a most remarkable
goblin shadow on the wall.
- Extractor: ATTRIBUTE; confidence: MEDIUM
- Proposition: `{"relation_type": "ATTRIBUTE", "v3_relation": "ATTRIBUTE", "subject": "Mr. Lorry", "predicate": "became", "object": "aware"}`
- Template question: What state did Mr. Lorry become in the account?
- Answer: aware
- V2 validation: MEDIUM_LOW_DIAGNOSTIC ['CONFIDENCE_NOT_HIGH']

## 11. The Importance of Being Earnest — OL33723557W__tokens_220__6c43a35872a7d05b

- Sentences: 17; clauses: 17
- NO_PROPOSITION: no supported explicit pattern

## 12. Alice's Adventures in Wonderland — OL38619874W__tokens_220__1a05e8533ad22fce

- Sentences: 2; clauses: 3
- NO_PROPOSITION: no supported explicit pattern

## 13. The Adventures of Tom Sawyer — OL28944494W__tokens_220__8982de8fed708033

- Sentences: 4; clauses: 8
- NO_PROPOSITION: no supported explicit pattern

## 14. Pride and Prejudice — OL66524W__tokens_220__388ec553efe52948

- Sentences: 8; clauses: 13
- Source clause: They walked towards the Lucases’, because Kitty wished to call upon
Maria;
- Extractor: MOTIVATION; confidence: MEDIUM
- Proposition: `{"relation_type": "MOTIVATION", "v3_relation": "MOTIVATION", "subject": "Kitty", "predicate": "wished", "cause": "to call upon\nMaria", "effect": "Kitty wished to call upon\nMaria"}`
- Template question: What action did Kitty wish to take?
- Answer: to call upon
Maria
- V2 validation: MEDIUM_LOW_DIAGNOSTIC ['CONFIDENCE_NOT_HIGH']

## 15. Dracula — OL85892W__tokens_220__0467f1546f70e70e

- Sentences: 9; clauses: 9
- Source clause: _--Mr. Harker arrived at nine o’clock.
- Extractor: TEMPORAL_AT; confidence: MEDIUM
- Proposition: `{"relation_type": "TEMPORAL", "v3_relation": "TEMPORAL_AT", "subject": "Mr. Harker", "predicate": "arrived", "time": "at nine o’clock"}`
- Template question: At what clock time did Mr. Harker arrive?
- Answer: at nine o’clock
- V2 validation: MEDIUM_LOW_DIAGNOSTIC ['CONFIDENCE_NOT_HIGH']

## 16. Great Expectations — OL41470186W__tokens_220__a3427e26cbce2981

- Sentences: 3; clauses: 4
- Source clause: At breakfast-time my sister declared her intention of going to town
with us, and being left at Uncle Pumblechook’s and called for “when we
had done with our fine ladies”—a way of putting the case, from which
Joe appeared inclined to augur the worst.
- Extractor: ATTRIBUTE; confidence: MEDIUM
- Proposition: `{"relation_type": "ATTRIBUTE", "v3_relation": "ATTRIBUTE", "subject": "Joe", "predicate": "appeared", "object": "inclined"}`
- Template question: What state did Joe become in the account?
- Answer: inclined
- V2 validation: MEDIUM_LOW_DIAGNOSTIC ['CONFIDENCE_NOT_HIGH']

## 17. Frankenstein — OL45326637W__tokens_220__339648c88ffe9088

- Sentences: 6; clauses: 11
- Source clause: Henry wished to dissuade me;
- Extractor: MOTIVATION; confidence: MEDIUM
- Proposition: `{"relation_type": "MOTIVATION", "v3_relation": "MOTIVATION", "subject": "Henry", "predicate": "wished", "cause": "to dissuade me", "effect": "Henry wished to dissuade me"}`
- Template question: What action did Henry wish to take?
- Answer: to dissuade me
- V2 validation: MEDIUM_LOW_DIAGNOSTIC ['CONFIDENCE_NOT_HIGH']

## 18. Jane Eyre — OL36979234W__tokens_220__dcf60be521a7e99b

- Sentences: 8; clauses: 11
- Source clause: Diana and Mary Rivers became more sad and silent as the day approached
for leaving their brother and their home.
- Extractor: ATTRIBUTE; confidence: MEDIUM
- Proposition: `{"relation_type": "ATTRIBUTE", "v3_relation": "ATTRIBUTE", "subject": "Mary Rivers", "predicate": "became", "object": "more"}`
- Template question: What state did Mary Rivers become in the account?
- Answer: more
- V2 validation: MEDIUM_LOW_DIAGNOSTIC ['CONFIDENCE_NOT_HIGH']

## 19. The War of the Worlds — OL33027136W__tokens_220__f1dac0783aa0bced

- Sentences: 9; clauses: 9
- NO_PROPOSITION: no supported explicit pattern

## 20. Adventures of Huckleberry Finn — OL35758281W__tokens_220__7ee92840fc571a64

- Sentences: 7; clauses: 9
- NO_PROPOSITION: no supported explicit pattern
