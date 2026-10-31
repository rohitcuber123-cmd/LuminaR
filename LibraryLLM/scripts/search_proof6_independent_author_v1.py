"""Independent, blind, prose-authored normative population. No parser import or invocation."""
import ast
import collections
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
BRIEF = ROOT / 'reports/search_proof6_blind_author_brief.json'
C2 = ROOT / 'scripts/search_v2c_c2_benchmark.py'
brief = json.loads(BRIEF.read_text(encoding='utf-8'))

# Compile only these two independently inspected pure helpers; module imports and
# all other source nodes, including main and historical rows, are never executed.
tree = ast.parse(C2.read_text(encoding='utf-8'))
nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {'normalized', 'mode', 'structure'}]
assert {n.name for n in nodes} == {'normalized', 'mode', 'structure'}
assert all(not any(isinstance(v, (ast.Import, ast.ImportFrom)) for v in ast.walk(n)) for n in nodes)
namespace = {'re': re, 'unicodedata': unicodedata}
exec(compile(ast.Module(body=nodes, type_ignores=[]), '<pure-c2-helpers>', 'exec'), namespace)
structure = namespace['structure']

FAMILIES = []
def add(fid, decision, features, query, hard=None, *, sort='RELEVANCE', soft=None,
        unresolved=None, unadapted=None, roles=None, why='', completion=None):
    FAMILIES.append(dict(fid=fid, decision=decision, features=features, query=query,
                         hard=hard or {}, sort=sort, soft=soft or [], unresolved=unresolved or [],
                         unadapted=unadapted or [], roles=roles or [], why=why, completion=completion))

def role(source_text, field, kind='MANDATORY_SEARCH_CONDITION', modality='MUST'):
    return dict(source_text=source_text, field=field, role=kind, modality=modality,
                mandatory=modality in {'MUST', 'MUST_NOT'})

def preference(text, value):
    return {'source_text': text, 'preference': value, 'modality': 'SHOULD'}

add('e01-intersect-owned-strings', 'EXECUTABLE', 'rating,author,title,format,sort',
    'Find online books by "Nera Vell" titled "The Copper Orchard", rated at least 3.6. Sort: title.',
    dict(author_text='Nera Vell', title_text='The Copper Orchard', formats=['ONLINE'], rating_min=3.6), sort='TITLE',
    roles=[role('by "Nera Vell"','author_text'), role('titled "The Copper Orchard"','title_text')],
    why='Author and title are separate literal contains operands intersected with an inclusive rating floor and supported online format; no bibliography identity is assumed.')
add('e02-text-exclusion-under-ceiling', 'EXECUTABLE', 'rating,negative,format,sort',
    'Keep online books rated no more than 4.2; exclude the whole word "fossil" from searchable text. Sort: title.',
    dict(formats=['ONLINE'],rating_max=4.2,exclude_terms=['fossil']),sort='TITLE',
    roles=[role('exclude the whole word "fossil"','exclude_terms','EXPLICIT_EXCLUSION','MUST_NOT')],
    why='An inclusive score ceiling and a whole-word text exclusion are supported; the exclusion is neither a category nor a negative author predicate.')
add('e03-classified-literal-title', 'EXECUTABLE', 'title,include,format,sort',
    'Within category Fiction, show online books titled "River Glass". Sort: title.',
    dict(subjects=['Fiction'],title_text='River Glass',formats=['ONLINE']),sort='TITLE',
    roles=[role('category Fiction','subjects'),role('titled "River Glass"','title_text')],
    why='Fiction is present in every supplied vocabulary. Category, online format, and owned title substring intersect without a capability adaptation.')
add('e04-quoted-topic-and-advisory-level', 'EXECUTABLE', 'rating,negative,format,preference',
    'Search for "brass sundial" in online books rated above 2.8, without the whole word "replica". Prefer an introduction.',
    dict(exact_text='brass sundial',formats=['ONLINE'],rating_min=2.8,rating_min_exclusive=True,exclude_terms=['replica']),
    soft=[preference('Prefer an introduction','introductory')],
    roles=[role('"brass sundial"','exact_text','QUOTED_LITERAL'),role('Prefer an introduction','soft_preferences','OPTIONAL_PREFERENCE','SHOULD')],
    why='The unowned quotation remains literal; above is strict. Introductory treatment is advisory and must not become a hard audience filter.')
