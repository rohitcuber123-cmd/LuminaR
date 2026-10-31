"""Evidence-backed engineering reports; no parser, application or DB calls."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import json,hashlib,ast,math,statistics
R=Path('reports');P='search_v2c_smarteng_';ROOT=Path.cwd()
def load(n):return json.loads((R/(P+n)).read_text(encoding='utf8'))
def rows(n):return [json.loads(s) for s in (R/(P+n)).read_text(encoding='utf8').splitlines() if s.strip()]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(n,v):
    with (R/(P+n)).open('x',encoding='utf8') as f:json.dump(v,f,indent=2,sort_keys=True,ensure_ascii=False)
def md(n,t):
    with (R/(P+n)).open('x',encoding='utf8') as f:f.write(t.strip()+'\n')
def link(p):return '['+Path(p).name+']('+str(Path(p).resolve()).replace('\\','/')+')'
def main():
    pre=load('preflight.json');frozen=load('candidate_freeze.json')
    assert all(sha(p)==h for p,h in pre['protected_files'].items()) and all(sha(p)==h for p,h in frozen['files'].items())
    metric=load('independent_metrics.json');overall=metric['overall'];observed=rows('independent_scored_observations.jsonl');gold={g['case_id']:g for g in rows('reviewed_population.jsonl')};pred={g['case_id']:g for g in rows('independent_predictions.jsonl')}
    cases=[];families={}
    for r in observed:
        family=r['shared_semantic_pattern_id'];entry=families.setdefault(family,{'contexts':0,'typed_correct':0,'false_execution':0,'missed_execution':0,'critical_operand_cases':0,'case_ids':[]})
        entry['contexts']+=1;entry['typed_correct']+=r['typed_correct'];entry['false_execution']+=not r['expected_execution'] and r['execution'];entry['missed_execution']+=r['expected_execution'] and not r['execution'];entry['critical_operand_cases']+=bool(r['critical_executed_operand_mismatches']);entry['case_ids'].append(r['case_id'])
        if r['mismatches']:
            cases.append({'case_id':r['case_id'],'family':family,'query':gold[r['case_id']]['query_text'],'expected':r['expected_decision'],'actual':r['decision'],'execution':r['execution'],
                'reason':pred[r['case_id']]['actual_plan']['decision']['reason_code'],'ledger':pred[r['case_id']]['actual_plan']['decision']['requirements'],'mismatches':r['mismatches']})
    blockers=[
        'Independent safety gate failed:15/100 blocked gold requests execute. Omitted creator/title/exclusion values are not represented as MissingOperand; lexical missing-word triggers do not generalize.',
        'Seven executed contexts have scored mandatory operand mismatches: whole-word WITHOUT exclusions are lost and the inherited facet fallback invents a Records category from a grammatical record noun. One overlaps an unsafe recommendation.',
        'Five valid canonical-repair/title requests are refused because residual frame proof remains surface-bound. Five exposed C5C missing cases also change type to UNSUPPORTED while remaining blocked.',
        'Full current Mongo/API authentication, current membership, expiry/CAS/one-use commits and canonical circulation workflows were not rerun: the user prohibited ALL Mongo writes, including disposable databases.',
        'Real embedding/vector relevance, index loading, staging end-to-end service behavior and production runtime health remain unqualified. Last known health is STALE/degraded; baseline_verified=False.',
        'Parser tail latency and four-worker contention need an agreed staging SLO and profiling. Existing append-only completion cannot fill an explicit placeholder; long parser queries also exceed the existing150-character choice contract.'
    ]
    write('acceptance_error_analysis.json',{'status':'SAFETY_GATES_FAILED','families':families,'failures':cases,'concrete_blockers':blockers,
        'candidate_edits_after_primary':0,'primary_captures':1,'recaptures':0,'normative_gold_changes_after_capture':0,
        'recommendation':'Retain active C4 production route. Advanced candidate remains experimental and disabled; no C5F or deployment.',
        'minimum_resolution':'A separately authorized revision needs structural MissingOperand and negative-domain ownership, proof for inherited facets, narrow completion/length compatibility, and genuinely fresh validation. Do not rebrand this exposed150 as independent again.'})
    perf=load('performance.json');dur=sorted(p['elapsed_ms'] for p in pred.values());capture_latency={'count':150,'p50_ms':statistics.median(dur),'p95_ms':dur[math.ceil(.95*len(dur))-1],'max_ms':max(dur)}
    lengths=Counter('over150' if len(g['query_text'])>150 else 'at_most150' for g in gold.values())
    write('native_contract_limits.json',{'real_Mongo_API_qualification':'BLOCKED_BY_USER_NO_WRITE_CONSTRAINT','Mongo_calls':0,'Mongo_writes':0,
        'local_function_checks':40,'global_retrieval_cases':8,'native_choice_projection_checks':4,'actual_native_transformer_checks':4,
        'auth_durability':'N/A for fresh live/native Mongo tests; historical C5E310 scenarios and833 boundaries preserved, not relabelled as new-candidate qualification.',
        'explicit_placeholder_completion':'Actual unchanged native transformer rejects append-only completion422; mandatory placeholder remains unresolved. Edit/resubmit is needed until a separately reviewed compatible completion design exists.',
        'length_contract':{'parser_max':500,'choice_query_max':150,'source':'search/interaction_api.py:ChoiceRequest','fresh_context_lengths':dict(lengths)},
        'correction_compatibility':'Candidate scoped FacetVocabulary now accepts exactly the same unique one-edit canonical proof used by understanding; native Apply/Keep pure transformers verified.',
        'qualified_native_response':'Current public chips, serialization, result count/offset/pagination and whole-word predicate tested with read-only in-memory providers. No real vector service or HTTP/Mongo session commit.'})
    core=Path('scratch/search_smart_engineering/ownership_recovery');inventory=[]
    purposes={'parser.py':'Legacy compatibility bridge, field-family recomposition, single explained typed guard and unchanged QueryPlan output.',
        'query_ir.py':'Source-owned modality, literal/facet/negative operators, relationships, missing/unsupported evidence and semantic topic.',
        'source_repair.py':'Protect explicit entity operands before applying bounded grammar edit proposals.',
        'vocabulary.py':'Shared unique scoped one-edit canonicalization for parser notices and native correction actions.',
        '__init__.py':'Disabled candidate package boundary.'}
    for p in core.glob('*.py'):inventory.append({'path':str(p.resolve()),'sha256':sha(p),'purpose':purposes.get(p.name,'Focused source-ownership/native-transformer regression'),'production_routing':False})
    write('implementation_inventory.json',{'candidate':'search-smarteng-disabled-compositional-2','files':inventory,
        'shared_frozen_dependency':'scratch/search_v2c_c5er/candidate_search_v4 (numeric grammar, QueryPlan, predicates, controls, C4 assess)',
        'earlier_disabled_version':'scratch/search_smart_engineering/parser.py and query_ir.py retained unchanged after supersession',
        'development_lineage':'Source snapshots and exact hash reconstruction accompany older development captures; API-only FacetVocabulary export aligned after the C5C capture. No original capture, gold or historical manifest was rewritten.',
        'source_modified_outside_new_namespaces':False,'active_C4_policy_changed':False})
    dev=load('final_c5c_typed_decision_scoring.json')['overall'];d90=load('final90_summary.json');d150=load('final150_summary.json')
    write('development_regression_report.json',{'C5C':{'contexts':644,'typed':dev['typed_accuracy'],'execution':dev['execution_accuracy'],'false':dev['false_execution_rate'],'missed':dev['missed_execution_rate'],
        'safe_typed_regressions':5,'strict_mismatch_contexts':442,'source_capture_lineage':str(R/(P+'final_c5c_source_lineage.json'))},
        'C5E90':d90,'C5ER150':d150,'broad_tests_passed':1438,'broad_final_failed':0,'native_choice_XML_tests':9,'overlap_note':'Five of the9 targeted choice/entity tests overlap the1438 broad tests. Do not add denominators as independent trials.',
        'failed_development_runs_preserved':{'first_broad':8,'focused_followup':2,'native_initial':'Author Aster was incorrectly repaired into after; fixture caught zero results; source protection fixed before acceptance.'},
        'independent_metrics_not_merged':True})
    md('01_architecture_diagnosis.md',f'''# Architecture diagnosis
All150 frozen C5E-R rows were traced before implementation: {link(R/(P+'baseline_traces.jsonl'))}. Baseline57/150 typed,97/150 execution,8/100 unsafe and45/50 missed.

Confirmed defects: modality was assigned after scalar extraction and covered only a few advisory adjectives; unquoted category/classification ownership missed common syntax and repairs; sort wording entered the missing-rating guard; deferred relationships were reduced to scalar matches; capability validation overwrote more informative unresolved decisions; negative domains depended on narrow phrase templates.

The first incorrect transformations and actual functions are recorded in {link(R/(P+'architecture_diagnosis.json'))}. These are source-backed defects, not a claim that every strict text mismatch changes meaning. Frozen gold and all old predictions remain intact.

Fresh acceptance still found structural failures: delimited omitted values, inherited incidental facet matches, missing WITHOUT whole-word ownership and overly narrow frame proof. The architecture is not qualified for production.''')
    md('02_architecture_decision.md',f'''# Architecture decision
Selected B: a compositional ownership IR with a lightweight native compatibility bridge. It shares frozen mature numeric recognition, QueryPlan, scalar predicates, explicit controls and C4 assessment. It adds modality ownership before extraction, explicit relationship evidence, scoped canonical repair and proof-based field recomposition. No model inference or database operation enters parsing.

A patch-only extension was rejected because three competing decision paths caused the demonstrated errors. A soft hybrid is used only for legitimate topics/advice; it cannot stand in for a missing required filter. A general model hot path would add latency, state and validation dependencies without proving native constraints. The selected implementation is small and inspectable, but its residual finite grammar and inherited fallback still failed fresh safety gates.

Maintainability: new logic is confined to {link(core/'parser.py')}, {link(core/'query_ir.py')}, {link(core/'source_repair.py')} and {link(core/'vocabulary.py')}. Earlier failed code is retained for lineage, not activated. Production imports remain unchanged.''')
    md('03_implementation_inventory.md','# Implementation inventory\n\n'+ '\n'.join('- '+link(x['path'])+' — '+x['purpose'] for x in inventory)+f'\n\nMachine-readable hashes: {link(R/(P+"implementation_inventory.json"))}. No active source, authorization, C4 policy, frontend/theme, RAG, recommendation, Qwen or index implementation was modified.')
    md('04_query_representation.md', '''# Query representation and flow
`Requirement` stores field, operator, parsed value, exact original source span, owning clause span, status, required/advisory ownership, hard/advisory/relationship representation and provenance. `Understanding` holds source candidates, relationship evidence, changed field families, canonical corrections and topic spans. QueryPlan remains the native dataclass.

```mermaid
flowchart LR
 Q[Query and explicit mode] --> L[Frozen compatibility grammar]
 Q --> E[Protected entity operands]
 E --> M[Modality and source-owned operations]
 M --> I[Requirement IR and relationships]
 L --> C[Recompose only proved field families]
 I --> C
 C --> D[Contradiction / missing / unresolved / unsupported guard]
 D --> P[Native QueryPlan and C4 assessment]
 A[Authenticated library / workspace] --> V[Authorized facets and capabilities]
 V --> M
 P -. disabled integration proposal .-> R[Existing native filtered retrieval]
```

Scope is not inferred from query text. The parser receives scoped vocabulary; trusted capability validation and native actor/library/workspace ownership remain external. `trusted_scope_from_text=False` is explicit IR metadata, not an authorization credential. EXACT and identifiers retain native literal behavior. The parser may interpret words about another library as text; it cannot change the authenticated provider.

Semantic topic/advice is kept separately from hard filters. Native `ranking_query()` can carry beginner/research guidance. Unrepresented strict operations remain blocked. Structured advisory truth has no invented string-equivalence metric. The failed fresh examples show that current missing-operand and inherited-facet ownership is still incomplete.''')
    md('05_safety_invariants.md', '''# Safety invariants and observed limits
- A recognized token is not sufficient proof that its entire required relationship is resolved.
- Advisory year/language/availability must not become hard scope filters.
- Missing required values are distinct from absent optional fields.
- Contradictory resolved predicates retain both sides; unsupported aggregate/result-set/proximity operations cannot become per-book approximations.
- Canonical category exclusions and broad whole-word text exclusions are distinct. `ar` does not exclude `Marsh` by substring.
- Literal entities are protected from cue repair; notices identify actual changed source text and a scoped canonical target.
- Query text cannot grant user role, library access or inventory authority.

These are required invariants, not a statement that this candidate satisfies them universally. Fresh acceptance violated missing-operand completeness and mandatory negative/facet ownership. The zero-safety-error gate failed, so the candidate must remain experimental and disabled. Full native durability/current-membership enforcement was not rerun under the no-Mongo-write constraint.''')
    md('06_development_regressions.md',f'''# Development regressions
| Exposed cohort | Typed | Execution | False | Missed |
|---|---:|---:|---:|---:|
| C5C644 |639/644|644/644|0/394|0/250|
| C5E90 |90/90|90/90|0/60|0/30|
| C5E-R150 |150/150|150/150|0/100|0/50|

The five C5C type changes remain blocked (INCOMPLETE→UNSUPPORTED), not unsafe executions. Native scalar fidelity and strict diagnostic mismatch files are retained separately.1438 broad tests passed; nine targeted native-choice/entity tests passed, with five overlapping broad cases. Failed broad/focused/native fixture runs are retained with source snapshots. Development perfection on two exposed cohorts is not independent evidence.

Details and code-lineage caveat: {link(R/(P+'development_regression_report.json'))}.''')
    md('07_independent_validation.md',f'''# Fresh independent validation — FAILED
150 contexts,30 semantic families and30 distinct actual C2 operation topologies; five contexts per30 scope/stratum cells. Fresh AI author and fresh AI reviewer received no candidate source, predictions, error list or target pass percentage. Human review0. Normative review/reconciliation completed before one frozen gold-blind capture; zero capture errors/retries. Established sealed structural audit and final focused-test audit passed; heldout evaluations0.

Typed115/150 (76.67%); execution130/150 (86.67%); false15/100 (15%); missed5/50 (10%). Recall: ambiguous20/25, incomplete0/25, unsupported25/25, contradictory25/25, notice20/25, clear executable25/25. Seven executed rows have scored mandatory operand mismatches. Strict scored fields79/150, not a complete semantic-meaning accuracy measure. Structured advisory/semantic-oracle gaps remain N/A.

Pre-registered targets95% typed,99% execution,zero unsafe or critical operand loss/invention,≤5% missed. Failed. All30 cells and every failure: {link(R/(P+'independent_metrics.json'))}, {link(R/(P+'independent_failures.json'))}, {link(R/(P+'acceptance_error_analysis.json'))}. No postcapture candidate changes or recapture occurred. This150 is now exposed development material.''')
    md('08_semantic_retrieval.md',f'''# Semantic retrieval and mandatory filters
Eight global cases execute the exact protected native GlobalQuerySearch implementation against read-only metadata and a fixed-ID synthetic semantic provider.40 public/private patron/staff local searches execute exact native tenant functions with read-only collection doubles. Verified: literal/author/category/ratings/whole-word exclusions, subject-filter transport, semantic topic delivered to provider, hydration predicate checks, pagination, serialization, empty matches and EXACT behavior.

The semantic provider is NOT a measured embedding/HNSW service. Native diagnostic `hnsw_used` on the synthetic branch does not establish a real index lookup. Ranking relevance, vector latency, real Mongo latency and real end-to-end service behavior are N/A. No ranking improvement is claimed. Source tests found and fixed Aster→after author corruption before acceptance; fresh acceptance still lost a WITHOUT word exclusion and invented a Records facet, so global semantic constraint correctness is not qualified.

Raw observations: {link(R/(P+'retrieval_contracts_final.json'))}; {link(R/(P+'offline_native_components_final.json'))}.''')
    md('09_native_integration.md',f'''# Native integration limits
No Mongo connection or write occurred. The user expressly prohibited all Mongo writes, including disposable databases. Therefore the previously passing310 real native scenarios/833 boundaries/529 denials remain HISTORICAL evidence; they are not fresh qualification of this candidate.

Fresh evidence:40 local and8 global exact-native-function cases with in-memory dependencies; four native choice projections; four actual native transformer checks (Apply,Keep,literal resolution,and rejected placeholder completion). Scoped one-edit canonicalization is now shared with native correction transforms. Current ownership/role/provider dependencies in the read-only harness are explicit doubles. Current membership, expiry/CAS, one-use commit, inventory/borrowing and full HTTP authorization were not freshly exercised. No authorization implementation changed.

An explicit omitted slot cannot be repaired by merely appending a value under the existing native `complete` operation: it correctly rejects422. Also, native ChoiceRequest permits150 query characters, while parser permits500; {lengths.get('over150',0)}/150 acceptance queries exceed the choice length. These are integration prerequisites, not deployed fixes. {link(R/(P+'native_contract_limits.json'))}.''')
    md('10_private_library_independence.md', '''# Private/global dependency audit and future catalog reduction
Read-only native-function fixtures include own local unlinked books under public/private patron/staff contexts with global fixture EMPTY and INACCESSIBLE. Local results and exact/author/subject/negative constraints continue working; foreign-library rows are excluded; zero global collection reads occur for unlinked local books. This establishes no five-million-record precondition for that tested path. Full Mongo/API/current-membership qualification remains unavailable.

Source dependencies:
- `backend/services/library_catalogue_experience.py`: `usable`, `source_locked`, `hydrate` and `read_context`. Local rows live in library_books, keyed by library_id/library_book_id. Linked global_work_id optionally supplies ratings, description, cover seed and book capabilities; unavailable global reads can still affect linked metadata.
- `backend/services/library_intelligence_store.py`: `source_records`, `fingerprint`, `directory`. Tenant datasets/search/kg generations use library UUID namespaces. Optional global enrichment affects content fingerprints and stale/fallback behavior after a catalog change.
- `backend/services/library_intelligence_artifacts.py`: `VectorCache`, `ArtifactCache`. Tenant embedding cache is per library and content/model version, separate from global work cache. No embedding/index/KG build was performed.
- `search/query_execution.py`: tenant search starts with native authorization and local source; it does not search the global candidate universe on an empty tenant result. Personalization can still depend on global work metadata.
- `recommendation/recommendation_service.py:get_recommendations` and local catalogue recommendations use global candidates/metadata plus local intersection/discovery. Global reduction changes recommendation quality/universe and linked references; unchanged storage does not prove unchanged recommendations.
- `rag/services/library_asset_pipeline.py`: authorized asset_id/library_id/generation namespaces keep local uploaded-document artifacts separate. Linked global-book QA/assets remain dependencies; no RAG behavior was changed or end-to-end requalified.

Future migration PLAN ONLY (no execution authorized):
1. Obtain separate read/export/staging-write authorization and a consistent rollback snapshot of global records, metadata sidecars, model/index/KG manifests and referencing collections.
2. Inventory all work_id/global_work_id references in library_books, loans/issues/reservations/reading lists/book assets/recommendation signals. Protect institution-owned rows/assets; do not prune by global count.
3. Select the curated5000–20000 global universe and retain referenced records or design an independently reviewed archival/reference strategy. Snapshot required linked metadata; preserve stable IDs/aliases.
4. In a disposable authorized staging database, exercise linked/unlinked institution books with global-empty/missing and curated metadata, disabled/stale tenant indices, local assets, role/privacy and borrowing boundaries.
5. Under separate index-build authorization only, construct matching GLOBAL lexical/vector/KG artifacts and manifests for the curated generation. Do not simply delete Mongo books while leaving old global index IDs/counts.
6. Detect tenant source-fingerprint changes and use existing stale/fallback safeguards. Any tenant re-enrichment/rebuild needs explicit authorization and must preserve scope namespaces.
7. Requalify global/private/public search, recommendations/More Like This and global/local RAG independently. Compare relevance and latency using real judgments/providers.
8. Cut over a versioned generation with a reversible pointer/data snapshot plan. Roll back the paired metadata/index generation together. No migration step was performed in this phase.

Feasibility is CONDITIONAL, not an approval or proof that arbitrary global deletion is safe.''')
    md('11_performance.md',f'''# Performance and operations
Exposed C5E-R150 parser-only serial timing: p50{perf['serial']['p50_ms']:.2f}ms, p95{perf['serial']['p95_ms']:.2f}ms. Four worker timings: p50{perf['concurrent_four_workers']['p50_ms']:.2f}ms, p95{perf['concurrent_four_workers']['p95_ms']:.2f}ms;150/150 serial/concurrent plan fingerprints match. CPU{perf['process_CPU_ms']:.2f}ms for the combined300 calls; RSS{perf['rss_before_bytes']}→{perf['rss_after_bytes']} bytes. Thread results include GIL/scheduling contention.

Fresh single-capture parser timing: p50{capture_latency['p50_ms']:.2f}ms,p95{capture_latency['p95_ms']:.2f}ms,max{capture_latency['max_ms']:.2f}ms. These are parser calls, not full search. Read-only fixture call timings are separately recorded in native reports and include in-memory dependencies.

Historical C5E10.19/20.63ms and real-native59.48/143.35ms came from different populations/providers/conditions; do not infer a matched speed improvement. Current tail/contended latency requires profiling and a declared staging SLO. Real Mongo, vector lookup, embedding/relevance and live end-to-end latency are N/A. No Qwen/model calls, network or index loads/builds occurred. Last known global health remains STALE/degraded; baseline_verified=False. No resident endpoint repoll.''')
    md('12_preservation.md',f'''# Preservation
Verified all2224 protected baseline entries at preflight and before acceptance, including the2040 C5E-R protected records, its exact candidate/gold/predictions and earlier C5A–C5E freezes.462 original production entries remain unchanged. No staged/tracked production modification, live Mongo write, HNSW/KG build, heldout evaluation, Qwen/recommendation/RAG change or activation occurred.

The initial working tree was clean at git822b667. Work is on codex/smart-search-engineering. New versioned files only. Failed development/native runs, source snapshots and old scoring outputs are retained. Where the public vocabulary export changed after an exposed C5C capture, the exact prior parser bytes were recovered and hash-verified in an immutable snapshot; the original capture/manifest was not rewritten. Final candidate freeze and primary outputs remain unchanged.

Final byte verification and complete file hashes are produced by the evidence-freeze script. Candidate freeze: {link(R/(P+'candidate_freeze.json'))}.''')
    md('13_production_integration_plan.md', '''# Conditional integration / rollback proposal — NOT IMPLEMENTED
Deployment is NOT authorized and this candidate failed acceptance. Retain the proven active C4 route. Do not begin C5F. The following plan applies only after separately authorized repairs and new qualification.

Exact integration surfaces to review:
- `search/query_plan.py`: a server-owned parser selector defaulting to C4, unchanged QueryPlan/public schema, mode handling and max-length policy. Package the reviewed experimental implementation under an application module before staging; no production scratch imports.
- `search/query_confidence.py`: one compatible typed/capability decision composition and native edit revalidation, preserving unresolved mandatory semantics.
- `search/query_session.py`, `search/session_store.py`, `search/query_interaction.py`: consistent parser version, parse/validate/canonical resolver imports, current identity/login/library/workspace binding, source-span edits, correction availability, expiry/version and one-use reservations. Do not change authorization behavior or use global monkeypatching.
- `search/interaction_api.py`: review existing150-character query/100-character completion contracts and placeholder completion semantics. Any schema or UX change is a separate reviewed decision, not silently extended here.
- `search/query_execution.py`, `search/api.py` and institutional route callers: retain native fresh access guards, scoped facet/capability selection, local-only candidate universes, filtering/hydration, pagination, error behavior and C4 assessment. Scope comes from trusted server context.

Staging prerequisites: zero observed unsafe/critical-operand errors under pre-registered fresh validation; required typed/execution/notice/EXACT gates; authorized disposable Mongo/API/current-membership/expiry/CAS/replay/borrowing tests; real providers and unavailable-service checks; benchmarked relevance; accepted parser/retrieval/concurrency latency; health/index-generation verification and packaging hashes. Current no-write constraint must be separately lifted for those staging fixtures.

Rollout proposal: independently reviewed server feature flag (does not exist in this phase), defaultC4, small authorized staging cohort and rollback rehearsal. Monitor decision types/reason codes, field coverage, parser/provider latency/errors, blocked/unsafe audits by mode/scope; never log private raw queries broadly. No unconditional model fallback.

Rollback: switch proposed selector back to C4; reject/migrate only incompatible search parser-version contexts through existing actor/scope-bound facilities. Do not delete general login/library data. Restore paired artifacts/config generation only if an authorized deployment changed them; this phase changed no database or indexes and needs no data rollback. Deployment/flag/source edits are not performed by this report.''')
    # Exact line-verified implementation map for project demonstrations.
    mapping=[('Experimental entry/typed guard',str(core/'parser.py'),'parse_query','Disabled; no HTTP route',str(core/'test_source_ownership.py'),'Independent safety FAILED'),
        ('Modality/relationships/negative IR',str(core/'query_ir.py'),'understand','Called by experimental parser','scratch/search_smart_engineering/test_architecture.py','Focused tests pass; new incomplete/negative gaps remain'),
        ('Entity protection',str(core/'source_repair.py'),'prepare_source','Experimental parser pre-extraction',str(core/'test_source_ownership.py'),'5 focused checks pass'),
        ('Canonical correction',str(core/'vocabulary.py'),'FacetVocabulary','Future native choice adapter only',str(core/'test_native_choices.py'),'Apply/Keep pure native transforms pass'),
        ('Global HTTP entry','search/api.py','search','POST /search','scripts/search_v2c_smarteng_native_final.py','Active route unchanged; full staging N/A'),
        ('Global execution','search/query_execution.py','GlobalQuerySearch','Existing global search','scripts/search_v2c_smarteng_native_final.py','8 read-only provider fixtures'),
        ('Institution execution','search/query_execution.py','_tenant_search','Existing institution search callers','scripts/search_v2c_smarteng_native_final.py','40 read-only local fixtures'),
        ('Current choice API','search/interaction_api.py','install','/query/suggestions, /query/resolve',str(core/'test_native_choices.py'),'No new HTTP/Mongo commit qualification'),
        ('Choice mutation logic','search/query_interaction.py','transformer','POST /query/resolve',str(core/'test_native_choices.py'),'4 source-extracted native transformer checks'),
        ('Search ownership/durability','search/session_store.py','resolve','Native execution/session service','tests/institution_v2g/test_query_v2c_c5a_native.py','Historical C5E only; unchanged source'),
        ('Library authority','backend/services/library_inventory_access.py','require_library_patron','Native catalogue guards','tests/institution_v2g/test_query_v2c_c5a_native.py','Historical real security evidence; no new DB writes'),
        ('Scoped catalogue/hydration','backend/services/library_catalogue_experience.py','hydrate','Institution catalogue/execution','scripts/search_v2c_smarteng_native_final.py','Read-only own-book fixtures'),
        ('Tenant source/index namespace','backend/services/library_intelligence_store.py','source_records','Tenant intelligence source pipeline','scripts/search_v2c_smarteng_native_final.py','Static dependency audit; no builds'),
        ('Tenant embeddings','backend/services/library_intelligence_artifacts.py','VectorCache','Existing tenant build service','reports/search_v2c_smarteng_10_private_library_independence.md','Static only; unchanged'),
        ('Local document RAG','rag/services/library_asset_pipeline.py','ask','Existing authorized asset QA','reports/search_v2c_smarteng_10_private_library_independence.md','Static audit; not requalified')]
    mapped=[];lines=['# Reviewer implementation map\n\n| Feature | Exact source/function | Route | Test/evidence | Verification |\n|---|---|---|---|---|\n']
    for feature,path,name,route,test,status in mapping:
        text=Path(path).read_text(encoding='utf8');nodes=[n for n in ast.walk(ast.parse(text)) if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name];line=nodes[0].lineno if nodes else None
        target=str(Path(path).resolve()).replace('\\','/')+((':'+str(line)) if line else '')
        lines.append('| '+feature+' | ['+path+']('+target+') `'+name+'` | '+route+' | '+link(test)+' | '+status+' |\n')
        mapped.append({'feature':feature,'path':str(Path(path).resolve()),'function':name,'line':line,'route':route,'test':str(Path(test).resolve()),'status':status})
    md('15_reviewer_implementation_map.md',''.join(lines));write('reviewer_map.json',mapped)
    fields={'FINAL':'PARTIAL','CANDIDATE_ID':'search-smarteng-disabled-compositional-2','ARCHITECTURE_SELECTED':'B: compositional ownership IR with shared native compatibility bridge','CANDIDATE_DISABLED':True,'PRODUCTION_READINESS':'BLOCKED','C5F_READY':False,'REMAINING_BLOCKERS':blockers,
        'GENERALIZATION_ROOT_CAUSES':'Modality-after-extraction, narrow field grammar, scalarized alternatives, overlapping decision composition; new missing placeholders/negative domains/inherited facets remain inadequate.',
        'SOURCE_FILES_CHANGED':[x['path'] for x in inventory],'NEW_MODULES':[x['path'] for x in inventory if not Path(x['path']).name.startswith('test')],
        'REMOVED_OR_SUPERSEDED_LOGIC':'No production logic removed; candidate supersedes raw entity cue repairs, late advisory extraction and selected unsupported-residue decisions only when source proof exists.',
        'QUERY_REPRESENTATION_IMPLEMENTED':True,'REQUIREMENT_LEDGER_STATUS':'Implemented; fresh missing-operand/ownership failures remain','SEMANTIC_REMAINDER_STATUS':'Transport tested; independent semantic meaning accuracy N/A without oracle','EXECUTION_GUARD_STATUS':'FAILED independent safety gate','NOTICE_AND_CORRECTION_STATUS':'20/25 fresh notice recall; scoped Apply/Keep pure transforms pass; placeholder/HTTP durability limits remain',
        'DEVELOPMENT_CONTEXTS_EVALUATED':{'C5C':644,'C5E':90,'C5ER':150},'DEVELOPMENT_TYPED_ACCURACY':{'C5C':dev['typed_accuracy'],'C5E':'90/90','C5ER':'150/150'},'DEVELOPMENT_EXECUTION_ACCURACY':{'C5C':'644/644','C5E':'90/90','C5ER':'150/150'},
        'DEVELOPMENT_FALSE_EXECUTION':{'C5C':'0/394','C5E':'0/60','C5ER':'0/100'},'DEVELOPMENT_MISSED_EXECUTION':{'C5C':'0/250','C5E':'0/30','C5ER':'0/50'},'REGRESSION_TESTS_PASSED':1438,'REGRESSION_TESTS_FAILED':{'final':0,'prior_failed_runs_retained':True},
        'INDEPENDENT_CONTEXTS_EVALUATED':150,'INDEPENDENT_TYPED_ACCURACY':overall['typed_accuracy'],'INDEPENDENT_EXECUTION_ACCURACY':overall['execution_accuracy'],'INDEPENDENT_FALSE_EXECUTION':overall['false_execution'],'INDEPENDENT_MISSED_EXECUTION':overall['missed_execution'],
        'AMBIGUITY_RECOGNITION':overall['per_kind_recall']['AMBIGUOUS'],'INCOMPLETE_RECOGNITION':overall['per_kind_recall']['INCOMPLETE'],'UNSUPPORTED_RECOGNITION':overall['per_kind_recall']['UNSUPPORTED'],'CONTRADICTION_RECOGNITION':overall['per_kind_recall']['CONTRADICTORY'],'EXECUTABLE_WITH_NOTICE_RECOGNITION':overall['per_kind_recall']['EXECUTABLE_WITH_NOTICE'],
        'STRUCTURAL_ISOLATION_STATUS':'PASS;30 topologies;150 unique contexts; no exposed/heldout overlap','INDEPENDENT_REVIEW_PROVENANCE':{'author':'/root/smarteng_normative_author','reviewer':'/root/smarteng_blind_reviewer','human':0,'model':'NOT_EXPOSED','reviewed':150},
        'SEMANTIC_CONSTRAINT_CORRECTNESS':'FAILED:7 executed scalar mismatch contexts; structured semantics/relevance N/A','SMART_MODE_STATUS':'Independent safety failed','EXACT_MODE_STATUS':'Read-only native and regression fixtures passed','GLOBAL_SEARCH_STATUS':'8 synthetic provider/native-function fixtures pass; live health unverified','PUBLIC_LIBRARY_STATUS':'Read-only local native-function checks pass; current real API qualification N/A','PRIVATE_LIBRARY_STATUS':'Read-only local native-function checks pass; current real API qualification N/A',
        'PRIVATE_GLOBAL_INDEPENDENCE':'Own unlinked local books pass empty/inaccessible global fixtures; linked metadata/recommendation dependencies remain conditional','STAFF_PATRON_AUTHORIZATION':'Unchanged source; fresh fixture authority doubled, historical real tests preserved','OUTSIDER_CONCEALMENT':'Fixture404 and historical native evidence; no new real membership/Mongo validation','END_TO_END_SEARCH_VERIFIED':False,'RETRIEVAL_RELEVANCE_RESULTS':'N/A; fixed-ID semantic fixture, no real ranking oracle',
        'PARSER_LATENCY':{'exposed_serial':perf['serial'],'fresh_single_capture':capture_latency,'concurrent_four':perf['concurrent_four_workers']},'SEMANTIC_RETRIEVAL_LATENCY':'N/A for real service','FULL_SEARCH_LATENCY':'Read-only fixture timings only; live/staging N/A','RUNTIME_HEALTH_VERIFIED':False,'STAGING_VALIDATION_STATUS':'BLOCKED:all Mongo writes prohibited; native auth/durability/real providers unavailable','HNSW_REBUILT':False,'KG_REBUILT':False,'PRODUCTION_DATABASE_MUTATED':False,'PRODUCTION_PARSER_CHANGED':False,'PRODUCTION_POLICY_CHANGED':False,'HELDOUT_EVALUATIONS':0,'HISTORICAL_EVIDENCE_PRESERVED':{'protected_entries':len(pre['protected_files']),'changes':0}}
    write('final_qa.json',{'required_fields':fields,'finite_sample_limit':'150 contexts share30 families across five scopes; no real-world zero-risk claim. Exposed and fresh denominators remain separate.',
        'fresh_candidate_freeze_sha256':sha(R/(P+'candidate_freeze.json')),'primary_predictions_sha256':sha(R/(P+'independent_predictions.jsonl')),
        'primary_attempts':1,'postcapture_candidate_changes':0,'postcapture_gold_changes':0,'recommendation':'Retain active C4 route and restrict advanced candidate to experimental use. No C5F/production activation.',
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),'source_paths':[x['path'] for x in inventory]})
    qa=['# Final QA — PARTIAL\n\nProduction readiness and C5F are BLOCKED. Candidate remains disabled. Retain the active C4 route.\n\n',
        'Development: C5C639/644 typed,644/644 execution; C5E90/90 and C5E-R150/150 typed/execution. Fresh independent115/150 typed,130/150 execution,15/100 false and5/50 missed. Seven executed contexts lose or invent scored mandatory operands.1438 regression cases pass.\n\n',
        'Read-only fixtures validate48 native-function retrieval cases and bounded choice logic; they do not qualify real Mongo/API/current authorization/durability. All Mongo writes remained prohibited. No real embedding relevance or live health qualification occurred.\n\n',
        'What improved: early modality, source-owned field families, explicit relationships, canonical repair/choice alignment and entity protection. Fresh results establish some behavior outside old cases, including20/25 ambiguity and25/25 contradiction/unsupported recall, but do not meet production safety. Missing placeholder semantics, negative domains and inherited facet ownership are concrete blockers. No code changes or retest of this cohort followed acceptance.\n\n',
        '| Required field | Actual value |\n|---|---|\n']
    for k,v in fields.items():qa.append('| '+k+' | '+(v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,separators=(',',':'))).replace('|','\\|')+' |\n')
    qa.append('\n## Required deliverables\n\n')
    for n in ['01_architecture_diagnosis.md','02_architecture_decision.md','03_implementation_inventory.md','04_query_representation.md','05_safety_invariants.md','06_development_regressions.md','07_independent_validation.md','08_semantic_retrieval.md','09_native_integration.md','10_private_library_independence.md','11_performance.md','12_preservation.md','13_production_integration_plan.md','15_reviewer_implementation_map.md']:
        qa.append('- '+link(R/(P+n))+'\n')
    qa.append('\nExact candidate and evidence hashes: '+link(R/(P+'candidate_freeze.json'))+'. Final preservation/evidence freeze is recorded separately. No deployment, catalog reduction, index build or C5F was performed.\n')
    md('14_final_qa.md',''.join(qa))
    print(json.dumps({'FINAL':'PARTIAL','required_fields':len(fields),'documents':15,'remaining_false':15,'remaining_missed':5,'C5F_READY':False}))
if __name__=='__main__':main()
