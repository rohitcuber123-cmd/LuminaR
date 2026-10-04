# V4 30-chunk mechanics probe

EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS

Stats: `{'chunks': 30, 'sentences': 271, 'clauses': 340, 'can_match_cues': 111, 'relation_matches': 30, 'HIGH': 27, 'SEMANTIC_FAILED': 14, 'validator_failures': 14, 'AUTO_VALIDATED': 13, 'MEDIUM': 2, 'MEDIUM_LOW_DIAGNOSTIC': 2, 'duplicate_propositions': 1}`
Relations: `{'STATEMENT': 19, 'LOCATION_TO': 1, 'ENTITY_RELATION': 1, 'ATTRIBUTE': 4, 'INSTRUCTION': 1, 'MOTIVATION': 1, 'LOCATION_FROM': 1, 'ACTION': 1}`
Source ranges SHA-256: `f195ab4c7213b4fa147941b250f3c4891edd8305aa4c5a0469525ea7329e7276`

## A Tale of Two Cities — OL43032614W__tokens_220__ea56c57d1d6695fc

Range: [284273, 284880]

- HIGH STATEMENT: Which statement did Stryver make about Mr. Lorry? → Then you mean to tell me, Mr. Lorry,
  Source: “Then you mean to tell me, Mr. Lorry,” said Stryver
  Validation: SEMANTIC_FAILED ['ANSWER_TOO_VAGUE']
- HIGH STATEMENT: Which statement did Mr. Lorry make about Not? → Not exactly so. I mean to tell you, Mr. Stryver,
  Source: “Not exactly so. I mean to tell you, Mr. Stryver,” said Mr. Lorry
  Validation: SEMANTIC_FAILED ['ANSWER_TOO_VAGUE']

## Dracula — OL85892W__tokens_220__e516e275ed3c5122

Range: [779309, 780180]

- HIGH LOCATION_TO: Where did Skinsky come to on the journey? → Hildesheim
  Source: but
there must have been some letter or message, since Skinsky came to
Hildesheim.
  Validation: AUTO_VALIDATED []

## Pride and Prejudice — OL66524W__tokens_220__67be71e90c5fab45

Range: [252641, 253608]

- HIGH ENTITY_RELATION: Which person was identified as Mr. Collins's wife? → Charlotte
  Source: Charlotte, the wife of Mr. Collins, was a
most humiliating picture!
  Validation: AUTO_VALIDATED []

## The Time Machine — OL27039837W__tokens_220__4a2381af0130e098

Range: [1975, 2868]

- HIGH ATTRIBUTE: What change in state did Filby undergo? → became pensive
  Source: Filby became pensive.
  Validation: AUTO_VALIDATED []
- MEDIUM ATTRIBUTE: What state did Filby become in the account? → pensive
  Source: Filby became pensive.
  Validation: MEDIUM_LOW_DIAGNOSTIC ['NO_V4_EVIDENCE_CONTRACT']

## Jane Eyre — OL36979234W__tokens_220__67e51678a3f1fb52

Range: [150374, 151204]

- HIGH INSTRUCTION: Whom did Miss Temple tell to be seated in a low arm-chair on one side of the
hearth? → Helen Burns
  Source: Miss Temple
told Helen Burns to be seated in a low arm-chair on one side of the
hearth, and herself taking another, she called me to her side.
  Validation: AUTO_VALIDATED []

## Adventures of Huckleberry Finn — OL35758281W__tokens_220__97dce02a214a9eef

Range: [142562, 143267]

- HIGH MOTIVATION: What action did Bill want to take? → to
kill Turner
  Source: Bill wanted to
kill Turner.
  Validation: AUTO_VALIDATED []

## Pride and Prejudice — OL66524W__tokens_220__09452ca5a6a39f88

Range: [550351, 551309]

- HIGH LOCATION_FROM: Which place did Mr. Gardiner leave on the journey? → Longbourn
  Source: Mr. Gardiner left Longbourn on Sunday;
  Validation: AUTO_VALIDATED []