add('e05-background-versus-preference', 'EXECUTABLE', 'author,title,include,preference,sort',
    'My earlier seminar used advanced monographs, which explains my reading habits. This time include category Fiction and books by "Evin Sore" titled "Lantern Wake". Prefer an introduction; sort: title.',
    dict(subjects=['Fiction'],author_text='Evin Sore',title_text='Lantern Wake'),sort='TITLE',
    soft=[preference('Prefer an introduction','introductory')],
    roles=[role('My earlier seminar used advanced monographs','soft_preferences','BACKGROUND_EXPLANATION','NON_OPERATIVE'),role('Prefer an introduction','soft_preferences','OPTIONAL_PREFERENCE','SHOULD')],
    why='The former seminar is background rather than an advanced-level demand. The present category and both owned strings are mandatory; only the current introductory preference is advisory.')

add('n01-canonical-transposition-repair', 'EXECUTABLE_WITH_NOTICE', 'rating,author,include,format,sort',
    'Use category "Fictoin"; that spelling is a transposition of Fiction, so correct it. Find online books by "Lera Moss" rated at least 3.1. Sort: title.',
    dict(subjects=['Fiction'],formats=['ONLINE'],author_text='Lera Moss',rating_min=3.1),sort='TITLE',
    roles=[role('that spelling is a transposition of Fiction, so correct it','subjects','CORRECTION_INSTRUCTION')],
    why='The user explicitly identifies the intended canonical spelling, which exists in all five scopes. Preserve the repair notice while applying the other filters.')
add('n02-repaired-title-field-label', 'EXECUTABLE_WITH_NOTICE', 'author,title,include,format,sort',
    'The label "titel" below is a typo for title; repair that label: titled "Ash Compass". Include category Fiction, online books, and books by "Olan Reeve". Sort: title.',
    dict(title_text='Ash Compass',subjects=['Fiction'],formats=['ONLINE'],author_text='Olan Reeve'),sort='TITLE',
    roles=[role('The label "titel" below is a typo for title; repair that label','title_text','CORRECTION_INSTRUCTION')],
    why='The source supplies a unique correction to a field label; the title string itself remains untouched. This correction merits notice and does not establish an author identity.')
add('n03-repaired-rating-label', 'EXECUTABLE_WITH_NOTICE', 'rating,title,negative,include,sort',
    'I wrote "raitng" for rating; repair the field label and use a minimum of 3.3. Include category Fiction, titled "Quiet Estuary", and exclude the whole word "abridged". Sort: title.',
    dict(rating_min=3.3,subjects=['Fiction'],title_text='Quiet Estuary',exclude_terms=['abridged']),sort='TITLE',
    roles=[role('I wrote "raitng" for rating; repair the field label','rating_min','CORRECTION_INSTRUCTION')],
    why='An explicit field spelling repair is source-owned. The rating floor, positive category, title contains string, and text exclusion remain resolved and executable with notice.')
add('n04-repaired-author-label', 'EXECUTABLE_WITH_NOTICE', 'author,negative,include,format,preference',
    'Repair my field label "authro" to author: books by "Tavi Mere". Include category Fiction and online access, without the whole word "pirate". Prefer advanced treatment.',
    dict(author_text='Tavi Mere',subjects=['Fiction'],formats=['ONLINE'],exclude_terms=['pirate']),
    soft=[preference('Prefer advanced treatment','advanced')],
    roles=[role('Repair my field label "authro" to author','author_text','CORRECTION_INSTRUCTION'),role('Prefer advanced treatment','soft_preferences','OPTIONAL_PREFERENCE','SHOULD')],
    why='Repair only the explicitly misspelled field name, retain the source string, and report notice. The optional level remains distinct from mandatory constraints.')
