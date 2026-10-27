"""Cohort A/B analysis; no parser calls or acceptance query access."""
from pathlib import Path
from collections import Counter
import json,hashlib,difflib
R=Path('reports');P='search_v2c_c5e_'
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def rows(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf8').splitlines() if s.strip()]
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf8') as f:json.dump(v,f,indent=2,ensure_ascii=False,sort_keys=True)
def main():
    result=rows(R/(P+'v2_development_scored_observations.jsonl'))
    first={r['case_id']:r for r in rows(R/(P+'development_scored_observations.jsonl'))}
    old={r['case_id']:r for r in rows(R/'search_v2c_c5d_repair_v2_scored_observations.jsonl')}
    operands={'author_text','title_text','subjects','exclude_terms','exclude_subjects','rating_min','rating_max','year_min','year_max','formats','exclusive_formats','excluded_formats','availability','language'}
    functional=[];representations=[];indeterminate=[]
    for r in result:
        for field,m in r['mismatches'].items():
            item={'case_id':r['case_id'],'field':field,'expected_execution':r['expected_execution'],'difference':m}
            if field in operands:
                item['classification']='Confirmed wrong/missing hard filter under frozen scalar oracle; current case is blocked and not executed.'
                functional.append(item)
            elif field=='intent':
                item['classification']='Evaluator-contract disagreement: historical C5 intent representation remains strictly mismatched; no normalization or score change.'
                representations.append(item)
            else:
                item['classification']='Indeterminate strict diagnostic; affected-field taxonomy or residual text is not by itself proof of changed retrieval meaning.'
                indeterminate.append(item)
    positive=[r for r in result if r['expected_execution']]
    ledger=next(r for r in rows(R/(P+'v2_development_predictions.jsonl')) if r['case_id']=='C5A-1-3-12')
    introduced_false=[r['case_id'] for r in result if r['expected_execution'] is False and r['execution'] is True and old[r['case_id']]['execution'] is False]
    introduced_missed=[r['case_id'] for r in result if r['expected_execution'] is True and r['execution'] is False and old[r['case_id']]['execution'] is True]
    write('development_analysis.json',{'population':'A frozen C5C eligible development644; no independent claims','contexts':len(result),
          'typed_correct':sum(r['typed_correct'] for r in result),'execution_correct':sum(r['execution_correct'] for r in result),
          'introduced_false_execution_vs_C5D_v2':introduced_false,'introduced_missed_execution_vs_C5D_v2':introduced_missed,
          'executable_contexts_with_scored_operand_mismatch':[r['case_id'] for r in positive if set(r['mismatches'])&operands],
          'executable_contexts_with_strict_semantic_remainder_mismatch':[r['case_id'] for r in positive if 'semantic_text' in r['mismatches']],
          'all_strict_mismatch_contexts':sum(bool(r['mismatches']) for r in result),'per_field':load(R/(P+'v2_development_operand_scoring.json'))['per_field'],
          'known_unsafe_resolution':{'case_id':ledger['case_id'],'typed_decision':ledger['typed_decision'],'executable':ledger['executable'],
              'requirements':ledger['actual_plan']['decision']['requirements'],'prediction_output_sha256':ledger['output_sha256']},
          'candidate1_to_2_semantic_mismatch_change':{'before':sum('semantic_text' in r['mismatches'] for r in first.values()),'after':sum('semantic_text' in r['mismatches'] for r in result)},
          'semantic_diagnostic_classes':{'wrong_hard_filter':functional,'historical_representation_contract':representations,'indeterminate':indeterminate},
          'not_claimed':'Strict semantic equality is not universal semantic correctness. No frozen gold, masks or historical scores were changed; all raw failures remain.'})
    patch=[];changes=[]
    olddir=Path('scratch/search_v2c_c5d_repair_v2/candidate_search');newdir=Path('scratch/search_v2c_c5e/candidate_search_v2')
    for p in sorted(newdir.glob('*.py')):
        parent=olddir/p.name
        patch.extend(difflib.unified_diff(parent.read_text(encoding='utf8').splitlines(True),p.read_text(encoding='utf8').splitlines(True),fromfile=str(parent),tofile=str(p)))
        changes.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'parent':str(parent),'parent_sha256':hashlib.sha256(parent.read_bytes()).hexdigest()})
    with (R/(P+'implementation.patch')).open('x',encoding='utf8') as f:f.writelines(patch)
    write('implementation_changes.json',{'candidate_id':'search-v2c-c5e-disabled-candidate-2','files':changes,'production_routing_changed':False,
          'changes':['Mandatory/advisory ownership and unresolved relationship ledger with original offsets','Bounded seven missing grammar repair families and source notices','Missing negative-group scope versus unnamed required operand typing','Quoted canonical correction bridge to existing native issued choices','Whole-word online/physical/digital exclusion ownership','Consume format wrappers and avoid synthetic advisory semantic topics'],
          'scorer_changes':'New independent orchestration only; unchanged norm/BOTH and author/reviewer field masks. Original C5C scorer used verbatim for A.',
          'preserved_candidate1':'scratch/search_v2c_c5e/candidate_search','active_C4_policy_changed':False})
if __name__=='__main__':main()