## Dracula — OL85892W__tokens_220__c94a28abc3dd9f4e

Range: [651453, 652169]

- HIGH ACTION: What did Quincey find at Walworth and Mile End and destroyed them? → the lairs
  Source: that the two doctors and I should remain there, whilst Lord Godalming
and Quincey found the lairs at Walworth and Mile End and destroyed them.
  Validation: AUTO_VALIDATED []

## Great Expectations — OL41470186W__tokens_220__f4eea167f99ad34b

Range: [13690, 14470]

- HIGH STATEMENT: What question did Mrs. Joe ask about Where? → Where have you been, you young monkey?
  Source: “Where have you been, you young monkey?” said Mrs. Joe
  Validation: AUTO_VALIDATED []

## The Adventures of Tom Sawyer — OL28944494W__tokens_220__5c28d39d634c2315

Range: [373225, 373981]

- HIGH STATEMENT: Which statement did Huck make about Now? → Now less fetch the guns and things,
  Source: “Now less fetch the guns and things,” said Huck
  Validation: SEMANTIC_FAILED ['ANSWER_TOO_VAGUE']

## Frankenstein — OL45326637W__tokens_220__53643f9e9676d31c

Range: [375110, 376029]

- HIGH STATEMENT: Which statement did Elizabeth make about Victor? → Be happy, my dear Victor,
  Source: "Be happy, my dear Victor," replied Elizabeth
  Validation: SEMANTIC_FAILED ['ANSWER_TOO_VAGUE']

## Alice's Adventures in Wonderland — OL38619874W__tokens_220__ee1fd30a2b71749a

Range: [82549, 83392]

- HIGH STATEMENT: Which statement did Alice make about Really? → Really, now you ask me,
  Source: “Really, now you ask me,” said Alice
  Validation: SEMANTIC_FAILED ['ANSWER_TOO_VAGUE']

## Great Expectations — OL41470186W__tokens_220__c66c6788715a24ab

Range: [174673, 175262]

- HIGH STATEMENT: Which statement did Mr. Camilla make about Much? → Much higher than your head, my love,
  Source: “Much higher than your head, my love,” said Mr. Camilla
  Validation: SEMANTIC_FAILED ['ANSWER_TOO_VAGUE']

## A Tale of Two Cities — OL43032614W__tokens_220__4e918a09826db732

Range: [339996, 340779]

- HIGH STATEMENT: What question did Jacques ask about Good? → Good! You have acted
and recounted faithfully. Will you wait for us a little, outside the
door?
  Source: Jacques said, “Good! You have acted
and recounted faithfully. Will you wait for us a little, outside the
door?”
  Validation: AUTO_VALIDATED []

## Jane Eyre — OL36979234W__tokens_220__378ccd242ef09b0e

Range: [804938, 805426]

- HIGH STATEMENT: Which statement did Diana make about Amen? → Amen! We can yet live,
  Source: “Amen! We can yet live,” said Diana
  Validation: SEMANTIC_FAILED ['ANSWER_TOO_VAGUE']

## The Adventures of Tom Sawyer — OL28944494W__tokens_220__d797b9b41db3c870

Range: [211375, 212049]

- HIGH STATEMENT: Which statement did Tom make about Now? → Now, auntie, you know I do care for you,
  Source: “Now, auntie, you know I do care for you,” said Tom
  Validation: SEMANTIC_FAILED ['ANSWER_TOO_VAGUE']

## Frankenstein — OL45326637W__tokens_220__694ebeab2c91d18a

Range: [349054, 349890]

- HIGH STATEMENT: Which statement did Mr. Kirwin make about Your? → Your family is perfectly well,
  Source: "Your family is perfectly well," said Mr. Kirwin
  Validation: SEMANTIC_FAILED ['ANSWER_TOO_VAGUE']

## Alice's Adventures in Wonderland — OL38619874W__tokens_220__bed77d91ce5c4204

Range: [50519, 51264]

- HIGH STATEMENT: Which statement did Alice make about Well? → Well, I should like to be a _little_ larger, sir, if you wouldn’t
mind,
  Source: “Well, I should like to be a _little_ larger, sir, if you wouldn’t
