# RAG retrieval v1 — independent source-label review

Review the source excerpts without consulting any retriever output. For each
question, verify the premise and answer, decide whether each span is directly
answer-bearing, find omitted valid passages, and check boundary/neighbor notes.
Record decisions in the versioned JSON; this packet itself does not mark labels
reviewed. All current labels are assistant-authored DRAFTs.

## v8_01 — Frankenstein (DEV)

**Question:** Why does Victor create the creature?

**Category/difficulty/ambiguity:** MOTIVATION / MEDIUM / MULTIPLE_VALID

**Draft note:** Victor's ambition to create life is explicit here; reviewer should assess other equally direct motives.

**Passage 1:** CHAPTER IV., source [94731, 94965), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL45326637W_000044', 'next': None}

```text
nds, which I should first break through, and pour a
torrent of light into our dark world. A new species would bless me as
its creator and source; many happy and excellent natures would owe their
being to me. No father could claim the 
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## v8_02 — Frankenstein (DEV)

**Question:** Who is Victor's father?

**Category/difficulty/ambiguity:** BOUNDARY_SENSITIVE / EASY / BOUNDARY

**Draft note:** Father's signature appears near an overlapping chunk edge; check narrative references too.

**Passage 1:** CHAPTER VII., source [132933, 133165), grade 2, neighbor allowance True

**Adjacent covering chunks:** {'previous': None, 'current': 'OL45326637W_000061', 'next': None}

```text
. Enter the house of mourning, my
friend, but with kindness and affection for those who love you, and not
with hatred for your enemies.

"Your affectionate and afflicted father,

"ALPHONSE FRANKENSTEIN.

"Geneva, May 12th, 17--."

*
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## v8_03 — Frankenstein (DEV)

**Question:** Why doesn't Victor create a female creature?

**Category/difficulty/ambiguity:** MOTIVATION / MEDIUM / MULTIPLE_VALID

**Draft note:** One stated fear behind destroying the female companion; other feared consequences may also answer.

**Passage 1:** CHAPTER XIX., source [319980, 320241), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL45326637W_000146', 'next': None}

```text
he deserts of the new
world, yet one of the first results of those sympathies for which the
dæmon thirsted would be children, and a race of devils would be
propagated upon the earth, who might make the very existence of the
species of man a condition precarious
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## v8_04 — Frankenstein (DEV)

**Question:** What happens after Victor creates the creature?

**Category/difficulty/ambiguity:** EVENT / MEDIUM / BOUNDARY

**Draft note:** Question is broad; immediate horrified reaction is one answer. Review whether flight and fever also require accepted spans.

**Passage 1:** CHAPTER V., source [102037, 102340), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL45326637W_000048', 'next': None}

```text
f rest and health. I had desired it with an ardour that far
exceeded moderation; but now that I had finished, the beauty of the
dream vanished, and breathless horror and disgust filled my heart.
Unable to endure the aspect of the being I had created, I rushed out of
the room, and continued a long time 
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## v8_05 — Dracula (DEV)

**Question:** Why does Dracula travel to London?

**Category/difficulty/ambiguity:** MOTIVATION / HARD / QUESTIONABLE

**Draft note:** The question presupposes a single explicit motive for Dracula's travel. Source-first inspection did not establish one; exclude from primary metrics pending human judgment.

**No accepted passage; premise requires adjudication.**

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## v8_06 — Dracula (DEV)

**Question:** Why doesn't Jonathan Harker leave the castle?

**Category/difficulty/ambiguity:** CAUSAL / EASY / BOUNDARY

**Draft note:** Harker explicitly discovers he is confined; overlapping chunks may both contain the answer.

**Passage 1:** CHAPTER II, source [60944, 61188), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': 'OL85892W_000028', 'current': 'OL85892W_000029', 'next': None}

```text
cked and
bolted. In no place save from the windows in the castle walls is there
an available exit.

The castle is a veritable prison, and I am a prisoner!

CHAPTER III

JONATHAN HARKER’S JOURNAL--_continued_

When I found that I was a prisoner 
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## v8_07 — Dracula (DEV)

**Question:** Who is Mina's husband?

**Category/difficulty/ambiguity:** ENTITY_RELATION / EASY / MULTIPLE_VALID

**Draft note:** Separate direct references to Mina's husband.

**Passage 1:** CHAPTER VIII, source [223111, 223271), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL85892W_000104', 'next': None}

```text
 be that ... I must write no more; I must keep it to say
