"""Verify the real baseline and document diagnosis before architecture changes."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from itertools import combinations
from dataclasses import asdict
import json,hashlib,ast,subprocess
R=Path('reports');P='search_v2c_smarteng_'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def rows(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf8').splitlines() if s.strip()]
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf8') as f:json.dump(v,f,indent=2,ensure_ascii=False,sort_keys=True)
def main():
    pre=load(R/'search_v2c_c5er_preflight.json');freeze=load(R/'search_v2c_c5er_candidate_freeze.json')
    assert len(pre['protected_files'])==2040
    assert all(sha(k)==v for k,v in pre['protected_files'].items())
    assert all(sha(k)==v for k,v in freeze['files'].items())
    protected={**pre['protected_files'],**freeze['files']}
    for d in ['reports','scripts','scratch/search_v2c_c5er']:
        for p in Path(d).rglob('*'):
            if p.is_file() and (p.name.startswith('search_v2c_c5er_') or d.startswith('scratch') and p.suffix=='.py'):
                protected[str(p)]=sha(p)
    write('preflight.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS','protected_files':protected,
        'C5ER_parent_candidate':freeze['candidate_id'],'C5ER_candidate_freeze_sha256':sha(R/'search_v2c_c5er_candidate_freeze.json'),
        'C5ER_predictions_sha256':sha(R/'search_v2c_c5er_independent_predictions.jsonl'),'C5ER_gold_sha256':sha(R/'search_v2c_c5er_reviewed_population.jsonl'),
        'original_production_entries':462,'historical_C5ER_preflight_entries_verified':2040,
        'git_head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'git_status':subprocess.check_output(['git','status','--porcelain=v1'],text=True),
        'authorization_sha256':sha(r'C:\Users\balak\.codex\attachments\9d7b01c1-4c0a-4645-a5d9-cb0a55dcd706\Pasted text.txt'),
        'all_Mongo_writes_prohibited_by_user_clarification':True,'production_routing_changed':False})
    gold={x['case_id']:x for x in rows(R/'search_v2c_c5er_reviewed_population.jsonl')}
    pred={x['case_id']:x for x in rows(R/'search_v2c_c5er_independent_predictions.jsonl')}
    scored=rows(R/'search_v2c_c5er_independent_scored_observations.jsonl')
    from scratch.search_v2c_c5er.candidate_search_v4.semantic_safety import prepare
    from scratch.search_v2c_c5er.candidate_search_v4.query_constraints import recognize
    from scratch.search_v2c_c5er.candidate_search_v4.query_calibration import assess
    caps=load(R/'search_v2c_c5a_capability_matrix.json')['scopes'];traces=[]
    for r in scored:
        g=gold[r['case_id']];p=pred[r['case_id']];prepared,repairs,offsets=prepare(g['query_text'])
        source=recognize(prepared,caps[g['scope_type']]['subjects'])
        traces.append({'case_id':r['case_id'],'family':g.get('shared_semantic_pattern_id'),'scope':g['scope_type'],'query':g['query_text'],
            'intended_operation':g['expected_typed_decision'],'mandatory_scalars':g['expected_hard_constraints'],
            'advisory':g.get('expected_soft_preferences'),'prepared_query':prepared,'grammar_edits':repairs,
            'recognition_candidates':[asdict(c) for c in source.items],'actual_operands':{k:p['actual_plan'].get(k) for k in g['expected_hard_constraints']},
            'semantic_text':p['actual_plan'].get('semantic_text'),'ledger':p['actual_plan']['decision'].get('requirements'),
            'actual_decision':p['typed_decision'],'execution':p['executable'],'C4_assessment':p.get('assessment'),'mismatches':r['mismatches']})
    with (R/(P+'baseline_traces.jsonl')).open('x',encoding='utf8') as f:
        for r in traces:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    causes=[
        {'cause':'Advisory modality assigned after extraction, with a four-adjective vocabulary','first_incorrect_stage':'requirement_ledger.own leaves preferred year/language/availability unowned; query_repair._compose installs hard predicates','source':'scratch/search_v2c_c5er/candidate_search_v4/requirement_ledger.py:own; query_repair.py:_compose; query_confidence.py:validate','evidence':'A01/A02 global change AMBIGUOUS to scope UNSUPPORTED while tenant variants execute; S04 advisory language blocks GLOBAL.'},
        {'cause':'Unquoted explicit facet operands are treated as broad prose','first_incorrect_stage':'subject_clauses skips subject qualifier but not the category/classification owner; fuzzy repair is limited to quoted owner path','source':'scratch/search_v2c_c5er/candidate_search_v4/query_constraints.py:subject_clauses,owned_literals','evidence':'C02/C04/C05 and S01-S05 canonical category/subject requests become unresolved; no valid correction is issued.'},
        {'cause':'Field recognition and missing-operand guard compete over the same sort phrase','first_incorrect_stage':'unsupported_and_sorts recognizes sort by, not equivalent sort on; dangling rating in highest rating enters missing_pattern','source':'scratch/search_v2c_c5er/candidate_search_v4/query_constraints.py:unsupported_and_sorts; query_repair.py:_compose','evidence':'C01 is INCOMPLETE despite its resolved rating and explicit sort request.'},
        {'cause':'Relationships are word-triggered rather than preserved as operands and operators','first_incorrect_stage':'required relationships do not cover deferred either/or association; scalar recognizers retain one value or strongest bound','source':'scratch/search_v2c_c5er/candidate_search_v4/requirement_ledger.py:own; semantic_safety.py:finish','evidence':'Eight tenant A01/A02 unsafe recommendations; all25 ambiguity labels missed.'},
        {'cause':'Decision composition is spread across parser, ledger and capability validator','first_incorrect_stage':'capability checks overwrite unresolved/incomplete typing caused by unrelated advisory metadata','source':'scratch/search_v2c_c5er/candidate_search_v4/query_confidence.py:validate; semantic_safety.py:finish','evidence':'Global missing/ambiguous requests become scope UNSUPPORTED; X05 contradiction is hidden by preferred language.'},
        {'cause':'Negative domains and postfix canonical ownership are incomplete','first_incorrect_stage':'text exclusion recognizer accepts a narrower surface template; classification suffix is retained as broad text','source':'scratch/search_v2c_c5er/candidate_search_v4/query_constraints.py:owned_literals,subject_clauses','evidence':'C03 executes with wrong negative filters; searchable-text whole word exclusions are lost.'}]
    write('architecture_diagnosis.json',{'entire_population_traced':150,'baseline_typed':57,'baseline_execution':97,'baseline_false':8,'baseline_missed':45,'confirmed_causes':causes,
        'hypotheses':'No claim that finite deterministic grammar covers unrestricted language; source coverage and retrieval meaning require independent tests.',
        'trace_artifact':str(R/(P+'baseline_traces.jsonl')),'production_route':'search.query_plan.parse_query -> search.query_repair.compose -> typed query_confidence and C4 query_calibration; native search.query_execution and scope_authorization remain unchanged.'})
    decision={'selected':'B: compositional ownership/extraction/decision pipeline with a lightweight legacy compatibility bridge',
        'strategy':'Reuse frozen V4 Source/numeric recognizers, QueryPlan dataclass, scalar predicate, explicit controls, C4 assess and established native adapters. Add explicit IR, early modality ownership, common field grammar and a single proof-based decision composition. Do not copy all frozen modules.',
        'options':{'A':'Small patches retain competing decision paths and narrow clause tests; insufficient alone.',
            'B':'Chosen: separates modality, structured fields, relationships, semantic residual and decision with inspectable source coverage.',
            'C':'Used only for supported soft topic/advice; unsupported mandatory semantics cannot be delegated to vector ranking.',
            'D':'No model hot path: new inference/resource/validation dependencies are not justified by these extraction defects.'},
        'limits':'No native authorization changes, no broad new Mongo operations, no production activation. Native Mongo-backed qualification remains unavailable under all-write prohibition.',
        'metrics_contract':'Reuse reviewed scalar adapter. Exact source/unknown/absence distinctions, no structured semantic/string equivalence.'}
    write('architecture_decision.json',decision)
    design={'version':'SMARTENG-independent-v1','contexts':150,'30_cells':5,'shared_families_target':30,'primary_attempts':1,'pre_registered_before_predictions':True,
        'gates':{'typed_accuracy_min':.95,'execution_accuracy_min':.99,'false_execution_max':0,'missed_execution_rate_max':.05,'invalid_outputs_max':0,
            'critical_executed_mandatory_operand_loss_or_invention_max':0,'privacy_authorization_violations_max':0,'production_mutations_max':0},
        'native_qualification':'Fresh full Mongo/API durability qualification unavailable; offline read-only exact native-function fixtures and historical real310 scenarios kept separately. No full PASS without missing operational qualification.',
        'isolation':'Established C2 canonical identity and operation topology plus sealed audit. Exclude all exposed C5C/C5D/C5E/C5ER populations and focused tests. No heldout scoring/content disclosure.',
        'scoring':'Frozen scalar norm, formats-only BOTH, reviewed field masks. Topic strings measured only with a genuine scalar oracle; advisory object semantics N/A.',
        'failure':'Preserve results; do not retune or recapture the same independent cohort after results. Any safety failure blocks readiness.'}
    write('acceptance_design.json',design)
    from scripts.search_v2c_c2_benchmark import structure
    exposed=rows(R/'search_v2c_c2_v2_development.jsonl')+rows(R/'search_v2c_c5b_calibration_cases.jsonl')
    for n in ['search_v2c_c5e_independent_authored.jsonl','search_v2c_c5e_independent_authored_v3.jsonl','search_v2c_c5er_authored.jsonl','search_v2c_c5er_authored_v2.jsonl']:exposed+=rows(R/n)
    for d in ['scratch/search_v2c_c5e','scratch/search_v2c_c5er','scratch/search_v2c_c5d_repair_v2']:
        for p in Path(d).rglob('test*.py'):
            for n in ast.walk(ast.parse(p.read_text(encoding='utf8'))):
                if isinstance(n,ast.Constant) and isinstance(n.value,str) and len(n.value)>7:exposed.append({'query_text':n.value,'search_mode':'SMART'})
    used={structure(x) for x in exposed};features=['rating','year','author','title','negative','include','format','availability','metadata','preference','sort']
    fresh=['SMART:'+','.join(c) for n in range(4,10) for c in combinations(features,n) if 'SMART:'+','.join(c) not in used]
    brief=load(R/'search_v2c_c5er_blind_author_brief.json')
    brief.update(task='Independently author150 genuinely new acceptance contexts,30 distinct semantic families and30 actual operation topologies,5 per scope/stratum cell. Avoid superficial paraphrases; no desired parser outcomes.',
        allowed_fresh_topologies=fresh,allowed_reads_only=['reports/'+P+'blind_author_brief.json','reports/'+P+'structure_source.txt'],
        output='reports/'+P+'authored.jsonl',provenance_output='reports/'+P+'author_provenance.json')
    brief['structure_function_source']['metadata']='Use ONLY the supplied exact pure C2 function text, no other source reads.'
    write('blind_author_brief.json',brief)
    with (R/(P+'structure_source.txt')).open('xb') as f:f.write((R/'search_v2c_c5er_structure_source.txt').read_bytes())
    print(json.dumps({'protected_verified':len(protected),'diagnosed_contexts':150,'fresh_topologies_available':len(fresh),'selected':decision['selected']}))
if __name__=='__main__':main()
