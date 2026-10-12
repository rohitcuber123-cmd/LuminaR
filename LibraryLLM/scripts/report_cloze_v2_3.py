"""Final phase audit. No tokens, submitted text or private PDF excerpts."""
import hashlib,json,re
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];REPORTS=ROOT/'reports'
def read(name):return json.loads((REPORTS/name).read_text(encoding='utf8'))
def save(name,value):(REPORTS/name).write_text(json.dumps(value,indent=2),encoding='utf8')
def digest(name):return hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
production=['rag/services/'+n+'.py' for n in ['cloze_grading','knowledge_cloze','knowledge_encoder','knowledge_artifacts','knowledge_routes','knowledge_quiz']]+[
    'frontend/src/lib/knowledgeArtifacts.ts','frontend/src/components/knowledge/KnowledgeTools.tsx','frontend/src/components/knowledge/Quiz.tsx']
tests=['tests/test_cloze_v2_3.py','tests/test_knowledge_quiz.py','frontend/tests/knowledge-artifacts.test.tsx']
support=['scripts/check_cloze_v2_3.py','scripts/check_cloze_v2_3_live.py','scripts/test_cloze_v2_3_regressions.py','scripts/test_cloze_v2_3_events.py','scripts/report_cloze_v2_3.py']
baseline=read('cloze_v2_3_baseline_hashes.json');changed=[p for p,h in baseline.items() if digest(p)!=h]
assert set(changed)<=set(production),changed
assert 'rag/services/document_knowledge.py' not in changed
audit={'production':production,'tests':tests,'support':support,'existing_production_changed':changed,
    'new_production':[p for p in production if p not in baseline],'baseline_compared':len(baseline),
    'frozen_files_unchanged':len(baseline)-len(changed),'recommendation_files_unchanged':sum(p.startswith('recommendation/') for p in baseline),
    'hashes':{p:digest(p) for p in production+tests+support},'prior_dirty_work_preserved':True}
save('cloze_v2_3_source_audit.json',audit)
groups=[]
for name in ['knowledge_final','hardening_final','regression_unit','regression_assistant','regression_security',
    'regression_staff','regression_notifications','regression_circulation','regression_search','regression_kg','regression_kg_graph','regression_events']:
    cases=list(ET.parse(REPORTS/f'cloze_v2_3_{name}.xml').iter('testcase'))
    groups.append({'group':name,'tests':len(cases),'failed':sum(any(c.tag in ('failure','error') for c in t) for t in cases),
        'skipped':sum(any(c.tag=='skipped' for c in t) for t in cases)})
assert not any(x['failed'] for x in groups)
front=(REPORTS/'cloze_v2_3_frontend_full.log').read_text(encoding='utf8');build=(REPORTS/'cloze_v2_3_build.log').read_text(encoding='utf8');lint=(REPORTS/'cloze_v2_3_lint.log').read_text(encoding='utf8')
assert re.findall(r'pass (\d+)',front)[-1]=='298' and re.findall(r'fail (\d+)',front)[-1]=='0'
assert 'built in' in build and 'error ' not in lint.lower()
geometry=read('cloze_v2_3_browser_geometry.json');assert len(geometry)==6
assert all(not x['horizontalOverflow'] and x['scroll']['bottom']<x['launcher']['top'] for x in geometry)
assert all(abs(x['viewport'][n]-x['target'][n])<=1 for x in geometry for n in [0,1])
regression={'backend_groups':groups,'passed_executions':sum(x['tests']-x['skipped'] for x in groups),
    'skipped_executions':sum(x['skipped'] for x in groups),'overlapping_suites':True,
    'final_hardening_note':'Final conservative plural/entity-article checks follow the broad CPU-batching regression run; all 105 focused cases pass.',
    'frontend_passed':298,'frontend_failed':0,'knowledge_frontend_cases':52,'build':'PASS','lint_errors':0,
    'lint_warnings':'Existing diagnostics only; no changed Knowledge component diagnostics. Existing large-bundle warning remains.',
    'events_fixture_clock':'Test-only adjustment of expired fixed 6 Oct fixtures to real UTC. Real JWT expiration remains enforced.',
    'flashcard_test_synchronization':'Existing keyboard test now awaits React effects; production Flashcards code unchanged.',
    'document_knowledge_version':'3.2.1','frozen_source_files':audit['frozen_files_unchanged'],'router_mode':'existing_qwen','router_research_rerun':False,
    'browser':read('cloze_v2_3_frontend.json'),'cleanup':read('cloze_v2_3_cleanup.json')}