to Jonathan, my husband. The letter that he has seen and touched must
comfort me till we meet.

_Letter
```

**Passage 2:** CHAPTER XXIII, source [684370, 684530), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL85892W_000311', 'next': None}

```text
, hush! in the name of the good God. Don’t say such things,
Jonathan, my husband; or you will crush me with fear and horror. Just
think, my dear--I have been th
```

**Passage 3:** CHAPTER XIV, source [407566, 407746), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL85892W_000186', 'next': None}

```text
you must eat. You are overwrought and perhaps over-anxious.
Husband Jonathan would not like to see you so pale; and what he like not
where he love, is not to his good. Therefore fo
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## v8_08 — Dracula (DEV)

**Question:** What ship transported Dracula to England?

**Category/difficulty/ambiguity:** FACTUAL_DIRECT / MEDIUM / MULTIPLE_VALID

**Draft note:** Ship name appears in the landing account and later retrospective reference.

**Passage 1:** CHAPTER VII, source [181764, 181989), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL85892W_000085', 'next': None}

```text
rm last night is almost more startling than the thing itself. It
turns out that the schooner is a Russian from Varna, and is called the
_Demeter_. She is almost entirely in ballast of silver sand, with only a
small amount of 
```

**Passage 2:** CHAPTER XVII, source [500900, 501121), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL85892W_000227', 'next': None}

```text
d, I think, have raised his terms.

Of one thing I am now satisfied: that _all_ the boxes which arrived at
Whitby from Varna in the _Demeter_ were safely deposited in the old
chapel at Carfax. There should be fifty of the
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## v8_09 — Frankenstein (DEV)

**Question:** Why does Victor regret creating the creature?

**Category/difficulty/ambiguity:** MOTIVATION / HARD / MULTIPLE_VALID

**Draft note:** Broad regret question needs human adjudication for all direct reasons and consequences.

**Passage 1:** CHAPTER IX., source [170312, 170663), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL45326637W_000078', 'next': None}

```text
mong them?

At these moments I wept bitterly, and wished that peace would revisit my
mind only that I might afford them consolation and happiness. But that
could not be. Remorse extinguished every hope. I had been the author of
unalterable evils; and I lived in daily fear, lest the monster whom I
had created should perpetrate some new wickedness. I 
```

**Passage 2:** CHAPTER X., source [189812, 190106), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL45326637W_000087', 'next': 'OL45326637W_000088'}

```text
 to my remembrance," I rejoined, "circumstances, of
which I shudder to reflect, that I have been the miserable origin and
author? Cursed be the day, abhorred devil, in which you first saw light!
Cursed (although I curse myself) be the hands that formed you! You have
made me wretched beyond exp
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## v8_10 — Frankenstein (DEV)

**Question:** What happens when Victor first sees the creature?

**Category/difficulty/ambiguity:** EVENT / MEDIUM / BOUNDARY

**Draft note:** Both animation and Victor's immediate reaction may count, depending on human interpretation.

**Passage 1:** CHAPTER IV., source [100778, 101024), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL45326637W_000047', 'next': None}

```text
the panes, and my candle was
nearly burnt out, when, by the glimmer of the half-extinguished light, I
saw the dull yellow eye of the creature open; it breathed hard, and a
convulsive motion agitated its limbs.

[Illustration: "_By the glimmer of 
```

**Passage 2:** CHAPTER V., source [103176, 103477), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL45326637W_000048', 'next': None}

```text
d: when, by the dim and yellow light of
the moon, as it forced its way through the window shutters, I beheld the
wretch--the miserable monster whom I had created. He held up the curtain
of the bed; and his eyes, if eyes they may be called, were fixed on me.
His jaws opened, and he muttered some inart
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## pp_01 — Pride and Prejudice (DEV)

**Question:** Which estate has been let to a wealthy young man from northern England?

**Category/difficulty/ambiguity:** LOCATION / EASY / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** Unknown, source [29830, 30068), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL66524W_000014', 'next': None}

```text
by George Allen._]]

