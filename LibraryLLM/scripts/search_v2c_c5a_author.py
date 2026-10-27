"""Independent C5A semantic author. Reads exactly the two commissioned specs.

No application imports, parser outputs, evaluation, or sealed data are used.
The tables below are authored intent plans; rendering them is not prediction.
"""
import copy
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIEF = json.loads((ROOT/'reports/search_v2c_c5a_author_brief.json').read_text(encoding='utf-8-sig'))
MATRIX = json.loads((ROOT/'reports/search_v2c_c5a_capability_matrix.json').read_text(encoding='utf-8-sig'))
SCOPES = BRIEF['scopes']
STRATA = BRIEF['strata']
ROWS = []

# Terms below were selected from the frozen, scope-specific vocabulary.
SUBJECTS = {
 'GLOBAL': ['History','Physics','Poetry','Mathematics','Fiction','Ecology','Philosophy','Biography'],
 'PUBLIC_TENANT_PATRON': ['Community archives','Quantum computing','Ecology','Mathematics','Fiction','Physics','Philosophy','Biography'],
 'PUBLIC_TENANT_STAFF': ['Climate change mitigation','Computer science','Water','Transportation','History','Economics','Science','Education'],
 'PRIVATE_TENANT_PATRON': ['Mystery','Neural Networks','Romance','Wizards','Fiction','Detective Fiction','V2CC Private Orchid','Mystery'],
 'PRIVATE_TENANT_STAFF': ['Detective Fiction','Wizards','Neural Networks','Romance','Fiction','V2CC Private Orchid','Mystery','Detective Fiction'],
}
TOPICS = {
 'GLOBAL': ['tidal observatories','pottery ledgers','mountain signal fires','canal boat songs','desert seed exchanges','winter clock towers','island navigators','silent theater masks','rooftop sundials','glacial field notebooks','orchard cooperatives','inkmaking workshops','marshland bridges','paper lantern rituals','storm bell keepers','copper route maps','volcanic gardens','quarry soundscapes','river ice diaries','harbor constellation charts'],
 'PUBLIC_TENANT_PATRON': ['neighborhood memory walks','quantum error mosaics','wetland migration maps','geometric loom puzzles','moonlit orchard fables','acoustic tide gauges','collective promises','bridge keeper memoirs','seed library networks','thermal refuge planning','portable water sensors','village debate circles','rural energy councils','courtyard rainfall logs','community repair clubs','robotic garden tenders','coastal memory projects','trading post diaries','civic listening rooms','railway platform songs'],
 'PUBLIC_TENANT_STAFF': ['heat shelter placement','archive access networks','reservoir boundary disputes','night bus connections','harbor customs ledgers','cooperative price signals','foam river experiments','peer learning circles','solar workshop planning','estuary salinity models','bicycle signal timing','factory reading rooms','county weather diaries','market garden accounting','instrument calibration clubs','library teaching circles','tidal energy governance','navigation chart errors','mutual aid economies','village observatory lessons'],
 'PRIVATE_TENANT_PATRON': ['clockmaker alibis','sparse orchard classifiers','letters across a flooded valley','apprentice weather charms','moon ferry adventures','missing conservatory keys','orchid glasshouse riddles','snowbound radio puzzles','lost lake invitations','tangled message networks','lantern shop promises','wand repair apprenticeships','traveling shadow fairs','locked pottery studios','undersea garden maps','mirror school rivalries','forecasting comet trails','midnight greenhouse meetings','stolen festival bells','desert caravan riddles'],
 'PRIVATE_TENANT_STAFF': ['train carriage alibis','rune powered windmills','noisy telescope classifiers','rival mapmakers in love','floating village voyages','orchid conservatory accounts','vanished lighthouse clocks','silver ink apprentices','stolen weather instruments','riverboat message networks','long distance observatory letters','weather spell ethics','folded city adventures','museum night patrols','moonrise garden histories','icebridge wizard councils','puzzle box disappearances','sensor drift detection','stormbound pen pals','tangled harbor testimony'],
}
FIRST = ['Mirel','Talven','Orena','Sivren','Narela','Velis','Dorin','Evara','Rulwen','Aveli','Therin','Cirel','Novra','Jalen','Isven','Luriel','Pevra','Salen','Yvren','Zarela']
LAST = ['Orvane','Kelmor','Veylish','Darsel','Umbrin','Fenmire','Tovarin','Caldris','Nerovan','Ildren','Mosveil','Queren','Harveth','Selmar','Wynrel','Brenova','Ashven','Dalmere','Yorven','Zelmari']
TITLE_A = ['The Lantern','A Copper','The Quiet','A River','The Hidden','A Winter','The Amber','A Broken','The Silver','A Tidal','The Last','A Velvet','The Distant','A Paper','The Hollow','A Midnight','The Glass','A Wandering','The Blue','A Folded']
TITLE_B = ['Meridian','Notebook','Observatory','Causeway','Orchard','Compass','Gallery','Cistern','Harbor','Archive','Sundial','Signal','Aqueduct','Cottage','Garden','Workshop','Labyrinth','Pavilion','Estuary','Bell']

def ctx(scope, stratum, i):
    k = SCOPES.index(scope)
    j = STRATA.index(stratum)
    # Invented names/titles identify individual cases; count comes from the
    # differing intent plans, never from these lexical substitutions.
    return dict(scope=scope, stratum=stratum, i=i,
      s=SUBJECTS[scope], topic=TOPICS[scope][(i+3*j)%20],
      a=f'{FIRST[(i+3*k+j)%20]} {LAST[(i+7*k+3*j)%20]}',
      b=f'{FIRST[(i+9+2*k+j)%20]} {LAST[(i+11+5*k+3*j)%20]}',
      t=f'{TITLE_A[(i+4*k+j)%20]} {TITLE_B[(i+7*k+2*j)%20]}',
      u=f'{TITLE_A[(i+11+3*k+j)%20]} {TITLE_B[(i+9+2*k+2*j)%20]}')

def cl(text, hard=None, soft=None, remainder=None, entities=None):
    return dict(text=text, hard=hard or {}, soft=soft or {}, remainder=remainder, entities=entities or [])

def op(code,c):
    s,a,t=c['s'],c['a'],c['t']
    table={
      'topic':cl('about '+c['topic'],remainder=c['topic']),
      'a':cl('by '+a,{'author_text':a},entities=[(a,'AUTHOR')]),
      't':cl('titled "'+t+'"',{'title_text':t},entities=[(t,'TITLE')]),
      'i':cl('include subject "'+s[0]+'"',{'subjects':[s[0]]}),
      'j':cl('include subject "'+s[1]+'"',{'subjects':[s[1]]}),
      'k':cl('include subject "'+s[2]+'"',{'subjects':[s[2]]}),
      'x':cl('exclude category "'+s[3]+'"',{'exclude_subjects':[s[3]]}),
      'z':cl('exclude category "'+s[4]+'"',{'exclude_subjects':[s[4]]}),
      'n':cl('exclude every record containing the text "prism engine"',{'exclude_terms':['prism engine']}),
      'r':cl('rated at least 4 stars',{'rating_min':4.0,'rating_min_exclusive':False}),
      'l':cl('rated over 3 stars',{'rating_min':3.0,'rating_min_exclusive':True}),
      'h':cl('rated at most 4.5 stars',{'rating_max':4.5,'rating_max_exclusive':False}),
      'q':cl('rated exactly 4 stars',{'rating_min':4.0,'rating_max':4.0,'rating_min_exclusive':False,'rating_max_exclusive':False}),
      'o':cl('online only',{'formats':['ONLINE'],'exclusive_formats':['ONLINE']}),
      'd':cl('digital format',{'formats':['ONLINE']}),
      'p':cl('physical format only',{'formats':['PHYSICAL'],'exclusive_formats':['PHYSICAL']}),
      'b':cl('in both physical and online formats',{'formats':['BOTH']}),
      'v':cl('available to borrow now',{'availability':'AVAILABLE_NOW'}),
      'y':cl('published from 2011 onward',{'year_min':2011,'year_min_exclusive':False}),
      'w':cl('published before 2020',{'year_max':2020,'year_max_exclusive':True}),
      'e':cl('published exactly in 2016',{'year_min':2016,'year_max':2016,'year_min_exclusive':False,'year_max_exclusive':False}),
      'f':cl('language French',{'language':'French'}),
      'g':cl('language German',{'language':'German'}),
      'beg':cl('prefer beginner explanations',soft={'level':'beginner'}),
      'adv':cl('prefer advanced treatments',soft={'level':'advanced'}),
      'short':cl('prefer short works',soft={'length':'short'}),
      'ref':cl('prefer reference works',soft={'purpose':'reference'}),
    }
    return copy.deepcopy(table[code])

