# G1 MS MARCO DEV dense retrieval

Experimental/descriptive: DEV labels remain DRAFT. TEST was not evaluated.

| Metric | Baseline A | G1 |
|---|---:|---:|
| MRR | 0.1653 | 0.1096 |
| Hit@1 | 0.0690 | 0.0345 |
| Hit@3 | 0.1724 | 0.1034 |
| Hit@5 | 0.2414 | 0.1724 |
| Hit@10 | 0.3448 | 0.2414 |
| Hit@20 | 0.4828 | 0.3793 |
| Hit@50 | 0.6552 | 0.5172 |
| Recall@5 | 0.2414 | 0.1724 |
| Recall@10 | 0.3448 | 0.2414 |
| Recall@20 | 0.4655 | 0.3793 |
| Recall@50 | 0.6207 | 0.5000 |
| No gold in Top50 | 10 | 14 |

Movement: {'IMPROVED': 5, 'REGRESSED': 13, 'UNCHANGED': 11}; recovered Top50: 0; lost Top50: 4.

## v8_08 (OL85892W)

Question: What ship transported Dracula to England?

A gold span ranks: [46, None]; G1 gold span ranks: [None, None].

Accepted span: rm last night is almost more startling than the thing itself. It turns out that the schooner is a Russian from Varna, and is called the _Demeter_. She is almost entirely in ballast of silver sand, with only a small amount of 

A nearest:

- #1 `OL85892W__tokens_220__6ef8ddca53731104`: Quincey Morris, Jonathan Harker, Mina Harker.  Dr. Van Helsing described what steps were taken during the day to discover on what boat and whither bound Count Dracula made his esca
- #2 `OL85892W__tokens_220__c9d2fb7c878635ee`: I knew that if anything were to take us to Castle Dracula we should go by Galatz, or at any rate through Bucharest, so I learned the times very carefully. Unhappily there are not m
- #3 `OL85892W__tokens_220__84a8e03f7e32bbca`: They had, mind ye, taken the box on the deck ready to fling in, and as it was marked Galatz _via_ Varna, I thocht I’d let it lie till we discharged in the port an’ get rid o’t alth

G1 nearest:

- #1 `OL85892W__tokens_220__6ef8ddca53731104`: Quincey Morris, Jonathan Harker, Mina Harker.  Dr. Van Helsing described what steps were taken during the day to discover on what boat and whither bound Count Dracula made his esca
- #2 `OL85892W__tokens_220__932a9d97188bcf75`: Fifty years ago a series of great fires took place, which made terrible havoc on five separate occasions. At the very beginning of the seventeenth century it underwent a siege of t
- #3 `OL85892W__tokens_220__c9d2fb7c878635ee`: I knew that if anything were to take us to Castle Dracula we should go by Galatz, or at any rate through Bucharest, so I learned the times very carefully. Unhappily there are not m

## v8_10 (OL45326637W)

Question: What happens when Victor first sees the creature?

A gold span ranks: [23, 13]; G1 gold span ranks: [None, None].

