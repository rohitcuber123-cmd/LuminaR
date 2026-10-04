# LuminaR domain QA source review

**EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS**

**Diagnostic packet:** this generation batch failed a semantic-quality spot review. Do not bulk-approve it. Edit or reject each item against the source; this packet is far below the 200-reviewed-example training gate.

Mark the companion CSV with APPROVE, REJECT, or EDIT; name the reviewer and mark every checklist column YES for an approved item. For EDIT, enter only changed fields. These are unreviewed candidates. Retriever rankings are intentionally absent.

## DQ00001 — Jane Eyre

- Split: TRAIN; chapter: CHAPTER III; category: FACTUAL_DIRECT; difficulty: EASY
- Question: Who was being charged by the man to be careful about the narrator during the night?
- Short answer: Bessie
- Evidence: ” Then he laid
me down, and addressing Bessie, charged her to be very careful that I
was not disturbed during the night.
- Source offsets: 33241–33361; chunk: OL36979234W__tokens_220__4ac7e90406ec0b2c
- Validation note: Exact evidence and answer containment verified; semantic support awaits review. Category, referents, and answerability need human review.

```text
Lloyd, an apothecary,
sometimes called in by Mrs. Reed when the servants were ailing: for
herself and the children she employed a physician.

“Well, who am I?” he asked.

I pronounced his name, offering him at the same time my hand: he took
it, smiling and saying, “We shall do very well by-and-by.” Then he laid
me down, and addressing Bessie, charged her to be very careful that I
was not disturbed during the night. Having given some further
directions, and intimated that he should call again the next day, he
departed; to my grief: I felt so sheltered and befriended while he sat
in the chair near my pillow; and as he closed the door after him, all
the room darkened and my heart again sank: inexpressible sadness
weighed it down.

“Do you feel as if you should sleep, Miss?” asked Bessie, rather
softly.

Scarcely dared I answer her; for I feared the next sentence might be
rough. “I will try.”
```

## DQ00002 — The Adventures of Tom Sawyer

- Split: TRAIN; chapter: CHAPTER XII; category: LOCATION; difficulty: EASY
- Question: Where did Tom see another frock pass in at?
- Short answer: at the gate
- Evidence: Then one more frock passed
in at the gate, and Tom’s heart gave a great bound.
- Source offsets: 150463–150541; chunk: OL28944494W__tokens_220__722bbc43186a2124
- Validation note: Exact evidence and answer containment verified; semantic support awaits review. Category, referents, and answerability need human review.

```text
At last frocks
ceased to appear, and he dropped hopelessly into the dumps; he entered
the empty schoolhouse and sat down to suffer. Then one more frock passed
in at the gate, and Tom’s heart gave a great bound. The next instant he
was out, and “going on” like an Indian; yelling, laughing, chasing boys,
jumping over the fence at risk of life and limb, throwing handsprings,
standing on his head—doing all the heroic things he could conceive of,
and keeping a furtive eye out, all the while, to see if Becky Thatcher
was noticing. But she seemed to be unconscious of it all; she never
looked. Could it be possible that she was not aware that he was there?
```

## DQ00003 — Great Expectations

- Split: TRAIN; chapter: Chapter XV.; category: SEMANTIC_PARAPHRASE; difficulty: EASY
- Question: What did Old Orlick do upon hearing the news?
- Short answer: growled
- Evidence: ”

Old Orlick growled, as if he had nothing to say about that, and we all
went on together.
- Source offsets: 239071–239162; chunk: OL41470186W__tokens_220__e432800001646326
- Validation note: Exact evidence and answer containment verified; semantic support awaits review. Category, referents, and answerability need human review.

```text
We were noticing this, and saying how that the mist rose
with a change of wind from a certain quarter of our marshes, when we
came upon a man, slouching under the lee of the turnpike house.

“Halloa!” we said, stopping. “Orlick there?”

“Ah!” he answered, slouching out. “I was standing by a minute, on the
chance of company.”

“You are late,” I remarked.

Orlick not unnaturally answered, “Well? And _you_’re late.”

“We have been,” said Mr. Wopsle, exalted with his late performance,—“we
have been indulging, Mr. Orlick, in an intellectual evening.”

Old Orlick growled, as if he had nothing to say about that, and we all
went on together. I asked him presently whether he had been spending
his half-holiday up and down town?
```

## DQ00004 — Frankenstein