def merge(parts):
    hard,soft={},{}
    for p in parts:
      for k,v in p['hard'].items():
        if isinstance(v,list): hard[k]=list(dict.fromkeys(hard.get(k,[])+v))
        else:
          assert k not in hard or hard[k]==v,(k,hard.get(k),v)
          hard[k]=v
      for k,v in p['soft'].items():
        assert k not in soft or soft[k]==v
        soft[k]=v
    return hard,soft

FEATURES=[
 ('rating',r'\b(?:rating|ratings|rated|stars)\b|\d\+'),
 ('year',r'\b(?:publish\w*|release\w*|year|after|before|onward)\b'),
 ('author',r'\bby\b'),('title',r'\btitled\b'),
 ('negative',r'\b(?:not|exclud\w*|without|except)\b'),
 ('include',r'\b(?:include|included|subject|category)\b'),
 ('format',r'\b(?:online|digital\w*|physical\w*|hardcover|binding)\b'),
 ('availability',r'\b(?:available|request|loan|borrow)\b'),
 ('metadata',r'\b(?:page|edition|language|french|dollar|costing|difficulty|audience)\b'),
 ('preference',r'\b(?:beginner\w*|introduct\w*|advanced|research|reference|short\w*)\b'),
 ('sort',r'\b(?:sort|highest|newest|oldest)\b'),
]
def topology(q):
    return 'SMART:'+','.join(k for k,pat in FEATURES if re.search(pat,q,re.I))

DECISIONS=dict(zip(STRATA,['EXECUTABLE','EXECUTABLE_WITH_NOTICE','AMBIGUOUS','INCOMPLETE','UNSUPPORTED','CONTRADICTORY']))
def add(c,parts,pattern,rationale,ambiguity=None,incomplete=None,unsupported=None,contradiction=None,notice=None,unresolved=None,query=None):
    hard,soft=merge(parts)
    q=query or 'Find books '+ '; '.join(p['text'] for p in parts)+'.'
    topo=topology(q)
    # Denylist compatibility is checked in one complete mechanical pass below.
    entities=[]
    for p in parts:
      for text,kind in p['entities']:
        starts=[m.start() for m in re.finditer(re.escape(text),q)]
        assert starts,(text,q)
        for start in starts:
          item=dict(text=text,start=start,end=start+len(text),kind=kind)
          if item not in entities: entities.append(item)
    # A resolved title/author elsewhere in the same request can also appear in
    # an ambiguous pairing note. Protect the span once, with the resolved role.
    role_priority={'TITLE':3,'AUTHOR':3,'TITLE_CANDIDATE':2,'AUTHOR_CANDIDATE':2}
    spans={}
    for entity in entities:
      key=(entity['start'],entity['end'])
      old=spans.get(key)
      if old is None or role_priority.get(entity['kind'],1)>role_priority.get(old['kind'],1): spans[key]=entity
    entities=sorted(spans.values(),key=lambda e:(e['start'],e['end']))
    app={
      'typed_decision':{'status':'APPLICABLE','reason':'Independently authored normative decision.'},
      'hard_constraints':{'status':'APPLICABLE','reason':'Only resolved and supported operands are listed; blocked execution does not erase them.'},
      'soft_preferences':{'status':'APPLICABLE','reason':'Only expressly advisory requests are preferences.'},
      'semantic_remainder':{'status':'APPLICABLE','reason':'Unstructured topical request retained independently of filters.'},
      'confidence':{'status':'INAPPLICABLE','reason':'No target numerical confidence was authored.'},
    }
    for field in set((incomplete or [])+(unresolved or [])):
      app[field]={'status':'UNRESOLVED','reason':'The query does not uniquely determine this operand.'}
    for field in unsupported or []:
      app[field]={'status':'INAPPLICABLE','reason':'This requested hard filter is outside the frozen scope capabilities.'}
    # Scope restrictions are explicit even when a particular query omits them.
    caps=MATRIX['scopes'][c['scope']]['capabilities']
    for cap,fields in [('year',['year_min','year_max']),('language',['language']),('availability',['availability'])]:
      if not caps[cap]:
        for field in fields:
          app.setdefault(field,{'status':'INAPPLICABLE','reason':'Unavailable in this frozen scope.'})
    cid=f"C5A-{SCOPES.index(c['scope'])+1}-{STRATA.index(c['stratum'])+1}-{c['i']+1:02d}"
    row=dict(case_id=cid,benchmark_version='V2C-C-C5A-calibration-v1',query_text=q,
      family_id='c5a-'+pattern,pattern_id=pattern,operation_topology=topo,
      structural_component_id='c5a-structure-'+hashlib.sha256(topo.encode()).hexdigest()[:16],
      scope_type=c['scope'],workspace_type=MATRIX['scopes'][c['scope']]['workspace_type'],search_mode='SMART',
      decision_stratum=c['stratum'],expected_typed_decision=DECISIONS[c['stratum']],
      expected_executable=c['stratum'] in STRATA[:2],expected_hard_constraints=hard,
      expected_soft_preferences=soft,expected_semantic_remainder='; '.join(p['remainder'] for p in parts if p['remainder']),
      expected_ambiguity=ambiguity or [],expected_incomplete_fields=incomplete or [],
      expected_unsupported_fields=unsupported or [],expected_contradiction=contradiction or dict(present=False,fields=[],reason='No incompatible resolved supported operands.'),
      protected_entities=entities,
      capability_profile=dict(profile_id=c['scope']+'-frozen-v1',capabilities=copy.deepcopy(caps),canonical_reference='search_v2c_c5a_capability_matrix.json#'+c['scope']),
      review_status='UNREVIEWED',reviewer_type='INDEPENDENT_AUTHOR_PENDING_SEPARATE_REVIEW',
      label_confidence_or_review_notes=notice or 'Normative labels authored from the query and authorized specification; independent review pending.',
      metric_applicability=app,partition='calibration',example_class='CORE',author_id='c5a-independent-semantic-author',semantic_rationale=rationale)
    ROWS.append(row)
    return row

# Each scope has a separately composed twenty-intent plan. Every character is
# an active filter/preference, not padding to manipulate topology membership.
CLEAR={
 'GLOBAL': [
  'a r o topic','t a r','i j r o','i x r beg','t r x short','a i d ref','a l h o','t i j d','i j x r d','a n r short','t a i o','t x d beg','a j r h o','i x z o ref','a t r h o','j k d adv','t n r o','a i j x','i r o short','a t i x ref'],
 'PUBLIC_TENANT_PATRON':[
  'i r v y topic','a p w beg','t a f r','i j b y','r h p v','t x d f','a i y w','j x v short','a t d v','i r e f','t j p ref','a x b y','i j x r v','t r h g','a n d e','j k p f adv','t i y w v','a j r o short','i x z b y','a t i f v'],
 'PUBLIC_TENANT_STAFF':[
  'a i y p topic','t j f v','i j r b','a t w o','i x y w ref','a l h v','t i e p','j x g d','a r f short','t a x b','i j k y v','t r o beg','a n e v','j k x p adv','t a g y','i r h p v','a i j f','t x z o ref','i j e b','a t i r v'],
 'PRIVATE_TENANT_PATRON':[
  't a p r topic','i j y v','a x f d','i r h o','t i g v','a j p beg','i x z y w v','t r b short','a l h e','i j k d ref','t a f y','a i x v','j k r p','t n e o','a j g b','i r y w v','t i x p adv','a t r o','j x z f v','a i j e d'],
 'PRIVATE_TENANT_STAFF':[
  'i j e p topic','a t f b','t x y v','a i r o','j k x p ref','t l h g','a y w b','i r v beg','t a i e','j x f d','a n p v','i j k r short','t i o y','a j x e','i r h f b','t a g v','j k y w adv','a i z o','t r e p v','a t i j f'],
}
for scope in SCOPES:
  for i,plan in enumerate(CLEAR[scope]):
    c=ctx(scope,STRATA[0],i)
    parts=[op(x,c) for x in plan.split()]
    if not any(p['remainder'] for p in parts) and i%3==1: parts.append(op('topic',c))
    add(c,parts,f'clear-{scope.lower()}-{i+1:02d}',
      'All hard operands have a unique reading and are supported here. This plan combines '+', '.join(plan.split())+'; any preference is advisory, and the free topic is not a strict title.')

