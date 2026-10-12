"""Build count/ID-only completion reports from verified local runs."""
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/'reports'
def read(name):return json.loads((REPORTS/name).read_text(encoding='utf8'))
def save(name,value):(REPORTS/name).write_text(json.dumps(value,indent=2),encoding='utf8')

cn=read('knowledge_tools_v2_1_cn_quiz.json');live=read('knowledge_tools_v2_1_live.json');ocr=read('knowledge_tools_v2_1_ocr.json')
frontend=read('knowledge_tools_v2_1_frontend.json');final=read('knowledge_tools_v2_1_final_live.json')
audit=read('knowledge_tools_v2_1_quiz_coverage_audit.json')
audit['root_causes']=['Exact article-derived categories isolate all 19 validated facts into undersized distractor pools.',
    'Matching was grouped by page rather than source relation family, excluding valid cross-section pairs.',
    'Multiple true properties were treated as conflicting identity definitions; generic answer-leak rules also suppressed valid frames.',
    'Short structured notes required evidence-aware parsing; fragments ending in conjunctions must still be rejected.']
audit['after']={'core_model_counts':audit['before']['model_counts'],'runs':cn['runs'],'model_version':'3.2.1','quiz_version':'3.1.0','private_text_logged':False}
save('knowledge_tools_v2_1_quiz_coverage_audit.json',audit)
tmp=ROOT/'.scratch/knowledge_tools_v2_1'
manual=json.loads((tmp/'cn_mcq.json').read_text(encoding='utf8'))
cn['manual_review']={'mcqs':[{ 'id':q['id'],'page':q['pageStart'],'rating':'ACCEPTABLE' if index in (5,7) else 'GOOD',
    'answer_supported':True,'four_source_supported_options':True,'unambiguous':True} for index,q in enumerate(manual['questions'])],
    'matching_sets':[{'id':q['id'],'rating':'GOOD','pairs':len(q['leftItems']),'all_pairs_source_verified':True}
                     for q in json.loads((tmp/'cn_matching.json').read_text(encoding='utf8'))['questions']],
    'good_or_acceptable_percent':100,'notes':['Two definitions retain awkward source wording; all answers and alternatives are source-supported.',
    'The incomplete conjunction-ending candidate was rejected before the final run.'], 'private_text_in_report':False}
cn['qwen_decision']={'adopted':False,'calls':0,'reason':'Deterministic real-CN coverage exceeds six MCQs and one matching set, so the conditional experiment is not triggered.'}
save('knowledge_tools_v2_1_cn_quiz.json',cn)
save('knowledge_tools_v2_1_performance.json',{'live_preparation_and_artifacts':live['documents'],'ocr_fixtures':ocr['fixtures'],
    'final_ocr_and_restore':final,'cold_legacy_quiz_facet_migration_ms':cn['facet_preparation_ms'],
    'new_model_semantics':'Reuses existing single CPU embedding batch; legacy facet migration has one bounded batch, then persists identities.',
    'production_quiz_qwen_calls':0,'measurements':'Single local runs, not a throughput benchmark.'})

groups=[]
for name in ['unit','assistant','security','staff','notifications','circulation','search','knowledge','private_final','hardening','kg','events']:
    path=REPORTS/f'knowledge_tools_v2_1_regression_{name}.xml'
    tree=ET.parse(path);cases=list(tree.iter('testcase'))
    groups.append({'group':name,'tests':len(cases),'failed':sum(any(c.tag in ('error','failure') for c in t) for t in cases),
                   'skipped':sum(any(c.tag=='skipped' for c in t) for t in cases)})
assert not any(g['failed'] for g in groups),groups
frontlog=(REPORTS/'knowledge_tools_v2_1_frontend_tests.log').read_text(encoding='utf8')
frontpass=int(re.findall(r'pass (\d+)',frontlog)[-1]);frontfail=int(re.findall(r'fail (\d+)',frontlog)[-1]);assert frontfail==0
regression={'backend_groups':groups,'passed_executions':sum(g['tests']-g['skipped'] for g in groups),'skipped_executions':sum(g['skipped'] for g in groups),
    'counts_include_overlapping_isolated_suites':True,'frontend_passed':frontpass,'frontend_failed':frontfail,'build':'PASS','lint_errors':0,
    'lint_warnings':'Existing warnings retained; no new diagnostics in the changed study components.',
    'events_fixture_clock':'Original tests pin 6 Oct 2026; five stale receipt tests fail against a later real JWT clock. Runner aligns fixture NOW with current UTC, preserving expiry validation. All 76 then pass; Events sources unchanged.'}
save('knowledge_tools_v2_1_regression.json',regression)

