# G2 Natural Questions DEV dense retrieval

Experimental/descriptive: DEV labels remain DRAFT. TEST was not evaluated.

| Metric | Baseline A | G2 |
|---|---:|---:|
| MRR | 0.1653 | 0.1544 |
| Hit@1 | 0.0690 | 0.0690 |
| Hit@3 | 0.1724 | 0.1724 |
| Hit@5 | 0.2414 | 0.2414 |
| Hit@10 | 0.3448 | 0.3448 |
| Hit@20 | 0.4828 | 0.4138 |
| Hit@50 | 0.6552 | 0.6207 |
| Recall@5 | 0.2414 | 0.2414 |
| Recall@10 | 0.3448 | 0.3448 |
| Recall@20 | 0.4655 | 0.3966 |
| Recall@50 | 0.6207 | 0.6034 |
| No gold in Top50 | 10 | 11 |

Movement: {'IMPROVED': 9, 'REGRESSED': 11, 'UNCHANGED': 9}; recovered Top50: 1; lost Top50: 2.

## v8_06 (OL85892W)

Question: Why doesn't Jonathan Harker leave the castle?

A gold span ranks: [None]; G2 gold span ranks: [32].

Accepted span: cked and bolted. In no place save from the windows in the castle walls is there an available exit.  The castle is a veritable prison, and I am a prisoner!  CHAPTER III  JONATHAN HARKER’S JOURNAL--_continued_  When I found that I was a prisoner 

A nearest:

- #1 `OL85892W__tokens_220__b2fcccaa27b65e8a`: Harker and Harker; Quincey and Art are all out following up the clues as to the earth-boxes. I shall finish my round of work and we shall meet to-night.  _Mina Harker’s Journal._  
- #2 `OL85892W__tokens_220__84ba230d9042d7cc`: He have always the strength in his hand of twenty men; even we four who gave our strength to Miss Lucy it also is all to him. Besides, he can summon his wolf and I know not what. S
- #3 `OL85892W__tokens_220__bd0e1f87626f1267`: It was terribly weak, and looked quite emaciated. It too, when partially restored, had the common story to tell of being lured away by the “bloofer lady.”  CHAPTER XIV  MINA HARKER

G2 nearest:

- #1 `OL85892W__tokens_220__b2fcccaa27b65e8a`: Harker and Harker; Quincey and Art are all out following up the clues as to the earth-boxes. I shall finish my round of work and we shall meet to-night.  _Mina Harker’s Journal._  
- #2 `OL85892W__tokens_220__84ba230d9042d7cc`: He have always the strength in his hand of twenty men; even we four who gave our strength to Miss Lucy it also is all to him. Besides, he can summon his wolf and I know not what. S
- #3 `OL85892W__tokens_220__34ab94d264decd0c`: Harker realised the danger herself, it was much pain as well as much danger averted. Under the circumstances we agreed, by a questioning look and answer, with finger on lip, to pre

## pp_02 (OL66524W)

Question: How does Darcy describe Elizabeth when declining to dance with her?

A gold span ranks: [17]; G2 gold span ranks: [None].

Accepted span:  and turning round, he looked for a moment at Elizabeth, till, catching her eye, he withdrew his own, and coldly said, “She is tolerable: but not handsome enough to tempt _me_; and I am in no humour at present to give consequence to young ladies

A nearest:

- #1 `OL66524W__tokens_220__c7c2902b1742e25c`: He paused in hopes of an answer: but his companion was not disposed to make any; and Elizabeth at that instant moving towards them, he was struck with the notion of doing a very ga
- #2 `OL66524W__tokens_220__b30be6ce14886144`: Elizabeth made no answer, and took her place in the set, amazed at the dignity to which she was arrived in being allowed to stand opposite to Mr. Darcy, and reading in her neighbou
- #3 `OL66524W__tokens_220__3961e6ba460a571f`: Darcy, who, though extremely surprised, was not unwilling to receive it, when she instantly drew back, and said with some discomposure to Sir William,--  “Indeed, sir, I have not t

G2 nearest:

- #1 `OL66524W__tokens_220__e27568b05b935f28`: Elizabeth, easy and unaffected, had been listened to with much more pleasure, though not playing half so well; and Mary, at the end of a long concerto, was glad to purchase praise 
- #2 `OL66524W__tokens_220__3961e6ba460a571f`: Darcy, who, though extremely surprised, was not unwilling to receive it, when she instantly drew back, and said with some discomposure to Sir William,--  “Indeed, sir, I have not t
- #3 `OL66524W__tokens_220__c7c2902b1742e25c`: He paused in hopes of an answer: but his companion was not disposed to make any; and Elizabeth at that instant moving towards them, he was struck with the notion of doing a very ga

## time_01 (OL27039837W)

Question: What year does the Time Traveller say he has reached when he meets the Eloi?

A gold span ranks: [44, None]; G2 gold span ranks: [None, None].

Accepted span: sent position. I resolved to mount to the summit of a crest, perhaps a mile and a half away, from which I could get a wider view of this our planet in the year Eight Hundred and Two Thousand Seven Hundred and One, A.D. For that, I should explain, was the date the little dials of my machine recorded.  “As I walk

A nearest:

- #1 `OL27039837W__tokens_220__0b77b629a260b8a1`: At the risk of disappointing Richardson I stayed on, waiting for the Time Traveller; waiting for the second, perhaps still stranger story, and the specimens and photographs he woul
- #2 `OL27039837W__tokens_220__8318352404474dd2`: But the Time Traveller had more than a touch of whim among his elements, and we distrusted him. Things that would have made the fame of a less clever man seemed tricks in his hands
- #3 `OL27039837W__tokens_220__b924fd20b5d9a134`: You read, I will suppose, attentively enough; but you cannot see the speaker’s white, sincere face in the bright circle of the little lamp, nor hear the intonation of his voice. Yo

G2 nearest:

- #1 `OL27039837W__tokens_220__8318352404474dd2`: But the Time Traveller had more than a touch of whim among his elements, and we distrusted him. Things that would have made the fame of a less clever man seemed tricks in his hands
- #2 `OL27039837W__tokens_220__0b77b629a260b8a1`: At the risk of disappointing Richardson I stayed on, waiting for the Time Traveller; waiting for the second, perhaps still stranger story, and the specimens and photographs he woul
- #3 `OL27039837W__tokens_220__2a0ec14fa8e64c08`: “I’m frightfully busy,” said he, “with that thing in there.”  “But is it not some hoax?” I said. “Do you really travel through time?”  “Really and truly I do.” And he looked frankl
