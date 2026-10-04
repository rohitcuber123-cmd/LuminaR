# G3 GooAQ DEV dense retrieval

Experimental/descriptive: DEV labels remain DRAFT. TEST was not evaluated.

| Metric | Baseline A | G3 |
|---|---:|---:|
| MRR | 0.1653 | 0.1360 |
| Hit@1 | 0.0690 | 0.0345 |
| Hit@3 | 0.1724 | 0.1724 |
| Hit@5 | 0.2414 | 0.2069 |
| Hit@10 | 0.3448 | 0.3793 |
| Hit@20 | 0.4828 | 0.4483 |
| Hit@50 | 0.6552 | 0.7241 |
| Recall@5 | 0.2414 | 0.2069 |
| Recall@10 | 0.3448 | 0.3793 |
| Recall@20 | 0.4655 | 0.4483 |
| Recall@50 | 0.6207 | 0.6897 |
| No gold in Top50 | 10 | 8 |

Movement: {'IMPROVED': 8, 'REGRESSED': 7, 'UNCHANGED': 14}; recovered Top50: 2; lost Top50: 0.

## v8_06 (OL85892W)

Question: Why doesn't Jonathan Harker leave the castle?

A gold span ranks: [None]; G3 gold span ranks: [47].

Accepted span: cked and bolted. In no place save from the windows in the castle walls is there an available exit.  The castle is a veritable prison, and I am a prisoner!  CHAPTER III  JONATHAN HARKER’S JOURNAL--_continued_  When I found that I was a prisoner 

A nearest:

- #1 `OL85892W__tokens_220__b2fcccaa27b65e8a`: Harker and Harker; Quincey and Art are all out following up the clues as to the earth-boxes. I shall finish my round of work and we shall meet to-night.  _Mina Harker’s Journal._  
- #2 `OL85892W__tokens_220__84ba230d9042d7cc`: He have always the strength in his hand of twenty men; even we four who gave our strength to Miss Lucy it also is all to him. Besides, he can summon his wolf and I know not what. S
- #3 `OL85892W__tokens_220__bd0e1f87626f1267`: It was terribly weak, and looked quite emaciated. It too, when partially restored, had the common story to tell of being lured away by the “bloofer lady.”  CHAPTER XIV  MINA HARKER

G3 nearest:

- #1 `OL85892W__tokens_220__b2fcccaa27b65e8a`: Harker and Harker; Quincey and Art are all out following up the clues as to the earth-boxes. I shall finish my round of work and we shall meet to-night.  _Mina Harker’s Journal._  
- #2 `OL85892W__tokens_220__6eb69d39e29aba6c`: Harker has got the letters between the consignee of the boxes at Whitby and the carriers in London who took charge of them. He is now reading his wife’s typescript of my diary. I w
- #3 `OL85892W__tokens_220__61178db585acbaa6`: Harker everything which had passed; and although she grew snowy white at times when danger had seemed to threaten her husband, and red at others when his devotion to her was manife

## pp_05 (OL66524W)

Question: Which man does Lydia leave Brighton with, alarming her family?

A gold span ranks: [None]; G3 gold span ranks: [49].

Accepted span: for time, my head is so bewildered that I cannot answer for being coherent. Dearest Lizzy, I hardly know what I would write, but I have bad news for you, and it cannot be delayed. Imprudent as a marriage between Mr. Wickham and our poor Lydia would be, we are now anxious to be assured it has taken place, for there is but too much reason to fear they are not gone to Scotland. Colonel Forster came yesterday, having left Brighton the day before, not

A nearest:

- #1 `OL66524W__tokens_220__ed4650337b0907aa`: Lydia’s going to Brighton was all that consoled her for the melancholy conviction of her husband’s never intending to go there himself.  But they were entirely ignorant of what had
- #2 `OL66524W__tokens_220__f915ac65851d429c`: She got up and ran out of the room; and returned no more, till she heard them passing through the hall to the dining-parlour. She then joined them soon enough to see Lydia, with an
- #3 `OL66524W__tokens_220__26ddfe20d4330d82`: Gardiner, after general assurances of his affection for her and all her family, told her that he meant to be in London the very next day, and would assist Mr. Bennet in every endea

G3 nearest:

- #1 `OL66524W__tokens_220__ed4650337b0907aa`: Lydia’s going to Brighton was all that consoled her for the melancholy conviction of her husband’s never intending to go there himself.  But they were entirely ignorant of what had
- #2 `OL66524W__tokens_220__f915ac65851d429c`: She got up and ran out of the room; and returned no more, till she heard them passing through the hall to the dining-parlour. She then joined them soon enough to see Lydia, with an
- #3 `OL66524W__tokens_220__afe3a410b9e8065c`: Lydia does not leave me because she is married; but only because her husband’s regiment happens to be so far off. If that had been nearer, she would not have gone so soon.”  But th
