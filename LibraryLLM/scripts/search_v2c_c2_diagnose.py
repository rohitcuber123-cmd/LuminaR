"""Classify frozen DEVELOPMENT evidence before any parser changes."""
from collections import Counter, defaultdict
import json
from pathlib import Path
from scripts.search_v2c_c2_benchmark import write, read_rows


def main():
    R=Path('reports')
    cases={r['query_id']:r for r in read_rows(R/'search_v2c_c_resume_development.jsonl')}
    observations=read_rows(R/'search_v2c_c_resume_development_observations.jsonl')
    classified=[]
    for row in observations:
        if row['exact']:continue
        details=[]
        for field,mismatch in row['mismatches'].items():
            category='G. UNKNOWN / REQUIRES REVIEW'
            reason='No independent semantic conclusion for this dimension; raw error retained.'
            if field=='exclude_terms' and row['actual_plan']['exclude_subjects'] and mismatch['expected']==[]:
                category='E. REPRESENTATION DIFFERENCE WITH NON-EQUIVALENT OR BROADER SEMANTICS'
                reason='matches() checks exclude_terms against title, author, description and subject; exclude_subjects checks canonical subjects only. A title mentioning Romance with another subject is a counterexample.'
            elif row['family_id'] in ['resume_title_author_mode','d22_isbn_like']:
                category='C. GOLD-LABEL AMBIGUITY'
                reason='Accepted literal TITLE_AUTHOR / identifier contract differs from authored semantic expectation; no label correction made.'
            elif row['family_id']=='d17_typographical_noise' and field in ['subjects','semantic_text','intent']:
                category='C. GOLD-LABEL AMBIGUITY'
                reason='Conservative typo repair is an accepted feature but gold expects soft literal semantics; independent policy review required.'
            elif row['family_id'] in ['d05_by_vs_about','d32_author_subject_names'] and field in ['author_text','title_text','subjects','semantic_text']:
                category='A. CONFIRMED PARSER DEFECT'
                reason='Author span crosses explicit about/on boundary or vocabulary-resolved subject is incorrectly converted into a title.'
            elif row['family_id']=='d11_negation_scope' and row['false_filters']:
                category='A. CONFIRMED PARSER DEFECT'
                reason='Negative recognizer consumes topical not after books about / word not rather than an explicit catalogue exclusion.'
            elif row['expected_decision'] in ['CONTRADICTORY','INCOMPLETE','UNSUPPORTED']:
                if row['family_id']=='d13_rating_contradictions' and any(c.get('code')=='rating_domain_assumption' for c in cases[row['query_id']].get('label_review_concerns',[])):
                    category='C. GOLD-LABEL AMBIGUITY';reason='Pre-existing output-blind review flags unproven rating-domain expectation; raw labels retained.'
                elif row['decision']=='UNSUPPORTED' and row['expected_decision']=='UNSUPPORTED':
                    category='F. UNSUPPORTED FEATURE CORRECTLY REJECTED';reason='Execution is correctly rejected; remaining mismatch concerns representation/field naming, not unsafe enforcement.'
                else:
                    category='A. CONFIRMED PARSER DEFECT';reason='Explicit source cue requires a typed blocked decision or mathematical contradiction; recognizer omits or misbounds it.'
            elif field.startswith('rating') or field.startswith('year'):
                category='A. CONFIRMED PARSER DEFECT';reason='Explicit comparator/field grammar has an operand or source boundary not recognized by current patterns.'
            details.append({'dimension':field,'classification':category,'reason':reason,'original_mismatch':mismatch})
        classified.append({'query_id':row['query_id'],'family_id':row['family_id'],'query_text':cases[row['query_id']]['query_text'],
                           'details':details,'parser_output_visible_to_reviewer':True,'labels_changed':False})
    clusters=defaultdict(list)
    for row in observations:
        if not row['false_filters']:continue
        case=cases[row['query_id']]
        clusters[row['family_id']].append({**row,'query_text':case['query_text'],
            'expected_strict_filters':{k:v for k,v in case.items() if k.startswith('expected_')},
            'recognized_source_spans':row['actual_plan']['source_spans'],
            'eligible_candidate_set_changes':True,'can_silently_exclude_or_introduce':True,
            'candidate_set_caution':'Title-mode and identifier/typo gold disputes remain C/G, not proven production errors.'})
    write('error_taxonomy.json', {'population':'Frozen V1 development observations only; before parser edits',
        'categories':{'A':'Confirmed parser defect','B':'Confirmed evaluator defect','C':'Gold-label ambiguity','D':'Provably execution-equivalent representation','E':'Non-equivalent/broader representation','F':'Unsupported correctly rejected','G':'Unknown/requires review'},
        'dimension_counts':dict(Counter(d['classification'] for r in classified for d in r['details'])), 'cases':classified,
        'evaluator_defects_confirmed':0,'equivalences_proven':0})
    write('false_hard_filters_before.json', {'population':'Original 3742 development rows including seven duplicates', 'case_count':sum(map(len,clusters.values())),
        'clusters':[{'family':family,'count':len(rows),'representative':rows[0]['query_text'],'cases':rows} for family,rows in sorted(clusters.items(),key=lambda kv:-len(kv[1]))]})
    write('unsafe_before.json', {'population':'Original/raw V1','blocked_denominator':867,'all_denominator':3742,'cases':[r for r in observations if r['unsafe_auto_parse']]})
    write('label_review.json', {'changed_development_labels':[], 'labels_changed':0,'parser_outputs_visible_to_root':True,
          'independent_gold_corrections':0,'policy':'Disputed labels remain unchanged. No score may use a root review as an independent correction.'})
    (R/'search_v2c_c2_evaluator_rules.md').write_text('''# C2 evaluator rules (c2-development-1)

No evaluator semantic correction is justified by the current review. Reuse the
V1 strict expected-plan adapter, atom definitions, comparator and safety metrics.
Raw V1 rates remain available alongside V2 deduplicated rates. The documented
atomic view compares canonical field/value/operator atoms. No additional
normalization or case-specific exception is applied.

Subject exclusion and text exclusion are NOT equivalent: a book whose subject
is History but title mentions Romance is rejected only by the latter. Therefore
an extra exclude_terms atom stays an error. Do not collapse those fields.

Pure list order/case/whitespace adapters are inherited and disclosed; literal
source JSON and original labels remain preserved. Strict plan match means all
authored dimensions compared, not byte equality of dataclass provenance.

Blocked-case unsafe auto-parse uses blocked gold rows, with all-case incidence
reported separately. Completeness, unsupported and contradiction denominators
are frozen labels. Supported contradiction diagnostic is additive and excludes
only the pre-existing independently flagged rating_domain_assumption cases;
the raw full contradiction metric is never replaced.

No calibration/heldout entry point exists in the C2 development evaluator.
''',encoding='utf8')
    print(json.dumps({'mismatching_cases':len(classified),'false_filter_cases':sum(map(len,clusters.values())),'labels_changed':0}))

if __name__=='__main__':main()