This was invitation enough.

“Why, my dear, you must know, Mrs. Long says that Netherfield is taken
by a young man of large fortune from the north of England; that he came
down on Monday in a chaise and four to see th
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## pp_02 — Pride and Prejudice (DEV)

**Question:** How does Darcy describe Elizabeth when declining to dance with her?

**Category/difficulty/ambiguity:** QUOTE_OR_PHRASE / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** CHAPTER III., source [44095, 44340), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL66524W_000020', 'next': None}

```text
 and turning round, he looked for a moment at
Elizabeth, till, catching her eye, he withdrew his own, and coldly said,
“She is tolerable: but not handsome enough to tempt _me_; and I am in no
humour at present to give consequence to young ladies
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## pp_03 — Pride and Prejudice (DEV)

**Question:** Whom does Charlotte Lucas agree to marry?

**Category/difficulty/ambiguity:** ENTITY_RELATION / EASY / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** CHAPTER XXII., source [251514, 251738), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL66524W_000110', 'next': None}

```text
eat as to overcome at first the bounds of decorum, and
she could not help crying out,--

“Engaged to Mr. Collins! my dear Charlotte, impossible!”

The steady countenance which Miss Lucas had commanded in telling her
story ga
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## pp_04 — Pride and Prejudice (DEV)

**Question:** To whom is Mr. Bennet's estate entailed?

**Category/difficulty/ambiguity:** ENTITY_RELATION / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** CHAPTER XXIX., source [319716, 319959), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL66524W_000139', 'next': None}

```text
l the impertinence of her
questions, but answered them very composedly. Lady Catherine then
observed,--

“Your father’s estate is entailed on Mr. Collins, I think? For your
sake,” turning to Charlotte, “I am glad of it; but otherwise I see no

```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## pp_05 — Pride and Prejudice (DEV)

**Question:** Which man does Lydia leave Brighton with, alarming her family?

**Category/difficulty/ambiguity:** EVENT / MEDIUM / CLEAR

**Draft note:** The letter connects Wickham and Lydia's flight with Colonel Forster's departure from Brighton; review whether a more concise span exists.

**Passage 1:** Chapter XLVI., source [511869, 512470), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL66524W_000224', 'next': None}

```text
for time, my
head is so bewildered that I cannot answer for being coherent. Dearest
Lizzy, I hardly know what I would write, but I have bad news for you,
and it cannot be delayed. Imprudent as a marriage between Mr. Wickham
and our poor Lydia would be, we are now anxious to be assured it has
taken place, for there is but too much reason to fear they are not gone
to Scotland. Colonel Forster came yesterday, having left Brighton the
day before, not many hours after the express. Though Lydia’s short
letter to Mrs. F. gave them to understand that they were going to Gretna
Green, something was dropp
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## alice_01 — Alice's Adventures in Wonderland (DEV)

**Question:** What unusual item does the White Rabbit take from his waistcoat pocket?

**Category/difficulty/ambiguity:** FACTUAL_DIRECT / EASY / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** Unknown, source [1366, 1626), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL38619874W_000001', 'next': None}

```text
ds,
it occurred to her that she ought to have wondered at this, but at the
time it all seemed quite natural); but when the Rabbit actually _took a
watch out of its waistcoat-pocket_, and looked at it, and then hurried
on, Alice started to her feet, for it flas
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## alice_02 — Alice's Adventures in Wonderland (DEV)

**Question:** How tall is Alice after drinking from the first small bottle?

**Category/difficulty/ambiguity:** FACTUAL_DIRECT / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** CHAPTER I., source [9035, 9327), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL38619874W_000005', 'next': None}