Accepted span: the panes, and my candle was nearly burnt out, when, by the glimmer of the half-extinguished light, I saw the dull yellow eye of the creature open; it breathed hard, and a convulsive motion agitated its limbs.  [Illustration: "_By the glimmer of 

A nearest:

- #1 `OL45326637W__tokens_220__6664e2d3e693a3ab`: The monster continued to utter wild and incoherent self-reproaches. At length I gathered resolution to address him in a pause of the tempest of his passion: "Your repentance," I sa
- #2 `OL45326637W__tokens_220__a335185d00485d68`: Sometimes he commanded his countenance and tones, and related the most horrible incidents with a tranquil voice, suppressing every mark of agitation; then, like a volcano bursting 
- #3 `OL45326637W__tokens_220__432d011638ca1058`: This picture is gone, and was doubtless the temptation which urged the murderer to the deed. We have no trace of him at present, although our exertions to discover him are unremitt

G1 nearest:

- #1 `OL45326637W__tokens_220__0d11f652f36bfe7e`: "William is dead!--that sweet child, whose smiles delighted and warmed my heart, who was so gentle, yet so gay! Victor, he is murdered!  "I will not attempt to console you; but wil
- #2 `OL45326637W__tokens_220__a335185d00485d68`: Sometimes he commanded his countenance and tones, and related the most horrible incidents with a tranquil voice, suppressing every mark of agitation; then, like a volcano bursting 
- #3 `OL45326637W__tokens_220__ebad03a94a77f07f`: He manifested the greatest eagerness to be upon deck, to watch for the sledge which had before appeared; but I have persuaded him to remain in the cabin, for he is far too weak to 

## alice_04 (OL38619874W)

Question: Who tells Alice that everyone there is mad?

A gold span ranks: [2]; G1 gold span ranks: [None].

Accepted span: ion,” waving the other paw, “lives a March Hare. Visit either you like: they’re both mad.”  “But I don’t want to go among mad people,” Alice remarked.  “Oh, you can’t help that,” said the Cat: “we’re all mad here. I’m mad. You’re mad.”  “How do you know I’m mad?” said Alice.  “You must be,” said the Cat, “or yo

A nearest:

- #1 `OL38619874W__tokens_220__dccc539e2d87241d`: Alice didn’t think that proved it at all; however, she went on “And how do you know that you’re mad?”  “To begin with,” said the Cat, “a dog’s not mad. You grant that?”  “I suppose
- #2 `OL38619874W__tokens_220__8565fab0079a0ec0`: “In _that_ direction,” the Cat said, waving its right paw round, “lives a Hatter: and in _that_ direction,” waving the other paw, “lives a March Hare. Visit either you like: they’r
- #3 `OL38619874W__tokens_220__31d052f7056ca4ef`: He had been looking at Alice for some time with great curiosity, and this was his first speech.  “You should learn not to make personal remarks,” Alice said with some severity; “it

G1 nearest:

- #1 `OL38619874W__tokens_220__00683a65e1fd2cfc`: the Queen shouted at the top of her voice. Nobody moved.  “Who cares for you?” said Alice, (she had grown to her full size by this time.) “You’re nothing but a pack of cards!”  At 
- #2 `OL38619874W__tokens_220__31d052f7056ca4ef`: He had been looking at Alice for some time with great curiosity, and this was his first speech.  “You should learn not to make personal remarks,” Alice said with some severity; “it
- #3 `OL38619874W__tokens_220__b65f1560c89ba137`: “You’re thinking about something, my dear, and that makes you forget to talk. I can’t tell you just now what the moral of that is, but I shall remember it in a bit.”  “Perhaps it h

## time_02 (OL27039837W)

Question: What is the name of the Eloi woman who befriends the Time Traveller?

A gold span ranks: [50]; G1 gold span ranks: [None].

Accepted span: might have done. We passed each other flowers, and she kissed my hands. I did the same to hers. Then I tried talk, and found that her name was Weena, which, though I don’t know what it meant, somehow seemed appropriate enough. That was the beginnin

A nearest:

- #1 `OL27039837W__tokens_220__8318352404474dd2`: But the Time Traveller had more than a touch of whim among his elements, and we distrusted him. Things that would have made the fame of a less clever man seemed tricks in his hands
- #2 `OL27039837W__tokens_220__b924fd20b5d9a134`: You read, I will suppose, attentively enough; but you cannot see the speaker’s white, sincere face in the bright circle of the little lamp, nor hear the intonation of his voice. Yo
- #3 `OL27039837W__tokens_220__0b77b629a260b8a1`: At the risk of disappointing Richardson I stayed on, waiting for the Time Traveller; waiting for the second, perhaps still stranger story, and the specimens and photographs he woul

G1 nearest:

- #1 `OL27039837W__tokens_220__122791a833523bc8`: The Time Machine had gone. Save for a subsiding stir of dust, the further end of the laboratory was empty. A pane of the skylight had, apparently, just been blown in.  I felt an un
- #2 `OL27039837W__tokens_220__40f55b29e7af8aca`: Thanks. And the salt.”  “One word,” said I. “Have you been time travelling?”  “Yes,” said the Time Traveller, with his mouth full, nodding his head.  “I’d give a shilling a line fo
- #3 `OL27039837W__tokens_220__12dc2d1ee74ca72f`: I looked round for the Time Traveller, and—“It’s half-past seven now,” said the Medical Man. “I suppose we’d better have dinner?”  “Where’s——?” said I, naming our host.  “You’ve ju
