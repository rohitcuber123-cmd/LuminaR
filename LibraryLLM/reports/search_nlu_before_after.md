# Old versus new Search

Old entries below are actual pre-change HTTP responses, not reconstructed rankings. New entries are live responses and canonical plans.

## fiction

Old top titles: Fiction is folks, Fiction, The philosophy of fiction in literature
New top titles: Who is Bugs Potter?, The prince she never knew, 靈山 = Ling shan
New plan: `{"raw_query": "fiction", "mode": "SMART", "semantic_text": null, "title_text": null, "author_text": null, "subjects": ["Fiction"], "rating_min": null, "rating_max": null, "rating_min_exclusive": false, "rating_max_exclusive": false, "year_min": null, "year_max": null, "year_min_exclusive": false, "year_max_exclusive": false, "formats": [], "availability": null, "language": null, "exact_text": null, "sort": "RELEVANCE", "interpretation_confidence": 1.0, "corrections": [], "unknown_subject": false, "suggested_subject": null}`
Canonical filter violations: 0

## detectve

Old top titles: Signal detection and recognition by human observers, Detection theory, Detection Theory
New top titles: Death of a Stranger (A William Monk Mystery), Blacklist, The dying detective
New plan: `{"raw_query": "detectve", "mode": "SMART", "semantic_text": null, "title_text": null, "author_text": null, "subjects": ["Detective and mystery stories"], "rating_min": null, "rating_max": null, "rating_min_exclusive": false, "rating_max_exclusive": false, "year_min": null, "year_max": null, "year_min_exclusive": false, "year_max_exclusive": false, "formats": [], "availability": null, "language": null, "exact_text": null, "sort": "RELEVANCE", "interpretation_confidence": 0.9411764705882353, "corrections": [{"from": "detectve", "to": "Detective and mystery stories", "kind": "typo"}], "unknown_subject": false, "suggested_subject": null}`
Canonical filter violations: 0

## books about wizards

Old top titles: A book of wizards, Wizards (Story Books), The Book of Wizards
New top titles: Wizards (Story Books), WIZARDS: A HISTORY, A Guide to Wizards of the World - Being a True Account of Wizards in the Known World
New plan: `{"raw_query": "books about wizards", "mode": "SMART", "semantic_text": "wizards", "title_text": null, "author_text": null, "subjects": [], "rating_min": null, "rating_max": null, "rating_min_exclusive": false, "rating_max_exclusive": false, "year_min": null, "year_max": null, "year_min_exclusive": false, "year_max_exclusive": false, "formats": [], "availability": null, "language": null, "exact_text": null, "sort": "RELEVANCE", "interpretation_confidence": 1.0, "corrections": [], "unknown_subject": false, "suggested_subject": null}`
Canonical filter violations: 0

## books about wizards with rating above 4

Old top titles: The Young Wizards, Books 1-5, A book of wizards, Wizards (Story Books)
New top titles: The crusading wizard, Wizards at War, Her Majesty's wizard
New plan: `{"raw_query": "books about wizards with rating above 4", "mode": "SMART", "semantic_text": "wizards", "title_text": null, "author_text": null, "subjects": [], "rating_min": 4.0, "rating_max": null, "rating_min_exclusive": true, "rating_max_exclusive": false, "year_min": null, "year_max": null, "year_min_exclusive": false, "year_max_exclusive": false, "formats": [], "availability": null, "language": null, "exact_text": null, "sort": "RELEVANCE", "interpretation_confidence": 1.0, "corrections": [], "unknown_subject": false, "suggested_subject": null}`
Canonical filter violations: 0

## online books about robotics

Old top titles: A robot engineering textbook, Robotics and Automation Handbook, Robotics
New top titles: No compliant results
New plan: `{"raw_query": "online books about robotics", "mode": "SMART", "semantic_text": "robotics", "title_text": null, "author_text": null, "subjects": [], "rating_min": null, "rating_max": null, "rating_min_exclusive": false, "rating_max_exclusive": false, "year_min": null, "year_max": null, "year_min_exclusive": false, "year_max_exclusive": false, "formats": ["ONLINE"], "availability": null, "language": null, "exact_text": null, "sort": "RELEVANCE", "interpretation_confidence": 1.0, "corrections": [], "unknown_subject": false, "suggested_subject": null}`
Canonical filter violations: 0

Fiction now requires canonical classification, and detective typos use the known facet rather than detection-theory titles. Topic-only searches retain semantic retrieval. Rating and Online requests exclude noncompliant results, including empty results instead of unrelated filler.