TYPO={
 'History':'Histroy','Physics':'Phsyics','Poetry':'Peotry','Mathematics':'Matheamtics','Fiction':'Fictoin','Ecology':'Ecolgoy','Philosophy':'Philosohpy','Biography':'Biogrpahy',
 'Community archives':'Community archvies','Quantum computing':'Quantum comupting','Climate change mitigation':'Climate chnage mitigation','Computer science':'Computer scinece','Water':'Wtaer','Transportation':'Transporattion','Economics':'Econmoics','Science':'Scinece','Education':'Educatoin',
 'Mystery':'Msytery','Neural Networks':'Neural Netwroks','Romance':'Roamnce','Wizards':'Wizrads','Detective Fiction':'Detecitve Fiction','V2CC Private Orchid':'V2CC Private Orhcid',
}
def safe_special(c):
    i=c['i'];s=c['s'];a=c['a'];t=c['t']
    choices=[
      (cl('rated at leat 4 stars',{'rating_min':4.0,'rating_min_exclusive':False}),'at leat','at least','misspelled inclusive minimum'),
      (cl('rated at msot 4.5 stars',{'rating_max':4.5,'rating_max_exclusive':False}),'at msot','at most','misspelled inclusive maximum'),
      (cl('rated gretaer than 3 stars',{'rating_min':3.0,'rating_min_exclusive':True}),'gretaer','greater','misspelled strict comparison'),
      (cl('rated exaclty 4 stars',{'rating_min':4.0,'rating_max':4.0,'rating_min_exclusive':False,'rating_max_exclusive':False}),'exaclty','exactly','misspelled equality operator'),
      (cl('rated betwen 3 and 4 stars, including the endpoints',{'rating_min':3.0,'rating_max':4.0,'rating_min_exclusive':False,'rating_max_exclusive':False}),'betwen','between','recoverable two-sided rating operator'),
      (cl('include subject "'+TYPO[s[0]]+'"',{'subjects':[s[0]]}),TYPO[s[0]],s[0],'recoverable canonical first-subject spelling'),
      (cl('include subject "'+TYPO[s[1]]+'"',{'subjects':[s[1]]}),TYPO[s[1]],s[1],'recoverable canonical second-subject spelling'),
      (cl('exclude category "'+TYPO[s[3]]+'"',{'exclude_subjects':[s[3]]}),TYPO[s[3]],s[3],'recoverable category-only exclusion spelling'),
      (cl('exclude category "'+TYPO[s[4]]+'"',{'exclude_subjects':[s[4]]}),TYPO[s[4]],s[4],'recoverable exclusion of a different canonical category'),
      (cl('onlien only',{'formats':['ONLINE'],'exclusive_formats':['ONLINE']}),'onlien','online','transposed format word'),
      (cl('digtial format',{'formats':['ONLINE']}),'digtial','digital','recoverable format synonym spelling'),
      (cl('online onyl',{'formats':['ONLINE'],'exclusive_formats':['ONLINE']}),'onyl','only','recoverable exclusivity operator'),
      (cl('prefer beginer explanations',soft={'level':'beginner'}),'beginer','beginner','recoverable advisory experience preference'),
      (cl('prefer advnaced treatments',soft={'level':'advanced'}),'advnaced','advanced','recoverable advisory depth preference'),
      (cl('prefer shrot works',soft={'length':'short'}),'shrot','short','recoverable advisory length preference'),
      (cl('prefer refrence works',soft={'purpose':'reference'}),'refrence','reference','recoverable advisory purpose preference'),
      (cl('exlcude every record containing the text "amber boiler"',{'exclude_terms':['amber boiler']}),'exlcude','exclude','recoverable broad textual negation'),
      (cl('titeld "'+t+'"',{'title_text':t},entities=[(t,'TITLE')]),'titeld','titled','recoverable explicit title introducer'),
      (cl('byy '+a,{'author_text':a},entities=[(a,'AUTHOR')]),'byy','by','recoverable author introducer'),
      (cl('include subject "'+s[0]+'" adn subject "'+s[1]+'"',{'subjects':[s[0],s[1]]}),'adn','and','recoverable conjunction of two required categories'),
    ]
    return choices[i]

SAFE={
 'GLOBAL':[
  'S a i o','t S x d','i S a short','S t j o','a S x beg',
  'S t r d','a S r x','t S l d','a S q ref','S a r i x',
  't S j x r','S a l h','S t r x o','S a i r d','t S l j o',
  'a S t r','S t i r o','S a i r d','S t j r o','S a r x d'],
 'PUBLIC_TENANT_PATRON':[
  'S t y p v','S a f b','i S y w o','S t g v','a S j p e',
  'S a r f v','t S y b','S a e d ref','t S r p','S a y f',
  't S r v','S i j e','S t f p v','S a j r b','t S g y d',
  'a S r e o','S a i y p','S a r f b','S t j y v','S t r p g'],
 'PUBLIC_TENANT_STAFF':[
  'S a g y d','t S i p e','a S j b v','S i f y p','t S x o v',
  'S t r p y','a S e f','t S r b','a S y w d','S t r f',
  'a S e v','S j x r','S a i f b','S t j y p','a S i r v',
  't S g e d','S t r p y','S a i f v','S t r b e','S a x p v'],
 'PRIVATE_TENANT_PATRON':[
  'S a t p v','S i j y d','t S f e b','S a x p g','i S t y v',
  'S t r f d','a S r p e','S t y w o','a S g b r','S a i e',
  't S j r v','S a x f','S t i r b','S a j y v','S t x p e',
  'S a i f v','S t j r b','S a x p e','S t r i d','S a y w p'],
 'PRIVATE_TENANT_STAFF':[
  'S t i f b','a S x e p','S a j y v','t S i g d','S a x b e',
  'S a r p v','t S g y d','a S l p e','S t r f v','S t a e',
  'a S j r g','S t i y','S a j p v','S t x r o','S a i g b',
  'S t r y p','S a t i v','S a r f o','S t j e b','S t a p v'],
}
for scope in SCOPES:
  for i,plan in enumerate(SAFE[scope]):
    c=ctx(scope,STRATA[1],i)
    special,bad,good,kind=safe_special(c)
    parts=[copy.deepcopy(special) if x=='S' else op(x,c) for x in plan.split()]
    if i%2==0: parts.append(op('topic',c))
    add(c,parts,f'safe-{kind.replace(" ","-")}-{scope.lower()}',
      f'A visible interpretation is required: {bad!r} is read as {good!r}. The surrounding request fixes the semantic role; the correction changes no invented entity and does not invent a missing value. All resulting constraints are supported in this scope.',
      notice=f'EXECUTABLE_WITH_NOTICE: interpret {bad!r} as {good!r}; show that correction. This is an author rationale, not a confidence prediction.')