add('n05-repaired-sort-label-with-literal-ellipsis', 'EXECUTABLE_WITH_NOTICE', 'title,negative,include,preference,sort',
    'My label "srot" means sort; repair its spelling and order alphabetically on title. Include category Fiction, titled "...", without the whole word "retelling". Prefer an introduction.',
    dict(subjects=['Fiction'],title_text='...',exclude_terms=['retelling']),sort='TITLE',
    soft=[preference('Prefer an introduction','introductory')],
    roles=[role('My label "srot" means sort; repair its spelling','sort','CORRECTION_INSTRUCTION'),role('titled "..."','title_text','QUOTED_LITERAL')],
    why='The correction targets the sorting label. The nonempty field-owned ellipsis is a literal title operand, not an absent title; the repair is executable with notice.')

add('a01-cross-field-mandatory-union', 'AMBIGUOUS', 'author,title,negative,sort',
    'Find books by "Sela Wynn" or titled "Copper Orchard"; I have left the choice between those two routes undecided. Exclude the whole word "fossil". Sort: title.',
    dict(author_text='UNRESOLVED',title_text='UNRESOLVED',exclude_terms=['fossil']),sort='TITLE',unresolved=['author_text','title_text'],
    unadapted=['Mandatory alternative between an author contains operand and a title contains operand.'],
    roles=[role('by "Sela Wynn" or titled "Copper Orchard"','author_text','UNRESOLVED_RELATION_OR_ALTERNATIVE','UNKNOWN')],
    why='The common text exclusion resolves, but choosing one cross-field mandatory route or silently conjoining both changes the source intent.')
add('a02-unresolved-rating-bound-choice', 'AMBIGUOUS', 'rating,title,negative,preference,sort',
    'Use titled "Amber Causeway", exclude the whole word "tourism", and prefer an introduction. The mandatory minimum rating is either 3.2 or 4.1; I still need to choose. Sort: title.',
    dict(title_text='Amber Causeway',exclude_terms=['tourism'],rating_min='UNRESOLVED'),sort='TITLE',unresolved=['rating_min'],
    soft=[preference('prefer an introduction','introductory')],
    unadapted=['Mandatory rating floor alternative: 3.2 or 4.1, undecided.'],
    roles=[role('either 3.2 or 4.1','rating_min','UNRESOLVED_RELATION_OR_ALTERNATIVE','UNKNOWN')],
    why='The source explicitly leaves the scalar floor undecided; the title, negative word, ordering, and preference are common resolved parts.')
add('a03-negative-domain-choice', 'AMBIGUOUS', 'negative,include,preference,sort',
    'Exclude Fiction, but I have yet to decide whether that means the category or the whole word in searchable text. Prefer advanced treatment. Sort: title.',
    dict(exclude_subjects='UNRESOLVED',exclude_terms='UNRESOLVED'),sort='TITLE',unresolved=['exclude_subjects','exclude_terms'],
    soft=[preference('Prefer advanced treatment','advanced')],
    unadapted=['Negative domain is undecided between canonical category exclusion and whole-word text exclusion.'],
    roles=[role('whether that means the category or the whole word in searchable text','exclude_subjects','UNRESOLVED_RELATION_OR_ALTERNATIVE','UNKNOWN')],
    why='The two exclusion domains are distinct native operations, even though Fiction is canonical. Neither domain is common to both readings.')
add('a04-modality-not-yet-chosen', 'AMBIGUOUS', 'author,format,preference,sort',
    'Online books by "Mira Sol"; sort: title. For advanced treatment, I cannot yet say whether it is mandatory or merely a preference. Keep that choice open.',
    dict(author_text='Mira Sol',formats=['ONLINE']),sort='TITLE',
    unadapted=['Unresolved modality for advanced treatment: mandatory requirement versus optional preference.'],
    roles=[role('whether it is mandatory or merely a preference','soft_preferences','UNRESOLVED_RELATION_OR_ALTERNATIVE','UNKNOWN')],
    why='The source makes the strength of the advanced-treatment condition unresolved. It is unsafe either to impose an audience requirement or assume a soft preference.')
