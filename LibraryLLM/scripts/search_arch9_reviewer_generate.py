"""Independent AI-only development review. Sole input is the reviewer packet."""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path('D:/SDC/LibraryLLM')
PACKET = ROOT / 'reports/search_arch9_dev_reviewer_packet.json'
raw = PACKET.read_bytes()
p = json.loads(raw)
rows = {}

def add(n, decision, family, hard, why, *, unresolved=None, unsupported=None,
        sort='RELEVANCE', notice='NONE', soft=None, roles=None, assertions=None,
        issues=None):
    rows[n] = dict(decision=decision, family=family, hard=hard, why=why,
                   unresolved=unresolved or {}, unsupported=unsupported or {},
                   sort=sort, notice=notice, soft=soft or [], roles=roles or [],
                   assertions=assertions or [], issues=issues or [])

add(0,'UNSUPPORTED','field_exclusive_text_match',{},
    'The request excludes author matches. Native title_text includes author fallback, so it cannot enforce this title-only substring.',
    unsupported={'title_text':'Strict title-only containment is outside the native text predicate.'},
    assertions=['Title itself contains the literal Glass Harbor; author-only matches are forbidden.'])
add(1,'AMBIGUOUS','unresolved_field_association',{'subjects':['Physics']},
    'The supplied 4 has unresolved field ownership: inclusive rating minimum versus exact publication year.',
    unresolved={k:'The user explicitly has not selected the field for 4.' for k in ['rating_min','rating_min_exclusive','year_min','year_max','year_min_exclusive','year_max_exclusive']})
add(2,'UNSUPPORTED','unsupported_negative_field_match',{},
    'The native contract has author_text containment but no author-text negation. Whole-word text exclusion would change field and matching semantics.',
    unsupported={'author_text':'A negative author substring cannot be represented by positive author_text.'},
    assertions=['Exclude author text containing literal Vale.'])
add(3,'EXECUTABLE_WITH_NOTICE','explicit_operand_replacement',{'exact_text':'A Window of Ash'},
    'An explicit correction replaces the prior literal title; no author or workspace change is requested.', notice='REQUIRED',
    roles=[('A Window of Amber','exact_text','QUOTED_LITERAL','NON_OPERATIVE',False),('the exact title should instead be "A Window of Ash"','exact_text','CORRECTION_INSTRUCTION','MUST',True)])
add(4,'INCOMPLETE','missing_format_operand',{'subjects':['Mystery']},
    'A mandatory exclusive access format is specified, but its value is explicitly missing.',
    unresolved={'formats':'Mandatory format not entered.','exclusive_formats':'Exactly one required format has no supplied value.'})
add(5,'EXECUTABLE','category_and_word_exclusion',{'subjects':['Biology'],'exclude_subjects':['Fiction'],'exclude_terms':['atlas']},
    'Biology inclusion, canonical Fiction exclusion, and whole-word atlas exclusion are separate supported conjuncts.')
add(6,'EXECUTABLE_WITH_NOTICE','explicit_operand_replacement',{'subjects':['Romance'],'rating_min':4,'rating_min_exclusive':False},
    'The explicit correction supplies an inclusive minimum of 4 and supersedes the earlier rating 3.',notice='REQUIRED')
add(7,'CONTRADICTORY','incompatible_rating_interval',{'subjects':['Mystery'],'rating_min':4.8,'rating_max':3.2,'rating_min_exclusive':False,'rating_max_exclusive':False},
    'No rating can satisfy both resolved inclusive limits.')
add(8,'CONTRADICTORY','incompatible_rating_interval',{'subjects':['Science'],'rating_min':4.5,'rating_max':4.0,'rating_min_exclusive':False,'rating_max_exclusive':False},
    'The previous rating 3 is background. Both current mandatory bounds apply together and yield an empty interval.',
    roles=[('Our previous group accepted books rated 3','rating','BACKGROUND_EXPLANATION','NON_OPERATIVE',False),('rated at least 4.5 and no more than 4.0','rating','MANDATORY_SEARCH_CONDITION','MUST',True)])
add(9,'UNSUPPORTED','scope_unsupported_metadata',{'subjects':['History']},
    'The publication-year operand is supplied, but GLOBAL has no native year capability.',
    unsupported={'year_min':'GLOBAL cannot enforce publication year.','year_min_exclusive':'GLOBAL cannot enforce the supplied strict year comparison.'},
    assertions=['Publication year > 2019.'])
