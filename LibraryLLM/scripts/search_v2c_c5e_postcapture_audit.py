"""Supplemental audit of immutable capture; not a second acceptance attempt.

The primary scorer's scalar-mask lookup omitted the reviewed
`hard_constraints.` prefix. Preserve its output and disclose that limitation.
Apply the same existing norm/BOTH/scalar absence rules to the already frozen
gold and predictions for a separately named operand diagnostic. No parser,
candidate edit, label edit, threshold, new semantic equivalence or recapture.
"""
from pathlib import Path
from collections import Counter,defaultdict
import json,hashlib,statistics,math
from scripts.search_v2c_c5c_score import OPERANDS,LISTS,rate
from scripts.search_v2c_c_evaluate import norm
from scripts.search_v2c_c4_evaluate import normalize_both
R=Path('reports');P='search_v2c_c5e_'
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def rows(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf8').splitlines() if s.strip()]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf8') as f:json.dump(v,f,indent=2,sort_keys=True,ensure_ascii=False)
def main():
    freeze=load(R/(P+'candidate_freeze.json'));assert all(sha(p)==h for p,h in freeze['files'].items())
    complete=load(R/(P+'independent_prediction_complete.json'))
    assert sha(R/(P+'independent_predictions.jsonl'))==complete['prediction_sha256']
    gold={r['case_id']:r for r in rows(R/(P+'reviewed_population_v3.jsonl'))}
    pred=rows(R/(P+'independent_predictions.jsonl'));scored=rows(R/(P+'independent_scored_observations.jsonl'))
    fields=defaultdict(list);details=[];excluded=[];semantic_absence=[];semantic_unadapted=[]
    for p in pred:
        g=gold[p['case_id']];a=normalize_both(p['actual_plan']);hard=normalize_both(g['expected_hard_constraints'])
        assertions=[];mismatch=[]
        for field in sorted(OPERANDS):
            mask=g['metric_applicability'].get('hard_constraints.'+field,g.get('expected_hard_field_masks',{}).get(field,{}))
            state=mask.get('status') if isinstance(mask,dict) else mask
            if state not in ['APPLICABLE','APPLICABLE_ABSENCE','PARTIALLY_APPLICABLE']:
                excluded.append({'case_id':g['case_id'],'field':field,'mask':mask});continue
            if state=='APPLICABLE_ABSENCE':wanted=[] if field in LISTS else False if field.endswith('_exclusive') else None
            else:
                assert field in hard or 'resolved_value' in mask,(g['case_id'],field)
                wanted=mask.get('resolved_value',hard.get(field))
            got=a.get(field)
            good=set(norm(wanted)).issubset(set(norm(got))) if state=='PARTIALLY_APPLICABLE' and isinstance(wanted,list) and isinstance(got,list) else norm(wanted)==norm(got)
            record={'field':field,'correct':good,'expected':wanted,'actual':got,'mask':mask}
            assertions.append(record);fields[field].append(good)
            if not good:mismatch.append(record)
        details.append({'case_id':g['case_id'],'scope':g['scope_type'],'stratum':g['decision_stratum'],'expected_execution':g['expected_executable'],
             'actual_execution':p['executable'],'assertions':assertions,'mismatches':mismatch,'all_scored_operands_correct':not mismatch})
        semantic=g['expected_semantic_remainder'];smask=g['metric_applicability']['semantic_remainder']['status']
        if smask=='APPLICABLE_ABSENCE':semantic_absence.append({'case_id':g['case_id'],'correct':not bool(a.get('semantic_text')),'actual':a.get('semantic_text')})
        else:semantic_unadapted.append({'case_id':g['case_id'],'gold':semantic,'actual':a.get('semantic_text'),'reason':'Structured semantic/advisory assertion list vs native string; no frozen oracle adapter. Primary string/list equality is not semantic accuracy.'})
    unsafe=[r for r in scored if r['expected_execution'] is False and r['execution'] is True]
    misses=[r for r in scored if r['expected_execution'] is True and r['execution'] is False]
    patterns={}
    for r in scored:
        pat=r['shared_semantic_pattern_id'];entry=patterns.setdefault(pat,{'contexts':0,'expected_decision':r['expected_decision'],'actual_decisions':Counter(),'false_execution':0,'missed_execution':0,'case_ids':[]})
        entry['contexts']+=1;entry['actual_decisions'][r['decision']]+=1;entry['false_execution']+=r in unsafe;entry['missed_execution']+=r in misses;entry['case_ids'].append(r['case_id'])
    write('supplemental_operand_audit.json',{'status':'SUPPLEMENTAL_POSTCAPTURE_DIAGNOSTIC_NOT_PRIMARY_ACCEPTANCE','frozen_candidate_unchanged':True,'primary_predictions_unchanged':True,
          'primary_scoring_limitation':'Primary scalar mask lookup expected unprefixed keys, but reviewed masks are hard_constraints.FIELD; all scalar fields were omitted from primary strict metric. Typed/execution confusion unaffected. Primary strict5/90 is incomplete and not used for readiness.',
          'method':'Mechanical mask-key namespace lookup; existing C5C scalar absence and exact norm/C4 formats-only BOTH comparison, no normative changes or new equivalence.',
          'per_field':{k:rate(sum(v),len(v)) for k,v in fields.items()},'all_scored_operand_match':rate(sum(d['all_scored_operands_correct'] for d in details),len(details)),
          'details':details,'excluded_unresolved_or_unadapted':excluded,'known_absence_semantic':{'rate':rate(sum(x['correct'] for x in semantic_absence),len(semantic_absence)),'rows':semantic_absence},
          'semantic_list_to_string_adapter_unavailable':semantic_unadapted,'literal_exact_match_qualifiers':'Only operand values compared. Native exact matching semantics are not inferred from string equality.',
          'source_gold_sha256':sha(R/(P+'reviewed_population_v3.jsonl')),'source_prediction_sha256':sha(R/(P+'independent_predictions.jsonl')),'parser_calls':0,'scorer_changes_to_primary':0})
    times=sorted(p['elapsed_ms'] for p in pred)
    write('acceptance_error_analysis.json',{'population':'C independent90 contexts,18 shared patterns; one prediction per context','typed_correct':sum(r['typed_correct'] for r in scored),'execution_correct':sum(r['execution_correct'] for r in scored),
          'false_execution':{'rate':rate(len(unsafe),sum(r['expected_execution'] is False for r in scored)),'case_ids':[r['case_id'] for r in unsafe]},
          'missed_execution':{'rate':rate(len(misses),sum(r['expected_execution'] is True for r in scored)),'case_ids':[r['case_id'] for r in misses]},
          'patterns':patterns,'critical_failures_retained':True,'readiness':'BLOCKED','postcapture_candidate_changes':0,'acceptance_recaptures':0,'human_reviewed':0,
          'parser_capture_latency':{'count':len(times),'p50_ms':statistics.median(times),'p95_ms':times[math.ceil(.95*len(times))-1],'max_ms':max(times),'instrumentation':'One gold-blind parser call per acceptance context; no tracemalloc; import warmup precedes capture.'},
          'confirmed_failure_mechanisms':[
             'A2/A3: unresolved exclusion ownership/category alternatives execute; a nearby recognized value does not establish mandatory interpretation.',
             'I1/I3: explicit empty creator/rating data in ordinary sentences executes; nonempty placeholder surface text is incorrectly treated as an operand or dropped.',
             'U3: creator-wide aggregate rating is mistaken for per-work average rating, silently broadening a strict unsupported condition.',
             'C1/S1: legitimate bibliographic intersections are refused by broad strict-residue detection, even though their intended fields are supported.',
             'Plural titles and sort grammar can be repaired into title/preference cues. A source substring and a unique edit alone are insufficient semantic evidence.',
             'Quoted exact bibliographic clauses can absorb following sentences; canonical tags and broad whole-word exclusion paraphrases are not consistently retained.',
             'No contradictory independent case receives the intended CONTRADICTORY kind; their blocking is insufficient evidence of correct semantic recognition.'
          ],
          'minimum_safe_resolution':[
             'Repair sentence/literal field boundaries, legitimate cue protection, and mandatory relationship/completeness ownership in a new disabled revision; do not add acceptance-ID exceptions.',
             'Distinguish creator-wide aggregate predicates from per-work fields and block unsupported operations without blanket refusal of clear requests.',
             'Correct the scorer mask namespace and keep structured semantic assertions unscored until an independently reviewed native representation adapter exists; preserve this primary scoring output.',
             'Qualify the new revision with its focused regressions, disposable native workflow checks, and genuinely fresh independently reviewed structurally isolated acceptance. This exposed90 cannot be recaptured as fresh acceptance.'
          ],'next_phase_started':False})
    print(json.dumps({'supplemental_scalar_match':sum(d['all_scored_operands_correct'] for d in details),'denominator':len(details),'false_execution':len(unsafe),'missed':len(misses),'primary_preserved':True}))
if __name__=='__main__':main()