def ambiguous_special(c):
    s,a,b,t,u=c['s'],c['a'],c['b'],c['t'],c['u']
    specs=[
      ('my rating note says "4", but I cannot remember whether that is an exact rating or a minimum', ['rating_min','rating_max'], ['exactly 4 stars','at least 4 stars'], 'rating-equality-versus-floor', []),
      ('my rating limit is 3 stars, but I cannot read whether the note says at least or at most', ['rating_min','rating_max'], ['minimum 3 stars','maximum 3 stars'], 'rating-floor-versus-ceiling', []),
      (f'exclude category "{s[0]}" and "{s[1]}" together; I cannot tell whether together means their intersection or either category', ['exclude_subjects'], ['exclude only records bearing both categories','exclude records bearing either category'], 'negative-set-intersection-versus-union', []),
      (f'my slip reads "titled {t} by {a}"; I cannot tell whether "by {a}" belongs inside the title or is an author credit', ['title_text','author_text'], [f'title {t}; author {a}',f'title {t} by {a}; author unspecified'], 'title-author-boundary', [(t,'TITLE_CANDIDATE'),(a,'AUTHOR_CANDIDATE')]),
      (f'by {a} and {b}; I cannot tell whether my note means a joint work or separate works by either writer', ['author_text'], ['both named people must be coauthors','either named writer is acceptable'], 'joint-authorship-versus-author-alternatives', [(a,'AUTHOR_CANDIDATE'),(b,'AUTHOR_CANDIDATE')]),
      (f'not category "{s[0]}" or "{s[1]}"; I lost the parentheses around the negative part', ['subjects','exclude_subjects'], [f'neither {s[0]} nor {s[1]}',f'either not {s[0]} or positively {s[1]}'], 'negation-or-scope', []),
      (f'include subject "{s[0]}" or "{s[1]}" and "{s[2]}"; my note has no grouping marks', ['subjects'], [f'{s[0]} OR ({s[1]} AND {s[2]})',f'({s[0]} OR {s[1]}) AND {s[2]}'], 'positive-category-grouping', []),
      (f'I want a book titled "{t}" or a book titled "{u}", but I have not chosen which title to search for', ['title_text'], [f'search only for {t}',f'search only for {u}'], 'unselected-title-intent', [(t,'TITLE_CANDIDATE'),(u,'TITLE_CANDIDATE')]),
      (f'include subject "{s[0]}" preferably and subject "{s[1]}"; I cannot remember whether preferably modifies both requirements', ['subjects'], ['both categories are soft preferences',f'{s[0]} is soft and {s[1]} is mandatory'], 'hard-soft-subject-attachment', []),
      ('my note says rated "four-ish", with no tolerance; I mean a rating filter but cannot decide how close counts', ['rating_min','rating_max'], ['ratings from 3.5 through 4.5','ratings from 3.9 through 4.1'], 'unspecified-approximate-rating-tolerance', []),
      (f'my two-author note lists {a} and {b} beside titles "{t}" and "{u}"; I cannot remember which author belongs to which title', ['author_text'], [f'{a} wrote {t}; {b} wrote {u}',f'{b} wrote {t}; {a} wrote {u}'], 'author-title-pairing-identity', [(a,'AUTHOR_CANDIDATE'),(b,'AUTHOR_CANDIDATE'),(t,'TITLE_CANDIDATE'),(u,'TITLE_CANDIDATE')]),
      ('my note says online, but I cannot remember whether that is mandatory access or merely a preference', ['formats','exclusive_formats'], ['require ONLINE access','prefer ONLINE access without filtering'], 'hard-soft-format-intent', []),
      (f'include subject "{s[0]}" and exclude category "{s[1]}" unless the subject is "{s[2]}"; I lost whether the exception overrides only the exclusion or the whole request', ['subjects','exclude_subjects'], ['the exception relaxes only the excluded category','the exception replaces the entire category condition'], 'exception-scope', []),
      (f'by {a}; my title note names "{t}" and "{u}" with a smudge where the choice mark was, so I do not know which is intended', ['title_text'], [f'title {t}',f'title {u}'], 'author-fixed-title-choice', [(a,'AUTHOR'),(t,'TITLE_CANDIDATE'),(u,'TITLE_CANDIDATE')]),
      ('the rating comparison says "over 4" or "at least 4"; I cannot read the crossed-out word', ['rating_min','rating_min_exclusive'], ['strictly greater than 4','greater than or equal to 4'], 'rating-boundary-inclusivity', []),
      (f'exclude "{s[0]}"; I cannot tell whether this means category membership or every occurrence of those words in catalogue text', ['exclude_subjects','exclude_terms'], [f'category-only exclusion of {s[0]}',f'broad text exclusion of {s[0]}'], 'canonical-category-versus-broad-text-negation', []),
      (f'by {a} / {b}; the slash is either a joint-author separator or a choice between writers, and I do not know which', ['author_text'], ['coauthored by both','one of the two authors, choice unresolved'], 'author-list-slash-intent', [(a,'AUTHOR_CANDIDATE'),(b,'AUTHOR_CANDIDATE')]),
      (f'titled {t}: {u}; my colon either joins one complete title or separates two title requests, and I cannot tell which', ['title_text'], [f'one full title {t}: {u}',f'two alternative title requests {t} and {u}'], 'title-colon-boundary', [(t,'TITLE_CANDIDATE'),(u,'TITLE_CANDIDATE')]),
      ('my rating note says 4 stars, but I have not decided whether the floor is mandatory or an aspiration', ['rating_min'], ['mandatory minimum rating of 4','soft preference for a rating of 4 or more'], 'hard-soft-rating-intent', []),
      (f'by {a} and {b}, excluding {a}; I cannot tell whether excluding means remove that author from the alternatives or reject any jointly authored record', ['author_text','exclude_terms'], [f'only {b} remains as an author alternative',f'joint works containing author text {a} are rejected'], 'author-alternative-exclusion-scope', [(a,'AUTHOR_CANDIDATE'),(b,'AUTHOR_CANDIDATE')]),
    ]
    text,fields,interpretations,name,entities=specs[c['i']]
    # No selected value is fabricated for the unresolved fragment.
    hard={'author_text':a} if c['i']==13 else {}
    return cl(text,hard=hard,entities=entities),fields,interpretations,name

AMBIG={
 'GLOBAL':[
  'S a i o','t S x d beg','S a r o','S i r d','S t r o',
  'S a t d','S a l o','S a r x','S t r d','S a i o ref',
  'S t r d','S a t r','S a r o','S r x d','S t i o',
  'S a r d','S t i r','S a r o','S a t x d','S t i r o'],
 'PUBLIC_TENANT_PATRON':[
  'S a f p y','S t v e d','S a r b f','S i r p v','S t r y d',
  'S a t f v','S a e p','S a r g v','S t y p','S a f b v',
  'S t r y o','S a i r v','S a t f p','S r g b v','S t j e p',
  'S a r f b','S t r y p','S a i e v','S a t f p','S t r g b'],
 'PUBLIC_TENANT_STAFF':[
  'S t f b v','S a i y p','S a t r v','S j g r d','S t i e p',
  'S a r b y','S t a f v','S a j p w','S a t r b','S t i g p',
  'S a t e v','S a j y f','S t r e d','S r i f p','S a t y v',
  'S t r g b','S i r e p','S a j f b','S t i y p','S t r e v'],
 'PRIVATE_TENANT_PATRON':[
  'S t a y p','S a j f d','S a r g v','S i r b e','S t x p v',
  'S a t e o','S a r g b','S a i y v','S t a p e','S a j b y',
  'S t r p v','S t a f e','S a r d g','S r i p v','S t j f b',
  'S a t r p','S t i f v','S a j r b','S a i e p','S t j f v'],
 'PRIVATE_TENANT_STAFF':[
  'S a i f v','S t y b ref','S a r e p','S j r f v','S t r y o',
  'S a g p e','S a t r v','S a j g b','S a t e v','S t i y d',
  'S a t r b','S t a i g','S t r y b','S r j f p','S a t e d',
  'S a r p v','S t j e b','S a i f p','S a t g v','S t i r b'],
}
for scope in SCOPES:
  for i,plan in enumerate(AMBIG[scope]):
    c=ctx(scope,STRATA[2],i)
    special,fields,choices,name=ambiguous_special(c)
    parts=[copy.deepcopy(special) if x=='S' else op(x,c) for x in plan.split()]
    if i%4==0: parts.append(op('topic',c))
    add(c,parts,f'ambiguous-{name}-{scope.lower()}',
      'The request explicitly leaves a material intent unresolved. Both supplied readings fit the fragment, so choosing one would invent user intent. Fixed operands elsewhere remain resolved.',
      ambiguity=[dict(fragment=special['text'],interpretations=choices,reason='The visible note/request does not select one of these materially different readings.')],unresolved=fields)

