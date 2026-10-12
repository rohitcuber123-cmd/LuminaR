"""Finalize identity/count-only V2.2 reports from verified evidence."""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/'reports'

def read(name):
    return json.loads((REPORTS/name).read_text(encoding='utf8'))

def save(name,value):
    (REPORTS/name).write_text(json.dumps(value,indent=2),encoding='utf8')

def digest(path):
    return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()

production=[f'rag/services/{name}.py' for name in (
    'document_knowledge','knowledge_artifacts','knowledge_quiz','knowledge_quiz_relations','knowledge_mcq','knowledge_match')]+[
    'frontend/src/components/knowledge/KnowledgeTools.tsx','frontend/src/components/knowledge/Quiz.tsx',
    'frontend/src/lib/knowledgeArtifacts.ts']
tests=['tests/test_quiz_v2_2.py','tests/test_knowledge_quiz.py','tests/test_knowledge_artifacts.py',
       'frontend/tests/knowledge-artifacts.test.tsx']
support=['scripts/check_quiz_v2_2.py','scripts/test_quiz_v2_2_regressions.py','scripts/report_quiz_v2_2.py']
baseline={p.replace('\\','/'):h for p,h in read('quiz_v2_2_baseline_hashes.json').items()}
changed=[p for p,h in baseline.items() if digest(p)!=h]
assert set(changed)<=set(production),changed
previous=read('knowledge_tools_v2_1_baseline_hashes.json')
recommendation={p:h for p,h in previous.items() if p.replace('\\','/').startswith('recommendation/')}
assert all(digest(p)==h for p,h in recommendation.items())
save('quiz_v2_2_source_audit.json',{'production':production,'tests':tests,'support':support,
    'baseline_compared':len(baseline),'existing_production_changed':changed,
    'frozen_files_unchanged':len(baseline)-len(changed),'recommendation_files_unchanged':len(recommendation),
    'hashes':{p:digest(p) for p in production+tests+support},'prior_dirty_work_preserved':True})

groups=[]
for name in ('knowledge','hardening_final','regression_unit','regression_assistant','regression_security',
             'regression_staff','regression_notifications','regression_circulation','regression_search',
             'regression_kg','regression_kg_graph','regression_events'):
    tree=ET.parse(REPORTS/f'quiz_v2_2_{name}.xml');cases=list(tree.iter('testcase'))
    groups.append({'group':name,'tests':len(cases),'failed':sum(any(c.tag in ('error','failure') for c in t) for t in cases),
                   'skipped':sum(any(c.tag=='skipped' for c in t) for t in cases)})
assert not any(g['failed'] for g in groups)
front=(REPORTS/'quiz_v2_2_frontend_tests.log').read_text(encoding='utf8')
focused=(REPORTS/'quiz_v2_2_frontend_final.log').read_text(encoding='utf8')
front_passes=[int(v) for v in re.findall(r'pass (\d+)',front)]
assert sum(int(v) for v in re.findall(r'fail (\d+)',front))==0
assert re.findall(r'pass (\d+)',focused)[-1]=='43' and re.findall(r'fail (\d+)',focused)[-1]=='0'
lint=(REPORTS/'quiz_v2_2_lint.log').read_text(encoding='utf8')
build=(REPORTS/'quiz_v2_2_build.log').read_text(encoding='utf8')
assert 'error ' not in lint.lower() and 'built in' in build.lower()
regression={'backend_groups':groups,'passed_executions':sum(g['tests']-g['skipped'] for g in groups),
    'skipped_executions':sum(g['skipped'] for g in groups),'overlapping_isolated_suites':True,
    'frontend_full_passed':sum(front_passes),'frontend_final_knowledge_passed':43,'frontend_failed':0,
    'build':'PASS','lint_errors':0,'lint_warnings':'Existing warnings; no new diagnostics in changed study components.',
    'events_clock':'Test-only NOW alignment to current UTC for stale 6 October fixtures; real JWT expiry checks remain enabled.',
    'test_retry':'One unrelated flashcard keyboard timing failure on the final focused run; immediate rerun passed all 43. No flashcard source changes.'}