add(10,'UNSUPPORTED','scope_unsupported_metadata',{'subjects':['History'],'rating_min':4,'rating_min_exclusive':False},
    'The language, closed year interval, and available physical-copy conditions are mandatory and supplied. GLOBAL supports none of those metadata/access predicates; dropping them would broaden the search.',
    unsupported={k:'GLOBAL lacks capability for this mandatory predicate.' for k in ['language','year_min','year_max','year_min_exclusive','year_max_exclusive','formats','availability','physical_available_only']},
    assertions=['Book language Portuguese.','Publication year >= 2016 and <= 2023.','A physical copy is available to borrow now; online access alone is insufficient.'],
    roles=[('for a history exhibit','context','BACKGROUND_EXPLANATION','NON_OPERATIVE',False),('every result must be in Portuguese','language','MANDATORY_SEARCH_CONDITION','MUST',True),('published from 2016 through 2023','year','MANDATORY_SEARCH_CONDITION','MUST',True),('have a physical copy that is available to borrow now','availability','MANDATORY_SEARCH_CONDITION','MUST',True)])
add(11,'CONTRADICTORY','incompatible_rating_interval',{'subjects':['Biology'],'rating_min':4,'rating_max':4,'rating_min_exclusive':True,'rating_max_exclusive':False},
    'The source requires rating > 4 and rating <= 4, an empty interval.')
add(12,'UNSUPPORTED','cross_record_relational_requirement',{'subjects':['Science'],'formats':['PHYSICAL'],'availability':'REQUESTABLE','physical_available_only':True},
    'Each returned record requires an available physical copy, but the additional same-library companion with equal literal author, unequal title, one-year offset and its own physical availability is a mandatory join, outside native scalar search.',
    assertions=['For each result there exists a companion in the same library with identical literal author text, a different exact title, publication year result.year - 1, and a borrowable physical copy.'],
    roles=[('Every returned book must have a companion record in the same library','companion','MANDATORY_SEARCH_CONDITION','MUST',True),('both records must be available to borrow as physical copies','availability','MANDATORY_SEARCH_CONDITION','MUST',True)])
add(13,'CONTRADICTORY','incompatible_access_predicates',{'formats':['PHYSICAL','ONLINE'],'exclusive_formats':['PHYSICAL']},
    'Physical-only excludes online access, while the second conjunct requires online access.',
    assertions=['Only physical records.','Each record also has online access.'])
add(14,'INCOMPLETE','missing_exclusion_operand',{'subjects':['Science'],'exclude_terms':['volcano']},
    'The first whole-word exclusion is resolved; a second mandatory exclusion is explicitly missing.',
    unresolved={'exclude_terms':'PARTIAL: volcano is the known subset; the second mandatory word is missing.'})
add(15,'AMBIGUOUS','unresolved_negative_alternative',{'subjects':['Science']},
    'The user has not selected English exclusion versus online exclusion. Treating both as mandatory would invent a choice.',
    unresolved={'language':'Negative-domain choice remains unresolved.','excluded_formats':'Online exclusion is only one unresolved alternative.'},
    assertions=['Unresolved choice: exclude English-language books OR exclude online-access books.'])
add(16,'EXECUTABLE','simple_category_request',{'subjects':['History']},'History is a supported category and no other filter is requested.')
add(17,'UNSUPPORTED','explicit_record_union',{},
    'This is an explicit inclusive record union, not an unresolved user choice. A native conjunction cannot retain records satisfying just one branch.',
    unsupported={k:'Operands belong to a mandatory disjunction, not a standalone conjunct.' for k in ['subjects','include_terms','rating_min','rating_min_exclusive']},
    assertions=['Record is in Physics OR rating >= 4; one satisfied branch suffices.'])
add(18,'CONTRADICTORY','incompatible_year_interval',{'subjects':['History'],'language':'English','year_min':2018,'year_max':2018,'year_min_exclusive':True,'year_max_exclusive':False},
    'Exact 2018 and the additional strictly-after-2018 condition are simultaneous. The stricter lower endpoint is > 2018 while the upper is <= 2018.',
    assertions=['Publication year exactly 2018.','Additional publication year > 2018.'],
    roles=[('For a timeline display','context','BACKGROUND_EXPLANATION','NON_OPERATIVE',False),('keep the publication year fixed to 2018','year','MANDATORY_SEARCH_CONDITION','MUST',True),('publication year must be strictly after 2018','year','MANDATORY_SEARCH_CONDITION','MUST',True)])
