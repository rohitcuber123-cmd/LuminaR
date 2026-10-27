"""Manually authored labels, never derived by calling the parser.

These are agent-curated gold CANDIDATES pending independent review. Generated
metamorphic labels are template assertions, not human-verified accuracy.
"""
import json,random
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'reports'
cases=[]
def family(name,rows):
 for q,expected in rows:
  mode=expected.pop('mode','SMART');sequence=expected.pop('sequence',None)
  defaults={'semantic_text':None,'subjects':[],'author_text':None,'title_text':None,'exact_text':None,
   'rating_min':None,'rating_max':None,'rating_min_exclusive':False,'rating_max_exclusive':False,
   'year_min':None,'year_max':None,'year_min_exclusive':False,'year_max_exclusive':False,
   'formats':[],'exclude_terms':[],'sort':'RELEVANCE','decision_type':'EXECUTABLE'}
  defaults.update(expected)
  cases.append({'id':f'gold-{len(cases)+1:03}','query':q,'mode':mode,'expected':defaults,
   'source_span_expectations':'Every recognized candidate must equal the slice in source_query and have bounded nonnegative offsets; protected literals must not become hard constraints.',
   'support_status':'UNSUPPORTED' if defaults['decision_type']=='UNSUPPORTED' else 'SUPPORTED_OR_EXPLICIT_DECISION',
   'family':name,'sequence':sequence,'review_status':'AGENT_CURATED_PENDING_INDEPENDENT_REVIEW'})