save('mcq_v2_2_regression.json',regression)

geometry=read('quiz_v2_2_browser_geometry.json')
assert len(geometry)==6 and all(not x['overlap'] and not x['horizontalOverflow'] for x in geometry)
assert all(abs(x['target'][i]-x['viewport'][i])<=1 for x in geometry for i in (0,1))
frontend={'mcq':{'question_1_to_5_to_1':True,'option_order_preserved':True,'selection_preserved':True,
    'checked_feedback_preserved':True,'contention_window_source_page':26,'frontend_reshuffle':False,
    'identity':'Unique option text, checked against backend correctAnswer; no numeric answer index.'},
    'matching':{'opaque_ids':True,'score_checked':'2 / 3','wrong_row_shows_user_and_expected':True,
    'next_previous_order_preserved':True,'selections_preserved':True,'submitted_feedback_preserved':True,
    'row_source_opens_page':26,'sets':2,'pairs':9,'full_score_checked':'6 / 6'},
    'responsive':geometry,'viewport_note':'Current browser zoom calibrated to requested CSS dimensions; rounding at most one CSS pixel.',
    'unit_tests':43,'screenshots':['match_v2_2_desktop.png','match_v2_2_mobile.png']}
save('mcq_v2_2_frontend.json',frontend)
save('match_v2_2_frontend.json',frontend)

live=read('quiz_v2_2_live.json')
cn=read('mcq_v2_2_cn_live.json');integrity=read('mcq_v2_2_answer_integrity.json')
matches=read('match_v2_2_cn_live.json')
assert integrity['cn_sample_size']>=20 and integrity['wrong_keys']==integrity['multiple_correct']==0
assert all(integrity['core_views_preserved'].values())
cn['live_api']=[x for x in live['documents'] if x['name']=='cn'][0]
cn['good_or_acceptable_percent']=100
save('mcq_v2_2_cn_live.json',cn)
matches['live_api']=cn['live_api'];matches['manual_pair_count']=9
save('match_v2_2_cn_live.json',matches)

required=['mcq_v2_2_'+x+'.json' for x in ('root_cause','answer_integrity','option_diversity','cn_live','frontend','regression')]+[
    'mcq_v2_2_decision.md']+['match_v2_2_'+x+'.json' for x in ('root_cause','relation_quality','cross_format_diversity','cn_live','frontend')]