def incomplete_special(c):
    s=c['s'];tenant=c['scope']!='GLOBAL'
    # Ellipses here represent the user's explicitly unfinished value; the gold
    # deliberately contains no placeholder or guessed completion.
    specs=[
      (cl('rated at least ...; I have not supplied the minimum'),['rating_min'],'missing-rating-floor'),
      (cl('rated at most ...; I have not supplied the ceiling'),['rating_max'],'missing-rating-ceiling'),
      (cl('rated exactly ...; the rating value is missing'),['rating_min','rating_max'],'missing-rating-equality'),
      (cl('rated between ... and 4 stars, inclusive; the lower endpoint is missing',{'rating_max':4.0,'rating_max_exclusive':False}),['rating_min'],'missing-lower-rating-endpoint'),
      (cl('rated between 3 and ... stars, inclusive; the upper endpoint is missing',{'rating_min':3.0,'rating_min_exclusive':False}),['rating_max'],'missing-upper-rating-endpoint'),
      (cl('rated between two endpoints that I have not entered yet'),['rating_min','rating_max'],'missing-entire-rating-interval'),
      (cl('by ...; the author name is still blank'),['author_text'],'missing-author-name'),
      (cl('titled ...; I have not entered the title'),['title_text'],'missing-explicit-title'),
      (cl('include subject ...; the required category is still blank'),['subjects'],'missing-positive-category'),
      (cl('exclude category ...; the category name is missing'),['exclude_subjects'],'missing-negative-category'),
      (cl('exclude every record containing the text ...; I have not supplied that text'),['exclude_terms'],'missing-broad-exclusion-text'),
      (cl('by '+c['a'].split()[0]+' ...; the surname is unfinished'),['author_text'],'truncated-author-identity'),
      (cl('titled "'+c['t'].split()[0]+' ..."; the rest of the title is missing'),['title_text'],'truncated-title-literal'),
      (cl('include subject "'+s[0]+'" and one more subject that I have not named',{'subjects':[s[0]]}),['subjects'],'incomplete-positive-category-conjunction'),
      (cl('exclude category "'+s[3]+'" and another unnamed category',{'exclude_subjects':[s[3]]}),['exclude_subjects'],'incomplete-negative-category-conjunction'),
      (cl('titled ... by ...; both identifying values remain blank'),['title_text','author_text'],'missing-title-and-author'),
      (cl('titled ... and rated at least ...; neither the title nor the threshold has been filled in'),['title_text','rating_min'],'missing-identity-and-threshold'),
      (cl('include subject ... and exclude category ...; both category slots are blank'),['subjects','exclude_subjects'],'missing-positive-and-negative-categories'),
      (cl('use only the format I meant to specify: ...; I have left the format blank'),['formats','exclusive_formats'],'missing-mandatory-format'),
      (cl('by ... and exclude category ...; the author and rejected category are both unfinished'),['author_text','exclude_subjects'],'missing-author-and-excluded-category'),
    ]
    if tenant:
      specs[2]=(cl('published exactly in the year ...; the year is blank'),['year_min','year_max'],'missing-exact-publication-year')
      specs[3]=(cl('published between ... and 2018, inclusive; the starting year is missing',{'year_max':2018,'year_max_exclusive':False}),['year_min'],'missing-publication-lower-endpoint')
      specs[4]=(cl('published between 2010 and ..., inclusive; the ending year is missing',{'year_min':2010,'year_min_exclusive':False}),['year_max'],'missing-publication-upper-endpoint')
      specs[5]=(cl('language ...; the mandatory language value is blank'),['language'],'missing-required-language')
      specs[11]=(cl('use only the format ...; the access medium has not been entered'),['formats','exclusive_formats'],'missing-exclusive-access-medium')
      specs[12]=(cl('filter availability to ...; I have not specified the wanted availability state'),['availability'],'missing-availability-state')
      specs[18]=(cl('published between two years that are both still blank'),['year_min','year_max'],'missing-entire-publication-interval')
      specs[19]=(cl('by ... in language ...; I have not entered either value'),['author_text','language'],'missing-author-and-language')
    return specs[c['i']]

INCOMPLETE={
 'GLOBAL':[
  'S a i o','S t a d','S a x o beg','S a t d','S t i o',
  'S a i d','S t r o','S a r i d','S a t r o','S t a r d',
  'S a t r o','S t i r d','S a i r o','S a r d x','S t r o i',
  'S i r o','S a i o','S a t r d','S a t r i','S t r d'],
 'PUBLIC_TENANT_PATRON':[
  'S a i p y','S t g b v','S a r d f','S t i p r','S a j b v',
  'S t r p e','S t i r f v','S a j b y','S a t r f p','S a t r g v',
  'S t i r p','S a t r y','S a t r f b','S a r p y','S t r f v',
  'S i r p f','S a j b v','S a t r p','S a i r f b','S t i r p v'],
 'PUBLIC_TENANT_STAFF':[
  'S t a f b','S a i p v','S t r g o','S a j r b','S t a p f',
  'S a i r y v','S t j p f','S a i r b v','S a t r g v','S t a r p e',
  'S a j r f b','S a t r f','S t a r y d','S t r g b','S a i r p e',
  'S j r b v','S a i p e','S a t r f d','S t a i r p','S t j r b e'],
 'PRIVATE_TENANT_PATRON':[
  'S a t p e','S t i g v','S a j r p','S t r f b','S a i r o',
  'S t a r e','S t j r b y','S a i p g','S a t r p v','S t a r f b',
  'S a i r p y','S a t r v','S t a r f p','S a r g v','S t i r b y',
  'S j r f p','S a i b e','S a t r g p','S a j r v d','S t i r b y'],
 'PRIVATE_TENANT_STAFF':[
  'S t j f v','S a i b y','S t a r p','S a i r f v','S t j r b',
  'S a i p e','S t i r f','S a j r b e','S t a r p g','S a t r d y',
  'S t j r b v','S a t i r','S a t r g b','S t r p e','S a i r f v',
  'S i r b y','S a j p v','S a t r b','S t j r f p','S t i r o v'],
}
for scope in SCOPES:
  for i,plan in enumerate(INCOMPLETE[scope]):
    c=ctx(scope,STRATA[3],i)
    special,fields,name=incomplete_special(c)
    parts=[copy.deepcopy(special) if x=='S' else op(x,c) for x in plan.split()]
    if i%3==0: parts.append(op('topic',c))
    add(c,parts,f'incomplete-{name}-{scope.lower()}',
      'A mandatory operand is explicitly unfinished, rather than merely difficult to parse. No value is inferred from the remaining filters. Any completed endpoint or category is retained separately.',incomplete=fields)