- Split: TRAIN; chapter: CHAPTER XX.; category: ENTITY_RELATION; difficulty: EASY
- Question: Who was selected by the magistrate to testify?
- Short answer: Daniel Nugent
- Evidence: About half a dozen men came forward; and, one being selected by the
magistrate, he deposed, that he had been out fishing the night before
with his son and brother-in-law, Daniel Nugent, when, about ten o'clock,
they observed a strong northerly blast rising, and they accordingly put
in for port.
- Source offsets: 337892–338187; chunk: OL45326637W__tokens_220__f90d5824ced32858
- Validation note: Exact evidence and answer containment verified; semantic support awaits review. Category, referents, and answerability need human review.

```text
I must pause here; for it requires all my fortitude to recall the memory
of the frightful events which I am about to relate, in proper detail, to
my recollection.

CHAPTER XXI.

I was soon introduced into the presence of the magistrate, an old
benevolent man, with calm and mild manners. He looked upon me, however,
with some degree of severity: and then, turning towards my conductors,
he asked who appeared as witnesses on this occasion.

About half a dozen men came forward; and, one being selected by the
magistrate, he deposed, that he had been out fishing the night before
with his son and brother-in-law, Daniel Nugent, when, about ten o'clock,
they observed a strong northerly blast rising, and they accordingly put
in for port. It was a very dark night, as the moon had not yet risen;
they did not land at the harbour, but, as they had been accustomed, at a
creek about two miles below.
```

## DQ00005 — The Time Machine

- Split: TRAIN; chapter: Epilogue; category: EVENT; difficulty: EASY
- Question: What did the feeding of an Underworld become?
- Short answer: disjointed
- Evidence: Apparently as time went on, the feeding
of an Underworld, however it was effected, had become disjointed.
- Source offsets: 153768–153873; chunk: OL27039837W__tokens_220__1b0b9b91b89973cb
- Validation note: Exact evidence and answer containment verified; semantic support awaits review. Category, referents, and answerability need human review.

```text
Nature never
appeals to intelligence until habit and instinct are useless. There is
no intelligence where there is no change and no need of change. Only
those animals partake of intelligence that have to meet a huge variety
of needs and dangers.

“So, as I see it, the Upperworld man had drifted towards his feeble
prettiness, and the Underworld to mere mechanical industry. But that
perfect state had lacked one thing even for mechanical
perfection—absolute permanency. Apparently as time went on, the feeding
of an Underworld, however it was effected, had become disjointed.
Mother Necessity, who had been staved off for a few thousand years,
came back again, and she began below. The Underworld being in contact
with machinery, which, however perfect, still needs some little thought
outside habit, had probably retained perforce rather more initiative,
if less of every other human character, than the Upper. And when other
meat failed them, they turned to what old habit had hitherto forbidden.
```

## DQ00006 — Adventures of Huckleberry Finn

- Split: TRAIN; chapter: CHAPTER XXXII.; category: CAUSAL; difficulty: EASY
- Question: What caused the narrator to feel cold chills?
- Short answer: But here we’re a-running on this way
- Evidence: Pretty soon she made the cold chills
streak all down my back, because she says:

“But here we’re a-running on this way, and you hain’t told me a word
about Sis, nor any of them.
- Source offsets: 436081–436258; chunk: OL35758281W__tokens_220__278031021979d46f
- Validation note: Exact evidence and answer containment verified; semantic support awaits review. Category, referents, and answerability need human review.

```text
I had my mind on the
children all the time; I wanted to get them out to one side and pump
them a little, and find out who I was. But I couldn’t get no show, Mrs.
Phelps kept it up and run on so. Pretty soon she made the cold chills
streak all down my back, because she says:

“But here we’re a-running on this way, and you hain’t told me a word
about Sis, nor any of them. Now I’ll rest my works a little, and you
start up yourn; just tell me _everything_—tell me all about ’m all
every one of ’m; and how they are, and what they’re doing, and what
they told you to tell me; and every last thing you can think of.”
```

## DQ00007 — Pride and Prejudice

- Split: TRAIN; chapter: CHAPTER LII.; category: TEMPORAL; difficulty: EASY
- Question: When does the narrator say he likes Lizzy's boyfriend?
- Short answer: before)
- Evidence: Will you be very angry with me, my dear
Lizzy, if I take this opportunity of saying (what I was never bold
enough to say before) how much I like him?
- Source offsets: 606878–607027; chunk: OL66524W__tokens_220__78cb461f45a34b63
- Validation note: Exact evidence and answer containment verified; semantic support awaits review. Category, referents, and answerability need human review.

