"""Serialize independent semantic judgments; reads only the blind packet.

No candidate parser, author population, prediction, or scoring code is imported.
The numbered entries below were reasoned from the query text in the packet.
"""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(r'D:\SDC\LibraryLLM\reports')
packet = json.loads((ROOT / 'search_proof6_blind_reviewer_packet.json').read_text(encoding='utf-8'))
fields = packet['schema']['scalar_fields']
list_fields = {'subjects', 'exclude_subjects', 'exclude_terms', 'formats', 'exclusive_formats', 'excluded_formats'}

def role(text, field, role='MANDATORY_SEARCH_CONDITION', modality='MUST', mandatory=True):
    return dict(text=text, field=field, role=role, modality=modality, mandatory=mandatory)

def pref(text):
    return dict(source_text=text, modality='SHOULD', mandatory=False, meaning=text)

def obligation(text, field, operation, **kwargs):
    return dict(source_text=text, field=field, operation=operation, mandatory=True, **kwargs)

# Each record states a semantic judgment; repeated contexts have identical
# utterances, but canonical categories and capabilities are checked per scope.
judgments = [
 dict(decision='EXECUTABLE', hard=dict(formats=['ONLINE'],author_text='Nera Vell',title_text='The Copper Orchard',rating_min=3.6),sort='TITLE',
      why='Online access, both literal field substrings, and an inclusive item-rating floor form a supported intersection. Unfamiliar names do not require identity resolution.',
      roles=[role('online books','formats'),role('by "Nera Vell"','author_text'),role('titled "The Copper Orchard"','title_text'),role('rated at least 3.6','rating_min')]),
 dict(decision='EXECUTABLE',hard=dict(formats=['ONLINE'],rating_max=4.2,exclude_terms=['fossil']),sort='TITLE',
      why='The rating ceiling is inclusive, and the explicitly whole-word searchable-text exclusion is supported. It is not a category exclusion.',
      roles=[role('online books','formats'),role('rated no more than 4.2','rating_max'),role('exclude the whole word "fossil" from searchable text','exclude_terms','EXPLICIT_EXCLUSION','MUST_NOT')]),
 dict(decision='EXECUTABLE',hard=dict(subjects=['Fiction'],formats=['ONLINE'],title_text='River Glass'),sort='TITLE',
      why='Fiction is present in each supplied canonical inventory; the literal title substring and online access are compatible supported predicates.',
      roles=[role('category Fiction','subjects'),role('online books','formats'),role('titled "River Glass"','title_text')]),
 dict(decision='EXECUTABLE',hard=dict(exact_text='brass sundial',formats=['ONLINE'],rating_min=2.8,rating_min_exclusive=True,exclude_terms=['replica']),preferences=[pref('Prefer an introduction')],
      why='The unowned quote remains a literal exact-text operand. Above is strict; the whole-word exclusion is hard and the introduction request advisory.',
      roles=[role('"brass sundial"','exact_text','QUOTED_LITERAL'),role('rated above 2.8','rating_min'),role('without the whole word "replica"','exclude_terms','EXPLICIT_EXCLUSION','MUST_NOT'),role('Prefer an introduction','soft_preferences','OPTIONAL_PREFERENCE','SHOULD',False)]),
 dict(decision='EXECUTABLE',hard=dict(subjects=['Fiction'],author_text='Evin Sore',title_text='Lantern Wake'),sort='TITLE',preferences=[pref('Prefer an introduction')],
      why='The earlier seminar is background and the research shelf explicitly hypothetical. Only the current Fiction/author/title intersection is mandatory; the current introduction request is advisory.',
      roles=[role('My earlier seminar used advanced monographs, which explains my reading habits.','background','BACKGROUND_EXPLANATION','NON_OPERATIVE',False),role('For a hypothetical research shelf, I would prefer advanced monographs.','background','EXAMPLE_OR_HYPOTHETICAL','NON_OPERATIVE',False),role('category Fiction','subjects'),role('by "Evin Sore"','author_text'),role('titled "Lantern Wake"','title_text'),role('Prefer an introduction','soft_preferences','OPTIONAL_PREFERENCE','SHOULD',False)]),
 dict(decision='EXECUTABLE_WITH_NOTICE',hard=dict(subjects=['Fiction'],formats=['ONLINE'],author_text='Lera Moss',rating_min=3.1),sort='TITLE',
      why='The user explicitly identifies the transposition and supplies the canonical correction. Fiction exists in each scope; retain a correction notice and execute the supported intersection.',
      notice='Correct category Fictoin to Fiction as explicitly requested.',roles=[role('that spelling is a transposition of Fiction, so correct it','subjects','CORRECTION_INSTRUCTION'),role('category "Fictoin"','subjects'),role('by "Lera Moss"','author_text'),role('rated at least 3.1','rating_min')]),
 dict(decision='EXECUTABLE_WITH_NOTICE',hard=dict(subjects=['Fiction'],formats=['ONLINE'],author_text='Olan Reeve',title_text='Ash Compass'),sort='TITLE',
      why='The field-label correction is explicit and unique; the following title operand is complete. Preserve the repair notice rather than treating the quoted misspelling as searchable content.',
      notice='Repair titel to title as explicitly requested.',roles=[role('The label "titel" below is a typo for title; repair that label','title_text','CORRECTION_INSTRUCTION'),role('titled "Ash Compass"','title_text'),role('category Fiction','subjects'),role('by "Olan Reeve"','author_text')]),
 dict(decision='EXECUTABLE_WITH_NOTICE',hard=dict(subjects=['Fiction'],title_text='Quiet Estuary',rating_min=3.3,exclude_terms=['abridged']),sort='TITLE',
      why='The explicitly repaired rating label owns the inclusive 3.3 minimum. Category, title substring and whole-word exclusion are supported and compatible.',
      notice='Repair raitng to rating as explicitly requested.',roles=[role('I wrote "raitng" for rating; repair the field label','rating_min','CORRECTION_INSTRUCTION'),role('use a minimum of 3.3','rating_min'),role('titled "Quiet Estuary"','title_text'),role('exclude the whole word "abridged"','exclude_terms','EXPLICIT_EXCLUSION','MUST_NOT')]),
 dict(decision='EXECUTABLE_WITH_NOTICE',hard=dict(subjects=['Fiction'],author_text='Tavi Mere',formats=['ONLINE'],exclude_terms=['pirate']),preferences=[pref('Prefer advanced treatment')],
      why='The field-label repair has an explicit unique target. Advanced treatment is advisory; it must not become a metadata requirement or hard topic predicate.',
      notice='Repair authro to author as explicitly requested.',roles=[role('Repair my field label "authro" to author','author_text','CORRECTION_INSTRUCTION'),role('by "Tavi Mere"','author_text'),role('without the whole word "pirate"','exclude_terms','EXPLICIT_EXCLUSION','MUST_NOT'),role('Prefer advanced treatment','soft_preferences','OPTIONAL_PREFERENCE','SHOULD',False)]),
 dict(decision='EXECUTABLE_WITH_NOTICE',hard=dict(subjects=['Fiction'],title_text='...',exclude_terms=['retelling']),sort='TITLE',preferences=[pref('Prefer an introduction')],
      why='The requested sort repair has an explicit target. The field-owned nonempty quoted ellipsis is a literal title operand, not a missing value.',
      notice='Repair srot to sort as explicitly requested.',roles=[role('My label "srot" means sort; repair its spelling','sort','CORRECTION_INSTRUCTION'),role('order alphabetically on title','sort','USER_REQUESTED_OPERATION'),role('titled "..."','title_text','QUOTED_LITERAL'),role('without the whole word "retelling"','exclude_terms','EXPLICIT_EXCLUSION','MUST_NOT'),role('Prefer an introduction','soft_preferences','OPTIONAL_PREFERENCE','SHOULD',False)]),
 dict(decision='AMBIGUOUS',hard=dict(author_text='UNRESOLVED',title_text='UNRESOLVED',exclude_terms=['fossil']),sort='TITLE',
      why='The user explicitly leaves the author route versus title route undecided. Neither route can be conjoined or selected on the user\'s behalf; the common exclusion and ordering remain resolved.',
      unresolved=['author_text','title_text'],roles=[role('by "Sela Wynn" or titled "Copper Orchard"','author_text|title_text','UNRESOLVED_RELATION_OR_ALTERNATIVE','UNKNOWN'),role('I have left the choice between those two routes undecided','decision','UNRESOLVED_RELATION_OR_ALTERNATIVE','UNKNOWN'),role('Exclude the whole word "fossil"','exclude_terms','EXPLICIT_EXCLUSION','MUST_NOT')]),
 dict(decision='AMBIGUOUS',hard=dict(title_text='Amber Causeway',exclude_terms=['tourism'],rating_min='UNRESOLVED'),sort='TITLE',preferences=[pref('prefer an introduction')],unresolved=['rating_min'],
      why='Both candidate minimum values are supplied, but their mandatory selection is explicitly unresolved. It is not a missing numeric answer and must not become a range or conjunction.',
      roles=[role('titled "Amber Causeway"','title_text'),role('exclude the whole word "tourism"','exclude_terms','EXPLICIT_EXCLUSION','MUST_NOT'),role('The mandatory minimum rating is either 3.2 or 4.1; I still need to choose','rating_min','UNRESOLVED_RELATION_OR_ALTERNATIVE','UNKNOWN'),role('prefer an introduction','soft_preferences','OPTIONAL_PREFERENCE','SHOULD',False)]),
 dict(decision='AMBIGUOUS',hard=dict(exclude_subjects='UNRESOLVED',exclude_terms='UNRESOLVED'),sort='TITLE',preferences=[pref('Prefer advanced treatment')],unresolved=['exclude_subjects','exclude_terms'],
      why='The negative domain is explicitly undecided between canonical category and searchable whole word. Neither exclusion field has a definitive operand; the advisory request does not resolve this.',
      roles=[role('Exclude Fiction, but I have yet to decide whether that means the category or the whole word in searchable text','exclude_subjects|exclude_terms','UNRESOLVED_RELATION_OR_ALTERNATIVE','MUST_NOT'),role('Prefer advanced treatment','soft_preferences','OPTIONAL_PREFERENCE','SHOULD',False)]),
 dict(decision='AMBIGUOUS',hard=dict(formats=['ONLINE'],author_text='Mira Sol'),sort='TITLE',
      why='The mandatory-versus-advisory status of advanced treatment is expressly open. Resolve that modality before execution; no unsupported strict predicate or definite preference may be invented.',
      modality_unresolved=True,
      roles=[role('Online books','formats'),role('by "Mira Sol"','author_text'),role('For advanced treatment, I cannot yet say whether it is mandatory or merely a preference. Keep that choice open.','difficulty','UNRESOLVED_RELATION_OR_ALTERNATIVE','UNKNOWN',None)]),
 dict(decision='AMBIGUOUS',hard=dict(subjects=['Fiction'],formats=['ONLINE'],author_text='Rian Loam',rating_min=3.7,title_text='UNRESOLVED'),preferences=[pref('Prefer an introduction')],unresolved=['title_text'],
      why='The common subject/access/author/rating conjunction is resolved. The user explicitly has not selected the mandatory title substring, so do not turn the two title alternatives into a Boolean query or select one.',
      roles=[role('category Fiction','subjects'),role('by "Rian Loam"','author_text'),role('rated at least 3.7','rating_min'),role('They must be titled either "Moth Harbor" or "Winter Reed", with the intended one still undecided','title_text','UNRESOLVED_RELATION_OR_ALTERNATIVE','UNKNOWN'),role('Prefer an introduction','soft_preferences','OPTIONAL_PREFERENCE','SHOULD',False)]),
 dict(decision='INCOMPLETE',hard=dict(author_text='Oren Vale',rating_min='UNRESOLVED'),sort='TITLE',preferences=[pref('Prefer an introduction')],unresolved=['rating_min'],
      why='A mandatory inclusive rating minimum is explicitly missing. The supplied completion answers that source-owned placeholder without altering the author or preference.',
      roles=[role('by "Oren Vale"','author_text'),role('[value omitted]','rating_min','MISSING_OPERAND_PLACEHOLDER'),role('Prefer an introduction','soft_preferences','OPTIONAL_PREFERENCE','SHOULD',False)]),
 dict(decision='INCOMPLETE',hard=dict(author_text='UNRESOLVED',title_text='Salt Lattice',exclude_terms=['almanac']),preferences=[pref('Prefer advanced treatment')],unresolved=['author_text'],
      why='The author value is explicitly omitted while its field ownership is clear. Completing the author substring preserves the literal title, whole-word exclusion and advisory treatment.',
      roles=[role('[author omitted]','author_text','MISSING_OPERAND_PLACEHOLDER'),role('titled "Salt Lattice"','title_text'),role('without the whole word "almanac"','exclude_terms','EXPLICIT_EXCLUSION','MUST_NOT'),role('Prefer advanced treatment','soft_preferences','OPTIONAL_PREFERENCE','SHOULD',False)]),
 dict(decision='INCOMPLETE',hard=dict(title_text='UNRESOLVED',rating_min=3.5),sort='TITLE',preferences=[pref('prefer an introduction')],unresolved=['title_text'],
      why='The literal ellipsis is a complete mandatory title substring. A separate second mandatory substring is expressly missing. A single scalar title field cannot encode the complete conjunction; retain the resolved ellipsis independently and do not execute.',
      unadapted=[obligation('Books must be titled "..." literally.','title_text','CONTAINS',value='...'),obligation('I also require a second title substring, whose value I omitted.','title_text','CONTAINS',value='UNRESOLVED')],
      roles=[role('titled "..." literally','title_text','QUOTED_LITERAL'),role('I also require a second title substring, whose value I omitted','title_text','MISSING_OPERAND_PLACEHOLDER'),role('rating of at least 3.5','rating_min'),role('prefer an introduction','soft_preferences','OPTIONAL_PREFERENCE','SHOULD',False)]),
 dict(decision='INCOMPLETE',hard=dict(subjects=['Fiction'],formats=['ONLINE'],exclude_terms='UNRESOLVED'),sort='TITLE',unresolved=['exclude_terms'],
      why='The exclusion domain is settled as a whole word in searchable text, but the mandatory word is omitted. The supplied answer completes only this exclusion.',
      roles=[role('category Fiction','subjects'),role('online access','formats'),role('[word omitted]','exclude_terms','MISSING_OPERAND_PLACEHOLDER','MUST_NOT')]),
 dict(decision='INCOMPLETE',hard=dict(author_text='Aven Rook',subjects='UNRESOLVED'),sort='TITLE',preferences=[pref('Prefer an introduction')],unresolved=['subjects'],
      why='A mandatory category operand is explicitly omitted. The proposed completion Fiction is canonical in every supplied scope and preserves the author and advisory request.',
      roles=[role('by "Aven Rook"','author_text'),role('[category omitted]','subjects','MISSING_OPERAND_PLACEHOLDER'),role('Prefer an introduction','soft_preferences','OPTIONAL_PREFERENCE','SHOULD',False)]),
 dict(decision='UNSUPPORTED',hard=dict(author_text='Iven Sare',year_min=2014),preferences=[pref('Prefer an introduction')],
      why='An author-bibliography median gate requires an aggregate and related corpus lookup, not an item rating threshold. It cannot be dropped or translated into rating_min. The literal year bound remains resolved; GLOBAL additionally lacks year filtering.',
      unadapted=[obligation("only if the median rating across that author's entire bibliography exceeds 4.0",'bibliography_median_rating','AGGREGATE_GATE',operator='>',value=4.0)],
      roles=[role('by "Iven Sare"','author_text'),role('published from 2014 onward','year_min'),role("only if the median rating across that author's entire bibliography exceeds 4.0",'bibliography_median_rating','MANDATORY_SEARCH_CONDITION','CONDITIONAL'),role('Prefer an introduction','soft_preferences','OPTIONAL_PREFERENCE','SHOULD',False)]),
 dict(decision='UNSUPPORTED',hard=dict(title_text='Velvet Compass',rating_min=3.9),
      why='Publisher-specific edition exclusion has no supported hard field. It is not a searchable whole-word exclusion, a subject exclusion, or a title operand.',
      unadapted=[obligation('exclude every edition whose publisher is "Cedar House"','publisher','NOT_EQUALS',value='Cedar House')],
      roles=[role('titled "Velvet Compass"','title_text'),role('rated at least 3.9','rating_min'),role('exclude every edition whose publisher is "Cedar House"','publisher','EXPLICIT_EXCLUSION','MUST_NOT')]),
 dict(decision='UNSUPPORTED',hard=dict(rating_min=3.0),
      why='The hard A1 beginner certification and exclusion of uncertified books require unavailable metadata. They cannot be reduced to a soft preference or a literal topic; the item rating floor remains resolved.',
      unadapted=[obligation('beginner difficulty certified at level A1; exclude books lacking that certification','difficulty_certification','CERTIFIED',value='A1')],
      roles=[role('rating at least 3.0','rating_min'),role('beginner difficulty certified at level A1','difficulty_certification'),role('exclude books lacking that certification','difficulty_certification','EXPLICIT_EXCLUSION','MUST_NOT')]),
 dict(decision='UNSUPPORTED',hard=dict(author_text='Ari Teal'),na=['year_min','year_max'],
      why='The other book\'s title identifies a relational reference, not a result-title filter. Its unknown year must be looked up and equated across books; the native scalar contract cannot perform that operation. GLOBAL also lacks year filtering.',
      unadapted=[obligation('published in the same year as the book titled "Silver Fen"; exclude any book published in a different year','publication_year','EQUALS_REFERENCED_BOOK_YEAR',reference_title_contains='Silver Fen')],
      roles=[role('by "Ari Teal"','author_text'),role('the book titled "Silver Fen"','reference_title','FIELD_OR_CONCEPT_REFERENCE','NON_OPERATIVE',False),role('published in the same year as the book titled "Silver Fen"','publication_year'),role('exclude any book published in a different year','publication_year','EXPLICIT_EXCLUSION','MUST_NOT')]),
 dict(decision='UNSUPPORTED',hard=dict(formats=['ONLINE']),sort='TITLE',na=['title_text'],
      why='The title predicate is ordered bounded word proximity. A single contains phrase cannot encode possible intervening words and must not replace the requested distance/order semantics.',
      unadapted=[obligation('titled with "copper" within two words ahead of "orchard", without reversing that order','title_text','ORDERED_WORD_PROXIMITY',first='copper',second='orchard',maximum_distance_words=2)],
      roles=[role('Online books','formats'),role('titled with "copper" within two words ahead of "orchard", without reversing that order','title_text')]),
 dict(decision='CONTRADICTORY',hard=dict(formats=['ONLINE'],author_text='Teren Pike',title_text='Cinder Loom',rating_min=4.4,rating_max=2.6),preferences=[pref('Prefer an introduction')],
      why='A single rating cannot be simultaneously at least 4.4 and at most 2.6. Retain both resolved bounds; advisory introduction does not relax either bound.',
      roles=[role('by "Teren Pike"','author_text'),role('titled "Cinder Loom"','title_text'),role('rating at least 4.4','rating_min'),role('at most 2.6','rating_max'),role('Prefer an introduction','soft_preferences','OPTIONAL_PREFERENCE','SHOULD',False)]),
 dict(decision='CONTRADICTORY',hard=dict(subjects=['Fiction'],exclude_subjects=['Fiction'],formats=['ONLINE'],title_text='Marble Rain',rating_min=3.0),sort='TITLE',
      why='The same canonical category is required and excluded simultaneously. All operands are resolved; this is a contradiction rather than domain ambiguity.',
      roles=[role('Include category Fiction','subjects'),role('exclude category Fiction simultaneously','exclude_subjects','EXPLICIT_EXCLUSION','MUST_NOT'),role('online books','formats'),role('titled "Marble Rain"','title_text'),role('rated at least 3.0','rating_min')]),
 dict(decision='CONTRADICTORY',hard=dict(formats=['ONLINE'],exclusive_formats=['ONLINE'],excluded_formats=['ONLINE'],title_text='Fallow Bell',rating_min=3.2),preferences=[pref('Prefer advanced treatment')],
      why='Only-online access requires ONLINE and rejects other formats; the independent exclusion rejects ONLINE itself. The intersection is empty in all supplied scopes.',
      roles=[role('Only online books','exclusive_formats'),role('titled "Fallow Bell"','title_text'),role('rated at least 3.2','rating_min'),role('exclude the online format as well','excluded_formats','EXPLICIT_EXCLUSION','MUST_NOT'),role('Prefer advanced treatment','soft_preferences','OPTIONAL_PREFERENCE','SHOULD',False)]),
 dict(decision='CONTRADICTORY',hard=dict(formats=['ONLINE'],author_text='Lio Hart',title_text='the cedar grove',exclude_terms=['cedar']),sort='TITLE',
      why='The required literal title substring contains the complete interior word cedar. Searchable text includes the title, so excluding that same whole word rejects every title satisfying the literal phrase; substring-versus-word distinctions do not save this case.',
      roles=[role('by "Lio Hart"','author_text'),role('titled "the cedar grove"','title_text'),role('Exclude the whole word "cedar" from searchable text','exclude_terms','EXPLICIT_EXCLUSION','MUST_NOT')]),
 dict(decision='CONTRADICTORY',hard=dict(author_text='Maren Dusk',rating_min=4.0,rating_max=4.0,rating_min_exclusive=True),sort='TITLE',preferences=[pref('Prefer an introduction')],
      why='Exact 4.0 supplies an inclusive upper bound of 4.0, while the independently explicit lower boundary is strictly above 4.0. No rating satisfies both; the later wording reinforces the strict constraint rather than retracting the exact one.',
      roles=[role('by "Maren Dusk"','author_text'),role('rating exactly 4.0','rating_max'),role('not a rating of 4.0 or below','rating_min','EXPLICIT_EXCLUSION','MUST_NOT'),role('the lower boundary is strictly above 4.0','rating_min'),role('Prefer an introduction','soft_preferences','OPTIONAL_PREFERENCE','SHOULD',False)]),
]