def unsupported_special(c):
    # These are explicit mandatory filters, not mere topical mentions. No
    # unsupported predicate is copied into the enforceable hard-constraint gold.
    tenant=[
      (cl('require at most 180 pages as a hard page-count filter'),['page_count_max'],'page-count-ceiling'),
      (cl('require exactly edition 3 as a hard filter'),['edition'],'edition-number'),
      (cl('require a purchase price with a 22 dollar ceiling'),['price_max'],'purchase-price'),
      (cl('require a machine-verified difficulty level of B2'),['difficulty'],'mandatory-reading-difficulty'),
      (cl('require an audience age range of exactly 9 through 11'),['audience_age'],'mandatory-audience-age'),
      (cl('require the publisher to be "Cobalt Fern Press"',entities=[('Cobalt Fern Press','PUBLISHER')]),['publisher'],'publisher-identity'),
      (cl('require the translator credit "Virel Tansor"',entities=[('Virel Tansor','TRANSLATOR')]),['translator'],'translator-credit'),
      (cl('require the narrator credit "Elsen Mavora"',entities=[('Elsen Mavora','NARRATOR')]),['narrator'],'narrator-credit'),
      (cl('require the text to be unabridged, enforced as a filter'),['abridgement'],'unabridged-edition-state'),
      (cl('require full-color illustrations, enforced as a filter'),['illustration_color'],'illustration-color'),
      (cl('require hardcover binding rather than just any physical copy',{'formats':['PHYSICAL']}),['binding'],'specific-binding'),
      (cl('require a print size of at least 18 points'),['print_size_min'],'large-print-size'),
      (cl('require an audio running time below six hours'),['audio_duration_max'],'audio-duration'),
      (cl('require ISBN 9781999987654 as an exact identifier filter',entities=[('9781999987654','ISBN')]),['isbn'],'isbn-identifier'),
      (cl('require a CC BY-SA copyright license'),['license'],'reuse-license'),
      (cl('require digital files specifically encoded as EPUB',{'formats':['ONLINE']}),['file_type'],'digital-file-encoding'),
      (cl('require each digital download to be below 12 megabytes',{'formats':['ONLINE']}),['file_size_max'],'download-size'),
      (cl('require shelf location "West Alcove 8" as a catalogue filter',entities=[('West Alcove 8','LOCATION')]),['shelf_location'],'copy-shelf-location'),
      (cl('require inventory barcode "INV-ORV-742" as an exact filter',entities=[('INV-ORV-742','BARCODE')]),['inventory_barcode'],'inventory-barcode-in-human-search'),
      (cl('require verified screen-reader tagging as a mandatory access filter'),['accessibility_tagging'],'verified-accessibility-tagging'),
    ]
    global_specs=[
      (cl('require books published from 2021 onward'),['year_min'],'global-publication-floor'),
      (cl('require language French'),['language'],'global-language'),
      (cl('require books available to borrow immediately'),['availability'],'global-availability'),
      (cl('require physical format only'),['formats','exclusive_formats'],'global-physical-access'),
      (cl('require both physical and online formats for the same record'),['formats'],'global-both-access'),
      (cl('require publication before 1995 and language German'),['year_max','language'],'global-year-plus-language'),
      (cl('require records currently on loan to another reader'),['availability'],'global-loan-state'),
      tenant[0],tenant[1],tenant[2],tenant[3],tenant[4],tenant[5],tenant[6],tenant[15],tenant[16],
      (cl('require physical large-print copies with at least 20-point type'),['formats','print_size_min'],'global-print-format-plus-type-size'),
      (cl('require audio editions narrated by "Nivra Pelden"',entities=[('Nivra Pelden','NARRATOR')]),['audio_format','narrator'],'global-audio-and-narrator'),
      tenant[17],tenant[13],
    ]
    return (global_specs if c['scope']=='GLOBAL' else tenant)[c['i']]

UNSUPPORTED={
 'GLOBAL':[
  'S a i r o','S t a r d','S a t r x','S a r i','S t r x',
  'S a i r d','S t a r o','S a t r d','S t i r o','S a i r beg',
  'S t a r o','S a i r d','S t i r o','S a t r d','S a i r x',
  'S t a r','S a t r i','S t i r o','S a t r d','S a i r o'],
 'PUBLIC_TENANT_PATRON':[
  'S a i r p v','S t a y d','S a j r b','S t i r v','S a t f p',
  'S t r y p','S a i g v','S t a r b','S a j e o','S t i r p',
  'S a t r v','S a i r y','S t j f b','S a t r p','S i j r v',
  'S a t y f','S t i r v','S a j r o','S t a f b','S a i r p y'],
 'PUBLIC_TENANT_STAFF':[
  'S t a f b','S a i r p','S t j e v','S a t r d','S i j r y',
  'S a t g v','S t i r b','S a j y p','S t a r f','S a i e d',
  'S a j r y','S t i r b','S a t f v','S t i r p','S a j e b',
  'S t a r g','S a i r y','S t j f p','S a t r d','S i j r v'],
 'PRIVATE_TENANT_PATRON':[
  'S a t r p','S t i g v','S a j y b','S t a r f','S i j r p',
  'S a t e d','S t i r v','S a j f b','S t a r p','S i j e o',
  'S a t r g','S t i r b','S a j y p','S t a r v','S i j r f',
  'S a t y v','S t j r e','S a i r b','S t a f p','S i j r y'],
 'PRIVATE_TENANT_STAFF':[
  'S t i r b','S a t f p','S i j r v','S t a e o','S a i r y',
  'S t j r p','S a t g v','S i j e b','S a t r f','S t i r v',
  'S a t r e','S i j r d','S t a f b','S a i r y','S t j r p',
  'S a t r v','S i j e f','S t a r b','S a i r p','S t j y v'],
}
for scope in SCOPES:
  for i,plan in enumerate(UNSUPPORTED[scope]):
    c=ctx(scope,STRATA[4],i)
    special,fields,name=unsupported_special(c)
    parts=[copy.deepcopy(special) if x=='S' else op(x,c) for x in plan.split()]
    if i%4==1: parts.append(op('topic',c))
    add(c,parts,f'unsupported-{name}-{scope.lower()}',
      'The user makes this unsupported predicate mandatory: '+special['text']+'. Other listed predicates are independently supported. Returning an executable plan would falsely promise to enforce '+', '.join(fields)+'.',unsupported=fields)

