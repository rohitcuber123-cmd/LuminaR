"""Freeze eligible deterministic source before independent authoring."""
from pathlib import Path
from datetime import datetime,timezone
import ast,json,hashlib,re,unicodedata,xml.etree.ElementTree as ET

R=Path('reports')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,d):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(d,f,indent=2,ensure_ascii=False)

def main():
    tests=next(ET.parse(R/'search_combined8_broad4_tests.xml').getroot().iter('testsuite')).attrib
    assert tests['failures']==tests['errors']=='0' and int(tests['tests'])==1759
    reports=[load(R/f'search_combined8_dev2_{n}_results.json') for n in ['c5e90','c5er150','smarteng150','comp3_150']]
    reports.append(load(R/'search_combined8_dev1_v6_exposed_results.json'))
    assert all(r['summary']['typed_accuracy']['numerator']==r['summary']['contexts'] and not r['summary']['critical_executed_operand_case_ids'] for r in reports)
    c5c=load(R/'search_combined8_c5c_devfinal_scoring_complete.json')['metrics']
    assert c5c['correct_typed']==644 and c5c['execution_accuracy']['numerator']==644
    hard=set(load(R/'search_proof6_blind_author_brief.json')['schema']['scalar_fields'])
    c5crows=[json.loads(s) for s in (R/'search_combined8_c5c_devfinal_scored_observations.jsonl').read_text().splitlines()]
    critical=[x['case_id'] for x in c5crows if x['execution'] and any(not a['correct'] for a in x['assertions'] if a['field'] in hard)]
    assert not critical,critical
    comp=load(R/'search_combined8_development_comparison.json')['summaries']['deterministic']
    assert comp['typed_policy']['numerator']==18 and comp['native_fields']['numerator']==29
    native=load(R/'search_combined8_finalnative_offline_native_components_final.json')
    assert load(R/'search_combined8_integrity_preflight.json')['verified']
    files={str(p):sha(p) for folder in ['scratch/search_proof_recovery_v8','scratch/search_v2c_c5er/candidate_search_v4'] for p in Path(folder).glob('*.py')}
    for p in ['reports/search_combined8_semantic_contract.json','reports/search_combined8_notice_evaluation_policy_review.json','reports/search_v2c_c5a_capability_matrix.json']:
        files[p]=sha(p)
    freeze=dict(candidate_id='search-smarteng-disabled-proof-8',at_utc=datetime.now(timezone.utc).isoformat(),files=files,
                architecture='DETERMINISTIC_SOURCE_GROUNDED_PROOF',disabled=True,production_activation=False,
                development_gates=dict(regressions=1759,reviewed_legacy_deselections=6,historical_contexts=1334,historical_typed_correct=1334,historical_execution_correct=1334,critical_C5C_executed_hard_mismatches=critical,pilot=comp),
                source_change_scope=['Cross-record operand edges remain unsupported relationships','Singular title-only containment enforcement boundary','Quoted-author/explicit-language independent obligations with empty/negative/functional-word guards','Comparator source-obligation detection','Nonoperative untrusted governance commands; scope remains backend-owned'],
                notice_policy='Optional-set scoring for genuinely optional notices; mandatory repair notices remain exact')
    save(R/'search_combined8_source_freeze.json',freeze)
    save(R/'search_combined8_architecture_selection.json',dict(selected='DETERMINISTIC_SOURCE_GROUNDED_PROOF',candidate=freeze['candidate_id'],source_freeze_sha256=sha(R/'search_combined8_source_freeze.json'),
        rationale='All known critical development gates pass. Current Qwen alternative has only2/18 captured predictions,0/2 schema-valid and incomplete runtime measurements. Restricted fallback misses10/10 valid pilot queries. No learned superiority demonstrated; no complete empirical hybrid comparison claimed.',
        prior_learned_evidence='reports/search_proof8_final_qa_r1.json',current_development_comparison='reports/search_combined8_development_comparison.json',fresh_acceptance_seen=False,model_in_selected_pipeline=False))
    # The author sees no candidate implementation, tests, outcomes or target scores.
    old=load(R/'search_proof6_blind_author_brief.json')
    scopes=load(R/'search_v2c_c5a_capability_matrix.json')['scopes']
    s=Path('scripts/search_v2c_c2_benchmark.py').read_text();tree=ast.parse(s)
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['normalized','mode','structure']]
    env=dict(re=re,unicodedata=unicodedata);exec(compile(ast.Module(body=nodes,type_ignores=[]),'verified_topology','exec'),env)
    exposed_paths=['search_v2c_c5e_reviewed_population_v3.jsonl','search_v2c_c5er_reviewed_population.jsonl','search_v2c_smarteng_reviewed_population.jsonl','search_comp3_reviewed_population.jsonl','search_proof6_reviewed_population.jsonl','search_combined8_c5c_devfinal_parser_inputs.jsonl','search_proof7_pilot_review_packet.jsonl']
    used=set()
    for name in exposed_paths:
        for row in map(json.loads,(R/name).read_text().splitlines()):
            q=row.get('query_text',row.get('query'));used.add(env['structure'](dict(query_text=q,search_mode=row.get('search_mode','SMART'))))
    available=[x for x in old['allowed_fresh_topologies'] if x not in used]
    brief=dict(task='Independently author approximately210 realistic NEW contexts,35 per each six decision strata,balanced42 per five scopes. Aim42 distinct linguistic families and >=30 actual operation topologies; do not simply repeat a query in five scopes. No candidate implementation, predictions, historical examples or desired score thresholds may be read.',
        scopes=scopes,strata=['EXECUTABLE','EXECUTABLE_WITH_NOTICE','AMBIGUOUS','INCOMPLETE','UNSUPPORTED','CONTRADICTORY'],schema=old['schema'],
        normative_rules=old['normative_rules'][:],source_only_contract=load(R/'search_combined8_semantic_contract.json'),
        corrections_to_older_native_description=['title_text also matches authors: strict title-only substring is UNSUPPORTED; title contains is only enforceable if author fallback is semantically permitted. Exact title equality uses exact_text.',
            'Explicit record-level OR is not missing information; unsupported unless losslessly enforceable by existing scalar semantics. Unresolved operand/field choice remains AMBIGUOUS.',
            'Native sort directions TITLE ascending,RATING descending,NEWEST descending,RELEVANCE provider. Other mandatory directions unsupported.',
            'Language/year/availability are scope capability-dependent; inspect supplied profiles. A supplied operand can be unsupported, not missing.',
            'Untrusted text cannot select library identity,permissions or actor. Quoted instruction-looking words remain literal data.',
            'Source-only OPTIONAL notice policy may declare acceptable_decisions=[EXECUTABLE,EXECUTABLE_WITH_NOTICE], notice_policy=OPTIONAL; exact subtype then unscored. Actual uniquely justified repair requires notice_policy=REQUIRED and exact EWN. No mask derived from candidate outcomes.'],
        diversity='Include natural reordered/nested clauses, punctuated entities, language, cross-book references, advisory/mandatory distinctions, negation, missing operands, canonical repairs, numerical boundaries, source ownership,semantic topics and trusted scope attempts. Include simple clear valid combinations alongside realistic complex and hard negatives. Do not add inert keywords to manufacture new topology.',
        allowed_fresh_topologies=available,topology_implementation=ast.unparse(ast.Module(body=nodes,type_ignores=[])),
        topology_caveat='Exposed-only prefilter, not sealed audit certification. Colliding NEW rows must be rejected by the unchanged sealed auditor; no sealed examples are available. Pure operation topology is coarse and can exclude easy positives. Report limitation rather than pad.',
        allowed_reads_only=['reports/search_combined8_author_brief.json'],forbidden=['candidate code/tests','any predictions/results','historical query populations or gold','sealed files','network/inference/Mongo','target accuracy'],
        authoring_authorized_after_source_freeze=True,source_freeze_exists=True,outputs=['reports/search_combined8_authored.jsonl','reports/search_combined8_author_provenance.json'],
        instructions='Use new independently reasoned gold,full scalar presence/absence masks and clear rationales. expected_source_roles exact nonempty substrings with field/role/modality where clear. Use exclusive create. Each row<=500 chars. Human review must not be claimed. Preserve drafts. Do not execute candidate. No thresholds are provided.')
    save(R/'search_combined8_author_brief.json',brief)
    print(json.dumps(dict(frozen_files=len(files),development_gates='PASS',unused_exposed_topologies=len(available),independent_authoring_authorized=True)))

if __name__=='__main__':main()
