"""Final all-input freeze after source-only review and unchanged sealed metadata audit."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import json,hashlib

R=Path('reports');P='search_combined8_'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(n):return json.loads((R/(P+n+'.json')).read_text(encoding='utf-8'))
def save(n,d):
    with (R/(P+n+'.json')).open('x',encoding='utf-8') as f:json.dump(d,f,indent=2)


def main():
    source=load('source_freeze');assert all(sha(p)==h for p,h in source['files'].items())
    contract=load('acceptance_contract');audit=load('reviewed_structural_isolation')
    gold=[json.loads(s) for s in (R/(P+'reviewed_population_r1.jsonl')).read_text(encoding='utf-8').splitlines()]
    c=contract['population'];cells=Counter((g['scope_type'],g['expected_typed_decision']) for g in gold)
    eligible=(audit['structural_pass'] and c['eligible_min']<=len(gold)<=c['eligible_max'] and audit['distinct_actual_topologies']>=c['actual_operation_topologies_min']
              and len({g['family_id'] for g in gold})>=c['linguistic_families_min'] and len({g['scope_type'] for g in gold})==5 and len({g['expected_typed_decision'] for g in gold})==6)
    save('population_eligibility',dict(eligible=eligible,contexts=len(gold),linguistic_families=len({g['family_id'] for g in gold}),actual_topologies=audit['distinct_actual_topologies'],
                                      scope_stratum_cells=[dict(scope=s,decision=k,count=v) for (s,k),v in sorted(cells.items())],structural_pass=audit['structural_pass'],criteria=contract['population'],
                                      audit_sha256=sha(R/(P+'reviewed_structural_isolation.json')),candidate_source_unchanged=True))
    if not eligible:
        print(json.dumps(dict(eligible=False,reason='Population isolation/design gates failed; no primary capture authorized')));return
    inputs=R/(P+'independent_parser_inputs.jsonl')
    with inputs.open('x',encoding='utf-8') as f:
        for g in gold:
            value={k:g[k] for k in ['case_id','query_text','scope_type','workspace_type','search_mode']}
            if g.get('completion_input'):value['completion_input']=g['completion_input']
            f.write(json.dumps(value,ensure_ascii=False,sort_keys=True)+'\n')
    script_names=['search_combined8_independent_predict.py','search_combined8_independent_score.py','search_combined8_score_adapter.py','search_combined8_acceptance_prepare.py','search_combined8_acceptance_freeze.py','search_combined8_apply_adjudication.py','search_combined8_population_audit.py','search_v2c_c5er_evaluation_adapter_v2.py','search_v2c_c5c_score.py','search_v2c_c_evaluate.py','search_v2c_c4_evaluate.py','search_v2c_c5a_sealed_audit.py','search_v2c_c2_benchmark.py']
    scripts={str(Path('scripts')/n):sha(Path('scripts')/n) for n in script_names}
    files=dict(source['files']);files.update(scripts)
    names=['source_freeze.json','architecture_selection.json','semantic_contract.json','acceptance_contract.json','authored.jsonl','author_provenance.json','author_brief.json','blind_reviewer_packet.json','reviewer_id_map.json','independent_review.jsonl','reviewer_provenance.json','review_reconciliation.json','reviewed_population.jsonl','reviewed_structural_isolation.json','reviewed_sealed_structural_isolation.json','reviewed_sealed_access_audit.json','population_eligibility.json','independent_parser_inputs.jsonl','broad4_tests.xml','scorer_tests2.xml']
    for n in names:files[str(R/(P+n))]=sha(R/(P+n))
    for n in ['author_reconciliation.json','blind_source_adjudication.json','source_dispute_packet.json','review_reconciliation_final.json','reviewed_population_r1.jsonl']:
        files[str(R/(P+n))]=sha(R/(P+n))
    caps=R/'search_v2c_c5a_capability_matrix.json'
    save('independent_parser_configuration',dict(candidate_id=source['candidate_id'],prediction_calls_planned=len(gold),input_sha256=sha(inputs),caps_path=str(caps),caps_sha256=sha(caps),
                                                parser_source_hashes=source['files'],frozen_before_prediction_scripts=scripts,
                                                gold_reads_by_predictor=0,primary_attempts_allowed=1))
    files[str(R/(P+'independent_parser_configuration.json'))]=sha(R/(P+'independent_parser_configuration.json'))
    save('acceptance_freeze',dict(candidate_id=source['candidate_id'],at_utc=datetime.now(timezone.utc).isoformat(),files=files,primary_attempts_allowed=1,primary_attempts_started=0,
                                  population=len(gold),linguistic_families=len({g['family_id'] for g in gold}),actual_topologies=audit['distinct_actual_topologies'],
                                  human_reviewers=0,separate_AI_author_and_reviewer=True,source_frozen_before_authoring=True,heldout_evaluations=0,Mongo_writes=0,production_activation=False))
    print(json.dumps(dict(eligible=True,frozen_files=len(files),contexts=len(gold),primary_attempts=0)))

if __name__=='__main__':main()
