"""Versioned, conservative initial policies; no fitted recommendation weights."""
RELATION_WEIGHTS = {'author': 2.0, 'subject': 1.0, 'topic': 0.5}
RELATIONS = {'author': ('AUTHORED_BY', 'authors'), 'subject': ('HAS_SUBJECT', 'subjects'),
             'topic': ('HAS_TOPIC', 'description')}
V2_VERSION = 'kg31-description-topics-pilot-v2'
TOPIC_POLICY = {'min_degree': 3, 'maximum_degree_fraction': .001, 'max_topics_per_book': 5,
                'max_description_tokens': 512, 'min_description_tokens': 20,
                'language_policy': 'Unicode source phrases; English stop words plus conservative generic terms. Language unknown, never inferred.'}