def contradictory_special(c):
    s,a,t=c['s'],c['a'],c['t']; word=t.split()[1];surname=a.split()[1]
    def cr(text,hard,fields,name,reason,entities=None):
      return cl(text,hard=hard,entities=entities),fields,name,reason
    subject=cr(f'include subject "{s[0]}" and exclude that same category "{s[0]}"',{'subjects':[s[0]],'exclude_subjects':[s[0]]},['subjects','exclude_subjects'],'positive-negative-same-category','The same record must possess and lack the same category.')
    multi=cr(f'include subject "{s[0]}" and subject "{s[1]}" but exclude category "{s[1]}"',{'subjects':[s[0],s[1]],'exclude_subjects':[s[1]]},['subjects','exclude_subjects'],'required-conjunction-excluded-member','One member of a mandatory subject conjunction is forbidden.')
    title=cr(f'titled "{t}" but exclude every record containing the exact text "{t}"',{'title_text':t,'exclude_terms':[t]},['title_text','exclude_terms'],'strict-title-versus-broad-literal-exclusion','The required literal title necessarily contains the forbidden text.',[(t,'TITLE')])
    author=cr(f'by {a} but exclude every record containing the exact text "{a}"',{'author_text':a,'exclude_terms':[a]},['author_text','exclude_terms'],'required-author-versus-broad-literal-exclusion','The required author credit necessarily contains the forbidden text.',[(a,'AUTHOR')])
    titleword=cr(f'titled "{t}" but exclude every record containing the word "{word}"',{'title_text':t,'exclude_terms':[word]},['title_text','exclude_terms'],'strict-title-versus-word-exclusion','A word in the required title is forbidden anywhere in the record.',[(t,'TITLE')])
    surnamecase=cr(f'by {a} but exclude every record containing the word "{surname}"',{'author_text':a,'exclude_terms':[surname]},['author_text','exclude_terms'],'required-author-versus-surname-exclusion','The required author surname is forbidden anywhere in the record.',[(a,'AUTHOR')])
    rating0=cr('rated at least 4 stars and rated at most 3 stars',{'rating_min':4.0,'rating_max':3.0,'rating_min_exclusive':False,'rating_max_exclusive':False},['rating_min','rating_max'],'reversed-inclusive-rating-interval','The inclusive minimum exceeds the inclusive maximum.')
    rating1=cr('rated over 4 stars and rated at most 4 stars',{'rating_min':4.0,'rating_max':4.0,'rating_min_exclusive':True,'rating_max_exclusive':False},['rating_min','rating_max','rating_min_exclusive'],'strict-lower-rating-empty-boundary','The lower endpoint is excluded while the ceiling is the same value.')
    rating2=cr('rated at least 4 stars and rated below 4 stars',{'rating_min':4.0,'rating_max':4.0,'rating_min_exclusive':False,'rating_max_exclusive':True},['rating_min','rating_max','rating_max_exclusive'],'strict-upper-rating-empty-boundary','The upper endpoint is excluded while the floor is the same value.')
    rating3=cr('rated above 4 stars and below 4 stars',{'rating_min':4.0,'rating_max':4.0,'rating_min_exclusive':True,'rating_max_exclusive':True},['rating_min','rating_max','rating_min_exclusive','rating_max_exclusive'],'both-rating-boundaries-open-at-same-point','The only possible boundary point is excluded by both operators.')
    online=cr('require online format and exclude online format',{'formats':['ONLINE'],'excluded_formats':['ONLINE']},['formats','excluded_formats'],'required-format-excluded','ONLINE is a supported operand in every scope, and is both required and excluded.')
    onlineonly=cr('require online only and also exclude online format',{'formats':['ONLINE'],'exclusive_formats':['ONLINE'],'excluded_formats':['ONLINE']},['formats','exclusive_formats','excluded_formats'],'exclusive-format-itself-forbidden','The sole permitted access format is explicitly forbidden.')
    doublecat=cr(f'include subject "{s[0]}" and subject "{s[1]}"; exclude category "{s[0]}" and category "{s[1]}"',{'subjects':[s[0],s[1]],'exclude_subjects':[s[0],s[1]]},['subjects','exclude_subjects'],'two-independent-category-clashes','Both mandatory categories are independently excluded.')
    titleauthor=cr(f'titled "{t}" by {a}; exclude every record containing "{t}" and every record containing "{a}"',{'title_text':t,'author_text':a,'exclude_terms':[t,a]},['title_text','author_text','exclude_terms'],'both-required-entities-broadly-forbidden','Each of two required literal entities independently triggers a broad exclusion.',[(t,'TITLE'),(a,'AUTHOR')])
    def join(left,right,name):
      p=cl(left[0]['text']+'; '+right[0]['text'],hard=merge([left[0],right[0]])[0],entities=left[0]['entities']+right[0]['entities'])
      return p,list(dict.fromkeys(left[1]+right[1])),name,left[3]+' '+right[3]
    globalspec=[rating0,rating1,rating2,subject,multi,title,author,titleword,surnamecase,
      join(subject,rating0,'category-clash-and-reversed-rating'),doublecat,
      join(title,rating1,'title-exclusion-and-strict-rating'),
      join(author,multi,'author-exclusion-and-subject-clash'),
      join(titleword,subject,'title-word-exclusion-and-category-clash'),titleauthor,
      join(doublecat,rating2,'two-category-clashes-and-open-rating-ceiling'),online,onlineonly,
      join(online,subject,'format-clash-and-category-clash'),rating3]
    if c['scope']=='GLOBAL': return globalspec[c['i']]
    year0=cr('published from 2020 onward but published no later than 2015',{'year_min':2020,'year_max':2015,'year_min_exclusive':False,'year_max_exclusive':False},['year_min','year_max'],'reversed-inclusive-publication-interval','The supported earliest year is later than the supported latest year.')
    year1=cr('published after 2016 but published no later than 2016',{'year_min':2016,'year_max':2016,'year_min_exclusive':True,'year_max_exclusive':False},['year_min','year_max','year_min_exclusive'],'open-publication-floor-meets-closed-ceiling','The only possible endpoint is excluded by the supported lower comparison.')
    year2=cr('published from 2016 onward but published before 2016',{'year_min':2016,'year_max':2016,'year_min_exclusive':False,'year_max_exclusive':True},['year_min','year_max','year_max_exclusive'],'closed-publication-floor-meets-open-ceiling','The only possible endpoint is excluded by the supported upper comparison.')
    physical=cr('require physical format and exclude physical format',{'formats':['PHYSICAL'],'excluded_formats':['PHYSICAL']},['formats','excluded_formats'],'physical-format-required-and-excluded','The same supported physical format is required and forbidden.')
    both=cr('require both physical and online formats but exclude physical format',{'formats':['BOTH'],'excluded_formats':['PHYSICAL']},['formats','excluded_formats'],'both-access-versus-excluded-physical-member','Requiring both access forms requires the physical member which is forbidden.')
    tenant=[rating0,rating1,rating2,subject,multi,title,author,year0,year1,year2,online,physical,both,
      join(subject,year0,'category-clash-and-reversed-publication'),
      join(rating1,year2,'two-supported-empty-numeric-intervals'),titleauthor,
      join(physical,subject,'physical-clash-and-category-clash'),doublecat,
      join(titleword,rating3,'title-word-exclusion-and-two-open-rating-bounds'),
      join(online,subject,'online-clash-and-category-clash')]
    return tenant[c['i']]

CONTRADICTORY={
 'GLOBAL':[
  'S a i o','S t a d','S a x o beg','S a t r d','S a r o',
  'S a r d','S t r o','S a i r','S t j r d','S a t o',
  'S a t r d','S a i o','S t r d','S a r o','S i r d',
  'S a t o','S a t r i','S a t r x','S a t r','S a t i o'],
 'PUBLIC_TENANT_PATRON':[
  'S a i p v','S t f b','S a j y o','S a t r p','S t r g v',
  'S a r b y','S t r f p','S a t r o','S a i r p','S t j f v',
  'S a t r y','S a t r f','S a t r v','S a t r p','S a t i b',
  'S i r p v','S a t r g','S a t r b','S a i p v','S a t r e'],
 'PUBLIC_TENANT_STAFF':[
  'S t a f b','S a i p v','S t j g d','S a t r v','S a r e b',
  'S a j r p','S t i r f','S a t r b','S t i r v','S a j r p',
  'S a t r g','S a t r y','S a t i r','S a t r f','S a t i p',
  'S j r b y','S a t r e','S a t r g','S a j f b','S a t r v'],
 'PRIVATE_TENANT_PATRON':[
  'S a t p y','S t i g v','S a j f b','S a t r o','S a r p v',
  'S a i r b','S t j r e','S a t r f','S a i r b','S t j r p',
  'S a t r v','S a t i r','S a t r y','S a t r b','S a t j p',
  'S i r g v','S a t r f','S a t r e','S a i p y','S a t r g'],
 'PRIVATE_TENANT_STAFF':[
  'S t i f v','S a t p y','S a j b e','S a t r f','S t r p y',
  'S a i r v','S t j r b','S a t i r','S a j r p','S t i r f',
  'S a t r e','S a t r g','S a t j r','S a t r p','S a t i v',
  'S j r b e','S a t r y','S a t r f','S a j b v','S a t r e'],
}
for scope in SCOPES:
  for i,plan in enumerate(CONTRADICTORY[scope]):
    c=ctx(scope,STRATA[5],i)
    special,fields,name,reason=contradictory_special(c)
    parts=[copy.deepcopy(special) if x=='S' else op(x,c) for x in plan.split()]
    if i%4==2: parts.append(op('topic',c))
    add(c,parts,f'contradictory-{name}-{scope.lower()}',
      reason+' Every contradictory operand is independently supported in this frozen scope; no unsupported request is promoted to a contradiction.',
      contradiction=dict(present=True,fields=fields,reason=reason))

# Expand clear pattern identifiers into meaningful operation names rather than
# opaque serial numbers. This does not change any query or normative label.
OP_NAMES={
 'topic':'topical-relevance','a':'author-credit','t':'strict-title','i':'subject-a','j':'subject-b','k':'subject-c',
 'x':'category-exclusion-a','z':'category-exclusion-b','n':'broad-text-exclusion','r':'inclusive-rating-floor',
 'l':'strict-rating-floor','h':'rating-ceiling','q':'exact-rating','o':'online-exclusivity','d':'online-access',
 'p':'physical-exclusivity','b':'both-access','v':'current-availability','y':'publication-floor','w':'strict-publication-ceiling',
 'e':'exact-publication-year','f':'french-language','g':'german-language','beg':'beginner-preference',
 'adv':'advanced-preference','short':'short-preference','ref':'reference-preference',
}
for row in ROWS:
    if row['decision_stratum']=='CLEAR_EXECUTABLE':
      ix=int(row['case_id'].rsplit('-',1)[1])-1
      plan=CLEAR[row['scope_type']][ix]
      name='clear-'+'-with-'.join(OP_NAMES[p] for p in plan.split())
      row['family_id']='c5a-'+name
      row['pattern_id']=name
      row['semantic_rationale']='A separately composed conjunction of '+', '.join(OP_NAMES[p] for p in plan.split())+'. Every mandatory operand is supported in this scope; preferences remain advisory and free topical words are not a strict title.'