family('rating_comparators',[
 ('fiction books above rating of 3',dict(subjects=['Fiction'],rating_min=3,rating_min_exclusive=True)),
 ('above a rating of 3 fiction books',dict(subjects=['Fiction'],rating_min=3,rating_min_exclusive=True)),
 ('fiction rated more than 3',dict(subjects=['Fiction'],rating_min=3,rating_min_exclusive=True)),
 ('fiction with more than 3 stars',dict(subjects=['Fiction'],rating_min=3,rating_min_exclusive=True)),
 ('science fiction rated at least 4',dict(subjects=['Science fiction'],rating_min=4)),
 ('science fiction rated above 4',dict(subjects=['Science fiction'],rating_min=4,rating_min_exclusive=True)),
 ('minimum rating 3 fiction',dict(subjects=['Fiction'],rating_min=3)),
 ('fiction rating no lower than 3',dict(subjects=['Fiction'],rating_min=3)),
])
family('rating_ranges',[
 ('fiction 3+ stars',dict(subjects=['Fiction'],rating_min=3)),
 ('fiction rated 3 or higher',dict(subjects=['Fiction'],rating_min=3)),
 ('fiction rating below 4',dict(subjects=['Fiction'],rating_max=4,rating_max_exclusive=True)),
 ('fiction less than 4 stars',dict(subjects=['Fiction'],rating_max=4,rating_max_exclusive=True)),
 ('fiction at most 4 stars',dict(subjects=['Fiction'],rating_max=4)),
 ('fiction rating between 3 and 4',dict(subjects=['Fiction'],rating_min=3,rating_max=4)),
 ('fiction rating greater than 3 and less than 5',dict(subjects=['Fiction'],rating_min=3,rating_max=5,rating_min_exclusive=True,rating_max_exclusive=True)),
 ('fiction rating exactly 4',dict(subjects=['Fiction'],rating_min=4,rating_max=4)),
])
family('publication_year',[
 ('fiction published after 2020',dict(subjects=['Fiction'],year_min=2020,year_min_exclusive=True)),
 ('fiction books after the year 2020',dict(subjects=['Fiction'],year_min=2020,year_min_exclusive=True)),
 ('mystery books published since 2015',dict(subjects=['Mystery'],year_min=2015)),
 ('fiction from 2020 onward',dict(subjects=['Fiction'],year_min=2020)),
 ('fiction published before 2000',dict(subjects=['Fiction'],year_max=2000,year_max_exclusive=True)),
 ('fiction published between 1990 and 2005',dict(subjects=['Fiction'],year_min=1990,year_max=2005)),
 ('fiction books released in 2018',dict(subjects=['Fiction'],year_min=2018,year_max=2018)),
 ('fiction books from 2010 to 2020',dict(subjects=['Fiction'],year_min=2010,year_max=2020)),
])
family('history_and_topic_year',[
 ('books about history after 1945',dict(semantic_text='history after 1945')),
 ('history of events after 1945',dict(semantic_text='history of events after 1945')),
 ('history books published after 1945',dict(subjects=['History'],year_min=1945,year_min_exclusive=True)),
 ('books published after 2020 about events in 1945',dict(semantic_text='events in 1945',year_min=2020,year_min_exclusive=True)),
 ('books about the number 4',dict(semantic_text='the number 4')),
 ('books about war in 1945',dict(semantic_text='war in 1945')),
 ('books about events before 2000',dict(semantic_text='events before 2000')),
 ('books published in 2018 about history',dict(semantic_text='history',year_min=2018,year_max=2018)),
])
family('canonical_facets',[
 ('fiction',dict(subjects=['Fiction'])),('fiction books',dict(subjects=['Fiction'])),
 ('science fiction',dict(subjects=['Science fiction'])),('sci fi',dict(subjects=['Science fiction'])),
 ('mystery novels',dict(subjects=['Mystery'])),('books in the Fiction category',dict(subjects=['Fiction'])),
 ('fiction about wizards',dict(subjects=['Fiction'],semantic_text='wizards')),
 ('fiction about dragons with more than 3 stars',dict(subjects=['Fiction'],semantic_text='dragons',rating_min=3,rating_min_exclusive=True)),
])
family('author_vs_subject',[
 ('books by Isaac Asimov',dict(author_text='isaac asimov')),
 ('written by Asimov',dict(author_text='asimov')),
 ('Foundation by Asimov',dict(author_text='asimov',title_text='foundation')),
 ('the book titled Foundation',dict(title_text='foundation')),
 ('books about Isaac Asimov',dict(semantic_text='isaac asimov')),
 ('biographies of Isaac Asimov',dict(semantic_text='biographies of isaac asimov')),
 ('books by Asimov but not Clarke',dict(author_text='asimov',exclude_terms=['clarke'])),
 ('Asimov books',dict(semantic_text='asimov')),
])
family('numeric_titles',[
 ('1984',dict(semantic_text='1984')),('2001: A Space Odyssey',dict(semantic_text='2001: a space odyssey')),
 ('Catch-22',dict(semantic_text='catch-22')),('Dune 2',dict(semantic_text='dune 2')),
 ('Python 3',dict(semantic_text='python 3')),('Windows 11',dict(semantic_text='windows 11')),
 ('The Three-Body Problem',dict(semantic_text='the three-body problem')),
 ('1984 by George Orwell',dict(title_text='1984',author_text='george orwell')),
])
family('format_availability',[
 ('online books',dict(formats=['ONLINE'])),('physical books',dict(formats=['PHYSICAL'])),
 ('books I can read digitally',dict(formats=['ONLINE'])),
 ('physical and online copies of networking books',dict(formats=['BOTH'],semantic_text='networking')),
 ('books with both online and physical copies',dict(formats=['BOTH'])),
 ('available online and physically',dict(formats=['BOTH'])),
 ('online but not physical',dict(formats=['ONLINE'],excluded_formats=['PHYSICAL'])),
 ('books with available copies',dict(availability='AVAILABLE_NOW')),
])
family('negative_scope',[
 ('fiction not romance',dict(subjects=['Fiction'],exclude_terms=['Romance'])),
 ('fiction excluding romance',dict(subjects=['Fiction'],exclude_terms=['Romance'])),
 ('AI but not deep learning',dict(semantic_text='ai',exclude_terms=['deep learning'])),
 ('Java but not JavaScript',dict(semantic_text='java',exclude_terms=['javascript'])),
 ('history without military history',dict(subjects=['History'],exclude_terms=['Military History'])),
 ('not only fiction',dict(semantic_text='not only fiction')),
 ('non-fiction',dict(semantic_text='non-fiction')),
 ('books about the phrase "not fiction"',dict(semantic_text='the phrase not fiction')),
])
family('clause_reordering',[
 ('fiction about wizards above rating of 3',dict(subjects=['Fiction'],semantic_text='wizards',rating_min=3,rating_min_exclusive=True)),
 ('rating above 3 fiction about wizards',dict(subjects=['Fiction'],semantic_text='wizards',rating_min=3,rating_min_exclusive=True)),
 ('fiction online rated above 4',dict(subjects=['Fiction'],formats=['ONLINE'],rating_min=4,rating_min_exclusive=True)),
 ('rated above 4 online fiction',dict(subjects=['Fiction'],formats=['ONLINE'],rating_min=4,rating_min_exclusive=True)),
 ('fiction published after 2020 online',dict(subjects=['Fiction'],formats=['ONLINE'],year_min=2020,year_min_exclusive=True)),
 ('online fiction published after 2020',dict(subjects=['Fiction'],formats=['ONLINE'],year_min=2020,year_min_exclusive=True)),
 ('AI excluding deep learning rated above 4',dict(semantic_text='ai',exclude_terms=['deep learning'],rating_min=4,rating_min_exclusive=True)),
 ('rating above 4 AI excluding deep learning',dict(semantic_text='ai',exclude_terms=['deep learning'],rating_min=4,rating_min_exclusive=True)),
])
family('incomplete',[
 ('fiction rating above',dict(subjects=['Fiction'],decision_type='INCOMPLETE')),
 ('rating above',dict(decision_type='INCOMPLETE')),
 ('fiction rating below',dict(subjects=['Fiction'],decision_type='INCOMPLETE')),
 ('books published after',dict(decision_type='INCOMPLETE')),
 ('books published before',dict(decision_type='INCOMPLETE')),
 ('books written by',dict(decision_type='INCOMPLETE')),
 ('books by',dict(decision_type='INCOMPLETE')),
 ('books under pages',dict(decision_type='INCOMPLETE')),
])
family('contradictions',[
 ('books rated above 4 and below 3',dict(rating_min=4,rating_max=3,rating_min_exclusive=True,rating_max_exclusive=True,decision_type='CONTRADICTORY')),
 ('books rated above 4 and rated below 3',dict(rating_min=4,rating_max=3,rating_min_exclusive=True,rating_max_exclusive=True,decision_type='CONTRADICTORY')),
 ('after 2020 before 2000',dict(year_min=2020,year_max=2000,year_min_exclusive=True,year_max_exclusive=True,decision_type='CONTRADICTORY')),
 ('published after 2020 and before 2000',dict(year_min=2020,year_max=2000,year_min_exclusive=True,year_max_exclusive=True,decision_type='CONTRADICTORY')),
 ('online only and physical only',dict(formats=['ONLINE','PHYSICAL'],decision_type='CONTRADICTORY')),
 ('fiction excluding fiction',dict(subjects=['Fiction'],exclude_terms=['Fiction'],decision_type='CONTRADICTORY')),
 ('include Fiction and exclude Fiction',dict(subjects=['Fiction'],exclude_terms=['Fiction'],decision_type='CONTRADICTORY')),
 ('rated above 4 and rated at most 4',dict(rating_min=4,rating_max=4,rating_min_exclusive=True,decision_type='CONTRADICTORY')),
])
family('ambiguity_and_unsupported',[
 ('fiction 4',dict(subjects=['Fiction'],semantic_text='fiction 4',decision_type='AMBIGUOUS')),
 ('books above 4',dict(semantic_text='above 4',decision_type='AMBIGUOUS')),
 ('operating systems 2',dict(semantic_text='operating systems 2',decision_type='AMBIGUOUS')),
 ('AI 300',dict(semantic_text='ai 300',decision_type='AMBIGUOUS')),
 ('books under 250 pages',dict(decision_type='UNSUPPORTED')),
 ('second edition operating systems',dict(semantic_text='operating systems',decision_type='UNSUPPORTED')),
 ('sort by author',dict(decision_type='UNSUPPORTED')),
 ('oldest first',dict(decision_type='UNSUPPORTED')),
])
family('soft_preferences',[
 ('short mystery books',dict(subjects=['Mystery'],soft_preference='Prefer shorter books')),
 ('short books about climate change',dict(semantic_text='climate change',soft_preference='Prefer shorter books')),
 ('beginner Python books',dict(semantic_text='python',soft_preference='Introductory / beginner (preference)')),
 ('Python 3 for beginners',dict(semantic_text='python 3',soft_preference='Introductory / beginner (preference)')),
 ('advanced networking',dict(semantic_text='networking',soft_preference='Advanced (preference)')),
 ('first-year computer science',dict(semantic_text='computer science',soft_preference='Introductory / beginner (preference)')),
 ('research-level NLP',dict(semantic_text='nlp',soft_preference='Advanced (preference)')),
 ('shorter fiction',dict(subjects=['Fiction'],soft_preference='Prefer shorter books')),
])
family('literal_modes_identifiers',[
 ('C++',dict(semantic_text='c++')),('C#',dict(semantic_text='c#')),
 ('OL19545719W',dict(exact_text='OL19545719W')),
 ('9780131103627',dict(exact_text='9780131103627')),
 ('fiction 4',dict(mode='EXACT',exact_text='fiction 4')),
 ('rating above 4',dict(mode='EXACT',exact_text='rating above 4')),
 ('Foundation',dict(mode='TITLE_AUTHOR',title_text='Foundation')),
 ('Fiction',dict(mode='GENRE_SUBJECT',subjects=['Fiction'])),
])
family('session_refinement',[
 ('online only',dict(sequence=['books about machine learning','online only'],semantic_text='machine learning',formats=['ONLINE'])),
 ('only highly rated',dict(sequence=['books about machine learning','only highly rated'],semantic_text='machine learning',rating_min=4)),
 ('rating above 4',dict(sequence=['books about machine learning','rating above 4'],semantic_text='machine learning',rating_min=4,rating_min_exclusive=True)),
 ('after 2020',dict(sequence=['books about machine learning','after 2020'],semantic_text='machine learning',year_min=2020,year_min_exclusive=True)),
 ('something different',dict(sequence=['books about machine learning','something different'])),
 ('ancient history',dict(sequence=['books about machine learning','online only','ancient history'],subjects=['Ancient History'])),
 ('show me operating systems instead',dict(sequence=['books about machine learning','online only','show me operating systems instead'],semantic_text='operating systems',formats=['ONLINE'])),
 ('physical instead',dict(sequence=['books about machine learning','online only','physical instead'],semantic_text='machine learning',formats=['PHYSICAL'])),
])
family('typos_and_conservative_identity',[
 ('fictin',dict(subjects=['Fiction'])),
 ('histroy',dict(subjects=['History'])),
 ('biograpy',dict(subjects=['Biography'])),
 ('science fictin',dict(subjects=['Science fiction'])),
 ('tolkein',dict(semantic_text='tolkein')),
 ('xylophonetransport',dict(semantic_text='xylophonetransport')),
 ('fictin',dict(mode='EXACT',exact_text='fictin')),
 ('tolkein',dict(mode='TITLE_AUTHOR',title_text='tolkein')),
])
assert len(cases)==136
(R/'search_v2c_a_gold_queries.jsonl').write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in cases),encoding='utf8')
rng=random.Random(20261015);variants=[]
forms=[('rating above 3',dict(rating_min=3,rating_min_exclusive=True)),('above a rating of 3',dict(rating_min=3,rating_min_exclusive=True)),
 ('rated at least 4',dict(rating_min=4)),('less than 4 stars',dict(rating_max=4,rating_max_exclusive=True)),
 ('rating between 3 and 4',dict(rating_min=3,rating_max=4)),('published after 2020',dict(year_min=2020,year_min_exclusive=True)),
 ('published since 2020',dict(year_min=2020)),('published before 2000',dict(year_max=2000,year_max_exclusive=True))]