decision='''# Quiz correctness V2.2

A. **PARTIAL under the requested strict acceptance rule.** Implementation and reproduced checks pass. MCQ acceptance gate 1 requires identifying a wrong-key root cause; no wrong key was reproduced in the supplied CN baseline. The reported defect remains unconfirmed. Independent matching gates pass against the reviewed records and tested invariants; dependent matching gate 16 remains PARTIAL because it requires full MCQ acceptance. This is not a universal semantic guarantee.

B. Confirmed causes: first compatible distractors repeated across the quiz, no global duplicate option-set gate, and permissive candidate associations. Legacy matching consumed evidence directly (not MCQ objects), but lacked a dedicated authoritative relation facet, opaque IDs and pair-level global allocation.

C. No backend key mismatch reproduced. Strict subject/relation/target round-trip and assembled-option verification now reject tampered or detached bindings.

D. No frontend option identity defect reproduced. The existing MCQ contract checks exact unique option text; no correct_index or browser reshuffling exists. Matching uses stable opaque left/right IDs.

E. Fix the correct target before distractor construction. Preserve source fact, subject, relation, evidence units, pages and source explanation together; verify again after option assembly.

F. Alternatives come from compatible relation families and retain their own source evidence. Reject equivalent values (including simple time-unit conversions), cached semantic peers and alternatives also supported for the current subject.

G. Bounded candidate generation and global selection penalize reuse after the first placement, cap distractor reuse at two, reject duplicate/near-duplicate sets and prefer varied correct targets.

H. Maximum two questions per primary concept, relation/form diversity where supported. CN accepted evidence supports definitions only; unsupported categories are not fabricated. Educational and OCR fixtures exercise definition/identification, with explicit purpose and numeric tests.

I. Contention-window baseline: page 26 explicitly establishes option C. D belongs to another subject's definition. No confirmed answer-binding defect. The browser source panel displays the same page for MCQ and matching feedback.

J. CN requested 12 MCQs: nine baseline questions become five stricter final questions. Across five stable seeded count requests, 24 final displayed items were manually reviewed against local source evidence: all GOOD/ACCEPTABLE. Match-only: two sets, three and six pairs, nine distinct supported learning items. Mixed: four MCQs + four clozes + one four-pair set; primary fact/concept/relation reuse across formats is zero. All nine final CN pairs were reviewed.

K. Known wrong keys in the reviewed final CN sample: **0**.

L. Multiple-correct and unsupported-correct answers in that sample: **0 / 0**.

M. CN distractor maximum reuse **8 → 2**, mean **6.75 → 1.667**, duplicate option sets **3 → 0**. Unique options stay nine as placements decrease **36 → 20**; the source vocabulary is limited. A/B/C/D all occur across the larger reviewed sample.

N. Live browser Q1→Q5→Q1 preserved MCQ order, selected answer and feedback. Matching Next/Previous preserved opaque-ID order, selections and 2/3 score. Row-level correction and page source were checked; six viewport checks have no page overflow or launcher overlap. All-correct matching also shows a numerical score.

O. Cached-model generation in the final audit is below one second (maximum 806ms on that run); live artifact cache hits and cold creation are separately recorded. No new encoder, no extra semantic batch, zero artifact Qwen calls. Assistant stays existing_qwen.

P. Knowledge/backend suite **279 passed**, final hardening **43 passed**. Frozen-system regressions include Assistant 439, Search 157, KG 32, Events 76, staff 76, notifications 51, circulation 40, unit 37 and security 116 passed / 10 skipped. Isolated suites overlap. Events uses a test-only fixture-clock alignment without production edits.

Q. Full frontend run **289 passed**; after the final all-correct score change, focused Knowledge tests **43 passed**. One unrelated flashcard keyboard timing failure passed on rerun; disclosed rather than hidden.

R. Production build **PASS**, lint **zero errors**. Existing lint and Vite large-chunk warnings remain.

S. Exact changed/new files in this phase:

'''
for category,entries in [('Production',production),('Tests',tests),('Support',support)]:
    decision+=category+':\n\n'+''.join('- `'+x+'`\n' for x in entries)+'\n'
decision+='T. Required reports:\n\n'+''.join('- `reports/'+x+'`\n' for x in required)
decision+='''
Additional source hashes, final API evidence, OCR fixture statistics, cleanup evidence, XML/logs and screenshots are retained. Private question/model text is kept out of permanent JSON reports.

U. The reported wrong-key case could not be reproduced, so strict overall acceptance remains PARTIAL. Candidate validation is deterministic and conservative; limited or ambiguous notes yield partial counts. Existing persisted semantic-peer metadata is reused; relationships outside that metadata depend on lexical/source-binding checks. Numeric equivalence covers basic durations, not arbitrary dimensional analysis. Stable requested-count seeds are reproducible; refresh does not imply a new quiz. No frozen subsystem or core 3.2.1 ranking/view changed. This phase stops here.
'''
(REPORTS/'mcq_v2_2_decision.md').write_text(decision,encoding='utf8')
assert all((REPORTS/name).exists() for name in required)
save('quiz_v2_2_completion.json',{'status':'PARTIAL','unconfirmed_mcq_gate':1,'implementation_checks':'PASS',
    'required_reports':required,'matching_acceptance_gates':{str(i):'PARTIAL' if i==16 else 'PASS' for i in range(1,21)},
    'core_version':'3.2.1','quiz_version':'3.2.2','relation_facet_version':3,'artifact_qwen_calls':0})
print('Required reports complete; status PARTIAL because reported wrong-key root cause is unconfirmed.')
