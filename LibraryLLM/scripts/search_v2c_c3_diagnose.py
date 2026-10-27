"""Immutable C2 development diagnosis, written before C3 final scoring."""
import json
from collections import defaultdict
from pathlib import Path

R = Path('reports')
CAUSES = {
 'h03_negation_semantic_roles': ('Topical or rhetorical negation treated as strict exclusion', 'HIGH'),
 'c02_combined_presence': ('BOTH versus two positive format predicates; provable representation equivalence', 'REPRESENTATION'),
 'c08_without_scoping': ('Negative operand quantifiers and clause boundaries', 'HIGH'),
 'resume_title_author_mode': ('Literal mode versus SMART author interpretation contract dispute', 'REVIEW_REQUIRED'),
 'c03_kg_negative': ('Canonical subject versus broader text-negative label dispute', 'REVIEW_REQUIRED'),
 'd17_typographical_noise': ('Accepted correction versus soft-only authored label dispute', 'REVIEW_REQUIRED'),
 'd11_negation_scope': ('Canonical negation duplicated into broader text predicate', 'HIGH'),
 'd08_format_direct': ('Canonical negation duplicated into broader text predicate', 'HIGH'),
 'd10_include_exclude': ('List operands inherit operator inconsistently', 'HIGH'),
 'c07_year_intersections': ('Publication by-year consumed as author', 'HIGH'),
 'd22_isbn_like': ('Accepted exact identifier versus semantic-only authored label dispute', 'REVIEW_REQUIRED'),
 'h02_temporal_roles': ('Publication by-year consumed as author', 'HIGH'),
 'd05_by_vs_about': ('Topical biography framing consumed as category', 'MEDIUM'),
 'h10_private_scope_absence': ('Metalinguistic negation treated as strict exclusion', 'HIGH'),
 'c09_scope_switch_labels': ('Explicit subject clause consumed as author', 'HIGH'),
 'c11_unsupported_positive_boolean': ('Unrepresentable positive format/subject OR executed', 'HIGH'),
 'd12_multi_reordering': ('Ambiguous list scope requires independent review', 'REVIEW_REQUIRED'),
 'h09_author_appositives': ('Negative phrase crosses semicolon and author clause', 'HIGH'),
}

def main():
    original = json.loads((R/'search_v2c_c2_false_hard_filters_after.json').read_text())['cases']
    groups = defaultdict(list)
    for row in original:
        groups[row['family_id']].append(row)
    clusters = []
    for family, rows in sorted(groups.items(), key=lambda p: -len(p[1])):
        cause, severity = CAUSES.get(family, ('Unclassified structural dispute', 'REVIEW_REQUIRED'))
        examples = []
        for row in rows:
            fields = {f[0] for f in row['false_filters']}
            examples.append({'query_id': row['query_id'], 'query': row['query_text'],
                'recognized_spans': row['source_spans'], 'invented_fields': row['false_filters'],
                'expected_fields': {k:v for k,v in row['expected_strict_filters'].items()
                                    if any(f in k for f in fields)},
                'candidate_eligibility_impact': 'Equivalent conjunction' if severity=='REPRESENTATION' else
                    'Extra hard predicate can reject otherwise eligible candidates; contract review may establish label defect',
                'severity': severity})
        clusters.append({'family': family, 'cause': cause, 'count': len(rows), 'severity': severity,
                         'representative_examples': examples[:3], 'cases': examples})
    out = {'basis': 'Entire immutable C2 development false-filter report; no C3 predictions',
           'case_count': len(original), 'clustered_count': sum(g['count'] for g in clusters),
           'clusters': clusters,
           'format_equivalence_proof': {'rule': 'Expand positive BOTH into ONLINE and PHYSICAL atoms in every actual and expected plan',
              'truth_table': [{'online': o, 'physical': p, 'BOTH': o and p,
                              'ONLINE_AND_PHYSICAL': o and p} for o in (False,True) for p in (False,True)],
              'limits': 'Positive presence only. ONLY and excluded formats remain separate. No equivalence between canonical subject exclusion and text exclusion.',
              'raw_scores_preserved': True}}
    assert out['clustered_count']==455
    (R/'search_v2c_c3_false_hard_filter_clusters.json').write_text(json.dumps(out,indent=2),encoding='utf8')

if __name__=='__main__':main()