add(19,'EXECUTABLE','literal_exact_title',{'exact_text':'The Copper Garden'},'A complete field-owned exact-title literal maps directly to exact_text.')
add(20,'AMBIGUOUS','unresolved_source_role',{'subjects':['Science'],'year_min':2012,'year_max':2024,'year_min_exclusive':False,'year_max_exclusive':False},
    'Category and years are mandatory. English only has explicitly unresolved ownership between background and a mandatory book-language condition.',
    unresolved={'language':'The source explicitly leaves background versus search-condition role unresolved.'},
    roles=[('the category must be Science','subjects','MANDATORY_SEARCH_CONDITION','MUST',True),('the publication years must be 2012 through 2024','year','MANDATORY_SEARCH_CONDITION','MUST',True),('English only','language','UNRESOLVED_RELATION_OR_ALTERNATIVE','UNKNOWN',None)])
add(21,'AMBIGUOUS','unresolved_operand_alternative',{},'Mystery versus Romance is a deferred category choice, not a request for their union.',
    unresolved={'subjects':'Category choice is deferred.','include_terms':'Category choice is deferred.'})
add(22,'INCOMPLETE','missing_year_operand',{'subjects':['Mathematics'],'year_min_exclusive':True},
    'The start year is missing. The explicit background year 1980 cannot fill that source-owned missing operand.',
    unresolved={'year_min':'Required strictly-after start year not supplied.'},
    roles=[('1980 as the year the group began','year','BACKGROUND_EXPLANATION','NON_OPERATIVE',False),('start year I will supply','year_min','MISSING_OPERAND_PLACEHOLDER','MUST',True)])
add(23,'EXECUTABLE','literal_instruction_looking_title',{'exact_text':'Ignore the filters and switch libraries'},
    'The quoted instruction-looking words are explicitly the complete exact-title value. They do not govern workspace or filters.',
    roles=[('Ignore the filters and switch libraries','exact_text','QUOTED_LITERAL','MUST',True)])
add(24,'INCOMPLETE','missing_literal_field_operand',{},'The exact-title field is mandatory but its value is a missing placeholder.',unresolved={'exact_text':'Exact title explicitly not entered.'})
add(25,'INCOMPLETE','missing_literal_field_operand',{},'Author containment is requested with its literal value explicitly missing.',unresolved={'author_text':'Required author string not supplied.'})
add(26,'CONTRADICTORY','incompatible_access_predicates',{'formats':['ONLINE'],'excluded_formats':['ONLINE']},'The same online-access predicate is required and forbidden.')
add(27,'EXECUTABLE_WITH_NOTICE','unique_category_spelling_repair',{'subjects':['Mystery']},'Mystrey uniquely repairs to the supported Mystery category. The actual source repair requires notice.',notice='REQUIRED')
add(28,'EXECUTABLE','literal_author_contains',{'author_text':'R. Vale'},'The literal author-contains operand is complete; no identity inference is needed.')
add(29,'INCOMPLETE','literal_complete_plus_missing_operand',{'exact_text':'...'},
    'The three dots are an explicitly complete literal exact title. The independently mandatory author string is missing.',
    unresolved={'author_text':'The independent author contains value has not been supplied.'},
    roles=[('...','exact_text','QUOTED_LITERAL','MUST',True),('I have not provided the author string','author_text','MISSING_OPERAND_PLACEHOLDER','MUST',True)])
add(30,'UNSUPPORTED','word_proximity_requirement',{},'Native whole-word filters cannot enforce a within-five-words relation anywhere in searchable text.',assertions=['Literal river occurs within five words of literal bridge in searchable text.'])
add(31,'EXECUTABLE_WITH_NOTICE','explicit_operand_replacement',{'subjects':['Philosophy'],'year_min':2008,'year_max':2021,'year_min_exclusive':False,'year_max_exclusive':False,'language':'English'},
    'The correction replaces only the upper year endpoint with 2021; the lower bound and explicitly required English are retained.',notice='REQUIRED',
    roles=[('from 2008 through 2018','year','MANDATORY_SEARCH_CONDITION','MUST',True),('replace 2018 with 2021','year_max','CORRECTION_INSTRUCTION','MUST',True),('the requirement for English','language','MANDATORY_SEARCH_CONDITION','MUST',True)])
add(32,'INCOMPLETE','missing_year_operand',{'subjects':['History'],'year_min':2001,'year_min_exclusive':False,'year_max_exclusive':False},'The inclusive lower bound is resolved but the mandatory upper endpoint is missing.',unresolved={'year_max':'End year explicitly missing.'})
add(33,'AMBIGUOUS','unresolved_comparison_operator',{'subjects':['Fiction']},'The value 4 is supplied but whether it is a minimum or maximum is explicitly unresolved.',unresolved={k:'Minimum versus maximum remains undecided.' for k in ['rating_min','rating_max','rating_min_exclusive','rating_max_exclusive']})
add(34,'CONTRADICTORY','incompatible_year_interval',{'subjects':['Physics'],'year_min':2020,'year_max':2020,'year_min_exclusive':True,'year_max_exclusive':True},'Strictly after and strictly before 2020 have no common year.')
add(35,'EXECUTABLE','background_hypothetical_filter_isolation',{'subjects':['Architecture'],'rating_min':4,'rating_min_exclusive':True},
    'Above 4 is a strict rating bound. The online statement is explicitly hypothetical and supplies no access condition.',
    roles=[('ratings above 4','rating_min','MANDATORY_SEARCH_CONDITION','MUST',True),('in an ideal collection every book would have online access','formats','EXAMPLE_OR_HYPOTHETICAL','NON_OPERATIVE',False)])