add('a05-title-alternative-with-common-intersection', 'AMBIGUOUS', 'rating,author,title,include,format,preference',
    'Include category Fiction: online books by "Rian Loam", rated at least 3.7. The title must contain either "Moth Harbor" or "Winter Reed", with the intended one still undecided. Prefer an introduction.',
    dict(subjects=['Fiction'],formats=['ONLINE'],author_text='Rian Loam',rating_min=3.7,title_text='UNRESOLVED'),unresolved=['title_text'],
    soft=[preference('Prefer an introduction','introductory')],
    unadapted=['Mandatory undecided alternatives within title contains: Moth Harbor / Winter Reed.'],
    roles=[role('either "Moth Harbor" or "Winter Reed"','title_text','UNRESOLVED_RELATION_OR_ALTERNATIVE','UNKNOWN')],
    why='This is an unresolved intra-field operand choice; the author, category, format and score are common resolved constraints, with no invented disjunction.')

add('i01-missing-score-floor', 'INCOMPLETE', 'rating,author,preference,sort',
    'Books by "Oren Vale", rated at least [value omitted]. Prefer an introduction. Sort: title.',
    dict(author_text='Oren Vale',rating_min='UNRESOLVED'),sort='TITLE',unresolved=['rating_min'],
    soft=[preference('Prefer an introduction','introductory')],
    roles=[role('[value omitted]','rating_min','MISSING_OPERAND_PLACEHOLDER')],
    why='A mandatory numeric floor is explicitly absent. The author and advisory level do not supply that missing number.',completion=('rating_min',3.4))
add('i02-missing-author-amid-resolved-title', 'INCOMPLETE', 'author,title,negative,preference',
    'Find books by [author omitted], titled "Salt Lattice", without the whole word "almanac". Prefer advanced treatment.',
    dict(author_text='UNRESOLVED',title_text='Salt Lattice',exclude_terms=['almanac']),unresolved=['author_text'],
    soft=[preference('Prefer advanced treatment','advanced')],
    roles=[role('[author omitted]','author_text','MISSING_OPERAND_PLACEHOLDER')],
    why='The owned author slot is absent while the title and exclusion are complete. A proposed completion may fill only the missing author field.',completion=('author_text','Luma Fen'))
add('i03-independent-missing-title-beside-ellipsis', 'INCOMPLETE', 'rating,title,preference,sort',
    'The title must contain "..." literally. I also require a second title substring, whose value I omitted. Require a rating of at least 3.5, prefer an introduction, and sort: title.',
    dict(title_text='...',rating_min=3.5),sort='TITLE',
    soft=[preference('prefer an introduction','introductory')],
    unadapted=['A second mandatory title substring is explicitly omitted; the resolved literal title substring ... remains required.'],
    roles=[role('"..."','title_text','QUOTED_LITERAL'),role('whose value I omitted','title_text','MISSING_OPERAND_PLACEHOLDER')],
    why='The literal ellipsis is a resolved title condition. An external statement separately creates a missing second title operand; one scalar contains slot cannot losslessly represent both obligations.')
add('i04-missing-negative-word', 'INCOMPLETE', 'negative,include,format,sort',
    'Include category Fiction and online access. Exclude the whole word [word omitted] from searchable text. Sort: title.',
    dict(subjects=['Fiction'],formats=['ONLINE'],exclude_terms='UNRESOLVED'),sort='TITLE',unresolved=['exclude_terms'],
    roles=[role('[word omitted]','exclude_terms','MISSING_OPERAND_PLACEHOLDER')],
    why='The negative domain is resolved as whole-word searchable text, but its required operand is absent. Category and format are fully known.',completion=('exclude_terms',['tide']))
