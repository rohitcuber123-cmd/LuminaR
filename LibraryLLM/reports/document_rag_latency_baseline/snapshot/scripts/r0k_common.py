"""Read-only production score execution for R0K; fixed candidate membership."""
from __future__ import annotations

import ast
import copy
from functools import lru_cache
import hashlib
import inspect
import json
from types import SimpleNamespace
from r0i_common import *
from r0j_common import freeze_j, ids, CRITICAL

OUT_K = REPORTS / 'rag_r0k_composite_audit.json'
SCORES_K = TRAIN / 'evaluation/rag_r0k_composite_scores.parquet'
PRE_K = REPORTS / 'rag_r0k_preflight.json'
R0J = REPORTS / 'rag_r0j_dense_quota_candidates.json'
SYSTEMS = ('dense', 'raw-ce', 'current-composite')
SELECTION_K = ('Compare current-composite versus raw-ce lexicographically by Hit20, Hit10, Hit5, MRR. '
               'Exact equality is neutral; descriptive DRAFT DEV results, no weight optimization.')


def freeze_k():
    ledger, r0, r0i = freeze_j()
    pre_j = read(REPORTS / 'rag_r0j_preflight.json')
    verify_ledger(pre_j['before_sha256'])
    for path, expected in pre_j['experimental_code_sha256'].items():
        assert sha(path) == expected
    r0j = read(R0J)
    assert r0j['decision'] == 'G. R0J MIXED / INCONCLUSIVE'
    assert sha(r0j['score_path']) == r0j['score_parquet_sha256']
    assert sha(r0j['tests']['path']) == r0j['tests']['sha256']
    for name in r0j['artifacts_created']:
        path = ROOT / name
        assert path.is_file(), path
        ledger[str(path)] = sha(path)
    return ledger, r0, r0i, r0j


@lru_cache(maxsize=1)
def production_formula():
    """Compile untouched post-CE statements directly from RAGReranker.search."""
    from rag.evidence import calculate_evidence_score, normalize_scores_minmax
    from rag.evidence import CROSSENCODER_WEIGHT, EVIDENCE_WEIGHT, FAISS_WEIGHT
    source = ROOT / 'rag/reranker.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'RAGReranker')
    search = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'search')
    start = next(i for i, n in enumerate(search.body) if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'raw_scores' for t in n.targets))
    stop = next(i for i, n in enumerate(search.body) if isinstance(n, ast.Expr)
                and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute)
                and isinstance(n.value.func.value, ast.Name) and n.value.func.value.id == 'candidates'
                and n.value.func.attr == 'sort')
    statements = copy.deepcopy(search.body[start:stop+1])
    # Reject accidental extraction of candidate generation or any model call.
    calls = [n for s in statements for n in ast.walk(s) if isinstance(n, ast.Call)]
    assert not any(isinstance(n.func, ast.Name) and n.func.id == 'generate_expanded_queries' for n in calls)
    assert not any(isinstance(n.func, ast.Attribute) and n.func.attr in ('search', 'predict', 'encode') for n in calls)
    args = ast.arguments(posonlyargs=[], args=[ast.arg(arg=x) for x in
        ('self', 'candidates', 'scores', 'query', 'retrieval_queries', 'intent_data')],
        vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[])
    fn = ast.FunctionDef(name='production_post_ce', args=args,
        body=statements + ast.parse("return candidates, {'evidence_seconds':evidence_time}").body,
        decorator_list=[])
    namespace = {'time': time, 'normalize_scores_minmax': normalize_scores_minmax,
        'calculate_evidence_score': calculate_evidence_score,
        'CROSSENCODER_WEIGHT': CROSSENCODER_WEIGHT, 'EVIDENCE_WEIGHT': EVIDENCE_WEIGHT, 'FAISS_WEIGHT': FAISS_WEIGHT}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), str(source), 'exec'), namespace)
    final_assignment = next(n for s in statements for n in ast.walk(s) if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == 'item'
                and isinstance(t.slice, ast.Constant) and t.slice.value == 'final_score' for t in n.targets))
    hashes = {str(p): sha(p) for p in (source, ROOT / 'rag/evidence.py', ROOT / 'rag/retriever.py')}
    info = {'source_sha256': hashes, 'post_CE_AST_sha256': hashlib.sha256(ast.dump(ast.Module(body=statements, type_ignores=[])).encode()).hexdigest(),
        'production_statement_first_line': search.body[start].lineno,
        'production_statement_last_line': search.body[stop].end_lineno,
        'formula_from_current_AST': ast.unparse(final_assignment.value),
        'weights': {'CE': CROSSENCODER_WEIGHT, 'evidence': EVIDENCE_WEIGHT, 'dense': FAISS_WEIGHT},
        'normalization': {'CE': 'per-query pool min-max (score-min)/(max-min)',
            'dense': 'same per-query min-max; input score key, fallback faiss_score, fallback0',
            'empty': '[]', 'zero_range': '0.5 for every candidate if span ==0 exactly',
            'normalization_clipping': 'none; finite actual inputs are in[0,1] after min-max',
            'evidence': 'calculate_evidence_score directly; internally clamped max(0,min(1,score)), no pool normalization',
            'final_score_clipping': 'none'},
        'tie_behavior': 'Python stable candidates.sort(key=final_score, reverse=True); exact ties retain incoming dense order',
        'evidence_context': {'retrieval_queries': '[original question] only; no generator or expanded retrieval called',
            'intent_data': None, 'intent_note': 'Unchanged RAGReranker.search default; equivalent to historical audit intent_data={}; no external semantic intent model invoked.',
            'metadata': 'Exact frozen tokens_220 corpus metadata, with score=G3 inner product and dense input rank',
            'all_chunks_dict': 'All16895 exact frozen tokens_220 texts keyed by unchanged canonical chunk_id',
            'concept_matching': 'Existing evidence-internal concept matching remains; no separate lexical retrieval/score added.',
            'default_evidence_formula': 'clamp(0.20*term_overlap +0.20*phrase_overlap +0.10*concept_density +0.30*alignment_score +0.15*multi_q_coverage +0.05*speaker_score)',
            'default_branch_note': 'intent_data=None leaves semantic_intent=None, so existing final evidence combination takes fallback even when regex intent is causal/temporal. multi_q_coverage=0 for a single retrieval query. No branch repaired.',
            'metadata_index_note': 'Existing neighbor/temporal helpers parse numeric chunk-ID suffixes; frozen tokens_220 hash IDs are not remapped to numeric IDs.'},
        'evidence_function_source': inspect.getsource(calculate_evidence_score),
        'normalization_function_source': inspect.getsource(normalize_scores_minmax),
        'executed_post_CE_source': '\n'.join(source.read_text(encoding='utf-8').splitlines()[search.body[start].lineno-1:search.body[stop].end_lineno])}
    info['formula_fingerprint_sha256'] = hashlib.sha256(json.dumps({'sources': hashes, 'AST': info['post_CE_AST_sha256']}, sort_keys=True).encode()).hexdigest()
    return namespace[fn.name], info