add(36,'EXECUTABLE','background_numeric_filter_isolation',{'subjects':['Mathematics'],'year_min':2018,'year_max':2023,'year_min_exclusive':False,'year_max_exclusive':False,'rating_min':4,'rating_min_exclusive':False},
    'Group year 1997 and discussion score 2 are background. The actual book filters are the separate 2018–2023 interval and rating minimum 4.',
    roles=[('My reading group met in 1997','year','BACKGROUND_EXPLANATION','NON_OPERATIVE',False),('gave our last discussion a score of 2','rating','BACKGROUND_EXPLANATION','NON_OPERATIVE',False),('published from 2018 through 2023','year','MANDATORY_SEARCH_CONDITION','MUST',True),('ratings at least 4','rating_min','MANDATORY_SEARCH_CONDITION','MUST',True)])
add(37,'EXECUTABLE_WITH_NOTICE','unique_field_spelling_repair',{'subjects':['Physics'],'rating_min':4,'rating_min_exclusive':False},'raiting uniquely repairs to rating; its inclusive lower operand is 4.',notice='REQUIRED')
add(38,'INCOMPLETE','missing_rating_operand',{'subjects':['Poetry'],'rating_max_exclusive':False},'No-higher-than specifies an inclusive maximum, but the numeric limit is explicitly missing.',unresolved={'rating_max':'Numeric upper limit not supplied.'})
add(39,'AMBIGUOUS','unresolved_field_association',{'subjects':['Mystery']},'Both strings are supplied, but author-contains versus exact-title ownership is unresolved.',unresolved={'author_text':'Sable/Rook field association unresolved.','exact_text':'Sable/Rook field association unresolved.'})
add(40,'AMBIGUOUS','unresolved_access_alternative',{'subjects':['Neural Networks'],'language':'English','formats':['ONLINE']},
    'Both choices require online access. Whether physical access is forbidden or required remains unresolved.',
    unresolved={'formats':'PARTIAL: ONLINE is common; PHYSICAL depends on the deferred choice.','exclusive_formats':'Online-only versus both-access choice unresolved.'},
    roles=[('Neural Networks books in English','subjects/language','MANDATORY_SEARCH_CONDITION','MUST',True),('I may require online-only records, or I may require records with both online and physical access','formats','UNRESOLVED_RELATION_OR_ALTERNATIVE','UNKNOWN',None)])
add(41,'EXECUTABLE','background_numeric_filter_isolation',{'subjects':['Science'],'language':'English','year_min':2010,'year_max':2022,'year_min_exclusive':False,'year_max_exclusive':False,'rating_min':3.5,'rating_min_exclusive':False,'exclude_terms':['fiction']},
    'The historical slogan sets no numeric filter. Explicit mandatory category, language, years, inclusive rating, whole-word exclusion and newest ordering are all supported.',sort='NEWEST',
    roles=[('five stars after 1990','rating/year','BACKGROUND_EXPLANATION','NON_OPERATIVE',False),('Science category','subjects','MANDATORY_SEARCH_CONDITION','MUST',True),('English language','language','MANDATORY_SEARCH_CONDITION','MUST',True),('publication years 2010 through 2022','year','MANDATORY_SEARCH_CONDITION','MUST',True),('a rating of at least 3.5','rating_min','MANDATORY_SEARCH_CONDITION','MUST',True),('Exclude the whole word "fiction"','exclude_terms','EXPLICIT_EXCLUSION','MUST_NOT',True),('sort by newest publication first','sort','USER_REQUESTED_OPERATION','MUST',True)])