add('i05-missing-canonical-category', 'INCOMPLETE', 'author,include,preference,sort',
    'Books by "Aven Rook" must be in category [category omitted]. Prefer an introduction. Sort: title.',
    dict(author_text='Aven Rook',subjects='UNRESOLVED'),sort='TITLE',unresolved=['subjects'],
    soft=[preference('Prefer an introduction','introductory')],
    roles=[role('[category omitted]','subjects','MISSING_OPERAND_PLACEHOLDER')],
    why='A positive category slot is explicitly missing; the author contains operand is not evidence for a category. Fiction is an independently valid proposed answer in every scope.',completion=('subjects',['Fiction']))

add('u01-author-level-aggregate', 'UNSUPPORTED', 'rating,year,author,preference',
    'Books by "Iven Sare" published from 2014 onward. Keep them only if the median rating across that author\'s entire bibliography exceeds 4.0. Prefer an introduction.',
    dict(author_text='Iven Sare'),soft=[preference('Prefer an introduction','introductory')],
    unadapted=['Author-bibliography median rating > 4.0 is mandatory.', 'Publication year >= 2014 is mandatory; unsupported in GLOBAL, supported as year_min in tenant scopes.'],
    roles=[role('median rating across that author\'s entire bibliography exceeds 4.0','rating_min')],
    why='A bibliography-level median is an aggregate relation, not a per-book rating floor. All scopes therefore remain unsupported; the year condition must additionally respect scope capabilities.')
add('u02-negative-metadata-domain', 'UNSUPPORTED', 'rating,title,negative,metadata',
    'Books titled "Velvet Compass", rated at least 3.9, but exclude every edition whose publisher is "Cedar House".',
    dict(title_text='Velvet Compass',rating_min=3.9),
    unadapted=['Mandatory negative publisher predicate: publisher != Cedar House, applied to every edition.'],
    roles=[role('exclude every edition whose publisher is "Cedar House"','publisher','EXPLICIT_EXCLUSION','MUST_NOT')],
    why='Native category/text exclusions cannot enforce a negative publisher or edition relation. Do not turn the publisher name into a whole-word text exclusion.')
add('u03-strict-reading-difficulty', 'UNSUPPORTED', 'rating,negative,metadata,preference',
    'Require rating at least 3.0 and beginner difficulty certified at level A1; exclude books lacking that certification.',
    dict(rating_min=3.0),
    unadapted=['Mandatory certified beginner reading difficulty A1.', 'Mandatory exclusion of records lacking difficulty certification.'],
    roles=[role('beginner difficulty certified at level A1','difficulty'),role('exclude books lacking that certification','difficulty','EXPLICIT_EXCLUSION','MUST_NOT')],
    why='Beginner is mandatory here, with a strict certification predicate. A soft reading-level preference cannot satisfy a required unsupported metadata condition.')
add('u04-cross-book-publication-relation', 'UNSUPPORTED', 'year,author,title,negative',
    'Books by "Ari Teal" published in the same year as the book titled "Silver Fen"; exclude any book published in a different year.',
    dict(author_text='Ari Teal'),
    unadapted=['Publication year must equal that of the bibliographic object described as titled Silver Fen; cross-book relation and identity resolution required.'],
    roles=[role('the book titled "Silver Fen"','title_text','FIELD_OR_CONCEPT_REFERENCE','NON_OPERATIVE')],
    why='The quoted title names the comparison object, not a title filter on returned books. Native scalar year bounds cannot enforce this cross-book relation or invent its year.')
add('u05-ordered-proximity', 'UNSUPPORTED', 'title,negative,format,sort',
    'Online books titled with "copper" within two words ahead of "orchard", without reversing that order. Sort: title.',
    dict(formats=['ONLINE']),sort='TITLE',
    unadapted=['Mandatory ordered title proximity: copper precedes orchard at a distance of at most two words.'],
    roles=[role('"copper" within two words ahead of "orchard"','title_text')],
    why='A literal title contains operand cannot encode ordered word-distance semantics. The source explicitly forbids reversing the order; simplification would discard a mandatory relation.')

