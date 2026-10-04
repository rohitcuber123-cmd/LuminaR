# V4 probe HIGH source audit

EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS

Inspected all 27 HIGH. Clean: 7. Rejected: 20.
The ≥8 HIGH / zero-failure gate failed. Independent pilot is blocked.

## 0. STATEMENT — REJECT

- Question: Which statement did Stryver make about Mr. Lorry?
- Answer: Then you mean to tell me, Mr. Lorry,
- Source: “Then you mean to tell me, Mr. Lorry,” said Stryver
- Reason: UNCHANGED_V2_VALIDATOR: ANSWER_TOO_VAGUE

## 1. STATEMENT — REJECT

- Question: Which statement did Mr. Lorry make about Not?
- Answer: Not exactly so. I mean to tell you, Mr. Stryver,
- Source: “Not exactly so. I mean to tell you, Mr. Stryver,” said Mr. Lorry
- Reason: UNCHANGED_V2_VALIDATOR: ANSWER_TOO_VAGUE

## 2. LOCATION_TO — CLEAN_ON_SOURCE_INSPECTION

- Question: Where did Skinsky come to on the journey?
- Answer: Hildesheim
- Source: but
there must have been some letter or message, since Skinsky came to
Hildesheim.
- Reason: Named participant, relation, question, and answer match the local source

## 3. ENTITY_RELATION — CLEAN_ON_SOURCE_INSPECTION

- Question: Which person was identified as Mr. Collins's wife?
- Answer: Charlotte
- Source: Charlotte, the wife of Mr. Collins, was a
most humiliating picture!
- Reason: Named participant, relation, question, and answer match the local source

## 4. ATTRIBUTE — CLEAN_ON_SOURCE_INSPECTION

- Question: What change in state did Filby undergo?
- Answer: became pensive
- Source: Filby became pensive.
- Reason: Named participant, relation, question, and answer match the local source

## 5. INSTRUCTION — CLEAN_ON_SOURCE_INSPECTION

- Question: Whom did Miss Temple tell to be seated in a low arm-chair on one side of the
hearth?
- Answer: Helen Burns
- Source: Miss Temple
told Helen Burns to be seated in a low arm-chair on one side of the
hearth, and herself taking another, she called me to her side.
- Reason: Named participant, relation, question, and answer match the local source

## 6. MOTIVATION — CLEAN_ON_SOURCE_INSPECTION

- Question: What action did Bill want to take?
- Answer: to
kill Turner
- Source: Bill wanted to
kill Turner.
- Reason: Named participant, relation, question, and answer match the local source

## 7. LOCATION_FROM — CLEAN_ON_SOURCE_INSPECTION

- Question: Which place did Mr. Gardiner leave on the journey?
- Answer: Longbourn
- Source: Mr. Gardiner left Longbourn on Sunday;
- Reason: Named participant, relation, question, and answer match the local source

## 8. ACTION — REJECT

- Question: What did Quincey find at Walworth and Mile End and destroyed them?
- Answer: the lairs
- Source: that the two doctors and I should remain there, whilst Lord Godalming
and Quincey found the lairs at Walworth and Mile End and destroyed them.
- Reason: ACTION_CONTEXT_DRIFT: question folds a second action into the location context

## 9. STATEMENT — REJECT

- Question: What question did Mrs. Joe ask about Where?
- Answer: Where have you been, you young monkey?
- Source: “Where have you been, you young monkey?” said Mrs. Joe
- Reason: STATEMENT_FALSE_TOPIC: 'Where' is a question word, not a named topic

## 10. STATEMENT — REJECT

- Question: Which statement did Huck make about Now?
- Answer: Now less fetch the guns and things,
- Source: “Now less fetch the guns and things,” said Huck
- Reason: UNCHANGED_V2_VALIDATOR: ANSWER_TOO_VAGUE

## 11. STATEMENT — REJECT

- Question: Which statement did Elizabeth make about Victor?
- Answer: Be happy, my dear Victor,
- Source: "Be happy, my dear Victor," replied Elizabeth
- Reason: UNCHANGED_V2_VALIDATOR: ANSWER_TOO_VAGUE

## 12. STATEMENT — REJECT

- Question: Which statement did Alice make about Really?
- Answer: Really, now you ask me,
- Source: “Really, now you ask me,” said Alice
- Reason: UNCHANGED_V2_VALIDATOR: ANSWER_TOO_VAGUE

## 13. STATEMENT — REJECT