```text
Darcy was punctual
in his return, and, as Lydia informed you, attended the wedding. He
dined with us the next day, and was to leave town again on
Wednesday or Thursday. Will you be very angry with me, my dear
Lizzy, if I take this opportunity of saying (what I was never bold
enough to say before) how much I like him? His behaviour to us has,
in every respect, been as pleasing as when we were in Derbyshire.
His understanding and opinions all please me; he wants nothing but
a little more liveliness, and _that_, if he marry _prudently_, his
wife may teach him. I thought him very sly; he hardly ever
mentioned your name. But slyness seems the fashion. Pray forgive
me, if I have been very presuming, or at least do not punish me so
far as to exclude me from P. I shall never be quite happy till I
have been all round the park.
```

## DQ00008 — Pride and Prejudice

- Split: TRAIN; chapter: CHAPTER LVI.; category: MOTIVATION; difficulty: EASY
- Question: Why did the speaker come here?
- Short answer: with the determined resolution of carrying my purpose
- Evidence: You are to understand, Miss Bennet, that I came
here with the determined resolution of carrying my purpose; nor will I
be dissuaded from it.
- Source offsets: 661692–661832; chunk: OL66524W__tokens_220__d49cc77547cd0d41
- Validation note: Exact evidence and answer containment verified; semantic support awaits review. Category, referents, and answerability need human review.

```text
“These are heavy misfortunes,” replied Elizabeth. “But the wife of Mr.
Darcy must have such extraordinary sources of happiness necessarily
attached to her situation, that she could, upon the whole, have no cause
to repine.”

“Obstinate, headstrong girl! I am ashamed of you! Is this your gratitude
for my attentions to you last spring? Is nothing due to me on that
score? Let us sit down. You are to understand, Miss Bennet, that I came
here with the determined resolution of carrying my purpose; nor will I
be dissuaded from it. I have not been used to submit to any person’s
whims. I have not been in the habit of brooking disappointment.”

“_That_ will make your Ladyship’s situation at present more pitiable;
but it will have no effect on _me_.”
```

## DQ00009 — Jane Eyre

- Split: TRAIN; chapter: CHAPTER X; category: QUOTE_OR_PHRASE; difficulty: EASY
- Question: What did the narrator argue about Thornfield?
- Short answer: Thornfield will
- Evidence: Not that my fancy was much captivated by the idea of
long chimneys and clouds of smoke—“but,” I argued, “Thornfield will,
probably, be a good way from the town.
- Source offsets: 194333–194493; chunk: OL36979234W__tokens_220__cc4d2730f0cd7291
- Validation note: Exact evidence and answer containment verified; semantic support awaits review. Category, referents, and answerability need human review.

```text
I longed to go where there was life and movement:
Millcote was a large manufacturing town on the banks of the A——: a busy
place enough, doubtless: so much the better; it would be a complete
change at least. Not that my fancy was much captivated by the idea of
long chimneys and clouds of smoke—“but,” I argued, “Thornfield will,
probably, be a good way from the town.”

Here the socket of the candle dropped, and the wick went out.

Next day new steps were to be taken; my plans could no longer be
confined to my own breast; I must impart them in order to achieve their
success. Having sought and obtained an audience of the superintendent
during the noontide recreation, I told her I had a prospect of getting
a new situation where the salary would be double what I now received
(for at Lowood I only got £15 per annum); and requested she would break
the matter for me to Mr.
```

## DQ00010 — Pride and Prejudice

- Split: TRAIN; chapter: CHAPTER XXVI.; category: FACTUAL_DIRECT; difficulty: EASY
- Question: What did Elizabeth have to send that would make her aunt contented?
- Short answer: information
- Evidence: Gardiner about this time reminded Elizabeth of her promise
concerning that gentleman, and required information; and Elizabeth had
such to send as might rather give contentment to her aunt than to
herself.
- Source offsets: 293672–293876; chunk: OL66524W__tokens_220__56366b6a5c55b283
- Validation note: Exact evidence and answer containment verified; semantic support awaits review. Category, referents, and answerability need human review.

```text
His character sunk on every
review of it; and, as a punishment for him, as well as a possible
advantage to Jane, she seriously hoped he might really soon marry Mr.
Darcy’s sister, as, by Wickham’s account, she would make him abundantly
regret what he had thrown away.

Mrs. Gardiner about this time reminded Elizabeth of her promise
concerning that gentleman, and required information; and Elizabeth had
such to send as might rather give contentment to her aunt than to
herself. His apparent partiality had subsided, his attentions were over,
he was the admirer of some one else. Elizabeth was watchful enough to
see it all, but she could see it and write of it without material pain.
Her heart had been but slightly touched, and her vanity was satisfied
with believing that _she_ would have been his only choice, had fortune
permitted it.
```
