"""Read the preserved primary outputs only; never rerun or modify the candidate."""
from pathlib import Path
from collections import Counter
import json,hashlib

R=Path('reports');P='search_combined8_'
def rows(name):return [json.loads(s) for s in (R/(P+name+'.jsonl')).read_text(encoding='utf-8').splitlines()]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    gold={g['case_id']:g for g in rows('reviewed_population_r1')};pred={p['case_id']:p for p in rows('independent_predictions')};scored=rows('independent_scored_observations')
    unsafe=[x for x in scored if x['expected_execution'] is False and x['execution'] is True]
    missed=[x for x in scored if x['expected_execution'] is True and x['execution'] is not True]
    critical=[x for x in scored if x['critical_executed_operand_mismatches']]
    def trace(x):
        g=gold[x['case_id']];p=pred[x['case_id']]['actual_plan'];d=p['decision']
        return dict(case_id=x['case_id'],query=g['query_text'],scope=g['scope_type'],expected=x['expected_decision'],actual=x['decision'],
                    mismatches=x['mismatches'],critical_fields=x['critical_executed_operand_mismatches'],
                    recorded_coverage_complete=d.get('source_coverage',{}).get('complete_within_detected_obligations'),
                    proof_violations=d.get('execution_proof',{}).get('violations'),
                    source_requirements=d.get('query_ir_contract',{}).get('requirements'),normative_rationale=g['semantic_justification'])
    report=dict(population='205 fresh primary contexts, now exposed development; no recapture or retuning',
                parser_calls=0,primary_predictions_sha256=sha(R/(P+'independent_predictions.jsonl')),
                candidate_source_changed=False,gold_changed_after_primary=False,
                unsafe_by_expected_kind=dict(Counter(x['expected_decision'] for x in unsafe)),
                confusion=dict(Counter(x['expected_decision']+' -> '+str(x['decision']) for x in scored)),
                executed_contexts=sum(x['execution'] is True for x in scored),executed_critical_contexts=len(critical),
                valid_gold_executed_contexts=sum(x['execution'] is True and x['expected_execution'] for x in scored),
                valid_gold_executed_critical=sum(x['execution'] is True and x['expected_execution'] and bool(x['critical_executed_operand_mismatches']) for x in scored),
                critical_field_frequency=dict(Counter(f for x in critical for f in x['critical_executed_operand_mismatches'])),
                unsafe_with_recorded_complete_coverage=sum(pred[x['case_id']]['actual_plan']['decision'].get('source_coverage',{}).get('complete_within_detected_obligations') is True for x in unsafe),
                unsafe_coverage_denominator=len(unsafe),
                missed_by_reason=dict(Counter(pred[x['case_id']]['actual_plan']['decision'].get('reason_code') for x in missed)),
                generalized_findings=[
                    dict(classification='Recognition completeness is not established by IR self-consistency',evidence='All unsafe recommendations have recorded coverage_complete=true; unrecognized source requirements become semantic residue outside the obligation set.',next_requirement='Independent source-obligation/ownership analysis must challenge extraction, not only validate the recognized subset.'),
                    dict(classification='Operator and entity ownership are lost',evidence='Exact-title requests become title_text containment; explicitly named authors are omitted. Native title_text also matches authors, so this is a real enforcement weakening.',next_requirement='Represent operation, operand and source owner independently with complete entity/operator boundaries and native capability proof.'),
                    dict(classification='Unresolved choices and missing operands become searchable residue',evidence='Six ambiguous and one incomplete gold contexts are recommended executable; one missing By: placeholder is not represented as an edit obligation.',next_requirement='Typed unresolved owner/value/direction state across clauses and punctuation, with no execution on an unresolved mandatory obligation.'),
                    dict(classification='Unsupported numeric metadata and nested record relations escape the boundary',evidence='Four unsupported contexts execute, including mandatory page/price restrictions and relative rating references. A referenced title can become a result filter.',next_requirement='Domain-owned unsupported/reference nodes must precede scalar/text exclusion fallback, including inflection and nested reference graphs.'),
                    dict(classification='Negation and explanatory ownership are confused',evidence='Not a union invents a text exclusion; exclude prices becomes broad text; removing online access fails to produce the required negative format predicate.',next_requirement='Negation must bind to a semantic domain and governing speech act; metalinguistic negation is not a retrieval exclusion.'),
                    dict(classification='Benign context/advisory paraphrases overblock and contaminate topic transport',evidence='47/67 valid searches blocked;38 IR_UNSUPPORTED,7 IR_AMBIGUOUS,2 IR_INCOMPLETE. Source-role/modality agreement is low and semantic strings retain framing prose.',next_requirement='Stabilize grammatical segments and source roles, preserving free topical text and advisory preferences without inventing hard metadata.')],
                unsafe_traces=[trace(x) for x in unsafe],critical_case_ids=[x['case_id'] for x in critical],
                missed_case_ids=[x['case_id'] for x in missed],
                limitations=['Strict semantic string mismatch is not a vector relevance judgment.','Incorrect nonempty scalar replacement is counted conservatively as both lost intended value and invented actual value.','Development success did not qualify generalization; no new phrase patches or acceptance rerun performed.'],
                next_bounded_investigation=dict(objective='Replace the recognition/coverage circularity with a compositional typed source front end or a schema-constrained learned proposal component plus independent proof. Compare complete pipelines on newly declared development data; do not extend phrase lists indefinitely.',
                    cached_model_resource_requirement_available_RAM_bytes=7784628224,
                    model_quality_requirement='Repair and freeze schema/domain/operator/source ownership extraction; more RAM alone does not fix0/2 schema-valid observed predictions.',
                    model_policy='Existing cached revision only under guards; no training/downloads/remote inference without separate authorization.',
                    acceptance_policy='This205-context primary is now exposed development. Any later acceptance needs a new independently authored/reviewed isolated set after another complete freeze.'))
    with (R/(P+'error_analysis.json')).open('x',encoding='utf-8') as f:json.dump(report,f,indent=2,ensure_ascii=False)
    print(json.dumps({k:report[k] for k in ['unsafe_by_expected_kind','executed_contexts','executed_critical_contexts','unsafe_with_recorded_complete_coverage','unsafe_coverage_denominator']}))

if __name__=='__main__':main()