- Question: Which statement did Mr. Camilla make about Much?
- Answer: Much higher than your head, my love,
- Source: “Much higher than your head, my love,” said Mr. Camilla
- Reason: UNCHANGED_V2_VALIDATOR: ANSWER_TOO_VAGUE

## 14. STATEMENT — REJECT

- Question: What question did Jacques ask about Good?
- Answer: Good! You have acted
and recounted faithfully. Will you wait for us a little, outside the
door?
- Source: Jacques said, “Good! You have acted
and recounted faithfully. Will you wait for us a little, outside the
door?”
- Reason: STATEMENT_FALSE_TOPIC: 'Good' is an interjection, not a named topic

## 15. STATEMENT — REJECT

- Question: Which statement did Diana make about Amen?
- Answer: Amen! We can yet live,
- Source: “Amen! We can yet live,” said Diana
- Reason: UNCHANGED_V2_VALIDATOR: ANSWER_TOO_VAGUE

## 16. STATEMENT — REJECT

- Question: Which statement did Tom make about Now?
- Answer: Now, auntie, you know I do care for you,
- Source: “Now, auntie, you know I do care for you,” said Tom
- Reason: UNCHANGED_V2_VALIDATOR: ANSWER_TOO_VAGUE

## 17. STATEMENT — REJECT

- Question: Which statement did Mr. Kirwin make about Your?
- Answer: Your family is perfectly well,
- Source: "Your family is perfectly well," said Mr. Kirwin
- Reason: UNCHANGED_V2_VALIDATOR: ANSWER_TOO_VAGUE

## 18. STATEMENT — REJECT

- Question: Which statement did Alice make about Well?
- Answer: Well, I should like to be a _little_ larger, sir, if you wouldn’t
mind,
- Source: “Well, I should like to be a _little_ larger, sir, if you wouldn’t
mind,” said Alice
- Reason: UNCHANGED_V2_VALIDATOR: ANSWER_TOO_VAGUE

## 19. STATEMENT — REJECT

- Question: Which statement did Carton make about Ace?
- Answer: I play my Ace, Mr. Barsad,
- Source: “I play my Ace, Mr. Barsad,” said Carton
- Reason: UNCHANGED_V2_VALIDATOR: ANSWER_TOO_VAGUE

## 20. STATEMENT — REJECT

- Question: What question did Miss Havisham ask about Have?
- Answer: Have you brought his indentures with you?
- Source: “Have you brought his indentures with you?” asked Miss Havisham
- Reason: STATEMENT_FALSE_TOPIC: 'Have' is a question auxiliary, not a named topic

## 21. STATEMENT — REJECT

- Question: Which statement did Elizabeth make about Nothing?
- Answer: Nothing so easy, if you have but the inclination,
- Source: “Nothing so easy, if you have but the inclination,” said Elizabeth
- Reason: UNCHANGED_V2_VALIDATOR: ANSWER_TOO_VAGUE

## 22. STATEMENT — REJECT

- Question: What question did Bessie ask about Miss?
- Answer: Do you feel as if you should sleep, Miss?
- Source: “Do you feel as if you should sleep, Miss?” asked Bessie
- Reason: STATEMENT_FALSE_TOPIC: 'Miss' is a form of address, not a named topic

## 23. STATEMENT — REJECT

- Question: Which statement did Van Helsing make about Madam Mina?
- Answer: I swear the same, my dear Madam Mina!
- Source: “I swear the same, my dear Madam Mina!” said Van Helsing
- Reason: STATEMENT_CONTEXT_DEPENDENT: 'I swear the same' lacks the referred pledge

## 24. STATEMENT — REJECT

- Question: Which statement did Tom make about Joe?
- Answer: Oh no, Joe, you’ll feel better by and by,
- Source: “Oh no, Joe, you’ll feel better by and by,” said Tom
- Reason: UNCHANGED_V2_VALIDATOR: ANSWER_TOO_VAGUE

## 25. STATEMENT — REJECT

- Question: Which statement did Alice make about Well?
- Answer: Well, perhaps your feelings may be different,
- Source: “Well, perhaps your feelings may be different,” said Alice
- Reason: UNCHANGED_V2_VALIDATOR: ANSWER_TOO_VAGUE

## 26. ATTRIBUTE — CLEAN_ON_SOURCE_INSPECTION

- Question: What profession or role did Mr. Kirwin hold?
- Answer: a magistrate
- Source: Mr. Kirwin is a magistrate;
- Reason: Named participant, relation, question, and answer match the local source