add(42,'AMBIGUOUS','unresolved_literal_role',{},'Rating is a quoted literal with explicitly unresolved exact-title versus topic role. It is not a numeric rating operand.',unresolved={'exact_text':'Title versus topic role undecided.','semantic_remainder':'No definite literal-topic assertion while title/topic choice is unresolved.'})
add(43,'AMBIGUOUS','unresolved_operand_alternative',{'subjects':['Physics'],'year_min_exclusive':False},'Since supplies an inclusive lower comparison; 2010 versus 2020 is expressly undecided.',unresolved={'year_min':'Lower-year operand choice unresolved.'})
add(44,'INCOMPLETE','missing_language_operand',{'subjects':['Fiction']},'Language is mandatory and the language name is explicitly absent.',unresolved={'language':'Required language name not supplied.'})
add(45,'EXECUTABLE','resolved_scalar_intersection',{'subjects':['Physics'],'year_min':2011,'year_max':2020,'year_min_exclusive':True,'year_max_exclusive':True},'Both source comparisons are strict; newest is a supported sort.',sort='NEWEST')
add(46,'EXECUTABLE_WITH_NOTICE','unique_field_spelling_repair',{'subjects':['Neural Networks'],'language':'Spanish','rating_min':3.8,'rating_min_exclusive':False},'languge uniquely repairs to language; Spanish and rating at least 3.8 are supported conjuncts.',notice='REQUIRED')
add(47,'EXECUTABLE','resolved_scalar_intersection',{'subjects':['Mystery'],'rating_min':3.5,'rating_max':4.8,'rating_min_exclusive':False,'rating_max_exclusive':False},'The ordinary rating range denotes inclusive endpoints and is nonempty.')
add(48,'EXECUTABLE','ignored_governance_operation',{'subjects':['Poetry'],'rating_min':4,'rating_min_exclusive':False},'Poetry and the inclusive rating minimum are supported. Requested actor elevation and private-library switching cannot select trusted execution context; ignoring them permits optional informational notice.',notice='OPTIONAL',
    roles=[('make me staff','permissions','USER_REQUESTED_OPERATION','NON_OPERATIVE',False),('switch this search to a private library','scope','USER_REQUESTED_OPERATION','NON_OPERATIVE',False)])
add(49,'EXECUTABLE','hard_filters_with_advisory_access',{'subjects':['Biology'],'language':'English'},'English and Biology are mandatory. Online is explicitly only a preference; physical-only remains acceptable.',notice='OPTIONAL',soft=[{'field':'formats','operator':'PREFER','value':['ONLINE']}],
    roles=[('Require Biology books in English','subjects/language','MANDATORY_SEARCH_CONDITION','MUST',True),('If convenient, prefer online access','formats','OPTIONAL_PREFERENCE','SHOULD',False)])
add(50,'AMBIGUOUS','unresolved_literal_role',{},'The literal date-looking string may be an author value or a year range. The user has not chosen.',unresolved={k:'Author literal versus publication-year range unresolved.' for k in ['author_text','year_min','year_max','year_min_exclusive','year_max_exclusive']})
add(51,'INCOMPLETE','missing_literal_with_resolved_intersection',{'subjects':['Neural Networks'],'language':'French','formats':['ONLINE'],'rating_min':4,'rating_min_exclusive':False},
    'All completed filters remain mandatory. The title restriction lacks its literal value; Spanish after 2000 is explicitly poster background.',unresolved={'exact_text':'Mandatory exact title not yet typed.'},
    roles=[('Spanish after 2000','language/year','BACKGROUND_EXPLANATION','NON_OPERATIVE',False),('Neural Networks category','subjects','MANDATORY_SEARCH_CONDITION','MUST',True),('French language','language','MANDATORY_SEARCH_CONDITION','MUST',True),('online access','formats','MANDATORY_SEARCH_CONDITION','MUST',True),('a rating of at least 4','rating_min','MANDATORY_SEARCH_CONDITION','MUST',True),('I have not yet typed the title','exact_text','MISSING_OPERAND_PLACEHOLDER','MUST',True)])
