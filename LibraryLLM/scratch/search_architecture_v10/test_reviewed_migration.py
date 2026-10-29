"""Versioned replacement assertions approved by an independent contract reviewer.

Original gold/assertions remain immutable and their six failures remain recorded.
These tests retain all original applicable fields except the reviewed decision.
"""
import json
from pathlib import Path
import pytest
from .parser import parse_query,executable,assess,matches

ROOT=Path(__file__).resolve().parents[2]
FACETS=[r['subject'] for r in json.loads((ROOT/'reports/search_v2a_facet_vocabulary.json').read_text(encoding='utf-8'))['results']]
GOLD={g['id']:g for g in map(json.loads,(ROOT/'reports/search_v2c_a_gold_queries.jsonl').read_text(encoding='utf-8').splitlines())}
C4=json.loads((ROOT/'reports/search_v2c_c4_reviewed_contract.json').read_text(encoding='utf-8'))

@pytest.mark.parametrize('case_id',['gold-036','gold-129','gold-130','gold-131','gold-132'])
def test_reviewed_typed_notice_retains_all_prior_field_assertions(case_id):
    g=GOLD[case_id];expected={**g['expected'],**C4['overrides'].get(case_id,{}),'decision_type':'EXECUTABLE_WITH_NOTICE'}
    p=parse_query(g['query'],FACETS);actual={**vars(p),'decision_type':p.decision['decision_type']}
    assert not {k:(v,actual.get(k)) for k,v in expected.items() if actual.get(k)!=v}
    assert executable(p) and p.corrections and assess(p)['policy']=='EXECUTE_WITH_NOTICE'
    assert p.decision['repair_notices'] and matches(p,{'subjects':p.subjects})
    assert not matches(p,{'subjects':['Unrelated']})

def test_reviewed_opaque_quoted_ellipsis_retains_literal_title_and_author():
    p=parse_query('titled "A ..."; by Alder Vale',FACETS)
    assert executable(p) and p.decision['decision_type']=='EXECUTABLE' and p.title_text=='a ...' and p.author_text=='alder vale'
    assert p.rating_min is None and not p.formats and not p.subjects
    assert matches(p,{'title':'A ...','authors':['Alder Vale']})
    assert not executable(parse_query('titled [not supplied]; by Alder Vale',FACETS))