```text
) she very soon finished it off.

* * * * * * *

* * * * * *

* * * * * * *

“What a curious feeling!” said Alice; “I must be shutting up like a
telescope.”

And so it was indeed: she was now only ten inches high, and her face
brightened up at the thought that she was now the right size for 
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## alice_03 — Alice's Adventures in Wonderland (DEV)

**Question:** What does the Caterpillar say the two sides of the mushroom will do?

**Category/difficulty/ambiguity:** CAUSAL / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** CHAPTER V., source [51496, 51838), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL38619874W_000022', 'next': None}

```text
ah out of its mouth and
yawned once or twice, and shook itself. Then it got down off the
mushroom, and crawled away in the grass, merely remarking as it went,
“One side will make you grow taller, and the other side will make you
grow shorter.”

“One side of _what?_ The other side of _what?_” thought Alice to
herself.

“Of the mushroom,” sai
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## alice_04 — Alice's Adventures in Wonderland (DEV)

**Question:** Who tells Alice that everyone there is mad?

**Category/difficulty/ambiguity:** QUOTE_OR_PHRASE / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** CHAPTER VI., source [68701, 69013), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL38619874W_000029', 'next': None}

```text
ion,” waving the other paw, “lives a
March Hare. Visit either you like: they’re both mad.”

“But I don’t want to go among mad people,” Alice remarked.

“Oh, you can’t help that,” said the Cat: “we’re all mad here. I’m mad.
You’re mad.”

“How do you know I’m mad?” said Alice.

“You must be,” said the Cat, “or yo
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## alice_05 — Alice's Adventures in Wonderland (DEV)

**Question:** What animals serve as balls and mallets in the Queen's croquet game?

**Category/difficulty/ambiguity:** FACTUAL_DIRECT / EASY / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** CHAPTER VIII., source [90963, 91221), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL38619874W_000038', 'next': None}

```text
hought she had never seen such a curious croquet-ground
in her life; it was all ridges and furrows; the balls were live
hedgehogs, the mallets live flamingoes, and the soldiers had to double
themselves up and to stand on their hands and feet, to make the arc
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## time_01 — The Time Machine (DEV)

**Question:** What year does the Time Traveller say he has reached when he meets the Eloi?

**Category/difficulty/ambiguity:** TEMPORAL / EASY / MULTIPLE_VALID

**Draft note:** The year is stated in two direct passages in the traveller's account.

**Passage 1:** Epilogue, source [51063, 51375), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL27039837W_000023', 'next': None}

```text
sent position. I resolved to
mount to the summit of a crest, perhaps a mile and a half away, from
which I could get a wider view of this our planet in the year Eight
Hundred and Two Thousand Seven Hundred and One, A.D. For that, I should
explain, was the date the little dials of my machine recorded.

“As I walk
```

**Passage 2:** Epilogue, source [79874, 80146), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL27039837W_000037', 'next': None}

```text
 up of
words, of letters even, absolutely unknown to you? Well, on the third
day of my visit, that was how the world of Eight Hundred and Two
Thousand Seven Hundred and One presented itself to me!

“That day, too, I made a friend—of a sort. It happened that, as I was
watc
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## time_02 — The Time Machine (DEV)

**Question:** What is the name of the Eloi woman who befriends the Time Traveller?

**Category/difficulty/ambiguity:** ENTITY_RELATION / EASY / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** Epilogue, source [81538, 81786), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL27039837W_000038', 'next': None}

```text
might have done. We passed each other flowers,
and she kissed my hands. I did the same to hers. Then I tried talk, and
found that her name was Weena, which, though I don’t know what it
meant, somehow seemed appropriate enough. That was the beginnin
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## time_03 — The Time Machine (DEV)

**Question:** Where does the Time Traveller conclude his missing machine has been hidden?

**Category/difficulty/ambiguity:** LOCATION / MEDIUM / BOUNDARY

**Draft note:** The white sphinx/pedestal reference may require preceding context at a chunk edge.

**Passage 1:** Epilogue, source [70693, 71063), grade 2, neighbor allowance True

**Adjacent covering chunks:** {'previous': 'OL27039837W_000032', 'current': 'OL27039837W_000033', 'next': None}