def make_masks(hard, judgment):
    masks = {}
    for f in fields:
        if f in judgment.get('unresolved', []):
            masks[f] = dict(status='UNRESOLVED',reason='The required field value, alternative, or complete scalar representation is unresolved; known obligations remain separately preserved.')
        elif f in judgment.get('na', []):
            masks[f] = dict(status='N/A',reason='A clear structured mandatory relation has no equivalent native scalar operand; see unadapted_mandatory_assertions.')
        elif f in judgment['hard']:
            masks[f] = dict(status='APPLICABLE',reason='The query fixes this hard operand independently of execution eligibility.')
        else:
            masks[f] = dict(status='APPLICABLE_ABSENCE',reason='No current mandatory scalar condition is asserted for this field.')
    masks['sort'] = dict(status='APPLICABLE' if 'sort' in judgment else 'APPLICABLE_ABSENCE',reason='Explicit title ordering.' if 'sort' in judgment else 'No requested order; native default relevance applies.')
    masks['semantic_remainder'] = dict(status='N/A',reason='No independent plain literal topic remainder is asserted. Literal quotations are field operands; advisory and structured meanings have no scalar string-equivalence oracle.')
    masks['soft_preferences'] = dict(status='N/A',reason='Structured advisory meaning is reviewed separately; do not score by string equality.')
    return masks

