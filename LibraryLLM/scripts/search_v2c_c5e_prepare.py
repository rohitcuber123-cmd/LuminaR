"""C5E freeze verification and output-blind validation design. No parser calls."""
from pathlib import Path
from datetime import datetime,timezone
from itertools import combinations
import hashlib,json,ast
R=Path('reports');P='search_v2c_c5e_';C=Path('scratch/search_v2c_c5e/candidate_search')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def rows(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf8').splitlines() if s.strip()]
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf8') as f:f.write(json.dumps(v,sort_keys=True,indent=2,ensure_ascii=False)+'\n')
def main():
    assert not list(R.glob(P+'*')) and not C.exists()
    parent=load(R/'search_v2c_c5d_repair_freeze_manifest.json');pre=load(R/'search_v2c_c5d_repair_v2_preflight.json')
    assert all(sha(p)==h for p,h in parent['files'].items())
    assert all(sha(p)==h for p,h in pre['protected_files'].items())
    protected=dict(pre['protected_files']);protected.update(parent['files'])
    protected.update({str(p):sha(p) for p in R.glob('search_v2c_c*') if p.is_file() and not p.name.startswith(P)})
    protected.update({str(p):sha(p) for p in Path('scripts').glob('search_v2c_c*.py') if not p.name.startswith(P)})
    C.mkdir(parents=True)
    copies={}
    for p in Path('scratch/search_v2c_c5d_repair_v2/candidate_search').glob('*.py'):
        target=C/p.name;target.write_text(p.read_text(encoding='utf8').replace('scratch.search_v2c_c5d_repair_v2.candidate_search','scratch.search_v2c_c5e.candidate_search').replace('search-v2c-c5d-disabled-candidate-2','search-v2c-c5e-disabled-candidate-1'),encoding='utf8')
        copies[str(target)]={'parent':str(p),'parent_sha256':sha(p),'initial_sha256':sha(target)}
    write('preflight.json',{'status':'PASS','at_utc':datetime.now(timezone.utc).isoformat(),'protected_files':protected,'copies':copies,
        'C5D_master_freeze_sha256':sha(R/'search_v2c_c5d_repair_freeze_manifest.json'),'C5D_v2_freeze_sha256':sha(R/'search_v2c_c5d_repair_v2_candidate_freeze.json'),
        'C5C_predictions_sha256':sha(R/'search_v2c_c5c_predictions.jsonl'),'gold_sha256':sha(R/'search_v2c_c5b_expected_labels.jsonl'),
        'authorization_sha256':sha(r'C:\Users\balak\.codex\attachments\a2736db7-86d9-45b1-b2e5-9485785ba4f6\Pasted text.txt'),
        'production_activated':False,'production_parser_calls':0,'sealed_content_read':False})
    from scripts.search_v2c_c2_benchmark import structure
    exposed=rows(R/'search_v2c_c2_v2_development.jsonl')+rows(R/'search_v2c_c5b_calibration_cases.jsonl')
    for directory in ['scratch/search_v2c_c5d_repair','scratch/search_v2c_c5d_repair_v2']:
        for p in Path(directory).rglob('test*.py'):
            for node in ast.walk(ast.parse(p.read_text(encoding='utf8'))):
                if isinstance(node,ast.Constant) and isinstance(node.value,str) and len(node.value)>7:
                    exposed.append({'query_text':node.value,'search_mode':'SMART'})
    used={structure(r) for r in exposed};features=['rating','author','title','negative','include','format','preference','sort']
    ordered=['rating','year','author','title','negative','include','format','availability','metadata','preference','sort'];available=[]
    for n in range(4,9):
        for combo in combinations(features,n):
            topology='SMART:'+','.join(f for f in ordered if f in combo)
            if topology not in used:available.append(topology)
    caps=load(R/'search_v2c_c5a_capability_matrix.json')['scopes'];brief_caps={}
    for scope,value in caps.items():
        allowed=[s for s in ['History','Fiction','Physics','Ecology','Astronomy','Community archives','Quantum computing','Climate change mitigation','Computer science','Mystery','Neural Networks','Wizards','Detective Fiction'] if s in value['subjects']]
        brief_caps[scope]={'workspace_type':value['workspace_type'],'capabilities':value['capabilities'],'canonical_subjects':allowed,'profile_reference':'search_v2c_c5a_capability_matrix.json#'+scope}
    design={'version':'C5E-independent-acceptance-design-v1','specified_before_candidate_acceptance_results':True,'planned_contexts':90,'contexts_per_cell':3,
       'scopes':list(caps),'strata':['CLEAR_EXECUTABLE','SAFE_UNCERTAIN_EXECUTABLE','AMBIGUOUS','INCOMPLETE','UNSUPPORTED','CONTRADICTORY'],
       'units':'Logical SMART parser contexts; three genuinely different author-composed semantic families per stratum, contextualized across five scopes. Report shared groups honestly.',
       'primary_attempts':1,'independent_review_required':True,'candidate_freeze_required':True,'gold_not_from_parser':True,
       'isolation':'Established C2 canonical identity/operation topology and established sealed audit interface; additionally reject all exposed C5C/C5D/focused/native topology or canonical overlaps. No heldout text/labels/IDs exposed.',
       'gates':{'independent_false_execution':0,'native_authorization_privacy_violations':0,'known_unsafe_development_case_resolved':True,'clear_executable_critical_regressions':0,
                'no_blanket_safe_uncertain_refusal':True,'native_notice_correction_contracts':True,'historical_hash_changes':0,'live_application_side_effects':0},
       'typed_accuracy_gate':'Descriptive, all errors retained; never exclude difficult cases after predictions. Zero safety failures is finite-sample only.',
       'eligibility':'Every independently reviewed definite decision/execution case; no generated derivatives, no unresolved required gold, native assertions kept separate.',
       'inference':'Gold-blind isolated process, predictions committed before scoring; no candidate revision/retest on this acceptance set.',
       'contract':'Existing six typed kinds, execution bool, unchanged C5C norm/BOTH and per-field applicability rules. Structured advisory/actor metrics N/A where no oracle exists.',
       'failure_exit':'Any observed critical safety error blocks readiness; incomplete independent review/isolation/native qualification => PARTIAL. Integrity/privacy/prohibited action => FAIL.'}
    write('acceptance_design.json',design)
    write('blind_author_brief.json',{'task':'Independently author normative acceptance queries and gold, with no candidate/parser/output/performance access.',
       'design':design,'scope_contracts':brief_caps,'allowed_fresh_operation_topologies':available,
       'review_vocabulary':['EXECUTABLE','EXECUTABLE_WITH_NOTICE','AMBIGUOUS','INCOMPLETE','UNSUPPORTED','CONTRADICTORY'],
       'normative_rules':['Mandatory supported operands must be uniquely resolved before execution. Advisory preferences do not become hard filters.',
          'Safe unique canonical/spelling repair is executable with a source-backed notice; no numeric confidence target.',
          'Unresolved required association or hard/advisory ownership is AMBIGUOUS, a blank required value is INCOMPLETE, unenforceable strict fields/operations are UNSUPPORTED, incompatible resolved requirements are CONTRADICTORY.',
          'Canonical negative categories differ from broad whole-word text exclusion. Quoted entities remain literal except their explicit field owner.',
          'Use actual caps. GLOBAL cannot enforce year/language/availability/physical formats. Staff means catalogue search, not inventory commands.',
          'No unsupported Boolean operation is licensed by ordinary keywords. Do not invent catalogue facts or resolve an unknown bibliography association.',
          'Every extra topology feature must represent a meaningful requested operation; no inert padding. Avoid merely renaming C5C sentences.'],
       'required_row_keys':['case_id','query_text','scope_type','workspace_type','search_mode','decision_stratum','family_id','structural_component_id','expected_typed_decision','expected_executable','expected_hard_constraints','metric_applicability','semantic_justification'],
       'output':'reports/search_v2c_c5e_independent_authored.jsonl','provenance_output':'reports/search_v2c_c5e_author_provenance.json',
       'allowed_reads_only':['reports/search_v2c_c5e_blind_author_brief.json'],'forbidden_reads':'All production/candidate source, prior queries/gold, predictions, metrics, failure reports, other chat histories and sealed files.',
       'warning':'Definitive labels are independent semantic judgments, not a requirement to make the candidate pass. If uncertain, flag for fresh reviewer; never fabricate.'})
    print(json.dumps({'preflight':'PASS','protected_entries':len(protected),'fresh_topologies_for_author':len(available),'acceptance_design_frozen_before_results':True}))
if __name__=='__main__':main()
