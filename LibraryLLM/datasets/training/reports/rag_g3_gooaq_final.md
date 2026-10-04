# G3_GOOAQ — consolidated controlled experiment

**Decision: B. GOOAQ G3 IS NEUTRAL / INCONCLUSIVE.**

The valid comparison is untouched A → independently initialized GooAQ G3. G1/G2 remain COMPLETE AND FROZEN, with regression conclusions unchanged. All downstream results are experimental/descriptive because DEV labels remain DRAFT. TEST evaluated: NO. Stop after G3; no mixture, other dataset, reranker, or production promotion.

## Source, bounded sampling, inventory, and frozen pairs

Dataset [`sentence-transformers/gooaq`](https://huggingface.co/datasets/sentence-transformers/gooaq); config `pair`; revision `b089f728748a068b7bc5234e5bcf5b25e3c8279c`; split `train`; features `{'question': 'string', 'answer': 'string'}`; published source count 3,012,496. Automatic Hugging Face access/streaming succeeded without authentication. Cache `D:\SDC\LibraryLLM\datasets\training\hf_cache\gooaq_g3`; Windows symlink warning caused copy-based caching. No alternate source or complete multi-million-row materialization.

Sampling `{'seed': 42, 'shuffle_buffer': 10000, 'pair_rule': 'first 50k usable distinct normalized queries from seeded shuffled stream; seed-42 final shuffle, 45k/5k split; no later replacements', 'pool_rule': 'continue same shuffled stream until at least 200k normalized unique answers; bounded cap 500k processed source records', 'buffer_note': 'rows_inspected counts yielded rows; up to 10k lookahead rows may be internally buffered'}`. Inspected/materialized 255,250 bounded source rows, selected 50,000 pairs = 45,000 TRAIN + 5,000 validation. This is bounded buffered streaming sampling, not a globally uniform source sample. All TRAIN questions/positives were frozen before mining and remain identical in the same order; replacements: 0.

| Bounded source inventory | Count |
|---|---:|
| empty_questions | 0 |
| empty_answers | 0 |
| exact_duplicate_pairs | 0 |
| duplicate_normalized_questions | 0 |
| duplicate_answer_passages | 55250 |
| question_equals_answer | 0 |
| multi_positive_questions | 0 |

Normalized TRAIN/validation query overlap: 0. Multi-positive handling: all alternate positives discoverable among bounded inspected source records; unknown positives outside this pool remain unlabelled. Text canonicalization: first-seen original passage for normalized-equivalent texts; selected positives use that canonical source passage. Mining corpus provenance maps each canonical passage to a saved bounded source record ID; these IDs are processed shuffled-stream ordinals, not global source row numbers.

| Token length scope | Field | Min | Median | p90 | p95 | p99 | Max | >256 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| inspected_usable | question | 8 | 12 | 15 | 16 | 18 | 34 | 0 |
| inspected_usable | answer | 10 | 61 | 77 | 85 | 109 | 197 | 0 |
| selected_50000 | question | 8 | 12 | 15 | 16 | 18 | 34 | 0 |
| selected_50000 | answer | 11 | 61 | 77 | 85 | 110 | 197 | 0 |

Untruncated MiniLM token counts include special tokens. Model window remained 256.

| Frozen file | Rows | SHA-256 |
|---|---:|---|
| pairs_train | 45000 | `1ccb299ae166fd7007cfe13fc85a6888b8b47b5a504ca5da37150ac4b711de25` |
| pairs_validation | 5000 | `ab658a0657038e0b642e2f0637fa1ed8881687ad0401b2c554d060daa28fa271` |
| source_records | 255250 | `6dbbc76766617df9670744f496494100cb59e645273588bb5ad51de66d677fce` |
| answer_corpus | 200000 | `e723e858ca3c427e0a54c1e4690e0595ae5897d018724e75028376b517e9716c` |

Source manifest SHA-256 `70231f683e953cd663ca51024b0c4d3c664ae78329a52e00c181ed093c64ff72`; final data manifest SHA-256 `d45756db7cdd60b30a66ad21b20d1594ba97f17513e94800bd6adc48bc907c51`.

The negative corpus is a deterministic 200,000-passage pool, substantially larger than TRAIN positives, and is not the full 3-million-row answer corpus. Bounded mining limits RAM/disk/resource use on this shared machine.

## Mining calibration and source audit

Installed `sentence_transformers.util.mine_hard_negatives` signature: `(dataset: 'Dataset', model: 'SentenceTransformer', anchor_column_name: 'str | None' = None, positive_column_name: 'str | None' = None, corpus: 'list[str] | None' = None, cross_encoder: 'CrossEncoder | None' = None, range_min: 'int' = 0, range_max: 'int | None' = None, max_score: 'float | None' = None, min_score: 'float | None' = None, absolute_margin: 'float | None' = None, relative_margin: 'float | None' = None, num_negatives: 'int' = 3, sampling_strategy: "Literal['random', 'top']" = 'top', query_prompt_name: 'str | None' = None, query_prompt: 'str | None' = None, corpus_prompt_name: 'str | None' = None, corpus_prompt: 'str | None' = None, include_positives: 'bool' = False, output_format: "Literal['triplet', 'n-tuple', 'labeled-pair', 'labeled-list']" = 'triplet', output_scores: 'bool' = False, batch_size: 'int' = 32, faiss_batch_size: 'int' = 16384, use_faiss: 'bool' = False, use_multi_process: 'list[str] | bool' = False, verbose: 'bool' = True, cache_folder: 'str | None' = None, as_triplets: 'bool | None' = None, margin: 'float | None' = None) -> 'Dataset'`. It was used with baseline A, full bounded answer pool, FAISS, five candidates per query, random seeded candidate sampling, and one retained negative. No G1/G2 model or cross-encoder.

500 deterministic TRAIN questions; initial window `[10, 100]`, wider safe window `[10, 500]`. Final settings `{'absolute_margin': 0.02448827922344208, 'relative_margin': 0.03535122352084876, 'max_score': 0.5955077618360519}`. Derivation/adjustment: GooAQ raw calibration: absolute margin = clipped half p10 observed gap [.01,.04]; relative margin = absolute/median positive clipped [.02,.08]; cap = min(.85, negative p99+.03, positive p75); Engineering audit trial1 found one possible alternate answer (calorie-deficit question) and two ambiguous partial-relevance cases; tightened ceiling to measured raw negative p95, preserving margins and query distribution.. Initial audit trial found one possible alternate answer and two ambiguous cases; the ceiling was tightened to measured GooAQ raw-negative p95. Trial1 artifacts are preserved. G2 thresholds were not reused.

Raw calibration distributions: `{'positive': {'min': 0.22060838341712952, 'p10': 0.5392104744911194, 'median': 0.6927137672901154, 'p90': 0.8092228055000305, 'p95': 0.8315198630094518, 'max': 0.8966025114059448, 'mean': 0.6811445517539978, 'count': 2500}, 'negative': {'min': 0.22604645788669586, 'p10': 0.3557638645172119, 'median': 0.45501962304115295, 'p90': 0.5633065462112427, 'p95': 0.5955077618360519, 'max': 0.8102681636810303, 'mean': 0.4580120831131935, 'count': 2500}, 'margin': {'min': -0.3128971755504608, 'p10': 0.04897655844688416, 'median': 0.23176255822181702, 'p90': 0.38806853294372556, 'p95': 0.42246534973382943, 'max': 0.5690655708312988, 'mean': 0.2231324686408043, 'count': 2500}}`. Final calibration distributions: `{'positive_score': {'min': 0.2206083983182907, 'p10': 0.5392104744911194, 'median': 0.6927137672901154, 'p90': 0.8092228055000306, 'p95': 0.8315198630094527, 'max': 0.8966025114059448, 'mean': 0.6811445515453816, 'count': 500}, 'negative_score': {'min': -0.009861718863248825, 'p10': 0.3756163835525513, 'median': 0.47956059873104095, 'p90': 0.5515644311904907, 'p95': 0.5656304121017456, 'max': 0.587933361530304, 'mean': 0.47095397931337357, 'count': 500}, 'score_margin': {'min': 0.02598351240158081, 'p10': 0.062032794952392584, 'median': 0.21035557985305786, 'p90': 0.35027461349964145, 'p95': 0.3796218037605283, 'max': 0.5290684700012207, 'mean': 0.210190572232008, 'count': 500}, 'negative_rank': {'min': 12.0, 'p10': 18.0, 'median': 34.0, 'p90': 69.0, 'p95': 83.25, 'max': 497.0, 'mean': 45.596774193548384, 'count': 496}}`. Calibration hard/random counts 496/4. installed miner applies rank slice to eligible candidates after score/positive masking; stored ranks are raw 1-based corpus ranks.

Final engineering source-text audit: 25 deterministic seed-42 samples, 22 OBVIOUSLY_NOT_ANSWER, 0 POSSIBLE_FALSE_NEGATIVE, 3 AMBIGUOUS. This is engineering sanity inspection, not human training-label review or a full false-negative-rate estimate.

| Sample | Question | Positive answer | Candidate negative | Classification | Reason |
|---|---|---|---|---|---|
| 1 | what is restricted holiday and gazetted holiday? | Restricted holidays are the holidays which an employee can avail from the list of Gazetted/restricted holidays. Further these are the holidays only for employee and not for the organization or government departments. | Presidents Day is a federal holiday, so almost all government offices are closed. U.S. Post Office – Closed. Mail will not run and the post offices is closed. UPS and FedEx – Some schedules will be altered but both will be delivering packages. | OBVIOUSLY_NOT_ANSWER | Specific US holiday closure does not define restricted versus gazetted holidays. |
| 2 | why afc falls as output increases? | In economics, average fixed cost (AFC) is the fixed costs of production (FC) divided by the quantity (Q) of output produced. ... As the total number of units of the good produced increases, the average fixed cost decreases because the same amount of fixed costs is being spread over a larger number of units of output. | Firms need to sell their extra output at a higher price so that they can pay the higher marginal cost of production. Hence, decisions to supply are largely determined by the marginal cost of production. The supply curve slopes upward, reflecting the higher price needed to cover the higher marginal cost of production. | OBVIOUSLY_NOT_ANSWER | Marginal-cost/supply behavior does not explain declining average fixed cost. |
| 3 | what is the significance of the number 8 in numerology? | Number 8's are single-minded and show good judgment and executive skills, often achieving power and material success. 8 represents justice and balance. Those under the influence of the powerful and karmic number 8 seem to endure life's hardships moreso than other numbers. | 1. VII - the cardinal number that is the sum of six and one. 7, heptad, septenary, septet, seven, sevener. digit, figure - one of the elements that collectively form a system of numeration; "0 and 1 are digits" | OBVIOUSLY_NOT_ANSWER | Roman numeral seven does not give numerological significance of eight. |
| 4 | what are the minimum requirements for windows 7 installation? | ['1 gigahertz (GHz) or faster 32-bit (x86) or 64-bit (x64) processor*', '1 gigabyte (GB) RAM (32-bit) or 2 GB RAM (64-bit)', '16 GB available hard disk space (32-bit) or 20 GB (64-bit)', 'DirectX 9 graphics device with WDDM 1.0 or higher driver.'] | ['Wireless broadband Internet access is required for online features. ... ', 'Additional games and systems required for multiplayer mode.'] | OBVIOUSLY_NOT_ANSWER | Unspecified gaming/network requirements do not give Windows 7 installation requirements. |
| 5 | how much is a vehicle inspection in nc? | NC Vehicle Inspection Price Safety inspection fees are $13.60. Emissions inspection fees, which include Safety Inspection, cost $30.00. After market window tinting costs an additional $10 for both inspections. | ​$50 one-time issuance fee and twice the annual registration fee for vehicle type. | OBVIOUSLY_NOT_ANSWER | Issuance/registration fees do not establish North Carolina inspection price. |
| 6 | what is the function of the ribs? | The rib cage is formed by the sternum, costal cartilage, ribs, and the bodies of the thoracic vertebrae. The rib cage protects the organs in the thoracic cavity, assists in respiration, and provides support for the upper extremities. | The major functions of the skeletal system are body support, facilitation of movement, protection of internal organs, storage of minerals and fat, and blood cell formation. | AMBIGUOUS | General skeletal-system functions overlap rib functions; ambiguous partial relevance. |
| 7 | how long does it take for first herpes outbreak after exposure? | The average incubation period for an initial herpes infection is 4 days (range, 2 to 12) after exposure. The vesicles break and leave painful ulcers that may take two to four weeks to heal after the initial herpes infection. Experiencing these symptoms is referred to as having a first herpes “outbreak” or episode. | HSV-1 can be transmitted from oral or skin surfaces that appear normal and when there are no symptoms present. However, the greatest risk of transmission is when there are active sores. Individuals who already have HSV-1 oral herpes infection are unlikely to be subsequently infected with HSV-1 in the genital area. | OBVIOUSLY_NOT_ANSWER | Herpes transmission discussion does not supply exposure-to-outbreak incubation time. |
| 8 | what vaccines are required to enter taiwan? | Yes, some vaccines are recommended or required for Taiwan. The National Travel Health Network and Centre and WHO recommend the following vaccinations for Taiwan: hepatitis A, hepatitis B, Japanese encephalitis, rabies and tetanus. Recommended for most travellers to the region, especially if unvaccinated. | The PHAC and WHO recommend the following vaccinations for South Korea: hepatitis A, hepatitis B, typhoid, Japanese encephalitis, rabies, meningitis, polio, measles, mumps and rubella (MMR), Tdap (tetanus, diphtheria and pertussis), chickenpox, shingles, pneumonia and influenza. | OBVIOUSLY_NOT_ANSWER | Travel vaccinations concern South Korea, not Taiwan. |
| 9 | what are the pimples on my nipples? | Montgomery glands are normal skin glands that appear as small, painless bumps on the areola, which is the area of darkened skin around the nipple. Every person has Montgomery glands, though they are more apparent in some than others. These glands secrete oil to help keep the skin lubricated. | Pimples popping up on your lower cheek, jawline, and chin is known as a “hormonal pattern.” Acne in these areas is often caused by your skin's oil glands overreacting to hormonal responses, which can be triggered by factors such as stress, eating too much sugar or dairy, or the (perfectly normal) fluctuations that ... | OBVIOUSLY_NOT_ANSWER | Facial acne does not identify nipple/areola bumps. |
| 10 | are bearer shares legal in the uk? | UK: Bearer Shares Banned The first of the corporate transparency provisions in the Small Business, Enterprise and Employment Act 2015 came into force on 26 May 2015 with the banning of share warrants to bearer, or bearer shares as they are more commonly known. | In some countries, dowry has been outlawed due to the female death toll associated with it, but the practice remains legal in Britain. | OBVIOUSLY_NOT_ANSWER | Dowry legality does not establish bearer-share legality. |
| 11 | what is the primary function of the hormone adh? | Anti-diuretic hormone. Anti-diuretic hormone acts to maintain blood pressure, blood volume and tissue water content by controlling the amount of water and hence the concentration of urine excreted by the kidney. | Both systems control body functions. The nervous system controls through motor responses. Responses are quick, and short-lived. The endocrine system controls through chemicals, and responses are slow and long-lasting. | OBVIOUSLY_NOT_ANSWER | General endocrine control does not state the specific ADH function. |
| 12 | can apple cider vinegar lower blood pressure? | Take apple cider vinegar. Most importantly, it helps with weight loss by improving metabolism and reducing water retention -- and a healthy weight is key to normalizing blood pressure. Easy fix: Three teaspoons per day of apple cider vinegar can lower your blood pressure significantly within a week. | Apple cider vinegar has lots of health benefits, but drinking it straight isn't for the faint of heart. Combining it with other ingredients makes it much more palatable—and combining it with green tea, ginger and honey makes it an antioxidant-packed, cold-fighting powerhouse. | OBVIOUSLY_NOT_ANSWER | Vinegar taste/cold-fighting discussion does not address blood pressure. |
| 13 | they are few and far between meaning? | phrase. Things that are few and far between are very rare or do not happen very often. [emphasis] Visitors to the town were few and far between. Synonyms: scarce, rare, unusual, scattered More Synonyms of few and far between. | Homonyms Homophones Antonyms Synonyms. Antonyms are words that have opposite meanings, like large and small or hard and easy. | OBVIOUSLY_NOT_ANSWER | Antonym definition does not explain the requested idiom. |
| 14 | which among the following cell organelles does not participate in cellular division? | It is a fact considered that Neurons cannot divide because they lack centrioles. Centrioles are minute cylindrical organelle present near the nucleus in animal cells involved in the development of Spindle fibres in Cell division. | Contains genetic material, including DNA, which controls the cell's activities. Its structure is permeable to some substances but not to others. It therefore controls the movement of substances in and out of the cell. Organelles that contain the enzymes for respiration, and where most energy is released in respiration. | OBVIOUSLY_NOT_ANSWER | Generic cellular structures/respiration description does not identify participation in cell division. |
| 15 | what is the basic difference between covalent and ionic bonding? | The two main types of chemical bonds are ionic and covalent bonds. An ionic bond essentially donates an electron to the other atom participating in the bond, while electrons in a covalent bond are shared equally between the atoms. The only pure covalent bonds occur between identical atoms. | Covalent compounds are formed on the basis of sharing electrons. When the electrons are shared within the bonds, there is no electrons available to conduct electricity - hence why covalent compounds are generally poor conductors of electricity. | AMBIGUOUS | Explains covalent sharing without ionic comparison; ambiguous partial answer. |
| 16 | how long does it take to get verified for doordash? | This can vary for each restaurant and generally takes between 3-5 days on average. | Generally, it takes about 3 to 5 months to get a decision. However, the exact time depends on how long it takes to get your medical records and any other evidence needed to make a decision. * How does Social Security make the decision? | OBVIOUSLY_NOT_ANSWER | Social Security decision time does not answer DoorDash verification time. |
| 17 | when cm election in bihar? | 2020 Bihar Legislative Assembly election. Bihar Legislative Assembly elections will be held in Bihar in October 2020 to elect 243 members of the Bihar Legislative Assembly. | “The results will be released tomorrow February 28, 2019 at 10am at the President's office in the main auditorium. Minister of state for higher education will release them in acting capacity at the Minister of Education and Sports,” Muinda told SoftPower News on Wednesday. | OBVIOUSLY_NOT_ANSWER | Education result announcement does not answer Bihar election timing. |
| 18 | can lactose intolerant eat yogurt? | Summary: Lactose intolerant people often find yogurt much easier to digest than milk. The best yogurt for people with lactose intolerance is a full-fat, probiotic yogurt that contains live bacterial cultures. | Hard, aged cheeses like Swiss, parmesan, and cheddars are lower in lactose. Other low-lactose cheese options include cottage cheese or feta cheese made from goat or sheep's milk. ... If you want to avoid dairy completely, try lactose-free and dairy-free cheeses. | OBVIOUSLY_NOT_ANSWER | Cheese lactose levels do not answer yogurt tolerance. |
| 19 | what is the difference between a mazda 3 maxx and maxx sport? | maxx to maxx sport got climate control air, electronic park brake and a couple of other minor things. Happened in april last year. One of these is named as Mazda 3 Maxx and the other is named as Mada 3 Maxx Sports but they look exactly the same to me. The Maxx Sport has more crap crammed into it compared to the Maxx. | The only difference between the 883 and 1200 Sportster is the displacement of the engine. ... Simply put, the 1200 Sportster engine has a bit more material and weighs slightly more than the 883 engine; the difference in weight is too small though to make a significant effect on performance. | OBVIOUSLY_NOT_ANSWER | Sportster motorcycle engine comparison does not address Mazda trims. |
| 20 | what are the two major categories of probability interpretations? | There are two broad categories of probability interpretations which can be called "physical" and "evidential" probabilities. Physical probabilities, which are also called objective or frequency probabilities, are associated with random physical systems such as roulette wheels, rolling dice and radioactive atoms. | They also include artifacts such as paintings, coins, stamps, and manufactured items. Secondary sources are interpretations or analyses of primary source information. Secondary sources include textbooks, encyclopedias, as well as any secondhand telling of an event. | OBVIOUSLY_NOT_ANSWER | Primary/secondary historical sources do not categorize probability interpretations. |
| 21 | how to get a rental property with bad history? | ["Know What's in Your Credit Report. ... ", "Look for Property Owners Who Don't Check Credit. ... ", 'Get a Recommendation. ... ', 'Demonstrate Provable Income. ... ', 'Be Prepared to Pay More Upfront. ... ', 'Ask a Co-Signer to Help You.'] | If a taxpayer makes improvements to leased or owned property that qualifies for the shorter recovery period, the taxpayer is required to depreciate the improvement over 15 years for tax purposes. | OBVIOUSLY_NOT_ANSWER | Tax depreciation does not explain securing a rental with bad history. |
| 22 | how many calories it take to lose a pound? | Because 3,500 calories equals about 1 pound (0.45 kilogram) of fat, it's estimated that you need to burn about 3,500 calories to lose 1 pound. So, in general, if you cut about 500 to 1,000 calories a day from your typical diet, you'd lose about 1 to 2 pounds a week. | Setting a realistic time frame Generally, most health experts recommend aiming for about 1–3 pounds (0.5–1.4 kg) of weight loss per week, or approximately 1% of your total body weight ( 33 , 34 ). Therefore, it may take anywhere from a few weeks to several months to lose 30 pounds safely. | OBVIOUSLY_NOT_ANSWER | Weight-loss time frame does not give calorie deficit per pound. |
| 23 | what does it mean when you have grey hair on your private area? | The hairs on your genitals are subjected to exactly the same effects of time as those on your head. Hair follicles contain melanin, the pigment that gives hair (and your skin) its colour. As we get older, your body produces less melanin and your hair begins to turn grey, silver, or white. | There is nothing wrong with leaving this hair the way it is. But if you feel self conscious about the way it looks, you can remove it by shaving, applying a cream or waxing. Before you shave, make sure that you exfoliate the area and use warm water and a new razor to avoid any nicks or bumps. | OBVIOUSLY_NOT_ANSWER | Hair-removal instructions do not explain greying hair. |
| 24 | how many words is average novel? | A story that is over 40,000 words is generally considered a novel. However, it will be on the short side, as the average length of a novel hovers around 50,000-70,000 words. | There are 168,923 words. How many words are in Harry Potter and the Deathly Hallows? There are 198,227 words. While knowing the total number of words in the Harry Potter series isn't going to convince anyone to read all the books, knowing the total word count is an excellent way to encourage kids to read more. | OBVIOUSLY_NOT_ANSWER | Specific Harry Potter book counts do not give average novel length. |
| 25 | what is the relationship between elements and atoms quizlet? | Matter is anything that occupies space and has mass. what is the relationship between elements and atoms? Elements are substances that cannot be broken down chemically into simpler kinds of matter. Atoms are simplest particle of an element that continues to have all the properties of that element. | Isotopes are atoms that have the same numbers of protons but different numbers of neutrons. An ion is an atom that has gained or lost electrons, so it now has more or fewer electrons than it does protons. ... All atoms are isotopes and if an isotope gains or loses electrons it becomes an ion. | AMBIGUOUS | Isotope/ion definitions overlap atomic structure but do not state element-atom relationship; ambiguous relevance. |

Full mining: 44,713 HARD + 287 RANDOM_FALLBACK (0.64%); wider-window hard recoveries 1,058. Frozen TRAIN questions preserved, replacements 0. Fallback ≤5% gate passed. Safeguards: all normalized positives/alternates discoverable in bounded source records excluded; rank floor10, calibrated ceiling/margins; fixed safe wider window; random fallback also score/margin screened; no query replacement. Postfilter known-positive exclusions 0. Metadata is saved for diagnostics but excluded from model inputs.

Score/rank distributions: `{'positive_score': {'min': 0.018019119277596474, 'p10': 0.5480401396751404, 'median': 0.7044015228748322, 'p90': 0.8142160475254059, 'p95': 0.8389064013957976, 'max': 0.9471812844276428, 'mean': 0.6900377311041371, 'count': 45000}, 'negative_score': {'min': -0.20795796811580658, 'p10': 0.38397143185138705, 'median': 0.48256225883960724, 'p90': 0.5579559326171875, 'p95': 0.5686054527759552, 'max': 0.5920495986938477, 'mean': 0.47375354726517366, 'count': 45000}, 'score_margin': {'min': 0.025321662425994873, 'p10': 0.06940972506999969, 'median': 0.2159879207611084, 'p90': 0.3567699044942856, 'p95': 0.395626263320446, 'max': 0.6260011196136475, 'mean': 0.2162841838389635, 'count': 45000}, 'negative_rank': {'min': 12.0, 'p10': 17.0, 'median': 33.0, 'p90': 64.0, 'p95': 77.0, 'max': 500.0, 'mean': 41.22492340035336, 'count': 44713}}`. Final 45k triplets SHA-256 `0ae30b5083b831b298699511f1513eeb2b83d73ed145268d26614d44e01e059c`. Hard raw ranks are captured from the installed miner's native FAISS search outputs; observation does not change retrieval scores/candidates. Random fallback ranks are N/A.

## Current environment, initialization, contract, and training

Measured versions `{'python': '3.11.9 (tags/v3.11.9:de54cf5, Apr  2 2024, 10:12:12) [MSC v.1938 64 bit (AMD64)]', 'torch': '2.11.0+cu128', 'transformers': '5.15.1', 'datasets': '5.0.0', 'sentence_transformers': '5.6.0', 'accelerate': '1.14.0', 'faiss': '1.14.3'}`. CUDA 12.8; GPU NVIDIA GeForce RTX 5060 Laptop GPU; VRAM total/free 8,546,484,224/7,385,120,768 bytes; system RAM total/available 16,438,054,912/2,331,541,504 bytes; disk free 60,819,091,456 bytes; BF16 runtime support True.

Untouched A snapshot `C:\Users\balak\.cache\huggingface\hub\models--sentence-transformers--all-MiniLM-L6-v2\snapshots\1110a243fdf4706b3f48f1d95db1a4f5529b4d41`; base weights SHA-256 `53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db`. Full base-file fingerprint is in preflight and training manifests. Code asserts the base path is all-MiniLM-L6-v2 and contains neither G1 nor G2 experiment paths. Both smoke/full initialize freshly from A.

Contract test: 1 passed. Synthetic dataset includes metadata, explicitly selects question/positive/negative, retains negative_input_ids in collation, supplies three feature groups to MNRL, and proves changing the negative changes loss. Actual smoke/full trainer batches repeat the three-column assertion. Every loss is checked for finiteness before backward; callbacks guard finite logged gradients and ≥1.5 GiB free GPU memory. No unrelated processes/services were terminated.

Baseline A freshly reproduced all 30 DEV Top50 lists exactly against authoritative historical DEV records; 29 are evaluable. TEST rows were filtered out before model encoding/evaluation.

At the user's pause, mining and smoke had completed, and full training had not started. On explicit continuation, hashes and resources were checked again: free GPU memory 7,385,120,768 bytes; available system RAM 4,475,998,208 bytes; disk free 60,266,590,208 bytes. Full training starts freshly from A and does not load smoke weights.

Smoke: 1,024 triplets, 64 steps, finite aggregate loss 0.099021; BF16, forward/backward, saved checkpoint reload, normalized 384-dimensional encode all passed. Minimum free GPU headroom 6,284,115,968 bytes.

Full loss `MultipleNegativesRankingLoss`, sampler `NO_DUPLICATES`, physical/effective contrastive batch 16/16, accumulation1, BF16 True, FP16 False; 45k GooAQ-only triplets, seed42, 1 epoch, lr2e-5, weight decay.01, linear schedule, warmup.05. No hyperparameter/loss/window/architecture changes from G1/G2.

2813 steps in 348.20 seconds; aggregate final training loss 0.092800; peak reserved/allocated VRAM 1,077,936,128/940,789,760 bytes; minimum global free GPU headroom 6,263,144,448 bytes; peak process RSS 2,279,112,704 bytes.

Last logged training-loss window 0.074544. Aggregate loss above is the trainer's whole-run mean, not the final batch loss. Model `D:\SDC\LibraryLLM\datasets\training\models\minilm_g3_gooaq_50k_full`; weights SHA-256 `93e147de5e7a18998bff9a6cd9478ff6322553288403482bf6514792a0c940cd`; training-file hash `0ae30b5083b831b298699511f1513eeb2b83d73ed145268d26614d44e01e059c`. Reload/window256/dimension384/normalization verification passed.

## Generic GooAQ held-out sanity

actual held-out retrieval; candidate corpus = deduplicated 5k validation positives; not full GooAQ corpus. Questions 5,000; candidate corpus 4,909; normalized-query overlap 0; shared TRAIN/validation positive passages 674. This is held-out-question sanity, not a full-corpus benchmark or unseen-document test. It does not decide LuminaR promotion.

| Metric | A | G3 |
|---|---:|---:|
| MRR@50 | 0.9283 | 0.9260 |
| Hit@1 | 0.8820 | 0.8796 |
| Hit@5 | 0.9842 | 0.9834 |
| Hit@10 | 0.9934 | 0.9914 |
| Hit@20 | 0.9974 | 0.9968 |
| Hit@50 | 0.9986 | 0.9984 |

## Embedding/index integrity

Exact frozen tokens_220: shape `[16895, 384]`; finite and normalized; norm range 0.9999998808–1.0000001192; dimension384, global IndexFlatIP count 16,895 plus 18 per-book indexes. Embeddings SHA-256 `45668431c798415fb11169b38c4b4d615d7746a2f2acf4a2da5be3ffcc82b80a`; global FAISS SHA-256 `79276283bbeeb849f04b9fe46f1c9974eb4f8077edd1ea45f06c2c77e64a7d27`.

Global FAISS vectors and every per-book index were reconstructed and compared exactly to the saved G3 embedding rows in frozen corpus order. All 18 per-book counts, dimensions, inner-product types, and vector mappings passed. Per-book hashes are recorded in `rag_g3_gooaq_index_integrity.json`.

## Frozen LuminaR DEV four-way historical table

Original question, dense-only, per-book IndexFlatIP; no expansion, reranker, lexical, union, Qwen, or generation. Valid comparison A→G3; G1/G2 are frozen descriptive context.

| Metric | A | G1 MS MARCO | G2 NQ | G3 GooAQ |
|---|---:|---:|---:|---:|
| MRR | 0.1653 | 0.1096 | 0.1544 | 0.1360 |
| Hit@1 | 6.90% | 3.45% | 6.90% | 3.45% |
| Hit@3 | 17.24% | 10.34% | 17.24% | 17.24% |
| Hit@5 | 24.14% | 17.24% | 24.14% | 20.69% |
| Hit@10 | 34.48% | 24.14% | 34.48% | 37.93% |
| Hit@20 | 48.28% | 37.93% | 41.38% | 44.83% |
| Hit@50 | 65.52% | 51.72% | 62.07% | 72.41% |
| Recall@5 | 24.14% | 17.24% | 24.14% | 20.69% |
| Recall@10 | 34.48% | 24.14% | 34.48% | 37.93% |
| Recall@20 | 46.55% | 37.93% | 39.66% | 44.83% |
| Recall@50 | 62.07% | 50.00% | 60.34% | 68.97% |
| No accepted span Top50 | 10 | 14 | 11 | 8 |

Primary changes (G3 minus A): Hit@20 -3.45 percentage points; Hit@50 +6.90; Recall@20 -1.72; Recall@50 +6.90; no-gold Top50 -2. Decision uses these first-stage metrics; secondary MRR cannot override a primary tradeoff. Mixed directions are classified B, rather than counted as an unqualified improvement or regression.

A→G3 movement `{'IMPROVED': 8, 'REGRESSED': 7, 'UNCHANGED': 14}` across 29 evaluable DEV queries; recovered 2; lost 0. Movement labels use first accepted rank; recovered/lost are additional flags. Top20 entry ['time_05']; Top20 exits ['v8_10', 'pp_02'].

### RECOVERED_IN_TOP50: v8_06 — Dracula

Why doesn't Jonathan Harker leave the castle?

A accepted ranks [None]; G3 accepted ranks [47].

Frozen accepted-span diagnostic: cked and bolted. In no place save from the windows in the castle walls is there an available exit.  The castle is a veritable prison, and I am a prisoner!  CHAPTER III  JONATHAN HARKER’S JOURNAL--_continued_  When I found that I was a prisoner 

The accepted passage appears at rank 47; this recovery expands Top50 coverage but does not add a Top20 hit. Diagnostic top passages still need comparison with the frozen accepted span.

A diagnostic top passages:

- Rank 1, `OL85892W__tokens_220__b2fcccaa27b65e8a`: Harker and Harker; Quincey and Art are all out following up the clues as to the earth-boxes. I shall finish my round of work and we shall meet to-night.  _Mina Harker’s Journal._  _1 October._--It is strange to me to be kept in the dark as I am to-day; after Jonathan’s full confidence for so many years, to see him manifestly avoid certain matters, and those the most vital of all. This morning I slept late after the fatigues of yesterday, and thou
- Rank 2, `OL85892W__tokens_220__84ba230d9042d7cc`: He have always the strength in his hand of twenty men; even we four who gave our strength to Miss Lucy it also is all to him. Besides, he can summon his wolf and I know not what. So if it be that he come thither on this night he shall find me; but none other shall--until it be too late. But it may be that he will not attempt the place. There is no reason why he should; his hunting ground is more full of game than the churchyard where the Un-Dead 
- Rank 3, `OL85892W__tokens_220__bd0e1f87626f1267`: It was terribly weak, and looked quite emaciated. It too, when partially restored, had the common story to tell of being lured away by the “bloofer lady.”  CHAPTER XIV  MINA HARKER’S JOURNAL  _23 September_.--Jonathan is better after a bad night. I am so glad that he has plenty of work to do, for that keeps his mind off the terrible things; and oh, I am rejoiced that he is not now weighed down with the responsibility of his new position. I knew h
G3 diagnostic top passages:

- Rank 1, `OL85892W__tokens_220__b2fcccaa27b65e8a`: Harker and Harker; Quincey and Art are all out following up the clues as to the earth-boxes. I shall finish my round of work and we shall meet to-night.  _Mina Harker’s Journal._  _1 October._--It is strange to me to be kept in the dark as I am to-day; after Jonathan’s full confidence for so many years, to see him manifestly avoid certain matters, and those the most vital of all. This morning I slept late after the fatigues of yesterday, and thou
- Rank 2, `OL85892W__tokens_220__6eb69d39e29aba6c`: Harker has got the letters between the consignee of the boxes at Whitby and the carriers in London who took charge of them. He is now reading his wife’s typescript of my diary. I wonder what they make out of it. Here it is....  Strange that it never struck me that the very next house might be the Count’s hiding-place! Goodness knows that we had enough clues from the conduct of the patient Renfield! The bundle of letters relating to the purchase o
- Rank 3, `OL85892W__tokens_220__61178db585acbaa6`: Harker everything which had passed; and although she grew snowy white at times when danger had seemed to threaten her husband, and red at others when his devotion to her was manifested, she listened bravely and with calmness. When we came to the part where Harker had rushed at the Count so recklessly, she clung to her husband’s arm, and held it tight as though her clinging could protect him from any harm that might come. She said nothing, however

### RECOVERED_IN_TOP50: pp_05 — Pride and Prejudice

Which man does Lydia leave Brighton with, alarming her family?

A accepted ranks [None]; G3 accepted ranks [49].

Frozen accepted-span diagnostic: for time, my head is so bewildered that I cannot answer for being coherent. Dearest Lizzy, I hardly know what I would write, but I have bad news for you, and it cannot be delayed. Imprudent as a marriage between Mr. Wickham and our poor Lydia would be, we are now anxious to be assured it has taken place, for there is but too much reason to fear they are not gone to Scotland. Colonel Forster came yesterday, having left Brighton the day before, not

The accepted passage appears at rank 49; this recovery expands Top50 coverage but does not add a Top20 hit. Diagnostic top passages still need comparison with the frozen accepted span.

A diagnostic top passages:

- Rank 1, `OL66524W__tokens_220__ed4650337b0907aa`: Lydia’s going to Brighton was all that consoled her for the melancholy conviction of her husband’s never intending to go there himself.  But they were entirely ignorant of what had passed; and their raptures continued, with little intermission, to the very day of Lydia’s leaving home.  Elizabeth was now to see Mr. Wickham for the last time. Having been frequently in company with him since her return, agitation was pretty well over; the agitations
- Rank 2, `OL66524W__tokens_220__f915ac65851d429c`: She got up and ran out of the room; and returned no more, till she heard them passing through the hall to the dining-parlour. She then joined them soon enough to see Lydia, with anxious parade, walk up to her mother’s right hand, and hear her say to her eldest sister,--  “Ah, Jane, I take your place now, and you must go lower, because I am a married woman.”  It was not to be supposed that time would give Lydia that embarrassment from which she ha
- Rank 3, `OL66524W__tokens_220__26ddfe20d4330d82`: Gardiner, after general assurances of his affection for her and all her family, told her that he meant to be in London the very next day, and would assist Mr. Bennet in every endeavour for recovering Lydia.  “Do not give way to useless alarm,” added he: “though it is right to be prepared for the worst, there is no occasion to look on it as certain. It is not quite a week since they left Brighton. In a few days more, we may gain some news of them;
G3 diagnostic top passages:

- Rank 1, `OL66524W__tokens_220__ed4650337b0907aa`: Lydia’s going to Brighton was all that consoled her for the melancholy conviction of her husband’s never intending to go there himself.  But they were entirely ignorant of what had passed; and their raptures continued, with little intermission, to the very day of Lydia’s leaving home.  Elizabeth was now to see Mr. Wickham for the last time. Having been frequently in company with him since her return, agitation was pretty well over; the agitations
- Rank 2, `OL66524W__tokens_220__f915ac65851d429c`: She got up and ran out of the room; and returned no more, till she heard them passing through the hall to the dining-parlour. She then joined them soon enough to see Lydia, with anxious parade, walk up to her mother’s right hand, and hear her say to her eldest sister,--  “Ah, Jane, I take your place now, and you must go lower, because I am a married woman.”  It was not to be supposed that time would give Lydia that embarrassment from which she ha
- Rank 3, `OL66524W__tokens_220__afe3a410b9e8065c`: Lydia does not leave me because she is married; but only because her husband’s regiment happens to be so far off. If that had been nearer, she would not have gone so soon.”  But the spiritless condition which this event threw her into was shortly relieved, and her mind opened again to the agitation of hope, by an article of news which then began to be in circulation. The housekeeper at Netherfield had received orders to prepare for the arrival of

### Historical-query diagnostics (not tuning inputs)

| Query | Book | A accepted ranks | G1 accepted ranks | G2 accepted ranks | G3 accepted ranks |
|---|---|---|---|---|---|
| v8_06 | Dracula | [None] | [None] | [32] | [47] |
| v8_08 | Dracula | [46, None] | [None, None] | [15, None] | [44, None] |
| v8_10 | Frankenstein | [23, 13] | [None, None] | [24, 43] | [37, 27] |
| pp_02 | Pride and Prejudice | [17] | [4] | [None] | [29] |
| alice_04 | Alice's Adventures in Wonderland | [2] | [None] | [5] | [2] |
| time_01 | The Time Machine | [44, None] | [23, None] | [None, None] | [34, None] |
| time_02 | The Time Machine | [50] | [None] | [23] | [31] |

All per-query classifications and accepted ranks are in the consolidated JSON and `rag_g3_gooaq_eval.json`. No protected TEST evaluation.

## Safety, added files, and final stop

Before/after verification: `{'production_files': 64, 'production_changed': 0, 'historical_files': 159, 'G1_G2_changed': 0, 'baseline_unchanged': True, 'corpus_labels_sources_unchanged': True}`. Historical recorded G1/G2 model/data/index hashes passed; all frozen historical files have matching before/after SHA-256. No independent older report-hash ledger is claimed. Baseline/corpus/labels/source-map and 18 recorded source hashes unchanged. Production 64-file changes: 0.

**TEST evaluated: NO.** No domain QA, Qwen supervision/training, cross-encoder operation, production promotion, dataset mixture, or subsequent dataset experiment. Only G3 scripts/test and isolated data/cache/model/checkpoint/manifest/index/report paths added.

- `datasets/training/reports/rag_g3_gooaq_final.json`
- `datasets/training/reports/rag_g3_gooaq_final.md`
- `datasets\training\manifests\minilm_g3_gooaq_50k_full.json`
- `datasets\training\manifests\minilm_g3_gooaq_50k_smoke.json`
- `datasets\training\reports\rag_g3_baseline_reproduction.json`
- `datasets\training\reports\rag_g3_baseline_reproduction.log`
- `datasets\training\reports\rag_g3_gooaq_calibration.log`
- `datasets\training\reports\rag_g3_gooaq_calibration_v2.log`
- `datasets\training\reports\rag_g3_gooaq_contract_test.log`
- `datasets\training\reports\rag_g3_gooaq_eval.json`
- `datasets\training\reports\rag_g3_gooaq_eval.log`
- `datasets\training\reports\rag_g3_gooaq_eval.md`
- `datasets\training\reports\rag_g3_gooaq_final.log`
- `datasets\training\reports\rag_g3_gooaq_generic_validation.json`
- `datasets\training\reports\rag_g3_gooaq_generic_validation.log`
- `datasets\training\reports\rag_g3_gooaq_index.log`
- `datasets\training\reports\rag_g3_gooaq_index_integrity.json`
- `datasets\training\reports\rag_g3_gooaq_miner_docstring.txt`
- `datasets\training\reports\rag_g3_gooaq_mining.log`
- `datasets\training\reports\rag_g3_gooaq_preflight.json`
- `datasets\training\reports\rag_g3_gooaq_prepare.log`
- `datasets\training\reports\rag_g3_gooaq_resume_preflight.json`
- `datasets\training\reports\rag_g3_gooaq_smoke.log`
- `datasets\training\reports\rag_g3_gooaq_source_probe.json`
- `datasets\training\reports\rag_g3_gooaq_training.log`
- `scripts\build_rag_g3_index.py`
- `scripts\evaluate_gooaq_g3_validation.py`
- `scripts\evaluate_rag_g3.py`
- `scripts\gooaq_g3_controls.py`
- `scripts\mine_gooaq_hard_negatives_g3.py`
- `scripts\prepare_gooaq_g3.py`
- `scripts\probe_gooaq_g3_source.py`
- `scripts\report_gooaq_g3.py`
- `scripts\train_gooaq_biencoder_g3.py`
- `tests\test_gooaq_g3_training.py`

Isolated generated artifact directories:

- `datasets/training/generic/gooaq_g3`
- `datasets/training/hf_cache/gooaq_g3`
- `datasets/training/models/minilm_g3_gooaq_50k_smoke`
- `datasets/training/models/minilm_g3_gooaq_50k_full`
- `datasets/training/checkpoints/minilm_g3_gooaq_50k_smoke`
- `datasets/training/checkpoints/minilm_g3_gooaq_50k_full`
- `datasets/training/evaluation_indexes/minilm_g3_gooaq_50k`

**FINAL G3 DECISION: B. GOOAQ G3 IS NEUTRAL / INCONCLUSIVE.**

G3 shows mixed Top20/Top50 behavior and does not establish a uniform first-stage retrieval improvement.
Stop after G3. The user reviews this result before any next dataset, mixture, or training experiment.