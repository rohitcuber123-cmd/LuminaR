"""Frozen-capture-only error analysis and gate application; zero parser calls."""
from pathlib import Path
from collections import Counter,defaultdict
import json,hashlib
R=Path('reports');P='search_comp3_'
def load(n):return json.loads((R/(P+n)).read_text(encoding='utf8'))
def rows(n):return [json.loads(s) for s in (R/(P+n)).read_text(encoding='utf8').splitlines()]
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf8') as f:json.dump(v,f,indent=2,ensure_ascii=False,sort_keys=True)
def main():
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    frozen=load('candidate_freeze.json');assert all(sha(p)==h for p,h in frozen['files'].items())
    gold={g['case_id']:g for g in rows('reviewed_population.jsonl')};pred={p['case_id']:p for p in rows('independent_predictions.jsonl')}
    scored=rows('independent_scored_observations.jsonl');m=load('independent_metrics.json')['overall'];contract=load('acceptance_contract_v2.json')
    checks={'typed_at_least_95_percent':m['typed_accuracy']['percent']>=95,
        'execution_at_least_99_percent':m['execution_accuracy']['percent']>=99,
        'zero_false_execution':m['false_execution']['numerator']==0,
        'missed_valid_at_most_5_percent':m['missed_execution']['percent']<=5,
        'zero_executed_hard_operand_mismatch':not m['critical_executed_operand_case_ids']}
    decision={'parser_gates_passed':all(checks.values()),'checks':checks,'preregistered_contract_sha256':sha(R/(P+'acceptance_contract_v2.json')),
        'exact_metrics':m,'primary_attempts':1,'retries':0,'candidate_changes_after_capture':0,'gold_changes_after_capture':0,
        'operational_gates_passed':False,'operational_reasons':['Real API/JWT/Mongo durability/current authorization unqualified.','Long choice query and structural completion incompatible.','Actual vector relevance/current health unavailable.','No agreed staging SLO.'],
        'production_activation':False,'FINAL':'PARTIAL','PRODUCTION_READINESS':'BLOCKED'}
    write('independent_gate_decision.json',decision)
    descriptions={
        'F02':'Supported searchable-text exclusion lost when whole-word precedes searchable text; candidate word-order pattern owns only other equivalent forms.',
        'F03':'Declarative language grammar claims the word is as a language value; mandatory English residue produces a safe refusal in four tenant scopes.',
        'F06':'Quoted canonical operand is masked from new canonical recognition; native fallback uses old vocabulary and refuses Fictiom despite shared choice vocabulary.',
        'F08':'IR owns optional publication-year clause, but old NUMBER_WITHOUT_FIELD decision survives and blocks a resolved repaired title request.',
        'F09':'Equivalent negative text syntax lost; tenant declarative language ownership also causes refusal. Global execution loses required exclusion.',
        'F13':'Metalinguistic by/titled assignment is mistaken for a dangling slot although both values are supplied; missing beats ambiguity from incorrect operand role evidence.',
        'F14':'Unresolved negative-domain assignment expressed with between/and fails the limited alternatives recognizer and executes a chosen domain.',
        'F19':'Sort operand lacks a structural-slot owner; inherited optional-year number ambiguity outranks the actual missing sort value.',
        'F22':'Negative bibliographic owner exclude books by is parsed as positive by plus invented excluded Books facet; direct domain guard does not own the grammatical head.',
        'F23':'An unsupported mandatory negative field/value relationship is approximated by broad text tokens, then appears fully consumed and executable.',
        'F24':'Author-level aggregate exclusion not fully owned; inherited optional-year numeric ambiguity produces wrong blocked type.',
        'F29':'Whole-word searchable-text exclusion lost; necessary positive-title/negative-text contradiction is consequently never evaluated.',
        'F30':'Whole-word searchable-text exclusion lost; necessary positive-author/negative-text contradiction is consequently never evaluated.'}
    groups=defaultdict(list);traces=[]
    for x in scored:
        family=x['case_id'].split('-')[1];groups[family].append(x)
        if x['mismatches']:
            g=gold[x['case_id']];p=pred[x['case_id']]
            traces.append({'case_id':x['case_id'],'query_text':g['query_text'],'scope':g['scope_type'],'family':family,
                'cause':descriptions.get(family,'Strict scored representation/sort/operand differences; see frozen assertions.'),
                'gold_expected_type':g['expected_typed_decision'],'gold_hard_fields':g['expected_hard_constraints'],'gold_masks':g['metric_applicability'],
                'actual_plan':p['actual_plan'],'scored':x})
    summaries=[]
    for family,rr in sorted(groups.items()):
        summaries.append({'family':family,'contexts':len(rr),'typed_correct':sum(x['typed_correct'] for x in rr),
            'execution_correct':sum(x['execution_correct'] for x in rr),'false_execution':sum(not x['expected_execution'] and x['execution'] for x in rr),
            'missed_valid':sum(x['expected_execution'] and not x['execution'] for x in rr),
            'executed_hard_operand_failures':sum(bool(x['critical_executed_operand_mismatches']) for x in rr),
            'strict_scored_fields_correct':sum(x['all_scored_dimensions_correct'] for x in rr),'cause':descriptions.get(family,'No typed/execution failure; strict representation differences may remain.')})
    analysis={'status':'FROZEN_PRIMARY_FAILURE_PRESERVED','metrics':m,'actual_executed_denominator':sum(x['execution'] for x in scored),
        'families':summaries,'all_strict_failure_traces':traces,'parser_calls':0,'candidate_retuned':False,'gold_revised':False,
        'general_findings':['Operand-state enums improve represented slots but grammar-role and family coverage remain incomplete.',
            'Old native fallback still authorizes unowned negative fields and relationship interpretations; source span consumption does not prove semantic coverage.',
            'Canonical extraction, repair vocabulary and old decision composition have divergent paths around quoted operands and advisory numerics.',
            'Exposed development perfection did not generalize; this fresh population is now exposed and cannot be fresh acceptance in a later revision.'],
        'next_engineering_proposal':['Require typed domain/operator/operand/source proof for every final hard field, including inherited negative proposals; do not directly execute fallback scalar mutations.',
            'Normalize negative domain and grammatical head composition before entity/facet recognition; keep unsupported field relations typed instead of broad-text approximation.',
            'Represent assignment/domain alternatives and metalinguistic field references as relationships before structural missing-slot scanning.',
            'Make canonical/quoted extraction and advisory ownership feed one decision evidence set; an old unowned number must not reintroduce ambiguity.',
            'Create new development properties across domain/operator order and lexical frames, then use new independent qualification for any changed candidate.'],
        'ranking_quality':'N/A; no actual embedding relevance oracle','finite_sample_only':True}
    write('acceptance_error_analysis.json',analysis)
    print(json.dumps({'parser_gates_passed':decision['parser_gates_passed'],'critical_operands':len(m['critical_executed_operand_case_ids']),
        'executed':analysis['actual_executed_denominator'],'strict_failure_traces':len(traces)}))
if __name__=='__main__':main()