```text
ith the
frames. There were no handles or keyholes, but possibly the panels, if
they were doors, as I supposed, opened from within. One thing was clear
enough to my mind. It took no very great mental effort to infer that my
Time Machine was inside that pedestal. But how it got there was a
different problem.

“I saw the heads of two orange-clad people coming through the
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## time_04 — The Time Machine (DEV)

**Question:** Where does the Time Traveller infer the second human species lives?

**Category/difficulty/ambiguity:** SEMANTIC_PARAPHRASE / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** Epilogue, source [91944, 92237), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL27039837W_000042', 'next': None}

```text
Machine! And very vaguely there came a suggestion towards the solution
of the economic problem that had puzzled me.

“Here was the new view. Plainly, this second species of Man was
subterranean. There were three circumstances in particular which made
me think that its rare emergence above gro
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## time_05 — The Time Machine (DEV)

**Question:** What color is the sun in the far future at the end of the Traveller's journey?

**Category/difficulty/ambiguity:** FACTUAL_DIRECT / MEDIUM / CLEAR

**Draft note:** Check context for the far-future scene rather than earlier red sunsets.

**Passage 1:** Epilogue, source [163520, 163832), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL27039837W_000076', 'next': None}

```text
uniform poisonous-looking green of the lichenous plants, the thin air
that hurts one’s lungs: all contributed to an appalling effect. I moved
on a hundred years, and there was the same red sun—a little larger, a
little duller—the same dying sea, the same chill air, and the same
crowd of earthy crustacea creepin
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## war_01 — The War of the Worlds (DEV)

**Question:** What object does the crowd discover on Horsell Common after the first Martian landing?

**Category/difficulty/ambiguity:** FACTUAL_DIRECT / EASY / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** Unknown, source [19272, 19587), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL33027136W_000009', 'next': None}

```text
t?”

“Well?” said Henderson.

“It’s out on Horsell Common now.”

“Good Lord!” said Henderson. “Fallen meteorite! That’s good.”

“But it’s something more than a meteorite. It’s a cylinder—an
artificial cylinder, man! And there’s something inside.”

Henderson stood up with his spade in his hand.

“What’s that?” he s
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## war_02 — The War of the Worlds (DEV)

**Question:** What flag does the deputation carry toward the Martians?

**Category/difficulty/ambiguity:** FACTUAL_DIRECT / EASY / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** Unknown, source [35841, 36081), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL33027136W_000016', 'next': None}

```text
hin thirty yards of
the pit, advancing from the direction of Horsell, I noted a little
black knot of men, the foremost of whom was waving a white flag.

This was the Deputation. There had been a hasty consultation, and since
the Martians we
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## war_03 — The War of the Worlds (DEV)

**Question:** What shape are the towering machines the Martians use to walk?

**Category/difficulty/ambiguity:** FACTUAL_DIRECT / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** Unknown, source [75518, 75761), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL33027136W_000033', 'next': None}

```text
lematical object came out clear and sharp and bright.

And this Thing I saw! How can I describe it? A monstrous tripod, higher
than many houses, striding over the young pine trees, and smashing them
aside in its career; a walking engine of gli
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## war_04 — The War of the Worlds (DEV)

**Question:** What is the dominant color of Martian vegetation?

**Category/difficulty/ambiguity:** FACTUAL_DIRECT / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** Unknown, source [234382, 234647), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL33027136W_000101', 'next': None}

```text
 allude here to the curious
suggestions of the red weed.

Apparently the vegetable kingdom in Mars, instead of having green for a
dominant colour, is of a vivid blood-red tint. At any rate, the seeds
which the Martians (intentionally or accidentally) brought with t
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## war_05 — The War of the Worlds (DEV)

**Question:** What kills the Martians after their invasion?

**Category/difficulty/ambiguity:** CAUSAL / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** Unknown, source [313576, 313872), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL33027136W_000136', 'next': None}

```text
ed war-machines, some in the now rigid handling-machines,
and a dozen of them stark and silent and laid in a row, were the
Martians—_dead!_—slain by the putrefactive and disease bacteria against
which their systems were unprepared; slain as the red weed was being
slain; slain, after all man’s de
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## jekyll_01 — The Strange Case of Dr. Jekyll and Mr. Hyde (TEST)

**Question:** What is Mr. Utterson's profession?

**Category/difficulty/ambiguity:** FACTUAL_DIRECT / EASY / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** Unknown, source [279, 482), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL15933082W_000001', 'next': None}