import itertools
pool=[]
for fi,(form,expected) in enumerate(forms):
 for subject,topic,fmt in itertools.product(['Fiction','Science fiction','History'],['wizards','dragons','climate change','ocean research','archive preservation'],['ONLINE','PHYSICAL']):
  for parts in itertools.permutations([subject+' books about '+topic,form,fmt.lower()]):pool.append((parts,fi,subject,topic,fmt,expected))
rng.shuffle(pool)
for i,(parts,fi,subject,topic,fmt,expected) in enumerate(pool[:1000]):
 q=('  ' if i%2 else ' ').join(parts)
 if i%5==0:q=q.upper()
 variants.append({'id':f'meta-{i:04}','query':q,'mode':'SMART','family':'seeded_constraint_order_case_whitespace',
 'seed':20261015,'template_id':fi,'expected':{'subjects':[subject],'semantic_text':topic,'formats':[fmt],'decision_type':'EXECUTABLE',**expected},
 'review_status':'GENERATED_TEMPLATE_ASSERTION_NOT_HUMAN_VERIFIED'})
(R/'search_v2c_a_metamorphic_queries.jsonl').write_text(''.join(json.dumps(c)+'\n' for c in variants),encoding='utf8')
assert len(set(c['query'].casefold().split().__str__() for c in variants))==1000
print(json.dumps({'manually_authored_candidates':len(cases),'families':len(set(c['family'] for c in cases)),'seeded_variants':len(variants),'independent_review':'PENDING'}))