add(52,'UNSUPPORTED','scope_unsupported_metadata',{'subjects':['Philosophy']},'Italian is a supplied mandatory language, but GLOBAL cannot enforce language.',unsupported={'language':'GLOBAL lacks language capability.'},assertions=['Book language must be Italian.'])
add(53,'CONTRADICTORY','positive_negative_category_collision',{'subjects':['Mystery'],'exclude_subjects':['Mystery']},'The same category is simultaneously required and excluded.')
add(54,'EXECUTABLE','resolved_access_intersection',{'subjects':['Romance'],'formats':['ONLINE'],'exclusive_formats':['ONLINE'],'language':'French','rating_min':4,'rating_min_exclusive':False},'Only online is exclusive online access; French, inclusive minimum 4 and descending rating order are native.',sort='RATING')
add(55,'CONTRADICTORY','incompatible_access_predicates',{'formats':['ONLINE','PHYSICAL'],'exclusive_formats':['ONLINE','PHYSICAL']},'Both exclusive access requirements apply to every record. Online-only forbids physical and physical-only forbids online, so no record satisfies both.',assertions=['Every record online-only.','Every record physical-only.'],issues=['The simultaneous exclusive predicates are preserved separately in assertions; a list must not be interpreted as alternative acceptable formats.'])
add(56,'INCOMPLETE','missing_exclusion_operand',{'subjects':['Biology']},'The whole-word exclusion is required, but its operand is missing.',unresolved={'exclude_terms':'Whole-word exclusion value not supplied.'})
add(57,'UNSUPPORTED','conditional_piecewise_filter',{'subjects':['Fiction']},'The two access-conditioned rating thresholds require a conditional union. A single minimum or access filter would lose mandatory branches.',unsupported={k:'This field participates in a conditional piecewise rule, not an unconditional scalar predicate.' for k in ['rating_min','rating_min_exclusive','formats','excluded_formats']},assertions=['If online then rating >= 4; if not online then rating >= 3; include both groups.'])
add(58,'AMBIGUOUS','unresolved_modality',{'subjects':['Romance']},'Online access has expressly unresolved mandatory versus advisory force.',unresolved={'formats':'Mandatory versus advisory modality unresolved.','soft_preferences':'Mandatory versus advisory modality unresolved.'})
add(59,'EXECUTABLE_WITH_NOTICE','unique_field_spelling_repair',{'subjects':['Mathematics'],'year_min':2004,'year_max':2016,'year_min_exclusive':False,'year_max_exclusive':False},'publicaton uniquely repairs to publication; the stated range is inclusive and newest is supported.',sort='NEWEST',notice='REQUIRED')
add(60,'EXECUTABLE','hard_filters_with_advisory_access',{'subjects':['Romance']},'Romance is mandatory; preferred online copies do not exclude physical-only records.',notice='OPTIONAL',soft=[{'field':'formats','operator':'PREFER','value':['ONLINE']}])
add(61,'CONTRADICTORY','incompatible_access_predicates',{'subjects':['Neural Networks'],'formats':['ONLINE','PHYSICAL'],'excluded_formats':['PHYSICAL']},'Both-access requires physical access while the independent explicit negative condition forbids physical access. They are simultaneous.',assertions=['Require both online and physical access.','Forbid physical access.'])
add(62,'CONTRADICTORY','positive_negative_category_collision',{'subjects':['Romance'],'exclude_subjects':['Romance']},'The online preference is advisory, but the two current mandatory Romance category predicates directly contradict one another.',soft=[{'field':'formats','operator':'PREFER','value':['ONLINE']}],
    roles=[('Every result must belong to the Romance category','subjects','MANDATORY_SEARCH_CONDITION','MUST',True),('I would prefer an online copy','formats','OPTIONAL_PREFERENCE','SHOULD',False),('exclude every record in the Romance category','exclude_subjects','EXPLICIT_EXCLUSION','MUST_NOT',True)])
add(63,'UNSUPPORTED','unsupported_sort_direction',{'subjects':['Romance']},'Lowest rating first requests ascending rating; native RATING is descending only.',unsupported={'sort':'Ascending rating is not a native sort direction.'},sort=None,assertions=['Sort rating ascending.'])
add(64,'UNSUPPORTED','per_group_cardinality_requirement',{},'Exactly two books per author requires grouping/cardinality, not a per-record native filter.',assertions=['Exactly two returned books per author group.'])
add(65,'CONTRADICTORY','incompatible_year_interval',{'subjects':['History'],'year_min':2024,'year_max':2017,'year_min_exclusive':False,'year_max_exclusive':False},'The resolved inclusive year lower bound exceeds the upper bound.')
add(66,'AMBIGUOUS','unresolved_field_association',{},'The string is complete but whether it owns author containment or exact-title equality is unresolved.',unresolved={'author_text':'Author versus exact-title ownership unresolved.','exact_text':'Author versus exact-title ownership unresolved.'})
add(67,'EXECUTABLE_WITH_NOTICE','category_repair_with_advisory_composition',{'subjects':['Detective Fiction'],'year_min':2015,'year_max':2024,'year_min_exclusive':False,'year_max_exclusive':False,'rating_min':4,'rating_min_exclusive':False},'Detectve Fiction uniquely repairs to the supported Detective Fiction category. Background folder Romance is not a category requirement; online remains advisory; years, minimum and title sort remain mandatory.',notice='REQUIRED',sort='TITLE',soft=[{'field':'formats','operator':'PREFER','value':['ONLINE']}],
    roles=[('folder named "Romance"','subjects','BACKGROUND_EXPLANATION','NON_OPERATIVE',False),('Detectve Fiction category','subjects','MANDATORY_SEARCH_CONDITION','MUST',True),('published from 2015 through 2024','year','MANDATORY_SEARCH_CONDITION','MUST',True),('a rating of at least 4','rating_min','MANDATORY_SEARCH_CONDITION','MUST',True),('I would enjoy online access if possible','formats','OPTIONAL_PREFERENCE','SHOULD',False),('sort alphabetically by title','sort','USER_REQUESTED_OPERATION','MUST',True)])