```text
RATIVE

HENRY JEKYLL’S FULL STATEMENT OF THE CASE

STORY OF THE DOOR

Mr. Utterson the lawyer was a man of a rugged countenance that was
never lighted by a smile; cold, scanty and embarrassed in discours
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## jekyll_02 — The Strange Case of Dr. Jekyll and Mr. Hyde (TEST)

**Question:** What does Hyde do to the child in Enfield's account?

**Category/difficulty/ambiguity:** EVENT / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** Unknown, source [5376, 5684), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL15933082W_000003', 'next': None}

```text
s able down a cross
street. Well, sir, the two ran into one another naturally enough at the
corner; and then came the horrible part of the thing; for the man
trampled calmly over the child’s body and left her screaming on the
ground. It sounds nothing to hear, but it was hellish to see. It wasn’t
like a man
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## jekyll_03 — The Strange Case of Dr. Jekyll and Mr. Hyde (TEST)

**Question:** Who is named to inherit Jekyll's possessions in his will?

**Category/difficulty/ambiguity:** ENTITY_RELATION / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** Unknown, source [13921, 14235), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL15933082W_000006', 'next': None}

```text
ot only that, in case of the decease of Henry Jekyll, M.D., D.C.L.,
L.L.D., F.R.S., etc., all his possessions were to pass into the hands
of his “friend and benefactor Edward Hyde,” but that in case of Dr.
Jekyll’s “disappearance or unexplained absence for any period exceeding
three calendar months,” the said Edw
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## jekyll_04 — The Strange Case of Dr. Jekyll and Mr. Hyde (TEST)

**Question:** Who is the gentleman murdered by Hyde?

**Category/difficulty/ambiguity:** ENTITY_RELATION / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** Unknown, source [36927, 37243), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL15933082W_000017', 'next': None}

```text
reakfast and drove to the police station, whither the body had
been carried. As soon as he came into the cell, he nodded.

“Yes,” said he, “I recognise him. I am sorry to say that this is Sir
Danvers Carew.”

“Good God, sir,” exclaimed the officer, “is it possible?” And the next
moment his eye lighted up with profe
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## jekyll_05 — The Strange Case of Dr. Jekyll and Mr. Hyde (TEST)

**Question:** What does Jekyll drink to return from Hyde to his own form?

**Category/difficulty/ambiguity:** CAUSAL / HARD / CLEAR

**Draft note:** Review that the expanded excerpt explicitly contains the drug or draught.

**Passage 1:** Unknown, source [110295, 110770), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': 'OL15933082W_000050', 'current': 'OL15933082W_000051', 'next': None}

```text
ve
experiment had yet to be attempted; it yet remained to be seen if I had
lost my identity beyond redemption and must flee before daylight from a
house that was no longer mine; and hurrying back to my cabinet, I once
more prepared and drank the cup, once more suffered the pangs of
dissolution, and came to myself once more with the character, the
stature and the face of Henry Jekyll.

That night I had come to the fatal cross-roads. Had I approached my
discovery in a more
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## dorian_01 — The Picture of Dorian Gray (TEST)

**Question:** Who painted Dorian Gray's portrait?

**Category/difficulty/ambiguity:** ENTITY_RELATION / EASY / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** CHAPTER VII., source [171491, 171717), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL44512357W_000076', 'next': None}

```text
disused attic at Selby Royal. As
he was turning the handle of the door, his eye fell upon the portrait
Basil Hallward had painted of him. He started back as if in surprise.
Then he went on into his own room, looking somewhat p
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## dorian_02 — The Picture of Dorian Gray (TEST)

**Question:** What is Sibyl Vane's profession when Dorian meets her?

**Category/difficulty/ambiguity:** FACTUAL_DIRECT / EASY / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** CHAPTER X., source [239409, 239654), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL44512357W_000106', 'next': None}

