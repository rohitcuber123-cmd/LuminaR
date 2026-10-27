"""Independent, output-blind V2C-C canonical benchmark authorship.

Every query below was individually written by the independent author. Shared
defaults are schema conveniences, not query generation. No parser, prior gold,
or evaluator module is imported. Normative labels come from the user contract
and the supplied authorized vocabulary/capability snapshot only.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOCAB = json.loads((ROOT / 'reports/search_v2c_c_scope_vocabularies.json').read_text(encoding='utf-8'))
CASES = []
FAMILIES = []
G='GLOBAL'; P='PUBLIC_PATRON'; S='PUBLIC_STAFF'; V='PRIVATE_PATRON'; W='PRIVATE_STAFF'

def c(query, semantic='', **kw):
    """An individually authored utterance and explicit normative overrides."""
    return (query, semantic, kw)

def family(name, split, tags, scope, rows):
    assert len(rows) == 10, (name, len(rows))
    FAMILIES.append({'family_id':name,'split':split,'coverage_tags':tags,
                     'canonical_count':len(rows),'structural_isolation':True})
    for i,(query,semantic,kw) in enumerate(rows,1):
        row = dict(query_id=f'v2cc-authored-{name}-{i:02}',query=query,
            family_id=name,split=split,scope_type=scope,search_mode='semantic',category='canonical',
            expected_decision='EXECUTABLE',expected_intent='DISCOVER_TOPIC',
            expected_subjects=[],expected_excluded_subjects=[],expected_exclude_terms=[],
            expected_author=None,expected_title_entity=None,expected_exact_text=None,
            expected_rating_min=None,rating_min_exclusive=False,
            expected_rating_max=None,rating_max_exclusive=False,
            expected_year_min=None,year_min_exclusive=False,
            expected_year_max=None,year_max_exclusive=False,
            expected_format=[],expected_exclusive_formats=[],expected_excluded_formats=[],
            expected_availability=None,expected_sort=None,expected_semantic_text=semantic,
            expected_soft_preferences=[],expected_unsupported_fields=[],expected_ambiguous_spans=[],
            expected_incomplete_fields=[],expected_contradiction_fields=[],protected_spans=[],
            execution_allowed=True,notes='Independently authored normative label; no parser output consulted.',
            review_source='authored',authored_by='independent AI agent; no parser outputs',
            review_provenance='AI self-reviewed by independent author; no second separate reviewer; no human review')
        alias={'subjects':'expected_subjects','excluded':'expected_excluded_subjects',
               'exclude_terms':'expected_exclude_terms','author':'expected_author',
               'title':'expected_title_entity','exact':'expected_exact_text',
               'rmin':'expected_rating_min','rmax':'expected_rating_max',
               'rminx':'rating_min_exclusive','rmaxx':'rating_max_exclusive',
               'ymin':'expected_year_min','ymax':'expected_year_max',
               'yminx':'year_min_exclusive','ymaxx':'year_max_exclusive',
               'fmt':'expected_format','exclusive':'expected_exclusive_formats',
               'exfmt':'expected_excluded_formats','availability':'expected_availability',
               'sort':'expected_sort','soft':'expected_soft_preferences',
               'unsupported':'expected_unsupported_fields','ambiguous':'expected_ambiguous_spans',
               'incomplete':'expected_incomplete_fields','contradiction':'expected_contradiction_fields',
               'decision':'expected_decision','intent':'expected_intent','scope':'scope_type','mode':'search_mode'}
        protect=kw.pop('protect',[])
        for key,val in kw.items(): row[alias.get(key,key)]=val
        for literal in protect:
            start=query.index(literal)
            row['protected_spans'].append({'start':start,'end':start+len(literal),'text':literal})
        if row['expected_decision'] not in ('EXECUTABLE','EXECUTABLE_WITH_NOTICE'):
            row['execution_allowed']=False
        elif row['expected_subjects'] and not semantic:
            row['expected_intent']='BROWSE_CATEGORY'
        if row['expected_author'] and not kw.get('intent'):
            row['expected_intent']='FIND_AUTHOR'
        if row['expected_exact_text'] is not None:
            row['expected_intent']='FIND_EXACT'
        CASES.append(row)

# DEVELOPMENT: direct constructions. All textual rows are individually written.
family('d01_explicit_rating', 'development', [1,3,11], G, [
 c('fiction books above rating of 3',subjects=['Fiction'],rmin=3,rminx=True),
 c('fiction about wizards above rating of 3','wizards',subjects=['Fiction'],rmin=3,rminx=True),
 c('history rated above 4',subjects=['History'],rmin=4,rminx=True),
 c('books rated below 2 about old maps','old maps',rmax=2,rmaxx=True),
 c('a rating of at least 4 for astronomy',subjects=['Astronomy'],rmin=4),
 c('poetry rated at most 3.5',subjects=['Poetry'],rmax=3.5),
 c('rating greater than 4.2 on books about coral','coral',rmin=4.2,rminx=True),
 c('show travel guides with rating less than 3', 'travel guides',rmax=3,rmaxx=True),
 c('mystery books with rating equal to 4',subjects=['Mystery'],rmin=4,rmax=4),
 c('rating no lower than 2.5 for books on weaving','weaving',rmin=2.5),
])
family('d02_postfix_rating', 'development', [1,3], G, [
 c('AI excluding deep learning rated 4+','AI',exclude_terms=['deep learning'],rmin=4),
 c('science fiction rated 3+',subjects=['Science fiction'],rmin=3),
 c('books about beekeeping, rating >= 4','beekeeping',rmin=4),
 c('Fiction; rating > 3.5',subjects=['Fiction'],rmin=3.5,rminx=True),
 c('subject History, rating <= 2',subjects=['History'],rmax=2),
 c('poetry with rating < 4.5',subjects=['Poetry'],rmax=4.5,rmaxx=True),
 c('ceramic glazing rating=4','ceramic glazing',rmin=4,rmax=4),
 c('4+ rated Romance',subjects=['Romance'],rmin=4),
 c('books about amateur radio rated 0+','amateur radio',rmin=0),
 c('architecture rating >= 4.75',subjects=['Architecture'],rmin=4.75),
])
family('d03_publication_direct', 'development', [2,29], P, [
 c('history books published after 2020',subjects=['History'],ymin=2020,yminx=True),
 c('computer science published before 2010',subjects=['Computer science'],ymax=2010,ymaxx=True),
 c('books published in 2021 about renewable heating','renewable heating',ymin=2021,ymax=2021),
 c('publication year at least 2018 for cloud services','cloud services',ymin=2018),
 c('books on ocean currents published no later than 1999','ocean currents',ymax=1999),
 c('fiction published from 2015 to 2020',subjects=['Fiction'],ymin=2015,ymax=2020),
 c('published after 2001, books on irrigation','irrigation',ymin=2001,yminx=True),
 c('history with publication year under 1980',subjects=['History'],ymax=1980,ymaxx=True),
 c('published at or after 2019 about satellites','satellites',ymin=2019),
 c('books from publication year 2004 about harbours','harbours',ymin=2004,ymax=2004),
])
family('d04_canonical_subject', 'development', [3,25], G, [
 c('include Fiction',subjects=['Fiction']),
 c('subject Romance',subjects=['Romance']),
 c('genre Mystery',subjects=['Mystery']),
 c('browse History',subjects=['History']),
 c('science fiction books',subjects=['Science fiction']),
 c('books in Philosophy',subjects=['Philosophy']),
 c('only the Poetry subject',subjects=['Poetry']),
 c('category Architecture',subjects=['Architecture']),
 c('a book in the Astronomy subject',subjects=['Astronomy']),
 c('show Mathematics books',subjects=['Mathematics']),
])
family('d05_by_vs_about', 'development', [4,31], G, [
 c('books by Ursula K. Le Guin',author='Ursula K. Le Guin'),
 c('books about Ursula K. Le Guin','Ursula K. Le Guin'),
 c('fiction by George Orwell',subjects=['Fiction'],author='George Orwell'),
 c('books on the ideas of George Orwell','ideas of George Orwell'),
 c('poetry written by Emily Dickinson',subjects=['Poetry'],author='Emily Dickinson'),
 c('about the poetry of Emily Dickinson','poetry of Emily Dickinson'),
 c('books authored by Octavia Butler',author='Octavia Butler'),
 c('biographies about Octavia Butler','biographies about Octavia Butler'),
 c('by Terry Pratchett about witches','witches',author='Terry Pratchett'),
 c('study the influence of Terry Pratchett','influence of Terry Pratchett'),
])
family('d06_numeric_titles', 'development', [5,28,29], G, [
 c('1984','1984',title='1984',protect=['1984']),
 c('1984 by George Orwell','1984',author='George Orwell',title='1984',protect=['1984']),
 c('Catch-22','Catch-22',title='Catch-22',protect=['Catch-22']),
 c('Dune 2','Dune 2',title='Dune 2',protect=['Dune 2']),
 c('The Three-Body Problem','The Three-Body Problem',title='The Three-Body Problem',protect=['The Three-Body Problem']),
 c('Fahrenheit 451','Fahrenheit 451',title='Fahrenheit 451',protect=['Fahrenheit 451']),
 c('Around the World in 80 Days','Around the World in 80 Days',title='Around the World in 80 Days',protect=['Around the World in 80 Days']),
 c('The 39 Steps','The 39 Steps',title='The 39 Steps',protect=['The 39 Steps']),
 c('2001: A Space Odyssey','2001: A Space Odyssey',title='2001: A Space Odyssey',protect=['2001: A Space Odyssey']),
 c('Slaughterhouse-Five','Slaughterhouse-Five',title='Slaughterhouse-Five',protect=['Slaughterhouse-Five']),
])
family('d07_technical_literals', 'development', [6,28], G, [
 c('Python 3','Python 3',protect=['Python 3']),
 c('C++','C++',protect=['C++']),
 c('C#','C#',protect=['C#']),
 c('Windows 11','Windows 11',protect=['Windows 11']),
 c('TCP/IP','TCP/IP',protect=['TCP/IP']),
 c('.NET 8',' .NET 8'.strip(),protect=['.NET 8']),
 c('ISO 9001','ISO 9001',protect=['ISO 9001']),
 c('802.11ax wireless','802.11ax wireless',protect=['802.11ax']),
 c('Node.js 20','Node.js 20',protect=['Node.js 20']),
 c('HTTP/2 programming','HTTP/2 programming',protect=['HTTP/2']),
])
family('d08_format_direct', 'development', [7,32], V, [
 c('online detective fiction but not romance',subjects=['Detective Fiction'],excluded=['Romance'],fmt=['ONLINE']),
 c('physical only mystery books',subjects=['Mystery'],fmt=['PHYSICAL'],exclusive=['PHYSICAL']),
 c('online only Romance',subjects=['Romance'],fmt=['ONLINE'],exclusive=['ONLINE']),
 c('Fiction in online format',subjects=['Fiction'],fmt=['ONLINE']),
 c('Neural Networks in physical format',subjects=['Neural Networks'],fmt=['PHYSICAL']),
 c('physical books about wizards','wizards',fmt=['PHYSICAL']),
 c('show online titles on memory','memory',fmt=['ONLINE']),
 c('Mystery with an online version',subjects=['Mystery'],fmt=['ONLINE']),
 c('a physical copy about rivers','rivers',fmt=['PHYSICAL']),
 c('Fiction available digitally',subjects=['Fiction'],fmt=['ONLINE']),
])
family('d09_availability_now', 'development', [8], P, [
 c('books available now about network routing','network routing',availability='AVAILABLE_NOW'),
 c('available now in Fiction',subjects=['Fiction'],availability='AVAILABLE_NOW'),
 c('only books currently available on Java',subjects=['Java'],availability='AVAILABLE_NOW'),
 c('show available books about trams','trams',availability='AVAILABLE_NOW'),
 c('computer science, available now',subjects=['Computer science'],availability='AVAILABLE_NOW'),
 c('available physical books about aviation','aviation',fmt=['PHYSICAL'],availability='AVAILABLE_NOW'),
 c('online and available now about bridges','bridges',fmt=['ONLINE'],availability='AVAILABLE_NOW'),
 c('history available for borrowing now',subjects=['History'],availability='AVAILABLE_NOW'),
 c('find an available copy on canoe building','canoe building',availability='AVAILABLE_NOW'),
 c('books I can borrow now about marine engines','marine engines',availability='AVAILABLE_NOW'),
])
family('d10_include_exclude', 'development', [9,10], V, [
 c('include Fiction but exclude Romance',subjects=['Fiction'],excluded=['Romance']),
 c('include Mystery and exclude Romance',subjects=['Mystery'],excluded=['Romance']),
 c('include Neural Networks but exclude Fiction',subjects=['Neural Networks'],excluded=['Fiction']),
 c('include Fiction and Wizards; exclude Mystery',subjects=['Fiction','Wizards'],excluded=['Mystery']),
 c('include Romance, exclude Detective Fiction',subjects=['Romance'],excluded=['Detective Fiction']),
 c('exclude Romance; include Fiction',subjects=['Fiction'],excluded=['Romance']),
 c('books about Java not JavaScript','Java',exclude_terms=['JavaScript']),
 c('Java but not JavaScript','Java',exclude_terms=['JavaScript']),
 c('include Wizards but exclude Romance and Mystery',subjects=['Wizards'],excluded=['Romance','Mystery']),
 c('Neural Networks excluding deep learning','',subjects=['Neural Networks'],exclude_terms=['deep learning']),
])
family('d11_negation_scope', 'development', [10,9,20], G, [
 c('not only Romance','Romance',notes='Not-only construction is additive emphasis, not a subject exclusion.'),
 c('non-fiction','non-fiction',protect=['non-fiction']),
 c('books about not giving up','not giving up',protect=['not giving up']),
 c('fiction, not romance',subjects=['Fiction'],excluded=['Romance']),
 c('books about forests but not logging','forests',exclude_terms=['logging']),
 c('not the subject History','',excluded=['History']),
 c('exclude the phrase "not bad" from reviews','reviews',exclude_terms=['not bad'],protect=['not bad']),
 c('books about non-linear systems','non-linear systems',protect=['non-linear']),
 c('books about the word not','word not',protect=['not']),
 c('not only fiction but poetry too','fiction poetry',notes='An additive not-only construction must not become an exclusion; conjunction preserved semantically.'),
])
family('d12_multi_reordering', 'development', [11,18], V, [
 c('rated above 4, online Fiction about wizards','wizards',subjects=['Fiction'],fmt=['ONLINE'],rmin=4,rminx=True),
 c('exclude Romance; after publication year 2020; include Fiction',subjects=['Fiction'],excluded=['Romance'],ymin=2020,yminx=True),
 c('physical only, Mystery, rated below 4',subjects=['Mystery'],fmt=['PHYSICAL'],exclusive=['PHYSICAL'],rmax=4,rmaxx=True),
 c('Neural Networks available now rated at least 3',subjects=['Neural Networks'],availability='AVAILABLE_NOW',rmin=3),
 c('before 2018 in publication year, online books on bridges','bridges',ymax=2018,ymaxx=True,fmt=['ONLINE']),
 c('by Synthetic A1 Author, include Wizards, rating above 3',author='Synthetic A1 Author',subjects=['Wizards'],rmin=3,rminx=True),
 c('include Fiction, rating at most 4.5, exclude Romance',subjects=['Fiction'],excluded=['Romance'],rmax=4.5),
 c('about waterways, physical books published in 2021','waterways',fmt=['PHYSICAL'],ymin=2021,ymax=2021),
 c('online only; include Mystery; available now',subjects=['Mystery'],fmt=['ONLINE'],exclusive=['ONLINE'],availability='AVAILABLE_NOW'),
 c('rated 4+ about wizards, exclude Romance, Fiction','wizards',rmin=4,excluded=['Romance'],subjects=['Fiction']),
])
family('d13_rating_contradictions', 'development', [12,1], G, [
 c('rated above 4 and rated below 3',decision='CONTRADICTORY',rmin=4,rminx=True,rmax=3,rmaxx=True,contradiction=['rating']),
 c('Fiction rated at least 4 and at most 2',subjects=['Fiction'],rmin=4,rmax=2,decision='CONTRADICTORY',contradiction=['rating']),
 c('rating greater than 3 and rating at most 3',rmin=3,rminx=True,rmax=3,decision='CONTRADICTORY',contradiction=['rating']),
 c('rating below 2 and rating at least 2',rmin=2,rmax=2,rmaxx=True,decision='CONTRADICTORY',contradiction=['rating']),
 c('rated above 5',rmin=5,rminx=True,decision='CONTRADICTORY',contradiction=['rating'],notes='Rating scale upper bound is five; no eligible rating can be strictly greater.'),
 c('rating below 0',rmax=0,rmaxx=True,decision='CONTRADICTORY',contradiction=['rating']),
 c('rating at least 4.5 but below 4.5',rmin=4.5,rmax=4.5,rmaxx=True,decision='CONTRADICTORY',contradiction=['rating']),
 c('rating exactly 3 and rating above 3',rmin=3,rminx=True,rmax=3,decision='CONTRADICTORY',contradiction=['rating']),
 c('rating no more than 1 and no less than 4',rmin=4,rmax=1,decision='CONTRADICTORY',contradiction=['rating']),
 c('rating >= 4 and rating < 2',rmin=4,rmax=2,rmaxx=True,decision='CONTRADICTORY',contradiction=['rating']),
])
family('d14_incomplete_direct', 'development', [13,36], G, [
 c('rating above',decision='INCOMPLETE',incomplete=['rating']),
 c('published after',decision='INCOMPLETE',incomplete=['year']),
 c('books by',decision='INCOMPLETE',incomplete=['author']),
 c('not',decision='INCOMPLETE',incomplete=['exclusion']),
 c('include',decision='INCOMPLETE',incomplete=['subject']),
 c('exclude subject',decision='INCOMPLETE',incomplete=['excluded_subject']),
 c('rating between 3 and',rmin=3,decision='INCOMPLETE',incomplete=['rating_max']),
 c('books titled',decision='INCOMPLETE',incomplete=['title']),
 c('publication year before',decision='INCOMPLETE',incomplete=['year']),
 c('only',decision='INCOMPLETE',incomplete=['format_or_subject']),
])
family('d15_unsupported_metadata', 'development', [14,30], G, [
 c('mystery under 250 pages',subjects=['Mystery'],decision='UNSUPPORTED',unsupported=['page_count']),
 c('second edition networking books','networking',decision='UNSUPPORTED',unsupported=['edition']),
 c('history books published after 2020',subjects=['History'],decision='UNSUPPORTED',unsupported=['year']),
 c('only books in French about vineyards','vineyards',decision='UNSUPPORTED',unsupported=['language']),
 c('books available now on astronomy',subjects=['Astronomy'],decision='UNSUPPORTED',unsupported=['availability']),
 c('physical only books about radio','radio',decision='UNSUPPORTED',unsupported=['format']),
 c('books with both online and physical versions',decision='UNSUPPORTED',unsupported=['format']),
 c('first edition poetry',subjects=['Poetry'],decision='UNSUPPORTED',unsupported=['edition']),
 c('hardcover binding only on chess','chess',decision='UNSUPPORTED',unsupported=['binding']),
 c('books costing under 20 dollars about pottery','pottery',decision='UNSUPPORTED',unsupported=['price']),
])
family('d16_soft_preferences', 'development', [15], G, [
 c('short mystery books',subjects=['Mystery'],soft=['short'],decision='EXECUTABLE_WITH_NOTICE'),
 c('beginner Python','Python',soft=['beginner'],decision='EXECUTABLE_WITH_NOTICE',intent='LEARN'),
 c('advanced networking','networking',soft=['advanced'],decision='EXECUTABLE_WITH_NOTICE'),
 c('first-year computer science',subjects=['Computer science'],soft=['first-year'],decision='EXECUTABLE_WITH_NOTICE',intent='LEARN'),
 c('research-level NLP','NLP',soft=['research-level'],decision='EXECUTABLE_WITH_NOTICE',intent='RESEARCH'),
 c('easy books on paper folding','paper folding',soft=['easy'],decision='EXECUTABLE_WITH_NOTICE'),
 c('a concise history overview',subjects=['History'],soft=['concise','overview'],decision='EXECUTABLE_WITH_NOTICE'),
 c('gentle introduction to relativity','relativity',soft=['gentle introduction'],decision='EXECUTABLE_WITH_NOTICE',intent='LEARN'),
 c('comprehensive books about horticulture','horticulture',soft=['comprehensive'],decision='EXECUTABLE_WITH_NOTICE'),
 c('prefer recent books on astronomy',subjects=['Astronomy'],soft=['recent'],decision='EXECUTABLE_WITH_NOTICE'),
])
family('d17_typographical_noise', 'development', [16,35], G, [
 c('scince fiction','scince fiction',decision='EXECUTABLE_WITH_NOTICE',notes='A typo candidate may be offered; original text executes without silently replacing it with a strict subject.'),
 c('histroy books','histroy',decision='EXECUTABLE_WITH_NOTICE'),
 c('mystrey stories','mystrey stories',decision='EXECUTABLE_WITH_NOTICE'),
 c('romnace','romnace',decision='EXECUTABLE_WITH_NOTICE'),
 c('artifical intelligence','artifical intelligence',decision='EXECUTABLE_WITH_NOTICE'),
 c('astronmy for amateurs','astronmy for amateurs',decision='EXECUTABLE_WITH_NOTICE'),
 c('philosphy about ethics','philosphy about ethics',decision='EXECUTABLE_WITH_NOTICE'),
 c('netwroking protocols','netwroking protocols',decision='EXECUTABLE_WITH_NOTICE'),
 c('ficiton about islands','ficiton about islands',decision='EXECUTABLE_WITH_NOTICE'),
 c('archtecture of bridges','archtecture of bridges',decision='EXECUTABLE_WITH_NOTICE'),
])
family('d18_morphological_forms', 'development', [17], G, [
 c('histories of small towns','histories of small towns'),
 c('fictional accounts of explorers','fictional accounts of explorers'),
 c('romantic poetry','romantic poetry'),
 c('mathematical puzzles','mathematical puzzles'),
 c('philosophical thinking','philosophical thinking'),
 c('astronomical observations','astronomical observations'),
 c('architectural sketches','architectural sketches'),
 c('scientific explanations of rainbows','scientific explanations of rainbows'),
 c('biographical writing','biographical writing'),
 c('educational psychology resources','educational psychology resources'),
])
family('d19_word_order', 'development', [18,11], G, [
 c('about ocean navigation books','ocean navigation'),
 c('books, about mountain weather','mountain weather'),
 c('on old railway stations, books','old railway stations'),
 c('for sourdough baking I need books','sourdough baking'),
 c('bird migration is what I want to read about','bird migration'),
 c('books please on clock repair','clock repair'),
 c('on soil health find books','soil health'),
 c('something about bridge maintenance to read','bridge maintenance'),
 c('give books, the topic is ocean tides','ocean tides'),
 c('what can I read on bicycle gears','bicycle gears'),
])
family('d20_optional_filler', 'development', [19], G, [
 c('please find me books about urban beekeeping','urban beekeeping'),
 c('could you show me Fiction books',subjects=['Fiction']),
 c('I would like some books about sand dunes','sand dunes'),
 c('can I see books about hand weaving please','hand weaving'),
 c('I am looking for Poetry',subjects=['Poetry']),
 c('please help me find books on satellite orbits','satellite orbits'),
 c('would you mind showing books on timber joints','timber joints'),
 c('I need a book about ceramic kilns','ceramic kilns'),
 c('show me something to read about gliders','gliders'),
 c('I want books concerning tidal energy','tidal energy'),
])
family('d21_quoted_literals', 'development', [20,5,9], G, [
 c('books titled "Include Romance but Exclude Romance"',exact='Include Romance but Exclude Romance',title='Include Romance but Exclude Romance',protect=['Include Romance but Exclude Romance']),
 c('fiction "4"','4',subjects=['Fiction'],protect=['4']),
 c('books about "rated above 4"','rated above 4',protect=['rated above 4']),
 c('"published after 2020"','published after 2020',protect=['published after 2020']),
 c('books titled "Online Only"',exact='Online Only',title='Online Only',protect=['Online Only']),
 c('about "not Romance"','not Romance',protect=['not Romance']),
 c('"physical only and online only"','physical only and online only',protect=['physical only and online only']),
 c('books titled "Second Edition"',exact='Second Edition',title='Second Edition',protect=['Second Edition']),
 c('"rating above"','rating above',protect=['rating above']),
 c('Fiction about "Java but not JavaScript"','Java but not JavaScript',subjects=['Fiction'],protect=['Java but not JavaScript']),
])
family('d22_isbn_like', 'development', [21,6], G, [
 c('9780141036144','9780141036144',protect=['9780141036144']),
 c('ISBN 978-0-14-103614-4','ISBN 978-0-14-103614-4',protect=['978-0-14-103614-4']),
 c('0-451-52493-4','0-451-52493-4',protect=['0-451-52493-4']),
 c('find 9780307277671','9780307277671',protect=['9780307277671']),
 c('ISBN-10 014118776X','ISBN-10 014118776X',protect=['014118776X']),
 c('978-1-59327-928-8 Python','978-1-59327-928-8 Python',protect=['978-1-59327-928-8']),
 c('book identifier 9780201616224','book identifier 9780201616224',protect=['9780201616224']),
 c('ISBN 978 0 7432 7356 5','ISBN 978 0 7432 7356 5',protect=['978 0 7432 7356 5']),
 c('the text 123-4-567-89012-3','text 123-4-567-89012-3',protect=['123-4-567-89012-3']),
 c('ISBN: 9780000000002','ISBN: 9780000000002',protect=['9780000000002']),
])
family('d23_exact_mode', 'development', [22,20,28], G, [
 c('fiction rated above 4',mode='exact',exact='fiction rated above 4',protect=['fiction rated above 4']),
 c('1984 by George Orwell',mode='exact',exact='1984 by George Orwell',protect=['1984 by George Orwell']),
 c('published after 2020',mode='exact',exact='published after 2020',protect=['published after 2020']),
 c('include Fiction but exclude Fiction',mode='exact',exact='include Fiction but exclude Fiction',protect=['include Fiction but exclude Fiction']),
 c('online only and physical only',mode='exact',exact='online only and physical only',protect=['online only and physical only']),
 c('rating above',mode='exact',exact='rating above',protect=['rating above']),
 c('mystery under 250 pages',mode='exact',exact='mystery under 250 pages',protect=['mystery under 250 pages']),
 c('C++ 20',mode='exact',exact='C++ 20',protect=['C++ 20']),
 c('books by',mode='exact',exact='books by',protect=['books by']),
 c('978-0-14-103614-4',mode='exact',exact='978-0-14-103614-4',protect=['978-0-14-103614-4']),
])
family('d24_refinement_turns', 'development', [23], P, [
 c('only online',fmt=['ONLINE'],exclusive=['ONLINE'],notes='Standalone refinement label; sequence evaluator additionally preserves accepted topic.'),
 c('after 2020',ymin=2020,yminx=True,notes='Explicit temporal refinement on accepted search; initial-turn ambiguity differs.'),
 c('above 4',rmin=4,rminx=True,notes='Comparator refinement after accepted search; preserve topic.'),
 c('exclude cybersecurity',exclude_terms=['cybersecurity'],notes='Excluded free-text topic; PUBLIC lacks exact cybersecurity subject in supplied snapshot.'),
 c('rated at least 3.5',rmin=3.5),
 c('physical only',fmt=['PHYSICAL'],exclusive=['PHYSICAL']),
 c('available now',availability='AVAILABLE_NOW'),
 c('by Ada Lovelace',author='Ada Lovelace'),
 c('published before 2016',ymax=2016,ymaxx=True),
 c('exclude Java',excluded=['Java']),
])
family('d25_instead_turns', 'development', [24,23], P, [
 c('instead networking','networking',notes='Topic replacement in a session; prior explicit filters remain unless separately edited.'),
 c('instead books about sailing','sailing'),
 c('instead History',subjects=['History']),
 c('instead include Fiction',subjects=['Fiction']),
 c('instead about robotics','robotics'),
 c('instead Java',subjects=['Java']),
 c('instead books on water purification','water purification'),
 c('instead Computer science',subjects=['Computer science']),
 c('instead read about pottery','pottery'),
 c('instead of that, search for volcanoes','volcanoes'),
])
family('d26_public_vocab', 'development', [25,27], P, [
 c('include Java',subjects=['Java']),
 c('include Romance',decision='UNSUPPORTED',unsupported=['subject'],notes='PUBLIC has Romance fiction but not canonical Romance; no Global facet import.'),
 c('include Wizards',decision='UNSUPPORTED',unsupported=['subject']),
 c('include Neural Networks',decision='UNSUPPORTED',unsupported=['subject']),
 c('include Nonfiction',subjects=['Nonfiction']),
 c('books about Romance','Romance',notes='A topical reference remains semantic when no exact authorized canonical subject exists.'),
 c('Wizards','Wizards'),
 c('include Mystery',decision='UNSUPPORTED',unsupported=['subject']),
 c('include Detective Fiction',decision='UNSUPPORTED',unsupported=['subject']),
 c('include Computer science',subjects=['Computer science']),
])
family('d27_private_vocab', 'development', [25,26], V, [
 c('include V2CC Private Orchid',subjects=['V2CC Private Orchid']),
 c('subject Neural Networks',subjects=['Neural Networks']),
 c('genre Romance',subjects=['Romance']),
 c('browse Detective Fiction',subjects=['Detective Fiction']),
 c('include Wizards',subjects=['Wizards']),
 c('include History',decision='UNSUPPORTED',unsupported=['subject']),
 c('include Science fiction',decision='UNSUPPORTED',unsupported=['subject']),
 c('about architecture','architecture'),
 c('include Fiction and V2CC Private Orchid',subjects=['Fiction','V2CC Private Orchid']),
 c('Neural Networks excluding Romance',subjects=['Neural Networks'],excluded=['Romance']),
])
family('d28_unknown_subject', 'development', [27,14,25], W, [
 c('include Astrobiology',decision='UNSUPPORTED',unsupported=['subject']),
 c('subject Climate economics',decision='UNSUPPORTED',unsupported=['subject']),
 c('genre Space opera',decision='UNSUPPORTED',unsupported=['subject']),
 c('include Java',decision='UNSUPPORTED',unsupported=['subject']),
 c('only subject Quantum computing',decision='UNSUPPORTED',unsupported=['subject']),
 c('include Philosophy',decision='UNSUPPORTED',unsupported=['subject']),
 c('include Poetry',decision='UNSUPPORTED',unsupported=['subject']),
 c('include Computer science',decision='UNSUPPORTED',unsupported=['subject']),
 c('subject Renewable energy',decision='UNSUPPORTED',unsupported=['subject']),
 c('include Biography',decision='UNSUPPORTED',unsupported=['subject']),
])
family('d29_number_ambiguity', 'development', [28,36], G, [
 c('science fiction 4',subjects=['Science fiction'],decision='AMBIGUOUS',ambiguous=['4']),
 c('books above 4',decision='AMBIGUOUS',ambiguous=['above 4'],notes='Initial query lacks a rating unit; number may refer to level, volume or rating.'),
 c('history 2020',subjects=['History'],decision='AMBIGUOUS',ambiguous=['2020']),
 c('fiction 4',subjects=['Fiction'],decision='AMBIGUOUS',ambiguous=['4']),
 c('mystery 3.5',subjects=['Mystery'],decision='AMBIGUOUS',ambiguous=['3.5']),
 c('books about the number 4','number 4',protect=['number 4']),
 c('level 4 chemistry','level 4 chemistry',protect=['level 4']),
 c('volume 3 history','volume 3 history',protect=['volume 3']),
 c('astronomy 5',subjects=['Astronomy'],decision='AMBIGUOUS',ambiguous=['5']),
 c('Poetry 2',subjects=['Poetry'],decision='AMBIGUOUS',ambiguous=['2']),
])
family('d30_title_vs_year', 'development', [29,5,2], P, [
 c('books titled "2020"',exact='2020',title='2020',protect=['2020']),
 c('"1945" history books','1945',subjects=['History'],title='1945',protect=['1945']),
 c('the novel 1984','novel 1984',title='1984',protect=['1984']),
 c('books about history after 1945','history after 1945',protect=['after 1945'],notes='About-clause temporal detail describes topic, not publication date.'),
 c('books published after 2020 about events after 1945','events after 1945',ymin=2020,yminx=True,protect=['after 1945']),
 c('books titled "After 2020"',exact='After 2020',title='After 2020',protect=['After 2020']),
 c('read about life in 1999','life in 1999',protect=['1999']),
 c('a history of events before 1914','history of events before 1914',protect=['before 1914']),
 c('the year 2000 in popular culture','year 2000 in popular culture',protect=['year 2000']),
 c('books on the 1984 miners strike','1984 miners strike',protect=['1984 miners strike']),
])
family('d31_title_vs_edition', 'development', [30,5,14], G, [
 c('books titled "Second Edition Networking"',exact='Second Edition Networking',title='Second Edition Networking',protect=['Second Edition Networking']),
 c('The Second Sex','The Second Sex',title='The Second Sex',protect=['The Second Sex']),
 c('The Fifth Season','The Fifth Season',title='The Fifth Season',protect=['The Fifth Season']),
 c('Python 3 second edition','Python 3',decision='UNSUPPORTED',unsupported=['edition'],protect=['Python 3']),
 c('a revised edition of a book on sailing','sailing',decision='UNSUPPORTED',unsupported=['edition']),
 c('books about first editions','first editions',protect=['first editions']),
 c('studies of second-generation migrants','studies of second-generation migrants',protect=['second-generation']),
 c('3rd edition calculus','calculus',decision='UNSUPPORTED',unsupported=['edition']),
 c('books titled "First Edition"',exact='First Edition',title='First Edition',protect=['First Edition']),
 c('networking books edition 2','networking',decision='UNSUPPORTED',unsupported=['edition']),
])
family('d32_author_subject_names', 'development', [31,4,3], G, [
 c('books by Virginia Woolf about History','History',author='Virginia Woolf'),
 c('History by Mary Beard',subjects=['History'],author='Mary Beard'),
 c('books about Mary Beard and Rome','Mary Beard and Rome'),
 c('Fiction by Toni Morrison',subjects=['Fiction'],author='Toni Morrison'),
 c('books on Toni Morrison criticism','Toni Morrison criticism'),
 c('author bell hooks',author='bell hooks'),
 c('books about the author bell hooks','author bell hooks'),
 c('Poetry written by Langston Hughes',subjects=['Poetry'],author='Langston Hughes'),
 c('Romance by Jane Austen',subjects=['Romance'],author='Jane Austen'),
 c('books about Jane Austen novels','Jane Austen novels'),
])

# CALIBRATION: distinct grammatical constructions, never copied into dev/holdout.
family('c01_exclusivity_clashes', 'calibration', [32,12,7], V, [
 c('online only and physical only',fmt=['ONLINE','PHYSICAL'],exclusive=['ONLINE','PHYSICAL'],decision='CONTRADICTORY',contradiction=['format']),
 c('physical only yet an online version is required',fmt=['PHYSICAL','ONLINE'],exclusive=['PHYSICAL'],decision='CONTRADICTORY',contradiction=['format']),
 c('online-only Mystery that also must be physical',subjects=['Mystery'],fmt=['ONLINE','PHYSICAL'],exclusive=['ONLINE'],decision='CONTRADICTORY',contradiction=['format']),
 c('include Fiction and exclude Fiction',subjects=['Fiction'],excluded=['Fiction'],decision='CONTRADICTORY',contradiction=['subject']),
 c('include Romance but exclude Romance',subjects=['Romance'],excluded=['Romance'],decision='CONTRADICTORY',contradiction=['subject']),
 c('include Neural Networks while excluding Neural Networks',subjects=['Neural Networks'],excluded=['Neural Networks'],decision='CONTRADICTORY',contradiction=['subject']),
 c('include Mystery; exclude Mystery; online',subjects=['Mystery'],excluded=['Mystery'],fmt=['ONLINE'],decision='CONTRADICTORY',contradiction=['subject']),
 c('include Wizards and Fiction but exclude Wizards',subjects=['Wizards','Fiction'],excluded=['Wizards'],decision='CONTRADICTORY',contradiction=['subject']),
 c('online books with online excluded',fmt=['ONLINE'],exfmt=['ONLINE'],decision='CONTRADICTORY',contradiction=['format']),
 c('physical books except physical books',fmt=['PHYSICAL'],exfmt=['PHYSICAL'],decision='CONTRADICTORY',contradiction=['format']),
])
family('c02_combined_presence', 'calibration', [33,7], W, [
 c('books with both online and physical versions',fmt=['ONLINE','PHYSICAL']),
 c('Mystery in both physical and online formats',subjects=['Mystery'],fmt=['ONLINE','PHYSICAL']),
 c('require a digital version and a physical copy about kites','kites',fmt=['ONLINE','PHYSICAL']),
 c('Fiction with physical as well as online access',subjects=['Fiction'],fmt=['ONLINE','PHYSICAL']),
 c('Neural Networks online and physical',subjects=['Neural Networks'],fmt=['ONLINE','PHYSICAL']),
 c('books on ceramics that have both formats','ceramics',fmt=['ONLINE','PHYSICAL'],notes='Both formats refers to the two enumerated supported formats in this scope.'),
 c('both physical and online Romance',subjects=['Romance'],fmt=['ONLINE','PHYSICAL']),
 c('a physical copy plus online access about wizards','wizards',fmt=['ONLINE','PHYSICAL']),
 c('Detective Fiction with both versions',subjects=['Detective Fiction'],fmt=['ONLINE','PHYSICAL']),
 c('V2CC Private Orchid available online and as a physical book',subjects=['V2CC Private Orchid'],fmt=['ONLINE','PHYSICAL']),
])
family('c03_kg_negative', 'calibration', [34,9,10], G, [
 c('Artificial intelligence excluding neural networks',subjects=['Artificial intelligence'],exclude_terms=['neural networks']),
 c('Computer science minus cybersecurity',subjects=['Computer science'],exclude_terms=['cybersecurity']),
 c('Mathematics excluding calculus',subjects=['Mathematics'],exclude_terms=['calculus']),
 c('Astronomy excluding astrology',subjects=['Astronomy'],exclude_terms=['astrology']),
 c('Fiction without Romance',subjects=['Fiction'],excluded=['Romance']),
 c('History excluding military campaigns',subjects=['History'],exclude_terms=['military campaigns']),
 c('Engineering minus bridge design',subjects=['Engineering'],exclude_terms=['bridge design']),
 c('Philosophy except ethics',subjects=['Philosophy'],excluded=['Ethics']),
 c('Technology excluding social media',subjects=['Technology'],exclude_terms=['social media']),
 c('Science excluding astrology and alchemy',subjects=['Science'],exclude_terms=['astrology','alchemy']),
])
family('c04_correction_actions', 'calibration', [35,16,23], G, [
 c('keep the original text scince fiction','scince fiction',notes='Correction rejection: no canonical subject may be silently substituted.'),
 c('apply correction to Science fiction',subjects=['Science fiction'],notes='Explicit correction acceptance; session evaluator must bind an issued correction action.'),
 c('leave histroy unchanged','histroy'),
 c('use corrected subject History',subjects=['History']),
 c('keep my spelling romnace','romnace'),
 c('accept Romance as the subject',subjects=['Romance']),
 c('do not change the word netwroking','netwroking',protect=['netwroking']),
 c('use Fiction instead of ficiton',subjects=['Fiction'],notes='Explicit requested replacement, not silent autocorrection.'),
 c('keep astronmy as typed','astronmy'),
 c('change the subject spelling to Astronomy',subjects=['Astronomy']),
])
family('c05_clarification_units', 'calibration', [36,28], G, [
 c('Fiction, four please',subjects=['Fiction'],decision='AMBIGUOUS',ambiguous=['four']),
 c('History around 2020',subjects=['History'],decision='AMBIGUOUS',ambiguous=['around 2020']),
 c('Mystery at 3',subjects=['Mystery'],decision='AMBIGUOUS',ambiguous=['at 3']),
 c('four for Astronomy',subjects=['Astronomy'],decision='AMBIGUOUS',ambiguous=['four']),
 c('Poetry from 2000',subjects=['Poetry'],decision='AMBIGUOUS',ambiguous=['from 2000']),
 c('Romance no more than 2',subjects=['Romance'],decision='AMBIGUOUS',ambiguous=['no more than 2']),
 c('Science fiction between 3 and 4',subjects=['Science fiction'],decision='AMBIGUOUS',ambiguous=['between 3 and 4']),
 c('give me 4 History',subjects=['History'],decision='AMBIGUOUS',ambiguous=['4']),
 c('Fiction 2021 edition or year',subjects=['Fiction'],decision='AMBIGUOUS',ambiguous=['2021 edition or year']),
 c('Java 4','Java 4',decision='AMBIGUOUS',ambiguous=['4']),
])
family('c06_rating_interval_language', 'calibration', [1,11], G, [
 c('books whose rating is between 3 and 4 about orchards','orchards',rmin=3,rmax=4),
 c('keep ratings from 2.5 through 4.5 for Fiction',subjects=['Fiction'],rmin=2.5,rmax=4.5),
 c('a rating within 4 to 5 for History',subjects=['History'],rmin=4,rmax=5),
 c('rating must exceed 3 but stay below 4','',rmin=3,rminx=True,rmax=4,rmaxx=True),
 c('rating not below 4 for Astronomy',subjects=['Astronomy'],rmin=4),
 c('rating not above 3 for Poetry',subjects=['Poetry'],rmax=3),
 c('only ratings of 4 or higher about glassmaking','glassmaking',rmin=4),
 c('rating of 2 or less on animal tracks','animal tracks',rmax=2),
 c('books with a rating exceeding four about rainforests','rainforests',rmin=4,rminx=True),
 c('books with a rating below three about canals','canals',rmax=3,rmaxx=True),
])
family('c07_year_intersections', 'calibration', [2,12], S, [
 c('published after 2018 and before 2022 about drones','drones',ymin=2018,yminx=True,ymax=2022,ymaxx=True),
 c('publication from 2000 through 2010 about archives','archives',ymin=2000,ymax=2010),
 c('published no earlier than 1990 and no later than 1995',ymin=1990,ymax=1995),
 c('published after 2021 and before 2020',ymin=2021,yminx=True,ymax=2020,ymaxx=True,decision='CONTRADICTORY',contradiction=['year']),
 c('publication year at least 2010 and at most 2009',ymin=2010,ymax=2009,decision='CONTRADICTORY',contradiction=['year']),
 c('published strictly after 2020 but by 2020',ymin=2020,yminx=True,ymax=2020,decision='CONTRADICTORY',contradiction=['year']),
 c('published before 1999 and since 1999',ymin=1999,ymax=1999,ymaxx=True,decision='CONTRADICTORY',contradiction=['year']),
 c('publication year from 2021 to 2021 on Java',subjects=['Java'],ymin=2021,ymax=2021),
 c('publication after 1980, at most 1990, about sailing','sailing',ymin=1980,yminx=True,ymax=1990),
 c('publication year > 2017 and <= 2019 for Fiction',subjects=['Fiction'],ymin=2017,yminx=True,ymax=2019),
])
family('c08_without_scoping', 'calibration', [10,9], V, [
 c('Fiction without any Romance',subjects=['Fiction'],excluded=['Romance']),
 c('Mystery minus supernatural themes','',subjects=['Mystery'],exclude_terms=['supernatural themes']),
 c('Wizards except school stories','',subjects=['Wizards'],exclude_terms=['school stories']),
 c('not Romance, just Fiction',subjects=['Fiction'],excluded=['Romance']),
 c('Neural Networks with no Fiction',subjects=['Neural Networks'],excluded=['Fiction']),
 c('everything except Mystery',excluded=['Mystery']),
 c('no Romance or Mystery in Fiction',subjects=['Fiction'],excluded=['Romance','Mystery'],notes='Negation distributes over the excluded disjunction; no positive subject OR is constructed.'),
 c('Fiction but leave out Detective Fiction',subjects=['Fiction'],excluded=['Detective Fiction']),
 c('V2CC Private Orchid minus Romance',subjects=['V2CC Private Orchid'],excluded=['Romance']),
 c('leave out Wizards; find Neural Networks',subjects=['Neural Networks'],excluded=['Wizards']),
])
family('c09_scope_switch_labels', 'calibration', [25,26,27], S, [
 c('limit the category to Romance',decision='UNSUPPORTED',unsupported=['subject']),
 c('filter the subject to V2CC Private Orchid',decision='UNSUPPORTED',unsupported=['subject']),
 c('limit the subject to Java',subjects=['Java']),
 c('filter by subject Nonfiction',subjects=['Nonfiction']),
 c('restrict to the Mystery genre',decision='UNSUPPORTED',unsupported=['subject']),
 c('restrict to the Wizards subject',decision='UNSUPPORTED',unsupported=['subject']),
 c('match subject Neural Networks exactly',decision='UNSUPPORTED',unsupported=['subject']),
 c('limit to the Science fiction category',subjects=['Science fiction']),
 c('filter the category to Fiction',subjects=['Fiction']),
 c('restrict the subject to Computer science',subjects=['Computer science']),
])
family('c10_quoted_nested_clauses', 'calibration', [20,10,6], V, [
 c('Mystery about "not only Romance"','not only Romance',subjects=['Mystery'],protect=['not only Romance']),
 c('about "include Fiction and exclude Fiction"','include Fiction and exclude Fiction',protect=['include Fiction and exclude Fiction']),
 c('Fiction with the phrase "rating >= 4"','rating >= 4',subjects=['Fiction'],protect=['rating >= 4']),
 c('books about "published before 1900"','published before 1900',protect=['published before 1900']),
 c('"C# 12" online','C# 12',fmt=['ONLINE'],protect=['C# 12']),
 c('"Python 3" rated above 4','Python 3',rmin=4,rminx=True,protect=['Python 3']),
 c('"1984" published after 2000','1984',ymin=2000,yminx=True,title='1984',protect=['1984']),
 c('Mystery excluding "Neural Networks"',subjects=['Mystery'],exclude_terms=['Neural Networks'],protect=['Neural Networks'],notes='Quoted excluded phrase is text, not a canonical subject exclusion.'),
 c('"V2CC Private Orchid" as a phrase','V2CC Private Orchid',protect=['V2CC Private Orchid']),
 c('books titled "4+"',exact='4+',title='4+',protect=['4+']),
])
family('c11_unsupported_positive_boolean', 'calibration', [9,14,36], V, [
 c('include Fiction or Romance',decision='UNSUPPORTED',unsupported=['boolean_subject_logic']),
 c('include (Fiction and Wizards) or Mystery',decision='UNSUPPORTED',unsupported=['boolean_subject_logic']),
 c('Romance OR Neural Networks',decision='UNSUPPORTED',unsupported=['boolean_subject_logic']),
 c('include Fiction unless it is Mystery or Romance',decision='UNSUPPORTED',unsupported=['boolean_subject_logic']),
 c('online Mystery or physical Romance',decision='UNSUPPORTED',unsupported=['boolean_subject_logic']),
 c('include either Wizards or Detective Fiction',decision='UNSUPPORTED',unsupported=['boolean_subject_logic']),
 c('Fiction AND (Mystery OR Romance)',decision='UNSUPPORTED',unsupported=['boolean_subject_logic']),
 c('include Fiction XOR Romance',decision='UNSUPPORTED',unsupported=['boolean_subject_logic']),
 c('Mystery if not Romance otherwise Neural Networks',decision='UNSUPPORTED',unsupported=['boolean_subject_logic']),
 c('include any two of Fiction, Romance and Wizards',decision='UNSUPPORTED',unsupported=['boolean_subject_logic']),
])

# HELDOUT: isolated constructions; authoring source and split file remain sealed
# from the implementation agent until the parser freeze.
family('h01_star_thresholds', 'heldout', [1,11], G, [
 c('fiction with more than 3 stars about wizards','wizards',subjects=['Fiction'],rmin=3,rminx=True),
 c('at least 4 star science fiction',subjects=['Science fiction'],rmin=4),
 c('fewer than three stars for books on stained glass','stained glass',rmax=3,rmaxx=True),
 c('four stars or better for Poetry',subjects=['Poetry'],rmin=4),
 c('History with no more than two stars',subjects=['History'],rmax=2),
 c('Romance scoring over four stars',subjects=['Romance'],rmin=4,rminx=True),
 c('five-star Astronomy books',subjects=['Astronomy'],rmin=5,rmax=5),
 c('three-and-a-half stars or higher on shipbuilding','shipbuilding',rmin=3.5),
 c('Fiction below four and a half stars',subjects=['Fiction'],rmax=4.5,rmaxx=True),
 c('books earning no fewer than four stars about cob building','cob building',rmin=4),
])
family('h02_temporal_roles', 'heldout', [2,29,28], P, [
 c('on post-1945 rebuilding, with publication later than 2015','post-1945 rebuilding',ymin=2015,yminx=True,protect=['post-1945']),
 c('a book issued before 2005 on life after 1989','life after 1989',ymax=2005,ymaxx=True,protect=['after 1989']),
 c('history of 2020, published in 2022','history of 2020',ymin=2022,ymax=2022,protect=['2020']),
 c('books released since 2010 on events of 1917','events of 1917',ymin=2010,protect=['1917']),
 c('printed before 1990 about the year 2000','year 2000',ymax=1990,ymaxx=True,protect=['year 2000']),
 c('the title is "After 1945", publication later than 2000',exact='After 1945',title='After 1945',ymin=2000,yminx=True,protect=['After 1945']),
 c('published during 2021 on the 2011 earthquake','2011 earthquake',ymin=2021,ymax=2021,protect=['2011 earthquake']),
 c('books issued no earlier than 2012 about 1980s music','1980s music',ymin=2012,protect=['1980s']),
 c('writings on before-and-after photography, published by 2019','before-and-after photography',ymax=2019,protect=['before-and-after']),
 c('a publication dating to 2018 on Route 66','Route 66',ymin=2018,ymax=2018,protect=['Route 66']),
])
family('h03_negation_semantic_roles', 'heldout', [10,20,15], G, [
 c('stories where characters do not trust machines','stories where characters do not trust machines'),
 c('why not learn C++','C++',intent='LEARN',protect=['C++']),
 c('not a beginner guide to network switches','network switches',soft=['not beginner'],decision='EXECUTABLE_WITH_NOTICE'),
 c('books explaining the phrase not only but also','phrase not only but also',protect=['not only but also']),
 c('I am not looking for Romance; show Mystery',subjects=['Mystery'],excluded=['Romance']),
 c('please avoid Romance when finding Fiction',subjects=['Fiction'],excluded=['Romance']),
 c('stories on non-verbal communication','stories on non-verbal communication',protect=['non-verbal']),
 c('books about things that are not numbers','things that are not numbers'),
 c('the title is "Not History"',exact='Not History',title='Not History',protect=['Not History']),
 c('not just Fiction, something about hope','Fiction hope',notes='Not-just is additive emphasis; no negative subject filter.'),
])
family('h04_scope_conflicting_requirements', 'heldout', [12,9,32], W, [
 c('must be Fiction and must never be Fiction',subjects=['Fiction'],excluded=['Fiction'],decision='CONTRADICTORY',contradiction=['subject']),
 c('require Romance; forbid the Romance subject',subjects=['Romance'],excluded=['Romance'],decision='CONTRADICTORY',contradiction=['subject']),
 c('Mystery is required and Mystery is forbidden',subjects=['Mystery'],excluded=['Mystery'],decision='CONTRADICTORY',contradiction=['subject']),
 c('require an online version but disallow online',fmt=['ONLINE'],exfmt=['ONLINE'],decision='CONTRADICTORY',contradiction=['format']),
 c('physical is mandatory but physical must be excluded',fmt=['PHYSICAL'],exfmt=['PHYSICAL'],decision='CONTRADICTORY',contradiction=['format']),
 c('nothing physical, but a physical-only book is required',fmt=['PHYSICAL'],exclusive=['PHYSICAL'],exfmt=['PHYSICAL'],decision='CONTRADICTORY',contradiction=['format']),
 c('require both versions while excluding physical',fmt=['ONLINE','PHYSICAL'],exfmt=['PHYSICAL'],decision='CONTRADICTORY',contradiction=['format']),
 c('rating must be higher than four and lower than four',rmin=4,rminx=True,rmax=4,rmaxx=True,decision='CONTRADICTORY',contradiction=['rating']),
 c('the publication must precede 2020 and follow 2021',ymin=2021,yminx=True,ymax=2020,ymaxx=True,decision='CONTRADICTORY',contradiction=['year']),
 c('Wizards is mandatory; Wizards must be absent',subjects=['Wizards'],excluded=['Wizards'],decision='CONTRADICTORY',contradiction=['subject']),
])
family('h05_technical_plus_filters', 'heldout', [6,1,7,28], P, [
 c('C++ 23 with a rating no lower than 4','C++ 23',rmin=4,protect=['C++ 23']),
 c('for Python 3.12, only physical books','Python 3.12',fmt=['PHYSICAL'],exclusive=['PHYSICAL'],protect=['Python 3.12']),
 c('Windows 11 resources scoring at least 3 stars','Windows 11 resources',rmin=3,protect=['Windows 11']),
 c('about ISO 27001 with publication after 2018','ISO 27001',ymin=2018,yminx=True,protect=['ISO 27001']),
 c('C# 12 books with digital access','C# 12',fmt=['ONLINE'],protect=['C# 12']),
 c('rated over 3.5 for TCP/IP v6','TCP/IP v6',rmin=3.5,rminx=True,protect=['TCP/IP v6']),
 c('HTTP/3 titles published no later than 2023','HTTP/3',ymax=2023,protect=['HTTP/3']),
 c('802.11be books that I can borrow now','802.11be',availability='AVAILABLE_NOW',protect=['802.11be']),
 c('Node.js 22 with a physical and online version','Node.js 22',fmt=['ONLINE','PHYSICAL'],protect=['Node.js 22']),
 c('PostgreSQL 16, minimum rating 4.5','PostgreSQL 16',rmin=4.5,protect=['PostgreSQL 16']),
])
family('h06_entity_filter_mixtures', 'heldout', [5,21,20,1], G, [
 c('"1984" with four stars or more','1984',title='1984',rmin=4,protect=['1984']),
 c('Catch-22, minimum review rating 3','Catch-22',title='Catch-22',rmin=3,protect=['Catch-22']),
 c('The Three-Body Problem scoring over 4 stars','The Three-Body Problem',title='The Three-Body Problem',rmin=4,rminx=True,protect=['The Three-Body Problem']),
 c('ISBN 9780141036144 with an online copy','ISBN 9780141036144',fmt=['ONLINE'],protect=['9780141036144']),
 c('books on "number 4" rated no less than 3','number 4',rmin=3,protect=['number 4']),
 c('a title matching "Rating Below 3"',exact='Rating Below 3',title='Rating Below 3',protect=['Rating Below 3']),
 c('books titled "Published After"',exact='Published After',title='Published After',protect=['Published After']),
 c('"Second Edition" by Mira Rao',exact='Second Edition',title='Second Edition',author='Mira Rao',protect=['Second Edition']),
 c('Dune 2 scoring at least four stars','Dune 2',title='Dune 2',rmin=4,protect=['Dune 2']),
 c('"C++" not the phrase "C#"','C++',exclude_terms=['C#'],protect=['C++','C#']),
])
family('h07_soft_hard_composition', 'heldout', [15,14,11], V, [
 c('a short Mystery with rating no lower than 4',subjects=['Mystery'],soft=['short'],rmin=4,decision='EXECUTABLE_WITH_NOTICE'),
 c('beginner-friendly Neural Networks after publication year 2020',subjects=['Neural Networks'],soft=['beginner-friendly'],ymin=2020,yminx=True,decision='EXECUTABLE_WITH_NOTICE',intent='LEARN'),
 c('advanced Wizards with only online access',subjects=['Wizards'],soft=['advanced'],fmt=['ONLINE'],exclusive=['ONLINE'],decision='EXECUTABLE_WITH_NOTICE'),
 c('concise Fiction, but strictly fewer than 200 pages',subjects=['Fiction'],soft=['concise'],unsupported=['page_count'],decision='UNSUPPORTED'),
 c('a recent Romance, specifically published after 2019',subjects=['Romance'],soft=['recent'],ymin=2019,yminx=True,decision='EXECUTABLE_WITH_NOTICE'),
 c('research-level Neural Networks with minimum rating 4.5',subjects=['Neural Networks'],soft=['research-level'],rmin=4.5,decision='EXECUTABLE_WITH_NOTICE',intent='RESEARCH'),
 c('a gentle introduction to Mystery with a physical copy',subjects=['Mystery'],soft=['gentle introduction'],fmt=['PHYSICAL'],decision='EXECUTABLE_WITH_NOTICE',intent='LEARN'),
 c('an easy Fiction book, specifically the second edition',subjects=['Fiction'],soft=['easy'],unsupported=['edition'],decision='UNSUPPORTED'),
 c('comprehensive Detective Fiction that is available now',subjects=['Detective Fiction'],soft=['comprehensive'],availability='AVAILABLE_NOW',decision='EXECUTABLE_WITH_NOTICE'),
 c('a brief book about gardens with online access','gardens',soft=['brief'],fmt=['ONLINE'],decision='EXECUTABLE_WITH_NOTICE'),
])
family('h08_dangling_connectors', 'heldout', [13,36,11], V, [
 c('Fiction and rated no less than',subjects=['Fiction'],decision='INCOMPLETE',incomplete=['rating']),
 c('Mystery with publication earlier than',subjects=['Mystery'],decision='INCOMPLETE',incomplete=['year']),
 c('Wizards but leave out',subjects=['Wizards'],decision='INCOMPLETE',incomplete=['exclusion']),
 c('online about',fmt=['ONLINE'],decision='INCOMPLETE',incomplete=['topic']),
 c('a book written by',decision='INCOMPLETE',incomplete=['author']),
 c('the title should be',decision='INCOMPLETE',incomplete=['title']),
 c('minimum rating:',decision='INCOMPLETE',incomplete=['rating']),
 c('Neural Networks excluding the subject',subjects=['Neural Networks'],decision='INCOMPLETE',incomplete=['excluded_subject']),
 c('publication from 2010 through',ymin=2010,decision='INCOMPLETE',incomplete=['year_max']),
 c('Fiction rated between',subjects=['Fiction'],decision='INCOMPLETE',incomplete=['rating_min','rating_max']),
])
family('h09_author_appositives', 'heldout', [4,31,20], G, [
 c('for the author, use N. K. Jemisin',author='N. K. Jemisin'),
 c('the writer should be James Baldwin',author='James Baldwin'),
 c('a book whose author is Mary Shelley',author='Mary Shelley'),
 c('show works from author Chinua Achebe',author='Chinua Achebe'),
 c('not about Borges; written by Borges',author='Borges',exclude_terms=['Borges'],notes='The topical exclusion and author slot are distinct; no subject/author contradiction is invented.'),
 c('about the life of the writer James Baldwin','life of the writer James Baldwin'),
 c('subject is Fiction and the author is Kazuo Ishiguro',subjects=['Fiction'],author='Kazuo Ishiguro'),
 c('for author "History After 2020"',author='History After 2020',protect=['History After 2020']),
 c('discuss the work of the author N. K. Jemisin','work of the author N. K. Jemisin'),
 c('the author must be Liu Cixin, with rating at least 4',author='Liu Cixin',rmin=4),
])
family('h10_private_scope_absence', 'heldout', [25,26,27,14], V, [
 c('the requested subject is Oceanography',decision='UNSUPPORTED',unsupported=['subject']),
 c('I require the category Romance fiction',decision='UNSUPPORTED',unsupported=['subject']),
 c('the subject must match Artificial intelligence',decision='UNSUPPORTED',unsupported=['subject']),
 c('the topic is artificial intelligence','artificial intelligence'),
 c('the required subject is Neural Networks',subjects=['Neural Networks']),
 c('the category must be V2CC Private Orchid',subjects=['V2CC Private Orchid']),
 c('set the requested subject to Computer networks',decision='UNSUPPORTED',unsupported=['subject']),
 c('a topic of oceanography, not a subject filter','oceanography',notes='Explicitly topical, unknown private vocabulary remains semantic.'),
 c('the subject must be Detective Fiction',subjects=['Detective Fiction']),
 c('require the exact subject Science Fiction',decision='UNSUPPORTED',unsupported=['subject']),
])
family('h11_exact_adversarial_syntax', 'heldout', [22,20,28,12], S, [
 c('Mystery OR Romance',mode='exact',exact='Mystery OR Romance',protect=['Mystery OR Romance']),
 c('rating < 0 AND rating > 5',mode='exact',exact='rating < 0 AND rating > 5',protect=['rating < 0 AND rating > 5']),
 c('author: History 2020',mode='exact',exact='author: History 2020',protect=['author: History 2020']),
 c('NOT V2CC Private Orchid',mode='exact',exact='NOT V2CC Private Orchid',protect=['NOT V2CC Private Orchid']),
 c('include Fiction XOR Java',mode='exact',exact='include Fiction XOR Java',protect=['include Fiction XOR Java']),
 c('physical-only minus physical',mode='exact',exact='physical-only minus physical',protect=['physical-only minus physical']),
 c('published between 2020 and',mode='exact',exact='published between 2020 and',protect=['published between 2020 and']),
 c('under 250 pages, edition 2',mode='exact',exact='under 250 pages, edition 2',protect=['under 250 pages, edition 2']),
 c('C#>=4',mode='exact',exact='C#>=4',protect=['C#>=4']),
 c('9780307277671 above 4 stars',mode='exact',exact='9780307277671 above 4 stars',protect=['9780307277671 above 4 stars']),
])

def review_and_write():
    assert len(CASES)==540
    # Duplicate utterances can legitimately have different scopes or exact mode,
    # but none may cross structural splits. The shared literal examples are
    # deliberate scope/mode contrasts within development.
    seen={}
    for row in CASES:
        key=(row['query'].casefold(),row['scope_type'],row['search_mode'])
        assert key not in seen, (row['query_id'],seen.get(key))
        seen[key]=row['query_id']
        scope=VOCAB[row['scope_type']]
        authorized={s.casefold() for s in scope['subjects']}
        for subject in row['expected_subjects']+row['expected_excluded_subjects']:
            assert subject.casefold() in authorized,(row['query_id'],subject)
        for span in row['protected_spans']:
            assert row['query'][span['start']:span['end']]==span['text']
        assert row['execution_allowed']==(row['expected_decision'] in ['EXECUTABLE','EXECUTABLE_WITH_NOTICE'])
        if row['expected_decision']=='CONTRADICTORY':assert row['expected_contradiction_fields']
        if row['expected_decision']=='INCOMPLETE':assert row['expected_incomplete_fields']
        if row['expected_decision']=='AMBIGUOUS':assert row['expected_ambiguous_spans']
        if row['expected_decision']=='UNSUPPORTED':assert row['expected_unsupported_fields']
        # Self-review is recorded separately from initial authorship provenance.
        row['label_reviewed']=True
    out=ROOT/'reports'
    outputs={}
    for split in ['development','calibration','heldout']:
        path=out/f'search_v2c_c_gold_{split}.jsonl'
        rows=[r for r in CASES if r['split']==split]
        text=''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows)
        path.write_text(text,encoding='utf-8',newline='\n')
        outputs[split]={'path':str(path),'count':len(rows),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest=dict(authorship='540 individually written utterance/context cases; shared schema defaults only',
        independently_authored_cases=540,ai_self_reviewed_cases=540,
        independently_second_reviewed_cases=0,human_reviewed_cases=0,
        unique_query_texts=len({r['query'] for r in CASES}),
        parser_output_access=False,parser_implementation_access=False,
        prior_gold_access=False,heldout_implementation_agent_access_before_freeze=False,
        split_outputs=outputs,families=FAMILIES,
        review_provenance='AI self-reviewed by independent author; no second separate reviewer; no human review',
        uncertainties=['Normative intent/semantic remainder labels involve author judgment.',
            'Session refinement rows specify turn deltas; a separate sequence benchmark supplies accepted base context.',
            'Typo rows allow safe literal execution with a notice; a correction is never silently imposed.',
            'Field naming is evaluator-neutral; implementation adapter must not relabel expectations from parser output.'])
    path=out/'search_v2c_c_authored_families.json'
    path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k!='families'},indent=2))

if __name__=='__main__':review_and_write()
