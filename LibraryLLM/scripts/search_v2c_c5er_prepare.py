"""C5E-R preflight, disabled namespace and output-blind acceptance design."""
from pathlib import Path
from datetime import datetime,timezone
from itertools import combinations
import hashlib,json,ast
R=Path('reports');P='search_v2c_c5er_';C=Path('scratch/search_v2c_c5er/candidate_search')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def rows(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf8').splitlines() if s.strip()]
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf8') as f:json.dump(v,f,indent=2,sort_keys=True,ensure_ascii=False)
def main():
    assert not C.exists()
    pre=load(R/'search_v2c_c5e_preflight.json');master=load(R/'search_v2c_c5e_freeze_manifest.json')
    assert len(pre['protected_files'])==1868 and len(master['files'])==170
    assert all(sha(p)==h for p,h in pre['protected_files'].items()) and all(sha(p)==h for p,h in master['files'].items())
    assert sha(R/'search_v2c_c5e_candidate_freeze.json')=='59b216a38dded724747f162a10933bb14e15e99669f30d3a99711624cdf14e76'
    protected={**pre['protected_files'],**master['files']}
    for n in ['freeze_manifest.json','freeze_verification.json']:protected[str(R/('search_v2c_c5e_'+n))]=sha(R/('search_v2c_c5e_'+n))
    C.mkdir(parents=True)
    for p in Path('scratch/search_v2c_c5e/candidate_search_v2').glob('*.py'):
        (C/p.name).write_text(p.read_text(encoding='utf8').replace('scratch.search_v2c_c5e.candidate_search_v2','scratch.search_v2c_c5er.candidate_search').replace('search-v2c-c5e-disabled-candidate-2','search-v2c-c5er-disabled-candidate-1'),encoding='utf8')
    write('preflight.json',{'status':'PASS','at_utc':datetime.now(timezone.utc).isoformat(),'protected_files':protected,'original_protected_count':1868,'production_protected_count':462,
          'C5E_frozen_files_verified':170,'parent_candidate':'search-v2c-c5e-disabled-candidate-2','parent_manifest_sha256':sha(R/'search_v2c_c5e_freeze_manifest.json'),
          'user_clarification':'All Mongo writes prohibited, including disposable databases; native qualification limited.','mongo_calls_authorized':0,'resident_endpoint_calls_authorized':0,
          'authorization_sha256':sha(r'C:\Users\balak\.codex\attachments\49cbddaf-a393-4f18-b687-1e2da9ff8fa3\Pasted text.txt')})
    from scripts.search_v2c_c2_benchmark import structure
    exposed=rows(R/'search_v2c_c2_v2_development.jsonl')+rows(R/'search_v2c_c5b_calibration_cases.jsonl')
    exposed+=rows(R/'search_v2c_c5e_independent_authored.jsonl')+rows(R/'search_v2c_c5e_independent_authored_v3.jsonl')
    for directory in ['scratch/search_v2c_c5d_repair','scratch/search_v2c_c5d_repair_v2','scratch/search_v2c_c5e']:
        for p in Path(directory).rglob('test*.py'):
            for n in ast.walk(ast.parse(p.read_text(encoding='utf8'))):
                if isinstance(n,ast.Constant) and isinstance(n.value,str) and len(n.value)>7:exposed.append({'query_text':n.value,'search_mode':'SMART'})
    used={structure(r) for r in exposed};features=['rating','year','author','title','negative','include','format','availability','metadata','preference','sort']
    fresh=['SMART:'+','.join(c) for n in range(4,10) for c in combinations(features,n) if 'SMART:'+','.join(c) not in used]
    design={'version':'C5ER-preregistered-acceptance-v1','at_utc':datetime.now(timezone.utc).isoformat(),'contexts':150,'contexts_per_cell':5,'scope_stratum_cells':30,
        'shared_patterns_target':30,'primary_attempts':1,'independent_authors_and_reviewers':True,'candidate_gold_blind':True,
        'quality_targets':{'typed_accuracy_min':.95,'execution_accuracy_min':.98,'false_execution_max':0,'missed_clear_execution_max':1,'missed_safe_uncertain_execution_max':1,
           'critical_mandatory_constraint_loss_or_invention_max':0,'native_privacy_authorization_violations_max':0,'production_or_Mongo_mutations_max':0},
        'scope':'SMART logical parser contexts; EXACT and workflow compatibility separately qualified. No confidence-probability claims.',
        'isolation':'Unchanged established C2 identity/topology plus sealed structural auditor; include all C5E drafts/acceptance and focused exposed tests. Scope repeats are contextualizations, not independent families.',
        'gold':'Normative author and fresh independent reviewer receive no candidate source/predictions/performance/quality percentages; resolve disagreements before prediction freeze.',
        'metric_contract':'Existing scalar norm and formats-only BOTH. Per-field masks APPLICABLE/APPLICABLE_ABSENCE/PARTIALLY_APPLICABLE/UNRESOLVED/N/A. Unknown is not absent. Structured semantic/advisory objects have no invented string adapter.',
        'failure_exit':'Any critical safety error or incomplete fresh review/isolation/native qualification => PARTIAL; integrity/privacy/prohibited operation => FAIL. No candidate tuning or recapture after acceptance.',
        'native_limit':'User explicitly prohibits all Mongo writes; retain historical real310 native pass, new offline integration/independence evidence is bounded and cannot claim full fresh Mongo-native qualification.'}
    write('acceptance_design.json',design)
    caps=load(R/'search_v2c_c5a_capability_matrix.json')['scopes'];contracts={}
    for scope,v in caps.items():
        contracts[scope]={'workspace_type':v['workspace_type'],'capabilities':v['capabilities'],'canonical_subjects':[s for s in ['History','Fiction','Physics','Ecology','Astronomy','Community archives','Quantum computing','Climate change mitigation','Computer science','Mystery','Neural Networks','Wizards','Detective Fiction'] if s in v['subjects']]}
    write('blind_author_brief.json',{'task':'Author 150 fresh normative acceptance contexts: five distinct semantic families per six strata, contextualized across five scopes. Do not target parser success.',
       'scopes':contracts,'strata':['CLEAR_EXECUTABLE','SAFE_UNCERTAIN_EXECUTABLE','AMBIGUOUS','INCOMPLETE','UNSUPPORTED','CONTRADICTORY'],
       'allowed_fresh_topologies':fresh,'structure_function_source':{'regex_order':features,'metadata':'Exact pure established C2 structure function may be read ONLY from supplied structure_source.txt; no module execution.'},
       'normative_rules':['Supported mandatory operands must retain meaning; advisory conditions are not hard filters. Background narration is not a requirement.',
         'Unresolved mandatory alternatives/association => AMBIGUOUS; explicitly missing required value => INCOMPLETE; unenforceable strict aggregate/relational/metadata operation => UNSUPPORTED; incompatible resolved predicates => CONTRADICTORY.',
         'Clear supported multi-filter intersections execute. Safe unique field/canonical spelling repairs execute with source-backed notice. Unknown bibliography identities must not be invented.',
         'Author/title quoted field strings are literal contains operands in the native contract, not bibliographic identity proofs. Unowned quoted text stays literal.',
         'Canonical category exclusions differ from whole-word searchable-text exclusions; do not manufacture Boolean/proximity/aggregate capabilities. Global caps do not support year/language/availability/physical access.',
         'Every topology feature must represent meaningful requested semantics, no inert padding. Pure structure includes quoted words. Verify actual topology against supplied allowlist. Use multiple topologies, five genuinely different families per stratum; scope substitutions are not extra structural families.'],
       'schema':{'keys':['case_id','query_text','scope_type','workspace_type','search_mode','decision_stratum','family_id','structural_component_id','shared_semantic_pattern_id','expected_typed_decision','expected_executable','expected_hard_constraints','metric_applicability','semantic_justification'],
         'scalar_fields':['subjects','exclude_subjects','exclude_terms','author_text','title_text','exact_text','rating_min','rating_max','rating_min_exclusive','rating_max_exclusive','year_min','year_max','year_min_exclusive','year_max_exclusive','formats','exclusive_formats','excluded_formats','availability','language'],
         'masks':'unprefixed scalar field names; mask objects with status and reason. Known absent list=[],scalar=None,bool=False; unknown values UNRESOLVED. Preserve partial resolved common lists explicitly.',
         'other_fields':'expected_sort enum RELEVANCE/RATING/NEWEST/TITLE; expected_semantic_remainder string only if a definite literal topic is asserted, otherwise null with N/A mask; expected_soft_preferences structured objects separately, no string equivalence; unadapted mandatory assertions preserved separately.'},
       'allowed_reads_only':['reports/search_v2c_c5er_blind_author_brief.json','reports/search_v2c_c5er_structure_source.txt'],
       'forbidden':'All candidate/production source, prior cases/gold/reviews/results, hidden/heldout data, model APIs, databases or native calls.',
       'output':'reports/search_v2c_c5er_authored.jsonl','provenance_output':'reports/search_v2c_c5er_author_provenance.json'})
    tree=ast.parse(Path('scripts/search_v2c_c2_benchmark.py').read_text(encoding='utf8'))
    source=Path('scripts/search_v2c_c2_benchmark.py').read_text(encoding='utf8')
    with (R/(P+'structure_source.txt')).open('x',encoding='utf8') as f:
        for node in tree.body:
            if isinstance(node,ast.FunctionDef) and node.name in ['normalized','mode','structure']:f.write(ast.get_source_segment(source,node)+'\n\n')
    print(json.dumps({'protected_verified':len(protected),'fresh_topologies':len(fresh),'new_acceptance_target':150,'Mongo_writes_prohibited':True}))
if __name__=='__main__':main()