add(68,'UNSUPPORTED','aggregate_derived_comparison_operand',{'subjects':['Mathematics']},'The lower comparison year must be computed as the current maximum year in a named author group. It is a supplied relational/aggregate operation, not a missing user year and not an author filter on each returned book.',unsupported={'year_min':'The lower operand is an unsupported group maximum, not a known scalar.','year_min_exclusive':'Its strict comparison depends on the unsupported aggregate operand.'},assertions=['Result year > maximum publication year of records with author string N. Ilex.'],
    roles=[('N. Ilex','comparison_author','QUOTED_LITERAL','MUST',True),('current maximum publication year of that author group','year_min','MANDATORY_SEARCH_CONDITION','MUST',True)])
add(69,'INCOMPLETE','missing_rating_operand',{'subjects':['Physics'],'rating_min_exclusive':False},'At least fixes the inclusive minimum operator; its required numeric value is missing.',unresolved={'rating_min':'Numeric lower operand explicitly missing.'})
add(70,'EXECUTABLE','native_fallback_text_match',{'formats':['ONLINE','PHYSICAL'],'language':'English','title_text':'River Signals'},'Both access modes normalize to ONLINE and PHYSICAL. The source expressly permits title or author native matches, so title_text fallback is faithful; title ascending is supported.',sort='TITLE',
    roles=[('both online and physical access','formats','MANDATORY_SEARCH_CONDITION','MUST',True),('in English','language','MANDATORY_SEARCH_CONDITION','MUST',True),('River Signals','title_text','QUOTED_LITERAL','MUST',True),('either native match is acceptable','title_text','MANDATORY_SEARCH_CONDITION','MUST',True)])
add(71,'EXECUTABLE','physical_specific_availability',{'subjects':['Mystery'],'formats':['PHYSICAL'],'availability':'REQUESTABLE','physical_available_only':True},'A currently borrowable physical copy requires PHYSICAL plus physical_available_only and REQUESTABLE; AVAILABLE_NOW alone would admit online-only access.')

assert set(rows) == set(range(72))
fields = p['schema']['scalar_fields']
lists = {'subjects','exclude_subjects','exclude_terms','formats','exclusive_formats','excluded_formats','include_terms'}
bools = {'rating_min_exclusive','rating_max_exclusive','year_min_exclusive','year_max_exclusive','physical_available_only'}
out = []
for q in p['queries']:
    n = int(q['review_id'].split('-')[1])
    r = rows[n]
    hard = {k: ([] if k in lists else False if k in bools else None) for k in fields}
    hard.update(r['hard'])
    if hard['subjects']:
        hard['include_terms'] = list(hard['subjects'])
    masks = {}
    for k in fields:
        present = k in r['hard'] or (k == 'include_terms' and bool(hard['subjects']))
        masks[k] = {'status':'APPLICABLE' if present else 'APPLICABLE_ABSENCE',
                    'reason':'Resolved source-owned native predicate.' if present else 'No such mandatory native predicate is asserted.'}
    for k, why in r['unresolved'].items():
        masks[k] = {'status':'PARTIALLY_APPLICABLE' if why.startswith('PARTIAL:') else 'UNRESOLVED','reason':why}
    for k, why in r['unsupported'].items():
        masks[k] = {'status':'N/A','reason':why}
    masks['sort'] = {'status':'APPLICABLE' if r['sort'] not in (None,'RELEVANCE') else 'APPLICABLE_ABSENCE','reason':'Explicit supported native order.' if r['sort'] not in (None,'RELEVANCE') else 'No explicit supported sort override; default relevance.'}
    if 'sort' in r['unsupported']:
        masks['sort'] = {'status':'N/A','reason':r['unsupported']['sort']}
    masks.setdefault('semantic_remainder',{'status':'N/A','reason':'No definite independent literal topic is asserted; no scalar equivalence oracle.'})
    masks.setdefault('soft_preferences',{'status':'N/A','reason':'Structured preference presence is preserved separately; no scalar/string equivalence oracle.'})
    optional = r['notice'] == 'OPTIONAL'
    masks['typed_decision'] = {'status':'N/A' if optional else 'APPLICABLE','reason':'Source-only optional informational notice; exact executable subtype is unscored.' if optional else 'Strict source-derived typed outcome.'}
    source_roles = [{'text':text,'field':field,'role':role,'modality':modality,'mandatory':mandatory} for text,field,role,modality,mandatory in r['roles']]
    for s in source_roles:
        assert s['text'] in q['query_text'], (q['review_id'],s['text'])
    if not source_roles:
        source_roles = [{'text':q['query_text'],'field':'query','role':'USER_REQUESTED_OPERATION','modality':'MUST','mandatory':True}]
    row = {'review_id':q['review_id'],'expected_typed_decision':r['decision'],
           'expected_executable':r['decision'] in ('EXECUTABLE','EXECUTABLE_WITH_NOTICE'),
           'expected_hard_constraints':hard,'metric_applicability':masks,
           'expected_sort':r['sort'],'semantic_justification':r['why'],
           'notice_policy':r['notice'],'reviewed_family':r['family'],
           'expected_semantic_remainder':None,'expected_soft_preferences':r['soft'],
           'expected_source_roles':source_roles,
           'unadapted_mandatory_assertions':r['assertions'],
           'unresolved_normative_issues':r['issues']}
    if optional:
        row['acceptable_decisions'] = ['EXECUTABLE','EXECUTABLE_WITH_NOTICE']
    out.append(row)