production=['rag/services/'+p+'.py' for p in ['document_knowledge','knowledge_artifacts','knowledge_quiz','knowledge_quiz_evidence','knowledge_quiz_formats',
    'private_document_ocr','private_ocr_worker','private_documents','private_document_routes','local_document_cache']]+[
    'frontend/src/components/AIChatWidget.tsx','frontend/src/components/knowledge/KnowledgeTools.tsx','frontend/src/components/knowledge/Quiz.tsx',
    'frontend/src/index.css','frontend/src/lib/api.ts','frontend/src/pages/LLMPage.tsx']
tests=['tests/'+p+'.py' for p in ['test_knowledge_quiz','test_knowledge_artifacts','test_knowledge_algorithms','test_private_document_cache','test_knowledge_tools_v2_1','test_private_preparation_status']]+[
    'frontend/tests/assistant.test.tsx','frontend/tests/knowledge-artifacts.test.tsx','frontend/tests/part3-contract.test.tsx']
support=['scripts/check_knowledge_tools_v2_1.py','scripts/test_knowledge_tools_v2_1_regressions.py','scripts/test_knowledge_tools_v2_1_events.py',
    'scripts/report_knowledge_tools_v2_1.py','docs/private_document_ocr.md']
baseline=read('knowledge_tools_v2_1_baseline_hashes.json')
changed=[p for p,v in baseline.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=v]
assert set(changed)<=set(production),changed
files={'production':production,'tests':tests,'support':support,'baseline_compared':len(baseline),'baseline_changed':changed,
    'frozen_sources_unchanged':len(baseline)-len(changed),'hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in production+tests+support}}
save('knowledge_tools_v2_1_source_audit.json',files)
assert len(frontend['checks'])==36 and not any(c['overlap'] for r in frontend['checks'] for c in r['controls'])
assert all(r['scrollBottom']<r['launcherTop'] for r in frontend['checks'])
assert all(read('knowledge_tools_v2_1_preservation.json').values())

required=['quiz_coverage_audit','cn_quiz','ocr','frontend','performance','live','regression','decision']
doc='''# Knowledge Tools V2.1 completion

A. **PASS** — the 36 completion gates are satisfied. Fixture clock adaptation and viewport rounding are disclosed below.

B. Preserved DocumentKnowledgeModel 3.2.1 selection/ranking/diversity. The real CN concept IDs, labels, explanations and scores, card text/types, quick-summary text and map labels/types match the previous baseline exactly. One existing bounded CPU semantic batch is reused for new quiz ambiguity metadata. Old cached models migrate only their additive quiz facet.

C. Nineteen validated real-CN facts starved because article-derived category pools were too small. Matching used page-local groups. Identity-conflict/leak checks were also applied too broadly. The audit records before/after candidates and every requested rejection category.

D. Real CN MCQ-only, requested 12: **0 → 9**, all nine manually reviewed against source evidence and alternatives. Seven GOOD, two ACCEPTABLE for awkward original wording; no incomplete or invented answer.

E. Real CN Match-only, requested 12: **0 → 2 sets**, each four pairs, both manually verified and GOOD. Families span source pages. Mixed requested 12: **2 MCQs + 2 matching sets + 4 fill questions**; partial counts are explicit and other successful types survive.

F. Bounded typed evidence/option pools, up to 100 frames, exact source associations, aliases, lexical overlap and cached semantic-peer checks. Four distinct alternatives remain required. Description options remove the old category starvation; every alternative keeps its own source IDs. Cross-format evidence/concept deduplication and source-section preference remain active.

G. Additive quiz-only structured colon, heading/bullet and short-definition relations preserve exact excerpts and evidence unit IDs. Identity, purpose, property, process, composition, component function and explicit application families remain distinct. Core concepts/cards/summary/map and RAG text are not rewritten. Dangling conjunctions, generic/deictic subjects, flattened ambiguous formulas and unsupported fragments are rejected.

H. Optional Qwen experiment **not triggered**: deterministic CN coverage exceeds six MCQs and one matching set. Production artifact Qwen calls stay **zero**, with no per-question inference. Assistant remains **existing_qwen**.

I. Local **PyMuPDF embedded Tesseract**, English fast language data, no external OCR API, no GPU OCR model and no pytesseract dependency. The 4,113,088-byte pack is pinned and checksummed in the preflight report. RGB raster input is required by the tested build. [PyMuPDF OCR documentation](https://pymupdf.readthedocs.io/en/latest/faq/index.html#OCR), [official Tesseract language data](https://github.com/tesseract-ocr/tessdata_fast).

J. Native quality uses letter/word counts, alphabetic and printable ratios, and replacement/control character ratios. Defaults: 220 DPI, maximum 12 million raster pixels, one concurrent OCR page, two preparations, 20-second page timeout, 80 attempts. Oversized pages are rejected before allocation. Failures remain page-local with an authenticated UI warning.

K. Three-page image-only fixture: all three pages OCR, 12 concepts, 12 cards, 12 MCQs and 3 matching sets in single-type live runs. Ask Document returned a sourced answer with three sources. OCR View Source was verified through the browser and API.

L. Mixed text/scan/text fixture: methods **NATIVE/OCR/NATIVE**, original pages 1/2/3, only one OCR attempt. Blank and unusable-content fixtures remain empty rather than generating fabricated facts.

M. Images stay in memory/pipes; private extraction/chunks/model/artifacts use the existing authenticated session lifecycle. Encrypted restore retains OCR page markers and vectors with no PDF/raster and no OCR or embedding rerun. Live status is account/session/UUID scoped and disappears on completion. Owned test accounts/documents and private scratch files were removed; original CN PDF stays untouched. The nonprivate English language dependency remains cached.

N. The launcher was fixed over the content, and padding inside the scrolling content did not protect controls at intermediate scroll positions. The desktop sidebar also squeezed mobile content.

O. Shared launcher dimensions and a **rail outside the scroll viewport** guarantee clearance. Flashcards have Previous / Card N of M / Next, clamp/filter reset, and Left/Right/Space/Enter shortcuts that ignore interactive fields and dialogs. Desktop sidebar collapses to an optional mobile drawer.

P. Quiz pager renders one question, preserves per-question answers/checks, shows correct-answer or matching-pair feedback/source links, and exposes Previous/Next/Try again above the launcher rail. Exact generated/requested/per-type counts and shortfalls are visible.

Q. All **36 checks** across flashcards, MCQ feedback, matching feedback, concepts, summary and map at **1440×900, 1366×768, 1024×768, 768×1024, 390×844, 375×812** passed: zero visible overlaps or horizontal page overflow, 16px clearance. Actual clicks, matching answers, source links and card shortcuts were tested. Mobile launcher is a 52px accessible Ask LuminaR circle. Existing browser zoom was accounted for; measured CSS dimensions have at most one-pixel rounding.

R. Live native preparation: CN 29 pages **625ms**, three-page native **100ms**, zero OCR attempts. First CN model/concept view **1.49s**; other study views use the persisted model.

S. Live full-scan preparation **4.10s** (3.32s OCR), mixed **1.32s** (1.03s OCR). Final OCR worker peak RSS **97MB**, RGB raster **14MB**. Encrypted restore **42ms** with all three OCR markers. These are single local measurements, not throughput claims.

T. CN live mixed/MCQ/Match generation **59/53/55ms**, cache hits **17–19ms**. Cold legacy-facet migration includes one CPU encoder load (~12s); newly prepared models reuse their existing semantic batch and cached views do not repeat it.

U. Backend suites pass: Knowledge **233**, final private/cache/status **53**, final hardening **29**, KG **32**, Events **76**, plus unit/Assistant/security/staff/notifications/circulation/Search groups. Ten existing skips; isolated suites overlap. The unmodified Events fixtures pin 6 Oct 2026 and their receipts expire after that day. A test-only runner aligns NOW to current UTC, retaining expiry checks; all 76 pass without Events source edits.

V. Frontend **285 passed**, including Know More, Assistant, Events, paging and source/privacy controls.

W. Production build PASS; lint has **zero errors**, existing warnings retained. Existing Vite chunk-size warning remains.

X. Exact V2.1 changed/new files (prior V2 files left unchanged are excluded):

'''
for category,entries in [('Production',production),('Tests',tests),('Support/docs',support)]:
    doc+=category+':\n\n'+''.join('- `'+p+'`\n' for p in entries)+'\n'
doc+='Y. Required reports:\n\n'+''.join('- `reports/knowledge_tools_v2_1_'+p+('.md' if p=='decision' else '.json')+'`\n' for p in required)
doc+='''
Additional preflight, preservation, source audit, cleanup, final live, XML test evidence and screenshots accompany these reports.

Z. English printed-text OCR is optional and depends on local language data. Handwriting, poor scans, complex math and other languages may fail; failures are reported, with usable pages retained. Coverage is intentionally partial when supported facts or unique pairs are scarce. Matching counts are sets, not individual pairs. Viewport dimensions can round by one CSS pixel at the existing 80% browser zoom. Events regression requires its fixture clock alignment; no production Events change was made. No frozen Search/Recommendation/KG/Events/Admin/Notifications/Book RAG/router source changed (228 baseline files unchanged). No router experiment or new phase was started.
'''
(REPORTS/'knowledge_tools_v2_1_decision.md').write_text(doc,encoding='utf8')
print('Reports finalized:',regression['passed_executions'],'backend passes,',frontpass,'frontend passes; frozen baseline files:',files['frozen_sources_unchanged'])
