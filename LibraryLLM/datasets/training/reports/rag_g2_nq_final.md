# G2_NATURAL_QUESTIONS — consolidated controlled pilot

**Decision: C. NATURAL QUESTIONS G2 REGRESSES LUMINAR RETRIEVAL.**

The valid comparison is A → independently initialized NQ G2. G1 is frozen historical context. DEV labels remain DRAFT, so all downstream conclusions are experimental/descriptive. Stop after G2; no next dataset, mixture, or production promotion.

## Source, inventory, and selection

Source: [`sentence-transformers/natural-questions`](https://huggingface.co/datasets/sentence-transformers/natural-questions); configuration `pair`; revision `f9e894e1081e206e577b4eaa9ee6de2b06ae6f17`; split TRAIN; actual schema `{'query': 'string', 'answer': 'string'}`. Automatic download succeeded without authentication. The initial sandbox request failed with HTTPX ConnectError WinError 10061; the required request outside the sandbox succeeded. Windows symlinks were unavailable, so HF used file copies in the controlled cache. No alternate dataset was used.

Full-source inventory: `{'total_rows': 100231, 'empty_queries': 0, 'empty_answers': 0, 'exact_duplicate_pairs': 0, 'duplicate_queries': 0, 'duplicate_answer_passages': 25016, 'query_equals_answer': 0, 'token_lengths': {'query': {'min': 9, 'median': 11, 'p90': 14, 'p95': 16, 'p99': 19, 'max': 32, 'over_256': 0}, 'answer': {'min': 4, 'median': 124, 'p90': 230, 'p95': 274, 'p99': 385, 'max': 3144, 'over_256': 6583}}, 'multi_positive_queries': 0}`.

Selected final pairs: 50,000 = 45,000 TRAIN + 5,000 generic validation; seed 42; normalized-query overlap 0. Initial selection used shuffled normalized-query groups and one seeded positive per group. Full-source alternate positives were preserved for negative exclusion. Technical selection deviation: Unmineable initial TRAIN queries replaced with seed-42 shuffled NQ reserve queries; margins/window unchanged; validation unchanged; final 45k/5k. Replacements: 1853; full mining attempts: 50000; queries without a safe candidate: 2042. This conditions the TRAIN sample on safe-negative availability; it is not an unconditional uniform 45k NQ sample.

Token counts include tokenizer special tokens and are measured without truncation. Source query/answer distributions and counts over 256 are in the inventory above; the model window stayed at 256. Long passages are truncated at encode/train time.

| Saved data | Rows | SHA-256 |
|---|---:|---|
| pairs_train | 45000 | `2bae681f6e3a9f31cec37cdcd7ed971b1d150f17df98754b7f89d7c6a2be1639` |
| pairs_validation | 5000 | `8830c0c0201b5931e858e3a6c89bdf4cd316a6f214df9d65e50a1855b2b9f07b` |
| source_pairs | 100231 | `b2444063b4616334b6b3ea629061d747d59e9fa4ffdaec15f9ca52677106b561` |
| train | 45000 | `e061ea7afccf73743f1617aa054ed97988261542f5535e38a487558c97a591b0` |
| validation | 5000 | `8830c0c0201b5931e858e3a6c89bdf4cd316a6f214df9d65e50a1855b2b9f07b` |
| pairs_train_initial | 45000 | `6b3cdffd2ac3c66e32a1d187ec4b7c6f6c3478be415129d3225a33824a460658` |

## Negative mining and engineering audit

Mining model: untouched `sentence-transformers/all-MiniLM-L6-v2` at snapshot `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. Installed `sentence_transformers.util.mine_hard_negatives` was used with the full normalized-deduplicated answer corpus (75102 passages), FAISS, batch 32, five internal candidates, and one retained negative per final training query. No G1 or reranker mining.

Calibration attempted 500 queries; 479 had safe negatives. Raw score distributions were inspected before selecting the cap. Settings: `{'max_score': 0.7666103839874268, 'relative_margin': 0.1, 'absolute_margin': 0.05}`; eligible candidate rank slice 10–50. The cap is bounded by the measured positive upper quartile and .80; the .10 relative/.05 absolute margins conservatively require score separation. Settings stayed fixed for full mining. Saved `negative_rank` is the raw 1-based full-corpus rank, which differs from the installed miner's rank after positive/score masking.

Calibration distributions: `{'positive_score': {'min': 0.3961048126220703, 'p10': 0.5669594168663025, 'median': 0.7013835906982422, 'p90': 0.8194849133491516, 'p95': 0.8440094590187072, 'max': 0.9040256142616272, 'mean': 0.6972529631815773, 'count': 479}, 'negative_score': {'min': 0.2825446128845215, 'p10': 0.359961199760437, 'median': 0.4377790093421936, 'p90': 0.5411502957344055, 'p95': 0.5697214126586914, 'max': 0.6244127154350281, 'mean': 0.44478511088576345, 'count': 479}, 'margin': {'min': 0.060994625091552734, 'p10': 0.11456962823867797, 'median': 0.24394941329956055, 'p90': 0.39195788502693174, 'p95': 0.43287172317504874, 'max': 0.5253833830356598, 'mean': 0.2524678522958138, 'count': 479}, 'negative_rank': {'min': 12.0, 'p10': 14.0, 'median': 20.0, 'p90': 33.0, 'p95': 37.0, 'max': 51.0, 'mean': 21.661795407098122, 'count': 479}}`.
Full mining distributions: `{'positive_score': {'min': 0.33129483461380005, 'p10': 0.5624114096164703, 'median': 0.706401914358139, 'p90': 0.8186770439147949, 'p95': 0.8435563057661056, 'max': 0.9483343362808228, 'mean': 0.6974152351306544, 'count': 45000}, 'negative_score': {'min': 0.20920825004577637, 'p10': 0.3572266459465027, 'median': 0.4372420907020569, 'p90': 0.5450350403785705, 'p95': 0.5735918402671814, 'max': 0.7313360571861267, 'mean': 0.4447317157665888, 'count': 45000}, 'margin': {'min': 0.05382668972015381, 'p10': 0.11481022238731384, 'median': 0.24720151722431183, 'p90': 0.3974315732717514, 'p95': 0.4333195507526397, 'max': 0.6127687692642212, 'mean': 0.2526835193640656, 'count': 45000}, 'negative_rank': {'min': 12.0, 'p10': 14.0, 'median': 20.0, 'p90': 31.0, 'p95': 36.0, 'max': 51.0, 'mean': 21.328955555555556, 'count': 45000}}`.

Safeguards: all full-source alternate positives by normalized query/text excluded; 10% relative + .05 absolute margin; data-informed max_score; ranks 10–50 of eligible candidates; no cross-encoder. Known-positive candidates rejected by postfilter: 0. Every saved negative is checked against all full-source positives for its normalized query, including normalized-text duplicates.

Deterministic seed-42 source-text audit: 25 negatives; 23 OBVIOUSLY_NOT_ANSWER, 0 POSSIBLE_FALSE_NEGATIVE, 2 AMBIGUOUS. The two ambiguous cases concern general Bible authorship and generic climate factors; neither clearly supplies the requested specific answer. This is model engineering sanity inspection, not human training-label review, and cannot estimate a corpus-wide false-negative rate.

| Sample | Query | Classification | Reason |
|---|---|---|---|
| 1 | which word best describes the process of writing technical documents | OBVIOUSLY_NOT_ANSWER | Medical chart documentation does not describe technical-document writing. |
| 2 | is game of thrones based on the book | OBVIOUSLY_NOT_ANSWER | Discusses future fantasy novel chapters without establishing the television adaptation. |
| 3 | who won the supercar drivers championship in 2002 | OBVIOUSLY_NOT_ANSWER | IndyCar drivers and championships differ from the requested 2002 V8 Supercar championship. |
| 4 | why was the battle of the coral sea significant for the allies (4 points) | OBVIOUSLY_NOT_ANSWER | WWI tanks do not explain the WWII Coral Sea battle. |
| 5 | when will game of throne season 8 be released | OBVIOUSLY_NOT_ANSWER | Pilot production dates do not answer the season-eight release date. |
| 6 | who is mr. potter in it's a wonderful life | OBVIOUSLY_NOT_ANSWER | Harry Potter cast is unrelated to Mr. Potter in the specified film. |
| 7 | is there an australian version of i'm a celebrity | OBVIOUSLY_NOT_ANSWER | Other Australian reality competitions do not establish the requested series. |
| 8 | where does the secretary bird get its name | OBVIOUSLY_NOT_ANSWER | A memoir title does not explain the bird name. |
| 9 | who is the narrator talking to in tell tale heart | OBVIOUSLY_NOT_ANSWER | Titanic fictional necklace does not identify the Poe narrator interlocutor. |
| 10 | cancer is a disease that usually results when | OBVIOUSLY_NOT_ANSWER | Cancer charity organization does not explain disease causation. |
| 11 | where do they film anne with an e | OBVIOUSLY_NOT_ANSWER | A different film does not give Anne filming locations. |
| 12 | briefly explain html. what are the essential features of html | OBVIOUSLY_NOT_ANSWER | HTTP communication protocol does not give HTML language features. |
| 13 | who wrote the first 5 book of the bible | AMBIGUOUS | General Bible composition overlaps authorship but does not specify the first five books; ambiguous relevance. |
| 14 | why is climate different in different parts of india | AMBIGUOUS | General geographic climate factors could partially explain Indian regional variation; ambiguous partial relevance. |
| 15 | when did here comes the sun come out | OBVIOUSLY_NOT_ANSWER | Different song and artist. |
| 16 | who wrote the song baby it's cold outside | OBVIOUSLY_NOT_ANSWER | Different song and author. |
| 17 | who did the restoration restore to power in england | OBVIOUSLY_NOT_ANSWER | Anglo-Saxon history predates the Restoration and does not name the restored monarch. |
| 18 | who did vocals for mcdonald's i'm loving it | OBVIOUSLY_NOT_ANSWER | Different song and vocalist. |
| 19 | who sings i want to talk about me | OBVIOUSLY_NOT_ANSWER | Different song and vocalist. |
| 20 | what is a pivot joint in the body | OBVIOUSLY_NOT_ANSWER | Spreadsheet pivot tables are unrelated to anatomical joints. |
| 21 | who sang you'll never walk alone 1st | OBVIOUSLY_NOT_ANSWER | Different song, no original performer for requested song. |
| 22 | historically which party was dominant in texas from post-civil war until the 1960s | OBVIOUSLY_NOT_ANSWER | Pre-Civil-War annexation does not identify the later dominant party. |
| 23 | when was the last time we had a 5 star general | OBVIOUSLY_NOT_ANSWER | Military transport aircraft does not give a five-star general date. |
| 24 | when did america become the united states of america | OBVIOUSLY_NOT_ANSWER | Economic policy does not give the national founding/name date. |
| 25 | when was the name of the first malicious software detected on a pc | OBVIOUSLY_NOT_ANSWER | 2001 worm is not the first detected malicious software. |

## Environment, controls, and training

Measured preflight versions: `{'python': '3.11.9 (tags/v3.11.9:de54cf5, Apr  2 2024, 10:12:12) [MSC v.1938 64 bit (AMD64)]', 'torch': '2.11.0+cu128', 'transformers': '5.15.1', 'datasets': '5.0.0', 'sentence_transformers': '5.6.0', 'accelerate': '1.14.0', 'faiss': '1.14.3'}`. CUDA 12.8; NVIDIA GeForce RTX 5060 Laptop GPU; total/free VRAM 8,546,484,224/7,385,120,768 bytes; total/available RAM 16,438,054,912/3,767,996,416 bytes; disk free 61,589,413,888 bytes. BF16 support: True.

G2 was independently loaded from the untouched A snapshot `C:\Users\balak\.cache\huggingface\hub\models--sentence-transformers--all-MiniLM-L6-v2\snapshots\1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, not G1. Base `model.safetensors` SHA-256: `53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db`. All baseline snapshot file hashes are recorded in the preflight. G1 recorded model/data/index hashes passed verification and its full before/after file snapshot has 0 changes.

Fresh A reproduction: all 30 DEV questions have exactly matching historical Top50 chunk IDs; 29 are evaluable. Historical records also contain TEST rows, which were filtered out for the comparison; no TEST query was encoded/evaluated. The initial overly strict all-splits ID-set check was corrected to DEV-only; actual DEV rankings never mismatched.

Explicit-negative contract: focused synthetic trainer/collator/loss test passed (1 test). Query, positive, negative all reach MNRL; changing only the negative changes the loss. Real smoke/full trainer batches also assert all three columns. Metadata score/rank columns are explicitly excluded from the training Dataset. Every training loss is checked for finiteness before backward.

Loss `MultipleNegativesRankingLoss`; batch sampler `NO_DUPLICATES`; physical/effective contrastive batch 16/16; gradient accumulation 1; BF16 True; FP16 False. Seed42, 1 epoch, lr2e-5, weight decay.01, linear schedule, .05 warmup. No hyperparameter deviation from G1. Accumulation is not used to enlarge the in-batch pool.

Smoke: 1024 triplets, 64 steps, loss 0.050352; forward/backward, finite BF16 loss, saved-model reload and normalized 384-d encode passed. Minimum GPU free headroom 5,954,863,104 bytes.

Full: 45000 triplets, 2813 steps, 433.57 seconds; training aggregate loss 0.039054. Peak reserved/allocated VRAM 1,440,743,424/1,314,332,672 bytes; minimum global GPU headroom 5,902,434,304 bytes; peak process RSS 2,385,162,240 bytes. Safety callbacks monitor free GPU memory and finite loss/gradients; no unrelated processes were stopped.

Isolated model `D:\SDC\LibraryLLM\datasets\training\models\minilm_g2_nq_50k_full`; model weights SHA-256 `f1a5609a3315525d9794e16e6813d090b89970e533ac601352e8a2c9452a92ea`. Saved reload/window256/dimension384 verification passed.

## Generic NQ held-out sanity

actual held-out retrieval; candidate corpus = deduplicated 5k validation positives; not full NQ corpus; 5000 queries; 4864 candidates. This is actual bounded retrieval, not full-NQ retrieval and not a LuminaR promotion criterion.

Normalized-query overlap is zero; 1202 distinct positive passages appear in both TRAIN and validation. This is held-out-question sanity, not an unseen-document generalization test.

| Metric | A | G2 |
|---|---:|---:|
| MRR@50 | 0.9249 | 0.9321 |
| Hit@1 | 0.8726 | 0.8854 |
| Hit@5 | 0.9882 | 0.9878 |
| Hit@10 | 0.9946 | 0.9942 |
| Hit@20 | 0.9968 | 0.9958 |
| Hit@50 | 0.9978 | 0.9976 |

## Frozen LuminaR DEV result

Exact same 16,895 chunks, 18 books, tokens_220. Embedding shape `[16895, 384]`, finite/normalized; norm min/max 0.9999998808/1.0000001192. Global and per-book IndexFlatIP, dimension384; global count 16895; 18 per-book indexes. Embeddings SHA-256 `774d36470093251626bddac2e60fabe9c266ff5a6679a6386f735c86ba65a9a2`; global index SHA-256 `cbc38658b6e6583df6480a58ad9e76da24d3dd13885011a03ff4eae5641fd03b`. Frozen source/label/mapping hashes verified.

Original query only, dense-only per-book retrieval, DEV only. No expansion, lexical, union, reranker, Qwen, or answer generation.

| Metric | A baseline | G1 MS MARCO (historical) | G2 NQ |
|---|---:|---:|---:|
| MRR | 0.1653 | 0.1096 | 0.1544 |
| Hit@1 | 6.90% | 3.45% | 6.90% |
| Hit@3 | 17.24% | 10.34% | 17.24% |
| Hit@5 | 24.14% | 17.24% | 24.14% |
| Hit@10 | 34.48% | 24.14% | 34.48% |
| Hit@20 | 48.28% | 37.93% | 41.38% |
| Hit@50 | 65.52% | 51.72% | 62.07% |
| Recall@5 | 24.14% | 17.24% | 24.14% |
| Recall@10 | 34.48% | 24.14% | 34.48% |
| Recall@20 | 46.55% | 37.93% | 39.66% |
| Recall@50 | 62.07% | 50.00% | 60.34% |
| No accepted span Top50 | 10 | 14 | 11 |

A→G2 movement: `{'IMPROVED': 9, 'REGRESSED': 11, 'UNCHANGED': 9}`; recovered Top50 1; lost Top50 2. These describe this small DEV sample and do not establish statistical generalization.

| Query | Work | Movement | A accepted ranks | G2 accepted ranks |
|---|---|---|---|---|
| v8_01 | Frankenstein (OL45326637W) | UNCHANGED | [None] | [None] |
| v8_02 | Frankenstein (OL45326637W) | IMPROVED | [4] | [1] |
| v8_03 | Frankenstein (OL45326637W) | IMPROVED | [8] | [2] |
| v8_04 | Frankenstein (OL45326637W) | UNCHANGED | [None] | [None] |
| v8_06 | Dracula (OL85892W) | IMPROVED | [None] | [32] |
| v8_07 | Dracula (OL85892W) | UNCHANGED | [None, None, None] | [None, None, None] |
| v8_08 | Dracula (OL85892W) | IMPROVED | [46, None] | [15, None] |
| v8_09 | Frankenstein (OL45326637W) | UNCHANGED | [None, None] | [None, None] |
| v8_10 | Frankenstein (OL45326637W) | REGRESSED | [23, 13] | [24, 43] |
| pp_01 | Pride and Prejudice (OL66524W) | REGRESSED | [12] | [30] |
| pp_02 | Pride and Prejudice (OL66524W) | REGRESSED | [17] | [None] |
| pp_03 | Pride and Prejudice (OL66524W) | REGRESSED | [7] | [11] |
| pp_04 | Pride and Prejudice (OL66524W) | UNCHANGED | [None] | [None] |
| pp_05 | Pride and Prejudice (OL66524W) | UNCHANGED | [None] | [None] |
| alice_01 | Alice's Adventures in Wonderland (OL38619874W) | REGRESSED | [4] | [6] |
| alice_02 | Alice's Adventures in Wonderland (OL38619874W) | IMPROVED | [17] | [10] |
| alice_03 | Alice's Adventures in Wonderland (OL38619874W) | REGRESSED | [1] | [3] |
| alice_04 | Alice's Adventures in Wonderland (OL38619874W) | REGRESSED | [2] | [5] |
| alice_05 | Alice's Adventures in Wonderland (OL38619874W) | REGRESSED | [1] | [2] |
| time_01 | The Time Machine (OL27039837W) | REGRESSED | [44, None] | [None, None] |
| time_02 | The Time Machine (OL27039837W) | IMPROVED | [50] | [23] |
| time_03 | The Time Machine (OL27039837W) | UNCHANGED | [None] | [None] |
| time_04 | The Time Machine (OL27039837W) | IMPROVED | [10] | [9] |
| time_05 | The Time Machine (OL27039837W) | REGRESSED | [22] | [27] |
| war_01 | The War of the Worlds (OL33027136W) | UNCHANGED | [None] | [None] |
| war_02 | The War of the Worlds (OL33027136W) | REGRESSED | [2] | [46] |
| war_03 | The War of the Worlds (OL33027136W) | UNCHANGED | [None] | [None] |
| war_04 | The War of the Worlds (OL33027136W) | IMPROVED | [2] | [1] |
| war_05 | The War of the Worlds (OL33027136W) | IMPROVED | [27] | [5] |

### Recovered: v8_06 — Dracula (OL85892W)

Why doesn't Jonathan Harker leave the castle?

A accepted ranks: [None]; G2 accepted ranks: [32].

A diagnostic top passages:

- Rank 1, `OL85892W__tokens_220__b2fcccaa27b65e8a`: Harker and Harker; Quincey and Art are all out following up the clues as to the earth-boxes. I shall finish my round of work and we shall meet to-night.  _Mina Harker’s Journal._  _1 October._--It is strange to me to be kept in the dark as I am to-day; after Jonathan’s full confidence for so many years, to see him manifestly avoid certain matters, and those the most vital of all. This morning I slept late after the fatigues of yesterday, and thou
- Rank 2, `OL85892W__tokens_220__84ba230d9042d7cc`: He have always the strength in his hand of twenty men; even we four who gave our strength to Miss Lucy it also is all to him. Besides, he can summon his wolf and I know not what. So if it be that he come thither on this night he shall find me; but none other shall--until it be too late. But it may be that he will not attempt the place. There is no reason why he should; his hunting ground is more full of game than the churchyard where the Un-Dead 
- Rank 3, `OL85892W__tokens_220__bd0e1f87626f1267`: It was terribly weak, and looked quite emaciated. It too, when partially restored, had the common story to tell of being lured away by the “bloofer lady.”  CHAPTER XIV  MINA HARKER’S JOURNAL  _23 September_.--Jonathan is better after a bad night. I am so glad that he has plenty of work to do, for that keeps his mind off the terrible things; and oh, I am rejoiced that he is not now weighed down with the responsibility of his new position. I knew h
G2 diagnostic top passages:

- Rank 1, `OL85892W__tokens_220__b2fcccaa27b65e8a`: Harker and Harker; Quincey and Art are all out following up the clues as to the earth-boxes. I shall finish my round of work and we shall meet to-night.  _Mina Harker’s Journal._  _1 October._--It is strange to me to be kept in the dark as I am to-day; after Jonathan’s full confidence for so many years, to see him manifestly avoid certain matters, and those the most vital of all. This morning I slept late after the fatigues of yesterday, and thou
- Rank 2, `OL85892W__tokens_220__84ba230d9042d7cc`: He have always the strength in his hand of twenty men; even we four who gave our strength to Miss Lucy it also is all to him. Besides, he can summon his wolf and I know not what. So if it be that he come thither on this night he shall find me; but none other shall--until it be too late. But it may be that he will not attempt the place. There is no reason why he should; his hunting ground is more full of game than the churchyard where the Un-Dead 
- Rank 3, `OL85892W__tokens_220__34ab94d264decd0c`: Harker realised the danger herself, it was much pain as well as much danger averted. Under the circumstances we agreed, by a questioning look and answer, with finger on lip, to preserve silence in our suspicions, until we should have been able to confer alone again. We went at once into our Plan of Campaign. Van Helsing roughly put the facts before us first:--  “The _Czarina Catherine_ left the Thames yesterday morning. It will take her at the qu

### Lost: pp_02 — Pride and Prejudice (OL66524W)

How does Darcy describe Elizabeth when declining to dance with her?

A accepted ranks: [17]; G2 accepted ranks: [None].

A diagnostic top passages:

- Rank 1, `OL66524W__tokens_220__c7c2902b1742e25c`: He paused in hopes of an answer: but his companion was not disposed to make any; and Elizabeth at that instant moving towards them, he was struck with the notion of doing a very gallant thing, and called out to her,--  “My dear Miss Eliza, why are not you dancing? Mr. Darcy, you must allow me to present this young lady to you as a very desirable partner. You cannot refuse to dance, I am sure, when so much beauty is before you.” And, taking her ha
- Rank 2, `OL66524W__tokens_220__b30be6ce14886144`: Elizabeth made no answer, and took her place in the set, amazed at the dignity to which she was arrived in being allowed to stand opposite to Mr. Darcy, and reading in her neighbours’ looks their equal amazement in beholding it. They stood for some time without speaking a word; and she began to imagine that their silence was to last through the two dances, and, at first, was resolved not to break it; till suddenly fancying that it would be the gr
- Rank 3, `OL66524W__tokens_220__3961e6ba460a571f`: Darcy, who, though extremely surprised, was not unwilling to receive it, when she instantly drew back, and said with some discomposure to Sir William,--  “Indeed, sir, I have not the least intention of dancing. I entreat you not to suppose that I moved this way in order to beg for a partner.”  Mr. Darcy, with grave propriety, requested to be allowed the honour of her hand, but in vain. Elizabeth was determined; nor did Sir William at all shake he
G2 diagnostic top passages:

- Rank 1, `OL66524W__tokens_220__e27568b05b935f28`: Elizabeth, easy and unaffected, had been listened to with much more pleasure, though not playing half so well; and Mary, at the end of a long concerto, was glad to purchase praise and gratitude by Scotch and Irish airs, at the request of her younger sisters, who with some of the Lucases, and two or three officers, joined eagerly in dancing at one end of the room.  Mr. Darcy stood near them in silent indignation at such a mode of passing the eveni
- Rank 2, `OL66524W__tokens_220__3961e6ba460a571f`: Darcy, who, though extremely surprised, was not unwilling to receive it, when she instantly drew back, and said with some discomposure to Sir William,--  “Indeed, sir, I have not the least intention of dancing. I entreat you not to suppose that I moved this way in order to beg for a partner.”  Mr. Darcy, with grave propriety, requested to be allowed the honour of her hand, but in vain. Elizabeth was determined; nor did Sir William at all shake he
- Rank 3, `OL66524W__tokens_220__c7c2902b1742e25c`: He paused in hopes of an answer: but his companion was not disposed to make any; and Elizabeth at that instant moving towards them, he was struck with the notion of doing a very gallant thing, and called out to her,--  “My dear Miss Eliza, why are not you dancing? Mr. Darcy, you must allow me to present this young lady to you as a very desirable partner. You cannot refuse to dance, I am sure, when so much beauty is before you.” And, taking her ha

### Lost: time_01 — The Time Machine (OL27039837W)

What year does the Time Traveller say he has reached when he meets the Eloi?

A accepted ranks: [44, None]; G2 accepted ranks: [None, None].

A diagnostic top passages:

- Rank 1, `OL27039837W__tokens_220__0b77b629a260b8a1`: At the risk of disappointing Richardson I stayed on, waiting for the Time Traveller; waiting for the second, perhaps still stranger story, and the specimens and photographs he would bring with him. But I am beginning now to fear that I must wait a lifetime. The Time Traveller vanished three years ago. And, as everybody knows now, he has never returned.  Epilogue  One cannot choose but wonder. Will he ever return? It may be that he swept back into
- Rank 2, `OL27039837W__tokens_220__8318352404474dd2`: But the Time Traveller had more than a touch of whim among his elements, and we distrusted him. Things that would have made the fame of a less clever man seemed tricks in his hands. It is a mistake to do things too easily. The serious people who took him seriously never felt quite sure of his deportment; they were somehow aware that trusting their reputations for judgment with him was like furnishing a nursery with eggshell china. So I don’t thin
- Rank 3, `OL27039837W__tokens_220__b924fd20b5d9a134`: You read, I will suppose, attentively enough; but you cannot see the speaker’s white, sincere face in the bright circle of the little lamp, nor hear the intonation of his voice. You cannot know how his expression followed the turns of his story! Most of us hearers were in shadow, for the candles in the smoking-room had not been lighted, and only the face of the Journalist and the legs of the Silent Man from the knees downward were illuminated. At
G2 diagnostic top passages:

- Rank 1, `OL27039837W__tokens_220__8318352404474dd2`: But the Time Traveller had more than a touch of whim among his elements, and we distrusted him. Things that would have made the fame of a less clever man seemed tricks in his hands. It is a mistake to do things too easily. The serious people who took him seriously never felt quite sure of his deportment; they were somehow aware that trusting their reputations for judgment with him was like furnishing a nursery with eggshell china. So I don’t thin
- Rank 2, `OL27039837W__tokens_220__0b77b629a260b8a1`: At the risk of disappointing Richardson I stayed on, waiting for the Time Traveller; waiting for the second, perhaps still stranger story, and the specimens and photographs he would bring with him. But I am beginning now to fear that I must wait a lifetime. The Time Traveller vanished three years ago. And, as everybody knows now, he has never returned.  Epilogue  One cannot choose but wonder. Will he ever return? It may be that he swept back into
- Rank 3, `OL27039837W__tokens_220__2a0ec14fa8e64c08`: “I’m frightfully busy,” said he, “with that thing in there.”  “But is it not some hoax?” I said. “Do you really travel through time?”  “Really and truly I do.” And he looked frankly into my eyes. He hesitated. His eye wandered about the room. “I only want half an hour,” he said. “I know why you came, and it’s awfully good of you. There’s some magazines here. If you’ll stop to lunch I’ll prove you this time travelling up to the hilt, specimens and

Additional machine-readable diagnostics are in `rag_g2_nq_eval.json`.

### Descriptive check of four G1-lost queries

| Query | A accepted ranks | G2 accepted ranks |
|---|---|---|
| v8_08 | [46, None] | [15, None] |
| v8_10 | [23, 13] | [24, 43] |
| alice_04 | [2] | [5] |
| time_02 | [50] | [23] |

These four queries were not used to tune G2.

## Safety and files

**TEST evaluated: NO.** Cross-encoder and Qwen untouched. No domain QA training, other dataset training, mixture, production promotion, or G1 rerun.

Before/after safety: `{'production_files': 64, 'production_changed': 0, 'g1_files': 61, 'g1_changed': 0, 'baseline_unchanged': True, 'corpus_labels_sources_unchanged': True}`. Only experiment scripts/test and isolated G2 data/cache/models/checkpoints/manifests/indexes/reports were added. No production or evaluation-label changes. G1 reports remain unchanged; no independent historical report hash ledger exists beyond this run's before/after snapshot.

- `datasets/training/reports/rag_g2_nq_final.json`
- `datasets/training/reports/rag_g2_nq_final.md`
- `datasets\training\reports\rag_g2_baseline_reproduction.json`
- `datasets\training\reports\rag_g2_baseline_reproduction.log`
- `datasets\training\reports\rag_g2_nq_calibration.log`
- `datasets\training\reports\rag_g2_nq_contract_test.log`
- `datasets\training\reports\rag_g2_nq_eval.json`
- `datasets\training\reports\rag_g2_nq_eval.log`
- `datasets\training\reports\rag_g2_nq_eval.md`
- `datasets\training\reports\rag_g2_nq_generic_validation.json`
- `datasets\training\reports\rag_g2_nq_generic_validation.log`
- `datasets\training\reports\rag_g2_nq_index.log`
- `datasets\training\reports\rag_g2_nq_miner_docstring.txt`
- `datasets\training\reports\rag_g2_nq_mining.log`
- `datasets\training\reports\rag_g2_nq_preflight.json`
- `datasets\training\reports\rag_g2_nq_smoke.log`
- `datasets\training\reports\rag_g2_nq_source_probe.json`
- `datasets\training\reports\rag_g2_nq_source_probe_retry.json`
- `datasets\training\reports\rag_g2_nq_split_audit.json`
- `datasets\training\reports\rag_g2_nq_training.log`
- `scripts\build_rag_g2_index.py`
- `scripts\evaluate_nq_g2_validation.py`
- `scripts\evaluate_rag_g2.py`
- `scripts\mine_nq_hard_negatives_g2.py`
- `scripts\nq_g2_controls.py`
- `scripts\prepare_nq_g2.py`
- `scripts\probe_nq_g2_source.py`
- `scripts\report_nq_g2.py`
- `scripts\train_nq_biencoder_g2.py`
- `tests\test_nq_g2_training.py`

**FINAL G2 DECISION: C. NATURAL QUESTIONS G2 REGRESSES LUMINAR RETRIEVAL.**