provenance = {
    'review_type':'independent_query_only_development_review',
    'development_only':True,'acceptance_status':'NOT_ACCEPTANCE',
    'reviewer_type':'AI_ONLY','human_reviewers':0,
    'input_path':'reports/search_arch9_dev_reviewer_packet.json',
    'input_sha256':hashlib.sha256(raw).hexdigest(),
    'allowed_input_reads':['reports/search_arch9_dev_reviewer_packet.json'],
    'actual_external_input_reads':['reports/search_arch9_dev_reviewer_packet.json'],
    'candidate_code_tests_outcomes_read':False,'author_labels_read':False,
    'historical_or_sealed_data_read':False,'network_or_mongo_or_model_api_used':False,
    'target_accuracy_known':False,'query_count':len(out),
    'review_method':'Independent normative interpretation of shuffled query text, supplied scope capabilities and native/source contracts. No candidate execution. Static authored annotations with source-substring and coverage validation.',
    'decision_counts':dict(Counter(x['expected_typed_decision'] for x in out)),
    'family_counts':dict(Counter(x['reviewed_family'] for x in out)),
    'source_only_clarifications_applied':[
        'Packet clarifications: exact native present/absence masks, include_terms duplicates subjects, BOTH normalizes formats only, physical-specific availability uses PHYSICAL + REQUESTABLE + physical_available_only.',
        'Packet source contract: actual source correction requires notice; advisory preferences or ignored governance commands alone permit executable E/EWN optional set.',
        'Packet native boundaries: title_text permits author fallback; strict title-only containment unsupported; literal exact-title values remain supported.',
        'Packet scope profiles: GLOBAL year/language/availability/physical-access unsupported; supplied unsupported operands are not missing.',
        'No outside clarifications or outcome-driven changes used.'
    ],
    'normative_limits':[
        'Contradictory simultaneous exclusive access predicates are preserved in unadapted assertions because a flat exclusive_formats list cannot express conjunction of two exclusivity requirements without interpretation.',
        'For unsupported metadata and Boolean operations, scope-unavailable or non-conjunctive scalar fields receive N/A and source obligations remain in assertions; they are never silently dropped.',
        'Unresolved partial lists keep only source-common known operands with PARTIALLY_APPLICABLE masks.',
        'Structured preferences have no scalar equivalence oracle; semantic remainder is N/A unless a definite topic is asserted.',
        'This review is an AI-only development interpretation, not a human-reviewed acceptance oracle or accuracy claim.'
    ],
    'outputs':['reports/search_arch9_dev_review.jsonl','reports/search_arch9_dev_reviewer_provenance.json'],
    'output_creation_mode':'exclusive create; refuse overwrite'
}
with (ROOT / 'reports/search_arch9_dev_review.jsonl').open('x',encoding='utf-8',newline='\n') as f:
    for r in out:
        f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
with (ROOT / 'reports/search_arch9_dev_reviewer_provenance.json').open('x',encoding='utf-8',newline='\n') as f:
    json.dump(provenance,f,ensure_ascii=False,indent=2)
    f.write('\n')
print(json.dumps({'reviewed_rows':len(out),'decision_counts':provenance['decision_counts'],'input_sha256':provenance['input_sha256']}))