save('cloze_v2_3_regression.json',regression)
quality=read('cloze_v2_3_quality.json');performance=read('cloze_v2_3_performance.json');live=read('cloze_v2_3_live.json')
assert quality['examples']>=200 and quality['correct_precision']>=.98 and quality['overall_accuracy']>=.95 and quality['numeric_conflict_accuracy']>=.99
assert performance['hard_750ms_pass']
assert all(x['cloze_count']>=10 and x['source_verified'] for x in live['documents'])
limits=['Development calibration: 50 generated source-bound items with repeated formatting variants plus manually labelled source fixtures; not held-out/general essay accuracy.',
    'Paraphrases remain conservative; unknown aliases/acronyms, unrestricted synonyms and unsupported conversions are rejected.',
    'The live CN selection has term/short-phrase blanks, not a numeric 2T blank. Numeric/quantity conflicts are tested against explicit supplemental source fixtures, not fabricated CN questions.',
    'CPU model load occurs at service startup (roughly 14–20 seconds in isolated calibration runs). Single uncached phrase requests remain interactive.',
    '20 distinct longer phrase answers take about 607 ms, above the preferred 200 ms but below the 750 ms hard target. Queue bounded at 64 with retryable failures.',
    'Only the existing CPU MiniLM and deterministic checks are used; no optional Qwen ambiguity experiment was justified by this development corpus.']
required=['cloze_v2_3_architecture.md']+['cloze_v2_3_'+x+'.json' for x in ['calibration','quality','performance','live','regression']]
save('cloze_v2_3_completion.json',{'status':'PASS','quality':quality,'latency':performance,'known_limitations':limits,'required_reports':required,
    'source_audit':'cloze_v2_3_source_audit.json','services':'cloze_v2_3_service_check.json','cleanup':regression['cleanup']})
