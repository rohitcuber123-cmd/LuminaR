"""Corpus safety invariants; no parser/evaluator execution on any partition."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from scripts.search_v2c_c2_benchmark import identity, read_rows, structure

R=Path('reports')

def test_sealed_corpus_contexts_and_families_are_disjoint():
    manifest=json.loads((R/'search_v2c_c2_benchmark_v2_manifest.json').read_text())
    scopes=json.loads((R/'search_v2c_c_scope_vocabularies.json').read_text())
    rows=[]
    for file in manifest['files']:
        path=Path(file['path'])
        assert hashlib.sha256(path.read_bytes()).hexdigest()==file['sha256']
        rows+=read_rows(path)
    assert len(rows)==7211
    assert len({identity(r,scopes) for r in rows})==len(rows)
    families=defaultdict(set);structures=defaultdict(set)
    for row in rows:
        families[row['family_id']].add(row['split']);structures[structure(row)].add(row['split'])
        assert row['benchmark_version']=='V2C-C-Benchmark-v2'
        assert not row.get('human_reviewed')
        assert not (row.get('exposure_status')=='EXPOSED_LEGACY_HOLDOUT' and row['split']=='heldout')
    assert all(len(v)==1 for v in families.values())
    assert all(len(v)==1 for v in structures.values())
    assert len([r for r in rows if r.get('exposure_status')=='EXPOSED_LEGACY_HOLDOUT'])==10


def test_alias_identity_does_not_merge_scope_or_action():
    scopes={'GLOBAL':{'capabilities':{'rating':True}},'PRIVATE_PATRON':{'capabilities':{'rating':True}}}
    row={'query_text':'Fiction rated above 4','search_mode':'semantic','scope_type':'GLOBAL','workspace_type':'GLOBAL'}
    assert identity(row,scopes)==identity({**row,'query_text':'  FICTION rated above 4  ','search_mode':'SMART'},scopes)
    assert identity(row,scopes)!=identity({**row,'scope_type':'PRIVATE_PATRON','workspace_type':'PATRON'},scopes)
    assert identity({**row,'expected_action':'deny_staff'},scopes)!=identity({**row,'expected_action':'revoke_member'},scopes)


def test_category_minima_count_unique_contexts():
    d=json.loads((R/'search_v2c_c2_category_counts.json').read_text())
    assert d['unique_cases']>=7100
    assert all(d['counts'][key]>=limit for key,limit in d['minimums'].items())
    assert d['duplicates_counted'] is False