```text
rning at the Bell
Tavern, Hoxton Road, by Mr. Danby, the District Coroner, on the body of
Sibyl Vane, a young actress recently engaged at the Royal Theatre,
Holborn. A verdict of death by misadventure was returned. Considerable
sympathy was expr
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## dorian_03 — The Picture of Dorian Gray (TEST)

**Question:** What change does Dorian notice in his portrait after his cruelty to Sibyl?

**Category/difficulty/ambiguity:** EVENT / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** CHAPTER VIII., source [179561, 179920), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL44512357W_000079', 'next': 'OL44512357W_000080'}

```text
he
table. “I shut the window?”

Dorian shook his head. “I am not cold,” he murmured.

Was it all true? Had the portrait really changed? Or had it been simply
his own imagination that had made him see a look of evil where there
had been a look of joy? Surely a painted canvas could not alter? The
thing was absurd. It would serve as a tale to tell Basil some d
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## dorian_04 — The Picture of Dorian Gray (TEST)

**Question:** What weapon did Dorian use against Basil Hallward?

**Category/difficulty/ambiguity:** FACTUAL_DIRECT / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** CHAPTER XX., source [426981, 427222), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL44512357W_000187', 'next': None}

```text
 like conscience to him. Yes, it
had been conscience. He would destroy it.

He looked round and saw the knife that had stabbed Basil Hallward. He
had cleaned it many times, till there was no stain left upon it. It was
bright, and glistened. 
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## dorian_05 — The Picture of Dorian Gray (TEST)

**Question:** What does Dorian do to the portrait near the end of the novel?

**Category/difficulty/ambiguity:** EVENT / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** CHAPTER XX., source [427296, 427629), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL44512357W_000187', 'next': None}

```text
 that that meant. It would kill the past,
and when that was dead, he would be free. It would kill this monstrous
soul-life, and without its hideous warnings, he would be at peace. He
seized the thing, and stabbed the picture with it.

There was a cry heard, and a crash. The cry was so horrible in its
agony that the frightened serva
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## moby_01 — Moby-Dick (TEST)

**Question:** Who is the Pequod's chief mate?

**Category/difficulty/ambiguity:** ENTITY_RELATION / EASY / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** CHAPTER 25. Postscript., source [256660, 256881), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL27471326W_000118', 'next': None}

```text
en supply your kings and
queens with coronation stuff!

CHAPTER 26. Knights and Squires.

The chief mate of the Pequod was Starbuck, a native of Nantucket, and a
Quaker by descent. He was a long, earnest man, and though b
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## moby_02 — Moby-Dick (TEST)

**Question:** What material was used to make Captain Ahab's ivory leg?

**Category/difficulty/ambiguity:** FACTUAL_DIRECT / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** CHAPTER 28. Ahab., source [278355, 278677), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL27471326W_000128', 'next': None}

```text
le of this overbearing grimness was owing to the
barbaric white leg upon which he partly stood. It had previously come
to me that this ivory leg had at sea been fashioned from the polished
bone of the sperm whale’s jaw. “Aye, he was dismasted off Japan,” said
the old Gay-Head Indian once; “but like his dismasted craft, h
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## moby_03 — Moby-Dick (TEST)

**Question:** Which object belonging to Queequeg is remade as a life buoy?

**Category/difficulty/ambiguity:** FACTUAL_DIRECT / MEDIUM / BOUNDARY

**Draft note:** The coffin and life-buoy may straddle a chunk boundary; verify surrounding source.

**Passage 1:** CHAPTER 126. The Life-Buoy., source [1112962, 1113346), grade 2, neighbor allowance True

**Adjacent covering chunks:** {'previous': None, 'current': 'OL27471326W_000505', 'next': None}

```text
nnected with its final end, whatever that might prove to be;
therefore, they were going to leave the ship’s stern unprovided with a
buoy, when by certain strange signs and inuendoes Queequeg hinted a
hint concerning his coffin.

“A life-buoy of a coffin!” cried Starbuck, starting.

“Rather queer, that, I should say,” said Stubb.

“It will make a good enough one,” said Flask, “the c
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## moby_04 — Moby-Dick (TEST)

**Question:** Where does Ishmael find Queequeg after returning from the chapel?

**Category/difficulty/ambiguity:** LOCATION / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** CHAPTER 9. The Sermon., source [126987, 127237), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL27471326W_000058', 'next': None}

```text
ed,
and he was left alone in the place.

CHAPTER 10. A Bosom Friend.