assert len(ROWS)==600
denied=[dict(case_id=r['case_id'],query_text=r['query_text'],topology=r['operation_topology']) for r in ROWS if r['operation_topology'] in BRIEF['development_topology_denylist']]
if denied:
    raise AssertionError(json.dumps({'development_topology_collisions':denied},indent=2))
CORE=copy.deepcopy(ROWS)
DERIVATIVE_PREFIXES=['Please locate books ','Look for books ','Help me find books ','Show books ','I am looking for books ']
for scope in SCOPES:
  for stratum in STRATA:
    bases=[r for r in CORE if r['scope_type']==scope and r['decision_stratum']==stratum]
    for v,ix in enumerate([0,4,8,12,16]):
      parent=bases[ix]
      row=copy.deepcopy(parent)
      prefix=DERIVATIVE_PREFIXES[v]
      row['query_text']=prefix+parent['query_text'][len('Find books '):]
      row['case_id']=parent['case_id']+f'-D{v+1}'
      row['parent_core_id']=parent['case_id']
      row['example_class']='DERIVATIVE'
      row['review_status']='UNREVIEWED'
      row['reviewer_type']='UNREVIEWED_DERIVATIVE_NO_INDEPENDENT_REVIEW'
      row['label_confidence_or_review_notes']='UNREVIEWED derivative prefix paraphrase. Labels are inherited from its parent, not independently reviewed. Never count this as an independently reviewed core case.'
      row['semantic_rationale']='Derivative wording variant of '+parent['case_id']+'. The active intent clauses and scope are unchanged. This row supplies no independent core coverage.'
      delta=len(prefix)-len('Find books ')
      for entity in row['protected_entities']:
        entity['start']+=delta;entity['end']+=delta
      assert topology(row['query_text'])==row['operation_topology']
      ROWS.append(row)

# Mechanical checks only. They do not decide normative semantics or read any
# predictions, confidence, policy, heldout query, production code, or old report.
required=BRIEF['schema_required']+[x.split(' ')[0] for x in BRIEF['extra_required'] if not x.startswith('parent_core_id')]
query_seen=set();id_seen=set();counts=Counter();patterns=defaultdict(set);topos=Counter()
for row in ROWS:
    assert all(k in row for k in required),set(required)-row.keys()
    assert row['case_id'] not in id_seen
    assert row['query_text'] not in query_seen
    id_seen.add(row['case_id']);query_seen.add(row['query_text'])
    key=(row['scope_type'],row['decision_stratum'],row['example_class'])
    counts[key]+=1
    if row['example_class']=='CORE': patterns[key[:2]].add(row['pattern_id'])
    assert row['review_status']=='UNREVIEWED'
    assert row['partition']=='calibration' and row['search_mode']=='SMART'
    actual=topology(row['query_text'])
    assert actual==row['operation_topology'] and actual not in BRIEF['development_topology_denylist']
    assert row['structural_component_id']=='c5a-structure-'+hashlib.sha256(actual.encode()).hexdigest()[:16]
    topos[actual]+=1
    for ent in row['protected_entities']:
      assert row['query_text'][ent['start']:ent['end']]==ent['text']
    hard=row['expected_hard_constraints'];caps=MATRIX['scopes'][row['scope_type']]['capabilities']
    vocab=MATRIX['scopes'][row['scope_type']]['subjects']
    for f in ['subjects','exclude_subjects']:
      assert all(x in vocab for x in hard.get(f,[])),(row['case_id'],f,hard[f])
    if not caps['year']: assert not any(f in hard for f in ['year_min','year_max'])
    if not caps['language']: assert 'language' not in hard
    if not caps['availability']: assert 'availability' not in hard
    for f in ['formats','exclusive_formats','excluded_formats']:
      assert all(x in caps['formats'] for x in hard.get(f,[])),(row['case_id'],f,hard.get(f))
    assert not set(row['expected_unsupported_fields']) & hard.keys()
    assert row['expected_executable']==(row['decision_stratum'] in STRATA[:2])
    assert row['expected_contradiction']['present']==(row['decision_stratum']=='CONTRADICTORY')
for scope in SCOPES:
  for stratum in STRATA:
    assert counts[(scope,stratum,'CORE')]==20
    assert counts[(scope,stratum,'DERIVATIVE')]==5
    assert len(patterns[(scope,stratum)])>=4

out=ROOT/'reports/search_v2c_c5a_author_draft.jsonl'
payload=''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in ROWS)
out.write_text(payload,encoding='utf-8',newline='\n')
digest=hashlib.sha256(out.read_bytes()).hexdigest()
log={
 'author_id':'c5a-independent-semantic-author','status':'DRAFT_ALL_UNREVIEWED',
 'authorized_inputs':['reports/search_v2c_c5a_author_brief.json','reports/search_v2c_c5a_capability_matrix.json'],
 'outputs':['reports/search_v2c_c5a_author_draft.jsonl','reports/search_v2c_c5a_author_log.json','scripts/search_v2c_c5a_author.py'],
 'draft_sha256':digest,'core_count':len(CORE),'derivative_count':len(ROWS)-len(CORE),'total_count':len(ROWS),
 'label_source':'Independent authored intent plans and supplied normative rules, before any parser output.',
 'no_parser_or_evaluator_used':True,'no_predictions_or_confidence_used':True,'no_heldout_or_old_corpus_access':True,
 'authoring_method':'Individually composed active intent plans, rendered through a small author-owned clause vocabulary. Core count is supported by material differences in the conjunctive request, uncertainty role, ambiguity, missing operand, unsupported predicate, or contradiction; lexical names/numbers never establish independent coverage. Clause reuse is disclosed for independent review.',
 'review_caveat':'UNREVIEWED is a literal status for all600 core rows pending the separate independent reviewer. The150 derivative paraphrases are never independent core evidence. Sealed audit may discard collisions; this author has neither accessed sealed content nor inferred forbidden sealed structures.',
 'mechanical_validation':['required fields','case and query uniqueness','20 CORE and5 DERIVATIVE per cell','at least4 semantic pattern identifiers per cell','scope-specific canonical subject membership','no unsupported field placed in hard gold','frozen capability compatibility','protected entity offsets','actual ordered presence topology and DEVELOPMENT denylist exclusion','structural component hash'],
 'coverage':[dict(scope_type=s,decision_stratum=t,core=counts[(s,t,'CORE')],derivative=counts[(s,t,'DERIVATIVE')],authored_semantic_patterns=len(patterns[(s,t)])) for s in SCOPES for t in STRATA],
 'operation_topologies':dict(sorted(topos.items())),
 'limitations':['No non-SMART case is claimed as new isolated calibration: those structural families were already exposed in DEVELOPMENT.','GLOBAL cannot enforce year, language, availability, PHYSICAL or BOTH, so these remain unsupported rather than executable or contradictory.','No numerical target confidence is authored. Correction notices express independent semantic interpretations.','Exact production preferences and availability encodings may require a lossless review adapter; the human semantics are explicit.','No claim of review acceptance or survival of sealed-family isolation is made before those independent stages.'],
 'schema_adaptations':{'expected_typed_decision':'EXECUTABLE_WITH_NOTICE for genuinely recoverable spelling/operator interpretations','availability':'AVAILABLE_NOW means available for access now; no physical-copy-only promise is inferred from a generic availability clause','expected_soft_preferences':'level, length and purpose keys have literal advisory meanings','metric_applicability':'per-slot status/reason objects; unresolved slots are not fabricated gold','family_id':'meaningful authored intent interaction; operation topology separately hashed'},
}
(ROOT/'reports/search_v2c_c5a_author_log.json').write_text(json.dumps(log,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({'output':str(out),'sha256':digest,'core':len(CORE),'derivative':len(ROWS)-len(CORE),'unique_topologies':len(topos),'cells':len(patterns)},indent=2))