add('c01-disjoint-closed-rating-interval', 'CONTRADICTORY', 'rating,author,title,format,preference',
    'Online books by "Teren Pike" titled "Cinder Loom" must have rating at least 4.4 and at most 2.6. Prefer an introduction.',
    dict(formats=['ONLINE'],author_text='Teren Pike',title_text='Cinder Loom',rating_min=4.4,rating_max=2.6),
    soft=[preference('Prefer an introduction','introductory')],
    roles=[role('rating at least 4.4 and at most 2.6','rating_min')],
    why='The resolved closed rating interval is empty. The remaining supported predicates and advisory preference cannot make it satisfiable.')
add('c02-category-positive-negative-overlap', 'CONTRADICTORY', 'rating,title,negative,include,format,sort',
    'Include category Fiction and exclude category Fiction simultaneously. Use online books titled "Marble Rain", rated at least 3.0. Sort: title.',
    dict(subjects=['Fiction'],exclude_subjects=['Fiction'],formats=['ONLINE'],title_text='Marble Rain',rating_min=3.0),sort='TITLE',
    roles=[role('Include category Fiction','subjects'),role('exclude category Fiction','exclude_subjects','EXPLICIT_EXCLUSION','MUST_NOT')],
    why='Both predicates resolve to the same authoritative category. Required membership and prohibited membership conflict in every scope.')
add('c03-required-and-excluded-online-format', 'CONTRADICTORY', 'rating,title,negative,format,preference',
    'Only online books titled "Fallow Bell", rated at least 3.2; exclude the online format as well. Prefer advanced treatment.',
    dict(formats=['ONLINE'],exclusive_formats=True,excluded_formats=['ONLINE'],title_text='Fallow Bell',rating_min=3.2),
    soft=[preference('Prefer advanced treatment','advanced')],
    roles=[role('Only online books','formats'),role('exclude the online format','excluded_formats','EXPLICIT_EXCLUSION','MUST_NOT')],
    why='The sole allowed format is simultaneously excluded. Online itself is supported in all scopes, so this is a resolved contradiction rather than unavailable physical access.')
add('c04-owned-title-word-versus-text-exclusion', 'CONTRADICTORY', 'author,title,negative,format,sort',
    'Online books by "Lio Hart", titled "the cedar grove". Exclude the whole word "cedar" from searchable text. Sort: title.',
    dict(formats=['ONLINE'],author_text='Lio Hart',title_text='the cedar grove',exclude_terms=['cedar']),sort='TITLE',
    roles=[role('titled "the cedar grove"','title_text'),role('Exclude the whole word "cedar"','exclude_terms','EXPLICIT_EXCLUSION','MUST_NOT')],
    why='A title containing the literal string the cedar grove necessarily contains cedar with word boundaries. The title is searchable text, so the required complete word is simultaneously prohibited without adding a whole-word title capability.')
add('c05-strict-boundary-excludes-singleton', 'CONTRADICTORY', 'rating,author,negative,preference,sort',
    'Books by "Maren Dusk" must have rating exactly 4.0, but not a rating of 4.0 or below: the lower boundary is strictly above 4.0. Prefer an introduction. Sort: title.',
    dict(author_text='Maren Dusk',rating_min=4.0,rating_max=4.0,rating_min_exclusive=True),sort='TITLE',
    soft=[preference('Prefer an introduction','introductory')],
    roles=[role('rating exactly 4.0','rating_max'),role('the lower boundary is strictly above 4.0','rating_min')],
    why='The equality contributes an inclusive upper endpoint at 4.0; the simultaneous strict lower endpoint excludes that singleton. Both endpoint strength and direction are resolved.')

def constraints(overrides):
    lists = {'subjects','exclude_subjects','exclude_terms','formats','excluded_formats'}
    booleans = {'rating_min_exclusive','rating_max_exclusive','year_min_exclusive','year_max_exclusive','exclusive_formats'}
    result = {k: ([] if k in lists else False if k in booleans else None) for k in brief['schema']['scalar_fields']}
    result.update(overrides)
    return result