Returning to the Spouter-Inn from the Chapel, I found Queequeg there
quite alone; he having left the Chapel before the benediction some
time. He was sitting on a bench before the f
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## moby_05 — Moby-Dick (TEST)

**Question:** Who is captain of the Pequod?

**Category/difficulty/ambiguity:** ENTITY_RELATION / EASY / CLEAR

**Draft note:** The following lines identify this ship as the Pequod; a reviewer should identify multiple direct captain/ship passages.

**Passage 1:** CHAPTER 16. The Ship., source [173644, 174114), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL27471326W_000080', 'next': None}

```text
”

“Want to see what whaling is, eh? Have ye clapped eye on Captain Ahab?”

“Who is Captain Ahab, sir?”

“Aye, aye, I thought so. Captain Ahab is the Captain of this ship.”

“I am mistaken then. I thought I was speaking to the Captain himself.”

“Thou art speaking to Captain Peleg—that’s who ye are speaking to,
young man. It belongs to me and Captain Bildad to see the Pequod fitted
out for the voyage, and supplied with all her needs, including crew. We
are part owne
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## meta_01 — The Metamorphosis (TEST)

**Question:** What has Gregor Samsa become when he wakes from troubled dreams?

**Category/difficulty/ambiguity:** FACTUAL_DIRECT / EASY / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** Unknown, source [0, 213), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL42479046W_000001', 'next': None}

```text
I

One morning, when Gregor Samsa woke from troubled dreams, he found
himself transformed in his bed into a horrible vermin. He lay on his
armour-like back, and if he lifted his head a little he could see his
brow
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## meta_02 — The Metamorphosis (TEST)

**Question:** What is Gregor Samsa's job before his transformation?

**Category/difficulty/ambiguity:** FACTUAL_DIRECT / EASY / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** Unknown, source [606, 827), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL42479046W_000001', 'next': None}

```text
ween
its four familiar walls. A collection of textile samples lay spread out
on the table—Samsa was a travelling salesman—and above it there hung a
picture that he had recently cut out of an illustrated magazine and
house
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## meta_03 — The Metamorphosis (TEST)

**Question:** What thrown object lodges in Gregor's back?

**Category/difficulty/ambiguity:** EVENT / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** Unknown, source [77084, 77476), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL42479046W_000037', 'next': None}

```text
hese little, red apples rolled about on the
floor, knocking into each other as if they had electric motors. An
apple thrown without much force glanced against Gregor’s back and slid
off without doing any harm. Another one however, immediately following
it, hit squarely and lodged in his back; Gregor wanted to drag himself
away, as if he could remove the surprising, the incredible pain by
c
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## meta_04 — The Metamorphosis (TEST)

**Question:** Which instrument does Gregor's sister Grete play?

**Category/difficulty/ambiguity:** FACTUAL_DIRECT / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** Unknown, source [51847, 52130), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL42479046W_000025', 'next': None}

```text
ugh there was
no longer much warm affection given in return. Gregor only remained
close to his sister now. Unlike him, she was very fond of music and a
gifted and expressive violinist, it was his secret plan to send her to
the conservatory next year even though it would cause great 
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---

## meta_05 — The Metamorphosis (TEST)

**Question:** What do the lodgers announce after seeing Gregor?

**Category/difficulty/ambiguity:** EVENT / MEDIUM / CLEAR

**Draft note:** Source-backed draft; a human should check all alternate passages.

**Passage 1:** Unknown, source [101120, 101474), grade 2, neighbor allowance False

**Adjacent covering chunks:** {'previous': None, 'current': 'OL42479046W_000048', 'next': None}

```text
d and glancing at Gregor’s mother and
sister to gain their attention too, “that with regard to the repugnant
conditions that prevail in this flat and with this family”—here he
looked briefly but decisively at the floor—“I give immediate notice on
my room. For the days that I have been living here I will, of course,
pay nothing at all, on the contrary I
```

- [ ] Question premise and answer verified in the source
- [ ] All reasonable answer-bearing source spans added
- [ ] Span grade and boundaries verified
- [ ] Neighbor/overlap treatment verified
- Reviewer and date:

---