cases = []
assert len(judgments) == 30 and len(packet['cases']) == 150
for i,c in enumerate(packet['cases']):
    j = judgments[i // 5]
    assert c['query_text'] == packet['cases'][i//5*5]['query_text']
    h = {f: [] if f in list_fields else False if f.endswith('_exclusive') else None for f in fields}
    h.update(copy.deepcopy(j['hard']))
    for subject in h['subjects'] if isinstance(h['subjects'], list) else []:
        assert subject in packet['scopes'][c['scope_type']]['subjects']
    roles = copy.deepcopy(j['roles'])
    for r in roles:
        assert r['text'] in c['query_text'], (i,r)
    if 'sort' in j and not any(r['field']=='sort' for r in roles):
        source = 'Sort: title' if 'Sort: title' in c['query_text'] else 'sort: title'
        roles.append(role(source,'sort','USER_REQUESTED_OPERATION'))
    record = dict(review_id=c['review_id'],expected_typed_decision=j['decision'],expected_executable=j['decision'] in ('EXECUTABLE','EXECUTABLE_WITH_NOTICE'),expected_hard_constraints=h,metric_applicability=make_masks(h,j),expected_sort=j.get('sort','RELEVANCE'),expected_semantic_remainder=None,expected_soft_preferences=copy.deepcopy(j.get('preferences',[])),expected_source_roles=roles,semantic_justification=j['why'])
    if 'notice' in j:
        record['expected_notices'] = [j['notice']]
    if 'unadapted' in j:
        record['unadapted_mandatory_assertions'] = copy.deepcopy(j['unadapted'])
    if i//5 == 13:
        record['unresolved_annotations'] = [dict(field='difficulty_modality',reason='Explicitly unresolved requirement-versus-preference status; no definite soft preference or strict difficulty field is asserted.')]
    if i//5 == 17:
        record['resolved_mandatory_assertions'] = [dict(field='title_text',operator='CONTAINS',value='...')]
        record['unresolved_annotations'] = [dict(field='title_text',reason='A second mandatory substring is omitted. The first literal ellipsis remains known, but one scalar cannot represent the full conjunctive predicate.')]
    if 'completion_input' in c:
        inp=c['completion_input']; complete=copy.deepcopy(h)
        value=inp['value']
        if inp['field'] in list_fields: value=[value]
        elif inp['field'] in ('rating_min','rating_max'): value=float(value)
        complete[inp['field']]=value
        cj=copy.deepcopy(j); cj['hard'][inp['field']]=value; cj['unresolved']=[]
        record['expected_completion'] = dict(decision='EXECUTABLE',executable=True,hard_constraints=complete,metric_applicability=make_masks(complete,cj),sort=j.get('sort','RELEVANCE'),semantic_remainder=None,semantic_justification='The proposed answer fills the one explicitly missing source-owned operand. All other mandatory predicates and current advisory conditions remain unchanged.')
    cases.append(record)

out = dict(reviewer_provenance=dict(identity='/root/v6_blind_reviewer',exact_runtime_model_id='NOT_EXPOSED',human_reviewers=0,blind_to_predictions=True,blind_to_author_labels=True,review_method='Independent semantic judgments from the supplied query/context-only packet, normative rules, canonical inventories, capability snapshots and the permitted pure scalar schema adapter; no candidate parser or authored population/generator/provenance was read or executed.',source_inputs=['reports/search_proof6_blind_reviewer_packet.json','scripts/search_v2c_c5er_evaluation_adapter_v2.py']),cases=cases)
target=ROOT/'search_proof6_independent_review.json'
target.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(path=str(target),cases=len(cases),completion_cases=sum('expected_completion' in c for c in cases),sha256=hashlib.sha256(target.read_bytes()).hexdigest())))