def source_verify(info):
    for path, expected in info['source_sha256'].items():
        assert sha(path) == expected, 'Production scoring source changed; STOP'


def scoring_candidates(dense, metadata):
    assert len(dense) == 60 and len(set(ids(dense))) == 60
    return [{**copy.deepcopy(metadata[c['chunk_id']]), 'score': c['similarity'], 'rank': c['rank']}
            for c in dense]


def composite(candidates, scores, question, all_texts):
    fn, formula = production_formula()
    source_verify(formula)
    before = ids(candidates)
    assert len(before) == 60 and len(set(before)) == 60
    assert len(scores) == 60 and all(math.isfinite(float(x)) for x in scores)
    instance = SimpleNamespace(retriever=SimpleNamespace(chunk_texts=all_texts))
    rows, timing = fn(instance, copy.deepcopy(candidates), scores, question, [question], None)
    assert len(rows) == 60 and set(ids(rows)) == set(before), 'Composite changed membership; STOP'
    for i, c in enumerate(rows, 1):
        c['composite_rank'] = i
        assert math.isfinite(c['final_score'])
    return rows, timing


def formula_package_sources():
    """Fingerprint the actual CE predict/forward source, without loading a checkpoint."""
    from sentence_transformers import CrossEncoder
    import importlib.metadata
    files = {Path(inspect.getsourcefile(method)) for method in (CrossEncoder.predict, CrossEncoder.forward)}
    return {'source_sha256': {str(p): sha(p) for p in sorted(files)},
        'versions': {name: importlib.metadata.version(name) for name in ('sentence-transformers', 'transformers', 'torch')},
        'CE_scoring_adapter_source_sha256': {str(ROOT / 'scripts/r0i_common.py'): sha(ROOT / 'scripts/r0i_common.py')}}


def movements(questions, systems):
    per = []; crossings = {f'{kind}_TOP{k}': [] for kind in ('COMPOSITE_RECOVERED_TO', 'COMPOSITE_DEMOTED_OUT_OF') for k in (1, 3, 5, 10, 20)}
    for q in questions:
        qid = q['query_id']
        ranks = {name: systems[name]['per_query'][qid]['first_rank'] for name in SYSTEMS}
        old, new = ranks['raw-ce'], ranks['current-composite']
        if old is None:
            assert new is None
            kind = 'UNCHANGED'
        else:
            kind = 'IMPROVED' if new < old else 'REGRESSED' if new > old else 'UNCHANGED'
        per.append({'query_id': qid, 'dense_first_accepted_rank': ranks['dense'],
            'raw_CE_first_accepted_rank': old, 'composite_first_accepted_rank': new,
            'raw_CE_to_composite_first_accepted_rank_delta': new-old if old is not None else None,
            'classification': kind})
        for k in (1, 3, 5, 10, 20):
            if old is not None and old > k and new <= k: crossings[f'COMPOSITE_RECOVERED_TO_TOP{k}'].append(qid)
            if old is not None and old <= k and new > k: crossings[f'COMPOSITE_DEMOTED_OUT_OF_TOP{k}'].append(qid)
    return per, dict(Counter(x['classification'] for x in per)), crossings


def decision_k(system_metrics):
    def key(m): return tuple(m['hit'][str(k)] for k in (20, 10, 5)) + (m['mrr'],)
    b, c = key(system_metrics['raw-ce']), key(system_metrics['current-composite'])
    if b == c: return 'C. COMPOSITE IS EFFECTIVELY NEUTRAL — SIMPLIFYING TO RAW CE IS JUSTIFIED'
    # A/B report the frozen aggregate priority. Query-level conflicts remain fully visible.
    return ('A. CURRENT COMPOSITE IMPROVES G3 DENSE60 RERANKING' if c > b else
            'B. RAW CROSS-ENCODER IS BETTER THAN CURRENT COMPOSITE')