mind,” said Alice
  Validation: SEMANTIC_FAILED ['ANSWER_TOO_VAGUE']

## A Tale of Two Cities — OL43032614W__tokens_220__2cddc98346195d16

Range: [605108, 605958]

- HIGH STATEMENT: Which statement did Carton make about Ace? → I play my Ace, Mr. Barsad,
  Source: “I play my Ace, Mr. Barsad,” said Carton
  Validation: SEMANTIC_FAILED ['ANSWER_TOO_VAGUE']

## Great Expectations — OL41470186W__tokens_220__2ae13149033a7f9c

Range: [203148, 203655]

- HIGH STATEMENT: What question did Miss Havisham ask about Have? → Have you brought his indentures with you?
  Source: “Have you brought his indentures with you?” asked Miss Havisham
  Validation: AUTO_VALIDATED []

## Pride and Prejudice — OL66524W__tokens_220__a322923a89475507

Range: [122899, 123560]

- HIGH STATEMENT: Which statement did Elizabeth make about Nothing? → Nothing so easy, if you have but the inclination,
  Source: “Nothing so easy, if you have but the inclination,” said Elizabeth
  Validation: SEMANTIC_FAILED ['ANSWER_TOO_VAGUE']

## Jane Eyre — OL36979234W__tokens_220__4ac7e90406ec0b2c

Range: [32943, 33844]

- HIGH STATEMENT: What question did Bessie ask about Miss? → Do you feel as if you should sleep, Miss?
  Source: “Do you feel as if you should sleep, Miss?” asked Bessie
  Validation: AUTO_VALIDATED []

## Dracula — OL85892W__tokens_220__3cb3df5d1f5ae5fe

Range: [732481, 733300]

- HIGH STATEMENT: Which statement did Van Helsing make about Madam Mina? → I swear the same, my dear Madam Mina!
  Source: “I swear the same, my dear Madam Mina!” said Van Helsing
  Validation: AUTO_VALIDATED []

## The Adventures of Tom Sawyer — OL28944494W__tokens_220__659c3e428d4dbbc4

Range: [188842, 189591]

- HIGH STATEMENT: Which statement did Tom make about Joe? → Oh no, Joe, you’ll feel better by and by,
  Source: “Oh no, Joe, you’ll feel better by and by,” said Tom
  Validation: SEMANTIC_FAILED ['ANSWER_TOO_VAGUE']

## Alice's Adventures in Wonderland — OL38619874W__tokens_220__7cdea4d939c4414d

Range: [47108, 47939]

- HIGH STATEMENT: Which statement did Alice make about Well? → Well, perhaps your feelings may be different,
  Source: “Well, perhaps your feelings may be different,” said Alice
  Validation: SEMANTIC_FAILED ['ANSWER_TOO_VAGUE']

## Frankenstein — OL45326637W__tokens_220__383c8428eae0d635

Range: [336720, 337627]

- HIGH ATTRIBUTE: What profession or role did Mr. Kirwin hold? → a magistrate
  Source: Mr. Kirwin is a magistrate;
  Validation: AUTO_VALIDATED []

## The War of the Worlds — OL33027136W__tokens_220__c26c7738e1a19058

Range: [190786, 191628]

- MEDIUM ATTRIBUTE: What state did Martian become in the account? → beyond
  Source: When, an hour later, a Martian appeared beyond the Clock Tower and
waded down the river, nothing but wreckage floated above Limehouse.
  Validation: MEDIUM_LOW_DIAGNOSTIC ['NO_V4_EVIDENCE_CONTRACT']

## The Importance of Being Earnest — OL33723557W__tokens_220__6c43a35872a7d05b

Range: [108666, 109557]


## The War of the Worlds — OL33027136W__tokens_220__f1dac0783aa0bced

Range: [191420, 192192]


## Adventures of Huckleberry Finn — OL35758281W__tokens_220__7ee92840fc571a64

Range: [478326, 478812]