def masks(hard, unresolved):
    result = {}
    for k, v in hard.items():
        if k in unresolved:
            result[k] = {'status':'UNRESOLVED','reason':'The source leaves this mandatory operand or domain undecided/absent.'}
        else:
            absent = v is None or v is False or v == []
            result[k] = {'status':'APPLICABLE_ABSENCE' if absent else 'APPLICABLE',
                         'reason':'Known absent from mandatory native constraints.' if absent else 'Resolved source-owned native constraint.'}
    result['sort'] = {'status':'APPLICABLE','reason':'Explicit supported sort or native relevance default.'}
    result['semantic_remainder'] = {'status':'N/A','reason':'No independently asserted unquoted literal topic to compare.'}
    result['soft_preferences'] = {'status':'N/A','reason':'Structured preferences retained; scalar/string equivalence is not asserted.'}
    return result

rows = []
for fam in FAMILIES:
    for scope, cfg in brief['scopes'].items():
        hard = constraints(fam['hard'])
        unadapted = list(fam['unadapted'])
        if fam['fid'] == 'u01-author-level-aggregate' and scope != 'GLOBAL':
            hard['year_min'] = 2014
            unadapted = [unadapted[0]]
        row = dict(case_id='proof6-'+fam['fid']+'-'+scope.lower(), query_text=fam['query'],
                   scope_type=scope, workspace_type=cfg['workspace_type'], search_mode='SMART',
                   decision_stratum=fam['decision'], family_id='proof6-'+fam['fid'],
                   structural_component_id='proof6-component-'+fam['fid'],
                   shared_semantic_pattern_id='proof6-pattern-'+fam['fid'],
                   expected_typed_decision=fam['decision'],
                   expected_executable=fam['decision'] in {'EXECUTABLE','EXECUTABLE_WITH_NOTICE'},
                   expected_hard_constraints=hard, metric_applicability=masks(hard,fam['unresolved']),
                   semantic_justification=fam['why'], expected_sort=fam['sort'],
                   expected_semantic_remainder=None, expected_soft_preferences=fam['soft'],
                   expected_source_roles=fam['roles'],
                   unadapted_mandatory_assertions=unadapted)
        if fam['fid'] == 'i03-independent-missing-title-beside-ellipsis':
            row['metric_applicability']['title_text'] = {'status':'N/A','reason':'Resolved first literal ... is retained, but a second missing mandatory title operand prevents a complete scalar oracle; no scalar partial mask is asserted.'}
        if fam['completion']:
            field,value = fam['completion']
            completed = dict(hard); completed[field] = value
            row['completion_input'] = {'field':field,'value':value}
            row['expected_completion'] = {'decision':'EXECUTABLE', 'hard_constraints':completed,
                                           'metric_applicability':masks(completed,[]),
                                           'expected_sort':fam['sort'], 'expected_semantic_remainder':None}
        row['authored_operation_topology'] = structure(row)
        rows.append(row)

draft = ROOT / 'reports/search_proof6_authored_v1_precheck.jsonl'
assert not draft.exists(), 'Preserve every prior authoring version; increment generator version.'
draft.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
errors=[]
for row in rows:
    fam = next(f for f in FAMILIES if 'proof6-'+f['fid'] == row['family_id'])
    expected = 'SMART:'+fam['features']
    if row['authored_operation_topology'] != expected:
        errors.append({'family':fam['fid'],'expected':expected,'actual':row['authored_operation_topology']})
    if row['authored_operation_topology'] not in brief['allowed_fresh_topologies']:
        errors.append({'family':fam['fid'],'topology_not_allowlisted':row['authored_operation_topology']})
    for annotation in row['expected_source_roles']:
        assert row['query_text'].count(annotation['source_text']) == 1, annotation
        assert annotation['role'] in brief['schema']['source_role_enums']
        assert annotation['modality'] in brief['schema']['modality_enums']
    assert set(brief['schema']['keys']) <= row.keys()
    assert set(row['expected_hard_constraints']) == set(brief['schema']['scalar_fields'])
