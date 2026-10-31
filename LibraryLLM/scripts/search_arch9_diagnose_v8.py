"""Analyze V8 independent failures across all 42 families and 205 cases.
Generate reports/search_arch9_root_cause_matrix.json with the 12-stage classification.
"""
from pathlib import Path
import json, sys
sys.path.insert(0, '.')
from collections import defaultdict, Counter

R = Path('reports')

STAGES = [
    "1. Source segmentation",
    "2. Intent identification",
    "3. Source-role interpretation",
    "4. Required/advisory modality",
    "5. Operator ownership",
    "6. Field/domain identification",
    "7. Operand extraction",
    "8. Relationship recognition",
    "9. Missing/unknown classification",
    "10. Capability checking",
    "11. Query-plan projection",
    "12. Execution decision"
]

def load_data():
    gold = [json.loads(line) for line in (R / 'search_combined8_reviewed_population_r1.jsonl').read_text(encoding='utf-8').splitlines()]
    preds = [json.loads(line) for line in (R / 'search_combined8_independent_predictions.jsonl').read_text(encoding='utf-8').splitlines()]
    pred_map = {p['case_id']: p for p in preds}
    from scripts.search_combined8_score_adapter import score
    results = [score(g, pred_map[g['case_id']]) for g in gold]
    return gold, preds, pred_map, results

def classify_case(g, p, r):
    query = g['query_text'].lower()
    exp_dec = g['expected_typed_decision']
    act_dec = r['decision']
    exp_exec = g['expected_executable']
    act_exec = r['execution']
    mismatches = r.get('mismatches', {})
    crit = r.get('critical_executed_operand_mismatches', [])
    plan = p.get('actual_plan', {})
    sem = g.get('semantic_justification', '')
    fam = g.get('family_id', '')

    # Analyze first wrong stage
    stage = None
    fault_layer = None
    remedy = None
    intended = g.get('expected_hard_constraints', {})
    candidate_repr = {f: plan.get(f) for f in ['title_text', 'author_text', 'subjects', 'formats', 'rating_min', 'rating_max', 'year_min', 'year_max', 'sort', 'semantic_text'] if plan.get(f) is not None}
    capability_limitation = None

    # Check for specific failure patterns
    if 'pages' in query or 'page' in query or 'price' in query or 'cost' in query or 'publisher' in query or 'edition' in query:
        stage = "10. Capability checking"
        fault_layer = "validation"
        capability_limitation = "Page count, price, publisher, edition are unsupported attributes in LuminaR native catalog."
        remedy = "Detect unsupported metadata domain obligations and reject execution with UNSUPPORTED before falling back to generic tokenization."

    elif 'relative' in query or 'higher rating than' in query or 'more stars than' in query or 'same author as' in query or 'books related to' in query:
        stage = "8. Relationship recognition"
        fault_layer = "interpretation"
        capability_limitation = "Cross-book relative comparisons (e.g. higher rating than Book X) are unsupported by backend."
        remedy = "Recognize cross-book reference and relative entity dependency expressions; map to UNSUPPORTED or target clarification."

    elif 'by:' in query and ('by: ' in query or query.endswith('by:') or 'by: and' in query or 'by: with' in query):
        stage = "9. Missing/unknown classification"
        fault_layer = "interpretation"
        remedy = "Treat explicit missing author placeholder 'by:' as INCOMPLETE obligation requiring targeted clarification."

    elif 'either' in query or ' or ' in query or 'choose between' in query or 'whether' in query:
        stage = "9. Missing/unknown classification"
        fault_layer = "interpretation"
        remedy = "Identify unresolved disjunctive options (titles, authors, formats) as AMBIGUOUS requiring choice clarification."

    elif 'not a union' in query or 'not a ' in query or 'not searching for' in query or 'clarification:' in query:
        stage = "3. Source-role interpretation"
        fault_layer = "interpretation"
        remedy = "Distinguish metalinguistic instructions/negations from document attribute constraints; do not treat explanatory discourse as exclude_terms."

    elif 'exact title' in query or 'titled exactly' in query or 'verbatim title' in query:
        stage = "5. Operator ownership"
        fault_layer = "planning"
        capability_limitation = "LuminaR native projection only supports broad title_text; exact-title literal requires specific match semantics."
        remedy = "Enforce exact title operator semantics in validation; if native execution cannot guarantee exactness without author matching, warn or require notice."

    elif exp_exec is False and act_exec is True:
        # Unsafe execution
        if 'unsupported' in exp_dec.lower():
            stage = "10. Capability checking"
            fault_layer = "validation"
            remedy = "Independent obligation audit must reject execution if unrepresented source obligations exceed native capabilities."
        elif 'ambiguous' in exp_dec.lower():
            stage = "9. Missing/unknown classification"
            fault_layer = "interpretation"
            remedy = "Represent alternative interpretations explicitly in Interpretation contract and prevent planning when alternatives exist."
        elif 'incomplete' in exp_dec.lower():
            stage = "9. Missing/unknown classification"
            fault_layer = "interpretation"
            remedy = "Model missing required parameters as INCOMPLETE obligations."
        elif 'contradictory' in exp_dec.lower():
            stage = "10. Capability checking"
            fault_layer = "validation"
            remedy = "Cross-validate hard constraint intervals (e.g. min > max) during validation contract."
        else:
            stage = "12. Execution decision"
            fault_layer = "validation"
            remedy = "Proof compiler must enforce non-executable gating when source obligations remain unvalidated."

    elif exp_exec is True and act_exec is False:
        # Missed valid execution
        if 'about' in query and ('rating' in query or 'stars' in query or 'year' in query or 'published' in query):
            stage = "3. Source-role interpretation"
            fault_layer = "interpretation"
            remedy = "Separate free topical phrases ('about X') from structured predicates ('rated 4+') so topics do not erase valid filters."
        elif 'sort' in query:
            stage = "5. Operator ownership"
            fault_layer = "interpretation"
            remedy = "Parse sort directives distinctly from author/title search text."
        else:
            stage = "4. Required/advisory modality"
            fault_layer = "interpretation"
            remedy = "Distinguish advisory framing ('looking for a nice read') from mandatory search criteria; do not mark advisory phrasing as unsupported."

    elif crit:
        # Critical operand mismatch
        if 'author_text' in crit:
            stage = "7. Operand extraction"
            fault_layer = "interpretation"
            remedy = "Preserve author entity boundaries and avoid dropping named authors when trailing clauses are present."
        elif 'sort' in crit:
            stage = "5. Operator ownership"
            fault_layer = "interpretation"
            remedy = "Extract sort field and direction precisely from user phrase."
        elif 'rating_min' in crit or 'rating_max' in crit:
            stage = "5. Operator ownership"
            fault_layer = "interpretation"
            remedy = "Distinguish inclusive/exclusive comparisons and upper/lower bounds."
        else:
            stage = "6. Field/domain identification"
            fault_layer = "interpretation"
            remedy = "Bind extracted operands strictly to their respective ontology fields."

    else:
        # Decision or non-critical mismatch
        stage = "4. Required/advisory modality"
        fault_layer = "interpretation"
        remedy = "Model source unit obligations with clear modality and ownership."

    return {
        'case_id': g['case_id'],
        'family_id': fam,
        'query_text': g['query_text'],
        'scope_type': g['scope_type'],
        'expected_typed_decision': exp_dec,
        'actual_typed_decision': act_dec,
        'expected_executable': exp_exec,
        'actual_executable': act_exec,
        'critical_executed_operand_mismatches': crit,
        'mismatches': list(mismatches.keys()),
        'first_incorrect_stage': stage,
        'fault_layer': fault_layer,
        'capability_limitation': capability_limitation,
        'intended_semantics': g.get('semantic_justification', ''),
        'candidate_representation': candidate_repr,
        'architectural_remedy': remedy
    }