architecture=f'''# Fill in the Blanks Natural Answer V2.3 — PASS

Implemented narrowly in the existing private Knowledge Tools Quiz. DocumentKnowledgeModel 3.2.1, study renderers, Flashcards reveal-only flow, MCQ V2.2 and Match generators remain intact. Frozen production files were hash-checked: {audit['frozen_files_unchanged']} unchanged, including all {audit['recommendation_files_unchanged']} Recommendation files. Pre-existing dirty work was preserved.

## Authoritative grading and private lifecycle

`POST /rag/documents/{{document_id}}/artifacts/{{artifact_id}}/cloze/{{item_id}}/grade` accepts only `{{"answer":"..."}}` (strict string, 1–500 characters, unknown fields forbidden). Existing authentication resolves current Mongo identity and session. The service retrieves the owned, current artifact and active source revision, resolves the stored item, validates canonical/source/prompt identity and aliases, then grades. It rechecks active ownership and artifact existence after grading, so logout/delete cannot publish private results. Responses use `Cache-Control: no-store`. Missing/wrong-owner/wrong-session items retain private 404 behavior; unauthenticated/revoked tokens return 401. Client expected-answer injection returns 422.

Each stored item retains stable ID, source fact/subject/relation identities, relation type, canonical answer, answer type, accepted aliases, evidence units, chunk IDs, page bounds and a bounded source-term conflict list. Canonical text comes from the same excerpt used to construct the blank; reconstructing the excerpt from prompt + canonical must match. Repeated/leaked answers and suspicious OCR letter-digit corruption are rejected. New cloze metadata is generated from existing core facts/quiz relations; core ranking is untouched. Only quizzes containing fill blanks receive a cloze cache revision. MCQ-only/Match-only cache identities and outputs remain unchanged.

## Bounded decision flow

1. Unicode NFKC, case fold, whitespace collapse, safe letter-hyphen spacing and punctuation. Leading articles may be ignored for terms/phrases; entity names retain them. Numeric signs, decimal points and unit symbols are preserved.
2. NUMBER / NUMBER_WITH_UNIT use Decimal equality and explicit unit dimensions. Supported duration units include ms/s/min/h and printed spellings; percent formatting is supported. Unknown symbols match only themselves. Wrong values, missing units, unsupported unit changes and reversed signs cannot be rescued by semantics.
3. TERM / ENTITY use normalized identity, explicit same-source acronym/full-name aliases, then at most one edit in one sufficiently long word. Short words/acronyms/qualifiers stay strict; automatic plural/singular changes and other known source terms are rejected. No embeddings are used for term identity.
4. SHORT_PHRASE / DESCRIPTION require compatible source evidence as well as CPU MiniLM similarity and clause coverage. Numeric, negation, multiple/single, role/direction and other source-entity conflicts override similarity. A small compositional rate/speed rule retains sender/receiver and receiver-purpose identity; it is not a technical synonym dictionary. DESCRIPTION answers require a predicate for semantic full credit. Partial feedback is only for a supported but incomplete phrase; identity/numeric blanks remain binary.
5. Grading returns CORRECT / PARTIAL / INCORRECT, canonical answer, source pages/chunks, concise feedback, reason and measured server latency.

## CPU preparation, batching and Qwen decision

The existing cached local `all-MiniLM-L6-v2` singleton is prepared on FastAPI startup, on CPU. Preparation does not add a core-model encoding batch. Normal grade requests use zero Qwen calls, zero CUDA calls and no generation/GPU inference lock. Optional Qwen fallback was not added: the measured development cases passed without it.

A 512-entry, 300-second scalar similarity cache retains hashed keys and scores only. Identical requests share a Future. Distinct phrase requests collect for 5 ms and share source/context encoding through the same CPU encoder; no second model is loaded. The transient queue is bounded at 64 jobs; a 700 ms wait becomes a retryable 503 rather than an incorrect answer. Ownership is still checked per request and again after work completes. Cache hits never bypass authentication or source revision checks.

Initial distinct-phrase stress exposed serial encoder queuing (about 1113 ms at 20 users). CPU batching reduced the final 20-user maximum to {performance['unique_phrase_levels'][-1]['max_ms']} ms. Repeated/mixed 20-user p95 is {performance['levels'][-1]['p95_ms']} ms; maximum {performance['levels'][-1]['max_ms']} ms. Single distinct-phrase HTTP request: {performance['unique_phrase_levels'][0]['max_ms']} ms. All final 1/5/10/20 levels satisfy the 750 ms hard target. The distinct 10/20-user workload exceeds the preferred 200 ms target.

## Frontend behavior

The cloze card has a typed field, Check answer and Enter submission. Before submission it does not render canonical answers or aliases. Feedback uses text and symbols: ✓ Correct, ~ Partially correct, × Needs review, with Your answer, Accepted/Expected answer, explanatory text and source links. State is keyed by stable item ID and survives Previous/Next. Try again clears only the current cloze response/result without regenerating the question. Failure keeps input and offers retry. Duplicate submission is blocked; pending checks abort on unmount/document/account change. MCQ/Match scoring is unchanged. Flashcards still show Front → Reveal answer → Show front, with Previous/Next and zero typed fields.

Browser checks covered all three verdicts, Enter, drafts/results through navigation, per-cloze retry, source page 1, a real mixed quiz (4 MCQ, 4 cloze, 1 set/4 pairs), matching 4/4 and preserved MCQ/Match results after cloze retry. Six CSS viewport sizes from 375×811 to 1920×1079 have no horizontal overflow and reserve at least 16 px between the study scroll area and Ask LuminaR. See desktop/mobile PNGs and browser geometry JSON.

## Evidence and limits

Development calibration: {quality['examples']} cases, {len(read('cloze_v2_3_calibration.json')['categories'])} categories, 50 generated source items from the actual CN PDF, educational fixtures and real image-only OCR, plus independently labelled narrow source fixtures. Correct precision {quality['correct_precision']:.0%}; verdict accuracy {quality['overall_accuracy']:.0%}; numeric conflict accuracy {quality['numeric_conflict_accuracy']:.0%} ({quality['numeric_conflict_case_count']} cases); zero term false accepts. This is development calibration, not held-out or unrestricted essay accuracy. Only six manually labelled correct paraphrases and two partial-answer cases supplement formatting/identity coverage.

Live API: CN 12 clozes / 57 variants; OCR 12 clozes / 53 variants. Source excerpts/pages were verified through private source routes. The OCR fixture is a genuine 3-page image-only PDF, processed by the existing OCR pipeline; native text pages = 0. Both mixed quizzes retain 4 MCQ, 4 cloze and one 4-pair match set. Numeric 2T examples are supplemental source fixtures; the conservative CN selection does not generate that numeric blank.

Validation: broad Knowledge/Quiz/OCR/private/DocRAG suite 338 passed, then final focused grading/artifact suite 105 passed. Frozen regression groups pass, with 10 pre-existing security skips. All 298 frontend tests pass (52 Knowledge tests). Build passes; zero lint errors, existing warnings only. Events fixtures receive a test-only clock alignment; real JWT expiry is enforced. Router V1–V5 research was not rerun. Disposable readers/server copies/private scratch were removed; the user's original PDF was only read.

Known limits:

'''+ '\n'.join('- '+x for x in limits)+'\n\n## Exact phase files\n\n'+ '\n'.join('- `'+x+'`' for x in production+tests+support)+'\n\n## Required reports\n\n'+'\n'.join('- `reports/'+x+'`' for x in required)+'\n'
(REPORTS/'cloze_v2_3_architecture.md').write_text(architecture,encoding='utf8')
assert all((REPORTS/x).is_file() for x in required)
print('PASS. Required reports saved; phase audit complete.',regression['passed_executions'],'passing backend executions (overlapping suites).')