assert len(rows)==150
assert len(FAMILIES)==30
assert collections.Counter(f['decision'] for f in FAMILIES)=={s:5 for s in brief['strata']}
topologies=set(r['authored_operation_topology'] for r in rows)
if len(topologies)!=30: errors.append({'distinct_topologies':len(topologies)})
long_rows=[r for r in rows if 151<=len(r['query_text'])<=500]
assert len(long_rows)>=5
assert all(len(r['query_text'])<=500 for r in rows)
report={'status':'FAILED_PRE_PREDICTION_AUTHORING' if errors else 'PASS_BLIND_AUTHORING_CHECKS',
        'errors':errors,'contexts':len(rows),'families':len(FAMILIES),'distinct_actual_topologies':len(topologies),
        'long_151_500_character_contexts':len(long_rows),'minimum_query_characters':min(len(r['query_text']) for r in rows),
        'maximum_query_characters':max(len(r['query_text']) for r in rows)}
(ROOT/'reports/search_proof6_author_v1_precheck.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if errors:
    print(json.dumps(report,indent=2)); raise SystemExit(1)

output=ROOT/brief['output']
assert not output.exists(),'Do not overwrite a previous authoring population.'
output.write_bytes(draft.read_bytes())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
provenance={
    'population_path':brief['output'],'population_sha256':sha(output),
    'author_identity':'/root/v6_fresh_author','actual_model_identity':'NOT_EXPOSED',
    'human_authors':0,'independent_ai_authors':1,
    'independence':'Fresh prose and normative expectations authored after parent-confirmed source freeze; no candidate, predictions, historical gold/populations, sealed examples, Mongo/backend, network, or inference API accessed.',
    'parent_authorization':'Source frozen and Step1 passed, communicated in task instruction. Step1 results not read.',
    'sources_read':[
        {'path':'reports/search_proof6_blind_author_brief.json','sha256':sha(BRIEF)},
        {'path':'reports/search_v2c_c5a_capability_matrix.json','sha256':sha(ROOT/'reports/search_v2c_c5a_capability_matrix.json')},
        {'path':'scripts/search_v2c_c2_benchmark.py','sha256':sha(C2),'access':'Only pure helper function bodies inspected; structure/mode/normalized AST nodes compiled in isolated namespace. No module execution.'},
        {'path':'scripts/search_v2c_c5a_sealed_audit.py','access':'Function-definition names/line matches only; no data read or module execution.'}
    ],
    'schema_only_parent_clarifications':'Typed decision string and executable boolean; accepted mask status enums; source_text role substring contract and completion object shape. No examples, predictions, or scores received.',
    'generator':'scripts/search_proof6_independent_author_v1.py',
    'generator_sha256':sha(Path(__file__)),
    'version_preservation':['reports/search_proof6_authored_v1_precheck.jsonl','reports/search_proof6_author_v1_precheck.json'],
    'scope_derivation':'Every family appears in each of the five actual authoritative scopes. Most use only shared capabilities; u01 preserves the supported publication floor in tenant scopes while retaining the mandatory aggregate as unsupported everywhere. No global year/language/availability/physical hard filter is manufactured.',
    'family_counting':'Thirty separately authored linguistic/semantic families, each with a different actual C2 operation topology; scope replicas count only as contexts.',
    'topology_verification':'Actual provided pure C2 structure over full query_text, including quoted text; all actual topologies checked against exposed-only allowlist. No sealed audit data accessed.',
    'all_cells':{'scope_x_stratum':5,'strata':brief['strata'],'scopes':list(brief['scopes'])},
    'normative_oracle_notes':['Owned title and author strings are contains operands, never identity proofs.',
        'Whole-word text exclusion and canonical category exclusion remain separate.',
        'Soft preferences are retained as structured values with N/A scalar equivalence masks.',
        'Known absences are explicit; unresolved mandatory scalar/list operands use UNRESOLVED masks.',
        'The incomplete independent second-title obligation is separately preserved while retaining resolved literal ellipsis.',
        'Optional completion inputs are independently proposed user answers, without offsets or candidate feedback.'],
    **report}
(ROOT/brief['provenance_output']).write_text(json.dumps(provenance,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({'path':str(output),'sha256':sha(output),**report},indent=2))
