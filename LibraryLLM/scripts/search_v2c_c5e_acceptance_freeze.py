"""Final pre-inference acceptance freeze. No parser calls or result inspection."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,xml.etree.ElementTree as ET
R=Path('reports');P='search_v2c_c5e_';C=Path('scratch/search_v2c_c5e/candidate_search_v2')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf8') as f:json.dump(v,f,sort_keys=True,indent=2,ensure_ascii=False)
def xml(p,expected):
    s=next(ET.parse(p).getroot().iter('testsuite'))
    assert int(s.attrib['tests'])==expected and int(s.attrib['failures'])==int(s.attrib['errors'])==0
def main():
    pre=load(R/(P+'preflight.json'));assert all(sha(p)==h for p,h in pre['protected_files'].items())
    assert load(R/(P+'v3_structural_isolation.json'))['status']=='PASS'
    xml(R/(P+'v2_regression.xml'),1401);xml(R/(P+'v2_native_final.xml'),310)
    db=load(R/(P+'c5a_v2_native_final/search_v2c_c5e_disposable_database.json'))
    assert db['explicitly_disposable'] and db['cleanup_complete'] and not db['production_database_selected']
    pop=R/(P+'reviewed_population_v3.jsonl')
    rows=[json.loads(s) for s in pop.read_text(encoding='utf8').splitlines()]
    author=[json.loads(s) for s in (R/(P+'independent_authored_v3.jsonl')).read_text(encoding='utf8').splitlines()]
    assert len(rows)==90 and {r['case_id'] for r in rows}=={r['case_id'] for r in author}
    old={r['case_id']:r for r in author}
    keys=['case_id','query_text','scope_type','workspace_type','search_mode']
    assert all(all(r[k]==old[r['case_id']][k] for k in keys) for r in rows)
    review=load(R/(P+'independent_review_v3.json'))
    independent={r['case_id']:r for r in review['cases']}
    assert all(r['expected_typed_decision']==independent[r['case_id']]['expected_typed_decision'] and r['expected_executable']==independent[r['case_id']]['expected_executable'] for r in rows)
    assert len({(r['scope_type'],r['decision_stratum']) for r in rows})==30
    assert all(sum(r['scope_type']==s and r['decision_stratum']==t for r in rows)==3 for s,t in {(r['scope_type'],r['decision_stratum']) for r in rows})
    inputs=R/(P+'independent_parser_inputs.jsonl')
    with inputs.open('x',encoding='utf8') as f:
        for r in rows:f.write(json.dumps({k:r[k] for k in keys},sort_keys=True,ensure_ascii=False)+'\n')
    code={str(p):sha(p) for p in C.glob('*.py')}
    code.update({str(p):sha(p) for p in [Path('scripts/search_v2c_c5e_independent_score.py'),Path('scripts/search_v2c_c5e_v2_predict.py'),Path('scripts/search_v2c_c5c_score.py'),Path('scripts/search_v2c_c_evaluate.py'),Path('scripts/search_v2c_c4_evaluate.py')]})
    frozen=dict(code)
    artifacts=['acceptance_design.json','reviewed_population_v3.jsonl','independent_authored_v3.jsonl','author_provenance_v3.json',
               'independent_review_v3.json','review_reconciliation_v3.json','v3_structural_isolation.json','v3_sealed_structural_isolation.json',
               'v3_sealed_access_audit.json','independent_parser_inputs.jsonl','v2_regression.xml','v2_native_final.xml',
               'requirement_ledger.md','operational_limits.md']
    frozen.update({str(R/(P+n)):sha(R/(P+n)) for n in artifacts})
    frozen.update({str(p):sha(p) for p in Path('scratch/search_v2c_c5e/native_v2').glob('*.py')})
    frozen.update({str(p):sha(p) for p in Path('scratch/search_v2c_c5e/regression_v2').glob('*.py')})
    frozen[str(Path(__file__).relative_to(Path.cwd()))]=sha(__file__)
    write('candidate_freeze.json',{'candidate_id':'search-v2c-c5e-disabled-candidate-2','at_utc':datetime.now(timezone.utc).isoformat(),
         'files':frozen,'primary_acceptance_not_started':True,'acceptance_primary_attempts':1,'reviewed_contexts':90,
         'shared_semantic_patterns':len({r['shared_semantic_pattern_id'] for r in rows}),'independent_topologies':18,
         'regression_assertions':1401,'native_scenarios':310,'production_activation':False,'candidate1_preserved':True,
         'implementation_source_frozen_before_review_results':sha(R/(P+'v2_development_candidate_freeze.json')),
         'scoring_contract':'Existing norm, formats-only BOTH equivalence and independently reviewed explicit masks; no whole-word positive/exact_text equivalence.',
         'independence_limits':'AI author and AI independent reviewer; human0. Reviewer inherited only its previous blind review task, no candidate results. Root saw draft first C1 query and author v3 first two templates in provenance output; candidate2 code already frozen in development freeze before v3 template exposure. No resulting implementation changes.'})
    cap=R/'search_v2c_c5a_capability_matrix.json'
    write('independent_parser_configuration.json',{'candidate_id':'search-v2c-c5e-disabled-candidate-2','input_sha256':sha(inputs),'caps_path':str(cap),'caps_sha256':sha(cap),
          'prediction_calls_planned':90,'parser_source_hashes':{str(p):sha(p) for p in C.glob('*.py')},'frozen_before_prediction_scripts':code,
          'gold_population_path':str(pop),'gold_population_sha256':sha(pop),'candidate_freeze_sha256':sha(R/(P+'candidate_freeze.json')),
          'gold_decoded_by_predictor':False,'gold_file_reads_by_predictor':0,'activation':False,'model_calls_planned':0,'primary_attempts':1})
    print(json.dumps({'frozen_candidate':'search-v2c-c5e-disabled-candidate-2','contexts':90,'scope_stratum_cells':30,'files':len(frozen),'candidate_freeze_sha256':sha(R/(P+'candidate_freeze.json'))}))
if __name__=='__main__':main()