def main():
    gold, preds, pred_map, results = load_data()
    all_cases = []
    family_cases = defaultdict(list)

    for g, p, r in zip(gold, [pred_map[g['case_id']] for g in gold], results):
        c_diag = classify_case(g, p, r)
        c_diag['is_failure'] = not r['typed_correct'] or not r['execution_correct'] or bool(r['critical_executed_operand_mismatches'])
        all_cases.append(c_diag)
        family_cases[g['family_id']].append(c_diag)

    # Family-level synthesis
    family_matrix = {}
    for fam, cases in sorted(family_cases.items()):
        total = len(cases)
        failed = sum(1 for c in cases if c['is_failure'])
        stages = Counter(c['first_incorrect_stage'] for c in cases if c['is_failure'])
        layers = Counter(c['fault_layer'] for c in cases if c['is_failure'])
        primary_stage = stages.most_common(1)[0][0] if stages else "N/A (All Passed)"
        primary_layer = layers.most_common(1)[0][0] if layers else "N/A"
        remedies = list({c['architectural_remedy'] for c in cases if c['architectural_remedy']})
        caps = list({c['capability_limitation'] for c in cases if c['capability_limitation']})

        family_matrix[fam] = {
            'family_id': fam,
            'total_cases': total,
            'failed_cases': failed,
            'pass_rate': (total - failed) / total,
            'primary_stage': primary_stage,
            'stage_distribution': dict(stages),
            'primary_fault_layer': primary_layer,
            'representative_query': cases[0]['query_text'],
            'semantic_justification': cases[0]['intended_semantics'],
            'capability_limitations': caps,
            'architectural_remedies': remedies,
            'case_ids': [c['case_id'] for c in cases]
        }

    report = {
        'total_cases': len(all_cases),
        'total_families': len(family_matrix),
        'total_failed_cases': sum(1 for c in all_cases if c['is_failure']),
        'stage_summary': dict(Counter(c['first_incorrect_stage'] for c in all_cases if c['is_failure'])),
        'fault_layer_summary': dict(Counter(c['fault_layer'] for c in all_cases if c['is_failure'])),
        'families': family_matrix,
        'cases': all_cases
    }

    out_path = R / 'search_arch9_root_cause_matrix.json'
    with out_path.open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Successfully generated root cause matrix: {len(family_matrix)} families, {len(all_cases)} cases")
    print("Stage breakdown:", json.dumps(report['stage_summary'], indent=2))
    print("Fault layer breakdown:", json.dumps(report['fault_layer_summary'], indent=2))

if __name__ == '__main__':
    main()
